"""Bounded 128-case pilot. Full execution requires a separate passing receipt."""
import time
STARTED = time.monotonic()
import hashlib
import json
import sys
import traceback

import numpy as np
import pandas as pd

from data3001.modelling.common.runtime import save_frame, save_json
from data3001.modelling.baselines.exact_origin_s4_e7 import NeighbourIndex
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as gaussian
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_numerics as num
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inputs


def resource_projection(components, cold_seconds, cases):
    """Use both the observed case tail and sum of measured component tails."""
    components = np.asarray(components, float)
    if components.ndim != 2 or not np.isfinite(components).all() or (components<0).any():
        raise ValueError('Finite nonnegative per-case component timings required')
    case_p95 = float(np.quantile(components.sum(axis=1), .95))
    component_bound = float(np.quantile(components, .95, axis=0).sum())
    return dict(case_p95_seconds=case_p95, component_p95_sum_seconds=component_bound,
                formal_seconds=(cold_seconds+cases*max(case_p95,component_bound))*1.1)


def run_pilot(name):
    paths, run, cfg, approval, guard = inputs.context(name)
    budget = inputs.Budget(run, cfg, 'pilot', STARTED)
    current = None
    try:
        inputs.freeze_sources(paths, run, 'pilot')
        contexts, train, outer_query = inputs.load(cfg)
        geo = Geography(paths)
        for role, context in contexts.items():
            fit = context['fit']
            context['cache'] = opt.cache(fit, geo)
            context['index'] = NeighbourIndex(fit.lon.to_numpy(), fit.lat.to_numpy(),
                radius_m=cfg['radius_m'], tolerance_m=cfg['distance_tolerance_m'])
        cold_seconds = time.monotonic()-STARTED
        roster = []
        for role, context in contexts.items():
            q = context['query']
            for index in np.floor(np.arange(64)*(len(q)-1)/63).astype(int):
                row = q.iloc[index]
                roster.append(dict(role=role, query_position=int(index),
                    id=int(row.id), origin_source_obs=int(row.origin_source_obs), horizon_days=7,
                    lon=float(row.lon), lat=float(row.lat)))
        roster = pd.DataFrame(roster)
        roster.insert(0, 'pilot_position', np.arange(len(roster)))
        roster['evaluation_weight'] = num.id_weights(roster.id.to_numpy())
        save_frame(paths, run['results']/'pilot_roster.parquet', roster)
        outer_weights = num.id_weights(outer_query.id.to_numpy())
        save_json(paths, run['provenance']/'input_checks.json', dict(
            fitting_pairs=len(train), fitting_ids=int(train.id.nunique()),
            outer_queries=len(outer_query), outer_ids=int(outer_query.id.nunique()),
            repaired_usable_pairs=int(train.ci_2d_usable.sum()), pilot_queries=len(roster),
            inner_roles=list(contexts), outer_squared_weight_sum=float(outer_weights @ outer_weights),
            cold_geography_and_index_seconds=cold_seconds, outer_targets_read=False, final_test_access=False))
        energy_rows, region_rows, time_rows, support = [], [], [], []
        for row in roster.itertuples(index=False):
            current = dict(role=row.role, pilot_position=row.pilot_position, id=row.id,
                           origin_source_obs=row.origin_source_obs)
            budget.check()
            start = time.monotonic()
            context = contexts[row.role]
            indices, distances = context['index'].query(row.lon, row.lat, cfg['k'])
            pool = context['cache'].take(indices)
            fit_ids = context['fit'].id.to_numpy()[indices]
            _, counts = np.unique(fit_ids, return_counts=True)
            fit_keys = context['fit'].iloc[indices][inputs.KEY].to_numpy(dtype=np.int64)
            digest = hashlib.sha256(fit_keys.tobytes()).hexdigest()
            base_seconds = time.monotonic()-start
            io_start = time.monotonic()
            paths.publish(run['results']/'lineage'/f'{row.pilot_position:03d}.npz',
                          lambda f: np.savez_compressed(f, indices=indices, distances_m=distances))
            # Preserve donor identities before a scientific support/rank stop.
            try:
                fit_start = time.monotonic()
                packet = gaussian.fit(np.array([row.lon, row.lat]), pool.points)
                fit_seconds = time.monotonic()-fit_start
                base_seconds += fit_seconds
            except gaussian.SupportError as error:
                save_json(paths, run['results']/'support_failure.json', dict(**current,
                    donor_digest=digest, independent_ids=len(counts),
                    diagnostics=error.diagnostics, message=str(error)))
                raise
            save_json(paths, run['results']/'parameters'/f'{row.pilot_position:03d}.json',
                      dict(**current, donor_digest=digest, gaussian=packet))
            io_seconds = time.monotonic()-io_start-fit_seconds
            support.append(dict(**current, pairs=len(indices), independent_ids=len(counts),
                largest_id_share=float(counts.max()/counts.sum()), ci_unavailable_mass=float((~pool.usable).mean()),
                covariance_condition=packet['condition_number'], roundtrip_max_km=packet['roundtrip_max_km'],
                donor_digest=digest))
            key = (row.role, row.id, row.origin_source_obs, 7)
            point, packets_by_level = None, {}
            for count in cfg['region_levels']:
                budget.check()
                start = time.monotonic()
                profile = {}
                packets = num.build_regions(pool, packet, count, key, geo, point, profile)
                point = packets['ExactPoint']
                packets_by_level[count] = packets
                time_rows.append(dict(**current, task='region', level=count,
                    seconds=time.monotonic()-start, **profile))
                io_start = time.monotonic()
                save_json(paths, run['results']/'regions'/f'{row.pilot_position:03d}_{count}.json', packets)
                time_rows.append(dict(**current, task='region_io', level=count, seconds=time.monotonic()-io_start))
            # Only inner-role truth is accessed; no outer target table is opened.
            truth = context['target'].iloc[row.query_position][['endpoint_lon', 'endpoint_lat']].to_numpy(float)
            for count, packets in packets_by_level.items():
                for model, metrics in num.region_metrics(packets, truth).items():
                    region_rows.append(dict(**current, model=model, level=count, **metrics))
            calibration = None
            for count in cfg['energy_levels']:
                budget.check()
                start = time.monotonic()
                scores, calibration = num.scores(pool, packet, packets_by_level[cfg['region_levels'][0]],
                                                  truth, count, key, calibration)
                time_rows.append(dict(**current, task='energy', level=count, seconds=time.monotonic()-start))
                for model, metrics in scores.items():
                    energy_rows.append(dict(**current, model=model, level=count, **metrics))
            time_rows.append(dict(**current, task='base', level=0, seconds=base_seconds+io_seconds))
            # One bounded checkpoint per query survives a scientific/resource stop.
            io_start = time.monotonic()
            save_json(paths, run['results']/'case_receipts'/f'{row.pilot_position:03d}.json', dict(
                completed=True, support=support[-1], energy=[r for r in energy_rows if r['pilot_position']==row.pilot_position],
                regions=[r for r in region_rows if r['pilot_position']==row.pilot_position],
                timings=[r for r in time_rows if r['pilot_position']==row.pilot_position]))
            time_rows.append(dict(**current, task='checkpoint_io', level=0, seconds=time.monotonic()-io_start))
            if (row.pilot_position+1)%8 == 0:
                stats = budget.check()
                print('PILOT', row.pilot_position+1, '/128', round(stats['elapsed_seconds'], 1), 'seconds', flush=True)
        energy = pd.DataFrame(energy_rows)
        regions = pd.DataFrame(region_rows)
        timing = pd.DataFrame(time_rows)
        save_frame(paths, run['results']/'pilot_energy.parquet', energy)
        save_frame(paths, run['results']/'pilot_regions.parquet', regions)
        save_frame(paths, run['results']/'pilot_timings.csv', timing)
        save_frame(paths, run['results']/'pilot_support.csv', pd.DataFrame(support))
        gates = assess(energy, regions, timing, roster, outer_weights, cold_seconds, budget.stats())
        save_json(paths, run['results']/'pilot_gates.json', gates)
        inputs.verify(approval)
        budget.finish(paths, 'pilot', True, guard)
        print(json.dumps(gates), flush=True)
        return 0 if gates['passed'] else 2
    except Exception as error:
        save_json(paths, run['provenance']/'pilot_stopped.json', dict(
            status='STOPPED', error=repr(error), traceback=traceback.format_exc(), current_case=current,
            diagnostics=getattr(error, 'diagnostics', None),
            formal_started=False, outer_targets_read=guard.outcomes_read, final_test_access=False))
        budget.finish(paths, 'pilot', False, guard)
        print('PILOT_STOPPED', repr(error), current, flush=True)
        return 2


