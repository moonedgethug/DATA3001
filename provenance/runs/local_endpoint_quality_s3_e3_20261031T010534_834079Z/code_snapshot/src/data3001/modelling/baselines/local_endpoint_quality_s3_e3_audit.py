"""Independent counters and L1-overlap reconstruction; no new model helpers."""
from collections import Counter,defaultdict
import hashlib,json
import numpy as np
import pandas as pd
from data3001.modelling.baselines import local_endpoint_adaptive_s3_e2_audit as prior
from data3001.modelling.baselines.drifter_shrinkage_e3_audit import region,macro
from data3001.modelling.common.qualified_count_inputs import read_frame

CONTROLS=('B2','Fixed','Adaptive','LocalEndpoint','LocalEndpointAdaptive')
ABLATIONS=('QualitySimilarityOnly','QualityGateOnly')
MODELS=(*CONTROLS,'LocalEndpointQuality',*ABLATIONS)
METRICS=('brier','region90_cells','region90_hit')
PARAMETERS=['parameter_a','parameter_gamma','parameter_eta','parameter_rho']
IDENTITY=['horizon_days','model',*PARAMETERS]
CATEGORIES=('shared_rare','shared_common','local_only','weak_unseen','other_neighbour_only','outside_union','exit')


def rebuild(counts,folds,roles,states):
    bases=prior.rebuild(counts,folds,roles,states);index={int(j):k for k,j in enumerate(states)};D=states>=0
    for role,b in bases.items():
        train=set(roles[role]['training_ids']);raw=defaultdict(Counter);ids=defaultdict(lambda:defaultdict(set))
        for r in counts.itertuples(index=False):
            if r.id in train:
                raw[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1]+=r.pair_count
                ids[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1].add(r.id)
        data={};donor_rows=[];evidence=[]
        for key,p in b['p'].items():
            h,i=key;y,x=divmod(i,360);own=raw[key];nd=sum(v for j,v in own.items() if j>=0)
            donors=[];all_counts=Counter();all_ids=defaultdict(set)
            for (hh,k),c in sorted(raw.items()):
                yy,xx=divmod(k,360)
                if hh==h and k!=i and abs(y-yy)<=1 and abs(((x-xx+180)%360)-180)<=1:
                    donors.append(k);all_counts.update(c)
                    for j,ds in ids[(h,k)].items():all_ids[j].update(ds)
            dn=sum(v for j,v in all_counts.items() if j>=0)
            pd0=np.array([own.get(int(j),0)/nd if j>=0 and nd else 0. for j in states])
            reason='no_neighbours' if not donors else 'local_D_empty' if not nd else 'neighbour_D_empty' if not dn else ''
            weak=np.array([not reason and j>=0 and own.get(int(j),0)==0 and 0<100*all_counts.get(int(j),0)<dn and len(all_ids[int(j)])<3 for j in states])
            categories=[]
            for k,j0 in enumerate(states):
                j=int(j0)
                cat=6 if j<0 else (0 if 100*own[j]<nd else 1) if own[j]>0 and all_counts[j]>0 else 2 if own[j]>0 else 3 if weak[k] else 4 if all_counts[j]>0 else 5
                categories.append(cat)
                if own[j]>0 or all_counts[j]>0:
                    evidence.append(dict(horizon_days=h,origin_cell_1=i,destination_cell_1=j,local_pairs=own[j],neighbour_pairs=all_counts[j],
                        local_endpoint_ids=len(ids[key][j]),neighbour_endpoint_ids=len(all_ids[j]),local_D_probability=pd0[k],
                        original_neighbour_D_probability=all_counts[j]/dn if dn and j>=0 else 0.,weak_unseen=bool(weak[k]),category=CATEGORIES[cat],fallback_reason=reason))
            pieces=[]
            for k in donors:
                nk=sum(v for j,v in raw[(h,k)].items() if j>=0)
                pk=np.array([raw[(h,k)].get(int(j),0)/nk if j>=0 and nk else 0. for j in states])
                overlap=1-float(np.abs(pd0-pk).sum())/2 if nd and nk else np.nan
                pieces.append((k,nk,pk,overlap))
            refs={}
            for eta in (0.,.5,.9):
                weights=np.array([nk*(1-eta*(1-s)) if nk and not reason else float(nk) for k,nk,pk,s in pieces])
                if weights.sum():weights/=weights.sum()
                q=b['qe'][key].copy()
                if not reason and eta:
                    q[D]=sum((w*pk[D] for w,(k,nk,pk,s) in zip(weights,pieces)),start=np.zeros(D.sum()))*(1-q[index[-2]])
                refs[eta]=q
                for w,(k,nk,pk,s) in zip(weights,pieces):
                    donor_rows.append(dict(horizon_days=h,origin_cell_1=i,donor_cell_1=k,parameter_eta=eta,donor_pairs=sum(raw[(h,k)].values()),
                        donor_D_pairs=nk,donor_ids=len(set().union(*ids[(h,k)].values())),similarity=s,original_D_weight=nk/dn if dn else 0.,
                        reweighted_D_weight=w,applied_quality=not bool(reason),fallback_reason=reason))
            data[key]=dict(pD=pd0,weak=weak,category=np.array(categories),reason=reason,references=refs)
        b.update(quality=data,donor_quality=pd.DataFrame(donor_rows),endpoint_evidence=pd.DataFrame(evidence))
    return bases


