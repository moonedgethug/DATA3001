"""Independent Counter/set reconstruction; no E2 model or weight helper imports."""
from collections import Counter,defaultdict
import hashlib,json
import numpy as np
import pandas as pd
from data3001.modelling.baselines.drifter_shrinkage_e3_audit import region,macro
from data3001.modelling.common.qualified_count_inputs import read_frame

MODELS=('B2','Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive')
METRICS=('brier','region90_cells','region90_hit')
IDENTITY=['horizon_days','model','parameter_a','parameter_gamma']


def rebuild(counts,folds,roles,states):
    index={int(c):k for k,c in enumerate(states)};result={}
    for role,spec in roles.items():
        excluded=[spec[k] for k in ('outer_fold','inner_fold') if spec[k]>=0]
        train=set(spec['training_ids']);evaluation=set(spec['evaluation_ids'])
        assert train==set(folds.loc[~folds.outer_fold.isin(excluded),'id']) and not train&evaluation
        expected=set() if spec['outer_fold']<0 else set(folds.loc[folds.outer_fold.eq(spec['inner_fold'] if spec['inner_fold']>=0 else spec['outer_fold']),'id'])
        assert evaluation==expected
        raw=defaultdict(Counter);ids=defaultdict(Counter)
        for r in counts.itertuples(index=False):
            if r.id in train:
                raw[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1]+=r.pair_count
                ids[(r.horizon_days,r.origin_cell_1)][r.id]+=r.pair_count
        p={};q={h:np.zeros(len(states)) for h in (7,30)};qe={};ns={};support={}
        for key,c in sorted(raw.items()):
            h,i=key;z=np.zeros(len(states));n=sum(c.values());ns[key]=n
            for j,v in c.items():z[index[j]]=v/n;q[h][index[j]]+=v
            p[key]=z
        for h in q:q[h]/=q[h].sum()
        for (h,i),prob in p.items():
            y,x=divmod(i,360);donors=Counter();donor_ids=Counter();donor_cells=[]
            for (hh,k),c in raw.items():
                yy,xx=divmod(k,360)
                if hh==h and k!=i and abs(y-yy)<=1 and abs(((x-xx+180)%360)-180)<=1:
                    donors.update(c);donor_ids.update(ids[(hh,k)]);donor_cells.append(k)
            n=sum(donors.values());v=np.zeros(len(states))
            if n:
                for j,k in donors.items():v[index[j]]=k/n
            else:v=prob.copy()
            qe[(h,i)]=v;local=set(ids[(h,i)]);neighbour=set(donor_ids)
            support[(h,i)]=dict(local_ids=len(local),neighbour_ids=len(neighbour),local_ID_set=json.dumps(sorted(local)),
                neighbour_ID_set=json.dumps(sorted(neighbour)),local_pairs=ns[(h,i)],neighbour_pairs=n,neighbour_cells=len(donor_cells),
                overlap_local_neighbour_IDs=len(local&neighbour),jaccard_overlap=len(local&neighbour)/len(local|neighbour),
                local_largest_ID_share=max(ids[(h,i)].values())/ns[(h,i)],
                neighbour_largest_ID_share=max(donor_ids.values())/n if n else 0.,support_ratio=len(neighbour)/len(local),no_neighbour=n==0)
        median={h:float(np.median([n for (hh,i),n in ns.items() if hh==h])) for h in (7,30)}
        ratio={h:[d['support_ratio'] for (hh,i),d in support.items() if hh==h and d['neighbour_ids']>0] for h in (7,30)}
        rm={h:float(np.median(v)) if v else 1. for h,v in ratio.items()}
        for (h,i),d in support.items():d.update(median_support_ratio=rm[h],normalised_support_ratio=d['support_ratio']/rm[h],no_positive_support_ratio=not ratio[h])
        result[role]=dict(p=p,q=q,qe=qe,n=ns,m=median,support=support)
    return result


