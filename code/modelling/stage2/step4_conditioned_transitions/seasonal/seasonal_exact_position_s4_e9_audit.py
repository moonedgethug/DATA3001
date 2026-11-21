"""Independent arithmetic and support review of the stopped E9 pilot.

No new forecasts, outer outcomes, model search or precision changes.
"""
import hashlib
import json
import sys
import numpy as np
import pandas as pd
from pyproj import Geod

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json, save_frame
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_inputs as inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9 as model


def reference_calendar(times):
    """Intersect each seven-day interval with explicit calendar quarters."""
    dates = pd.DatetimeIndex(times).as_unit('ns')
    start = dates.asi8
    finish = start + 604800 * 10**9
    duration = np.zeros((len(start), 4), dtype=np.int64)
    departure = np.full(len(start), -1, dtype=np.int8)
    boundaries = [pd.Timestamp(year=y, month=m, day=1, tz='UTC').value
                  for y in range(dates.year.min()-1, dates.year.max()+2)
                  for m in (3, 6, 9, 12)]
    for lo, hi in zip(boundaries[:-1], boundaries[1:]):
        season = {3: 1, 6: 2, 9: 3, 12: 0}[pd.Timestamp(lo, tz='UTC').month]
        duration[:, season] += np.maximum(0, np.minimum(finish, hi)-np.maximum(start, lo))
        departure[(start >= lo) & (start < hi)] = season
    assert np.all(duration.sum(axis=1) == 604800*10**9) and np.all(departure >= 0)
    majority = duration.argmax(axis=1)
    tie = (duration == duration.max(axis=1)[:, None]).sum(axis=1) > 1
    majority[tie] = departure[tie]
    return majority, departure, duration/10**9, tie


def id_mean(frame, column):
    return float(frame.groupby('id')[column].mean().mean())


def reference_selection(fit, distances, season_labels, season):
    eligible = np.isfinite(distances) & (distances <= 100000.+1e-6)
    if season is not None:
        eligible &= season_labels == season
    ix = np.flatnonzero(eligible)
    ix = ix[np.lexsort((ix, distances[ix]))]
    if len(ix) > 8000:
        ix = ix[distances[ix] <= distances[ix[7999]]+1e-6]
    return ix


