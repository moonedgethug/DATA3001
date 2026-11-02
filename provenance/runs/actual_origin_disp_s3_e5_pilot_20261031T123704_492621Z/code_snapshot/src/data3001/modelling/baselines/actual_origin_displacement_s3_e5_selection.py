"""Approved E5 v2 Brier solvers and finite quality-feasibility searches."""
from dataclasses import dataclass
import time
import numpy as np
from scipy.optimize import minimize
from scipy.special import expit
from data3001.modelling.common.prediction_regions import checked_distribution, probability_region

EPS=1e-12
GRID=tuple(k/20 for k in range(21))
GAMMAS=(0.,.5,1.,2.)
METRICS=('brier','region90_cells','region90_hit')


def weight_gradient(a,gamma,z):
    z=np.asarray(z,float)
    if not np.isfinite([a,gamma]).all() or not 0<=a<=1 or not 0<=gamma<=2 or not np.isfinite(z).all() or (z<0).any():
        raise ValueError('Invalid bounded parameter/support')
    active=z>0;lam=np.zeros_like(z);da=np.zeros_like(z);dg=np.zeros_like(z)
    logz=np.log(z[active]);t=np.exp(gamma*logz)
    if a==0:lam[active]=0;da[active]=t
    elif a==1:lam[active]=1;da[active]=1/t
    else:
        lam[active]=float(a) if gamma==0 else expit(np.log(a)-np.log1p(-a)+gamma*logz)
        da[active]=t/(1-a+a*t)**2
        dg[active]=lam[active]*(1-lam[active])*logz
    if not all(np.isfinite(v).all() for v in (lam,da,dg)):
        raise FloatingPointError('Nonfinite adaptive weight/gradient')
    return lam,da,dg


def quadratic_terms(p,q,truth_index):
    p,q=np.asarray(p,float),np.asarray(q,float)
    if p.shape!=q.shape or not np.isfinite([p,q]).all():raise ValueError('Invalid forecast pair')
    d=q-p
    return np.array([d@d,2*(p@d-d[truth_index]),1+p@p-2*p[truth_index]])


def analytic_weight(coefficients):
    A,B,C=map(float,coefficients)
    if not np.isfinite([A,B,C]).all() or A<0:raise ValueError('Invalid Brier coefficients')
    if A==0:
        if abs(B)>EPS:raise ValueError('Inconsistent degenerate quadratic')
        return 0.
    return float(np.clip(-B/(2*A),0,1))


@dataclass
class ForecastCase:
    states: np.ndarray
    p: np.ndarray
    q: np.ndarray
    truth: int
    z: float
    weight: float
    block: tuple


class CaseEvaluator:
    """Exact per-query score before weighted ID/origin aggregation."""
    def __init__(self,cases,check=lambda:None):
        self.cases=list(cases);self.check=check;blocks={}
        if not self.cases or not np.isclose(sum(c.weight for c in cases),1,rtol=0,atol=EPS):
            raise ValueError('Expected positive normalised primary query weights')
        for c in cases:
            checked_distribution(c.p,c.states);checked_distribution(c.q,c.states)
            if c.weight<=0 or c.z<0 or not np.isfinite([c.weight,c.z]).all():raise ValueError('Invalid case weight/support')
            truth=np.flatnonzero(c.states==c.truth)
            if len(truth)!=1:raise ValueError('Include zero-probability truth in sparse support')
            key=(*c.block,float(c.z))
            blocks[key]=blocks.get(key,np.zeros(3))+c.weight*quadratic_terms(c.p,c.q,int(truth[0]))
        self.keys=sorted(blocks);self.coefficients=np.array([blocks[k] for k in self.keys])
        self.z=np.array([k[-1] for k in self.keys])
        self.fixed=self.coefficients.sum(axis=0)

    def objective(self,theta):
        lam,da,dg=weight_gradient(*theta,self.z)
        A,B,C=self.coefficients.T
        loss=float(np.sum((A*lam+B)*lam+C));slope=2*A*lam+B
        gradient=np.array([slope@da,slope@dg])
        if not np.isfinite(loss) or not np.isfinite(gradient).all():raise FloatingPointError('Invalid objective')
        return loss,gradient

    def metrics(self,a,gamma):
        total=np.zeros(4)
        for n,c in enumerate(self.cases):
            if n%256==0:self.check()
            lam=float(weight_gradient(a,gamma,np.array([c.z]))[0][0])
            p=(1-lam)*c.p+lam*c.q
            region,meta=probability_region(p,c.states)
            loc=int(np.flatnonzero(c.states==c.truth)[0])
            total+=c.weight*np.array([1+p@p-2*p[loc],meta['region90_cells'],float(region[loc]),meta['region90_mass']])
        if abs(total[0]-self.objective((a,gamma))[0])>EPS:
            raise AssertionError('Coefficient and direct Brier disagree')
        return dict(zip((*METRICS,'region90_mass'),map(float,total)))