def assess(energy, regions, timing, roster, outer_weights, cold_seconds, resources):
    weights = roster.evaluation_weight.to_numpy()
    square_sum = float(outer_weights @ outer_weights)
    energy_checks, region_checks = {}, {}
    for count in sorted(energy.level.unique()):
        rows = energy[energy.level.eq(count)]
        pivot = rows.pivot(index='pilot_position', columns='model', values=['energy_km','variance'])
        checks = {}
        for baseline in ('ExactPoint','EndpointCI'):
            checks[baseline] = num.es_projection(pivot['variance']['LocalGaussian']+pivot['variance'][baseline],
                                                 square_sum, float(weights @ pivot['energy_km'][baseline]))
        energy_checks[str(count)] = dict(contrasts=checks, passed=all(c['passed'] for c in checks.values()))
    levels = sorted(regions.level.unique())
    for j, count in enumerate(levels):
        next_count = levels[min(j+1,len(levels)-1)] if j < len(levels)-1 else levels[-2]
        checks = {}
        for model in num.MODELS:
            rows = regions[regions.level.eq(count)&regions.model.eq(model)].sort_values('pilot_position')
            other = regions[regions.level.eq(next_count)&regions.model.eq(model)].sort_values('pilot_position')
            check = num.region_gate(rows, weights)
            difference = float(weights @ (rows.h90.to_numpy()!=other.h90.to_numpy()).astype(float))
            mean_area = float(weights @ rows.area90_km2)
            area_change = abs(float(weights @ (rows.area90_km2.to_numpy()-other.area90_km2.to_numpy())))/mean_area if mean_area else 0.
            check.update(refinement_hit_disagreement=difference, refinement_area_relative_change=area_change)
            check['passed'] = bool(check['passed'] and difference <= .001 and area_change <= .005)
            checks[model] = check
        region_checks[str(count)] = dict(models=checks, passed=all(c['passed'] for c in checks.values()))
    e = next((int(c) for c,x in energy_checks.items() if x['passed']), None)
    r = next((int(c) for c,x in region_checks.items() if x['passed']), None)
    projection = None
    if e is not None and r is not None:
        base = timing[timing.task.eq('base')].set_index('pilot_position').seconds
        erows = timing[timing.task.eq('energy')&timing.level.eq(e)].set_index('pilot_position')
        rrows = timing[timing.task.eq('region')&timing.level.eq(r)].set_index('pilot_position')
        point = timing[timing.task.eq('region')&timing.level.eq(levels[0])].set_index('pilot_position').point_region_seconds
        region_io = timing[timing.task.eq('region_io')&timing.level.eq(r)].set_index('pilot_position').seconds
        checkpoint_io = timing[timing.task.eq('checkpoint_io')].set_index('pilot_position').seconds
        if len(region_io)!=len(base) or len(checkpoint_io)!=len(base):
            raise ValueError('Complete I/O timing required for a future resource pass certificate')
        components = np.column_stack([base, erows.seconds, rrows.seconds,
            point if r!=levels[0] else np.zeros(len(base)), region_io, checkpoint_io])
        projected = resource_projection(components,cold_seconds,33971)
        p95, formal = projected['case_p95_seconds'], projected['formal_seconds']
        audit_case = base+erows.seconds+rrows.replica_region_seconds.fillna(0)+rrows.region_check_seconds.fillna(0)
        audit = (33971*float(audit_case.quantile(.95))+cold_seconds+128*p95)*1.1
        storage = resources['retained_bytes']/128*33971*2
        projection = dict(**projected, formal_with_twofold_reserve_seconds=2*formal,
            audit_seconds=audit, storage_bytes=storage, storage_is_gross_conservative_proxy=True,
            memory_bytes=resources['peak_process_tree_rss_bytes'],
            passed=bool(2*formal<=7200 and audit<=1800 and storage<=2.5*2**30
                        and resources['peak_process_tree_rss_bytes']<=4*2**30))
    return dict(status='PILOT_PASSED_PENDING_AUDIT' if e and r and projection['passed'] else 'STOPPED_PILOT_GATE',
        passed=bool(e and r and projection['passed']), energy_checks=energy_checks, region_checks=region_checks,
        selected_energy_count=e, selected_region_count=r, resource_projection=projection,
        pilot_cases=128, formal_cases=33971, formal_started=False, outer_targets_read=False,
        final_test_access=False, pilot_metrics_are_not_formal_quality_evidence=True)


if __name__ == '__main__': raise SystemExit(run_pilot(sys.argv[1]))
