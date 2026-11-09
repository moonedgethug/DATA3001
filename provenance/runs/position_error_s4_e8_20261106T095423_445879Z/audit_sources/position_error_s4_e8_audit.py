"""Independent formulas and streams for the E8 continuous comparison.

Reference regions and paired scores intentionally do not call the production
distribution builder, score functions or region fitting functions.
"""
import hashlib
import json
import time
import numpy as np
import pandas as pd
from scipy import sparse
from pyproj import Geod,Transformer

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
from data3001.modelling.baselines import position_error_s4_e8_pipeline as pipe

GEOD=Geod(ellps='WGS84')
MAP=Transformer.from_crs('EPSG:4326','+proj=laea +lon_0=-75 +lat_0=35 +ellps=WGS84 +units=m',always_xy=True)


def reference_xyz(p):
    lon,lat=np.deg2rad(np.asarray(p)).T
    e2=1-(6356752.314245179/6378137.)**2
    radius=6378137./np.sqrt(1-e2*np.sin(lat)**2)
    return np.column_stack([radius*np.cos(lat)*np.cos(lon),radius*np.cos(lat)*np.sin(lon),radius*(1-e2)*np.sin(lat)])/1000


def reference_sd(p,h,ok):
    phi=np.deg2rad(p[:,1]);a=6378137.;b=6356752.314245179
    e2=1-(b/a)**2;den=1-e2*np.sin(phi)**2
    factor=np.column_stack([a*np.cos(phi)/np.sqrt(den),a*(1-e2)/den**1.5])
    widths=np.zeros_like(h)
    widths[ok]=h[ok]*np.pi/180*factor[ok]/(1000*1.9599639845)
    return widths


def reference_shift(p,s,z):
    offset=s*z
    lon,lat,_=GEOD.fwd(p[:,0],p[:,1],np.degrees(np.arctan2(offset[:,0],offset[:,1])),np.linalg.norm(offset,axis=1)*1000)
    result=np.column_stack([lon,lat]);zero=np.all(offset==0,axis=1);result[zero]=p[zero]
    return result


def reference_region(p,w,truth):
    xy=np.array(MAP.transform(p[:,0],p[:,1])).T/1000
    centre=np.sum(xy*w[:,None],axis=0);centered=xy-centre
    covariance=np.cov(xy.T,aweights=w,bias=True)
    values,vectors=np.linalg.eigh(covariance)
    active=values>64*np.finfo(float).eps*max(values[-1],0)
    if active.all():inverse=np.linalg.inv(covariance)
    else:inverse=(vectors[:,active]/values[active])@vectors[:,active].T
    distance=np.sum((centered@inverse)*centered,axis=1)
    order=np.argsort(distance,kind='stable');cumulative=np.cumsum(w[order])
    cutoff=distance[order[min(int(np.searchsorted(cumulative,.9)),len(p)-1)]]
    target=np.array(MAP.transform(truth[0],truth[1]))/1000-centre
    hit=bool(target@inverse@target<=cutoff+1e-12)
    nulltol=64*np.finfo(float).eps*max(1.,np.linalg.norm(centre),np.sqrt(max(values[-1],0)))
    if not active.all():hit=hit and np.linalg.norm(target-target@covariance@inverse)<=nulltol
    area=float(np.pi*cutoff*np.sqrt(max(np.linalg.det(covariance),0))) if active.all() else 0.
    return dict(centre=centre,inverse=inverse,covariance=covariance,rank=int(active.sum()),
                cutoff=float(cutoff),nulltol=nulltol,area=area,hit=float(hit),xy=xy)


def mass_in_frozen(p,w,region):
    xy=np.array(MAP.transform(p[:,0],p[:,1])).T/1000
    residual=xy-np.array(region['centre']);inv=np.array(region['inverse'])
    inside=np.sum((residual@inv)*residual,axis=1)<=region['cutoff']+1e-12
    if region['rank']<2:
        inside &= np.linalg.norm(residual-residual@np.array(region['covariance'])@inv,axis=1)<=region['null_tolerance_km']
    return float(w@inside)


