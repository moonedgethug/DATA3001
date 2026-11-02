"""Frozen-model diagnostics; no fitting, new predictors, or final-test access.

Full historical-validation hourly pairs assess one-step errors. A seeded,
ID-stratified subset of the common 7/30-day cohort assesses generated trajectories.
Completeness and training influence are descriptive, not new training weights.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import shapely as sh
from shapely.geometry import shape
import torch

from data3001.paths import project_paths, file_sha256
from data3001.modelling.continuous import (
    advance, mixture_draw, mixture_nll, particle_brier, to_lonlat, to_state,
)
from data3001.modelling.continuous_inputs import PARENT
from data3001.modelling.run_continuous import load_model
from data3001.modelling.run_markov_position import mapper_for
from data3001.modelling.run_neighbourhood import verified_run, _seal
from data3001.modelling.run_blend_cv import ReadOnlyInputs, save_frame, save_json

MODEL_RUN = 'continuous_cv_20261028T143556_027911Z'
CACHE = 'continuous_input_20261028T143429_995267Z'
MODELS = ['G_l2_0', 'MDN3_l2_0', 'MDN3_l2_1e4']
HOURS = (1, 6, 24, 72, 168, 720)


def run_lengths(origins):
    """Numbers of consecutive eligible one-hour transitions, not raw fixes."""
    a = np.asarray(origins)
    if not len(a):
        return np.array([], dtype=int)
    if np.any(np.diff(a) <= 0):
        raise ValueError('Origin indices must be strictly increasing within ID')
    return np.diff(np.r_[0, np.flatnonzero(np.diff(a) != 1) + 1, len(a)])


def select_queries(cohort, per_id=16, seed=2026102901):
    """Uniform without-replacement sample inside each ID; retain design weights."""
    if cohort.duplicated(['id', 'origin']).any():
        raise ValueError('Duplicate release key')
    rng = np.random.default_rng(seed)
    parts = []
    for _, g in cohort.sort_values(['id', 'origin']).groupby('id', sort=True):
        chosen = np.sort(rng.choice(len(g), min(per_id, len(g)), replace=False))
        q = g.iloc[chosen].copy()
        q['diagnostic_weight'] = len(g) / len(q)
        q['population_ID_origins'] = len(g)
        parts.append(q)
    return pd.concat(parts, ignore_index=True)


def physical_moments(output, mean, sd):
    """Joint mixture marginal means/variances, including between-component spread."""
    lp, mu, chol = output
    p = lp.exp()
    m = (p[..., None] * mu).sum(1)
    v = (p[..., None] * (chol.square().sum(-1) + mu.square())).sum(1) - m.square()
    return m * sd[4:] + mean[4:], v.clamp_min(0) * sd[4:].square()


def failure_reasons(state, mapped):
    """Codes: 0 live, 1 exit, 2 land/mapping, 3 nonfinite, 4 invalid latitude.

    The production mapper has only land rejection for finite in-domain valid
    coordinates. We separately verify that interpretation against its land mask.
    """
    a = np.asarray(state)
    m = np.asarray(mapped)
    reason = np.zeros(len(a), dtype=np.int8)
    reason[m == -2] = 1
    reason[m == -1] = 2
    xy = to_lonlat(a)
    finite = np.isfinite(a).all(1)
    reason[finite & ((xy[:, 1] < -90) | (xy[:, 1] >= 90))] = 4
    reason[~finite] = 3
    return reason


def completeness(support, keys, observations, release):
    rows = []
    for r in support.itertuples():
        ix = keys[r.pair_start:r.pair_end]
        lengths = run_lengths(ix)
        a = observations[ix]
        # No trajectory values are reclassified by these descriptive statistics.
        in_r = sh.intersects_xy(release, a['lon'], a['lat'])
        rows.append({**r._asdict(), 'R_pairs': int(in_r.sum()),
                     'continuous_segments': len(lengths),
                     'longest_segment_hours': int(lengths.max()) if len(lengths) else 0,
                     'next_hour_eligibility_fraction': len(ix) / r.D_candidate_origins if r.D_candidate_origins else np.nan,
                     **{f'fraction_in_segments_ge_{h}h': lengths[lengths >= h].sum() / len(ix) if len(ix) else np.nan for h in (24, 168, 720)}})
    return pd.DataFrame(rows)


@torch.no_grad()
def one_step(values, keys, observations, support, release, models):
    rows = []
    held = support.loc[support.historical_split.eq('validation') & support.pairs.gt(0)]
    for number, r in enumerate(held.itertuples(), 1):
        accum = {}
        for start in range(r.pair_start, r.pair_end, 32768):
            stop = min(start + 32768, r.pair_end)
            a = np.array(values[start:stop])
            origins = observations[keys[start:stop]]
            scope = sh.intersects_xy(release, origins['lon'], origins['lat'])
            speed = np.linalg.norm(a[:, 2:4], axis=1)
            bins = np.searchsorted([.25, .75], speed, side='right')
            unit = a[:, 2:4] / np.maximum(speed[:, None], 1e-12)
            for name, (model, mean, sd) in models.items():
                x = torch.from_numpy(a)
                mu0, sd0 = torch.from_numpy(mean), torch.from_numpy(sd)
                z = (x - mu0) / sd0
                output = model(z[:, :4])
                mu, var = physical_moments(output, mu0, sd0)
                mu, var = mu.numpy(), var.numpy()
                err = mu - a[:, 4:]
                metrics = {
                    'joint_NLL_sum': mixture_nll(output, z[:, 4:]).numpy() + np.log(sd[4:]).sum(),
                    'velocity_SSE': np.square(err[:, 2:]).sum(1),
                    'persistence_velocity_SSE': np.square(a[:, 6:]).sum(1),
                    'position_SSE_m2': np.square(err[:, :2]).sum(1),
                    'constant_velocity_position_SSE_m2': np.square(a[:, 4:6]).sum(1),
                    've_error_sum': err[:, 2], 'vn_error_sum': err[:, 3],
                    'predicted_parallel_dv_sum': (mu[:, 2:] * unit).sum(1),
                    'observed_parallel_dv_sum': (a[:, 6:] * unit).sum(1),
                    'predicted_velocity_variance_sum': var[:, 2:].sum(1),
                }
                for loc in (False, True):
                    for band in range(3):
                        take = (scope == loc) & (bins == band)
                        if not take.any():
                            continue
                        key = name, 'R' if loc else 'D_outside_R', band
                        dest = accum.setdefault(key, {'pairs': 0, **{k: 0. for k in metrics}})
                        dest['pairs'] += int(take.sum())
                        for k, v in metrics.items():
                            dest[k] += float(v[take].sum(dtype=np.float64))
        for (name, loc, band), sums in accum.items():
            rows.append({'id': int(r.id), 'model': name, 'scope': loc, 'speed_band': band, **sums})
        if number % 50 == 0 or number == len(held):
            print(f'One-step: {number}/{len(held)} validation IDs', flush=True)
    return pd.DataFrame(rows)


def summarize_one_step(rows):
    keys = ['model', 'scope', 'speed_band']
    sums = rows.groupby(keys)[[k for k in rows if k not in keys + ['id']]].sum()
    sums['IDs'] = rows.groupby(keys).id.nunique()
    sums['velocity_RMSE_m_s'] = np.sqrt(sums.velocity_SSE / sums.pairs)
    sums['persistence_velocity_RMSE_m_s'] = np.sqrt(sums.persistence_velocity_SSE / sums.pairs)
    sums['position_RMSE_m'] = np.sqrt(sums.position_SSE_m2 / sums.pairs)
    sums['constant_velocity_position_RMSE_m'] = np.sqrt(sums.constant_velocity_position_SSE_m2 / sums.pairs)
    for key in ('ve_error', 'vn_error', 'predicted_parallel_dv', 'observed_parallel_dv', 'joint_NLL'):
        sums[key] = sums[key + '_sum'] / sums.pairs
    sums['velocity_error_to_predicted_variance'] = sums.velocity_SSE / sums.predicted_velocity_variance_sum
    return sums.reset_index()


def sensitivity(states, models):
    """Local derivatives, not causal importance or evidence of predictive benefit."""
    rows = []
    for name, (model, mean, sd) in models.items():
        x = torch.tensor(states.astype('float32'), requires_grad=True)
        mu0, sd0 = torch.from_numpy(mean), torch.from_numpy(sd)
        m, _ = physical_moments(model((x-mu0[:4])/sd0[:4]), mu0, sd0)
        vnext = x[:, 2:] + m[:, 2:]
        jac = torch.stack([torch.autograd.grad(vnext[:, j].sum(), x, retain_graph=True)[0]
                           for j in range(2)], dim=1).detach().numpy()
        for i in range(len(x)):
            row = {'model': name, 'query': i,
                   'd_ve_next_d_ve': float(jac[i, 0, 2]),
                   'd_vn_next_d_vn': float(jac[i, 1, 3])}
            for j, label in enumerate(('chart_x_1km', 'chart_y_1km', 've_0p1m_s', 'vn_0p1m_s')):
                row[label + '_local_velocity_response_m_s'] = float(np.linalg.norm(jac[i, :, j]) * (1000 if j < 2 else .1))
            rows.append(row)
    return pd.DataFrame(rows)


@torch.no_grad()
def trace(model, mean, sd, query, observations, mapper, particles=32, seed=9123):
    """Production-equivalent draws with first-failure attribution and checkpoints."""
    torch.manual_seed(seed)
    initial = observations[query.origin.to_numpy()]
    states = to_state(initial['lon'], initial['lat'], initial['ve'], initial['vn'])
    n = len(states)
    s = torch.tensor(np.repeat(states.astype('float32'), particles, axis=0))
    mean, sd = torch.from_numpy(mean), torch.from_numpy(sd)
    reason = np.zeros(n * particles, dtype=np.int8)
    first = np.zeros(n * particles, dtype=np.int16)
    records, events, saved = [], [], {}
    for hour in range(1, max(HOURS) + 1):
        active = np.flatnonzero(reason == 0)
        if len(active):
            old = s[active]
            nxt = advance(old, mixture_draw(model((old-mean[:4])/sd[:4])) * sd[4:] + mean[4:])
            s[active] = nxt
            xy = to_lonlat(nxt.numpy())
            mapped = mapper(xy[:, 0], xy[:, 1])
            fail = failure_reasons(nxt.numpy(), mapped)
            land = fail == 2
            if land.any():
                x = (xy[land, 0] + 180) % 360 - 180
                if not sh.intersects_xy(mapper.land, x, xy[land, 1]).all():
                    raise ValueError('Finite mapping failure is not explained by frozen land mask')
            ix = active[fail != 0]
            reason[ix], first[ix] = fail[fail != 0], hour
            for p, why, point in zip(ix, fail[fail != 0], xy[fail != 0]):
                events.append({'query': int(p//particles), 'particle': int(p%particles),
                               'hour': hour, 'reason': int(why), 'lon': float(point[0]), 'lat': float(point[1])})
        if hour not in HOURS:
            continue
        a = s.numpy().astype(float).reshape(n, particles, 4)
        r = reason.reshape(n, particles)
        alive = r == 0
        count = alive.sum(1)
        # Reductions use where(), so NaN in a failed particle cannot poison survivors.
        centroid = np.where(alive[..., None], a, 0).sum(1) / np.maximum(count[:, None], 1)
        speed = np.linalg.norm(a[..., 2:], axis=2)
        avg_speed = np.where(alive, speed, 0).sum(1) / np.maximum(count, 1)
        spread = np.where(alive, np.square(a[..., :2]-centroid[:, None, :2]).sum(2), 0).sum(1)/np.maximum(count, 1)
        truth = observations[query.origin.to_numpy()+hour]
        if not (np.array_equal(truth['id'], initial['id']) and np.array_equal(truth['time']-initial['time'], np.full(n, hour*3600))):
            raise ValueError('Observed diagnostic endpoint misalignment')
        target = to_state(truth['lon'], truth['lat'], truth['ve'], truth['vn'])
        cells = np.full(n*particles, -3, dtype=np.int32)
        cells[reason == 1] = -2
        ix = np.flatnonzero(reason == 0)
        xy = to_lonlat(s[ix].numpy())
        cells[ix] = mapper(xy[:, 0], xy[:, 1])
        if (cells == -1).any():
            raise ValueError('Unresolved live particle')
        cells = cells.reshape(n, particles)
        score = particle_brier(cells, truth['cell'])
        for i, q in enumerate(query.itertuples()):
            rec = {'id': int(q.id), 'origin': int(q.origin), 'hour': hour,
                   'weight': q.diagnostic_weight, 'live_particles': int(count[i]), 'S': float(score[i]),
                   'observed_speed_m_s': float(np.linalg.norm(target[i, 2:])),
                   'observed_ve_m_s': float(target[i, 2]), 'observed_vn_m_s': float(target[i, 3]),
                   **{f'reason_{j}_fraction': float((r[i] == j).mean()) for j in range(5)}}
            for label, value in [('predicted_speed_m_s', avg_speed[i]),
                                 ('predicted_ve_m_s', centroid[i, 2]), ('predicted_vn_m_s', centroid[i, 3]),
                                 ('within_prediction_rms_chart_km', np.sqrt(spread[i])/1000),
                                 ('centroid_error_chart_km', np.linalg.norm(centroid[i, :2]-target[i, :2])/1000)]:
                rec[label] = float(value) if count[i] else np.nan
            records.append(rec)
        saved[hour] = cells
        print(f'  hour {hour}: live {(reason==0).mean():.3%}, land {(reason==2).mean():.3%}', flush=True)
    return pd.DataFrame(records), pd.DataFrame(events), saved


def main():
    parser = argparse.ArgumentParser(); parser.add_argument('--per-id', type=int, default=16)
    args = parser.parse_args()
    if args.per_id < 1:
        raise ValueError('Positive sample count required')
    begun = time.monotonic(); paths = project_paths()
    torch.set_num_threads(4); torch.use_deterministic_algorithms(True)
    receipt = verified_run(paths, MODEL_RUN)
    cfg = json.loads((receipt.parent/'run.json').read_text())['config']
    bound = {**cfg['input_sha256'], **cfg['source_sha256']}
    for rel, sha in bound.items():
        if file_sha256(paths.root/rel) != sha:
            raise ValueError('Frozen model input/code changed: '+rel)
    verified_run(paths, CACHE)
    name = datetime.now(timezone.utc).strftime('continuous_diagnostics_%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(name, {'model_run': MODEL_RUN, 'cache': CACHE, 'parent': PARENT,
        'final_test_access': False, 'fitting': False, 'features': ['lon','lat','ve','vn'],
        'per_ID_queries': args.per_id, 'particles': 32, 'seeds': [9123, 9124],
        'query_seed': 2026102901, 'hours': HOURS, 'speed_bands_m_s': [.25,.75],
        'input_sha256': bound, 'diagnostic_source_sha256': file_sha256(Path(__file__))})
    print('RUN='+name, flush=True)
    save_json(paths, run['provenance']/'method.json', {
        'one_step': 'All eligible historical-validation D hourly pairs; R is a geometric stratum.',
        'rollout': 'Uniform sample without replacement up to 16 origins per ID from common eligible 7/30d cohort; inverse inclusion weights. Two MC seeds. Descriptive diagnostic, not model selection.',
        'completeness': 'Contiguous eligible hourly transitions, not independent raw observations or a measurement-quality label.',
        'spread': 'Surviving-particle within-query RMS spread in fixed chart km; not geodesic distance or ground-truth conditional uncertainty.',
        'uncertainty': 'No claim of independent observations; repeated historical-validation diagnoses inform development.',
        'scope': 'No reweighting, covariance clipping, new lag kernel, new feature, refitting, or test access.'})
    paths.publish(run['provenance']/'diagnostic_source.py', lambda f:f.write(Path(__file__).read_bytes()))
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root); sys.addaudithook(guard)
    try:
        root = paths.root/'results/runs'/CACHE
        schema = json.loads((root/'schema.json').read_text())
        values = np.memmap(root/'pairs.float32', mode='r', dtype='<f4', shape=tuple(schema['shape']))
        keys = np.load(root/'origin_indices.npy', mmap_mode='r')
        support = pd.read_csv(root/'ID_support.csv')
        parent = paths.root/'results/runs'/PARENT
        observations = np.load(parent/'observations.npy', mmap_mode='r')
        releases = pd.read_parquet(parent/'releases.parquet')
        release = shape(json.loads(paths.asset('release_R', verify=True).read_text())['features'][0]['geometry'])
        sh.prepare(release)
        comp = completeness(support, keys, observations, release)
        save_frame(paths, run['results']/'ID_completeness.csv', comp)
        models = {name:load_model(paths.root/'results/runs'/MODEL_RUN/('refit_'+name)) for name in MODELS}
        hourly = one_step(values, keys, observations, support, release, models)
        save_frame(paths, run['results']/'one_step_by_ID.csv', hourly)
        save_frame(paths, run['results']/'one_step_summary.csv', summarize_one_step(hourly))
        held = set(support.loc[support.historical_split.eq('validation'), 'id'])
        use = releases.loc[releases.reason_code.eq(0) & releases.id.isin(held)]
        a = use.loc[use.horizon_days.eq(30)].copy()
        b = use.loc[use.horizon_days.eq(7), ['id','origin','destination_cell_1']].rename(columns={'destination_cell_1':'destination_7d'})
        cohort = a.merge(b, on=['id','origin'], validate='one_to_one')
        if (cohort[['destination_cell_1','destination_7d']] < 0).any().any():
            raise ValueError('This complete-path diagnostic needs separately handled observed exits')
        query = select_queries(cohort, args.per_id)
        # Check every observed intermediate hour, not just endpoint arithmetic.
        for q in query.itertuples():
            o = observations[q.origin:q.origin+721]
            if len(o)!=721 or not (o['id']==q.id).all() or not (np.diff(o['time'])==3600).all() or (o['cell']<0).any():
                raise ValueError('Common stopped cohort does not supply a complete in-domain path')
        save_frame(paths, run['results']/'diagnostic_queries.csv', query)
        initial = observations[query.origin.to_numpy()]
        states = to_state(initial['lon'],initial['lat'],initial['ve'],initial['vn'])
        save_frame(paths, run['results']/'local_sensitivity.csv', sensitivity(states, models))
        mapper = mapper_for(paths)
        for name in ('G_l2_0', 'MDN3_l2_0'):
            for seed in (9123, 9124):
                print(f'Trace {name}, seed {seed}, {len(query)} origins / {query.id.nunique()} IDs', flush=True)
                records, events, saved = trace(*models[name], query, observations, mapper, seed=seed)
                records['model'] = name; records['seed'] = seed
                events['model'] = name; events['seed'] = seed
                save_frame(paths, run['results']/f'trace_{name}_{seed}.csv', records)
                save_frame(paths, run['results']/f'failures_{name}_{seed}.parquet', events)
                for hour in (168,720):
                    paths.publish(run['results']/f'draws_{name}_{seed}_{hour}h.npy', lambda f,h=hour:np.save(f,saved[h]))
        logs = []
        for file in sorted((paths.root/'results/runs'/MODEL_RUN).glob('cv*.json')):
            d = json.loads(file.read_text())
            if 'logs' not in d: continue
            for entry in d['logs']:
                logs.append({'fit':file.stem, 'best_epoch':d['best_epoch'], **entry})
        save_frame(paths, run['results']/'frozen_training_history.csv', pd.DataFrame(logs))
        for rel, sha in bound.items():
            if file_sha256(paths.root/rel) != sha:
                raise ValueError('Input changed during diagnostic: '+rel)
        _seal(paths, run, {'completed':True, 'final_test_access':False, 'canonical_changed':False,
            'refitted':False, 'new_features':False, 'one_step_pairs_per_model':int(support.loc[support.historical_split.eq('validation'),'pairs'].sum()),
            'diagnostic_origins':len(query), 'diagnostic_IDs':int(query.id.nunique()),
            'common_cohort_origins':len(cohort), 'MC_seeds':[9123,9124],
            'denied_operations':guard.denied, 'elapsed_seconds':time.monotonic()-begun})
        print('DIAGNOSTIC_RUN='+run['results'].name, flush=True)
    finally:
        guard.active = False


if __name__ == '__main__':
    main()
