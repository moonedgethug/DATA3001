"""Synthetic-only reference audit tests; no experiment/data paths are read."""
from contextlib import ExitStack
import hashlib
import json
import math
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from data3001.modelling.continuous_models import conditional_mdn_s5_e3_formal_audit as audit
from data3001.modelling.continuous_models import conditional_mdn_s5_e3_selection as selection


def energy_row(role, position, identifier, k, energy):
    row = dict(role=role, position=position, id=identifier, origin_source_obs=position+100,
               horizon_days=7, K=k, model=f'MDN{k}', energy_km=energy, variance=0.,
               audit_energy_km=energy, audit_variance=0., excluded=False)
    row.update({f'es_rep{r}': energy for r in range(8)})
    row.update({f'es_audit_rep{r}': energy for r in range(8)})
    return row


def regions(frame, preferred):
    result = frame.copy()
    for prefix in ('', 'audit_'):
        result[prefix+'h90'] = np.where(result.model.eq(preferred), .95, .9)
        result[prefix+'area90_km2'] = np.where(result.model.eq(preferred), 95., 100.)
        result[prefix+'replica_area90_km2'] = result[prefix+'area90_km2']
        for field in ('land_mass', 'outside_D_mass'):
            result[prefix+field] = .02
        for field in ('land_variance', 'outside_variance', 'hit_disagreement'):
            result[prefix+field] = 0.
        for field in ('mass_radius', 'mass_diagnostic'):
            result[prefix+field] = .003
        result[prefix+'rank'] = 2
    return result


def inner():
    rows = []
    for role, identifiers in [('C_T0', [1, 1, 1, 2, 2, 3]), ('C_T1', [2, 2, 3, 4, 4, 4])]:
        for k in audit.KS:
            for position, identifier in enumerate(identifiers):
                rows.append(energy_row(role, position, identifier, k, {2: 98., 4: 97.}.get(k, 100.)))
    return pd.DataFrame(rows)


def production_inner(frame, region_frame):
    with ExitStack() as stack:
        stack.enter_context(patch.object(selection, 'INNER_PAIR_COUNTS', {'C_T0': 6, 'C_T1': 6}))
        stack.enter_context(patch.object(selection, 'INNER_ID_COUNTS', {'C_T0': 3, 'C_T1': 3}))
        stack.enter_context(patch.object(selection, 'INNER_UNIQUE_IDS', 4))
        return selection.apply_quality(selection.select_k(frame), region_frame)