def weight(base,h,o,model,a,gamma):
    if model=='B2':return 0.
    if model=='Fixed':return a
    if model=='Adaptive':
        if a in (0,1):return a
        tau=base['m'][h]*a/(1-a)
        return tau/(base['n'][(h,o)]+tau)
    s=base['support'][(h,o)]
    if s['neighbour_ids']==0:return 0.
    if model=='LocalEndpoint' or gamma==0 or a in (0,1):return a
    # Direct rational form independently checks the implementation's log odds.
    power=s['normalised_support_ratio']**gamma
    return a*power/(1-a+a*power)


def probability(base,h,o,model,a,gamma=0.):
    if (h,o) not in base['p']:return None
    p=base['p'][(h,o)]
    if model=='B2':return p
    q=base['q'][h] if model in ('Fixed','Adaptive') else base['qe'][(h,o)]
    w=weight(base,h,o,model,a,gamma)
    return p+w*(q-p)


def independent_audit(paths,run,counts,folds,roles,states):
    root=run['results'];bases=rebuild(counts,folds,roles,states);index={int(c):k for k,c in enumerate(states)}
    errors={k:0. for k in ('probability','candidate','score','summary','support','weight')}
    obs={}
    for r in counts.itertuples(index=False):obs.setdefault((r.horizon_days,r.origin_cell_1,r.id),Counter())[r.destination_cell_1]+=r.pair_count
    selected=read_frame(root/'selected_parameters.csv');units=read_frame(root/'candidate_id_cells.parquet')
    saved_scores=read_frame(root/'candidate_scores.csv').set_index(['fit_role',*IDENTITY])
    expected={('B2',0.,0.),*[(m,k/20,0.) for m in MODELS[1:4] for k in range(21)],*[(MODELS[-1],k/20,g) for k in range(21) for g in (0.,.5,1.,2.)]}
    spec=sorted(expected)
    for role,b in bases.items():
        saved=read_frame(root/'bases'/f'{role}_neighbour_support.csv').set_index(['horizon_days','origin_cell_1'])
        assert set(saved.index)==set(b['support'])
        for key,d in b['support'].items():
            for k,v in d.items():
                if isinstance(v,(str,bool)):assert saved.loc[key,k]==v,(role,key,k)
                else:errors['support']=max(errors['support'],abs(float(saved.loc[key,k])-v))
    for role,g in units.groupby('fit_role',sort=False):
        keys={key for key in obs if key[2] in roles[role]['evaluation_ids']}
        for ident,z in g.groupby(['model','parameter_a','parameter_gamma'],sort=False):
            assert ident in expected and not z.duplicated(['horizon_days','origin_cell_1','id']).any()
            assert set(z[['horizon_days','origin_cell_1','id']].itertuples(index=False,name=None))==keys
        assert set(g[['model','parameter_a','parameter_gamma']].itertuples(index=False,name=None))==expected
        for (h,o),z in g.groupby(['horizon_days','origin_cell_1'],sort=False):
            ids=sorted(z.id.unique());numbers=np.array([sum(obs[(h,o,d)].values()) for d in ids])
            table=z.sort_values(['model','parameter_a','parameter_gamma','id'])
            assert np.array_equal(table.eligible_pairs.to_numpy(),np.tile(numbers,148))
            if (h,o) not in bases[role]['p']:
                assert not table.supported.any();continue
            assert table.supported.all()
            observed=np.array([[obs[(h,o,d)].get(int(j),0)/n for j in states] for d,n in zip(ids,numbers)])
            probs=np.array([probability(bases[role],h,o,m,a,gamma) for m,a,gamma in spec])
            regions=np.array([region(p) for p in probs]);norm=np.einsum('ij,ij->i',probs,probs)
            bs=(1+norm[:,None]-2*(probs@observed.T)).ravel()
            ks=np.repeat(np.sum(regions&(states[None,:]>=0),axis=1),len(ids))
            hits=(regions.astype(float)@observed.T).ravel()
            for metric,v in zip(METRICS,(bs,ks,hits)):errors['candidate']=max(errors['candidate'],float(np.max(np.abs(v-table[metric].to_numpy()))))
            for a in [k/20 for k in range(21)]:
                p=probs[spec.index(('LocalEndpoint',a,0.))];q=probs[spec.index(('LocalEndpointAdaptive',a,0.))]
                assert np.max(np.abs(p-q))<=1e-12
        for key,z in g.groupby(IDENTITY):
            result=macro(z.to_dict('records'));saved=saved_scores.loc[(role,*key)]
            for m in METRICS:errors['summary']=max(errors['summary'],abs(result[m]-saved[m]))
    for role,choice in selected.groupby('role'):
        pool=units[units.selection_role.eq(role)]
        for (h,model),part in pool[pool.model.ne('B2')].groupby(['horizon_days','model']):
            vals=[(gamma,a,macro(g.to_dict('records'))['brier']) for (a,gamma),g in part.groupby(['parameter_a','parameter_gamma'])]
            best=min(v for gamma,a,v in vals);gamma,a,_=min(t for t in vals if t[2]<=best+1e-12)
            row=choice[(choice.horizon_days==h)&(choice.model==model)].iloc[0]
            assert (gamma,a)==(row.parameter_gamma,row.parameter_a)
        for model in MODELS:
            saved=read_frame(root/'matrices'/f'{role}_{model}.parquet')
            for (h,o),p0 in bases[role]['p'].items():
                pars=choice[(choice.horizon_days==h)&(choice.model==model)]
                a,gamma=(0.,0.) if model=='B2' else tuple(pars[['parameter_a','parameter_gamma']].iloc[0])
                p=probability(bases[role],h,o,model,a,gamma);v=np.zeros(len(states))
                for r in saved[(saved.horizon_days==h)&(saved.origin_cell_1==o)].itertuples(index=False):v[index[r.destination_cell_1]]=r.probability
                assert abs(v.sum()-1)<=1e-12 and (v>=0).all()
                errors['probability']=max(errors['probability'],float(np.max(np.abs(p-v))))
    candidate_rows=len(units)
    assert candidate_rows==6234500 and len(saved_scores)==7400
    del units
    support=read_frame(root/'row_support.csv')
    for r in support[support.supported].itertuples(index=False):
        b=bases[r.role];w=weight(b,r.horizon_days,r.origin_cell_1,r.model,r.parameter_a,r.parameter_gamma)
        errors['weight']=max(errors['weight'],abs(w-r.effective_borrowing_weight),abs(1-w-r.total_B2_weight))
    held=read_frame(root/'heldout_scores.parquet');cache={}
    for r in held.itertuples(index=False):
        key=(r.role,r.horizon_days,r.origin_cell_1,r.model)
        if key not in cache:
            pars=selected[(selected.role==r.role)&(selected.horizon_days==r.horizon_days)&(selected.model==r.model)]
            a,gamma=(0.,0.) if r.model=='B2' else tuple(pars[['parameter_a','parameter_gamma']].iloc[0])
            p=probability(bases[r.role],r.horizon_days,r.origin_cell_1,r.model,a,gamma);cache[key]=None if p is None else (p,region(p))
        item=cache[key];assert (item is not None)==(r.status=='evaluable')
        if item is None:continue
        p,reg=item;j=index[r.destination_cell_1];vals=(1+float(p@p)-2*p[j],int(np.sum(reg&(states>=0))),float(reg[j]))
        errors['score']=max(errors['score'],*(abs(x-getattr(r,m)) for x,m in zip(vals,METRICS)))
        union=(bases[r.role]['p'][(r.horizon_days,r.origin_cell_1)]>0)|(bases[r.role]['qe'][(r.horizon_days,r.origin_cell_1)]>0)
        assert r.outside_local_union==float(not union[j])
    for (h,m),g in held.groupby(['horizon_days','model']):
        good=g[g.status.eq('evaluable')];cell_ids=good.groupby('origin_cell_1').id.nunique();totals=good.groupby(['origin_cell_1','id']).pair_count.sum()
        for r in good.itertuples(index=False):
            expected_weight=r.pair_count/totals.loc[(r.origin_cell_1,r.id)]/cell_ids.loc[r.origin_cell_1]/len(cell_ids)
            assert abs(expected_weight-r.primary_group_weight)<=1e-12
    hu=read_frame(root/'heldout_id_cells.parquet');sm=read_frame(root/'summary.csv').set_index(['horizon_days','model'])
    for key,g in hu.groupby(['horizon_days','model']):
        for m,v in macro(g.to_dict('records')).items():
            if m in METRICS:errors['summary']=max(errors['summary'],abs(v-sm.loc[key,m]))
    assert max(errors.values())<=1e-12,errors
    return dict(passed=True,fitting_roles_checked=len(roles),candidate_id_cells_checked=candidate_rows,
                candidate_identities_checked=len(saved_scores),heldout_grouped_cases_checked=len(held),
                gamma_zero_equivalence=True,distinct_ID_sets_and_ratios_verified=True,maximum_absolute_errors=errors)


