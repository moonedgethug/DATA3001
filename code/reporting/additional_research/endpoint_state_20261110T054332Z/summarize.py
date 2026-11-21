import pandas as pd
from common import *

def main():
    f=pd.read_parquet(OUT/'results/endpoint_states.parquet')
    if f.ground_candidate.any() and not (OUT/'logs/grounding_case_review.json').exists():
        raise RuntimeError('Individual grounding candidate review required')
    if f.ground_candidate.any():
        decisions=json.loads((OUT/'logs/grounding_case_review.json').read_text())['approved_keys']
        approved=set(tuple(x) for x in decisions)
        f['ground_review_passed']=[tuple(row) in approved for row in f[KEY].itertuples(index=False,name=None)]
        assert not (f.ground_review_passed&~f.ground_candidate).any()
        f['state']=classify(f);f['state_strict10']=classify(f,10)
        f.to_parquet(OUT/'results/endpoint_states.parquet',index=False)
    records=[];perid=[]
    for scope,mask in [('all_risk',f.risk_set),('frozen_used',f.used_by_original)]:
        for version,col in [('primary_5km','state'),('strict_10km','state_strict10')]:
            for cohort,g in f[mask].groupby('cohort'):
                totals=g.groupby('id').size()
                for state in STATES:
                    counts=g[g[col].eq(state)].groupby('id').size().reindex(totals.index,fill_value=0)
                    records.append({'scope':scope,'version':version,'cohort':cohort,'state':state,'pairs':int(counts.sum()),
                        'ids':int((counts>0).sum()),'denominator_pairs':len(g),'denominator_ids':len(totals),
                        'pair_fraction':float(counts.sum()/len(g)),'id_equal_fraction':float((counts/totals).mean())})
                    for ident in totals.index:perid.append({'scope':scope,'version':version,'cohort':cohort,'id':int(ident),'state':state,'pairs':int(counts.loc[ident]),'total_pairs':int(totals.loc[ident]),'fraction':float(counts.loc[ident]/totals.loc[ident])})
    pd.DataFrame(records).to_csv(OUT/'results/summary.csv',index=False)
    pd.DataFrame(perid).to_csv(OUT/'results/per_id_summary.csv',index=False)
    unknown=f[f.risk_set&f.state.eq('uncertain')].groupby(['cohort','unknown_reason']).agg(pairs=('id','size'),ids=('id','nunique')).reset_index()
    unknown.to_csv(OUT/'results/unknown_reasons.csv',index=False)
    coast=f[f.risk_set&f.endpoint_available].copy()
    coast['shore_group']=np.select([coast.endpoint_on_land,coast.endpoint_distance_upper_m.le(5000),coast.endpoint_distance_upper_m.le(10000)],['mapped_land','<=5km','5_10km'],default='>10km')
    coast.groupby(['cohort','shore_group','state']).agg(pairs=('id','size'),ids=('id','nunique')).reset_index().to_csv(OUT/'results/endpoint_coastal_states.csv',index=False)
    f[~f.risk_set].groupby(['cohort','administrative_excluded','known_exit','origin_invalid']).agg(pairs=('id','size'),ids=('id','nunique')).reset_index().to_csv(OUT/'results/excluded_candidates.csv',index=False)
    chosen=[]
    for cohort,g in f[f.used_by_original&f.state.eq('uncertain')].groupby('cohort'):
        for reason,h in g.groupby('unknown_reason'):
            chosen.extend(h.sort_values(KEY).head(2).index.tolist())
    chosen=sorted(set(chosen)|set(f[f.ground_candidate|f.nearshore_stay_candidate].index))
    f.loc[chosen].to_csv(OUT/'results/review_examples.csv',index=False)
    print(pd.DataFrame(records).query("version == 'primary_5km'").to_string(index=False))

if __name__=='__main__':main()
