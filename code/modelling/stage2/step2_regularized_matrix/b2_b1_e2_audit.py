"""Independent E2 reconstruction; never calls production probability/selection code."""
from collections import Counter
from pathlib import Path
import json
import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.qualified_count_inputs import read_frame

METRICS=('brier','region90_cells','region90_hit')


def rebuild(counts, folds, roles, states):
    index={int(c):i for i,c in enumerate(states)}; out={}
    for role,spec in roles.items():
        train=set(spec['training_ids']);evaluation=set(spec['evaluation_ids'])
        outer,inner=spec['outer_fold'],spec['inner_fold']
        excluded=[v for v in (outer,inner) if v>=0]
        expected=set(folds.loc[~folds.outer_fold.isin(excluded),'id'])
        expected_eval=set() if outer<0 else set(folds.loc[folds.outer_fold.eq(inner if inner>=0 else outer),'id'])
        assert train==expected and evaluation==expected_eval and not train&evaluation,role
        counter=Counter()
        for r in counts.itertuples(index=False):
            if r.id in train:counter[(r.horizon_days,r.origin_cell_1,r.destination_cell_1)]+=r.pair_count
        raw={};q={h:np.zeros(len(states)) for h in (7,30)}
        for (h,o,j),n in counter.items():
            raw.setdefault((h,o),np.zeros(len(states)))[index[j]]=n;q[h][index[j]]+=n
        totals={k:float(v.sum()) for k,v in raw.items()}
        p={k:v/totals[k] for k,v in raw.items()}
        median={h:float(np.median([n for (hh,o),n in totals.items() if hh==h])) for h in (7,30)}
        for h in (7,30):q[h]/=q[h].sum()
        out[role]=(p,q,totals,median,counter)
    return out


def vector(rebuilt,states,h,o,model,a,c,beta):
    p,q,n,m,_=rebuilt
    if (h,o) not in p:return None
    local=p[(h,o)];ref=q[h].copy()
    if model=='Info' and c!=1:
        seen=(states>=0)&(local>0);unseen=(states>=0)&~seen
        s,u=float(ref[seen].sum()),float(ref[unseen].sum())
        if s+u>0:
            mass_seen=(s+u)*s/(s+c*u)
            mass_unseen=(s+u)*c*u/(s+c*u)
            if s>0:ref[seen]=ref[seen]/s*mass_seen
            if u>0:ref[unseen]=ref[unseen]/u*mass_unseen
    if model=='B2' or a==0:lam=0.
    elif a==1 or model in ('Fixed','Info') or beta==0:lam=float(a)
    else:lam=1/(1+(1-a)/a*np.exp(beta*np.log(n[(h,o)]/m[h])))
    return (1-lam)*local+lam*ref


def region(p):
    values=sorted(p[p>0],reverse=True); cumulative=0.
    for cutoff in values:
        cumulative+=cutoff
        if cumulative>=.9-1e-12:break
    return (p>0)&(p>=cutoff-1e-12)


def audit_candidates(counts, roles, states, rebuilt, candidates):
    index={int(c):i for i,c in enumerate(states)};error=0.;checked=0
    for role, table in candidates.groupby('fit_role'):
        valid=counts[counts.id.isin(roles[role]['evaluation_ids'])]
        # Reconstruct each vector separately with a different allocation identity.
        for h, candidate_group in table.groupby('horizon_days'):
            observations=[]
            for origin,g in valid[valid.horizon_days.eq(h)].groupby('origin_cell_1'):
                if (h,origin) not in rebuilt[role][0]:continue
                obs=np.zeros(len(states))
                for d,n in g.groupby('destination_cell_1').pair_count.sum().items():obs[index[d]]=n
                observations.append((origin,obs))
            for c in candidate_group.itertuples(index=False):
                B=0.;K=0.;H=0.;N=0
                for origin,obs in observations:
                    p=vector(rebuilt[role],states,h,origin,c.model,c.parameter_a,c.parameter_c,c.parameter_beta)
                    n=int(obs.sum());selected=region(p)
                    B+=n*(np.square(p).sum()+1)-2*float(np.sum(obs*p))
                    K+=n*int(np.sum(selected&(states>=0)));H+=float(obs[selected].sum());N+=n
                assert N==c.evaluable_pairs and int(valid.loc[valid.horizon_days.eq(h),'pair_count'].sum())==c.eligible_pairs
                if N:error=max(error,abs(B-c.score_sum)/N,abs(K-c.cell_sum)/N,abs(H-c.hit_sum)/N)
                checked+=1
    assert error<=1e-12, error
    return {'candidate_rows_checked':checked,'maximum_candidate_metric_error':error}


