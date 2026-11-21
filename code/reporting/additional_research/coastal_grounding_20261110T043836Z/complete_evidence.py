"""Complete descriptive association outputs and apply individually written review decisions."""
import json
import numpy as np
import pandas as pd
from runtime import *

def strata(frame,keys):
    out=[]
    for identity,g in frame.groupby(keys,dropna=False):
        if not isinstance(identity,tuple):identity=(identity,)
        per=g.groupby('id').agg(risk=('risk_set','sum'),missing=('missing_endpoint','sum'))
        rates=per.missing/per.risk.replace(0,np.nan)
        out.append(dict(zip(keys,identity))|dict(candidates=len(g),candidate_ids=g.id.nunique(),
            used=int(g.used_by_original.sum()),risk=int(g.risk_set.sum()),risk_ids=int(per.risk.gt(0).sum()),
            missing=int(g.missing_endpoint.sum()),missing_ids=int(per.missing.gt(0).sum()),zero_denominator_ids=int(per.risk.eq(0).sum()),
            missing_pair_rate=float(g.missing_endpoint.sum()/g.risk_set.sum()) if g.risk_set.sum() else np.nan,
            missing_id_equal_rate=float(rates.mean()) if rates.notna().any() else np.nan))
    return pd.DataFrame(out)

def main():
    with stage('events') as check:
        a=pd.read_parquet(RES/'origin_availability.parquet');coast=pd.read_parquet(RES/'coastal_groups.parquet')
        a=a.merge(coast[['id','origin_source_obs','horizon_days','coastal_group','group']],on=['id','origin_source_obs','horizon_days'],validate='one_to_one')
        save_frame('availability_by_death.csv',strata(a,['cohort','official_typedeath']))
        save_frame('availability_coastal_cross.csv',strata(a,['cohort','coastal_group','official_typedeath']))
        save_frame('availability_coastal_summary.csv',strata(a,['cohort','coastal_group']))
        save_frame('availability_coastal_fine_summary.csv',strata(a,['cohort','group']))
        reasons={1:'origin_invalid',2:'administrative_immaturity',4:'track_termination',8:'unknown_regime',16:'scenario_change',32:'missing_target_timestamp',64:'endpoint_position_invalid',128:'incomplete_path',256:'geometry_uncertain'}
        secondary=[]
        for cohort,f in a.groupby('cohort'):
            for bit,reason in reasons.items():
                mask=(f.secondary_predicates.astype('int64').to_numpy()&bit)>0
                secondary.append(dict(cohort=cohort,bit=bit,reason=reason,origins=int(mask.sum()),ids=int(f.loc[mask,'id'].nunique()),overlap_allowed=True))
        save_frame('secondary_reason_counts.csv',pd.DataFrame(secondary))
        ev=pd.read_csv(RES/'id_evidence.csv');case=pd.read_csv(RES/'case_review.csv')
        decisions=json.loads((LOG/'case_review_decisions.json').read_text())
        assert set(map(int,decisions['decisions']))==set(case.id)
        case['review_note']=case.id.map(lambda x:decisions['decisions'][str(x)])
        case['review_status']='individually_reviewed_records_only'
        ev['manual_reviewed']=ev.id.isin(case.id)
        ev['stagnation_status']=np.where(~ev.stagnation_check_available,'not_checkable',np.where(ev.stagnation_hint,'screening_hint','no_7d_screening_hint'))
        save_frame('case_review.csv',case);save_frame('id_evidence.csv',ev)
        ec=json.loads((LOG/'event_checks.json').read_text())
        ec.update(manual_reviewed=len(case),individual_review_decision_sha256=sha(LOG/'case_review_decisions.json'),
            unreviewed_conflict_ids=ev[ev.metadata_conflict&~ev.manual_reviewed].id.astype('int64').tolist())
        json_write(LOG/'event_checks.json',ec)
        check()

if __name__=='__main__':main()
