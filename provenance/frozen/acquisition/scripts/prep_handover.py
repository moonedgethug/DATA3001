"""Versioned architecture-audit additions. No acquisition or model fitting.

Baseline data products and freeze records are read-only. Native depth metadata
are audit strata, not a newly adopted primary cohort filter.
"""
import argparse
import importlib.util
import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import duckdb
import shapely as sh
from shapely.geometry import box, shape
from pyproj import Geod
from prep_io import BASE, OUT, Source, now, sha, save_json, parquet
from prep_geometry import mask, region_R

ROOT=OUT/'remediation_20261013'
GEOD=Geod(ellps='WGS84')
LAG_KEYS=['split','cell','season','days','scenario','target']
METADATA_KEYS=['depth_stratum','raw_depth_m','typebuoy','location_type']
SEASON_NAMES={-1:'annual',0:'DJF',1:'MAM',2:'JJA',3:'SON'}

def polygon_area_km2(g):
    if g.is_empty:return 0.
    if g.geom_type=='Polygon':
        return abs(GEOD.geometry_area_perimeter(sh.orient_polygons(g))[0])/1e6
    if hasattr(g,'geoms'):return sum(polygon_area_km2(x) for x in g.geoms)
    return 0.

def region_area_fields(cell,wet,r,d):
    cr=cell.intersection(r);cd=cell.intersection(d)
    return {'wet_area_in_R':polygon_area_km2(wet.intersection(r)),
            'wet_area_in_D':polygon_area_km2(wet.intersection(d)),
            'R_boundary_only':bool(cell.intersects(r) and cr.area==0),
            'R_positive_area':bool(cr.area>0),'D_positive_area':bool(cd.area>0)}

def release_weights(areas):
    a=np.asarray(areas,dtype=float)
    if not np.isfinite(a).all() or (a<0).any() or a.sum()<=0:
        raise ValueError('Release areas must be finite and nonnegative, with positive total')
    return a/a.sum()

def depth_stratum(depth):
    if pd.isna(depth):return 'missing_depth'
    if not np.isfinite(depth) or depth<=0:return 'nonpositive_or_nonfinite_depth_unresolved'
    if depth==15:return 'recorded_15m'
    if depth==10:return 'recorded_10m'
    return 'other_positive_recorded_depth'

def connection():
    con=duckdb.connect();con.execute("SET memory_limit='1500MB'");con.execute('SET threads=2')
    con.execute('SET preserve_insertion_order=false')
    (ROOT/'spill').mkdir(parents=True,exist_ok=True)
    con.execute(f"SET temp_directory='{ROOT}/spill'")
    return con

def reader(folder):return f"read_parquet('{OUT}/{folder}/*.parquet',union_by_name=true)"

def support_summary(con,relation,keys,eligible='eligible',candidates='candidates'):
    # Aggregate each ID before calculating dominance or annual ID unions.
    k=', '.join(keys)
    q=f'''WITH per_id AS (
        SELECT {k},id,sum({eligible}) n,sum({candidates}) c
        FROM {relation} GROUP BY {k},id)
        SELECT {k},sum(c) candidates,sum(n) eligible,
        count(DISTINCT CASE WHEN c>0 THEN id END) candidate_IDs,
        count(DISTINCT CASE WHEN n>0 THEN id END) eligible_IDs,
        coalesce(max(n),0) dominant_ID_pairs,
        max(n)/nullif(sum(n),0) dominant_ID_share,
        sum(n)/nullif(sum(c),0) availability
        FROM per_id GROUP BY {k}'''
    frame=con.execute(q).df()
    for name in ['candidates','eligible','candidate_IDs','eligible_IDs','dominant_ID_pairs']:
        frame[name]=frame[name].astype('int64')
    return frame

def batched_summary(con,relation,keys,day_column='days'):
    days=[int(x[0]) for x in con.execute(f'SELECT DISTINCT {day_column} FROM {relation} ORDER BY {day_column}').fetchall()]
    return pd.concat([support_summary(con,f'(SELECT * FROM {relation} WHERE {day_column}={day})',keys)
                      for day in days],ignore_index=True)

