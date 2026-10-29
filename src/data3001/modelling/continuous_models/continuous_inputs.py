"""Reproducible one-hour cache; source records and final test remain untouched."""
import json
import sys
import time
from datetime import datetime, timezone
import numpy as np
import pandas as pd
from data3001.dataset import PreparedSource, track_path
from data3001.modelling.continuous_models.continuous import to_state, residual, hour_pairs
from data3001.modelling.common.runtime import ReadOnlyInputs, save_frame, save_json
from data3001.modelling.markov_models.run_markov import identity, verify_bound
from data3001.modelling.common.runtime import verified_run, _seal
from data3001.paths import project_paths, file_sha256
from data3001.preprocessing.prep_pairs import load_track

PARENT = 'markov_position_input_20261027T093543_211496Z'


def prepare():
    paths = project_paths(); data, bound = identity(paths)
    receipt = verified_run(paths, PARENT)
    parent_config = json.loads((receipt.parent/'run.json').read_text())['config']
    for rel, sha in parent_config['input_sha256'].items():
        if file_sha256(paths.root/rel) != sha:
            raise ValueError('Stale parent input: ' + rel)
    bound[str(receipt.relative_to(paths.root))] = file_sha256(receipt)
    sources = {str(p.relative_to(paths.root)): file_sha256(p) for p in [
        paths.root/'src/data3001/modelling/continuous_models/continuous.py',
        paths.root/'src/data3001/modelling/continuous_models/continuous_inputs.py']}
    name = datetime.now(timezone.utc).strftime('continuous_input_%Y%m%dT%H%M%S_%fZ')
    run = paths.create_run(name, {'parent': PARENT, 'step_hours': 1, 'input_sha256': bound,
                                 'source_sha256': sources, 'final_test_access': False})
    guard = ReadOnlyInputs(paths.root, run, data_root=paths.data_root); sys.addaudithook(guard)
    parent = paths.root/'results/runs'/PARENT
    obs = np.load(parent/'observations.npy', mmap_mode='r')
    roster = pd.read_csv(parent/'source_ID_summary.csv')
    if set(roster.id) != {int(i) for i,r in data['records'].items() if r['pool']=='train'}:
        raise ValueError('Development roster mismatch')
    source = PreparedSource(allow_test=False); counts = []; origins = []; count = 0
    started = time.monotonic()
    try:
        def write(stream):
            nonlocal count
            for number, rec in enumerate(roster.itertuples(), 1):
                sid = int(rec.id); frame, a, _ = load_track(source, sid)
                old = obs[rec.start:rec.end]
                if len(frame) != len(old): raise ValueError('Source count mismatch')
                for key, native in [('time','time'),('source_obs','source_obs'),('lon','lon_normalized'),
                                    ('lat','lat'),('ve','ve'),('vn','vn')]:
                    if not np.array_equal(old[key], frame[native].to_numpy(), equal_nan=True):
                        raise ValueError(f'Cache differs from canonical {sid}: {key}')
                finite = np.isfinite(frame[['ve','vn']]).all(axis=1).to_numpy()
                if not finite.all(): raise ValueError('Unexpected missing velocity; do not silently drop')
                ix = hour_pairs(a['time'], a['position_ok'], a['mapping_ok'], a['inside_D'], finite)
                x = to_state(old['lon'], old['lat'], old['ve'], old['vn'])
                z = np.column_stack([x[ix], residual(x[ix], x[ix+1])]).astype('<f4')
                if not np.isfinite(z).all(): raise ValueError('Nonfinite one-hour target')
                stream.write(z.tobytes()); origins.append((ix+rec.start).astype('<i4'))
                counts.append({'id':sid, 'pair_start':count, 'pair_end':count+len(ix),
                    'pairs':len(ix), 'observed_exit_pairs':int((~a['inside_D'][ix+1]).sum()),
                    'D_candidate_origins':int(a['inside_D'].sum()),
                    'historical_split':data['records'][str(sid)]['historical_split'],
                    'source_sha256':data['records'][str(sid)]['sha256']})
                count += len(ix)
                if number%200==0 or number==len(roster):
                    print(f'Hourly cache {number}/{len(roster)} IDs; {count:,} pairs; {time.monotonic()-started:.1f}s', flush=True)
        paths.publish(run['results']/'pairs.float32', write)
        keys = np.concatenate(origins)
        paths.publish(run['results']/'origin_indices.npy', lambda stream: np.save(stream, keys))
        save_frame(paths, run['results']/'ID_support.csv', pd.DataFrame(counts))
        save_json(paths, run['results']/'schema.json', {'shape':[count,8], 'dtype':'<f4',
            'columns':['chart_x_m','chart_y_m','ve_m_s','vn_m_s','residual_x_m','residual_y_m','delta_ve_m_s','delta_vn_m_s'],
            'source_key':'parent observations[origin_indices[row]]; endpoint = origin + 1',
            'weighting':'all eligible hourly pairs, equal weight; no thinning',
            'parent':PARENT, 'hours':1})
        if guard.read_ids != set(roster.id): raise ValueError('Source read roster differs')
        for sid in roster.id: track_path(int(sid), allow_test=False)
        verify_bound(paths,bound,sources)
        _seal(paths,run,{'pairs':count,'IDs':len(roster),'observed_exit_pairs':sum(r['observed_exit_pairs'] for r in counts),
            'canonical_changed':False,'final_test_access':False,'denied_operations':guard.denied,
            'elapsed_seconds':time.monotonic()-started})
        print('CONTINUOUS_INPUT_RUN='+name, flush=True)
    finally: guard.active=False


if __name__ == '__main__': prepare()