class IndependentReductionTests(unittest.TestCase):
    def test_equal_id_window_reduction_prevents_duplicate_id_votes(self):
        frame = pd.DataFrame(dict(id=[1, 1, 1, 2], role=['a', 'a', 'b', 'b'], K=[1]*4,
                                  energy_km=[0., 2., 9., 3.]))
        result = audit.reference_id_means(frame, ['energy_km'])
        np.testing.assert_allclose(result.energy_km, [5., 3.])
        np.testing.assert_allclose(audit.reference_weights(frame), [.125, .125, .25, .5])
        self.assertAlmostEqual(float(audit.reference_weights(frame)@frame.energy_km), 4.)

    def test_selection_and_all_numerical_records_match_production(self):
        frame = inner()
        region_frame = regions(frame[frame.K.isin((1, 4))], 'MDN4')
        expected = production_inner(frame, region_frame)
        actual = audit.reference_selection(frame, region_frame)
        audit.close(actual, expected)
        self.assertEqual(actual['selected_k'], 4)
        self.assertEqual(actual['eligible'], [1, 2, 4])

    def test_failed_provisional_quality_goes_directly_to_one(self):
        frame = inner()
        region_frame = regions(frame[frame.K.isin((1, 4))], 'MDN4')
        for prefix in ('', 'audit_'):
            region_frame.loc[region_frame.K.eq(4), prefix+'h90'] = .8
        actual = audit.reference_selection(frame, region_frame)
        audit.close(actual, production_inner(frame, region_frame))
        self.assertEqual(actual['provisional_k'], 4)
        self.assertIn(2, actual['eligible'])
        self.assertEqual(actual['selected_k'], 1)

    def test_undeclared_alternative_quality_candidate_is_rejected(self):
        frame = inner()
        with self.assertRaisesRegex(ValueError, 'Only MDN1'):
            audit.reference_selection(frame, regions(frame[frame.K.isin((1, 2, 4))], 'MDN4'))

    def test_identity_selection_needs_no_region_table(self):
        frame = inner()
        for field in ['energy_km', 'audit_energy_km', *[f'es_rep{r}' for r in range(8)],
                      *[f'es_audit_rep{r}' for r in range(8)]]:
            frame[field] = 100.
        actual = audit.reference_selection(frame)
        audit.close(actual, production_inner(frame, None))
        self.assertEqual(actual['selected_k'], 1)

    def test_missing_replicate_and_nonfinite_required_value_fail(self):
        frame = inner()
        with self.assertRaisesRegex(ValueError, 'Incomplete eight'):
            audit.reference_numerics(frame.drop(columns='es_rep7'), 2, 1)
        frame.loc[0, 'es_rep3'] = np.nan
        with self.assertRaisesRegex(ValueError, 'Nonfinite'):
            audit.reference_numerics(frame, 2, 1)

    def test_shared_stream_covariance_is_retained(self):
        frame = inner()
        offsets = np.linspace(-.2, .2, 8)
        for r, offset in enumerate(offsets):
            frame[f'es_rep{r}'] = frame.energy_km+offset
            frame[f'es_audit_rep{r}'] = frame.energy_km+offset
        frame['variance'] = frame['audit_variance'] = offsets.var(ddof=1)/8
        actual = audit.reference_numerics(frame, 2, 1)
        self.assertLess(actual['three_se'], 1e-12)
        independent = audit.reference_numerics(frame, 2, 1, shared=False)
        self.assertGreater(independent['three_se'], .01)

    def test_nonfinite_and_string_booleans_cannot_be_coerced(self):
        with self.assertRaises(ValueError):
            audit.close({'passed': 'true'}, {'passed': True})
        with self.assertRaises(ValueError):
            audit.close(float('nan'), 0.)


class IndependentOuterTests(unittest.TestCase):
    def setUp(self):
        rows = []
        for model in audit.MODELS:
            for position, identifier in enumerate([1, 1, 2, 3, 4]):
                energy = 98.+identifier/10 if model == 'MDN2' else 100.+identifier/10
                row = energy_row('C_outer', position, identifier, 2, energy)
                row['model'] = model
                if model.startswith('MDN'):
                    row['K'] = int(model[3:])
                rows.append(row)
        self.frame = regions(pd.DataFrame(rows), 'MDN2')
        for field in [f'es_rep{r}' for r in range(8)]+[f'es_audit_rep{r}' for r in range(8)]:
            self.frame.loc[self.frame.model.isin(audit.CONTROLS), field] = np.nan

    def test_outer_means_intervals_and_acceptance_are_independent(self):
        with patch.object(selection, 'OUTER_PAIR_COUNT', 5), patch.object(selection, 'OUTER_ID_COUNT', 4):
            expected = selection.summarize_outer(self.frame, 2)
        actual = audit.reference_outer(self.frame, 2)
        for index, keys in ((0, ['model']), (1, ['id', 'model']), (2, ['model', 'baseline'])):
            first = actual[index].reset_index() if index == 0 else actual[index]
            second = expected[index].reset_index() if index == 0 else expected[index]
            audit.compare_frames(first, second, keys, 'outer synthetic reference')
        audit.close(actual[3], expected[3])
        self.assertTrue(actual[3]['overall_retention'])

    def test_first_control_failure_is_not_overridden_by_later_controls(self):
        mask = self.frame.model.eq('LocalGaussian')
        for field in ('energy_km', 'audit_energy_km'):
            self.frame.loc[mask, field] = 90.
        result = audit.reference_outer(self.frame, 2)
        self.assertFalse(result[3]['overall_retention'])
        self.assertTrue(result[2].loc[result[2].baseline.eq('ExactPoint'), 'eligible'].iloc[0])
        self.assertFalse(result[2].loc[result[2].baseline.eq('ExactPoint'), 'hierarchy_passed'].iloc[0])

    def test_outer_saved_intervals_cannot_be_changed(self):
        _, _, comparisons, _ = audit.reference_outer(self.frame, 2)
        changed = comparisons.copy()
        changed.loc[0, 'es_upper'] += .01
        with self.assertRaises(AssertionError):
            audit.compare_frames(changed, comparisons, ['model', 'baseline'], 'changed interval')

    def test_unselected_candidate_full_region_drift_is_not_ignored(self):
        mdn = self.frame[self.frame.model.str.startswith('MDN')].copy()
        result = audit.verify_full_numerical(mdn)
        self.assertEqual(len(result), 6)
        mdn.loc[mdn.K.eq(32), 'audit_area90_km2'] *= 1.01
        with self.assertRaisesRegex(ValueError, 'MDN32'):
            audit.verify_full_numerical(mdn)


