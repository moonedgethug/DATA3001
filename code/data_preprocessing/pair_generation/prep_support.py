"""Streamed target-specific observational support. No prediction fitting."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import argparse,json,time,hashlib
import numpy as np
import pandas as pd
import duckdb
from data3001.preprocessing.prep_io import BASE, OUT, Source, save_json, parquet, sha, now, code_hash
from data3001.preprocessing.prep_pairs import load_track, origin_indices, compact, generate, CUTOFF
from data3001.preprocessing import prep_core as c

ANCHORS=[7,30,90,180,365]
SCENARIOS=['drogued','undrogued','pooled']
KEY=['split','population','resolution','cell','season','scenario','horizon_days','target']

def own_ledger_paths(root,id):
    return list((root/'ledgers').glob(f'*/{id}_*.parquet'))

def part(df,a,ev,s,id,days,pop,scen,res,tgt,label,origins):
    suffix='1' if res==1 else '05';o=df.iloc[origins];reason=label['reason'];valid=reason==0
    x=pd.DataFrame({'cell':o['cell_'+suffix].to_numpy(),'season':o.season.to_numpy(),'eligible':valid.astype(int),
                    'outside':label['outside'].astype(int),'sst_available':(valid&o.sst_ok.to_numpy()).astype(int),
                    'origin_geometry_uncertain':(~o.mapping_ok.to_numpy()).astype(int),'origin_regime_unknown':(o.regime.to_numpy()<0).astype(int),
                    'origin_day':o.departure_day_UTC.to_numpy(),'visit':o['visit_cell_'+suffix].to_numpy(),
                    'year':o.departure_year.to_numpy(),'reason':reason,'secondary':label['secondary']})
    ix=label['endpoint_index'];safe=np.clip(ix,0,len(df)-1)
    x['destination']=np.where(valid,np.where(label['outside'],-2,df['cell_'+suffix].to_numpy()[safe]),-1)
    # A known observed outside followed by an eligible inside endpoint is return
    # evidence. The qualification of that exit uses stopped eligibility itself.
    if tgt=='endpoint':
        _,st=c.labels(a,origins,days,0,scen,ev,cutoff=CUTOFF)
        x['observed_return']= (valid&~label['outside']&st['outside']).astype(int)
    else:x['observed_return']=0
    for r in range(1,10):x['reason_'+str(r)]=(reason==r).astype(int)
    for b in c.SECONDARY:x['secondary_'+str(b)]=((label['secondary']&b)!=0).astype(int)
    gr=x.groupby(['cell','season'],sort=False,observed=True)
    sums=['eligible','outside','sst_available','origin_geometry_uncertain','origin_regime_unknown','observed_return']+['reason_'+str(i) for i in range(1,10)]+['secondary_'+str(i) for i in c.SECONDARY]
    stats=gr[sums].sum();stats['candidates']=gr.size();stats['candidate_visits']=gr['visit'].nunique();stats['candidate_drifter_days']=gr['origin_day'].nunique()
    q=x[valid].groupby(['cell','season'],sort=False,observed=True)
    stats['eligible_visits']=q['visit'].nunique();stats['eligible_drifter_days']=q['origin_day'].nunique();stats=stats.fillna(0).reset_index()
    dest=x[valid].groupby(['cell','season','destination'],sort=False).size().rename('count').reset_index()
    concentration=x[valid].groupby(['cell','season','year'],sort=False).size().rename('count').reset_index()
    meta={'id':id,'split':s.cohort.loc[id,'split'],'population':pop,'resolution':res,'scenario':scen,'horizon_days':days,'target':tgt,'expno':int(s.g['expno'][s.index[id]])}
    for z in (stats,dest,concentration):
        for k,v in meta.items():z[k]=v
    return stats,dest,concentration

@frozen_action
def process(split,ids=None):
    s=Source();root=legacy_path('preparation', 'restricted_test') if split=='test' else OUT;start=time.monotonic();runrows=[]
    relevant=['prep_support.py','prep_pairs.py','prep_core.py','prep_io.py']
    signature={'code_sha256':hashlib.sha256(''.join(sha(legacy_path('scripts', f)) for f in relevant).encode()).hexdigest(),'config_sha256':sha(legacy_path('preparation', 'config/preparation.json')),
               'D_sha256':sha(legacy_path('preparation', 'geometry/transport_D.geojson')),'input_snapshot':sha(legacy_path('manifests/source_snapshot.json'))}
    ss=json.dumps(signature,sort_keys=True)
    selected=[int(x) for x in s.ids if (s.cohort.loc[int(x),'split']=='test')==(split=='test')]
    if ids:selected=[x for x in selected if x in ids]
    selected.sort(key=lambda x:(x not in s.R,s.index[x]))
    for k,id in enumerate(selected):
        cp=root/'checkpoints'/f'pairs_{id}.json';sf=root/'support/partials'/f'{id}.parquet';dfp=root/'support/destinations'/f'{id}.parquet';cf=root/'support/concentration'/f'{id}.parquet'
        if cp.exists():
            old=json.loads(cp.read_text())
            if old['signature']==ss and all((root/z).exists() and sha(root/z)==h for z,h in old['files'].items()):runrows.append(old['counts']);continue
        df,a,ev=load_track(s,id);od=origin_indices(df,a,'D');orr=origin_indices(df,a,'R');compact(s,id,df,a,ev)
        stats=[];dests=[];cons=[];sens=[];lags=[]
        for days in ANCHORS:
            for scen in SCENARIOS:
                for pop,orig in [('D',od),('R',orr)]:
                    if not len(orig):continue
                    e,p=c.labels(a,orig,days,0,scen,ev,CUTOFF)
                    for res in (1,.5):
                        for tgt,label in [('endpoint',e),('stopped',p)]:
                            q,d,z=part(df,a,ev,s,id,days,pop,scen,res,tgt,label,orig);stats.append(q);dests.append(d);cons.append(z)
                    if pop=='R':
                        frames=generate(df,a,ev,id,orig,days,scen)
                        for target,z in zip(['endpoint','stopped'],frames):
                            parquet(z,root/'ledgers'/target/f'{id}_{days}_{scen}.parquet')
                        for tol in (0,1,2,3,6):
                            ee,pp=c.labels(a,orig,days,tol,scen,ev,CUTOFF)
                            sens.append({'id':id,'split':s.cohort.loc[id,'split'],'days':days,'scenario':scen,'tolerance_hours':tol,'candidates':len(orig),
                                         'endpoint_eligible':int((ee['reason']==0).sum()),'stopped_eligible':int((pp['reason']==0).sum()),
                                         'nonexact_matches':int(((ee['reason']==0)&(ee['time_error_seconds']!=0)).sum())})
        # Short lags and memory horizons are fully available on demand; here
        # audit their D-source support without a huge dense ledger cross-product.
        for days in [1,2,3,4,5,6,7,9,10,14,15,21]:
            for scen in SCENARIOS:
                ee,pp=c.labels(a,od,days,0,scen,ev,CUTOFF)
                cells=df.cell_1.to_numpy()[od];seasons=df.season.to_numpy()[od]
                x=pd.DataFrame({'cell':cells,'season':seasons,'endpoint_eligible':(ee['reason']==0).astype(int),'stopped_eligible':(pp['reason']==0).astype(int)})
                z=x.groupby(['cell','season'],sort=False).sum();z['candidates']=x.groupby(['cell','season'],sort=False).size();z=z.reset_index()
                for key,value in {'id':id,'split':s.cohort.loc[id,'split'],'days':days,'scenario':scen}.items():z[key]=value
                lags.append(z)
        empty=pd.DataFrame(columns=KEY+['id','eligible','candidates'])
        parquet(pd.concat(stats,ignore_index=True) if stats else empty,sf)
        parquet(pd.concat(dests,ignore_index=True) if dests else pd.DataFrame(columns=KEY+['id','destination','count']),dfp)
        parquet(pd.concat(cons,ignore_index=True) if cons else pd.DataFrame(columns=KEY+['id','year','count','expno']),cf)
        files=[sf,dfp,cf,root/'origins'/f'{id}.parquet',root/'events'/f'{id}.parquet']
        if sens:
            path=root/'support/sensitivity'/f'{id}.parquet';parquet(pd.DataFrame(sens),path);files.append(path)
        if lags:
            path=root/'support/lags'/f'{id}.parquet';parquet(pd.concat(lags,ignore_index=True),path);files.append(path)
        if len(orr):files.extend(own_ledger_paths(root,id))
        counts={'id':id,'D_origins':len(od),'R_origins':len(orr),'source_rows':len(df)};runrows.append(counts)
        save_json(cp,{'signature':ss,'files':{str(f.relative_to(root)):sha(f) for f in files},'counts':counts,'utc':now()})
        if k%50==0:print('support',split,k+1,len(selected),counts,flush=True)
    receipt='pair_run.json' if ids is None else f'pair_run_partition_{min(ids)}.json'
    save_json(root/'audit'/receipt,{'signature':signature,'utc':now(),'IDs':len(runrows),'rows':runrows,'elapsed_seconds':time.monotonic()-start})

@frozen_action
def aggregate(split):
    root=legacy_path('preparation', 'restricted_test') if split=='test' else OUT;con=duckdb.connect()
    tmp=root/'support/spill';tmp.mkdir(parents=True,exist_ok=True)
    con.execute("SET memory_limit='1500MB'");con.execute('SET threads=4');con.execute(f"SET temp_directory='{tmp}'")
    def reader(folder):return f"read_parquet('{root}/support/{folder}/*.parquet',union_by_name=true)"
    keys=', '.join(KEY)
    con.execute(f'CREATE VIEW p AS SELECT * FROM {reader("partials")}')
    sums=['eligible','outside','sst_available','origin_geometry_uncertain','origin_regime_unknown','observed_return','candidate_visits','candidate_drifter_days','eligible_visits','eligible_drifter_days']+['reason_'+str(i) for i in range(1,10)]+['secondary_'+str(i) for i in c.SECONDARY]
    sql=f"SELECT {keys}, sum(candidates) candidates,"+','.join(f'sum({k}) {k}' for k in sums)+",count(DISTINCT id) candidate_IDs,count(DISTINCT CASE WHEN eligible>0 THEN id END) eligible_IDs,max(eligible) dominant_ID_pairs FROM p GROUP BY "+keys
    con.execute('CREATE TEMP TABLE summary AS '+sql)
    con.execute(f'CREATE VIEW dest AS SELECT * FROM {reader("destinations")}')
    con.execute('CREATE TEMP TABLE dst AS SELECT '+keys+',count(DISTINCT destination) destination_diversity FROM dest GROUP BY '+keys)
    con.execute(f'CREATE VIEW conc AS SELECT * FROM {reader("concentration")}')
    for group in ['year','expno']:
        con.execute(f'CREATE TEMP TABLE {group}counts AS SELECT {keys}, {group},sum(count) n FROM conc GROUP BY {keys},{group}')
        con.execute(f'CREATE TEMP TABLE {group}top AS SELECT {keys},max(n) dominant_{group}_pairs FROM {group}counts GROUP BY {keys}')
    using=' USING ('+keys+') '
    q='SELECT summary.*,coalesce(destination_diversity,0) destination_diversity,coalesce(dominant_year_pairs,0) dominant_year_pairs,coalesce(dominant_expno_pairs,0) dominant_experiment_pairs FROM summary LEFT JOIN dst'+using+'LEFT JOIN yeartop'+using+'LEFT JOIN expnotop'+using
    df=con.execute(q).df()
    for name,num,den in [('availability','eligible','candidates'),('dominant_ID_share','dominant_ID_pairs','eligible'),('dominant_year_share','dominant_year_pairs','eligible'),('dominant_experiment_share','dominant_experiment_pairs','eligible'),('SST_extension_availability','sst_available','eligible')]:df[name]=df[num]/df[den].replace(0,np.nan)
    assert (df.candidates==df.eligible+df[['reason_'+str(i) for i in range(1,10)]].sum(axis=1)).all()
    parquet(df,root/'support/cell_support.parquet')
    r=df[(df.population=='R')&(df.resolution==1)]
    group=['split','season','scenario','horizon_days','target'];r.groupby(group)[['candidates','eligible','outside','observed_return']].sum().reset_index().to_csv(root/'support/R_seasonal_counts.csv',index=False)
    # SQL union preserves overlapping unique IDs in whole-R summaries.
    q=f"SELECT split,season,scenario,horizon_days,target,sum(candidates) candidates,sum(eligible) eligible,count(DISTINCT CASE WHEN eligible>0 THEN id END) eligible_IDs FROM p WHERE population='R' AND resolution=1 GROUP BY ALL"
    con.execute(q).df().to_csv(root/'support/R_seasonal_IDs.csv',index=False)
    for folder,name,keys2 in [('sensitivity','endpoint_tolerance','split,days,scenario,tolerance_hours'),('lags','lag_support','split,cell,season,days,scenario')]:
        try:
            if folder=='sensitivity':cols=['candidates','endpoint_eligible','stopped_eligible','nonexact_matches']
            else:cols=['candidates','endpoint_eligible','stopped_eligible']
            q='SELECT '+keys2+','+','.join('sum('+x+') '+x for x in cols)+' FROM '+reader(folder)+' GROUP BY '+keys2
            parquet(con.execute(q).df(),root/'support'/f'{name}.parquet')
        except duckdb.IOException:pass
    save_json(root/'audit/support_reconciliation.json',{'utc':now(),'support_rows':len(df),'all_candidate_cells_reconciled':True,'ID_overlap':'Do not sum unique IDs across cells/seasons/horizons. R seasonal ID table computes distinct unions.',
               'test_in_development_reference':0,'candidate_definition':'All QC-valid position/time origins in actual R or D, including unresolved mapping/regime, before scenario eligibility.',
               'denominator':'candidates within each split/population/grid/cell/season/scenario/horizon/target',
               'availability':'eligible/candidates; overlapping windows are not independent samples','zero_eligible_cells':int((df.eligible==0).sum())})
    print('aggregated',split,len(df),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('action',choices=['process','aggregate']);p.add_argument('--split',default='development',choices=['development','test']);p.add_argument('--ids',nargs='*',type=int);x=p.parse_args()
    if x.action=='process':process(x.split,x.ids)
    else:aggregate(x.split)
