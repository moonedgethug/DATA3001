"""Approved O1 staged resource trial; never launches full CV.

The process retains verified arrays between stages. Waiting for conditional
engineering work consumes no real-data execution budget. Every stage execution,
including a failed call, is recorded against its original cumulative allowance.
"""
import time
PROCESS_START=time.monotonic()
import os,sys,json,signal,traceback,resource,shutil,importlib
from datetime import datetime,timezone
from pathlib import Path
import numpy as np
import pandas as pd
from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_json,save_frame,_seal
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard,load_inputs,verify_file
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import base_allowlist,Geometry,neighbours,source_hashes
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_inputs import prepared_allowlist,load_prepared,as_query,ActualOriginKernel
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1 import G1Kernel,ExclusiveTimer
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_profile import ProfiledReference

OLD_RUN='actual_origin_disp_s3_e5_pilot_20261031T123704_492621Z'


class TrialStop(RuntimeError):pass


class Trial:
    def __init__(self):
        self.paths=project_paths();self.config=json.loads((self.paths.root/'configs/actual_origin_displacement_s3_e5_o1.json').read_text())
        self.run_id='actual_origin_disp_s3_e5_o1_'+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
        self.run=self.paths.create_run(self.run_id,self.config)
        self.used={k:0. for k in 'ABCD'};self.stage=None;self.started=None;self.serial=0
        self.timings=[];self.reference={};self.contexts={};self.results={};self.inventory={}
        self.status='RUNNING';self.reason='';self.phases=[];self.kernels={};self.variant_scores=[]
        self.old_root=self.paths.root/'results/runs'/OLD_RUN
        old_receipt=self.paths.root/'provenance/runs'/OLD_RUN/'outputs.json'
        allowed=base_allowlist(self.paths,self.config)+prepared_allowlist(self.paths,self.config)+[old_receipt,self.old_root/'pilot_roster.csv',self.old_root/'workload.csv']
        self.guard=ExperimentGuard(self.paths,self.run,allowed);sys.addaudithook(self.guard)
        self.last_check=0.;self.last_message=0.
        approval=json.loads((self.paths.root/self.config['optimisation_approval']).read_text())
        if approval.get('approved') is not True or approval['plan_sha256']!=self.config['optimisation_plan_sha256']:raise PermissionError('Missing O1 approval')
        self.write('approval',approval,provenance=True)
        if file_sha256(self.paths.root/self.config['optimisation_plan'])!=self.config['optimisation_plan_sha256']:raise ValueError('Plan changed')
        self.paths.publish(self.run['provenance']/'approved_optimisation_plan.md',lambda f:f.write((self.paths.root/self.config['optimisation_plan']).read_bytes()))
        if shutil.disk_usage(self.paths.root).free<self.config['max_new_artifact_bytes']:raise TrialStop('Insufficient free disk')
        signal.signal(signal.SIGALRM,self.alarm)
        print(json.dumps(dict(run_id=self.run_id,full_experiment_authorised=False)),flush=True)

    def write(self,name,value,provenance=False):
        save_json(self.paths,self.run['provenance' if provenance else 'results']/(name+'.json'),value)

    def frame(self,name,table):save_frame(self.paths,self.run['results']/(name+'.csv'),table)

    def alarm(self,*_):raise TrialStop('Stage '+str(self.stage)+' cumulative execution cap')

    def check(self):
        now=time.monotonic()
        if self.stage and now-self.started+self.used[self.stage]>=self.config['stage_caps'][self.stage]:self.alarm()
        if now-self.last_check>=5:
            rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
            if rss>self.config['max_rss_bytes']:raise TrialStop('Combined 8 GiB memory cap')
            size=sum(p.stat().st_size for d in self.run.values() for p in d.rglob('*') if p.is_file())
            if size>self.config['max_new_artifact_bytes']:raise TrialStop('20 GiB artifact cap')
            self.last_check=now
        if now-self.last_message>20:
            print(json.dumps(dict(stage=self.stage,stage_seconds=round(now-self.started+self.used[self.stage],2),completed_timings=len(self.timings))),flush=True)
            self.last_message=now

    def execute(self,stage,fn,include_startup=False):
        if self.status!='RUNNING':raise TrialStop('Trial already stopped')
        self.stage=stage;self.started=PROCESS_START if include_startup else time.monotonic()
        remaining=min(self.config['stage_caps'][stage]-self.used[stage],7200-sum(self.used.values()))-(time.monotonic()-self.started)
        if remaining<=0:self.alarm()
        signal.setitimer(signal.ITIMER_REAL,remaining)
        try:
            self.snapshot(stage);fn();self.check()
        except TrialStop as e:self.status='CAPACITY_NOT_ESTABLISHED';self.reason=str(e)
        except Exception as e:
            self.status='INTEGRITY_FAILED';self.reason=f'{type(e).__name__}: {e}';traceback.print_exc()
        finally:
            signal.setitimer(signal.ITIMER_REAL,0)
            elapsed=time.monotonic()-self.started;self.used[stage]+=elapsed;self.serial+=1
            self.phases.append(dict(stage=stage,elapsed_seconds=elapsed,status=self.status))
            self.write(f'budget_{self.serial:02d}',dict(used_seconds=self.used,phases=self.phases,status=self.status,reason=self.reason))
            self.frame(f'timings_{self.serial:02d}',pd.DataFrame(self.timings))
            self.stage=None;self.started=None
        print(json.dumps(dict(stage_finished=stage,status=self.status,reason=self.reason,used_seconds=self.used)),flush=True)

    def snapshot(self,stage):
        sources=source_hashes(self.paths)
        self.write(f'source_{stage}_{self.serial:02d}',sources,provenance=True)
        for rel in sources:
            self.paths.publish(self.run['provenance']/f'code_{stage}_{self.serial:02d}'/rel,lambda f,rel=rel:f.write((self.paths.root/rel).read_bytes()))

    def subset(self,row):
        q=as_query(row)
        return self.donors[(self.donors.horizon_days==q.horizon)&self.donors.origin_cell_1.isin(neighbours(q.origin))&self.donors.fold.ne(q.fold)]

    def fitting(self,row):return self.folds.loc[self.folds.outer_fold.ne(row.fold),'id'].tolist()

    def save_outcomes(self,name,out,why):
        self.paths.publish(self.run['results']/(name+'.npz'),lambda f:np.savez_compressed(f,destination=out,reason=why))

    def stage_a(self):
        tick=time.monotonic()
        self.counts,self.folds,self.origins,self.destinations,_,self.inventory=load_inputs(self.paths,self.config)
        self.geometry=Geometry.load(self.paths,self.destinations.cell)
        if file_sha256(self.paths.asset('transport_D'))!='57fcad5061e869e47f27b3a6f11041bd3e655ffd9dbab513e30473824b395da8':raise ValueError('Pinned D changed')
        self.tracks,self.donors,self.queries=load_prepared(self.paths,self.config,self.counts,self.folds,self.geometry,self.inventory,self.check)
        receipt=json.loads((self.paths.root/'provenance/runs'/OLD_RUN/'outputs.json').read_text())
        for name in ('pilot_roster.csv','workload.csv'):verify_file(self.paths,self.old_root/name,receipt['output_sha256'],self.inventory)
        self.workload=pd.read_csv(self.old_root/'workload.csv');roster=pd.read_csv(self.old_root/'pilot_roster.csv')
        self.roster=self.build_roster(roster)
        self.frame('roster',self.roster);self.frame('workload',self.workload)
        self.write('roster_freeze',dict(outcome_independent=True,roster_sha256=file_sha256(self.run['results']/'roster.csv')),True)
        self.write('input_inventory',self.inventory,True)
        self.setup_seconds=time.monotonic()-tick
        self.write('setup',dict(seconds=self.setup_seconds,queries=len(self.queries),donors=len(self.donors)))
        self.reference_kernel=ActualOriginKernel(self.geometry,self.tracks)
        prof=ProfiledReference(self.geometry,self.tracks)
        for row in self.roster[self.roster.calibration].itertuples(index=False):
            self.check();q=as_query(row);don=self.subset(row);ids=self.fitting(row)
            tick=time.monotonic();out,why,counts=self.reference_kernel.classify(q,don,ids,check=self.check);seconds=time.monotonic()-tick
            self.reference[row.query_index]=(out,why);self.save_outcomes(f'reference_{row.query_index:03d}',out,why)
            self.timings.append(dict(stage='A',variant='reference',batch=2048,query_index=row.query_index,horizon=q.horizon,origin=q.origin,coastal=row.coastal,seconds=seconds,**counts))
            prof.timer=ExclusiveTimer();tick=time.monotonic();a,b,_=prof.classify(q,don,ids,check=self.check);instrumented=time.monotonic()-tick
            np.testing.assert_array_equal(out,a);np.testing.assert_array_equal(why,b)
            self.write(f'profile_{row.query_index:03d}',dict(query_index=row.query_index,plain_seconds=seconds,instrumented_seconds=instrumented,overhead_fraction=instrumented/seconds-1,exclusive=prof.timer.rows,residual_seconds=instrumented-sum(v['seconds'] for v in prof.timer.rows.values())))
            print(json.dumps(dict(reference_query=row.query_index,seconds=seconds,instrumented_seconds=instrumented)),flush=True)

    def build_roster(self,old):
        old=old.copy();old['calibration']=False;old['parity_validation']=False
        meta=self.workload.set_index(['horizon_days','origin_cell_1']).coastal
        old['coastal']=[bool(meta.loc[(r.horizon_days,r.origin_cell_1)]) for r in old.itertuples()]
        for h in (7,30):
            for coast in (False,True):
                w=self.workload[(self.workload.horizon_days==h)&self.workload.coastal.eq(coast)].sort_values(['pilot_work_product','origin_cell_1'],ascending=[False,True])
                origin=int(w.iloc[0].origin_cell_1)
                g=old[(old.horizon_days==h)&old.origin_cell_1.eq(origin)].sort_values(['id','origin_source_obs'])
                old.loc[[g.index[0],g.index[-1]],'calibration']=True
                g=old[(old.horizon_days==h)&old.coastal.eq(coast)&~old.calibration].sort_values(['origin_cell_1','id','origin_source_obs'])
                old.loc[g.index[0],'parity_validation']=True
        extra=[]
        for h in (7,30):
            d=self.donors[self.donors.horizon_days.eq(h)]
            for fold in (0,2,3,4):
                fit=d[d.fold.ne(fold)];held=d[d.fold.eq(fold)];options=[]
                for origin,g in held.groupby('origin_cell_1'):
                    if not fit.origin_cell_1.eq(origin).any():continue
                    n=int(fit.origin_cell_1.isin(neighbours(origin)).sum())
                    if n:options.append((len(g)*n,int(origin)))
                _,origin=sorted(options,key=lambda x:(-x[0],x[1]))[0]
                r=self.queries[(self.queries.horizon_days==h)&self.queries.fold.eq(fold)&self.queries.origin_cell_1.eq(origin)].sort_values(['id','origin_source_obs']).iloc[0].to_dict()
                r.update(calibration=False,parity_validation=False,coastal=bool(meta.loc[(h,origin)]));extra.append(r)
        result=pd.concat([old,pd.DataFrame(extra)],ignore_index=True);result['query_index']=np.arange(len(result))
        if len(result)!=58 or result.calibration.sum()!=8 or result.parity_validation.sum()!=4:raise AssertionError('Frozen roster contract')
        return result

    def finish(self):
        if self.status=='RUNNING':self.status='TRIAL_COMPLETED'
        rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*(1 if sys.platform=='darwin' else 1024)
        result=dict(run_id=self.run_id,status=self.status,reason=self.reason,used_seconds=self.used,total_execution_seconds=sum(self.used.values()),peak_rss_bytes=rss,full_experiment_started=False,scientific_accuracy_results_available=False,denied_accesses=self.guard.denied,canonical_reads=len(self.guard.read_ids),final_test_access=False)
        self.write('trial',result);self.frame('timings',pd.DataFrame(self.timings))
        self.write('opened_inputs',sorted(str(p.relative_to(self.paths.root)) for p in self.guard.opened_inputs),True)
        _seal(self.paths,self.run,result);print(json.dumps(result,indent=2),flush=True)


def main():
    t=Trial();t.execute('A',t.stage_a,include_startup=True)
    while t.status=='RUNNING':
        print('PAUSED_FOR_STAGE_COMMAND',flush=True)
        command=sys.stdin.readline().strip()
        if command in ('','FINISH'):break
        if command not in ('B1','B2','B3','C','D'):raise ValueError('Unknown stage command')
        module=importlib.import_module('data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1_trial')
        fn=getattr(module,'stage_'+command.lower())
        t.execute(command[0],lambda:fn(t))
    t.finish()


if __name__=='__main__':main()