def best_brier(rows):
    rows=list(rows)
    if not rows:raise ValueError('Empty candidate pool')
    low=min(r['brier'] for r in rows)
    return min((r for r in rows if r['brier']<=low+EPS),key=lambda r:(r['gamma'],r['a']))


def quality_thresholds(references):
    if set(references)!={'LocalEndpointAdaptive','Fixed'}:raise ValueError('Both quality references required')
    return dict(H=max(r['region90_hit'] for r in references.values()),
                K=min(r['region90_cells'] for r in references.values()),
                B=min(r['brier'] for r in references.values()))


def select_pool(rows,thresholds):
    rows=list(rows);unconstrained=best_brier(rows)
    feasible=[r for r in rows if r['feasible']]
    improving=[r for r in feasible if r['brier']<thresholds['B']-EPS]
    status=('inner_admissible' if improving else
            'no_inner_Brier_gain' if feasible else 'no_feasible_candidate_in_searched_pool')
    selected=best_brier(improving) if improving else unconstrained
    return dict(selected=selected,unconstrained=unconstrained,status=status,
                eligible_for_replacement=bool(improving),feasible_count=len(feasible),
                improving_count=len(improving),pool_size=len(rows))


class CallLimit(RuntimeError):
    pass


def continuous_minima(evaluator,grid_best,a_star,check=lambda:None):
    starts={(a,g) for a in (.1,.5,.9) for g in (.25,1.,1.75)}
    starts.update([(grid_best['a'],grid_best['gamma']),(a_star,0.)])
    traces=[];runs=[];retained=[]
    for start_id,start in enumerate(sorted(starts,key=lambda x:(x[1],x[0]))):
        evaluated=[]
        def objective(theta):
            check()
            if len(evaluated)>=2000:raise CallLimit('hard_2000_calls')
            loss,grad=evaluator.objective(theta)
            row=dict(start_id=start_id,call=len(evaluated),a=float(theta[0]),gamma=float(theta[1]),
                     brier=loss,gradient_a=float(grad[0]),gradient_gamma=float(grad[1]))
            evaluated.append(row)
            return loss,grad
        try:
            result=minimize(objective,start,method='L-BFGS-B',jac=True,bounds=((0,1),(0,2)),
                options=dict(maxiter=200,maxfun=2000,maxls=20,maxcor=10,ftol=1e-12,gtol=1e-8))
            success=bool(result.success);message=str(result.message)
        except CallLimit as exc:
            success=False;message=str(exc)
        if not evaluated:raise AssertionError('Optimiser did not evaluate initial point')
        # Retain the actual smallest evaluated loss; deterministic exact ties.
        best=min(evaluated,key=lambda r:(r['brier'],r['gamma'],r['a']))
        retained.append((best['a'],best['gamma']));traces.extend(evaluated)
        grad=np.array([best['gradient_a'],best['gradient_gamma']])
        theta=np.array([best['a'],best['gamma']]);upper=np.array([1.,2.])
        projected=grad.copy()
        projected[(theta==0)&(grad>0)]=0;projected[(theta==upper)&(grad<0)]=0
        runs.append(dict(start_id=start_id,start_a=start[0],start_gamma=start[1],success=success,
                         message=message,calls=len(evaluated),best_a=best['a'],best_gamma=best['gamma'],
                         best_brier=best['brier'],projected_gradient=float(np.abs(projected).max())))
    return retained,runs,traces


