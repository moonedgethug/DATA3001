"""Separate arithmetic paths and whole-cohort identity/numerical checks."""
import hashlib
import json
from collections import Counter
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from data3001.modelling.common.runtime import save_json,save_frame
from . import local_gmm_s5_e2 as gmm
from . import local_gmm_s5_e2_numerics as num
from . import conditional_gaussian_s5_e1_reference as ref
from . import conditional_gaussian_s5_e1_full as io
from . import conditional_gaussian_s5_e1_numerics as old_num


def reference_e(z,w,a,b):
    cols=[]
    for weight,centre,cov in zip(w,a,b):
        delta=z-centre
        cols.append(np.log(weight)-np.log(2*np.pi)-.5*np.linalg.slogdet(cov)[1]
            -.5*np.sum((delta@np.linalg.inv(cov))*delta,axis=1))
    logp=np.array(cols).T;normalizer=logsumexp(logp,axis=1)
    return float(normalizer.mean()),np.exp(logp-normalizer[:,None])


def reference_m(z,r):
    counts=np.sum(r,axis=0);w=counts/len(z)
    a=np.array([np.average(z,axis=0,weights=r[:,k]) for k in range(r.shape[1])]);out=[]
    for k in range(len(w)):
        d=z-a[k];v=np.array([[np.sum(r[:,k]*d[:,i]*d[:,j])/counts[k] for j in range(2)] for i in range(2)])
        eigen,axes=np.linalg.eigh(v);out.append(axes@np.diag(np.maximum(eigen,.01))@axes.T)
    return w,a,np.array(out)


def reference_support(responsibilities,ids,covariances):
    order=np.argsort(ids,kind='stable');sorted_ids=np.asarray(ids)[order]
    starts=np.r_[0,np.flatnonzero(sorted_ids[1:]!=sorted_ids[:-1])+1]
    output=[]
    limits=[('probability',.02,False),('responsibility_count',50,False),
        ('effective_ids',3,False),('material_ids',3,False),
        ('largest_id_share',.5,True),('condition',1e12,True)]
    for k in range(responsibilities.shape[1]):
        values=responsibilities[:,k];count=float(values.sum())
        mass=np.add.reduceat(values[order],starts);eigen=np.linalg.eigvalsh(covariances[k])
        if count<=0 or eigen[0]<=0:raise ValueError('Invalid independently reconstructed component')
        row=dict(probability=count/len(values),responsibility_count=count,
            effective_pairs=count**2/np.sum(values**2),effective_ids=count**2/np.sum(mass**2),
            material_ids=int(np.sum(mass/count>=.01)),largest_id_share=float(mass.max()/count),
            condition=float(eigen[-1]/eigen[0]))
        row['failed']=[field for field,bound,upper in limits if
            (row[field]>bound if upper else row[field]<bound)]
        output.append(row)
    return output


def reference_region_xy(points,weights):
    w=np.asarray(weights);p=np.asarray(points);m=np.average(p,axis=0,weights=w)
    c=np.cov(p.T,aweights=w,bias=True);e,v=np.linalg.eigh(c)
    keep=e>64*np.finfo(float).eps*max(e[-1],0.)
    inverse=np.linalg.inv(c) if keep.all() else (v[:,keep]/e[keep])@v[:,keep].T
    d=p-m;dist=np.sum((d@inverse)*d,axis=1);order=np.argsort(dist,kind='stable')
    ratios=w/w.min();units=np.rint(ratios)
    if units.max()<1e9 and np.all(abs(ratios-units)<=8*np.finfo(float).eps*np.maximum(1,ratios)):
        cumulative=np.cumsum(units[order].astype(np.int64));threshold=(9*int(units.sum())+9)//10
    else:
        cumulative=np.cumsum(w[order],dtype=np.longdouble);threshold=np.longdouble('.9')*np.sum(w,dtype=np.longdouble)
    q=float(dist[order[min(np.searchsorted(cumulative,threshold),len(order)-1)]])
    return dict(centre=m.tolist(),covariance=c.tolist(),inverse=inverse.tolist(),cutoff=q,rank=int(keep.sum()),
        area_km2=float(np.pi*q*np.sqrt(max(np.linalg.det(c),0.))) if keep.all() else 0.,
        null_tolerance_km=float(64*np.finfo(float).eps*max(1.,np.linalg.norm(m),np.sqrt(max(e[-1],0.)))))


