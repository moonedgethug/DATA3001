"""Source-keyed adapter/threshold fixtures; synthetic records only."""
import importlib
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import numpy as np
import pandas as pd


def api():
    return importlib.import_module('data3001.modelling.markov_velocity_inputs')


class InputTests(unittest.TestCase):
    def test_each_threshold_uses_only_its_fitting_ids(self):
        m = api()
        speeds = {1: np.array([0., 1., 3.]), 2: np.array([100., 200.]),
                  3: np.array([5., 7.]), 4: np.array([10., 12.])}
        outer = {1: 0, 2: 1, 3: 0, 4: 1}
        inner = {0: {2: 0, 4: 1}, 1: {1: 0, 3: 1}}
        records = m.threshold_records(speeds, outer, inner)
        self.assertEqual(records['inner_1_1']['threshold_m_s'], 2.)
        self.assertEqual(records['inner_1_1']['fitting_ids'], [1])
        self.assertEqual(records['inner_1_1']['positive_origins'], 2)
        self.assertEqual(records['outer_1']['threshold_m_s'], 4.)
        self.assertTrue(records['development']['threshold_m_s'] > 0)

    def fixture(self):
        f = pd.DataFrame({'id': [1, 1, 1], 'source_obs': [7, 8, 9],
                          'time': [0., 86400., 172800.], 'cell_1': [10, 20, 30],
                          've': [1., -1., 2.], 'vn': [1., -1., 2.]})
        d = pd.DataFrame({'id': [1, 1], 'origin_source_obs': [7, 8],
                          'endpoint_source_obs': [8, -1], 'horizon_days': [1, 1],
                          'origin_cell_1': [10, 20], 'destination_cell_1': [20, -2],
                          'reason_code': [0, 0], 'target': ['stopped', 'stopped']})
        return f, d

    def test_exit_has_no_fabricated_endpoint_velocity(self):
        m = api(); f, d = self.fixture()
        result = m.attach_velocity_atoms(d, f, [.5], endpoint_velocity=True)
        self.assertEqual(result.destination_atom.tolist(), [2, -2])
        self.assertEqual(result.origin_atom.tolist(), [8, 2])
        plain = m.attach_velocity_atoms(d, f, [.5], endpoint_velocity=False)
        self.assertNotIn('destination_atom', plain)
        self.assertEqual(len(plain), 2)

    def test_bad_key_time_or_cell_is_rejected(self):
        m = api()
        for col, value in [('endpoint_source_obs', 99), ('destination_cell_1', 30),
                            ('horizon_days', 2), ('origin_cell_1', 20)]:
            f, d = self.fixture(); d.loc[0, col] = value
            with self.subTest(col=col), self.assertRaises(ValueError):
                m.attach_velocity_atoms(d, f, [.5], endpoint_velocity=True)

    def test_ineligible_pairs_excluded_not_relabeled(self):
        m = api(); f, d = self.fixture(); d.loc[0, 'reason_code'] = 1
        out = m.attach_velocity_atoms(d, f, [.5], endpoint_velocity=True)
        self.assertEqual(len(out), 1)
        self.assertEqual(out.destination_cell_1.tolist(), [-2])

    def test_candidate_R_file_with_zero_eligible_pairs_survives_full_cache(self):
        m = api()
        from data3001.preprocessing.prep_core import event_bounds
        from data3001.preprocessing.prep_pairs import generate
        from data3001.modelling.markov_inputs import count_pairs
        class Paths:
            def publish(self, path, writer):
                path.parent.mkdir(parents=True, exist_ok=True)
                with path.open('wb') as stream: writer(stream)
        tracks, old_D, old_R, summaries = {}, [], [], []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory); parent = root/'parent'; (parent/'release_labels').mkdir(parents=True)
            for sid in [1, 2, 3, 4]:
                hours = np.arange(1 if sid == 1 else 721); t = 1600000000+hours*3600
                f = pd.DataFrame({'id': sid, 'source_obs': hours, 'time': t,
                                  'time_UTC': pd.to_datetime(t, unit='s', utc=True),
                                  'cell_1': 10, 'season': 2, 've': 1., 'vn': 1.})
                a = {'time': t, 'position_ok': np.ones(len(t), bool), 'mapping_ok': np.ones(len(t), bool),
                     'inside_D': np.ones(len(t), bool), 'in_R': hours == 0,
                     'visit_cell_1': np.zeros(len(t), int), 'regime': np.ones(len(t), np.int8),
                     'loss': float(t[-1]+86400)}
                ev = event_bounds(a); tracks[sid] = (f, a, ev); digest = hashlib.sha256()
                for h in [1, 2, 3, 5, 7]:
                    d = generate(f, a, ev, sid, np.arange(len(t)), h, 'pooled')[1]
                    old_D.append(count_pairs(d)); digest.update(d[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']].to_numpy(dtype='<i8').tobytes())
                labels = []
                for h in [1, 2, 3, 5, 7, 30]:
                    d = generate(f, a, ev, sid, np.array([0]), h, 'pooled')[1]
                    labels.append(d); old_R.append(count_pairs(d))
                    digest.update(d[['origin_source_obs', 'horizon_days', 'destination_cell_1', 'reason_code']].to_numpy(dtype='<i8').tobytes())
                pd.concat(labels, ignore_index=True).to_parquet(parent/'release_labels'/f'{sid}.parquet')
                summaries.append({'id': sid, 'target_reason_digest': digest.hexdigest()})
            pd.concat(old_D, ignore_index=True).to_parquet(parent/'transition_counts_by_id.parquet')
            pd.concat(old_R, ignore_index=True).to_parquet(parent/'release_counts_by_id.parquet')
            pd.DataFrame(summaries).to_csv(parent/'source_ID_summary.csv', index=False)
            data = {'records': {str(sid): {'pool': 'train', 'sha256': 'synthetic'} for sid in tracks}}
            outer = {1: 0, 2: 1, 3: 0, 4: 1}; inner = {0: {2: 0, 4: 1}, 1: {1: 0, 3: 1}}
            with patch.object(m, 'manifest', return_value=data), patch.object(m, 'PreparedSource'), \
                    patch.object(m, 'load_track', side_effect=lambda source, sid: tracks[sid]):
                result = m.collect_velocity_inputs(Paths(), {'results': root/'result'}, tracks, parent, outer, inner,
                                                   progress=lambda *a, **k: None)
            self.assertTrue(result['all_source_keys_and_parent_counts_identical'])
            summary = pd.read_csv(root/'result/source_ID_summary.csv').set_index('id')
            self.assertEqual(summary.loc[1, 'D_pair_count'], 0)
            reasons = pd.read_csv(root/'result/candidate_reasons.csv')
            self.assertEqual(reasons.loc[reasons.id.eq(1) & reasons.population.eq('R'), 'candidate_count'].sum(), 2)


if __name__ == '__main__': unittest.main()
