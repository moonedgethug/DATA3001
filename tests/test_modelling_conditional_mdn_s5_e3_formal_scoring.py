"""Formal scoring safety and reproducibility using synthetic inputs only."""
import importlib
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd


def module():
    try:
        return importlib.import_module(
            'data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_scoring')
    except ModuleNotFoundError as exc:
        if exc.name.endswith('conditional_mdn_s5_e3_formal_scoring'):
            raise AssertionError('Formal MDN scorer is not implemented') from exc
        raise


def query_frame():
    return pd.DataFrame({'id': [10, 20], 'origin_source_obs': [100, 200],
                         'horizon_days': [7, 7], 'lon': [-75., -74.], 'lat': [35., 36.]})


def write_parameters(path, **changes):
    query = query_frame()
    values = dict(query_keys=query[['id', 'origin_source_obs', 'horizon_days']].to_numpy(np.int64),
                  origins=query[['lon', 'lat']].to_numpy(), pi=np.ones((2, 1)),
                  mu=np.zeros((2, 1, 2)), cov=np.tile(np.eye(2), (2, 1, 1, 1)),
                  target_scale=np.ones(2))
    values.update(changes)
    np.savez(path, **values)


class FormalScoringTests(unittest.TestCase):
    def test_full_energy_and_outer_modes_reject_candidate_or_role_thinning(self):
        m = module()
        for mode, role in [('inner_energy', 'C_T0'), ('outer_score', 'C_outer'),
                           ('outer_audit', 'C_outer')]:
            with self.assertRaises(ValueError):
                m.validate_request(role, mode, (1, 2), 65536, 65536)
        with self.assertRaises(ValueError):
            m.validate_request('C_outer', 'inner_energy', (1, 2, 4, 8, 16, 32), 65536, 65536)
        with self.assertRaises(ValueError):
            m.validate_request('C_T0', 'inner_regions', (2, 4), 65536, 65536)
        with self.assertRaises(ValueError):
            m.validate_request('C_T0', 'inner_regions', (1, 4), 32768, 65536)
        self.assertEqual(m.validate_request('C_T1', 'inner_regions', (4, 1), 65536, 65536), (1, 4))

    def test_parameter_roster_origin_and_covariance_floor_are_enforced(self):
        m = module()
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'parameters.npz'
            write_parameters(path)
            values = m.load_parameters(path, query_frame(), 1)
            np.testing.assert_array_equal(values['pi'], np.ones((2, 1)))
            for changes in [
                {'query_keys': np.array([[20, 200, 7], [10, 100, 7]])},
                {'origins': np.array([[-75., 35.], [-74., 36.1]])},
                {'cov': np.tile(np.eye(2) * 1e-6, (2, 1, 1, 1))},
                {'pi': np.array([[1.], [np.nan]])},
            ]:
                write_parameters(path, **changes)
                with self.assertRaises(ValueError):
                    m.load_parameters(path, query_frame(), 1)

    def test_stream_freeze_changes_with_keys_role_level_and_main_audit_scope(self):
        m = module()
        query = query_frame()
        main = m.stream_manifest(query, 'C_outer', 'outer_score', 65536, 65536)
        audit = m.stream_manifest(query, 'C_outer', 'outer_audit', 65536, 65536)
        self.assertNotEqual(main['node_key_sha256'], audit['node_key_sha256'])
        self.assertNotEqual(main['node_key_sha256'],
                            m.stream_manifest(query, 'C_T0', 'outer_score', 65536, 65536)['node_key_sha256'])
        self.assertNotEqual(main['node_key_sha256'],
                            m.stream_manifest(query, 'C_outer', 'outer_score', 131072, 65536)['node_key_sha256'])
        changed = query.copy(); changed.loc[0, 'origin_source_obs'] = 101
        self.assertNotEqual(main['node_key_sha256'],
                            m.stream_manifest(changed, 'C_outer', 'outer_score', 65536, 65536)['node_key_sha256'])
        self.assertEqual(main['seed_scheme'], 'mdn_s5_e3_v1')
        self.assertEqual(audit['iid_count'], 65536)
        np.testing.assert_array_equal(m.fixed_iid_positions(33971),
                                      np.floor(np.arange(128) * 33970 / 127).astype(int))

    def test_first_target_release_already_freezes_later_audit_and_region_streams(self):
        m = module()
        manifest = m.stream_manifest(query_frame(), 'C_outer', 'outer_score', 65536, 65536)
        streams = {(s['purpose'], s['replicate'], s['dimensions']) for s in manifest['all_streams']}
        self.assertTrue({('ES', 0, 6), ('audit', 7, 6), ('region', 0, 3),
                         ('audit', 100, 3), ('audit', 101, 3), ('IID', 10, 2),
                         ('IID', 11, 2)} <= streams)

    def test_region_report_uses_independent_mass_and_keeps_unbiased_mean_diagnostic(self):
        m = module()
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_optimized as optimized
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_numerics as numerics
        packet = dict(origin=[-75., 35.], weights=[1.], means=[[0., 0.]],
                      cholesky=[[[10., 0.], [2., 6.]]])
        target = [-74.9, 35.1]
        regions = optimized.build_region(packet, 65536, (10, 100, 7), 'C_T0')
        row = {'energy_km': 12.}
        m._region_fields(row, regions, target, False)
        self.assertEqual(row['model_mass90'], regions['mass_check']['probability'])
        truth = numerics.xyz(np.asarray(target)[None])[0]
        first, second = np.asarray(regions['means'])
        expected = 12./100 + float((first-truth) @ (second-truth))/10000
        self.assertEqual(row['auxiliary_loss'], expected)

    def test_completed_shard_needs_matching_identity_bytes_and_exact_rows(self):
        m = module()
        keys = query_frame()[['id', 'origin_source_obs', 'horizon_days']].to_numpy(np.int64)
        rows = [dict(position=i, id=int(key[0]), origin_source_obs=int(key[1]),
                     horizon_days=7, K=k, energy_km=10. + k)
                for i, key in enumerate(keys) for k in (1, 2)]
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            m.write_shard(folder, 0, rows, 'freeze-a', 0, 2)
            actual = m.read_valid_shard(folder, 0, 'freeze-a', keys, (1, 2), 0, 2)
            self.assertEqual(len(actual), 4)
            with self.assertRaises(ValueError):
                m.read_valid_shard(folder, 0, 'freeze-b', keys, (1, 2), 0, 2)
            receipt = folder / 'batch_000000.json'
            info = json.loads(receipt.read_text()); info['row_count'] = 3
            receipt.write_text(json.dumps(info))
            with self.assertRaises(ValueError):
                m.read_valid_shard(folder, 0, 'freeze-a', keys, (1, 2), 0, 2)

    def test_uncommitted_shard_is_recomputed_and_duplicate_rows_are_rejected(self):
        m = module()
        keys = query_frame()[['id', 'origin_source_obs', 'horizon_days']].to_numpy(np.int64)
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / 'batch_000000.parquet').write_bytes(b'incomplete')
            self.assertIsNone(m.read_valid_shard(folder, 0, 'freeze-a', keys, (1,), 0, 2))
            rows = [dict(position=0, id=10, origin_source_obs=100, horizon_days=7, K=1)] * 2
            m.write_shard(folder, 0, rows, 'freeze-a', 0, 2)
            with self.assertRaises(ValueError):
                m.read_valid_shard(folder, 0, 'freeze-a', keys, (1,), 0, 2)

    def test_query_energy_keeps_optimized_streams_and_independent_audit_replicates(self):
        m = module()
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_optimized as optimized
        packet = dict(origin=[-75., 35.], weights=[1.], means=[[0., 0.]],
                      cholesky=[[[10., 0.], [2., 6.]]])
        task = dict(role='C_T0', mode='inner_energy', position=0, key=(10, 100, 7),
                    target=[-74.9, 35.1], packets={1: packet}, count=65536, region_count=65536,
                    iid=False)
        rows = m.score_query(task, geography=None)
        self.assertEqual(len(rows), 1)
        expected = optimized.score_es(packet, task['target'], 65536, task['key'], 'C_T0')
        np.testing.assert_array_equal([rows[0][f'es_rep{j}'] for j in range(8)], expected['replicates'])
        self.assertEqual(rows[0]['energy_km'], expected['energy_km'])
        self.assertNotEqual([rows[0][f'es_rep{j}'] for j in range(8)],
                            [rows[0][f'es_audit_rep{j}'] for j in range(8)])
        self.assertEqual(rows[0]['excluded'], False)
        self.assertLessEqual(rows[0]['peak_node_cache_bytes'], 128 * 1024**2)

    def test_independent_ecef_and_density_have_analytic_reference_values(self):
        m = module()
        np.testing.assert_allclose(m.independent_xyz([[0., 0.], [90., 0.]]),
                                   [[6378.137, 0., 0.], [0., 6378.137, 0.]], atol=1e-9)
        actual = m.independent_log_density(np.array([[0., 0.], [1., 0.]]),
                                            np.array([1.]), np.array([[0., 0.]]),
                                            np.array([np.eye(2)]))
        np.testing.assert_allclose(actual, [-np.log(2*np.pi), -np.log(2*np.pi)-.5], atol=1e-14)

    def test_independent_iid_path_matches_identity_root_fixture_and_fixed_count(self):
        m = module()
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_numerics as numerics
        packet = dict(origin=[-75., 35.], weights=[1.], means=[[0., 0.]],
                      cholesky=[[[1., 0.], [0., 1.]]])
        target, key = [-74.99, 35.01], (10, 100, 7)
        actual = m.independent_iid_check(packet, target, key, 'C_outer')
        expected = numerics.iid_energy(packet, target, key, 'C_outer')
        self.assertAlmostEqual(actual['iid_energy_km'], expected['energy_km'], places=9)
        self.assertAlmostEqual(actual['iid_variance'], expected['variance'], places=12)
        self.assertLess(actual['iid_density_max_abs'], 1e-12)
        with self.assertRaises(ValueError):
            m.independent_iid_check(packet, target, key, 'C_outer', count=131072)

    def test_cancellation_happens_before_sampling_or_partial_rows(self):
        m = module()
        stop = threading.Event(); stop.set()
        with self.assertRaises(InterruptedError):
            m.score_query({}, geography=None, stop=stop)

    def test_worker_requires_single_thread_environment_without_optional_packages(self):
        m = module()
        environment = dict(OPENBLAS_NUM_THREADS='1', OMP_NUM_THREADS='1', MKL_NUM_THREADS='1',
                           VECLIB_MAXIMUM_THREADS='1', NUMEXPR_NUM_THREADS='1')
        with patch.dict(os.environ, environment):
            m.validate_worker_environment()
            os.environ['OMP_NUM_THREADS'] = '2'
            with self.assertRaises(RuntimeError):
                m.validate_worker_environment()


if __name__ == '__main__':
    unittest.main()