def audit_selection(candidates, selected):
    keys=['horizon_days','model','parameter_a','parameter_c','parameter_beta']
    for role,group in candidates.groupby('selection_role'):
        pooled=group.groupby(keys)[['score_sum','cell_sum','hit_sum','evaluable_pairs']].sum().reset_index()
        records=[]
        for r in pooled.to_dict('records'):
            for name,num in zip(METRICS,['score_sum','cell_sum','hit_sum']):r[name]=r[num]/r['evaluable_pairs']
            records.append(r)
        for h in (7,30):
            pool=[r for r in records if r['horizon_days']==h]
            controls={}
            for model in ('Fixed','E1Adaptive'):
                values=[r for r in pool if r['model']==model];minimum=min(r['brier'] for r in values)
                controls[model]=min((r for r in values if r['brier']<=minimum+1e-12),key=lambda r:r['parameter_a'])
            for model in ('Fixed','E1Adaptive','Info','Weight'):
                status='brier_control'
                if model in controls:chosen=controls[model]
                else:
                    anchor=controls['Fixed']
                    values=[r for r in pool if r['model']==model]
                    feasible=[r for r in values if r['brier']<=anchor['brier']+1e-12 and r['region90_hit']>=anchor['region90_hit']-1e-12 and r['region90_cells']<anchor['region90_cells']-1e-12]
                    if not feasible:
                        chosen=next(r for r in values if r['parameter_a']==anchor['parameter_a'] and (r['parameter_c']==1 if model=='Info' else r['parameter_beta']==0))
                        status='fallback_fixed'
                    else:
                        selectors=[(lambda r:r['region90_cells'],min),(lambda r:r['brier'],min),(lambda r:r['region90_hit'],max),
                                   (lambda r:abs(np.log(r['parameter_c'])) if model=='Info' else r['parameter_beta'],min),
                                   (lambda r:r['parameter_a'],min),(lambda r:r['parameter_c'] if model=='Info' else r['parameter_beta'],min)]
                        for getter,opt in selectors:
                            best=opt(getter(r) for r in feasible);feasible=[r for r in feasible if abs(getter(r)-best)<=1e-12]
                        chosen=feasible[0];status='constrained_gain'
                actual=selected[selected.role.eq(role)&selected.horizon_days.eq(h)&selected.model.eq(model)].iloc[0]
                for key in ('parameter_a','parameter_c','parameter_beta'):assert actual[key]==chosen[key],(role,h,model,key)
                assert actual.selection_status==status
    return True


def verify_sealed_run(paths, run_id, guard):
    if Path(run_id).name!=run_id or not run_id:raise ValueError('Unsafe run identity')
    receipt_path=paths.root/'provenance/runs'/run_id/'outputs.json';guard.input_files.add(receipt_path.resolve())
    receipt=json.loads(receipt_path.read_text());assert receipt['completed'] and receipt['final_test_access'] is False
    for relative,digest in receipt['output_sha256'].items():
        rel=Path(relative)
        assert not rel.is_absolute() and '..' not in rel.parts and rel.parts[:2] in (('results','runs'),('provenance','runs')) and rel.parts[2]==run_id
        path=paths.root/rel;guard.input_files.add(path.resolve());assert file_sha256(path)==digest,relative
    return receipt


def frozen_regressions(paths,run,guard,config):
    receipts={name:verify_sealed_run(paths,config[name],guard) for name in ('frozen_s1_run','frozen_e1_run')}
    current=read_frame(run['results']/'heldout_scores.parquet');keys=['id','horizon_days','origin_cell_1','destination_cell_1']
    for field, old_model, new_model in [('frozen_s1_run',None,'B2'),('frozen_e1_run','Fixed','Fixed'),('frozen_e1_run','Adaptive','E1Adaptive')]:
        old=read_frame(paths.root/'results/runs'/config[field]/'heldout_scores.parquet')
        if old_model is not None:old=old[old.model.eq(old_model)]
        fresh=current[current.model.eq(new_model)].copy()
        if 'model' in old:fresh['model']=old_model
        pd.testing.assert_frame_equal(fresh[old.columns].sort_values(keys).reset_index(drop=True),old.sort_values(keys).reset_index(drop=True),check_exact=False,rtol=0,atol=1e-12)
    for role in [f'outer_{k}' for k in range(5)]+['all_development_candidate']:
        for old_model,new_model in [('B2','B2'),('Fixed','Fixed'),('Adaptive','E1Adaptive')]:
            old=read_frame(paths.root/'results/runs'/config['frozen_e1_run']/'matrices'/f'{role}_{old_model}.parquet')
            fresh=read_frame(run['results']/'matrices'/f'{role}_{new_model}.parquet')
            pd.testing.assert_frame_equal(fresh,old,check_exact=False,rtol=0,atol=1e-12)
    old=read_frame(paths.root/'results/runs'/config['frozen_e1_run']/'selected_parameters.csv')
    new=read_frame(run['results']/'selected_parameters.csv')
    for r in old.itertuples(index=False):
        model='E1Adaptive' if r.model=='Adaptive' else r.model
        actual=new[new.role.eq(r.role)&new.horizon_days.eq(r.horizon_days)&new.model.eq(model)].iloc[0]
        assert actual.parameter_a==r.parameter_a
    return {'passed':True,'matrix_tables_compared':18,'heldout_comparators':3,
            'sealed_artifacts_verified':{config[k]:len(v['output_sha256']) for k,v in receipts.items()}}