def main(run_name):
    paths, run, cfg, approval, guard = inputs.context(run_name)
    budget = inputs.Budget(run, cfg, 'audit')
    completed = False
    folder = run['results']/'pilot_audit'; folder.mkdir()
    try:
        gate = json.loads((run['provenance']/'pilot_gate.json').read_text())
        assert not gate['pilot_passed'] and not gate['formal_authorized']
        frozen = json.loads((run['provenance']/'pilot_sources/hashes.json').read_text())
        for name, digest in frozen.items():
            assert file_sha256(inputs.ROOT/name) == digest, name
        train, ledger = inputs.load(cfg)
        _, outer, _ = inputs.role(cfg, 'C_outer', train, ledger)
        assert len(outer) == 33971 and outer.id.nunique() == 45
        outer_season, _, _, _ = reference_calendar(outer.origin_time_UTC)
        counts = outer.groupby('id').size().to_dict()
        outer_weights = np.array([1./(45*counts[i]) for i in outer.id])
        assert abs(outer_weights.sum()-1) < 1e-12
        roster = pd.read_parquet(run['results']/'pilot/roster.parquet')
        assert len(roster) == 128 and (roster.groupby('role').size() == 64).all()
        old_roster = pd.read_parquet(inputs.ROOT/'results/runs'/cfg['e8_run']/'pilot_attempt_4/roster.parquet')
        rows = []
        geod = Geod(ellps='WGS84')
        for role, subset in roster.groupby('role', sort=False):
            fit, query, _ = inputs.role(cfg, role, train, ledger)
            fit_season, _, _, _ = reference_calendar(fit.origin_time_UTC)
            query_season, query_departure, seconds, ties = reference_calendar(query.origin_time_UTC)
            index = model.SeasonalNeighbours(fit)
            np.testing.assert_array_equal(fit_season, index.labels.majority_season)
            for r in subset.itertuples(index=False):
                budget.check()
                q = query.iloc[r.query_position]
                assert (int(q.id), int(q.origin_source_obs)) == (r.id, r.origin_source_obs)
                assert query_season[r.query_position] == r.majority_season
                assert query_departure[r.query_position] == r.departure_season
                assert ties[r.query_position] == r.season_tie
                np.testing.assert_array_equal(seconds[r.query_position],
                    [getattr(r,s+'_seconds') for s in model.SEASONS])
                _, _, d = geod.inv(np.full(len(fit),q.lon),np.full(len(fit),q.lat),
                                    fit.lon.to_numpy(),fit.lat.to_numpy())
                d[(fit.lon.to_numpy()==q.lon)&(fit.lat.to_numpy()==q.lat)] = 0.
                annual = reference_selection(fit,d,fit_season,None)
                seasonal = reference_selection(fit,d,fit_season,r.majority_season)
                fallback = len(seasonal)==0
                assert fallback == r.seasonal_fallback
                if fallback: seasonal=annual
                current=index.query(q.lon,q.lat,r.majority_season)
                for j, (name, selected) in enumerate([('Annual',annual),('Seasonal',seasonal)]):
                    np.testing.assert_array_equal(current[j][0],selected)
                    np.testing.assert_allclose(current[j][1],d[selected],atol=1e-6,rtol=0)
                    part=fit.iloc[selected]
                    digest=hashlib.sha256(np.asarray(selected,dtype='<i8').tobytes()).hexdigest()
                    if j==0:
                        assert digest==old_roster.iloc[r.pilot_position].lineage_digest
                    rows.append(dict(pilot_position=r.pilot_position,id=r.id,role=role,pool=name,
                        donors=len(part),donor_IDs=part.id.nunique(),farthest_m=float(d[selected].max()),
                        error_fallback_pairs=int((~part.ci_2d_usable).sum()),
                        error_fallback_mass=float((~part.ci_2d_usable).mean()),
                        seasonal_fallback=fallback,lineage_digest=digest))
            print('independent support review',role,len(subset),flush=True)
        support=pd.DataFrame(rows)
        save_frame(paths,folder/'support.csv',support)
        verified_levels=[]
        for level in gate['levels']:
            ec,rc=level['energy_count'],level['region_count']
            scores=pd.read_parquet(run['results']/f'pilot/scores_{ec}_{rc}.parquet')
            precision=pd.read_parquet(run['results']/f'pilot/precision_{ec}_{rc}.parquet')
            timing=pd.read_csv(run['results']/f'pilot/timing_{ec}_{rc}.csv')
            assert len(scores)==512 and not scores.duplicated(['pilot_position','model']).any()
            for name, control in [('SeasonalExactPoint','AnnualExactPoint'),('SeasonalEndpointCI','AnnualEndpointCI')]:
                a=scores[scores.model.eq(name)].sort_values('pilot_position')
                b=scores[scores.model.eq(control)].sort_values('pilot_position')
                v=a.energy_mc_se.to_numpy()**2+b.energy_mc_se.to_numpy()**2
                v[a.seasonal_fallback.to_numpy()]=0
                projected_var=0.
                for season in range(4):
                    sample=v[a.majority_season.to_numpy()==season]
                    maximum=float(sample.max()) if len(sample) else float(v.max())
                    projected_var+=maximum*np.square(outer_weights[outer_season==season]).sum()
                three_se=3*np.sqrt(projected_var)
                threshold=id_mean(b,'energy_km')*.0001
                expected=level['energy_projection'][name]
                np.testing.assert_allclose([three_se,threshold],
                    [expected['three_se_km'],expected['threshold_km']],rtol=1e-12)
            for name,g in precision.groupby('model'):
                actual=[float(g.mass_error.max()),id_mean(g,'hit_change'),id_mean(g,'area_change')/id_mean(g,'area')]
                expected=level['region_checks'][name]
                np.testing.assert_allclose(actual,[expected[k] for k in
                    ('max_mass_error','weighted_hit_change','weighted_area_change')],rtol=1e-12,atol=1e-14)
            estimate=(float(np.percentile(timing.seconds,95))*len(outer)+60)*1.1
            np.testing.assert_allclose(estimate,level['formal_projected_seconds'],rtol=1e-12)
            verified_levels.append(ec)
        summaries=[]
        for name,g in scores.groupby('model',sort=False):
            pool='Seasonal' if name.startswith('Seasonal') else 'Annual'
            s=support[support.pool.eq(pool)]
            summaries.append(dict(model=name,scope='Fixed inner pilot only; not outer results',
                cases=len(g),IDs=g.id.nunique(),energy_km=id_mean(g,'energy_km'),
                h90=id_mean(g,'h90'),area90_km2=id_mean(g,'area90_km2'),
                seasonal_fallback_queries=int(g.seasonal_fallback.sum()) if pool=='Seasonal' else 0,
                error_fallback_mass=id_mean(s,'error_fallback_mass') if name.endswith('CI') else None,
                error_fallback_queries=int(s.error_fallback_pairs.gt(0).sum()) if name.endswith('CI') else 0))
        save_frame(paths,folder/'inner_pilot_summary.csv',pd.DataFrame(summaries))
        inputs.verify(approval)
        assert not guard.outcomes_read and not guard.denied
        receipt=dict(status='STOPPED_AT_PILOT_GATE',review_passed=True,
            formal_completed=False,formal_authorized=False,verified_levels=verified_levels,
            independent_support_cases=128,independent_calendar_method='Explicit UTC quarter intersections',
            protected_file_count=len(approval['protected_files']),pilot_sources_unchanged=True,
            majority_seasons_present=sorted(roster.majority_season.unique().tolist()),
            cross_season_queries=int(roster.cross_season.sum()),ties=int(roster.season_tie.sum()),
            seasonal_fallback_queries=int(roster.seasonal_fallback.sum()),
            outer_targets_read=False,final_test_access=False,
            limitations=['Pilot numerical variance is a conservative season-maximum extrapolation, not measured outer variance.',
                'Pilot support was independently reconstructed; original seasonal donor vectors were not retained.',
                'No formal model inference or independent formal score audit was performed.'],
            output_sha256={str(p.relative_to(inputs.ROOT)):file_sha256(p) for p in folder.iterdir()})
        save_json(paths,run['provenance']/'pilot_independent_review.json',receipt)
        completed=True
        print(json.dumps(receipt,indent=2),flush=True)
    finally:
        budget.finish(paths,'pilot_audit',completed,guard)


if __name__=='__main__':main(sys.argv[1])