def metadata_view(con):
    m=pd.read_parquet(OUT/'metadata/trajectory_context.parquet')
    m=m[m.split.isin(['train','validation'])].copy()
    m['raw_depth_m']=m.DrogueCenterDepth.astype(float)
    m['depth_stratum']=m.raw_depth_m.map(depth_stratum)
    con.register('md',pa.Table.from_pandas(m,preserve_index=False))
    return m

def lag_view(con,relation=None):
    relation=reader('support/lags') if relation is None else relation
    con.execute(f'''CREATE OR REPLACE VIEW lag AS
      SELECT id,split,cell,season,days,scenario,'endpoint' AS "target",candidates,endpoint_eligible eligible FROM {relation}
      UNION ALL
      SELECT id,split,cell,season,days,scenario,'stopped' AS "target",candidates,stopped_eligible eligible FROM {relation}''')

def position_census(con,relation):
    row=con.execute(f'''SELECT count(*) AS row_count,sum(CASE WHEN NOT position_ok THEN 1 ELSE 0 END) bad_positions,
      sum(CASE WHEN lon IS NULL OR lat IS NULL OR NOT isfinite(lon) OR NOT isfinite(lat) OR lon < -180 OR lon > 180 OR lat < -90 OR lat > 90 THEN 1 ELSE 0 END) native_invalid
      FROM {relation}''').fetchone()
    return dict(zip(['rows','bad_positions','native_invalid'],map(int,row)))

def areas():
    begin=time.monotonic();land=mask('h');r=region_R()
    d=shape(json.loads((OUT/'geometry/transport_D.geojson').read_text())['features'][0]['geometry'])
    original=pd.read_parquet(OUT/'geometry/state_index.parquet');rows=[];tiles={}
    for z in original.itertuples():
        cell=box(z.lon_min,z.lat_min,z.lon_min+z.resolution,z.lat_min+z.resolution)
        tx=int(np.floor(z.lon_min/5));ty=int(np.floor(z.lat_min/5));key=(tx,ty)
        if key not in tiles:tiles[key]=land.intersection(box(tx*5,ty*5,(tx+1)*5,(ty+1)*5))
        rows.append(region_area_fields(cell,cell.difference(tiles[key]),r,d))
    added=pd.DataFrame(rows);result=pd.concat([original,added],axis=1)
    result['whole_R_release_weight']=0.;summary=[]
    for res in [1.,.5]:
        take=result.resolution==res;x=result.loc[take]
        result.loc[take,'whole_R_release_weight']=release_weights(x.wet_area_in_R)
        summary.append({'resolution':res,'cells':len(x),'R_intersecting_cells':int(x.R_intersection.sum()),
                        'R_boundary_only_cells':int(x.R_boundary_only.sum()),
                        'whole_cell_wet_area_for_R_intersections_km2':float(x.loc[x.R_intersection,'wet_area_km2'].sum()),
                        'R_wet_area_km2':float(x.wet_area_in_R.sum()),'D_wet_area_km2':float(x.wet_area_in_D.sum())})
    parquet(result,ROOT/'geometry/state_index.parquet')
    save_json(ROOT/'geometry/area_policy.json',{'units':'km2','region_water':'cell intersection region intersection complement of GSHHG high L1',
        'whole_R_prior':'weight proportional to wet_area_in_R within each resolution; empirical historical origin prior remains within each cell',
        'zero_area_contact':'boundary included for point membership; zero area mass for line/point contact',
        'unsupported_cells':'retain release mass; model must preserve unresolved-support mass',
        'full_cell_area':'baseline wet_area_km2 retained for full-cell density; never whole-R release weight',
        'area_method':'WGS84 geodesic polygon areas with correctly oriented exterior/holes; degree-coordinate straight edges represented by geodesic vertex edges',
        'partition_area_note':'R/D partition totals may differ slightly across grids and from a whole-polygon geodesic area due to boundary segmentation; each resolution normalizes its own partition',
        'summaries':summary,'elapsed_seconds':time.monotonic()-begin})
    print('areas',summary,flush=True)

