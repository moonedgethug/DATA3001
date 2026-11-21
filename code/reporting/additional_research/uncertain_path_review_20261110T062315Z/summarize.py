import numpy as np
import pandas as pd
from io_utils import *

CATEGORIES=['consistent_drift_evidence','looping_evidence','suspected_local_stay','insufficient_or_conflicting','other_unresolved']
STATES=['grounding_evidence','drifting_evidence','uncertain','endpoint_missing']
def main():
    r=pd.read_parquet(OUT/'results/reviewed_uncertain.parquet');f=pd.read_parquet(OUT/'results/updated_endpoint_states.parquet')
    decomposed=[];totals=[];ids=[]
    for scope,mask in [('all_risk',f.risk_set),('frozen_used',f.used_by_original)]:
        for cohort,g in f[mask].groupby('cohort'):
            n=g.groupby('id').size();old=g[g.state.eq('uncertain')]
            for category in CATEGORIES:
                z=old[old.path_evidence.eq(category)]
                decomposed.append({'scope':scope,'cohort':cohort,'path_evidence':category,'pairs':len(z),'ids':z.id.nunique(),'original_uncertain_pairs':len(old)})
            for state in STATES:
                counts=g[g.updated_state.eq(state)].groupby('id').size().reindex(n.index,fill_value=0)
                totals.append({'scope':scope,'cohort':cohort,'state':state,'pairs':int(counts.sum()),'ids':int((counts>0).sum()),'total_pairs':len(g),'total_ids':len(n),'pair_fraction':float(counts.sum()/len(g)),'id_equal_fraction':float((counts/n).mean())})
                for ident in n.index:ids.append({'scope':scope,'cohort':cohort,'id':int(ident),'state':state,'pairs':int(counts.loc[ident]),'denominator':int(n.loc[ident]),'fraction':float(counts.loc[ident]/n.loc[ident])})
    pd.DataFrame(decomposed).to_csv(OUT/'results/uncertain_breakdown.csv',index=False)
    pd.DataFrame(totals).to_csv(OUT/'results/updated_summary.csv',index=False)
    pd.DataFrame(ids).to_csv(OUT/'results/per_id_summary.csv',index=False)
    remaining=r[r.updated_state.eq('uncertain')]
    remaining.groupby(['cohort','path_evidence','long_context_incomplete']).agg(pairs=('id','size'),ids=('id','nunique')).reset_index().to_csv(OUT/'results/remaining_detail.csv',index=False)
    stay=r[r.path_evidence.eq('suspected_local_stay')]
    stay.groupby(['cohort','id','official_typedeath']).agg(pairs=('id','size'),used_pairs=('used_by_original','sum'),
        target_min=('target_epoch','min'),target_max=('target_epoch','max'),min_coast_m=('endpoint_distance_lower_m','min'),max_coast_m=('endpoint_distance_upper_m','max'),
        min_radius_km=('post24_radius_km','min'),max_radius_km=('post24_radius_km','max')).reset_index().to_csv(OUT/'results/suspected_stay_by_id.csv',index=False)
    selected=[]
    for category,cap in [('looping_evidence',3),('consistent_drift_evidence',3),('suspected_local_stay',12)]:
        subset=r[r.path_evidence.eq(category)]
        for ident in sorted(subset.id.unique())[:cap]:selected.append(subset[subset.id.eq(ident)].sort_values(KEY).iloc[0])
    chosen=pd.DataFrame(selected);chosen.to_csv(OUT/'results/case_review_rows.csv',index=False)
    trajectories=pd.read_parquet(OUT/'results/representative_paths.parquet')
    trajectories.merge(chosen[KEY],on=KEY,validate='many_to_one').to_csv(OUT/'results/case_review_paths.csv',index=False)
    print(pd.DataFrame(decomposed).query("scope=='frozen_used'").to_string(index=False))
    print(pd.DataFrame(totals).query("scope=='frozen_used'").to_string(index=False))

if __name__=='__main__':main()