def independent_audit(paths,run,counts,folds,roles,states):
    root=run['results']; rebuilt=rebuild(counts,folds,roles,states);index={int(c):i for i,c in enumerate(states)}
    candidates=read_frame(root/'candidate_scores.csv');selected=read_frame(root/'selected_parameters.csv')
    result=audit_candidates(counts,roles,states,rebuilt,candidates)
    assert audit_selection(candidates,selected)
    for role,(p,q,n,m,counter) in rebuilt.items():
        stored=read_frame(root/'bases'/f'{role}_b2.parquet')
        assert {(r.horizon_days,r.origin_cell_1,r.destination_cell_1):r.pair_count for r in stored.itertuples(index=False)}==dict(counter)
        refs=read_frame(root/'bases'/f'{role}_b1.parquet')
        for r in refs.itertuples(index=False):assert abs(r.probability-q[r.horizon_days][index[r.destination_cell_1]])<=1e-12
    scores=read_frame(root/'heldout_scores.parquet'); errors={'probability':0.,'brier':0.,'diagnostics':0.};vectors={}
    expected=counts.sort_values(['id','horizon_days','origin_cell_1','destination_cell_1']).reset_index(drop=True)
    for model,g in scores.groupby('model'):
        actual=g[list(expected)].sort_values(['id','horizon_days','origin_cell_1','destination_cell_1']).reset_index(drop=True)
        pd.testing.assert_frame_equal(actual,expected,check_exact=True)
        assert g.outer_fold.eq(g.id.map(folds.set_index('id').outer_fold)).all()
    for role in [f'outer_{k}' for k in range(5)]+['all_development_candidate']:
        for model in ('B2','Fixed','E1Adaptive','Info','Weight'):
            stored=read_frame(root/'matrices'/f'{role}_{model}.parquet');seen_keys=set()
            for (h,o),g in stored.groupby(['horizon_days','origin_cell_1']):
                if model=='B2':a,c,beta=0.,1.,0.
                else:
                    sel=selected[selected.role.eq(role)&selected.horizon_days.eq(h)&selected.model.eq(model)].iloc[0]
                    a,c,beta=sel.parameter_a,sel.parameter_c,sel.parameter_beta
                p=vector(rebuilt[role],states,h,o,model,a,c,beta)
                actual=np.zeros(len(states))
                for r in g.itertuples(index=False):actual[index[r.destination_cell_1]]=r.probability
                assert set(g.destination_cell_1)==set(states[p>0]);assert not g.destination_cell_1.duplicated().any()
                errors['probability']=max(errors['probability'],float(np.max(np.abs(p-actual))))
                vectors[(role,model,h,o)]=p;seen_keys.add((h,o))
            assert seen_keys==set(rebuilt[role][0])
    for (role,model,h,o),cases in scores.groupby(['role','model','horizon_days','origin_cell_1']):
        p=vectors.get((role,model,h,o))
        if p is None:
            assert cases.status.eq('unsupported_origin').all() and cases.brier.isna().all();continue
        b2=rebuilt[role][0][(h,o)];mask=region(p);seen=(states>=0)&(b2>0);unseen=(states>=0)&(b2==0)
        assert cases.region90_cells.eq(np.sum(mask&(states>=0))).all()
        errors['diagnostics']=max(errors['diagnostics'],float(np.max(np.abs(cases.region90_mass-p[mask].sum()))))
        for dest,g in cases.groupby('destination_cell_1'):
            onehot=np.zeros(len(states));onehot[index[dest]]=1
            errors['brier']=max(errors['brier'],float(np.max(np.abs(g.brier-np.square(p-onehot).sum()))))
            assert g.region90_hit.eq(float(mask[index[dest]])).all()
            assert g.true_seen_D.eq(float(seen[index[dest]])).all() and g.true_unseen_D.eq(float(unseen[index[dest]])).all()
            for column,expected in [('seen_D_probability',p[seen].sum()),('unseen_D_probability',p[unseen].sum()),('predicted_exit_probability',p[index[-2]])]:
                errors['diagnostics']=max(errors['diagnostics'],float(np.max(np.abs(g[column]-expected))))
            for col in (v for v in g if v.startswith('hit_k_')):
                if dest==-2:assert g[col].isna().all();continue
                k=int(col[6:]);cut=sorted(p[states>=0],reverse=True)[k-1]
                above=(states>=0)&(p>cut+1e-12);tie=(states>=0)&(np.abs(p-cut)<=1e-12)
                expected=float(above[index[dest]])+float(tie[index[dest]])*(k-int(above.sum()))/int(tie.sum())
                errors['diagnostics']=max(errors['diagnostics'],float(np.max(np.abs(g[col]-expected))))
    changes=read_frame(root/'region_changes.csv')
    for r in changes.itertuples(index=False):
        p=vectors[(r.role,r.model,r.horizon_days,r.origin_cell_1)];q=vectors[(r.role,r.reference,r.horizon_days,r.origin_cell_1)]
        mask=region(p)&~region(q) if r.part=='added' else region(q)&~region(p)
        cases=scores[scores.role.eq(r.role)&scores.model.eq('B2')&scores.horizon_days.eq(r.horizon_days)&scores.origin_cell_1.eq(r.origin_cell_1)]
        assert r.cells==int(np.sum(mask&(states>=0)))
        assert r.hit_count==int(cases.loc[cases.destination_cell_1.isin(states[mask]),'pair_count'].sum())
        assert abs(r.probability_mass-p[mask].sum())<=1e-12
    assert max(errors.values())<=1e-12,errors
    result.update(fitting_roles_checked=len(roles),whole_ID_leakage=False,persisted_matrices_verified=True,
                  independent_selection_verified=True,complete_case_scores_verified=True,
                  regions_and_budgets_verified=True,maximum_errors=errors)
    return result


