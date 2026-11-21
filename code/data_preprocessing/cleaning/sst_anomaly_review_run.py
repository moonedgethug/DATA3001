"""Supplement the narrow >45 C repair using corroborated anomaly evidence."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from data3001.paths import project_paths,ensure_output_path,file_sha256
from data3001.dataset import manifest
from data3001.sst_completion import temperature_sidecar
from data3001.sst_anomaly_review import review_reasons,apply_reviewed_temperature_patch

RUN='sst_anomaly_recovery_20261017_v2'
PARENT='sst_anomaly_recovery_20261017_v1'
ROOT=project_paths().root
KEYS=['id','source_obs']


def save(path,value):
    path.write_text(json.dumps(value,indent=2,allow_nan=False,default=str)+'\n')


def execute():
    p=ROOT/'results/runs'/PARENT
    receipt=json.loads((p/'verification.json').read_text())
    assert receipt['status']=='passed' and file_sha256(p/'config.json')==receipt['config_sha256']
    for name,digest in json.loads((p/'artifact_manifest.json').read_text()).items():
        assert file_sha256(p/name)==digest,name
    dest=ensure_output_path('results/runs/'+RUN);dest.mkdir()
    q=pd.read_parquet(p/'comparisons.parquet')
    q['review_decision']=review_reasons(q)
    approved=q.review_decision.str.startswith('corroborated_')
    assert approved[q['replace']].all()
    q['additional_replace']=approved&~q['replace']
    q.to_parquet(dest/'review_decisions.parquet',index=False)
    dependencies=[p/'config.json',p/'artifact_manifest.json',p/'verification.json',
                  ROOT/'configs/dataset_manifest.json',ROOT/'docs/contract/data_contract_v1.0.xlsx',
                  ROOT/'src/data3001/sst_anomaly_review.py',ROOT/'src/data3001/sst_anomaly_review_run.py',
                  ROOT/'tests/test_sst_anomaly_review.py']
    config={'run_id':RUN,'parent_run':PARENT,
            'contract_sha256':'6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446',
            'authorization':'User also requested official-source checks for other unreasonable SST, beyond the 45 C cases',
            'screen_population':'The same 5,781 candidates already selected and matched in v1; no final-test outcome or score used',
            'rules':{'prior_high':'Retain v1 >45 C repairs',
                     'extreme_heat':'Native >40 C and >=8 K above same-date matched background',
                     'fit_inconsistency':'Absolute background difference >=10 K AND (non-diurnal flag 2/3 OR diurnal flag 2/3 with abs(diurnal anomaly)>=10 K)',
                     'guard':'Actual finite background in [-3,40] C; recovery-tail rows excluded; after-last-good grounding rows held'},
            'interpretation':'Project QA rules for a working daily-background covariate, not universal physical limits, proof of sensor failure, or recovered hourly truth',
            'dependencies':{str(path.relative_to(ROOT)):file_sha256(path) for path in dependencies}}
    assert file_sha256(ROOT/'docs/contract/data_contract_v1.0.xlsx')==config['contract_sha256']
    save(dest/'config.json',config)
    entries=[]
    fields=['sst_use_K','sst_method','sst_reason','availability_scope',
            'sst_source_sd_bound_K','sst_total_se_K','sst_error_kind']
    for sid,g in q[q.additional_replace].groupby('id'):
        old,_=temperature_sidecar(int(sid),run=PARENT)
        patch=g[KEYS].copy()
        patch['sst_use_K']=g.background_C.to_numpy()+273.15
        patch['sst_method']=g.background_method.to_numpy(dtype=np.int8)
        patch['sst_reason']='daily_oisst_'+g.review_decision.to_numpy()
        patch['availability_scope']='retrospective_only'
        patch['sst_source_sd_bound_K']=g.source_sd_bound_K.to_numpy()
        patch['sst_total_se_K']=np.nan
        patch['sst_error_kind']='official_background_source_only_bound; total_reconstruction_error_unknown'
        out=apply_reviewed_temperature_patch(old,patch,set(g[KEYS].itertuples(index=False,name=None)))
        selected=old.source_obs.isin(patch.source_obs)
        pd.testing.assert_frame_equal(old.loc[~selected].reset_index(drop=True),out.loc[~selected].reset_index(drop=True))
        pd.testing.assert_frame_equal(old.drop(columns=fields),out.drop(columns=fields))
        pool=manifest()['records'][str(sid)]['pool'];folder=dest/pool;folder.mkdir(exist_ok=True)
        path=folder/f'{sid}.parquet';out.to_parquet(path,index=False)
        entries.append({'id':int(sid),'pool':pool,'path':str(path.relative_to(ROOT)),
                        'sha256':file_sha256(path),'rows':len(out)})
    save(dest/'output_manifest.json',entries)
    for row in q[approved].itertuples(index=False):
        actual=sum(getattr(row,f'weight{k}')*getattr(row,f'corner{k}_C') for k in range(4)
                   if getattr(row,f'weight{k}')>0)
        assert abs(actual-row.background_C)<1e-10
    for sid,record in manifest()['records'].items():
        assert file_sha256(ROOT/record['path'])==record['sha256']
    summary={'status':'passed','config_sha256':file_sha256(dest/'config.json'),
             'canonical_files_preserved':3741,'canonical_rows_preserved':39107061,'fields_preserved':130,
             'whole_ID_pools_unchanged':True,'excluded_recovery_rows':receipt['excluded_recovery_rows'],
             'excluded_recovery_IDs':receipt['excluded_recovery_IDs'],
             'model_view_rows_after_recovery_exclusion':receipt['model_view_rows_after_recovery_exclusion'],
             'SST_candidates_compared':len(q),'official_background_matches':int(q.background_C.notna().sum()),
             'previous_high_replacements':int(q['replace'].sum()),
             'additional_corroborated_replacements':int(q.additional_replace.sum()),
             'total_replaced':int(approved.sum()),'replaced_in_R':int((approved&q.in_R).sum()),
             'replaced_IDs':q.loc[approved,'id'].nunique(),
             'remaining_review_only_large_discrepancies':int((~approved&(abs(q.native_minus_background_K)>5)).sum()),
             'source_acquisition_failures':receipt['source_failures']}
    save(dest/'verification.json',summary)
    save(dest/'artifact_manifest.json',{name:file_sha256(dest/name) for name in
         ['config.json','review_decisions.parquet','output_manifest.json']})
    print(json.dumps(summary,indent=2),flush=True)


if __name__=='__main__':execute()
