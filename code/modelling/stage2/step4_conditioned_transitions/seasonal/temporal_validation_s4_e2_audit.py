"""Independent counters, explicit squared errors and role checks for validation."""
from collections import Counter, defaultdict
import numpy as np
import pandas as pd
from data3001.modelling.baselines.temporal_validation_s4_e2 import SPECS, SCORE_COLS, METRICS, MODELS


def keys(frame):
    return set(frame[['id','origin_source_obs','horizon_days']].itertuples(index=False,name=None))


def audit_roles(bundle, outer, inner, config):
    q=bundle['q'];folds=bundle['folds'].set_index('id').outer_fold.to_dict();checked=0
    def direct(frame,cut,end):
        c=pd.Timestamp(cut,tz='UTC');e=pd.Timestamp(end,tz='UTC')
        records=list(frame[['id','origin_source_obs','horizon_days','origin_time_UTC','required_interval_end_epoch']].itertuples(index=False))
        v=[r for r in records if c<=r.origin_time_UTC<e]
        ids={r.id for r in v}
        epoch=c.timestamp()
        t=[r for r in records if r.origin_time_UTC<c and r.required_interval_end_epoch<epoch and r.id not in ids]
        return { (r.id,r.origin_source_obs,r.horizon_days) for r in t },{(r.id,r.origin_source_obs,r.horizon_days) for r in v}
    for block in config['blocks']:
        b=block['name'];role=outer[b]
        t,v=direct(q,block['cutoff'],block['end'])
        assert keys(role['train'])==t and keys(role['validation'])==v
        checked+=1
        for k,r in enumerate(inner[b]['G']):
            assert keys(r['validation'])==keys(role['train'][role['train'].id.map(folds).eq(k)])
            assert keys(r['train'])==t-keys(r['validation']);checked+=1
        for (cut,end),r in zip(block['inner_time'],inner[b]['T']):
            ti,vi=direct(role['train'],cut,end)
            assert keys(r['train'])==ti and keys(r['validation'])==vi;checked+=1
        for r in [role,*inner[b]['G'],*inner[b]['T']]:
            assert not set(r['train'].id)&set(r['validation'].id)
            assert not set(r['train'].id)&set(role['validation'].id)
    return {'independent_roles_checked':checked,'cross_horizon_ID_isolation':True}