def reference_draw(packet,z):
    return [ref.geographic(packet['origin'],np.asarray(m)+z@np.linalg.cholesky(np.asarray(c)).T)
        for m,c in zip(packet['means'],packet['covariances'])]


def reference_energy(packet,truth,count,key):
    target=ref.xyz(np.asarray(truth)[None])[0];means=[]
    for rep in range(8):
        z=gmm.normals(count//8,4,(*key,'independent_energy',rep))
        a=[ref.xyz(p) for p in reference_draw(packet,z[:,:2])]
        b=[ref.xyz(p) for p in reference_draw(packet,z[:,2:])]
        first=sum(w*np.sqrt(np.sum((p-target)**2,axis=1)) for w,p in zip(packet['weights'],a))
        selfdist=sum(w*v*np.sqrt(np.sum((p-q)**2,axis=1)) for w,p in zip(packet['weights'],a) for v,q in zip(packet['weights'],b))
        means.append(float(np.mean(first-selfdist/2)))
    return dict(energy_km=float(np.mean(means)),variance=float(np.var(means,ddof=1)/8),replicate_means=means)


def reference_region(packet,count,key):
    z=gmm.normals(count,2,(*key,'independent_region'))
    points=np.concatenate(reference_draw(packet,z));w=np.repeat(np.asarray(packet['weights'])/count,count)
    xy=np.column_stack(ref.MAP.transform(points[:,0],points[:,1]))/1000
    return reference_region_xy(xy,w)


def audit_parameters(rec,donor,points):
    a,_,d=ref.GEOD.inv(np.full(len(points),rec['origin'][0]),np.full(len(points),rec['origin'][1]),*points.T)
    v=np.column_stack([np.sin(np.deg2rad(a)),np.cos(np.deg2rad(a))])*d[:,None]/1000
    base=ref.fit_vectors(v);L=np.linalg.cholesky(np.asarray(base['covariance']))
    z=(v-base['mean'])@np.linalg.inv(L).T
    ids=donor.id.to_numpy()
    for k,p in rec['models'].items():
        np.testing.assert_allclose(p['base']['covariance'],base['covariance'],rtol=1e-10,atol=1e-7)
        np.testing.assert_allclose(p['base']['mean'],base['mean'],rtol=1e-10,atol=1e-8)
        if int(k)==1 or p['fallback']:
            np.testing.assert_allclose(p['means'],[base['mean']],rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(p['covariances'],[base['covariance']],rtol=1e-10,atol=1e-7)
            np.testing.assert_array_equal(p['weights'],[1.])
        np.testing.assert_allclose(np.asarray(p['cholesky'])@np.transpose(p['cholesky'],(0,2,1)),p['covariances'],rtol=1e-10,atol=1e-7)
        if np.any(np.asarray(p['weights'])<=0):raise ValueError('Invalid forecast mixture probabilities')
        np.testing.assert_allclose(np.sum(p['weights']),1.,rtol=0,atol=1e-10)
        valid=[]
        for restart in p['restarts']:
            if 'likelihood' not in restart:
                if restart['valid']:raise ValueError('Failed restart marked valid')
                if restart['status']=='EMPTY_INITIALISATION':
                    if len(np.unique(z,axis=0))>=int(k):raise ValueError('Unexplained empty initialisation')
                elif restart['status']=='EMPTY_COMPONENT':
                    parameters=[np.asarray(restart[f]) for f in ['white_weights','white_means','white_covariances']]
                    _,r=reference_e(z,*parameters)
                    if np.all(r.sum(0)>0):raise ValueError('Unexplained empty component')
                else:raise ValueError('Unknown failed restart state')
                continue
            params=tuple(np.asarray(restart[f]) for f in ['white_weights','white_means','white_covariances'])
            ll,r=reference_e(z,*params)
            np.testing.assert_allclose(ll-np.log(np.diag(L)).sum(),restart['likelihood'],rtol=0,atol=1e-8)
            if np.linalg.eigvalsh(params[2]).min()<.01-1e-10:raise ValueError('Independent covariance floor check failed')
            nxt=reference_m(z,r)
            residual=max(np.max(abs(x-y))/max(1.,np.max(abs(x))) for x,y in zip(params,nxt))
            np.testing.assert_allclose(residual,restart['fixed_point_residual'],rtol=1e-5,atol=1e-8)
            mapped=L[None]@params[2]@L.T[None]
            np.testing.assert_allclose(mapped,restart['covariances'],rtol=1e-10,atol=1e-7)
            np.testing.assert_allclose(np.asarray(base['mean'])+params[1]@L.T,restart['means'],rtol=1e-10,atol=1e-8)
            diagnostics=reference_support(r,ids,mapped)
            for actual,expected in zip(restart['component_diagnostics'],diagnostics):
                for field in expected:
                    if field=='failed':
                        if actual[field]!=expected[field]:raise ValueError('Component rejection reasons differ')
                    else:np.testing.assert_allclose(actual[field],expected[field],rtol=1e-8,atol=1e-8)
            trace=np.asarray(restart['trace']);increments=np.diff(trace)
            if len(trace)!=restart['iterations']+1 or np.any(increments < -1e-10):
                raise ValueError('Invalid EM convergence trace')
            np.testing.assert_allclose(trace[-1],ll,atol=1e-8,rtol=0)
            converged=len(increments)>=5 and np.all(increments[-5:]<=1e-6) and residual<=1e-4
            accepted=converged and not any(d['failed'] for d in diagnostics)
            status='VALID' if accepted else ('COMPONENT_REJECTED' if converged else 'NOT_CONVERGED')
            if bool(restart['valid'])!=bool(accepted) or restart['status']!=status:
                raise ValueError('Independently reconstructed restart validity differs')
            if restart['valid']:valid.append(restart)
        if int(k)>1:
            if bool(valid)==p['fallback']:raise ValueError('Incorrect whole-query fallback')
            if valid:
                best=valid[0]
                for r in valid[1:]:
                    if r['likelihood']>best['likelihood']+1e-10:best=r
                if p['chosen_restart']!=best['restart']:raise ValueError('Incorrect restart choice')
                for actual,expected in [('means','means'),('covariances','covariances'),('weights','white_weights')]:
                    np.testing.assert_allclose(p[actual],best[expected],rtol=1e-12,atol=1e-10)
    return v,z


def independent_refit(z,p,key):
    """All five starts on prespecified audit cases; independent E/M arithmetic."""
    K=p['K_requested']
    if K==1:return
    for original in p['restarts']:
        rng=gmm.generator((*key,K,original['restart'],'em'))
        centres=[z[int(rng.integers(len(z)))] ];d=np.sum((z-centres[0])**2,axis=1)
        failed=False
        for _ in range(1,K):
            if d.sum()==0:failed=True;break
            centre=z[int(rng.choice(len(z),p=d/d.sum()))];centres.append(centre);d=np.minimum(d,np.sum((z-centre)**2,axis=1))
        if failed:continue
        params=(np.full(K,1/K),np.asarray(centres),np.repeat(np.eye(2)[None],K,axis=0))
        ll,r=reference_e(z,*params);stable=0
        for iteration in range(1,201):
            if np.any(r.sum(0)==0):break
            new=reference_m(z,r);next_ll,next_r=reference_e(z,*new)
            if next_ll<ll-1e-10:raise ValueError('Independent EM monotonicity failed')
            stable=stable+1 if next_ll-ll<=1e-6 else 0
            params,ll,r=new,next_ll,next_r
            if stable>=5:
                nxt=reference_m(z,r)
                residual=max(np.max(abs(x-y))/max(1.,np.max(abs(x))) for x,y in zip(params,nxt))
                if residual<=1e-4:break
        if 'likelihood' in original:
            L=np.asarray(p['base']['cholesky'])
            np.testing.assert_allclose(ll-np.log(np.diag(L)).sum(),original['likelihood'],rtol=0,atol=2e-7)
            if abs(iteration-original['iterations'])>1:raise ValueError('Independent convergence iterations disagree')


def verify_selection_path(table,choice,regions):
    ids=sorted(table.id.unique());roles=['C_T0','C_T1'];scores={};fallback={};by_id={}
    for k in [1,2,3]:
        subset=table[table.model.eq(k)];averages={}
        for role in roles:
            part=subset[subset.role.eq(role)]
            values=[float(group.energy_km.to_numpy().mean()) for _,group in part.groupby('id')]
            scores[role,k]=float(np.mean(values))
            fallback[role,k]=float(np.mean([group.fallback.to_numpy().mean() for _,group in part.groupby('id')]))
            for identity,group in part.groupby('id'):averages.setdefault(identity,[]).append(group.energy_km.to_numpy().mean())
        by_id[k]=np.array([np.mean(averages[identity]) for identity in ids]);scores['pooled',k]=float(by_id[k].mean())
        np.testing.assert_allclose(scores['pooled',k],choice['pooled_scores'][str(k)],atol=1e-10,rtol=0)
        for role in roles:
            np.testing.assert_allclose([scores[role,k],fallback[role,k]],
                [choice['role_scores'][f'{role}:{k}'],choice['fallback_rates'][f'{role}:{k}']],atol=1e-10,rtol=0)

    def weights(rows):
        pairs=list(zip(rows.id,rows.role));counts=Counter(pairs);nroles=Counter(identity for identity,_ in counts)
        return np.array([1/(len(nroles)*nroles[identity]*counts[identity,role]) for identity,role in pairs])

    def numerical(rows,k,baseline):
        keys=['role','id','query_position'];a=rows[rows.model.eq(k)].sort_values(keys);b=rows[rows.model.eq(baseline)].sort_values(keys)
        np.testing.assert_array_equal(a[keys],b[keys]);w=weights(a)
        if 'replicate_means' in rows:
            differences=np.array(a.replicate_means.tolist())-np.array(b.replicate_means.tolist())
            variance=np.var(differences,axis=1,ddof=1)/8
        else:variance=a.variance.to_numpy()+b.variance.to_numpy()
        return float(3*np.sqrt(np.sum(w**2*variance)))

    eligible=[1]
    for k in [2,3]:
        accepted=True
        for role in roles:
            error=numerical(table[table.role.eq(role)],k,1);delta=scores[role,k]-scores[role,1]
            if error>.0001*scores[role,1]:raise ValueError('Independent selection precision failure')
            accepted=accepted and delta<=0 and (delta==0 or error<=.1*abs(delta)) and fallback[role,k]<=.05
        improvement=scores['pooled',1]-scores['pooled',k]
        accepted=accepted and improvement>=.001*scores['pooled',1] and numerical(table,k,1)<=.1*abs(improvement)
        if accepted:eligible.append(k)
    best=1
    for k in eligible[1:]:
        if scores['pooled',k]<scores['pooled',best]-numerical(table,k,best):best=k
    draws=np.random.default_rng(20261110).integers(len(ids),size=(10000,len(ids)))
    provisional=best
    for k in eligible:
        delta=by_id[k]-by_id[best];error=np.std(np.mean(delta[draws],axis=1),ddof=1)
        if delta.mean()<=error:provisional=k;break
    if (eligible,best,provisional)!=(choice['eligible'],choice['best_es_k'],choice['provisional_k']):
        raise ValueError('Independent complexity selection differs')
    selected=provisional
    if provisional>1:
        if regions is None:raise ValueError('Missing quality regions for selected candidate')
        for role in roles:
            pieces={k:regions[regions.role.eq(role)&regions.model.eq(k)].sort_values(['id','query_position']) for k in [1,provisional]}
            a,b=pieces[provisional],pieces[1];w=weights(a)
            average=lambda frame,field:float(np.sum(w*frame[field].to_numpy()))
            hit=average(a,'h90')-average(b,'h90');area=average(a,'area90_km2')/average(b,'area90_km2')-1
            hit_error=average(a,'hit_disagreement')+average(b,'hit_disagreement')
            area_error=sum(abs(average(x,'area_replica_km2')/average(x,'area90_km2')-1) for x in [a,b])
            passed=hit>=0 and area<=0 and hit_error<=.1*abs(hit) and area_error<=.1*abs(area)
            for field,var in [('land_mass','land_variance'),('outside_D_mass','outside_variance')]:
                variance=(np.sqrt(a[var].to_numpy())+np.sqrt(b[var].to_numpy()))**2
                error=3*np.sqrt(np.sum(w*w*variance));delta=average(a,field)-average(b,field)
                passed=passed and delta+error<=.01
            if not passed:selected=1
    if selected!=choice['selected_k']:raise ValueError('Independent quality fallback differs')
    return dict(passed=True,selected_k=selected,provisional_k=provisional,eligible=eligible,
        per_id=[dict(id=int(identity),**{f'K{k}_es':float(by_id[k][j]) for k in [1,2,3]}) for j,identity in enumerate(ids)])


def audit_inner(run,metrics,choice,cfg,budget):
    from . import local_gmm_s5_e2_pipeline as pipe
    paths=pipe.project_paths();count=0;refits=0
    for role in ['C_T0','C_T1']:
        fit,queries,_=pipe.load_role(cfg,role,False)
        selected=set(np.floor(np.arange(64)*(len(queries)-1)/63).astype(int))
        for p in sorted((run['results']/role/'parameters').glob('*.json.gz')):
            records=io.read_bundle(p);batch=int(p.name.split('.')[0])
            with np.load(pipe.batch_paths(run,role,batch)['lineage']) as f:flat,offset=f['indices'],f['offsets']
            for j,rec in enumerate(records):
                ix=io.unpack_lineage(flat,offset,j);donor=fit.iloc[ix]
                digest=hashlib.sha256(donor[pipe.KEY].to_numpy(np.int64).tobytes()).hexdigest()
                if digest!=rec['donor_digest']:raise ValueError('Inner donor identity changed')
                v,z=audit_parameters(rec,donor,donor[['endpoint_lon','endpoint_lat']].to_numpy())
                if rec['query_position'] in selected:
                    for packet in rec['models'].values():independent_refit(z,packet,tuple(rec['key']))
                    refits+=1
                count+=1
            budget.check()
            if count%1024==0:print('INNER_AUDIT',count,'/86373',flush=True)
    # Independently obtain repeated-ID/role averages with explicit ID iteration.
    independent={}
    for K in [1,2,3]:
        ids=[]
        for _,d in metrics[metrics.model.eq(K)].groupby('id'):
            ids.append(np.mean([q.energy_km.to_numpy().mean() for _,q in d.groupby('role')]))
        independent[str(K)]=float(np.mean(ids))
        np.testing.assert_allclose(independent[str(K)],choice['pooled_scores'][str(K)],atol=1e-10,rtol=0)
    regions=pd.concat([pipe.collect(run,role,'region_scores') for role in ['C_T0','C_T1']]) if choice['provisional_k']>1 else None
    path_check=verify_selection_path(metrics,choice,regions)
    save_json(paths,run['provenance']/'inner_audit.json',dict(passed=True,parameter_queries=count,
        independently_refitted_queries=refits,pooled_scores=independent,selection_path=path_check,final_test_access=False))


def audit_record(state,rec,ix,forecast,truth):
    pool=state['pool'].take(ix);donor=state['fit'].iloc[ix]
    digest=hashlib.sha256(donor[['id','origin_source_obs','horizon_days']].to_numpy(np.int64).tobytes()).hexdigest()
    if digest!=rec['donor_digest']:raise ValueError('Outer donor mismatch')
    v,z=audit_parameters(rec,donor,pool.points)
    selected=set(np.floor(np.arange(128)*(33971-1)/127).astype(int))
    key=tuple(rec['key']);cfg=state['cfg'];models={};regions={}
    for k,packet in rec['models'].items():
        if k!='1' and packet['fallback']:
            models[k]=models['1'];regions[k]=regions['1']
        else:
            models[k]=reference_energy(packet,truth,cfg['energy_count'],key)
            regions[k]=reference_region(packet,cfg['region_count'],key)
    # Reuse the independent E1 empirical arithmetic, not the production ES helper.
    base=dict(ref.fit_vectors(v),origin=rec['origin'])
    empirical=ref.energy(pool,base,truth,cfg['energy_count'],(*key,'e2_audit'))
    models.update({k:empirical[k] for k in ['ExactPoint','EndpointCI']})
    regions['ExactPoint']=ref.region(pool.points,np.full(len(pool.points),1/len(pool.points)))
    cloud,w=ref.ci_cloud(pool,cfg['region_count'],(*key,'e2_audit'));regions['EndpointCI']=ref.region(cloud,w)
    labels={'ExactPoint':'ExactPoint','EndpointCI':'EndpointCI','LocalGaussian':'1','LocalGMM':str(state['K'][-1])}
    xy=np.column_stack(ref.MAP.transform(*np.asarray(truth)[None].T))/1000
    if rec['query_position'] in selected:
        fit=state['fit'];_,_,d=ref.GEOD.inv(np.full(len(fit),rec['origin'][0]),np.full(len(fit),rec['origin'][1]),fit.lon.to_numpy(),fit.lat.to_numpy())
        eligible=np.flatnonzero(d<=100000+1e-6);chosen=eligible[np.lexsort((eligible,d[eligible]))]
        if len(chosen)>8000:chosen=chosen[d[chosen]<=d[chosen[7999]]+1e-6]
        np.testing.assert_array_equal(ix,chosen)
        for packet in rec['models'].values():independent_refit(z,packet,key)
    rows=[]
    for name,label in labels.items():
        r=regions[label];primary=forecast['regions'][label]['region'];es=models[label]
        row=dict(role=state['role'],query_position=rec['query_position'],id=rec['id'],model=name,
            energy_km=es['energy_km'],variance=es['variance'],h90=float(ref.inside(xy,r)[0]),
            area90_km2=r['area_km2'],hit_disagreement=float(ref.inside(xy,r)[0]!=ref.inside(xy,primary)[0]),
            original_h90=float(ref.inside(xy,primary)[0]),
            original_area90_km2=float(np.pi*primary['cutoff']*np.sqrt(max(np.linalg.det(primary['covariance']),0.))) if primary['rank']==2 else 0.,
            independent_refit=rec['query_position'] in selected,iid_energy_km=None,iid_variance=None)
        if name=='LocalGMM' and rec['query_position'] in selected:
            iid=num.iid_es(rec['models'][label],truth,65536,(*key,'independent_iid'))
            row.update(iid_energy_km=iid['energy_km'],iid_variance=iid['variance'])
        rows.append(row)
    return rows


def verify_full(paths,run,cfg,budget):
    from . import local_gmm_s5_e2_pipeline as pipe
    t=pipe.collect(run,'C_outer','score');a=pipe.collect(run,'C_outer','audit')
    regions=pipe.check_regions(t);checks={};per_id=[]
    for model_name in ['ExactPoint','EndpointCI','LocalGaussian','LocalGMM']:
        p=t[t.model.eq(model_name)].sort_values('query_position');q=a[a.model.eq(model_name)].sort_values('query_position')
        pipe.validate_keys(p[['id','query_position']],q[['id','query_position']]);w=old_num.id_weights(p.id)
        verify_primary_alignment(p,q)
        expected=np.floor(np.arange(128)*(33971-1)/127).astype(int)
        np.testing.assert_array_equal(q.loc[q.independent_refit,'query_position'],expected)
        for identity in sorted(p.id.unique()):
            pi=p[p.id.eq(identity)];qi=q[q.id.eq(identity)]
            row=dict(model=model_name,id=int(identity),cases=len(pi))
            for field in ['energy_km','h90','area90_km2']:
                row['primary_'+field]=float(np.sum(pi[field].to_numpy())/len(pi))
                row['reference_'+field]=float(np.sum(qi[field].to_numpy())/len(qi))
            row['primary_es_variance']=float(np.sum(pi.variance.to_numpy())/len(pi)**2)
            row['reference_es_variance']=float(np.sum(qi.variance.to_numpy())/len(qi)**2)
            per_id.append(row)
        diff=float(w@(q.energy_km.to_numpy()-p.energy_km.to_numpy()))
        precision=3*np.sqrt(w*w@(p.variance.to_numpy()+q.variance.to_numpy()))
        baseline=float(w@p.energy_km.to_numpy());area=float(w@q.area90_km2.to_numpy()/(w@p.area90_km2.to_numpy())-1)
        hit=float(w@q.hit_disagreement.to_numpy())
        passed=abs(diff)<=max(precision,.0001*baseline) and hit<=.001 and abs(area)<=.005
        checks[model_name]=dict(passed=bool(passed),es_difference=diff,es_three_se=float(precision),
            area_relative_drift=area,hit_disagreement=hit)
    g=t[t.model.eq('LocalGMM')].sort_values('query_position');w=old_num.id_weights(g.id)
    contrast_gates={}
    for base in ['LocalGaussian','ExactPoint','EndpointCI']:
        b=t[t.model.eq(base)].sort_values('query_position')
        if base=='LocalGaussian':
            v=np.var(np.asarray(g.replicate_means.tolist())-np.asarray(b.replicate_means.tolist()),axis=1,ddof=1)/8
        else:v=g.variance.to_numpy()+b.variance.to_numpy()
        se=float(3*np.sqrt(w*w@v));limit=.0001*float(w@b.energy_km.to_numpy())
        contrast_gates[base]=dict(three_se=se,limit=limit,passed=se<=limit)
    iid=verify_iid_alignment(g,a[a.model.eq('LocalGMM') & a.iid_energy_km.notna()])
    passed=all(c['passed'] for c in checks.values()) and all(c['passed'] for c in contrast_gates.values()) and iid['passed']
    result=dict(passed=passed,models=checks,contrast_precision=contrast_gates,region_precision=regions,
        iid_reference_check=iid,complete_cases=33971,ids=45,independent_refit_cases=128,final_test_access=False)
    save_json(paths,run['provenance']/'full_audit.json',result)
    save_frame(paths,run['results']/'independent_per_id.csv',pd.DataFrame(per_id))
    if not passed:raise ArithmeticError('Independent full audit failed: '+str(result))
    budget.check()


def verify_primary_alignment(primary,reference):
    p=primary.sort_values('query_position');a=reference.sort_values('query_position')
    np.testing.assert_array_equal(p[['id','query_position']],a[['id','query_position']])
    np.testing.assert_array_equal(p.h90.to_numpy(),a.original_h90.to_numpy())
    np.testing.assert_allclose(p.area90_km2,a.original_area90_km2,rtol=1e-10,atol=1e-7)


def verify_iid_alignment(primary,reference,expected_positions=None):
    if expected_positions is None:expected_positions=np.floor(np.arange(128)*(33971-1)/127).astype(int)
    a=reference.sort_values('query_position')
    np.testing.assert_array_equal(a.query_position.to_numpy(),expected_positions)
    p=primary.set_index('query_position').loc[expected_positions].reset_index()
    np.testing.assert_array_equal(p[['id','query_position']],a[['id','query_position']])
    direct=p.copy()
    for field in ['iid_energy_km','iid_variance']:direct[field]=a[field].to_numpy()
    main=iid_gate(direct);audit=iid_gate(a)
    return dict(passed=main['passed'] and audit['passed'],primary=main,reference=audit)


def iid_gate(rows):
    if not len(rows):raise ValueError('Missing IID audit cases')
    # Batches without IID cases can leave these numeric columns with object dtype.
    w=old_num.id_weights(rows.id);delta=rows.iid_energy_km.to_numpy(dtype=np.float64)-rows.energy_km.to_numpy(dtype=np.float64)
    variance=rows.iid_variance.to_numpy(dtype=np.float64)+rows.variance.to_numpy(dtype=np.float64)
    bound=float(3*np.sqrt(w*w@variance));effect=float(w@delta)
    scale=np.sqrt(variance);standardised=np.divide(abs(delta),scale,out=np.where(delta==0,0.,np.inf),where=scale>0)
    return dict(cases=len(rows),mean_difference=effect,three_se=bound,max_standardised_difference=float(standardised.max()),
        passed=bool(abs(effect)<=bound and standardised.max()<=6))
