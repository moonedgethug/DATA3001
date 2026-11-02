"""Planning-only audit of sealed development labels; no forecasts or model fitting."""
from pathlib import Path
import hashlib, json
import numpy as np
import pandas as pd

ROOT = Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')
OUT = Path('/tmp/data3001_seasonal_support_20261102')
OUT.mkdir(exist_ok=True)
RUN = ROOT/'results/runs/markov_input_20261025T095949_830292Z'
RECEIPT = ROOT/'provenance/runs'/RUN.name/'outputs.json'
receipt=json.loads(RECEIPT.read_text())
assert receipt['completed'] is True and receipt['final_test_access'] is False
inventory={}
def verified(p):
    data=p.read_bytes(); digest=hashlib.sha256(data).hexdigest()
    key=p.relative_to(ROOT).as_posix()
    assert receipt['output_sha256'][key]==digest, key
    inventory[key]=digest
    return p
manifest=json.loads((ROOT/'configs/dataset_manifest.json').read_text())
dev={int(k) for k,v in manifest['records'].items() if v['pool']=='train'}
source=pd.read_csv(verified(RUN/'source_ID_summary.csv'))
assert set(source.id)==dev and len(dev)==3224
for row in source.itertuples(index=False):
    ref=manifest['records'][str(row.id)]
    assert row.source_sha256==ref['sha256'] and row.retained_rows==ref['rows']
paths=sorted((RUN/'release_labels').glob('*.parquet'))
assert {int(p.stem) for p in paths}==set(source.loc[source.R_origins.gt(0),'id'])
cols=['id','origin_source_obs','origin_time_UTC','target_epoch','required_interval_end_epoch','horizon_days','origin_cell_1','departure_season','destination_cell_1','reason_code','target','scenario','tolerance_hours']
parts=[]
for p in paths:
    with verified(p).open('rb') as f:
        a=pd.read_parquet(f,columns=cols)
    assert a.id.eq(int(p.stem)).all() and int(p.stem) in dev
    assert a.target.eq('stopped').all() and a.scenario.eq('pooled').all() and a.tolerance_hours.eq(0).all()
    assert not a.duplicated(['id','origin_source_obs','horizon_days']).any()
    parts.append(a.loc[a.reason_code.eq(0)&a.horizon_days.isin([7,30])].copy())
