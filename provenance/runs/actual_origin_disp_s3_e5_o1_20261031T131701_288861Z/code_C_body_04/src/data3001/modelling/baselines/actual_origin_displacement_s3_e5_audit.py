"""Independent scalar geometry and solver arithmetic checks for E5."""
import numpy as np
from shapely.geometry import Point, LineString
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import FALLBACK
from data3001.modelling.common.qualified_count_inputs import EXIT


def literal_transfer(query, donor, tracks, geometry):
    """Chronological scalar oracle; no production certificates or event arrays."""
    q=Point(query.lon,query.lat)
    if not geometry.region.intersects(q) or not geometry.domain.intersects(q):
        raise ValueError('Invalid query start')
    if geometry.high.intersects(q) or geometry.intermediate.intersects(q):
        return FALLBACK,11
    prev=(query.lon,query.lat)
    for k in range(1,24*query.horizon+1):
        index=int(donor.start)+k
        if index>=int(donor.track_end):return FALLBACK,7
        if tracks.time[index]!=donor.epoch+k*3600:return FALLBACK,5
        x=(query.lon+(tracks.lon[index]-donor.lon)+180)%360-180
        y=query.lat+(tracks.lat[index]-donor.lat)
        if not tracks.valid[index] or not np.isfinite([x,y]).all() or not -90<=y<90:
            return FALLBACK,1
        pt=Point(x,y);inside=geometry.domain.intersects(pt)
        cell=int(np.floor(y+90))*360+int(np.floor(x+180))
        reason=4 if inside and cell not in geometry.states else 0
        h=inside and geometry.high.intersects(pt);m=inside and geometry.intermediate.intersects(pt)
        if h and m:reason=2
        elif h!=m:reason=3
        clipped=LineString([prev,(x,y)]).intersection(geometry.domain)
        h=geometry.high.intersects(clipped);m=geometry.intermediate.intersects(clipped)
        if h and m:reason=6
        elif h!=m:reason=10
        if reason:return FALLBACK,reason
        if not inside:return EXIT,0
        prev=(x,y)
    return cell,0


def audit_transfers(query, donors, tracks, geometry, outcomes, reasons, maximum=32):
    """Bounded real-data cross-check; full-run sample target is separately enforced."""
    if not len(donors):return []
    indices=set(np.linspace(0,len(donors)-1,min(maximum,len(donors)),dtype=int).tolist())
    # Include each observed reason, not just the common successful branch.
    indices.update(int(np.flatnonzero(reasons==r)[0]) for r in np.unique(reasons))
    checked=[]
    for j in sorted(indices):
        expected=literal_transfer(query,donors.iloc[j],tracks,geometry)
        actual=int(outcomes[j]),int(reasons[j])
        if expected!=actual:raise AssertionError(f'Independent transfer mismatch: {j}, {expected}, {actual}')
        checked.append(dict(donor_id=int(donors.iloc[j].id),donor_source_obs=int(donors.iloc[j].origin_source_obs),
                            destination=actual[0],reason=actual[1]))
    return checked


def audit_search(result, evaluator):
    rows={(r['a'],r['gamma']):r for r in result['candidates']}
    A,B,C=evaluator.fixed
    expected=0. if A==0 else min(1.,max(0.,-B/(2*A)))
    if abs(expected-result['analytic_a'])>1e-12:raise AssertionError('Analytic solve audit failed')
    thresholds=result['thresholds'];decisions={}
    for name,keys in result['memberships'].items():
        group=[rows[tuple(k)] for k in keys]
        feasible=[r for r in group if r['region90_hit']>=thresholds['H']-1e-12 and r['region90_cells']<=thresholds['K']+1e-12]
        accepted=[r for r in feasible if r['brier']<thresholds['B']-1e-12]
        options=accepted or group
        low=min(r['brier'] for r in options)
        winner=sorted((r for r in options if r['brier']<=low+1e-12),key=lambda r:(r['gamma'],r['a']))[0]
        chosen=result['selections'][name]
        if (winner['a'],winner['gamma'])!=(chosen['selected']['a'],chosen['selected']['gamma']):
            raise AssertionError('Independent selection audit failed')
        if bool(accepted)!=chosen['eligible_for_replacement']:raise AssertionError('Adoption gate mismatch')
        decisions[name]=dict(candidate_count=len(group),feasible_count=len(feasible),admissible=bool(accepted))
    for trace in result['optimizer_trace']:
        loss,grad=evaluator.objective((trace['a'],trace['gamma']))
        if abs(loss-trace['brier'])>1e-12 or not np.allclose(grad,[trace['gradient_a'],trace['gradient_gamma']],atol=1e-12,rtol=0):
            raise AssertionError('Optimiser trace arithmetic mismatch')
    return decisions
