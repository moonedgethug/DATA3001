"""Full-law ES and common single 90% quantile ellipse for E2."""
import numpy as np
from . import local_gmm_s5_e2 as gmm
from . import conditional_gaussian_s5_e1 as single
from . import conditional_gaussian_s5_e1_numerics as prior
from data3001.modelling.baselines import position_error_s4_e8 as geometry
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt


def mixture_integrands(first, second, truth, weights):
    first=np.asarray(first);second=np.asarray(second);weights=np.asarray(weights)
    value=np.zeros(first.shape[1])
    for k,w in enumerate(weights):
        value+=w*np.linalg.norm(first[k]-truth,axis=1)
        for l,v in enumerate(weights):value-=.5*w*v*np.linalg.norm(first[k]-second[l],axis=1)
    return value


def score_es(forecast,target,count,key):
    if count not in (8192,16384,32768,65536):raise ValueError('Unregistered ES level')
    truth=opt.xyz(np.asarray(target)[None])[0];means=[]
    for rep in range(8):
        z=gmm.normals(count//8,4,(*key,'energy',rep))
        first=np.asarray([opt.xyz(p) for p in gmm.draw_components(forecast,z[:,:2])])
        second=np.asarray([opt.xyz(p) for p in gmm.draw_components(forecast,z[:,2:])])
        means.append(float(mixture_integrands(first,second,truth,forecast['weights']).mean()))
    return dict(single.replicate_summary(means),sample_count=count)


def build_region(forecast,count,key,geography=None):
    if count not in (32768,65536):raise ValueError('Unregistered region level')
    regions=[];means=[]
    for rep in [0,1]:
        z=gmm.normals(count,2,(*key,'region',rep))
        clouds=gmm.draw_components(forecast,z)
        points=np.concatenate(clouds)
        weights=np.repeat(np.asarray(forecast['weights'])/count,count)
        regions.append(geometry.fit_region(opt.xy(points),weights))
        means.append((weights@opt.xyz(points)).tolist())
    check=gmm.draw_iid(forecast,count,(*key,'region_check'))
    hits=geometry.inside_region(opt.xy(check),regions[0])
    result=dict(region=regions[0],replica_region=regions[1],region_count=count,
        mass_check=single.mass_diagnostic(int(hits.sum()),count,0.),means=means)
    if geography is not None:
        result.update(geography.masses(check,np.full(count,1/count)))
        result['land_variance']=result['land_mass']*(1-result['land_mass'])/count
        result['outside_variance']=result['outside_D_mass']*(1-result['outside_D_mass'])/count
    return result


def empirical_regions(pool,count,key,geography):
    a=geometry.fit_region(pool.xy)
    point=dict(region=a,replica_region=a,mass_check=prior._point_mass(a,pool),
        land_mass=float(pool.land.mean()),outside_D_mass=float(pool.outside.mean()),
        land_variance=0.,outside_variance=0.,region_count=0,means=[pool.xyz.mean(0).tolist()]*2)
    if not pool.usable.any():return {'ExactPoint':point,'EndpointCI':point}
    regions=[];means=[]
    for rep in [0,1]:
        cloud,w,labels=geometry.component_cloud(pool.points,pool.sd,pool.usable,count,('s5_e2_v1',*key,'ci_region',rep))
        if np.max(np.abs(np.bincount(labels,weights=w,minlength=len(pool.points))-1/len(pool.points)))>1e-12:
            raise ValueError('Empirical component votes changed')
        regions.append(geometry.fit_region(opt.xy(cloud),w));means.append((w@opt.xyz(cloud)).tolist())
    rng=gmm.generator((*key,'ci_check'));ix=rng.integers(len(pool.points),size=count)
    check=geometry.perturbed(pool.points[ix],pool.sd[ix],rng.standard_normal((count,2)))
    hits=geometry.inside_region(opt.xy(check),regions[0]);atom=prior.boundary_atom(pool.xy,~pool.usable,regions[0])
    ci=dict(region=regions[0],replica_region=regions[1],region_count=count,means=means,
        mass_check=single.mass_diagnostic(int(hits.sum()),count,atom))
    ci.update(geography.masses(check,np.full(count,1/count)))
    ci.update(land_variance=ci['land_mass']*(1-ci['land_mass'])/count,
        outside_variance=ci['outside_D_mass']*(1-ci['outside_D_mass'])/count)
    return {'ExactPoint':point,'EndpointCI':ci}


def empirical_scores(pool,regions,target,count,key,calibration):
    values=opt.score(pool,{False:regions['ExactPoint'],True:regions['EndpointCI']},target,
        ('s5_e2_v1',*key,'empirical_energy'),count,calibration)
    return {name:dict(energy_km=values[flag]['energy_km'],variance=values[flag]['energy_mc_se']**2,
        energy_mc_se=values[flag]['energy_mc_se'],sample_count=count)
        for flag,name in [(False,'ExactPoint'),(True,'EndpointCI')]}


def iid_es(packet,target,count,key):
    a=opt.xyz(gmm.draw_iid(packet,count,(*key,'iid_first')))
    b=opt.xyz(gmm.draw_iid(packet,count,(*key,'iid_second')))
    v=np.linalg.norm(a-opt.xyz(np.asarray(target)[None])[0],axis=1)-.5*np.linalg.norm(a-b,axis=1)
    return dict(energy_km=float(v.mean()),variance=float(v.var(ddof=1)/count))