def reference_clouds(p,sd,ok,key,count=16384):
    valid=np.flatnonzero(ok);invalid=np.flatnonzero(~ok);n=len(p)
    if not len(valid):
        for name in ['EndpointCI','MatchedSpread']:yield name,p,np.full(n,1/n)
        return
    per=2*((count-len(invalid))//(2*len(valid)))
    if per<2:raise ValueError('Audit quadrature cannot retain all donors')
    seed=int.from_bytes(hashlib.sha256(('independent_region:'+str(key)).encode()).digest()[:16],'big')
    rng=np.random.Generator(np.random.PCG64(seed))
    z=rng.standard_normal((len(valid)*(per//2),2));z=np.concatenate([z,-z])
    idx=np.tile(np.repeat(valid,per//2),2)
    w=np.concatenate([np.full(len(idx),1/(n*per)),np.full(len(invalid),1/n)])
    common=np.zeros_like(sd);common[ok]=np.sqrt(np.sum(sd[ok]**2,axis=0)/len(valid))
    for name,widths in [('EndpointCI',sd),('MatchedSpread',common)]:
        sample=reference_shift(p[idx],widths[idx],z)
        yield name,np.concatenate([sample,p[invalid]]),w


def reference_energy(p,sd,ok,truth,key,count=65536):
    """Direct independent coupled contrasts, including self-pair draws."""
    seed=int.from_bytes(hashlib.sha256(('independent_energy:'+str(key)).encode()).digest()[:16],'big')
    rng=np.random.Generator(np.random.PCG64(seed));n=len(p)
    a=rng.integers(n,size=count);b=rng.integers(n,size=count)
    z1=rng.normal(size=(count,2));z2=rng.normal(size=(count,2))
    xyz=reference_xyz(p);y=reference_xyz(np.asarray(truth)[None,:])[0]
    first0=np.linalg.norm(xyz[a]-y,axis=1);second0=np.linalg.norm(xyz[a]-xyz[b],axis=1)
    base=float(np.linalg.norm(xyz-y,axis=1).mean()-.5*second0.mean())
    common=np.zeros_like(sd)
    if ok.any():common[ok]=np.sqrt(np.mean(sd[ok]**2,axis=0))
    rows={};contrasts={}
    for name,widths in [('EndpointCI',sd),('MatchedSpread',common)]:
        u=reference_xyz(reference_shift(p[a],widths[a],z1));v=reference_xyz(reference_shift(p[b],widths[b],z2))
        difference=np.linalg.norm(u-y,axis=1)-first0-.5*(np.linalg.norm(u-v,axis=1)-second0)
        contrasts[name]=difference
        rows[name]=dict(delta=float(difference.mean()),se=float(difference.std(ddof=1)/np.sqrt(count)),absolute_ES=base+float(difference.mean()))
    contrast=contrasts['EndpointCI']-contrasts['MatchedSpread']
    rows['EndpointCI_minus_MatchedSpread']=dict(delta=float(contrast.mean()),se=float(contrast.std(ddof=1)/np.sqrt(count)))
    return rows


def audit(paths,run,cfg,approval,guard):
    if (run['provenance']/'audit.json').exists():raise FileExistsError('Preserve prior audits')
    formal=json.loads((run['provenance']/'formal_resources.json').read_text());assert formal['completed']
    start=time.monotonic();passed=False
    try:
        pipe.source_snapshot(paths,run,'audit_sources')
        train,ledger=inputs.load_training(cfg);fit,query,_=inputs.load_role(cfg,'C_outer',train,ledger)
        target=inputs.release_outer_targets(run,cfg,approval).sort_values(inputs.KEY).reset_index(drop=True)
        pd.testing.assert_frame_equal(query[inputs.KEY],target[inputs.KEY]);assert not target.outside.any()
        points=fit[['endpoint_lon','endpoint_lat']].to_numpy();ok=fit.ci_2d_usable.to_numpy(bool)
        sd=reference_sd(points,fit[['repaired_err_lon','repaired_err_lat']].to_numpy(),ok)
        np.testing.assert_allclose(sd,fit[['sd_e_km','sd_n_km']].to_numpy(),rtol=2e-14,atol=1e-14)
        # Local metric conversion versus actual coordinate-offset distances.
        checks=[]
        for axis in [0,1]:
            choose=np.argsort(sd[:,axis])[-32:];p=points[choose];h=fit[['repaired_err_lon','repaired_err_lat']].to_numpy()[choose]
            displaced=p.copy();displaced[:,axis]+=h[:,axis]
            _,_,distance=GEOD.inv(p[:,0],p[:,1],displaced[:,0],displaced[:,1])
            checks.append(float(np.max(abs(distance/1000-sd[choose,axis]*1.9599639845)/(sd[choose,axis]*1.9599639845))))
        assert max(checks)<.001
        cases=inputs.read_frame(run['results']/'case_scores.parquet');d=inputs.read_frame(run['results']/'formal/donor_diagnostics.parquet')
        assert len(cases)==33971*4 and cases.id.nunique()==45
        assert not cases.duplicated(['query_position','model']).any()
        assert d.query_position.tolist()==list(range(33971))
        historical=inputs.read_frame(inputs.ROOT/'results/runs'/cfg['e7_run']/'outer_roster.parquet',
                    columns=inputs.KEY+['n','lineage_digest']).sort_values(inputs.KEY).reset_index(drop=True)
        pd.testing.assert_frame_equal(query[inputs.KEY],historical[inputs.KEY])
        np.testing.assert_array_equal(d.lineage_digest,historical.lineage_digest)
        np.testing.assert_array_equal(d.donors,historical.n)
        e7=inputs.ROOT/'results/runs'/cfg['e7_run']
        e7_receipt=json.loads((inputs.ROOT/'provenance/runs'/cfg['e7_run']/'outputs.json').read_text())
        for name in ['forecasts/Exact_0p5_probabilities.npz','forecasts/Exact_0p5_states.npy']:
            path=e7/name
            assert file_sha256(path)==e7_receipt['output_sha256'][str(path.relative_to(inputs.ROOT))]
        old_probability=sparse.load_npz(e7/'forecasts/Exact_0p5_probabilities.npz')
        old_states=np.load(e7/'forecasts/Exact_0p5_states.npy')
        donor_display=fit.destination_cell_05.to_numpy()
        expected_cases=cases.set_index(['query_position','model'])
        summary=pd.read_csv(run['results']/'summary.csv').set_index('model')
        metrics=['energy_km','h90','area90_km2','auxiliary','land_mass','outside_D_mass']
        for name,g in cases.groupby('model'):
            for col in metrics:
                manual=np.mean([part[col].to_numpy().mean() for _,part in g.groupby('id')])
                np.testing.assert_allclose(manual,summary.loc[name,col],rtol=1e-12,atol=1e-11)
        examples=json.loads((run['results']/'formal/example_selection.json').read_text())['query_positions']
        sample=set(examples+np.linspace(0,len(query)-1,122,dtype=int).tolist())
        for j in range(len(query)):
            if len(sample)>=128:break
            sample.add(j)
        save_json(paths,run['provenance']/'audit_selection.json',dict(query_positions=sorted(sample),outcome_based=False,region_replicates='all 33971 queries'))
        index=pipe.index_for(fit,cfg);cells={int(c):g.index.to_numpy() for c,g in fit.groupby('origin_cell_1')}
        region_rows=[];energy_rows=[];max_lineage_distance_error=0.
        with (run['results']/'formal/forecasts.jsonl').open() as stream,(run['results']/'formal/donors.i32').open('rb') as raw:
            for j,line in enumerate(stream):
                if j%128==0:pipe.check_budget(run,cfg,start,'audit')
                packet=json.loads(line);row=d.iloc[j];q=query.iloc[j]
                selected=np.frombuffer(raw.read(int(row.donors)*4),dtype='<i4')
                assert pipe.digest_indices(selected)==row.lineage_digest
                codes,counts=np.unique(donor_display[selected],return_counts=True)
                lo,hi=old_probability.indptr[j:j+2]
                np.testing.assert_array_equal(codes,old_states[old_probability.indices[lo:hi]])
                np.testing.assert_allclose(counts/len(selected),old_probability.data[lo:hi],rtol=0,atol=1e-12)
                assert len(np.unique(selected))==len(selected)
                assert np.isclose(ok[selected].mean(),row.error_available_fraction,rtol=0,atol=1e-15)
                assert abs(1-row.error_available_fraction-row.fallback_mass)<1e-14
                truth=target.iloc[j][['endpoint_lon','endpoint_lat']].to_numpy(float);p=points[selected];s=sd[selected];o=ok[selected]
                for name,cloud,w in reference_clouds(p,s,o,(int(q.id),int(q.origin_source_obs))):
                    assert abs(w.sum()-1)<1e-10
                    r=reference_region(cloud,w,truth);original=packet['forecast'][name]['region']
                    score=expected_cases.loc[(j,name)]
                    region_rows.append(dict(query_position=j,id=int(q.id),model=name,area_reference=r['area'],hit_reference=r['hit'],
                        area_difference=r['area']-score.area90_km2,hit_difference=r['hit']-score.h90,
                        mass_difference=mass_in_frozen(cloud,w,original)-original['attained_mass']))
                if j in sample:
                    selected_again,dist=index.query(q.lon,q.lat,cfg['k'])
                    np.testing.assert_array_equal(selected,selected_again)
                    if j in examples:
                        exhaustive,ed=index.exhaustive(q.lon,q.lat,cfg['k'])
                        np.testing.assert_array_equal(selected,exhaustive)
                        max_lineage_distance_error=max(max_lineage_distance_error,float(np.max(abs(dist-ed))))
                    for name,idx in [('ExactPoint',selected),('B2Point',cells[int(q.origin_cell_1)])]:
                        r=reference_region(points[idx],np.full(len(idx),1/len(idx)),truth)
                        score=expected_cases.loc[(j,name)]
                        np.testing.assert_allclose(r['area'],score.area90_km2,rtol=1e-11,atol=1e-7)
                        assert r['hit']==score.h90
                    ref=reference_energy(p,s,o,truth,(int(q.id),int(q.origin_source_obs)))
                    for name,result in ref.items():
                        estimate=float(expected_cases.loc[(j,'EndpointCI'),'energy_km']-expected_cases.loc[(j,'MatchedSpread'),'energy_km']) if name=='EndpointCI_minus_MatchedSpread' else float(expected_cases.loc[(j,name),'delta_energy_vs_exact_km'])
                        energy_rows.append(dict(query_position=j,id=int(q.id),model=name,reference_delta=result['delta'],reference_se=result['se'],production_delta=estimate,difference=result['delta']-estimate))
                if (j+1)%1024==0:print('independent region audit',j+1,'/33971',round(time.monotonic()-start,1),'s',flush=True)
        regions=pd.DataFrame(region_rows);energy=pd.DataFrame(energy_rows)
        save_frame(paths,run['results']/'audit_region_replication.parquet',regions)
        save_frame(paths,run['results']/'audit_energy_replication.csv',energy)
        detail={}
        for name,g in regions.groupby('model'):
            byid=g.groupby('id')[['area_difference','hit_difference','mass_difference']].mean()
            detail[name]=dict(area_relative_difference=float(abs(byid.area_difference.mean())/summary.loc[name,'area90_km2']),
                H90_difference=float(byid.hit_difference.mean()),absolute_H90_boundary_change=float(g.assign(changed=g.hit_difference.abs()).groupby('id').changed.mean().mean()),
                max_mass_difference=float(g.mass_difference.abs().max()),mean_mass_difference=float(byid.mass_difference.mean()))
        reference_energy_difference={name:float(g.groupby('id').difference.mean().mean()) for name,g in energy.groupby('model')}
        precision=all(v['area_relative_difference']<=.005 and v['absolute_H90_boundary_change']<=.001 and v['max_mass_difference']<=.005 for v in detail.values())
        threshold=.0001*summary.loc['ExactPoint','energy_km']
        precision=precision and abs(reference_energy_difference['EndpointCI'])<=threshold
        numeric=json.loads((run['results']/'numerical_summary.json').read_text())
        precision=precision and numeric['three_se_km']<=threshold
        # Independently reconcile the actual stored resampling indices and all
        # paired bootstrap results; hourly records are never iid bootstrap units.
        boot=np.load(run['results']/'bootstrap.npz');ids=pd.read_csv(run['results']/'per_ID.csv')
        names=boot['models'].tolist();cols=boot['metrics'].tolist();identity=boot['ids'];draws=boot['draws']
        assert np.array_equal(draws,np.random.Generator(np.random.PCG64(20261106)).integers(45,size=(10000,45)))
        ref=np.stack([ids[ids.model.eq(name)].set_index('id').loc[identity,cols].to_numpy() for name in names],axis=1)
        for startrow in range(0,10000,250):
            np.testing.assert_allclose(ref[draws[startrow:startrow+250]].sum(axis=1)/45,boot['values'][startrow:startrow+250],rtol=1e-12,atol=1e-9)
        for name,digest in approval['protected_files'].items():assert file_sha256(inputs.ROOT/name)==digest,name
        freeze=json.loads((run['provenance']/'forecast_freeze.json').read_text())
        for name,digest in freeze['source_sha256'].items():assert file_sha256(inputs.ROOT/name)==digest,name
        assert not guard.denied
        contrasts=pd.read_csv(run['results']/'contrasts.csv');main=contrasts[(contrasts.candidate=='EndpointCI')&(contrasts.control=='ExactPoint')].iloc[0]
        if not precision:conclusion='numerically inconclusive'
        elif not main.practical_ES_benefit:conclusion='practically tiny effect; no useful improvement demonstrated'
        elif not main.supported_ES_benefit:conclusion='evidence insufficient'
        elif not (main.point_quality_direction and main.interval_quality_guardrails and main.geographic_guardrails):conclusion='ES benefit with trade-off'
        else:conclusion='supported benefit with guardrails met'
        passed=bool(precision)
        audit=dict(passed=passed,engineering_passed=True,numerical_passed=bool(precision),conclusion=conclusion,
            cases=33971,IDs=45,independent_region_cases=33971,independent_energy_cases=128,
            local_metric_relative_error_max=max(checks),region_replication=detail,energy_reference_delta_change=reference_energy_difference,
            delta_ES_resolution_threshold_km=threshold,numerical_summary=numeric,protected_files_verified=len(approval['protected_files']),
            source_freeze_verified=True,all_donor_digests_verified=True,all_E7_outer_lineages_identical=True,
            all_ExactPoint_half_degree_probabilities_reconciled=True,bootstrap_IDs=45,bootstrap_draws=10000,
            final_test_access=False,outer_endpoint_errors_read=False,denied_access=guard.denied,
            interpretation='Same frozen development sample; no new physical or real-time calibration claim')
        save_json(paths,run['provenance']/'audit.json',audit)
        print(json.dumps(audit,indent=2),flush=True)
    finally:
        r=pipe.resources(run,start);r['completed']=passed
        save_json(paths,run['provenance']/'audit_resources.json',r)


def main():
    import argparse
    p=argparse.ArgumentParser();p.add_argument('--run',required=True);a=p.parse_args()
    audit(*inputs.context(a.run))

if __name__=='__main__':main()