def search(evaluator,references,check=lambda:None):
    """All four approved procedures; full-metric union is bounded by 252 points."""
    thresholds=quality_thresholds(references);cache={};members={};stage_calls=[]
    def score(a,gamma,stage):
        check();key=(float(a),float(gamma))
        if key not in cache:
            tick=time.monotonic();m=evaluator.metrics(*key)
            if not np.isfinite(list(m.values())).all():raise FloatingPointError('Nonfinite quality metric')
            feasible=m['region90_hit']>=thresholds['H']-EPS and m['region90_cells']<=thresholds['K']+EPS
            violation=max(0.,thresholds['H']-EPS-m['region90_hit'],
                          (m['region90_cells']-thresholds['K']-EPS)/max(1,thresholds['K']))
            cache[key]=dict(a=key[0],gamma=key[1],**m,feasible=bool(feasible),violation=violation,
                            discovery_stage=stage,a_hex=key[0].hex(),gamma_hex=key[1].hex())
            stage_calls.append(dict(a=key[0],gamma=key[1],stage=stage,seconds=time.monotonic()-tick))
        return cache[key]
    fg={(a,0.) for a in GRID};ag={(a,g) for a in GRID for g in GAMMAS}
    for a,g in sorted(ag,key=lambda x:(x[1],x[0])):score(a,g,'grid')
    astar=analytic_weight(evaluator.fixed);score(astar,0.,'analytic')
    if evaluator.objective((astar,0.))[0]>best_brier(cache[k] for k in fg)['brier']+EPS:
        raise AssertionError('Analytic optimum worse than grid')
    fixed_seed=fg|{(astar,0.)}
    retained,runs,traces=continuous_minima(evaluator,best_brier(cache[k] for k in ag),astar,check)
    for a,g in retained:score(a,g,'continuous_brier')
    continuous_seed=ag|{(astar,0.)}|set(retained)
    fa=fixed_seed|{(k/80,0.) for k in range(81)}
    for a,g in sorted(fa):score(a,g,'fixed_quality_mesh')
    ordered=sorted(a for a,g in fa);intervals={(l,r):0 for l,r in zip(ordered[:-1],ordered[1:])}
    for _ in range(32):
        eligible=[(l,r) for (l,r),depth in intervals.items() if r-l>1e-6 and depth<8]
        if not eligible:break
        def priority(pair):
            l,r=pair;left,right=cache[(l,0.)],cache[(r,0.)]
            cls=0 if left['feasible']!=right['feasible'] else 1 if astar in pair else 2
            return cls,-(r-l),min(left['brier'],right['brier']),l
        l,r=min(eligible,key=priority);depth=intervals.pop((l,r));mid=(l+r)/2
        score(mid,0.,'fixed_quality_midpoint');fa.add((mid,0.))
        intervals[(l,mid)]=intervals[(mid,r)]=depth+1
    ac=ag|fa|set(retained)
    for step in (.1,.05,.025,.0125):
        rows=[cache[k] for k in ac];feasible=[r for r in rows if r['feasible']]
        first=best_brier(feasible) if feasible else min(rows,key=lambda r:(r['violation'],r['brier'],r['gamma'],r['a']))
        anchors={(r['a'],r['gamma']/2) for r in (first,best_brier(rows))}
        proposed={(float(np.clip(a+da,0,1)),2*float(np.clip(u+du,0,1)))
                  for a,u in anchors for da in (-step,0.,step) for du in (-step,0.,step) if da or du}
        for a,g in sorted(proposed-ac,key=lambda x:(x[1],x[0])):score(a,g,'adaptive_quality_pattern')
        ac.update(proposed)
    members=dict(F_grid=fg,F_analytic=fa,A_grid=ag,A_continuous=ac)
    if not (fg<=fa and fg<=ag and fa<=ac and ag<=ac and len(fa)<=114 and len(ac)<=252 and len(cache)<=252):
        raise AssertionError('Candidate containment or budget failure')
    selections={name:select_pool([cache[k] for k in sorted(keys)],thresholds) for name,keys in members.items()}
    for small,large in [('F_grid','F_analytic'),('A_grid','A_continuous'),('F_analytic','A_continuous')]:
        if selections[small]['eligible_for_replacement'] and not selections[large]['eligible_for_replacement']:
            raise AssertionError('Superset lost an admissible seed')
    return dict(selections=selections,candidates=list(cache.values()),
                memberships={name:sorted(keys) for name,keys in members.items()},
                analytic_a=astar,fixed_solver_seed=best_brier(cache[k] for k in fixed_seed),
                continuous_solver_seed=best_brier(cache[k] for k in continuous_seed),
                optimizer_runs=runs,optimizer_trace=traces,metric_timings=stage_calls,thresholds=thresholds)
