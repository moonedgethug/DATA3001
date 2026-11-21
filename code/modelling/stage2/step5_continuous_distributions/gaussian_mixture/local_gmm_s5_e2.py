"""Contract-bound local constrained EM. No data access or evaluation targets."""
import hashlib
import json
import numpy as np
from scipy.special import logsumexp
from scipy.stats import qmc
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as single

DEFAULT = dict(covariance_floor=.01, restarts=5, max_iter=200,
    loglik_tolerance=1e-6, monotonic_tolerance=1e-10, stable_iterations=5,
    fixed_point_tolerance=1e-4, min_component_probability=.02,
    min_component_count=50, min_effective_ids=3, min_material_ids=3,
    material_id_share=.01, max_id_share=.5, condition_cap=1e12)


class NumericalError(ValueError):
    """Arithmetic faults must stop the run, never become statistical fallback."""


def generator(key):
    seed = hashlib.sha256(json.dumps(('s5_e2_v1', *key), separators=(',', ':')).encode()).digest()[:16]
    return np.random.Generator(np.random.PCG64(int.from_bytes(seed, 'little')))


def normals(count, dimensions, key):
    if count < 1 or count & (count-1) or dimensions not in (2, 4):
        raise ValueError('Power-of-two count and 2/4 dimensions required')
    u = qmc.Sobol(dimensions, scramble=True, rng=generator(key), optimization=None).random_base2(count.bit_length()-1)
    z = np.empty_like(u)
    for c in range(0, dimensions, 2):
        radius = np.sqrt(-2*np.log1p(-u[:, c])); angle = 2*np.pi*u[:, c+1]
        z[:, c], z[:, c+1] = radius*np.cos(angle), radius*np.sin(angle)
    if not np.isfinite(z).all(): raise NumericalError('Nonfinite normal quadrature')
    return z


def expectation(z, weights, means, covariance):
    """Stable log responsibilities, complete equal-record average likelihood."""
    logp = np.empty((len(z), len(weights)))
    for k, w in enumerate(weights):
        if w <= 0: raise NumericalError('Invalid component probability')
        b = covariance[k]; det = b[0, 0]*b[1, 1]-b[0, 1]*b[1, 0]
        if not np.isfinite(det) or det <= 0: raise NumericalError('Nonpositive covariance')
        d = z-means[k]
        quad = (b[1, 1]*d[:, 0]**2 + b[0, 0]*d[:, 1]**2 - 2*b[0, 1]*d[:, 0]*d[:, 1])/det
        logp[:, k] = np.log(w)-np.log(2*np.pi)-.5*np.log(det)-.5*quad
    sums = logsumexp(logp, axis=1)
    resp = np.exp(logp-sums[:, None])
    if not np.isfinite(sums).all() or np.max(np.abs(resp.sum(1)-1)) > 1e-10:
        raise NumericalError('Invalid responsibility calculation')
    return float(sums.mean()), resp


def maximize(z, responsibilities, floor=.01):
    counts = responsibilities.sum(0)
    if np.any(counts == 0): raise ArithmeticError('EMPTY_COMPONENT')
    weights = counts/len(z)
    means = responsibilities.T @ z / counts[:, None]
    cov = np.empty((len(counts), 2, 2))
    for k in range(len(counts)):
        d = z-means[k]
        b = (d.T * responsibilities[:, k]) @ d / counts[k]
        vals, vecs = np.linalg.eigh((b+b.T)/2)
        cov[k] = (vecs*np.maximum(vals, floor)) @ vecs.T
    return weights, means, cov


def component_support(resp, donor_ids, cov, spec=None):
    s = DEFAULT if spec is None else spec
    _, inverse = np.unique(donor_ids, return_inverse=True)
    out, reasons = [], []
    for k in range(resp.shape[1]):
        v = resp[:, k]; n = float(v.sum())
        masses = np.bincount(inverse, weights=v)
        vals = np.linalg.eigvalsh(cov[k])
        if not np.isfinite(vals).all() or vals[0] <= 0:
            raise NumericalError('Mapped covariance is nonpositive/nonfinite')
        d = dict(probability=n/len(resp), responsibility_count=n,
            effective_pairs=n*n/float(v@v), effective_ids=n*n/float(masses@masses),
            material_ids=int(np.sum(masses/n >= s['material_id_share'])),
            largest_id_share=float(masses.max()/n), condition=float(vals[-1]/vals[0]))
        failed = []
        for field, threshold, upper in [('probability',s['min_component_probability'],False),
            ('responsibility_count',s['min_component_count'],False),
            ('effective_ids',s['min_effective_ids'],False),('material_ids',s['min_material_ids'],False),
            ('largest_id_share',s['max_id_share'],True),('condition',s['condition_cap'],True)]:
            if (d[field] > threshold if upper else d[field] < threshold): failed.append(field)
        d['failed'] = failed; out.append(d)
        reasons += [f'component_{k}:{field}' for field in failed]
    return out, reasons


def initialise(z, K, rng):
    centres = [z[int(rng.integers(len(z)))].copy()]
    nearest = np.sum((z-centres[0])**2, axis=1)
    for _ in range(1, K):
        total = float(nearest.sum())
        if total <= 0: raise ArithmeticError('EMPTY_INITIALISATION')
        centres.append(z[int(rng.choice(len(z), p=nearest/total))].copy())
        nearest = np.minimum(nearest, np.sum((z-centres[-1])**2, axis=1))
    return np.full(K, 1/K), np.asarray(centres), np.repeat(np.eye(2)[None], K, axis=0)


def residual(parameters, updated):
    return float(max(np.max(np.abs(a-b))/max(1., np.max(np.abs(a))) for a,b in zip(parameters,updated)))


