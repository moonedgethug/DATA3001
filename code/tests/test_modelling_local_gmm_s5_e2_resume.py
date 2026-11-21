"""Formal scorer integration; synthetic data, never a model experiment."""
import copy
import gzip
import json
import tempfile
import unittest
from pathlib import Path
import pandas as pd
from test_modelling_local_gmm_s5_e2_scoreopt import packets
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as pipe
from data3001.modelling.continuous_models import local_gmm_s5_e2_scoreopt as optimized


class PublishFiles:
    def publish(self,path,writer):
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as f:writer(f)


def record():
    return dict(role='C_T0',query_position=0,id=99,origin_source_obs=1,horizon_days=7,
        origin_time_UTC='2014-01-01',pairs=8000,independent_ids=20,largest_id_share=.2,
        ci_unavailable_mass=0.,key=['C_T0',99,1,7],models={str(k):v for k,v in packets().items()})


class ResumeIntegrationTests(unittest.TestCase):
    def setUp(self):self.before=pipe.STATE.copy()
    def tearDown(self):pipe.STATE.clear();pipe.STATE.update(self.before)

    def test_explicit_native_backend_cannot_be_silently_ignored(self):
        pipe.STATE.clear();pipe.STATE.update(K=[1,2,3],cfg={'energy_count':8192,'score_native_path':'/missing/score.dylib'})
        with self.assertRaises(OSError):pipe.energy_rows(record(),[-75.,35.])

    def test_integrated_rows_preserve_old_scores_fallback_and_metadata(self):
        r=record();r['models']['3']=dict(copy.deepcopy(r['models']['1']),fallback=True)
        pipe.STATE.clear();pipe.STATE.update(K=[1,2,3],cfg={'energy_count':8192})
        expected=pipe.energy_rows(r,[-75.,35.])
        with tempfile.TemporaryDirectory() as d:
            lib=optimized.compile_kernel(Path(d)/'score.dylib');pipe.STATE['cfg']['score_native_path']=str(lib)
            self.assertEqual(pipe.energy_rows(r,[-75.,35.]),expected)

    def test_energy_batch_does_not_require_or_recompute_donor_lineage(self):
        with tempfile.TemporaryDirectory(dir=pipe.ROOT/'results') as d:
            base=Path(d);run={'results':base/'results','provenance':base/'provenance'};files=pipe.batch_paths(run,'C_T0',0)
            files['parameters'].parent.mkdir(parents=True)
            files['parameters'].write_bytes(gzip.compress(json.dumps([record()]).encode()))
            guard=type('AccessRecord',(),{'outcomes_read':False,'denied':[]})()
            lib=optimized.compile_kernel(base/'score.dylib')
            pipe.STATE.clear();pipe.STATE.update(paths=PublishFiles(),run=run,role='C_T0',mode='energy',
                cfg={'energy_count':8192,'score_native_path':str(lib)},K=[1,2,3],guard=guard,
                target=pd.DataFrame([{'endpoint_lon':-75.,'endpoint_lat':35.}]))
            receipt=pipe.work_batch((0,0,1))
            self.assertEqual(receipt['cases'],1)
            out=pd.read_parquet(files['energy']);self.assertEqual(list(out.model),[1,2,3])
            self.assertFalse(files['lineage'].exists())
