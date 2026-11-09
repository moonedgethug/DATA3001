import importlib
import json
import sys
import unittest
import tempfile
import subprocess
import time
import signal
from unittest.mock import patch
from pathlib import Path


def runtime():
    try:
        return importlib.import_module('data3001.modelling.continuous_models.conditional_mdn_s5_e3_runtime')
    except ModuleNotFoundError:
        raise AssertionError('MDN cumulative resource supervisor has not been implemented')


def test_remaining_counts_all_failed_and_completed_attempts():
    r=runtime()
    cfg={'seconds':{'pilot':10,'audit':8,'total':12}}
    ledger={'entries':[{'phase':'pilot','elapsed_seconds':4,'returncode':1},
                       {'phase':'audit','elapsed_seconds':3,'returncode':0}]}
    assert r.remaining(cfg,ledger,'pilot')==5
    assert r.remaining(cfg,ledger,'audit')==5


def test_supervisor_records_failure_and_preserves_cumulative_time(tmp_path):
    r=runtime()
    run={'results':tmp_path/'results','provenance':tmp_path/'provenance'}
    for p in run.values():p.mkdir()
    cfg={'seconds':{'pilot':10,'total':10},'rss_hard_gib':8,'storage_hard_gib':1}
    code=r.supervise(run,cfg,'pilot','expected_failure',[sys.executable,'-c','raise SystemExit(7)'])
    assert code==7
    ledger=json.loads((run['provenance']/'resource_ledger.json').read_text())
    assert ledger['active'] is None
    assert ledger['entries'][0]['elapsed_seconds']>0
    assert ledger['entries'][0]['returncode']==7


def test_supervisor_terminates_at_deadline(tmp_path):
    r=runtime()
    run={'results':tmp_path/'results','provenance':tmp_path/'provenance'}
    for p in run.values():p.mkdir()
    cfg={'seconds':{'pilot':0.3,'total':0.3},'rss_hard_gib':8,'storage_hard_gib':1}
    assert r.supervise(run,cfg,'pilot','timeout',[sys.executable,'-c','import time; time.sleep(5)'])!=0
    ledger=json.loads((run['provenance']/'resource_ledger.json').read_text())
    assert ledger['entries'][0]['stop_reason']=='time_budget'
    assert ledger['entries'][0]['elapsed_seconds']<2


def test_existing_active_receipt_prevents_parallel_budget_reset(tmp_path):
    r=runtime()
    run={'results':tmp_path/'results','provenance':tmp_path/'provenance'}
    for p in run.values():p.mkdir()
    r.atomic_json(run['provenance']/'resource_ledger.json',{'entries':[],'active':{'label':'running'}})
    cfg={'seconds':{'pilot':10,'total':10},'rss_hard_gib':8,'storage_hard_gib':1}
    with unittest.TestCase().assertRaisesRegex(RuntimeError, 'active'):
        r.supervise(run,cfg,'pilot','second',[sys.executable,'-c','pass'])


class RuntimeTests(unittest.TestCase):
    def test_disappearing_atomic_temporary_file_does_not_break_resource_scan(self):
        r=runtime()
        with tempfile.TemporaryDirectory() as d:
            target=Path(d)/'checkpoint.tmp';target.write_text('temporary')
            original=Path.stat;calls=[]
            def racing_stat(path,*a,**kw):
                if path==target:
                    calls.append(1)
                    if len(calls)==2:raise FileNotFoundError('simulated atomic rename')
                return original(path,*a,**kw)
            with patch.object(Path,'stat',racing_stat):
                r.storage_bytes({'results':Path(d)})

    def test_sigterm_supervisor_closes_receipt_and_stops_owned_child(self):
        import psutil
        r=runtime()
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);target=root/'child.pid'
            script="""import sys,json; from pathlib import Path
from data3001.modelling.continuous_models.conditional_mdn_s5_e3_runtime import supervise
p=Path(sys.argv[1]);run={'results':p/'results','provenance':p/'provenance'}
for f in run.values():f.mkdir()
code=\"import os,time,sys; from pathlib import Path; Path(sys.argv[1]).write_text(str(os.getpid())); time.sleep(20)\"
supervise(run,{'seconds':{'pilot':10,'total':10},'rss_hard_gib':8,'storage_hard_gib':1},'pilot','signal',[sys.executable,'-c',code,str(p/'child.pid')])
"""
            parent=subprocess.Popen([sys.executable,'-c',script,str(root)],stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            pid=None
            try:
                deadline=time.monotonic()+5
                while not target.exists() and time.monotonic()<deadline:time.sleep(.02)
                self.assertTrue(target.exists());pid=int(target.read_text())
                parent.send_signal(signal.SIGTERM);parent.wait(timeout=3)
                alive=psutil.pid_exists(pid) and psutil.Process(pid).status()!=psutil.STATUS_ZOMBIE
                self.assertFalse(alive,'SIGTERM left an unbudgeted child')
                ledger=json.loads((root/'provenance/resource_ledger.json').read_text())
                self.assertIsNone(ledger['active'])
            finally:
                if parent.poll() is None:parent.kill();parent.wait()
                if pid is not None and psutil.pid_exists(pid):
                    try:psutil.Process(pid).kill()
                    except psutil.NoSuchProcess:pass
    def test_normal_exit_does_not_leave_unbudgeted_grandchild(self):
        import psutil
        r=runtime()
        with tempfile.TemporaryDirectory() as d:
            run={'results':Path(d)/'results','provenance':Path(d)/'provenance'}
            for p in run.values():p.mkdir()
            target=Path(d)/'child.pid'
            script="import subprocess,sys; from pathlib import Path; c=subprocess.Popen([sys.executable,'-c','import time; time.sleep(20)']); Path(sys.argv[1]).write_text(str(c.pid))"
            cfg={'seconds':{'pilot':5,'total':5},'rss_hard_gib':8,'storage_hard_gib':1}
            code=r.supervise(run,cfg,'pilot','parent_exit',[sys.executable,'-c',script,str(target)])
            pid=int(target.read_text())
            try:
                alive=psutil.pid_exists(pid) and psutil.Process(pid).status()!=psutil.STATUS_ZOMBIE
                self.assertFalse(alive,'Supervisor left an unbudgeted descendant after leader exit')
            finally:
                if psutil.pid_exists(pid):
                    try:psutil.Process(pid).kill()
                    except psutil.NoSuchProcess:pass
    def test_remaining(self):
        test_remaining_counts_all_failed_and_completed_attempts()
    def test_failure(self):
        with tempfile.TemporaryDirectory() as d:
            test_supervisor_records_failure_and_preserves_cumulative_time(Path(d))
    def test_deadline(self):
        with tempfile.TemporaryDirectory() as d:
            test_supervisor_terminates_at_deadline(Path(d))
    def test_active_lock(self):
        with tempfile.TemporaryDirectory() as d:
            test_existing_active_receipt_prevents_parallel_budget_reset(Path(d))