def reference(b,h,i,eta,rho):
    t=b['quality'][(h,i)];q=t['references'][eta].copy();removed=q[t['weak']].sum()*(1-rho)
    q[t['weak']]*=rho;q+=removed*t['pD']
    return q,float(removed)


def probability(b,h,i,model,a,gamma=0.,eta=0.,rho=1.):
    if model in CONTROLS:return prior.probability(b,h,i,model,a,gamma)
    if (h,i) not in b['p']:return None
    q,delta=reference(b,h,i,eta,rho);p=b['p'][(h,i)]
    w=prior.weight(b,h,i,'LocalEndpointAdaptive',a,gamma)
    return p+w*(q-p)


def independent_audit(paths,run,counts,folds,roles,states):
    root=run['results'];bases=rebuild(counts,folds,roles,states);index={int(c):k for k,c in enumerate(states)}
    errors={k:0. for k in ('probability','candidate','score','summary','support','weight','category')}
    obs={}
    for r in counts.itertuples(index=False):obs.setdefault((r.horizon_days,r.origin_cell_1,r.id),Counter())[r.destination_cell_1]+=r.pair_count
    selected=read_frame(root/'selected_parameters.csv');units=read_frame(root/'candidate_id_cells.parquet')
    saved_scores=read_frame(root/'candidate_scores.csv').set_index(['fit_role',*IDENTITY])
    search=read_frame(root/'parameter_search.csv')
    control_spec=[('B2',0.,0.,0.,1.),*[(m,k/20,0.,0.,1.) for m in CONTROLS[1:4] for k in range(21)],
        *[('LocalEndpointAdaptive',k/20,g,0.,1.) for k in range(21) for g in (0.,.5,1.,2.)]]
    def params(role,h,model):
        if model=='B2':return (0.,0.,0.,1.)
        z=selected[(selected.role==role)&(selected.horizon_days==h)&(selected.model==model)]
        assert len(z)==1,(role,h,model)
        return tuple(float(z.iloc[0][k]) for k in PARAMETERS)
    for role,b in bases.items():
        saved=read_frame(root/'bases'/f'{role}_neighbour_support.csv').set_index(['horizon_days','origin_cell_1'])
        assert set(saved.index)==set(b['support'])
        for key,d in b['support'].items():
            for k,v in d.items():
                if isinstance(v,(str,bool)):assert saved.loc[key,k]==v,(role,key,k)
                else:errors['support']=max(errors['support'],abs(float(saved.loc[key,k])-v))
        for kind,keys,suffix in [('donor_quality',['horizon_days','origin_cell_1','donor_cell_1','parameter_eta'],'csv'),('endpoint_evidence',['horizon_days','origin_cell_1','destination_cell_1'],'parquet')]:
            saved=read_frame(root/'bases'/f'{role}_{kind}.{suffix}').fillna({'fallback_reason':''})
            expected=b[kind]
            pd.testing.assert_frame_equal(saved.sort_values(keys).reset_index(drop=True),expected[saved.columns].sort_values(keys).reset_index(drop=True),check_dtype=False,check_exact=False,rtol=0,atol=1e-12)
    for role,g in units.groupby('fit_role',sort=False):
        assert g.selection_role.nunique()==1;target=g.selection_role.iloc[0]
        for h in (7,30):
            a,gamma,_,_=params(target,h,'LocalEndpointAdaptive')
            spec=sorted([*control_spec,*[('LocalEndpointQuality',a,gamma,e,r) for e in (0.,.5,.9) for r in (1.,.5,0.)]])
            section=g[g.horizon_days.eq(h)];keys={key for key in obs if key[0]==h and key[2] in roles[role]['evaluation_ids']}
            assert set(section[['model',*PARAMETERS]].itertuples(index=False,name=None))==set(spec)
            for ident,z in section.groupby(['model',*PARAMETERS],sort=False):
                assert not z.duplicated(['horizon_days','origin_cell_1','id']).any()
                assert set(z[['horizon_days','origin_cell_1','id']].itertuples(index=False,name=None))==keys
            for o,z in section.groupby('origin_cell_1',sort=False):
                ids=sorted(z.id.unique());numbers=np.array([sum(obs[(h,o,d)].values()) for d in ids])
                table=z.sort_values(['model',*PARAMETERS,'id'])
                assert np.array_equal(table.eligible_pairs.to_numpy(),np.tile(numbers,157))
                if (h,o) not in bases[role]['p']:assert not table.supported.any();continue
                assert table.supported.all()
                observed=np.array([[obs[(h,o,d)].get(int(j),0)/n for j in states] for d,n in zip(ids,numbers)])
                probs=np.array([probability(bases[role],h,o,*t) for t in spec]);regions=np.array([region(p) for p in probs])
                bs=(1+np.einsum('ij,ij->i',probs,probs)[:,None]-2*probs@observed.T).ravel()
                ks=np.repeat(np.sum(regions&(states[None,:]>=0),axis=1),len(ids));hits=(regions.astype(float)@observed.T).ravel()
                for metric,v in zip(METRICS,(bs,ks,hits)):errors['candidate']=max(errors['candidate'],float(np.max(np.abs(v-table[metric].to_numpy()))))
                for aa in [k/20 for k in range(21)]:
                    assert np.max(np.abs(probs[spec.index(('LocalEndpoint',aa,0.,0.,1.))]-probs[spec.index(('LocalEndpointAdaptive',aa,0.,0.,1.))]))<=1e-12
                assert np.max(np.abs(probs[spec.index(('LocalEndpointAdaptive',a,gamma,0.,1.))]-probs[spec.index(('LocalEndpointQuality',a,gamma,0.,1.))]))<=1e-12
        for key,z in g.groupby(IDENTITY):
            result=macro(z.to_dict('records'));saved=saved_scores.loc[(role,*key)]
            for m in METRICS:errors['summary']=max(errors['summary'],abs(result[m]-saved[m]))
    for role,choice in selected.groupby('role'):
        pool=units[units.selection_role.eq(role)]
        for (h,m),part in pool[pool.model.ne('B2')].groupby(['horizon_days','model']):
            vals=[(t,macro(z.to_dict('records'))['brier']) for t,z in part.groupby(PARAMETERS)]
            minimum=min(v for t,v in vals);tied=[t for t,v in vals if v<=minimum+1e-12]
            best=min(tied,key=(lambda t:(t[2],-t[3])) if m=='LocalEndpointQuality' else (lambda t:(t[1],t[0])))
            assert best==params(role,h,m),(role,h,m,best,params(role,h,m))
            saved=search[(search.role==role)&(search.horizon_days==h)&(search.model==m)]
            for row in saved.itertuples(index=False):
                t=tuple(getattr(row,k) for k in PARAMETERS)
                assert row.selected==(t==best) and row.within_tie==(t in tied)
                value=dict(vals)[t];errors['summary']=max(errors['summary'],abs(value-row.brier))
        for h in (7,30):
            a,g,e,r=params(role,h,'LocalEndpointQuality')
            assert (a,g)==params(role,h,'LocalEndpointAdaptive')[:2]
            assert params(role,h,'QualitySimilarityOnly')==(a,g,e,1.)
            assert params(role,h,'QualityGateOnly')==(a,g,0.,r)
        for m in MODELS:
            saved=read_frame(root/'matrices'/f'{role}_{m}.parquet')
            for (h,o),p0 in bases[role]['p'].items():
                p=probability(bases[role],h,o,m,*params(role,h,m));v=np.zeros(len(states))
                for r in saved[(saved.horizon_days==h)&(saved.origin_cell_1==o)].itertuples(index=False):v[index[r.destination_cell_1]]=r.probability
                assert abs(v.sum()-1)<=1e-12 and (v>=0).all()
                errors['probability']=max(errors['probability'],float(np.max(np.abs(p-v))))
    candidate_rows=len(units);assert candidate_rows==6613625 and len(saved_scores)==7850
    del units
    support=read_frame(root/'row_support.csv')
    for r in support[support.supported].itertuples(index=False):
        b=bases[r.role];m=r.model if r.model in CONTROLS else 'LocalEndpointAdaptive'
        w=prior.weight(b,r.horizon_days,r.origin_cell_1,m,r.parameter_a,r.parameter_gamma)
        errors['weight']=max(errors['weight'],abs(w-r.borrowing_weight),abs(w-r.effective_borrowing_weight),abs(1-w-r.total_B2_weight))
        if r.model not in CONTROLS:
            q,delta=reference(b,r.horizon_days,r.origin_cell_1,r.parameter_eta,r.parameter_rho)
            p=probability(b,r.horizon_days,r.origin_cell_1,r.model,*params(r.role,r.horizon_days,r.model))
            original=prior.probability(b,r.horizon_days,r.origin_cell_1,'LocalEndpointAdaptive',r.parameter_a,r.parameter_gamma)
            errors['weight']=max(errors['weight'],abs(delta-r.redirected_D_mass),abs(w*delta-r.mixed_redirected_D_mass),abs(np.abs(p-original).sum()/2-r.quality_total_variation))
            assert abs(p[index[-2]]-original[index[-2]])<=1e-12
    held=read_frame(root/'heldout_scores.parquet');cache={}
    for r in held.itertuples(index=False):
        key=(r.role,r.horizon_days,r.origin_cell_1,r.model)
        if key not in cache:
            p=probability(bases[r.role],r.horizon_days,r.origin_cell_1,r.model,*params(r.role,r.horizon_days,r.model))
            cache[key]=None if p is None else (p,region(p))
        item=cache[key];assert (item is not None)==(r.status=='evaluable')
        if item is None:continue
        p,reg=item;j=index[r.destination_cell_1];vals=(1+float(p@p)-2*p[j],int(np.sum(reg&(states>=0))),float(reg[j]))
        errors['score']=max(errors['score'],*(abs(x-getattr(r,m)) for x,m in zip(vals,METRICS)))
        union=(bases[r.role]['p'][(r.horizon_days,r.origin_cell_1)]>0)|(bases[r.role]['qe'][(r.horizon_days,r.origin_cell_1)]>0)
        assert r.outside_local_union==float(not union[j])
        categories=bases[r.role]['quality'][(r.horizon_days,r.origin_cell_1)]['category']
        for k,name in enumerate(CATEGORIES):
            mask=categories==k;event=float(categories[j]==k)
            expected=(p[mask].sum(),event,event*float(reg[j]),float(p[mask]@p[mask])+event*(1-2*p[j]))
            errors['category']=max(errors['category'],*(abs(v-getattr(r,f'category_{name}_{suffix}')) for suffix,v in zip(('probability','observed','hit','brier'),expected)))
    for (h,m),g in held.groupby(['horizon_days','model']):
        good=g[g.status.eq('evaluable')];cell_ids=good.groupby('origin_cell_1').id.nunique();totals=good.groupby(['origin_cell_1','id']).pair_count.sum()
        for r in good.itertuples(index=False):
            expected_weight=r.pair_count/totals.loc[(r.origin_cell_1,r.id)]/cell_ids.loc[r.origin_cell_1]/len(cell_ids)
            assert abs(expected_weight-r.primary_group_weight)<=1e-12
    hu=read_frame(root/'heldout_id_cells.parquet');sm=read_frame(root/'summary.csv').set_index(['horizon_days','model'])
    extra=[f'category_{c}_{m}' for c in CATEGORIES for m in ('probability','observed','hit','brier')]
    for key,g in hu.groupby(['horizon_days','model']):
        for m,v in macro(g.to_dict('records'),fields=(*METRICS,*extra)).items():errors['summary']=max(errors['summary'],abs(v-sm.loc[key,m]))
    assert max(errors.values())<=1e-12,errors
    return dict(passed=True,fitting_roles_checked=len(roles),candidate_id_cells_checked=candidate_rows,candidate_identities_checked=len(saved_scores),
        heldout_grouped_cases_checked=len(held),neutral_anchor_and_gamma_zero_equivalence=True,distinct_ID_sets_and_endpoint_gates_verified=True,
        anchor_first_selection_and_ablations_verified=True,category_probability_and_score_accounting_verified=True,maximum_absolute_errors=errors)