def audit_bootstrap(paths,run,folds,replicates,seed):
    root=run['results'];scores=read_frame(root/'heldout_scores.parquet');draws=read_frame(root/'bootstrap_draws.csv')
    differences=read_frame(root/'paired_differences.csv');decisions=read_frame(root/'decisions.csv')
    ids=sorted(folds.id);mult=np.random.default_rng(seed).multinomial(len(ids),[1/len(ids)]*len(ids),size=replicates)
    max_error=0.;points={}
    for (h,model),g in scores.groupby(['horizon_days','model']):
        for metric in METRICS:
            rows=[]
            for ident,cases in g.groupby('id'):
                good=cases[cases[metric].notna()]
                rows.append((ident,float(np.dot(good[metric],good.pair_count)),float(good.pair_count.sum())))
            per_id=pd.DataFrame(rows,columns=['id','num','den']).set_index('id').reindex(ids,fill_value=0)
            n=per_id.num.to_numpy();d=per_id.den.to_numpy();active=d>0
            sampled_num=mult[:,active]@n[active];sampled_den=mult[:,active]@d[active]
            expected=np.divide(sampled_num,sampled_den,out=np.full(replicates,np.nan),where=sampled_den>0)
            actual=draws[draws.horizon_days.eq(h)&draws.model.eq(model)].sort_values('replicate')[metric].to_numpy()
            np.testing.assert_allclose(expected,actual,atol=1e-12,rtol=0,equal_nan=True)
            max_error=max(max_error,float(np.nanmax(np.abs(expected-actual))))
            points[(h,model,metric)]=float(n.sum()/d.sum())
    for r in differences.itertuples(index=False):
        d=draws[draws.horizon_days.eq(r.horizon_days)].pivot(index='replicate',columns='model',values=r.metric)
        delta=(d[r.model]-d.Fixed).dropna().to_numpy()
        assert r.defined_replicates==len(delta)
        for col,quantile in [('lower_95',.025),('upper_95',.975),('adjusted_lower',.05/12),('adjusted_upper',1-.05/12)]:
            assert abs(getattr(r,col)-np.quantile(delta,quantile,method='linear'))<=1e-12
        assert abs(r.difference-(points[(r.horizon_days,r.model,r.metric)]-points[(r.horizon_days,'Fixed',r.metric)]))<=1e-12
    for r in decisions.itertuples(index=False):
        d=differences[differences.horizon_days.eq(r.horizon_days)&differences.model.eq(r.model)].set_index('metric')
        point=d.loc['brier','difference']<=1e-12 and d.loc['region90_hit','difference']>=-1e-12 and d.loc['region90_cells','difference'] < -1e-12
        supported=point and d.defined_replicates.eq(replicates).all() and d.loc['brier','adjusted_upper']<=1e-12 and d.loc['region90_hit','adjusted_lower']>=-1e-12 and d.loc['region90_cells','adjusted_upper'] < -1e-12
        assert bool(r.joint_point_pass)==bool(point) and bool(r.conditional_support)==bool(supported)
    return {'paired_ID_draws_reproduced':True,'adjusted_bounds_verified':True,'classification_verified':True,'maximum_draw_error':max_error}