def audit_uncertainty(root,folds,replicates=10000,seed=20261031):
    units=read_frame(root/'heldout_id_cells.parquet');draws=read_frame(root/'bootstrap_draws.csv');diffs=read_frame(root/'paired_differences.csv')
    ids=sorted(folds.id.tolist());w=np.random.Generator(np.random.PCG64(seed)).exponential(size=(replicates,len(ids)))
    meta=json.loads((root/'multiplier_identity.json').read_text());assert hashlib.sha256(w.astype('<f8').tobytes()).hexdigest()==meta['little_endian_float64_sha256']
    assert meta['directional_comparisons']==12 and meta['quantile_method']=='linear'
    ix={d:k for k,d in enumerate(ids)};error=0.
    for (h,model),g in units[units.supported].groupby(['horizon_days','model']):
        agg=np.zeros((replicates,3));nc=g.origin_cell_1.nunique()
        for o,z in g.groupby('origin_cell_1'):
            mass=w[:,[ix[d] for d in z.id]];mass=mass/mass.sum(axis=1)[:,None]
            agg+=mass@z[list(METRICS)].to_numpy()/nc
        saved=draws[(draws.horizon_days==h)&(draws.model==model)].sort_values('replicate')[list(METRICS)].to_numpy()
        error=max(error,float(np.max(np.abs(agg-saved))))
    for r in diffs.itertuples(index=False):
        h=draws[draws.horizon_days.eq(r.horizon_days)].set_index(['model','replicate'])
        delta=h.xs(r.model,level='model')[r.metric]-h.xs(r.reference,level='model')[r.metric]
        for q,v in [(0.025,r.lower_95),(.975,r.upper_95)]:error=max(error,abs(float(np.quantile(delta,q))-v))
        if r.primary_comparison:
            q=.05/12 if r.metric=='region90_hit' else 1-.05/12
            error=max(error,abs(float(np.quantile(delta,q))-r.adjusted_directional_bound))
    decisions=read_frame(root/'decisions.csv')
    for r in decisions.itertuples(index=False):
        d=diffs[(diffs.horizon_days==r.horizon_days)&(diffs.reference==r.reference)].set_index('metric')
        b=d.loc['brier','difference']<-1e-12 and d.loc['brier','adjusted_directional_bound']<-1e-12
        c=b and d.loc['region90_hit','difference']>=-1e-12 and d.loc['region90_hit','adjusted_directional_bound']>=-1e-12
        q=c and d.loc['region90_cells','difference']<=1e-12 and d.loc['region90_cells','adjusted_directional_bound']<=1e-12
        assert (r.conditional_Brier_support,r.conditional_coverage_preserving,r.conditional_quality_preserving,r.conditional_smaller_region)==(b,c,q,q and d.loc['region90_cells','adjusted_directional_bound']<-1e-12)
    assert error<1e-12,error
    return dict(passed=True,max_error=error,replicates=replicates,draw_identity_verified=True,decision_rules_verified=True)