def fit_restart(z, donor_ids, base, K, key, restart, spec):
    rng = generator((*key, K, restart, 'em'))
    try: p = initialise(z, K, rng)
    except ArithmeticError as e: return dict(restart=restart, status=str(e), valid=False, iterations=0)
    if spec.get('native_path'):
        from .local_gmm_s5_e2_native import run
        native=run(z,p,spec['native_path']);p=native['parameters'];trace=native['trace']
        iteration=native['iterations'];fixed=native['fixed'];converged=native['code']==0
        if native['code'] in (3,4,5):raise NumericalError(f'Native EM arithmetic failure {native["code"]}: {key}, K={K}, restart={restart}')
        if native['code']==2:
            return dict(restart=restart,status='EMPTY_COMPONENT',valid=False,iterations=iteration,trace=trace,
                white_weights=p[0].tolist(),white_means=p[1].tolist(),white_covariances=p[2].tolist())
        ll,resp=expectation(z,*p)
    else:
        ll, resp = expectation(z, *p)
        trace = [ll]; stable = 0; converged = False; fixed = None
        for iteration in range(1, spec['max_iter']+1):
            try: updated = maximize(z, resp, spec['covariance_floor'])
            except ArithmeticError as e:
                return dict(restart=restart,status=str(e),valid=False,iterations=iteration,trace=trace,
                    white_weights=p[0].tolist(),white_means=p[1].tolist(),white_covariances=p[2].tolist())
            new_ll, new_resp = expectation(z, *updated)
            delta = new_ll-ll
            if delta < -spec['monotonic_tolerance']:
                raise NumericalError(f'EM likelihood decreased by {delta}; key={key}, K={K}, restart={restart}')
            stable = stable+1 if delta <= spec['loglik_tolerance'] else 0
            p, ll, resp = updated, new_ll, new_resp; trace.append(ll)
            if stable >= spec['stable_iterations']:
                fixed = residual(p, maximize(z, resp, spec['covariance_floor']))
                if fixed <= spec['fixed_point_tolerance']:
                    converged = True; break
    if fixed is None or not converged:
        fixed = residual(p, maximize(z, resp, spec['covariance_floor']))
    weights, means, cov = p
    L = np.asarray(base['cholesky']); m = np.asarray(base['mean'])
    means_km = m+means@L.T; cov_km = L[None] @ cov @ L.T[None]
    diag, reasons = component_support(resp, donor_ids, cov_km, spec)
    order = sorted(range(K), key=lambda k: (*means[k].tolist(), *cov[k].ravel().tolist(), k))
    valid = converged and not reasons
    status = 'VALID' if valid else ('NOT_CONVERGED' if not converged else 'COMPONENT_REJECTED')
    return dict(restart=restart,status=status,valid=bool(valid),iterations=iteration,trace=trace,
        likelihood=float(ll-np.log(np.diag(L)).sum()),fixed_point_residual=fixed,
        white_weights=weights[order].tolist(),white_means=means[order].tolist(),white_covariances=cov[order].tolist(),
        means=means_km[order].tolist(),covariances=cov_km[order].tolist(),
        component_diagnostics=[diag[k] for k in order],rejection_reasons=reasons,
        floor_active=int(np.sum(np.linalg.eigvalsh(cov) <= spec['covariance_floor']*(1+1e-10))))


def fit_local(vectors_km, donor_ids, K, seed_key, spec=None):
    s = dict(DEFAULT)
    if spec is not None:
        for k in s:
            if k in spec: s[k] = spec[k]
        if spec.get('native_path'):s['native_path']=spec['native_path']
    if K not in (1,2,3): raise ValueError('Only approved K=1,2,3')
    x = np.asarray(vectors_km, dtype=float); ids = np.asarray(donor_ids)
    if ids.ndim != 1 or len(ids) != len(x): raise ValueError('Donor ID/record mismatch')
    base = single.fit_vectors(x)
    result = dict(K_requested=K,K_effective=1,pairs=len(x),weights=[1.],
        means=[base['mean']],covariances=[base['covariance']],cholesky=[base['cholesky']],
        base=base,fallback=False,fallback_reason=None,restarts=[],component_diagnostics=[],
        backend='native' if s.get('native_path') else 'numpy')
    if K == 1: return result
    z = np.linalg.solve(np.asarray(base['cholesky']), (x-np.asarray(base['mean'])).T).T
    restarts = [fit_restart(z, ids, base, K, seed_key, r, s) for r in range(s['restarts'])]
    result['restarts'] = restarts
    valid = [r for r in restarts if r['valid']]
    if not valid:
        result.update(fallback=True,fallback_reason='ALL_RESTARTS_REJECTED')
        return result
    best = valid[0]
    for r in valid[1:]:
        if r['likelihood'] > best['likelihood']+1e-10: best=r
    result.update(K_effective=K,weights=best['white_weights'],means=best['means'],
        covariances=best['covariances'],cholesky=np.linalg.cholesky(np.asarray(best['covariances'])).tolist(),
        chosen_restart=best['restart'],component_diagnostics=best['component_diagnostics'])
    return result


def draw_components(packet, z):
    return [single.to_geographic(packet['origin'], np.asarray(m)+z@np.asarray(l).T)
            for m,l in zip(packet['means'], packet['cholesky'])]


def draw_iid(packet, count, key):
    rng=generator(key); labels=rng.choice(packet['K_effective'],size=count,p=packet['weights'])
    z=rng.standard_normal((count,2)); vectors=np.empty((count,2))
    for k in range(packet['K_effective']):
        mask=labels==k
        vectors[mask]=np.asarray(packet['means'][k])+z[mask]@np.asarray(packet['cholesky'][k]).T
    return single.to_geographic(packet['origin'],vectors)
