"""Compare saved qualified 7/30-day labels with directory boundaries."""
from pathlib import Path
import json
import pandas as pd

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
ledger=pd.read_csv(OUT/'boundary_ledger.csv')
parts=[]; counts=[]
for r in ledger.itertuples(index=False):
    path=ROOT/'results/runs/markov_input_20261025T095949_830292Z/release_labels'/f'{r.id}.parquet'
    f=pd.read_parquet(path,filters=[('reason_code','==',0),('horizon_days','in',[7,30]),('scenario','==','pooled'),('target','==','stopped')])
    origin=pd.to_datetime(f.origin_time_UTC,utc=True).map(lambda t:t.timestamp()).to_numpy(float)
    before=origin<r.official_start_epoch
    after=f.required_interval_end_epoch.to_numpy()>r.official_end_epoch
    f=f.assign(origin_before_official=before,required_end_after_official=after)
    for horizon,group in f.groupby('horizon_days'):
        counts.append(dict(id=r.id,horizon_days=int(horizon),qualified_pairs=len(group),before=int(group.origin_before_official.sum()),after=int(group.required_end_after_official.sum())))
    if (before|after).any():parts.append(f[before|after])
pd.DataFrame(counts).to_csv(OUT/'historical_pair_boundary_counts.csv',index=False)
flagged=pd.concat(parts,ignore_index=True) if parts else pd.DataFrame()
flagged.to_csv(OUT/'historical_boundary_pairs.csv',index=False)
print('historical flags',flagged[['id','origin_source_obs','horizon_days','origin_before_official','required_end_after_official']].to_dict('records'),flush=True)

# Roles across completed experiments, with no score recalculation.
runs=ROOT/'results/runs'
keys=['id','origin_source_obs','horizon_days']
role_files=[('seasonal_conditioning_s4_e1_primary_20261102T005104_943407Z','role_membership.parquet'),
            ('temporal_validation_s4_e2_primary_20261103T004920_642021Z','role_membership.parquet'),
            ('seasonal_information_s4_e3_primary_20261104T142729_626118Z','source_roles.parquet'),
            ('departure_direction_s4_e4_primary_20261104T153104_398790Z','roles.parquet'),
            ('exact_origin_s4_e7_primary_20261105T074326_829211Z','roles.parquet')]
roles=[]
for run,file in role_files:
    frame=pd.read_parquet(runs/run/file,filters=[('id','in',flagged.id.unique().tolist())])
    frame=frame.merge(flagged[keys],on=keys,validate='many_to_one')
    roles.append(frame.assign(run=run))
pd.concat(roles,ignore_index=True).to_csv(OUT/'boundary_pair_experiment_roles.csv',index=False)

primaries=['empirical_b2_20261029T121555_976173Z','adaptive_b2_b1_20261030T044950_931787Z',
           'b2_b1_e2_20261030T060621_291294Z','drifter_shrinkage_e3_20261030T074159_751985Z',
           'partial_weighting_e4_20261030T082826_141410Z','spatial_borrowing_s3_e1_20261030T114538_900248Z',
           'local_endpoint_adaptive_s3_e2_20261030T135819_234829Z','local_endpoint_quality_s3_e3_20261031T005527_091650Z',
           'local_endpoint_joint_s3_e4_20261031T021237_761696Z']
score_rows=[]
for run in primaries:
    saved=pd.read_parquet(runs/run/'heldout_scores.parquet',filters=[('id','in',flagged.id.unique().tolist())])
    match=['id','horizon_days','origin_cell_1','destination_cell_1']
    saved=saved.merge(flagged[match].drop_duplicates(),on=match,validate='many_to_one')
    cols=[c for c in match+['model','outer_fold','pair_count'] if c in saved]
    score_rows.append(saved[cols].assign(run=run))
pd.concat(score_rows,ignore_index=True).to_csv(OUT/'historical_score_row_presence.csv',index=False)
print('historical IDs scanned',len(ledger),'qualified pairs',sum(x['qualified_pairs'] for x in counts),'flagged pairs',len(flagged),flush=True)
