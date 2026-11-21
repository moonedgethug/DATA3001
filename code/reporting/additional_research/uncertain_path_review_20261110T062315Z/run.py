import json,time
import numpy as np
import pandas as pd
import shapely as sh
from io_utils import *
from path_rules import coordinates,path_features,decide

def main():
    s=Session();passed=False
    try:
        old=pd.read_parquet(s.read(OLD/'results/endpoint_states.parquet'))
        f=old[old.risk_set&old.state.eq('uncertain')].copy()
        assert len(f)==28300 and f.groupby('cohort').size().to_dict()=={'train':24793,'validation':3507}
        dm=json.loads(s.read(ROOT/'configs/dataset_manifest.json').read_text())['records'];qm=json.loads(s.read(ROOT/'configs/qualification_manifest.json').read_text())['records']
        assets=json.loads(s.read(ROOT/'configs/assets.json').read_text())['assets'];r=assets['land_mask_high']
        land=sh.from_wkb(s.read(ROOT/r['path'],r['sha256']).read_bytes());sh.prepare(land)
        parts=[];sample_paths=[];started=time.monotonic()
        for num,(ident,g) in enumerate(f.groupby('id',sort=True),1):
            r=dm[str(ident)];q=qm[str(ident)]
            tr=pd.read_parquet(s.read(ROOT/r['path'],r['sha256']),columns=['id','source_obs','time','lon_normalized','lat'])
            flags=pd.read_parquet(s.read(ROOT/q['path'],q['sha256']))
            assert np.array_equal(tr[['source_obs','time']],flags[['source_obs','time']]) and tr.id.eq(ident).all()
            g=g.reset_index(drop=True)
            lon,lat,valid=coordinates(tr,flags,g.target_epoch.to_numpy(),float(g.official_end_epoch.iloc[0]))
            features,xy=path_features(lon,lat,valid,land)
            out=pd.concat([g,features],axis=1)
            assert np.allclose(out.before6_direct_km,out.before_6h_km,atol=1e-9,equal_nan=True)
            assert np.allclose(out.after6_direct_km,out.after_6h_km,atol=1e-9,equal_nan=True)
            out['path_evidence']=decide(out)
            out['updated_state']=np.where(out.path_evidence.isin(['looping_evidence','consistent_drift_evidence']),'drifting_evidence','uncertain')
            out['long_context_incomplete']=~(out.before72_hours_complete&out.after72_hours_complete&out.before72_coarse_complete&out.after72_coarse_complete)
            parts.append(out)
            # First original-key record of each category per ID, selected without model scores.
            for cat,gg in out.groupby('path_evidence'):
                j=int(gg.sort_values(KEY).index[0]);row=out.loc[j]
                for h in range(145):
                    if valid[j,h]:sample_paths.append({'id':int(ident),'origin_source_obs':int(row.origin_source_obs),'horizon_days':7,'path_evidence':cat,'offset_hour':h-72,'time_epoch':row.target_epoch+(h-72)*3600,'lon':lon[j,h],'lat':lat[j,h],'east_km':xy[j,h,0],'north_km':xy[j,h,1]})
            if num==10:
                estimate=(time.monotonic()-started)/10*287
                write_json(OUT/'logs/ten_id_projection.json',{'seconds':time.monotonic()-started,'all_ids_estimate_seconds':estimate})
                if estimate>1500:raise RuntimeError('Projected budget exceeded')
            if num%50==0:print('Path review IDs',num,'seconds',round(time.monotonic()-started,1),flush=True)
            s.check()
        reviewed=pd.concat(parts,ignore_index=True);assert not reviewed.duplicated(KEY).any()
        reviewed.to_parquet(OUT/'results/reviewed_uncertain.parquet',index=False)
        pd.DataFrame(sample_paths).to_parquet(OUT/'results/representative_paths.parquet',index=False)
        update=reviewed[KEY+['path_evidence','updated_state']]
        allrows=old.merge(update,on=KEY,how='left',validate='one_to_one')
        allrows['updated_state']=allrows.updated_state.fillna(allrows.state)
        allrows['path_evidence']=allrows.path_evidence.fillna('not_reviewed_original_state_retained')
        assert (allrows.loc[~(allrows.risk_set&allrows.state.eq('uncertain')),'updated_state']==allrows.loc[~(allrows.risk_set&allrows.state.eq('uncertain')),'state']).all()
        allrows.to_parquet(OUT/'results/updated_endpoint_states.parquet',index=False)
        print(reviewed.groupby(['cohort','path_evidence']).agg(pairs=('id','size'),ids=('id','nunique')).to_string(),flush=True)
        passed=True
    finally:s.close('compute',passed)

if __name__=='__main__':main()