df=pd.concat(parts,ignore_index=True)
assert not df.duplicated(['id','origin_source_obs','horizon_days']).any()
assert df.id.isin(dev).all()
assert ((df.origin_time_UTC.dt.month%12)//3==df.departure_season).all()
epoch=(df.origin_time_UTC-pd.Timestamp('1970-01-01',tz='UTC')).dt.total_seconds()
assert (epoch+86400*df.horizon_days==df.target_epoch).all()
assert np.isfinite(df.required_interval_end_epoch).all()
keys=['id','horizon_days','origin_cell_1','destination_cell_1']
counts=pd.read_parquet(verified(RUN/'release_counts_by_id.parquet'))
counts=counts.loc[counts.horizon_days.isin([7,30])].sort_values(keys).reset_index(drop=True)
rebuilt=df.groupby(keys).size().reset_index(name='pair_count').sort_values(keys).reset_index(drop=True)
pd.testing.assert_frame_equal(counts,rebuilt,check_dtype=False,check_exact=True)
assert df.groupby('horizon_days').size().to_dict()=={7:303288,30:268998}
all_origins=sorted(df.origin_cell_1.unique().tolist())
assert len(all_origins)==37

def ts(s): return pd.Timestamp(s,tz='UTC')
def subset(lo,hi): return df.loc[df.origin_time_UTC.ge(ts(lo))&df.origin_time_UTC.lt(ts(hi))].copy()
def summary(a):
    g=a.groupby(['origin_cell_1','departure_season']).id.nunique()
    nids=g.reindex(pd.MultiIndex.from_product([all_origins,range(4)],names=g.index.names),fill_value=0)
    pairs=a.groupby(['origin_cell_1','departure_season','id']).size()
    totals=pairs.groupby(level=[0,1]).sum()
    dominant=pairs.groupby(level=[0,1]).max()/totals
    return {'pairs':len(a),'ids':int(a.id.nunique()),'origins':int(a.origin_cell_1.nunique()),
        'id_origin_units':len(a[['id','origin_cell_1']].drop_duplicates()),
        'first_origin':str(a.origin_time_UTC.min()),'last_origin':str(a.origin_time_UTC.max()),
        'cell_season_total':len(nids),'cell_season_empty':int(nids.eq(0).sum()),
        'cell_season_1_to_4_ids':int(nids.between(1,4).sum()),'cell_season_5_to_9_ids':int(nids.between(5,9).sum()),
        'cell_season_10plus_ids':int(nids.ge(10).sum()),
        'median_ids_per_supported_cell_season':float(g.median()),
        'median_dominant_id_pair_share':float(dominant.median())}

cohorts={}
for name,lo,hi in [('1998_2001','1998-01-01','2002-01-01'),('2002_2011','2002-01-01','2012-01-01'),('2012_2022','2012-01-01','2023-01-01'),('full_development','1900-01-01','2100-01-01')]:
    z=subset(lo,hi)
    for h in [7,30]: cohorts[f'{name}_{h}d']=summary(z.loc[z.horizon_days.eq(h)])
assert sum(cohorts[f'{name}_{h}d']['pairs'] for name in ['1998_2001','2002_2011','2012_2022'] for h in [7,30])==len(df)
annual=df.assign(year=df.origin_time_UTC.dt.year).groupby(['horizon_days','year']).agg(pairs=('id','size'),ids=('id','nunique'),origins=('origin_cell_1','nunique')).reset_index()
annual.to_csv(OUT/'annual_support.csv',index=False)

cut=ts('2020-01-01')
val=subset('2020-01-01','2023-01-01')
val_ids=set(val.id)
roles=[]; support_rows=[]; scenarios={}
for name,lo in [('recent_2012_train','2012-01-01'),('all_past_train','1998-01-01')]:
    train=subset(lo,'2020-01-01')
    available=train.loc[train.required_interval_end_epoch.lt(cut.timestamp())].copy()
    clean=available.loc[~available.id.isin(val_ids)].copy()
    assert set(clean.id).isdisjoint(val_ids)
    assert clean.required_interval_end_epoch.lt(cut.timestamp()).all()
    for h in [7,30]:
        t=train.loc[train.horizon_days.eq(h)]; av=available.loc[available.horizon_days.eq(h)]; tr=clean.loc[clean.horizon_days.eq(h)]; v=val.loc[val.horizon_days.eq(h)].copy()
        r={'before_boundary_purge':summary(t),'after_label_availability_purge':summary(av),'train_final':summary(tr),'validation':summary(v),
           'label_boundary_purged_pairs':len(t)-len(av),'whole_id_purged_pairs':len(av)-len(tr),
           'overlapping_ids_after_label_purge':sorted(set(av.id)&val_ids)}
        annual_n=tr.groupby('origin_cell_1').id.nunique()
        season_n=tr.groupby(['origin_cell_1','departure_season']).id.nunique()
        v['annual_ids']=v.origin_cell_1.map(annual_n).fillna(0).astype(int)
        v['season_ids']=pd.MultiIndex.from_frame(v[['origin_cell_1','departure_season']]).map(season_n).fillna(0).astype(int)
        def weight(a):
            pair_n=a.groupby(['origin_cell_1','id']).id.transform('size')
            ids_n=a.groupby('origin_cell_1').id.transform('nunique')
            return 1/(a.origin_cell_1.nunique()*ids_n*pair_n)
        v['weight']=weight(v)
        assert np.isclose(v.weight.sum(),1)
        r['validation_annual_unsupported_pairs']=int(v.annual_ids.eq(0).sum())
        r['validation_annual_unsupported_weight']=float(v.loc[v.annual_ids.eq(0),'weight'].sum())
        scored=v.loc[v.annual_ids.gt(0)].copy()
        scored['weight']=weight(scored)
        assert np.isclose(scored.weight.sum(),1)
        r['common_scored_pairs']=len(scored); r['common_scored_ids']=int(scored.id.nunique());r['common_scored_origins']=int(scored.origin_cell_1.nunique())
        for label,mask in [('season_empty',scored.season_ids.eq(0)),('season_1_to_4_ids',scored.season_ids.between(1,4)),('season_5_to_9_ids',scored.season_ids.between(5,9)),('season_10plus_ids',scored.season_ids.ge(10))]:
            r[label+'_pairs']=int(mask.sum()); r[label+'_weight']=float(scored.loc[mask,'weight'].sum())
        r['validation_season_summary']={str(s):{'pairs':len(q),'ids':int(q.id.nunique()),'origins':int(q.origin_cell_1.nunique()),'weight':float(q.weight.sum())} for s,q in v.groupby('departure_season')}
        scenarios[f'{name}_{h}d']=r
        roles.append(tr.assign(role='train',scenario_name=name)[['id','horizon_days','origin_source_obs','origin_time_UTC','origin_cell_1','departure_season','role','scenario_name']])
        for s,q in tr.groupby(['origin_cell_1','departure_season']):
            support_rows.append({'scenario':name,'horizon_days':h,'origin_cell_1':int(s[0]),'departure_season':int(s[1]),'pairs':len(q),'ids':int(q.id.nunique()),'years':int(q.origin_time_UTC.dt.year.nunique()),'dominant_id_share':float(q.id.value_counts().iloc[0]/len(q))})
pd.DataFrame(support_rows).to_csv(OUT/'training_cell_season_support.csv',index=False)
report={'status':'PLANNING_SUPPORT_AUDIT_ONLY','model_fitting':False,'final_test_access':False,'release':manifest['version'],
    'interval_convention':'[start,end); 2022 means through available 2022 observations, end exclusive 2023-01-01',
    'training_label_availability':'required_interval_end_epoch < 2020-01-01T00:00:00Z',
    'whole_id_rule':'All IDs with any eligible 7/30-day validation origin in [2020,2023) excluded from both training horizons.',
    'cell_season_denominator':'37 globally observed development origins times 4 UTC seasons; not all 54 indexed origins',
    'weights':'Equal eligible times per ID/origin, equal IDs per origin, equal origins; support bins are diagnostics, not adequacy thresholds.',
    'validation_ids_union':len(val_ids),'cohorts':cohorts,'chronological':scenarios,'inventory_sha256':inventory,
    'source_receipt_sha256':hashlib.sha256(RECEIPT.read_bytes()).hexdigest(),
    'manifest_sha256':hashlib.sha256((ROOT/'configs/dataset_manifest.json').read_bytes()).hexdigest()}
(OUT/'audit.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps({k:v for k,v in report.items() if k not in ['inventory_sha256','chronological']},indent=2))
print('CHRONOLOGICAL')
print(json.dumps(scenarios,indent=2))