def reference_fit(train, states):
    ix={int(j):k for k,j in enumerate(states)}
    row=defaultdict(Counter);ids=defaultdict(set);global_count=defaultdict(Counter)
    for r in train[['id','horizon_days','origin_cell_1','destination_cell_1']].itertuples(index=False):
        row[(r.horizon_days,r.origin_cell_1)][r.destination_cell_1]+=1
        ids[(r.horizon_days,r.origin_cell_1)].add(r.id)
        global_count[r.horizon_days][r.destination_cell_1]+=1
    def probability(c):
        p=np.zeros(len(states));n=sum(c.values())
        for j,v in c.items():p[ix[j]]=v/n
        return p
    own={key:probability(c) for key,c in row.items()}
    global_p={h:probability(c) for h,c in global_count.items()}
    n={key:sum(c.values()) for key,c in row.items()}
    medians={h:float(np.median([v for (hh,i),v in n.items() if hh==h])) for h in [7,30]}
    local={}; meta={}; ratios={h:[] for h in [7,30]}
    for h,i in row:
        yi,xi=divmod(int(i),360)
        donor=[k for hh,k in row if hh==h and k!=i and abs(k//360-yi)<=1 and min(abs(k%360-xi),360-abs(k%360-xi))<=1]
        pooled=Counter();di=set()
        for k in donor:pooled.update(row[(h,k)]);di.update(ids[(h,k)])
        L=len(ids[(h,i)]);M=len(di);meta[(h,i)]=(L,M)
        local[(h,i)]=probability(pooled) if pooled else own[(h,i)].copy()
        if M:ratios[h].append(M/L)
    rm={h:float(np.median(ratios[h])) if ratios[h] else 1. for h in [7,30]}
    def vector(h,i,m,a,gamma):
        if (h,i) not in own:return None
        p=own[(h,i)]
        if m=='B2':return p
        L,M=meta[(h,i)]
        if m in ['Fixed','Adaptive']:
            q=global_p[h]
            w=a if m=='Fixed' else 0. if a==0 else 1. if a==1 else medians[h]*a/((1-a)*n[(h,i)]+medians[h]*a)
        else:
            q=local[(h,i)]
            w=0. if M==0 or a==0 else 1. if a==1 else a if m=='LocalEndpoint' or gamma==0 else a*((M/L)/rm[h])**gamma/(1-a+a*((M/L)/rm[h])**gamma)
        return (1-w)*p+w*q
    return vector,own,ix


def audit_inner(role, base, units, reference):
    vector,own,ix=reference;max_error=0.
    lookup=units.set_index(['horizon_days','origin_cell_1','id'])
    by_unit=defaultdict(Counter)
    for r in role['validation'][['id','horizon_days','origin_cell_1','destination_cell_1']].itertuples(index=False):by_unit[(r.horizon_days,r.origin_cell_1,r.id)][r.destination_cell_1]+=1
    assert set(lookup.index)==set(by_unit)
    vec={}
    from data3001.modelling.baselines.local_endpoint_adaptive_s3_e2 import vector as old_vector
    for h,i in own:
        v=np.array([vector(h,i,m,a,g) for m,a,g in SPECS])
        old=np.array([old_vector(base,h,i,m,a,g) for m,a,g in SPECS])
        err=float(np.max(np.abs(v-old)));assert err<=1e-12;max_error=max(max_error,err)
        vec[(h,i)]=v
    for (h,i,d),c in by_unit.items():
        u=lookup.loc[(h,i,d)];assert int(u.eligible_pairs)==sum(c.values())
        assert bool(u.supported)==((h,i) in own)
        if (h,i) not in own:
            assert u[SCORE_COLS].isna().all();continue
        v=vec[(h,i)];at=v[:,[ix[j] for j in c]]
        squared=np.square(1-at)+np.square(v).sum(axis=1)[:,None]-np.square(at)
        bs=squared@np.array(list(c.values()))/sum(c.values())
        err=float(np.max(np.abs(bs-u[SCORE_COLS].to_numpy(float))));assert err<=1e-12;max_error=max(max_error,err)
    return {'role':role['name'],'audited_inner_units':len(by_unit),'maximum_error':max_error}


def audit_selection(parts, selected, pool):
    # Explicit accumulation combines repeated time-fold units before equal-ID weighting.
    weighted={};sizes=Counter()
    for part in parts:
        for r in part.itertuples(index=False):
            if not r.supported:continue
            key=(r.horizon_days,r.origin_cell_1,r.id)
            weighted.setdefault(key,np.zeros(len(SPECS)))
            weighted[key]+=np.array([getattr(r,c) for c in SCORE_COLS])*r.eligible_pairs
            sizes[key]+=r.eligible_pairs
    means=defaultdict(list)
    for key,v in weighted.items():means[key[:2]].append(v/sizes[key])
    for h in [7,30]:
        scores=np.mean([np.mean(v,axis=0) for (hh,i),v in means.items() if hh==h],axis=0)
        assert np.max(np.abs(scores-pool[pool.horizon_days.eq(h)].sort_values('candidate').brier.to_numpy()))<=1e-12
        family=[]
        for m in MODELS:
            candidates=[k for k,(name,a,gamma) in enumerate(SPECS) if name==m]
            best=min(scores[k] for k in candidates)
            tied=[k for k in candidates if scores[k]<=best+1e-12]
            k=min(tied,key=lambda k:(SPECS[k][2],SPECS[k][1]))
            row=selected[(selected.horizon_days==h)&(selected.model==m)].iloc[0]
            assert row.candidate==k;family.append((m,k,scores[k]))
        minimum=min(v for _,_,v in family)
        winner=next(m for m,k,v in family if v<=minimum+1e-12)
        assert selected[selected.horizon_days.eq(h)&selected.winner].model.tolist()==[winner]
    return True


def audit_outer(role, cache, meta, cases, units, summary, reference, block):
    vector,own,ix=reference;max_error=0.;count=Counter();region_sizes={};score_cache={}
    for r in role['validation'][['id','horizon_days','origin_cell_1','destination_cell_1']].itertuples(index=False):count[(r.id,r.horizon_days,r.origin_cell_1,r.destination_cell_1)]+=1
    for r in meta.itertuples(index=False):
        key=(block,r.policy,r.model,r.horizon_days,r.origin_cell_1)
        p=vector(r.horizon_days,r.origin_cell_1,r.selected_family,r.parameter_a,r.parameter_gamma);item=cache[key]
        assert (p is None)==(item is None)
        if p is None:continue
        assert np.max(np.abs(p-item['p']))<=1e-12 and abs(p.sum()-1)<=1e-12
        ordered=sorted([x for x in p if x>0],reverse=True);acc=0.
        for cut in ordered:
            acc+=cut
            if acc>=.9-1e-12:break
        mask=(p>0)&(p>=cut-1e-12)
        assert np.array_equal(mask,item['mask'])
        region_sizes[key]=float(sum(bool(mask[k]) for j,k in ix.items() if j>=0))
        assert region_sizes[key]==item['k90']
    for (policy,m),g in cases.groupby(['policy','model']):
        assert {(r.id,r.horizon_days,r.origin_cell_1,r.destination_cell_1):r.pair_count for r in g.itertuples(index=False)}==count
        direct=defaultdict(lambda:np.zeros(4))
        for r in g.itertuples(index=False):
            prediction_key=(block,policy,m,r.horizon_days,r.origin_cell_1)
            item=cache[prediction_key]
            assert bool(r.supported)==(item is not None)
            if item is None:assert np.isnan(r.brier);continue
            key=prediction_key+(r.destination_cell_1,)
            if key not in score_cache:
                p=item['p'];y=ix[r.destination_cell_1]
                errvec=p.copy();errvec[y]-=1
                score_cache[key]=(float(np.dot(errvec,errvec)),float(item['mask'][y]),region_sizes[prediction_key])
            bs,hit,size=score_cache[key]
            error=max(abs(bs-r.brier),abs(hit-r.h90),abs(size-r.k90));assert error<=1e-12;max_error=max(max_error,error)
            direct[(r.horizon_days,r.origin_cell_1,r.id)]+=r.pair_count*np.array([bs,hit,size,1.])
        expected=defaultdict(list)
        for (h,i,d),v in direct.items():expected[(h,i)].append(v[:3]/v[3])
        for h in [7,30]:
            avg=np.mean([np.mean(a,axis=0) for (hh,i),a in expected.items() if hh==h],axis=0)
            result=summary[(summary.block==block)&(summary.policy==policy)&(summary.model==m)&(summary.horizon_days==h)].iloc[0]
            assert np.max(np.abs(avg-result[METRICS].to_numpy(float)))<=1e-12
    return {'block':block,'independent_outer_cases':len(cases),'maximum_error':max_error}


def audit_uncertainty(units, ids, multipliers, values, intervals, flags, summary, config):
    assert np.array_equal(multipliers,np.random.Generator(np.random.PCG64(config['seed'])).exponential(1.,multipliers.shape))
    lookup={d:k for k,d in enumerate(ids)};index=0;error=0.
    for block in config['blocks']:
        b=block['name']
        for h in [7,30]:
            z=units[(units.block==b)&(units.horizon_days==h)&(units.model=='Selected')&units.scored_pairs.gt(0)]
            outcomes={}
            for policy,g in z.groupby('policy'):
                result=np.zeros((len(multipliers),3))
                for i,c in g.groupby('origin_cell_1'):
                    w=multipliers[:,[lookup[d] for d in c.id]];w=w/w.sum(axis=1)[:,None]
                    result+=np.einsum('rd,dm->rm',w,c[METRICS].to_numpy(),optimize=False)/g.origin_cell_1.nunique()
                outcomes[policy]=result
            delta=outcomes['T']-outcomes['G']
            rel=np.divide(delta[:,2],outcomes['G'][:,2],out=np.full(len(delta),np.nan),where=outcomes['G'][:,2]!=0)
            direct=np.column_stack([delta,rel]);err=float(np.nanmax(np.abs(direct-values[:,index])))
            assert err<=1e-12;error=max(error,err)
            for k,m in enumerate([*METRICS,'relative_k90']):
                ci=intervals[(intervals.block==b)&(intervals.horizon_days==h)&(intervals.metric==m)].iloc[0]
                bounds=np.quantile(direct[:,k],[.025,.975,config['tail'],1-config['tail']])
                assert np.allclose(bounds,ci[['lower95','upper95','adjusted_lower','adjusted_upper']].to_numpy(float),atol=1e-12,rtol=0,equal_nan=True)
            point=summary[(summary.block==b)&(summary.horizon_days==h)&(summary.model=='Selected')].set_index('policy')
            change=(point.loc['T',METRICS]-point.loc['G',METRICS]).to_numpy(float)
            ci=intervals[(intervals.block==b)&(intervals.horizon_days==h)].set_index('metric')
            decision=flags[(flags.block==b)&(flags.horizon_days==h)].iloc[0]
            assert np.max(np.abs(change-decision[['delta_brier','delta_h90','delta_k90']].to_numpy(float)))<=1e-12
            equivalent=all(ci.loc[m,'adjusted_lower']>=-margin and ci.loc[m,'adjusted_upper']<=margin for m,margin in config['equivalence'].items())
            point_gain=change[0]<-1e-12 and change[1]>=-1e-12 and change[2]<=1e-12
            supported=point_gain and ci.loc['brier','adjusted_upper']<-1e-12 and ci.loc['h90','adjusted_lower']>=-1e-12 and ci.loc['k90','adjusted_upper']<=1e-12
            assert bool(decision.equivalent_supported)==bool(equivalent)
            assert bool(decision.quality_point_gain)==bool(point_gain) and bool(decision.quality_supported)==bool(supported)
            index+=1
    return {'independent_multiplier_error':error,'fixed_forecasts_conditional_uncertainty':True}
