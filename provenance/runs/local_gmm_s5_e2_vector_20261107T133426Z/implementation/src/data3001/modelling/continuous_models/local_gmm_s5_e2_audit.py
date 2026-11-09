"""Separate arithmetic paths and whole-cohort identity/numerical checks."""
import hashlib
import json
import numpy as np
import pandas as pd
from scipy.special import logsumexp
from data3001.modelling.common.runtime import save_json
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
    ids=donor.id.to_numpy();order=np.argsort(ids,kind='stable');sorted_ids=ids[order]
    group_starts=np.r_[0,np.flatnonzero(sorted_ids[1:]!=sorted_ids[:-1])+1]
    for k,p in rec['models'].items():
        np.testing.assert_allclose(p['base']['covariance'],base['covariance'],rtol=1e-10,atol=1e-7)
        np.testing.assert_allclose(p['base']['mean'],base['mean'],rtol=1e-10,atol=1e-8)
        if int(k)==1 or p['fallback']:
            np.testing.assert_allclose(p['means'],[base['mean']],rtol=1e-10,atol=1e-8)
            np.testing.assert_allclose(p['covariances'],[base['covariance']],rtol=1e-10,atol=1e-7)
            np.testing.assert_array_equal(p['weights'],[1.])
        np.testing.assert_allclose(np.asarray(p['cholesky'])@np.transpose(p['cholesky'],(0,2,1)),p['covariances'],rtol=1e-10,atol=1e-7)
        valid=[]
        for restart in p['restarts']:
            if 'likelihood' not in restart:continue
            params=tuple(np.asarray(restart[f]) for f in ['white_weights','white_means','white_covariances'])
            ll,r=reference_e(z,*params)
            np.testing.assert_allclose(ll-np.log(np.diag(L)).sum(),restart['likelihood'],rtol=0,atol=1e-8)
            if np.linalg.eigvalsh(params[2]).min()<.01-1e-10:raise ValueError('Independent covariance floor check failed')
            nxt=reference_m(z,r)
            residual=max(np.max(abs(x-y))/max(1.,np.max(abs(x))) for x,y in zip(params,nxt))
            np.testing.assert_allclose(residual,restart['fixed_point_residual'],rtol=1e-5,atol=1e-8)
            for j,diag in enumerate(restart['component_diagnostics']):
                masses=np.add.reduceat(r[order,j],group_starts);n=r[:,j].sum()
                np.testing.assert_allclose([n*n/(masses@masses),masses.max()/n,n/len(r)],
                    [diag['effective_ids'],diag['largest_id_share'],diag['probability']],rtol=1e-8,atol=1e-8)
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
    save_json(paths,run['provenance']/'inner_audit.json',dict(passed=True,parameter_queries=count,
        independently_refitted_queries=refits,pooled_scores=independent,final_test_access=False))


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
            independent_refit=rec['query_position'] in selected,iid_energy_km=None,iid_variance=None)
        if name=='LocalGMM' and rec['query_position'] in selected:
            iid=num.iid_es(rec['models'][label],truth,65536,(*key,'independent_iid'))
            row.update(iid_energy_km=iid['energy_km'],iid_variance=iid['variance'])
        rows.append(row)
    return rows


def verify_full(paths,run,cfg,budget):
    from . import local_gmm_s5_e2_pipeline as pipe
    t=pipe.collect(run,'C_outer','score');a=pipe.collect(run,'C_outer','audit')
    regions=pipe.check_regions(t);checks={}
    for model_name in ['ExactPoint','EndpointCI','LocalGaussian','LocalGMM']:
        p=t[t.model.eq(model_name)].sort_values('query_position');q=a[a.model.eq(model_name)].sort_values('query_position')
        pipe.validate_keys(p[['id','query_position']],q[['id','query_position']]);w=old_num.id_weights(p.id)
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
    iid=iid_gate(a[a.model.eq('LocalGMM') & a.iid_energy_km.notna()])
    passed=all(c['passed'] for c in checks.values()) and all(c['passed'] for c in contrast_gates.values()) and iid['passed']
    result=dict(passed=passed,models=checks,contrast_precision=contrast_gates,region_precision=regions,
        iid_reference_check=iid,complete_cases=33971,ids=45,independent_refit_cases=128,final_test_access=False)
    save_json(paths,run['provenance']/'full_audit.json',result)
    if not passed:raise ArithmeticError('Independent full audit failed: '+str(result))
    budget.check()


def iid_gate(rows):
    if not len(rows):raise ValueError('Missing IID audit cases')
    w=old_num.id_weights(rows.id);delta=rows.iid_energy_km.to_numpy()-rows.energy_km.to_numpy()
    variance=rows.iid_variance.to_numpy()+rows.variance.to_numpy()
    bound=float(3*np.sqrt(w*w@variance));effect=float(w@delta)
    scale=np.sqrt(variance);standardised=np.divide(abs(delta),scale,out=np.where(delta==0,0.,np.inf),where=scale>0)
    return dict(cases=len(rows),mean_difference=effect,three_se=bound,max_standardised_difference=float(standardised.max()),
        passed=bool(abs(effect)<=bound and standardised.max()<=6))