def audit_uncertainty(root,folds,replicates=20000,seed=20261031):
    units=read_frame(root/'heldout_id_cells.parquet');draws=read_frame(root/'bootstrap_draws.csv');diffs=read_frame(root/'paired_differences.csv')
    ids=sorted(folds.id.tolist());w=np.random.Generator(np.random.PCG64(seed)).exponential(size=(replicates,len(ids)))
    meta=json.loads((root/'multiplier_identity.json').read_text());assert hashlib.sha256(w.astype('<f8').tobytes()).hexdigest()==meta['little_endian_float64_sha256']
    assert meta['directional_comparisons']==18 and meta['quantile_method']=='linear'
    ix={d:k for k,d in enumerate(ids)};error=0.
    for (h,m),g in units[units.supported].groupby(['horizon_days','model']):
        agg=np.zeros((replicates,3));nc=g.origin_cell_1.nunique()
        for o,z in g.groupby('origin_cell_1'):
            mass=w[:,[ix[d] for d in z.id]];mass=mass/mass.sum(axis=1)[:,None];agg+=mass@z[list(METRICS)].to_numpy()/nc
        saved=draws[(draws.horizon_days==h)&(draws.model==m)].sort_values('replicate')[list(METRICS)].to_numpy()
        error=max(error,float(np.max(np.abs(agg-saved))))
    for r in diffs.itertuples(index=False):
        h=draws[draws.horizon_days.eq(r.horizon_days)].set_index(['model','replicate']);d=h.xs(r.model,level='model')[r.metric]-h.xs(r.reference,level='model')[r.metric]
        for q,v in [(.025,r.lower_95),(.975,r.upper_95)]:error=max(error,abs(float(np.quantile(d,q))-v))
        if r.primary_comparison:error=max(error,abs(float(np.quantile(d,.05/18 if r.metric=='region90_hit' else 1-.05/18))-r.adjusted_directional_bound))
    decisions=read_frame(root/'decisions.csv')
    assert len(decisions)==6 and int(diffs.primary_comparison.sum())==18
    for r in decisions.itertuples(index=False):
        d=diffs[(diffs.horizon_days==r.horizon_days)&(diffs.reference==r.reference)].set_index('metric')
        b=d.loc['brier','difference']<-1e-12 and d.loc['brier','adjusted_directional_bound']<-1e-12
        c=b and d.loc['region90_hit','difference']>=-1e-12 and d.loc['region90_hit','adjusted_directional_bound']>=-1e-12
        q=c and d.loc['region90_cells','difference']<=1e-12 and d.loc['region90_cells','adjusted_directional_bound']<=1e-12
        strict=q and d.loc['region90_cells','difference']<-1e-12 and d.loc['region90_cells','adjusted_directional_bound']<-1e-12
        assert (r.conditional_Brier_support,r.conditional_coverage_preserving,r.conditional_quality_preserving,r.conditional_smaller_region)==(b,c,q,strict)
    assert error<1e-12,error
    return dict(passed=True,max_error=error,replicates=replicates,draw_identity_verified=True,decision_rules_verified=True)