class IndependentIIDTests(unittest.TestCase):
    def setUp(self):
        self.count = 130
        positions = np.floor(np.arange(128)*129/127).astype(int)
        rows = []
        for k in audit.KS:
            for position in range(self.count):
                row = energy_row('C_outer', position, position % 5, k, 100.)
                if position in positions:
                    row.update(iid_energy_km=100., iid_variance=.01, iid_count=65536,
                               iid_density_max_abs=1e-10)
                rows.append(row)
        self.frame = pd.DataFrame(rows)

    def test_fixed_128_per_candidate_aggregate_reference(self):
        result = audit.verify_iid(self.frame, self.count)
        self.assertEqual(set(result), set(map(str, audit.KS)))
        self.assertTrue(all(value['cases'] == 128 for value in result.values()))

    def test_no_new_per_query_three_se_requirement(self):
        # Two opposite errors in the same ID cancel in the registered aggregate.
        for position, error in ((0, 1.), (5, -1.)):
            self.frame.loc[self.frame.position.eq(position), 'iid_energy_km'] += error
        result = audit.verify_iid(self.frame, self.count)
        self.assertTrue(all(value['comparisons']['primary']['passed'] for value in result.values()))

    def test_wrong_fixed_key_or_partial_evidence_fails(self):
        fields = ['iid_energy_km', 'iid_variance', 'iid_count', 'iid_density_max_abs']
        changed = self.frame.copy()
        changed.loc[changed.position.eq(0), fields] = np.nan
        with self.assertRaisesRegex(ValueError, 'fixed-key'):
            audit.verify_iid(changed, self.count)
        changed = self.frame.copy()
        changed.loc[0, 'iid_count'] = np.nan
        with self.assertRaisesRegex(ValueError, 'Partially missing'):
            audit.verify_iid(changed, self.count)

    def test_aggregate_failure_and_density_error_fail(self):
        changed = self.frame.copy()
        changed['iid_energy_km'] += 1.
        with self.assertRaisesRegex(ValueError, 'aggregate IID'):
            audit.verify_iid(changed, self.count)
        changed = self.frame.copy()
        changed.loc[0, 'iid_density_max_abs'] = 1e-5
        with self.assertRaisesRegex(ValueError, 'density check'):
            audit.verify_iid(changed, self.count)