def lags():
    begin=time.monotonic();con=connection();lag_view(con)
    seasonal=batched_summary(con,'lag',LAG_KEYS)
    annual_keys=[x for x in LAG_KEYS if x!='season']
    annual=batched_summary(con,'lag',annual_keys);annual['season']=-1
    # Complete seasonal coverage for every annual candidate-cell combination.
    skeleton=annual[annual_keys].merge(pd.DataFrame({'season':[0,1,2,3]}),how='cross')
    seasonal=skeleton.merge(seasonal,on=LAG_KEYS,how='left')
    integers=['candidates','eligible','candidate_IDs','eligible_IDs','dominant_ID_pairs']
    seasonal[integers]=seasonal[integers].fillna(0).astype('int64')
    seasonal['support_status']=np.select([seasonal.candidates==0,seasonal.eligible_IDs==0,seasonal.eligible_IDs==1],
                    ['no_candidate_origins','no_eligible_IDs','one_eligible_ID'],default='multiple_eligible_IDs')
    for name,frame in [('lag_support',seasonal),('lag_annual_support',annual)]:
        frame['population']='D';frame['resolution']=1.;frame['tolerance_hours']=0
        frame['departure_season']=frame.season.map(SEASON_NAMES)
        parquet(frame,ROOT/'support'/f'{name}.parquet')
    coverage=seasonal.groupby(annual_keys,sort=False).agg(
        seasons_with_candidates=('candidates',lambda s:int((s>0).sum())),
        seasons_with_eligible_IDs=('eligible_IDs',lambda s:int((s>0).sum()))).reset_index()
    supported=seasonal[seasonal.eligible_IDs>0].groupby(annual_keys).departure_season.agg(lambda s:','.join(s)).reset_index(name='eligible_seasons')
    coverage=coverage.merge(supported,on=annual_keys,how='left');coverage['eligible_seasons']=coverage.eligible_seasons.fillna('')
    parquet(coverage,ROOT/'support/lag_seasonal_coverage.parquet')
    # Regional ID counts use unions across cells, never summed cell ID counts.
    for unit,keys in [('annual',['split','days','scenario','target']),
                      ('seasonal',['split','days','scenario','target','season'])]:
        batched_summary(con,'lag',keys).to_csv(ROOT/'support'/f'D_lag_{unit}_totals.csv',index=False)
    req=pd.DataFrame([{'horizon_days':h,'lag_days':tau,'full_steps':h//tau,'remainder_days':h%tau,'requires_remainder_kernel':h%tau!=0}
                      for tau in [1,3,5,7] for h in range(1,366)])
    req.to_csv(ROOT/'support/exact_duration_kernel_requirements.csv',index=False)
    old=pd.read_parquet(OUT/'support/lag_support.parquet');checks=[]
    for target in ['endpoint','stopped']:
        current=seasonal[seasonal.target==target].query('candidates>0')
        joined=old.merge(current,on=['split','cell','season','days','scenario'],validate='one_to_one',suffixes=('_old','_new'))
        assert len(joined)==len(old)
        assert (joined.candidates_old==joined.candidates_new).all()
        assert (joined[f'{target}_eligible']==joined.eligible).all()
        checks.append({'target':target,'groups_reconciled':len(joined)})
    assert ((seasonal.eligible_IDs<=seasonal.candidate_IDs)&(seasonal.eligible<=seasonal.candidates)).all()
    save_json(ROOT/'audit/lag_reconciliation.json',{'checks':checks,'days':sorted(seasonal.days.unique().tolist()),
            'annual_ID_policy':'distinct eligible ID union after aggregating per ID across seasons',
            'target_policy':'separate endpoint/stopped; all counts are overlapping hourly origins',
            'legacy_layout':'baseline lag_support is wide; this versioned lag_support is long with explicit target',
            'settings_selected':False,'elapsed_seconds':time.monotonic()-begin})
    con.close();print('lags',len(seasonal),'seasonal groups',len(annual),'annual groups',flush=True)

def depths():
    begin=time.monotonic();con=connection();m=metadata_view(con);lag_view(con)
    parquet(m[['id','split','expno','DrogueCenterDepth','raw_depth_m','depth_stratum','typebuoy','location_type']],ROOT/'support/depth_hardware_metadata.parquet')
    con.execute(f'''CREATE OR REPLACE VIEW depth_origins AS
      WITH o AS (SELECT *, 'D' population FROM {reader('origins')}
        UNION ALL SELECT *, 'R' population FROM {reader('origins')} WHERE in_R)
      SELECT o.id,md.split,population,cell_1 cell,season,regime,{', '.join('md.'+x for x in METADATA_KEYS)},
        count(*) candidates,sum(CASE WHEN mapping_ok THEN 1 ELSE 0 END) eligible
      FROM o JOIN md USING(id) GROUP BY ALL''')
    per_id=con.execute('SELECT * FROM depth_origins').df();parquet(per_id,ROOT/'support/depth_origin_per_ID.parquet')
    origin_keys=['split','population','cell','season','regime']+METADATA_KEYS
    origin=support_summary(con,'depth_origins',origin_keys)
    origin=origin.rename(columns={'eligible':'usable_mapping_origins','eligible_IDs':'usable_mapping_IDs'})
    parquet(origin,ROOT/'support/depth_origin_support.parquet')
    total_keys=['split','population','regime']+METADATA_KEYS
    total=support_summary(con,'depth_origins',total_keys).rename(columns={'eligible':'usable_mapping_origins','eligible_IDs':'usable_mapping_IDs'})
    total.to_csv(ROOT/'support/depth_origin_totals.csv',index=False)
    con.execute(f'''CREATE OR REPLACE VIEW depth_anchor AS
      SELECT p.*,{', '.join('md.'+x for x in METADATA_KEYS)} FROM {reader('support/partials')} p
      JOIN md USING(id) WHERE resolution=1''')
    keys=['split','population','cell','season','scenario','horizon_days','target']+METADATA_KEYS
    parquet(batched_summary(con,'depth_anchor',keys,'horizon_days'),ROOT/'support/depth_anchor_support.parquet')
    summary_keys=['split','population','scenario','horizon_days','target']+METADATA_KEYS
    support_summary(con,'depth_anchor',summary_keys).to_csv(ROOT/'support/depth_anchor_totals.csv',index=False)
    con.execute(f'''CREATE OR REPLACE VIEW depth_lag AS
      SELECT lag.*,{', '.join('md.'+x for x in METADATA_KEYS)} FROM lag JOIN md USING(id)''')
    parquet(batched_summary(con,'depth_lag',LAG_KEYS+METADATA_KEYS),ROOT/'support/depth_lag_support.parquet')
    support_summary(con,'depth_lag',['split','scenario','days','target']+METADATA_KEYS).to_csv(ROOT/'support/depth_lag_totals.csv',index=False)
    d=per_id[(per_id.population=='D')&(per_id.regime==1)&(per_id.eligible>0)]
    by_id=d.groupby(['id','split','depth_stratum','raw_depth_m','typebuoy'],dropna=False).eligible.sum().reset_index()
    n=by_id[by_id.depth_stratum.isin(['recorded_10m','missing_depth'])]
    z=by_id[by_id.depth_stratum=='nonpositive_or_nonfinite_depth_unresolved']
    def records(frame):return frame.astype(object).where(pd.notna(frame),None).to_dict('records')
    assert n.id.nunique()==17 and int(n.eligible.sum())==41879
    findings={'supplied_10m_or_missing_depth_finding':{'IDs':n.id.nunique(),'usable_drogued_D_origins':int(n.eligible.sum()),'IDs_detail':records(n)},
       'additional_nonpositive_depth':{'IDs':z.id.nunique(),'usable_drogued_D_origins':int(z.eligible.sum()),'IDs_detail':records(z)},
       'non15m_or_unresolved_R_drogued_origins':int(per_id.loc[(per_id.population=='R')&(per_id.regime==1)&(per_id.depth_stratum!='recorded_15m'),'eligible'].sum()),
       'depth_policy_status':'DEPTH-01 pending explicit architecture policy; all data and existing primary labels retained',
       'metadata_authority':'native DrogueCenterDepth in metres, fill NaN; source dictionary does not resolve zero as a physical immersion or standard depth',
       'hardware_policy':'native typebuoy and location_type retained; physical equivalence not asserted',
       'eligibility_note':'origin regime/mapping counts differ from constant-regime interval eligibility in anchor/lag tables',
       'test_used':False,'elapsed_seconds':time.monotonic()-begin}
    save_json(ROOT/'audit/depth_findings.json',findings);con.close()
    print('depth',findings['supplied_10m_or_missing_depth_finding']['IDs'],41879,'plus nonpositive',z.id.nunique(),int(z.eligible.sum()),flush=True)

def coverage():
    begin=time.monotonic();con=connection()
    con.execute(f"CREATE VIEW p AS SELECT * FROM {reader('support/partials')} WHERE population='R' AND resolution=1")
    anchors=support_summary(con,'p',['split','scenario','horizon_days','target'])
    parquet(anchors,ROOT/'support/R_anchor_support.parquet')
    folds=pd.read_csv(OUT/'manifests_development_folds.csv');con.register('folds',pa.Table.from_pandas(folds))
    con.execute('CREATE VIEW pf AS SELECT p.*,development_fold FROM p JOIN folds USING(id)')
    keys=['development_fold','season','scenario','horizon_days','target']
    seasonal=support_summary(con,'pf',keys)
    annual=support_summary(con,'pf',[x for x in keys if x!='season']);annual['season']=-1
    counts=pd.concat([seasonal,annual],ignore_index=True)
    skeleton=pd.MultiIndex.from_product([range(5),[-1,0,1,2,3],['drogued','undrogued','pooled'],[7,30,90,180,365],['endpoint','stopped']],names=keys).to_frame(index=False)
    complete=skeleton.merge(counts,on=keys,how='left')
    integer=['candidates','eligible','candidate_IDs','eligible_IDs','dominant_ID_pairs']
    complete[integer]=complete[integer].fillna(0).astype('int64')
    complete['departure_season']=complete.season.map(SEASON_NAMES)
    complete['evaluation_status']=np.where(complete.eligible_IDs==0,'not_evaluable','observed_labels_available_prediction_not_evaluated')
    complete.to_csv(ROOT/'support/R_grouped_fold_coverage.csv',index=False)
    s=pd.read_parquet(OUT/'support/cell_support.parquet')
    sparse=s[(s.population=='R')&(s.resolution==1)&(s.scenario=='drogued')&(s.horizon_days==365)].copy()
    parquet(sparse,ROOT/'support/R_365_cell_season_support.parquet')
    sparse_summary=[]
    for (split,target),x in sparse.groupby(['split','target']):
        supported=x[x.eligible_IDs>0]
        sparse_summary.append({'split':split,'target':target,'cell_season_with_candidates':len(x),'zero_eligible_IDs':int((x.eligible_IDs==0).sum()),
           'one_eligible_ID':int((x.eligible_IDs==1).sum()),'supported_dominant_ID_share_median':float(supported.dominant_ID_share.median())})
    parent=json.loads((ROOT/'architecture_independent_audit.json').read_text())
    for x in parent['R_fixed_drogued_from_actual_ledgers']:
        q=anchors[(anchors.split==x['split'])&(anchors.scenario=='drogued')&(anchors.horizon_days==x['horizon_days'])&(anchors.target==x['target'])].iloc[0]
        assert q.eligible==x['eligible'] and q.eligible_IDs==x['eligible_IDs'] and q.candidates==x['candidates']
    empties=complete[(complete.scenario=='drogued')&(complete.horizon_days==365)&(complete.season>=0)&(complete.eligible==0)]
    expected={(x['target'],x['season'],x['fold']) for x in parent['empty_DEV_year_validation_folds']}
    assert set(zip(empties.target,empties.season,empties.development_fold))==expected
    save_json(ROOT/'audit/annual_support_limits.json',{'cell_season_summary':sparse_summary,'empty_365_drogued_folds':empties[['target','departure_season','development_fold']].to_dict('records'),
        'evaluation_policy':'zero cases => not_evaluable, never score zero; preserve annual baseline and declared seasonal shrinkage; no prediction evaluated',
        'independent_audit_counts_reconciled':True,'no_split_change':True,'test_used':False,'elapsed_seconds':time.monotonic()-begin})
    con.close();print('coverage',sparse_summary,flush=True)

def source_reason():
    begin=time.monotonic();con=connection()
    stats=position_census(con,f"read_parquet(['{OUT}/cleaned/*.parquet','{OUT}/restricted_test/cleaned/*.parquet'])")
    assert stats['rows']==39107061 and stats['bad_positions']==0 and stats['native_invalid']==0
    spec=importlib.util.spec_from_file_location('architecture_baseline_core',ROOT/'baseline/prep_core.py')
    old=importlib.util.module_from_spec(spec);spec.loader.exec_module(old)
    import prep_core as current
    from prep_pairs import load_track,origin_indices,CUTOFF
    s=Source();r=[int(x) for x in s.ids if x in s.R and s.cohort.loc[int(x),'split']!='test'][:15]
    downstream=[int(x) for x in s.ids if x not in s.R and s.cohort.loc[int(x),'split']!='test'][:2]
    comparisons=cases=0
    for id in r+downstream:
        df,a,ev=load_track(s,id);o=origin_indices(df,a,'R' if id in s.R else 'D')
        previous=old.event_bounds(a)
        for day in [1,3,5,7,30,365]:
            for scenario in ['drogued','undrogued','pooled']:
                first=old.labels(a,o,day,0,scenario,previous,CUTOFF)
                second=current.labels(a,o,day,0,scenario,ev,CUTOFF)
                for x,y in zip(first,second):
                    for key in x:assert np.array_equal(x[key],y[key],equal_nan=True),(id,day,scenario,key)
                comparisons+=1;cases+=len(o)*2
    report={'source_position_technical_census':stats,'development_IDs_compared':r+downstream,
            'old_new_label_calls':comparisons,'target_eligibility_cases_compared':cases,
            'all_preexisting_label_fields_equal':True,'effect_on_existing_snapshot_eligibility':'none: all native/source positions usable; old and corrected predicates coincide in this condition',
            'new_fields':'independent source-position/geometry event times and per-target boolean annotations; no new primary eligibility rule',
            'test_access':'position and native-coordinate technical census only; no test labels used in settings or illustrations',
            'historical_schema':'existing event/label partitions are unchanged; current generator computes bounds from cleaned records and emits new annotations',
            'elapsed_seconds':time.monotonic()-begin}
    save_json(ROOT/'audit/source_reason_correction.json',report);con.close();print('reason correction',report,flush=True)

def main():
    p=argparse.ArgumentParser();p.add_argument('action',choices=['areas','lags','depths','coverage','source_reason']);x=p.parse_args()
    ROOT.mkdir(parents=True,exist_ok=True);(ROOT/'support').mkdir(exist_ok=True)
    {'areas':areas,'lags':lags,'depths':depths,'coverage':coverage,'source_reason':source_reason}[x.action]()

if __name__=='__main__':main()