class EvidenceAndTrainingTests(unittest.TestCase):
    def test_public_checkpoint_forecast_matches_every_exported_parameter(self):
        import torch
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3 as model
        from data3001.modelling.continuous_models import conditional_mdn_s5_e3_training as training
        with tempfile.TemporaryDirectory() as directory:
            checkpoint = Path(directory)/'checkpoint.pt'
            network = model.MDN(2, 20261121)
            with torch.no_grad():
                for parameter in network.parameters():
                    parameter.zero_()
            scaler = model.Standardizer(np.array([-75., 35.]), np.array([5., 4.]),
                                        np.array([1., 2.]), np.array([10., 12.]))
            identity = dict(checkpoint_version=training.CHECKPOINT_VERSION,
                            contract_sha256=model.CONTRACT_SHA256, k=2, role='C_outer',
                            base_seed=20261121, purpose='full_refit')
            torch.save(dict(identity=identity, model_state=network.state_dict(), best_model_state=None,
                            standardizer=scaler.state_dict(),
                            progress=dict(epoch=3, status='complete', history=[]),
                            tracker=dict(best_epoch=0, best_nll=math.inf)), checkpoint)
            query = pd.DataFrame(dict(lon=[-75., -70.], lat=[35., 30.]))
            covariance = np.diag((np.log(2.)**2 + .001)*np.array([100., 144.]))
            parameters = dict(origins=query[['lon', 'lat']].to_numpy(),
                              pi=np.full((2, 2), .5),
                              mu=np.tile([1., 2.], (2, 2, 1)),
                              cov=np.tile(covariance, (2, 2, 1, 1)))
            audit.verify_refit_forecasts(checkpoint, query, parameters)
            for field in ('pi', 'mu', 'cov'):
                changed = {name: value.copy() for name, value in parameters.items()}
                changed[field][-1].flat[-1] += .01
                if field == 'pi':
                    changed[field][-1, 0] -= .01  # Still a normalized finite mixture.
                with self.subTest(field=field), self.assertRaises(AssertionError):
                    audit.verify_refit_forecasts(checkpoint, query, changed)

    def test_historical_forecast_bundles_are_audited_and_cannot_change(self):
        from data3001.paths import file_sha256
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            name = 'local_gmm_s5_e2_synthetic'
            base, provenance = root/'results/runs'/name, root/'provenance/runs'/name
            provenance.mkdir(parents=True)
            artifacts = []
            for kind, suffix in (('parameters', '.json.gz'), ('lineage', '.npz'), ('regions', '.json.gz')):
                path = base/'C_outer'/kind/('00000'+suffix)
                path.parent.mkdir(parents=True)
                path.write_bytes(kind.encode())
                artifacts.append(path)
            forecast = provenance/'forecast_freeze.json'
            forecast.write_text(json.dumps(dict(role='C_outer', cases=33971, outer_targets_read=False,
                output_sha256={p.relative_to(root).as_posix(): file_sha256(p) for p in artifacts})))
            config = provenance/'run.json'
            config.write_text('{"config":{"batch_size":128}}')
            files = {p.relative_to(root).as_posix(): file_sha256(p) for p in [*artifacts, forecast, config]}
            evidence = audit.Evidence(root)
            audit.verify_historical_forecasts(evidence, name, files)
            self.assertEqual(set(evidence.hashes), set(files))
            missing = dict(files)
            missing.pop(artifacts[1].relative_to(root).as_posix())
            with self.assertRaisesRegex(ValueError, 'omits'):
                audit.verify_historical_forecasts(audit.Evidence(root), name, missing)
            artifacts[-1].write_bytes(b'changed saved scoring ellipse')
            with self.assertRaisesRegex(ValueError, 'checksum'):
                audit.verify_historical_forecasts(audit.Evidence(root), name, files)

    def test_complete_source_keys_are_required(self):
        frame = inner().query('role == "C_T0"').copy()
        query = frame[frame.K.eq(1)][audit.inp.KEY].reset_index(drop=True)
        audit.verify_roster(frame, {'C_T0': query}, audit.KS)
        frame.loc[frame.K.eq(2), 'origin_source_obs'] += 1
        with self.assertRaisesRegex(ValueError, 'source-key'):
            audit.verify_roster(frame, {'C_T0': query}, audit.KS)

    def test_hash_changes_and_path_escape_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root/'evidence.json'
            path.write_text('{"complete": true}')
            evidence = audit.Evidence(root)
            evidence.file(path)
            path.write_text('{"complete": false}')
            with self.assertRaisesRegex(ValueError, 'changed during'):
                evidence.file(path)
            with self.assertRaisesRegex(ValueError, 'Unsafe'):
                evidence.mapping({'../outside': 'abc'})

    def test_optional_missing_values_must_match_exactly(self):
        frame = pd.DataFrame(dict(id=[1, 2], optional=[1., np.nan]))
        audit.compare_frames(frame.copy(), frame, ['id'], 'optional evidence')
        changed = frame.fillna(0)
        with self.assertRaisesRegex(ValueError, 'missing-value pattern'):
            audit.compare_frames(changed, frame, ['id'], 'optional evidence')

    def fixture_fit(self, full=False):
        fit = pd.DataFrame({'id': [1, 1, 2, 2, 3, 3, 4, 4]})
        x = np.arange(16, dtype=np.float64).reshape(8, 2)
        y = x*.5+3
        role_identity = dict(role='C_T0', contract_sha256='synthetic')
        optimization, stopping = audit.partition_reference(fit.id)
        if full:
            optimization, stopping = [1, 2, 3, 4], []
        mask = np.isin(fit.id, optimization)
        seed, k, purpose = 20261121, 1, 'full_refit' if full else 'early_stop'
        count, epochs = int(mask.sum()), 1 if full else 31
        identity = dict(checkpoint_version=1, contract_sha256='synthetic', external=role_identity,
            data_sha256=audit.array_digest(x, y, fit.id.to_numpy(np.int64)), k=k, role='C_T0', base_seed=seed,
            purpose=purpose, max_epochs=1 if full else 500, batch_size=4096,
            architecture='2-64tanh-64tanh-6K', covariance_floor=.001,
            optimizer=dict(name='AdamW', lr=.001, betas=[.9, .999], eps=1e-8,
                           weight_decay_weights_only=1e-4, clip_norm=5.), patience=30,
            min_improvement=1e-4, dtype='float64', device='cpu', torch_version='2.14.1', threads=1,
            optimization_ids=optimization, stop_ids=stopping,
            stream_seeds={name: int.from_bytes(hashlib.sha256(
                f'mdn_s5_e3_v1|{name}|C_T0|1|{seed}||'.encode()).digest()[:8], 'little')
                for name in ('init', 'shuffle')})
        record = dict(identity=identity, base_seed=seed, purpose=purpose,
            standardizer={name: value.tolist() for name, value in dict(x_mean=x[mask].mean(axis=0),
                x_std=x[mask].std(axis=0), y_mean=y[mask].mean(axis=0), y_std=y[mask].std(axis=0)).items()},
            status='complete' if full else 'early_stopped', epochs_completed=epochs,
            best_epoch=1, best_nll=None if full else 5.,
            history=[dict(epoch=e, training_nll=5., stop_nll=None if full else 5., pairs_seen=count,
                batch_sizes=[count], clipped_steps=0, gradient_clip_rate=0.) for e in range(1, epochs+1)])
        selected = dict(base_seed=seed, best_epoch=1) if full else None
        return record, role_identity, k, fit, x, y, selected

    def test_raw_best_and_full_refit_pair_coverage(self):
        args = self.fixture_fit()
        self.assertEqual(audit.verify_fit_record(*args), 31)
        full = self.fixture_fit(full=True)
        self.assertEqual(audit.verify_fit_record(*full), 1)
        full[0]['history'][0]['pairs_seen'] -= 1
        with self.assertRaisesRegex(ValueError, 'integer differs'):
            audit.verify_fit_record(*full)

    def test_bad_early_stop_epoch_and_leaked_scaler_are_rejected(self):
        args = self.fixture_fit()
        args[0]['best_epoch'] = 2
        with self.assertRaisesRegex(ValueError, 'integer differs'):
            audit.verify_fit_record(*args)
        args = self.fixture_fit()
        args[0]['standardizer']['x_mean'][0] += 1
        with self.assertRaisesRegex(ValueError, 'numeric value differs'):
            audit.verify_fit_record(*args)


if __name__ == '__main__':
    unittest.main()
