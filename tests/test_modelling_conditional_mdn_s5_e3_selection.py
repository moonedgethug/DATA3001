"""Synthetic-only checks of the frozen MDN selection and acceptance rules."""
import numpy as np
import pandas as pd
import unittest
from unittest.mock import patch

from data3001.modelling.continuous_models import conditional_mdn_s5_e3_selection as selection


def _energy_row(role, position, id_, k, energy):
    row = dict(role=role, position=position, id=id_, K=k, energy_km=energy)
    row.update({f'es_rep{r}': energy for r in range(8)})
    row.update({f'es_audit_rep{r}': energy for r in range(8)})
    return row


def inner_frame():
    rows = []
    for role, ids in [('C_T0', [1, 1, 1, 2, 2, 3]), ('C_T1', [2, 2, 3, 4, 4, 4])]:
        for k in [1, 2, 4, 8, 16, 32]:
            for position, id_ in enumerate(ids):
                rows.append(_energy_row(role, position, id_, k, {2: 98., 4: 97.}.get(k, 100.)))
    return pd.DataFrame(rows)


def set_energy(frame, mask, values, audit_values=None):
    frame.loc[mask, 'energy_km'] = values
    for replicate in range(8):
        frame.loc[mask, f'es_rep{replicate}'] = values
        frame.loc[mask, f'es_audit_rep{replicate}'] = values if audit_values is None else audit_values


def region_frame(chosen=4):
    frame = inner_frame().query('K == 1 or K == @chosen').copy()
    frame['h90'] = .9
    frame['area90_km2'] = np.where(frame.K.eq(1), 100., 98.)
    frame['replica_area90_km2'] = frame.area90_km2
    frame['land_mass'] = .01
    frame['outside_D_mass'] = .01
    frame['land_variance'] = 0.
    frame['outside_variance'] = 0.
    frame['hit_disagreement'] = 0.
    frame['mass_radius'] = .002
    frame['mass_diagnostic'] = .003
    frame['rank'] = 2
    # Independent deterministic synthetic reconstructions agree exactly.
    for field in selection.REGION_FIELDS:
        frame['audit_' + field] = frame[field]
    return frame


def outer_frame():
    frames = []
    for model in ['MDN1', 'MDN2', 'MDN4', 'MDN8', 'MDN16', 'MDN32',
                  'LocalGaussian', 'ExactPoint', 'EndpointCI']:
        frame = region_frame().query('role == "C_T0" and K == 1').copy()
        frame['id'] = [1, 1, 2, 3, 4, 4]
        frame['role'] = 'outer'
        frame['model'] = model
        energy = 97. if model == 'MDN4' else 100.
        set_energy(frame, np.ones(len(frame), dtype=bool), energy)
        frame['area90_km2'] = 98. if model == 'MDN4' else 100.
        frame['replica_area90_km2'] = frame.area90_km2
        for field in selection.REGION_FIELDS:
            frame['audit_' + field] = frame[field]
        frame['es_variance'] = 0.
        frame['audit_energy_km'] = energy
        frame['audit_variance'] = 0.
        frames.append(frame)
    return pd.concat(frames, ignore_index=True)


class SelectionTests(unittest.TestCase):
    def setUp(self):
        # Only synthetic roster sizes shrink; statistical rules stay unchanged.
        sizes = {'INNER_PAIR_COUNTS': {'C_T0': 6, 'C_T1': 6},
                 'INNER_ID_COUNTS': {'C_T0': 3, 'C_T1': 3},
                 'INNER_UNIQUE_IDS': 4, 'OUTER_PAIR_COUNT': 6, 'OUTER_ID_COUNT': 4}
        for name, value in sizes.items():
            replacement = patch.object(selection, name, value)
            replacement.start()
            self.addCleanup(replacement.stop)

    def test_duplicate_window_ids_receive_one_vote(self):
        frame = inner_frame()
        values = {('C_T0', 1): 100., ('C_T0', 2): 30., ('C_T0', 3): 10.,
                  ('C_T1', 2): 50., ('C_T1', 3): 30., ('C_T1', 4): 40.}
        frame['energy_km'] = [values[(r.role, r.id)] for r in frame.itertuples()]
        means = selection.pooled_id_means(frame, 'energy_km')
        assert means[1].tolist() == [100., 40., 20., 40.]
        baseline = frame[frame.K.eq(1)]
        assert np.allclose(selection.query_weights(baseline) @ baseline.energy_km, 50.)


    def test_paired_numerics_keeps_shared_replicate_covariance(self):
        frame = pd.DataFrame([_energy_row('outer', i, i, k, 100. - k)
                              for k in [1, 2] for i in [1, 2]])
        offsets = np.array([-4, -3, -2, -1, 1, 2, 3, 4]) * .01
        for r, offset in enumerate(offsets):
            frame[f'es_rep{r}'] += offset
            frame[f'es_audit_rep{r}'] += offset
        paired = selection.paired_numerics(frame, 2, 1)
        independent = selection.paired_numerics(frame, 2, 1, shared_streams=False)
        assert np.allclose(paired['three_se'], 0.)
        assert np.allclose(independent['three_se'], 0.03105295017040594)


    def test_independent_replica_drift_uses_paired_difference(self):
        frame = pd.DataFrame([_energy_row('outer', 0, 1, k, 100. - k) for k in [1, 2]])
        for r in range(8):
            frame[f'es_audit_rep{r}'] += 5.
        assert np.allclose(selection.paired_numerics(frame, 2, 1)['independent_delta_drift'], 0.)


    def test_selection_uses_all_registered_candidates_and_complete_roles(self):
        frame = inner_frame()
        result = selection.select_k(frame)
        assert result['provisional_k'] == 4
        assert result['eligible'] == [1, 2, 4]
        assert result['unique_validation_ids'] == 4
        with self.assertRaisesRegex(ValueError, 'candidate|roster|registered'):
            selection.select_k(frame[frame.K.ne(32)])
        with self.assertRaisesRegex(ValueError, 'roster|count|duplicate'):
            selection.select_k(pd.concat([frame, frame.iloc[[0]]]))


    def test_a_candidate_cannot_hide_a_worse_window_in_pooled_gain(self):
        frame = inner_frame()
        set_energy(frame, frame.K.eq(4) & frame.role.eq('C_T0'), 100.1)
        result = selection.select_k(frame)
        assert result['provisional_k'] == 2
        assert 4 not in result['eligible']


    def test_one_standard_error_chooses_smallest_eligible_k(self):
        frame = inner_frame()
        set_energy(frame, frame.K.eq(2), 98.1)
        mask = frame.K.eq(4)
        set_energy(frame, mask, frame.loc[mask, 'id'].map({1: 96., 2: 100., 3: 96., 4: 100.}))
        result = selection.select_k(frame)
        assert result['best_es_k'] == 4
        assert result['provisional_k'] == 2
        assert result['one_se_rule']['2']['paired_bootstrap_se'] > .1
        assert result == selection.select_k(frame.sample(frac=1., random_state=4))


    def test_exact_score_ties_choose_smaller_k(self):
        frame = inner_frame()
        set_energy(frame, frame.K.eq(2), 97.)
        assert selection.select_k(frame)['provisional_k'] == 2


    def test_exact_relative_gain_threshold_is_inclusive(self):
        frame = inner_frame()
        set_energy(frame, frame.K.eq(2), 99.9)
        set_energy(frame, frame.K.eq(4), 100.)
        assert selection.select_k(frame)['provisional_k'] == 2


    def test_replica_disagreement_blocks_scientific_promotion(self):
        frame = inner_frame()
        set_energy(frame, frame.K.eq(4), 97., audit_values=97.5)
        assert selection.select_k(frame)['provisional_k'] == 2


    def test_failed_basic_precision_is_engineering_error(self):
        frame = inner_frame()
        frame.loc[frame.K.eq(32), 'es_rep0'] += 100.
        # Keep reported ES consistent with its actual replicate mean.
        frame.loc[frame.K.eq(32), 'energy_km'] += 12.5
        with self.assertRaisesRegex(ArithmeticError, 'precision'):
            selection.select_k(frame)


    def test_primary_score_must_match_its_replicates(self):
        frame = inner_frame()
        frame.loc[frame.K.eq(2), 'energy_km'] = 1.
        with self.assertRaisesRegex(ValueError, 'replicate|energy'):
            selection.select_k(frame)


    def test_quality_failure_falls_directly_to_one(self):
        choice = selection.select_k(inner_frame())
        frame = region_frame()
        frame.loc[frame.K.eq(4) & frame.role.eq('C_T0'), 'h90'] = .89
        frame.loc[frame.K.eq(4) & frame.role.eq('C_T0'), 'audit_h90'] = .89
        result = selection.apply_quality(choice, frame)
        assert result['selected_k'] == 1
        assert result['status'] == 'complete'
        assert result['provisional_k'] == 4


    def test_quality_gate_preserves_both_window_requirements(self):
        result = selection.apply_quality(selection.select_k(inner_frame()), region_frame())
        assert result['selected_k'] == 4
        assert all(g['passed'] for g in result['quality_gate'].values())
        frame = region_frame()
        frame.loc[frame.K.eq(4) & frame.role.eq('C_T1'), 'land_mass'] = .021
        assert selection.apply_quality(selection.select_k(inner_frame()), frame)['selected_k'] == 1


    def test_unresolvable_small_quality_improvement_does_not_promote(self):
        frame = region_frame()
        frame.loc[frame.K.eq(4), 'h90'] = .901
        frame.loc[frame.K.eq(4), 'hit_disagreement'] = .0005
        result = selection.apply_quality(selection.select_k(inner_frame()), frame)
        assert result['selected_k'] == 1


    def test_basic_region_failure_is_not_negative_model_evidence(self):
        frame = region_frame()
        frame.loc[frame.K.eq(4), 'mass_radius'] = .006
        with self.assertRaisesRegex(ArithmeticError, 'precision'):
            selection.apply_quality(selection.select_k(inner_frame()), frame)


    def test_inner_mdn_regions_require_complete_finite_audits(self):
        choice = selection.select_k(inner_frame())
        for invalid in ('absent', 'partial', 'nan', 'infinite'):
            with self.subTest(invalid=invalid):
                frame = region_frame()
                if invalid == 'absent':
                    frame = frame.drop(columns=['audit_' + field for field in selection.REGION_FIELDS])
                elif invalid == 'partial':
                    frame = frame.drop(columns=['audit_rank'])
                else:
                    frame.loc[frame.K.eq(4), 'audit_mass_radius'] = np.nan if invalid == 'nan' else np.inf
                with self.assertRaisesRegex(ValueError, 'Missing|Nonfinite'):
                    selection.apply_quality(choice, frame)


    def test_chosen_single_gaussian_needs_no_extra_inner_region_scores(self):
        result = selection.apply_quality({'provisional_k': 1}, pd.DataFrame())
        assert result['selected_k'] == 1
        assert result['status'] == 'complete'


    def test_outer_report_has_nine_unique_models_and_fixed_id_bootstrap(self):
        summary, per_id, comparisons, acceptance = selection.summarize_outer(outer_frame(), 4)
        assert len(summary) == 9
        assert len(per_id) == 36
        assert comparisons.baseline.tolist() == ['LocalGaussian', 'ExactPoint', 'EndpointCI', 'MDN1']
        assert np.allclose(comparisons.es_delta.tolist(), [-3.] * 4)
        assert np.allclose(comparisons.es_upper.tolist(), [-3.] * 4)
        assert np.allclose(comparisons.area_ratio.tolist(), [.98] * 4)
        assert acceptance['overall_retention'] is True
        assert acceptance['supports_added_components'] is True


    def test_outer_mdn_regions_require_complete_finite_audits(self):
        for invalid in ('absent', 'partial', 'nan', 'infinite'):
            with self.subTest(invalid=invalid):
                frame = outer_frame()
                if invalid == 'absent':
                    frame = frame.drop(columns=['audit_' + field for field in selection.REGION_FIELDS])
                elif invalid == 'partial':
                    frame = frame.drop(columns=['audit_rank'])
                else:
                    frame.loc[frame.model.eq('MDN32'), 'audit_mass_radius'] = np.nan if invalid == 'nan' else np.inf
                with self.assertRaisesRegex(ValueError, 'Missing|Nonfinite'):
                    selection.summarize_outer(frame, 4)


    def test_historical_controls_may_have_partial_region_audits(self):
        frame = outer_frame()
        partial_fields = ['audit_' + field for field in selection.REGION_FIELDS
                          if field not in ('h90', 'area90_km2', 'hit_disagreement')]
        frame.loc[frame.model.isin(selection.CONTROLS), partial_fields] = np.nan
        _, _, _, acceptance = selection.summarize_outer(frame, 4)
        assert acceptance['status'] == 'complete'
        assert acceptance['overall_retention'] is True
        for model in selection.CONTROLS:
            assert 'audit' not in acceptance['region_precision'][model]
            assert 'cross_reconstruction' not in acceptance['region_precision'][model]


    def test_unselected_outer_candidate_cross_region_drift_is_engineering_failure(self):
        for field in ('hit', 'area'):
            with self.subTest(field=field):
                frame = outer_frame()
                mask = frame.model.eq('MDN32')
                if field == 'hit':
                    frame.loc[mask, 'audit_h90'] = .898
                else:
                    frame.loc[mask, ['audit_area90_km2', 'audit_replica_area90_km2']] = 101.
                # Both internal reconstructions pass independently. Their
                # cross-reconstruction disagreement must still trigger an M
                # precision upgrade before final calculation acceptance.
                selection._region_precision(frame[mask], is_mdn=True)
                selection._region_precision(frame[mask], is_mdn=True, prefix='audit_')
                with self.assertRaisesRegex(ArithmeticError, 'region precision.*primary/audit'):
                    selection.summarize_outer(frame, 4)


    def test_inner_cross_region_failure_precedes_scientific_fallback(self):
        frame = region_frame()
        mask = frame.K.eq(4)
        frame.loc[mask, ['audit_area90_km2', 'audit_replica_area90_km2']] = 99.
        with self.assertRaisesRegex(ArithmeticError, 'region precision.*primary/audit'):
            selection.apply_quality(selection.select_k(inner_frame()), frame)


    def test_cross_region_precision_thresholds_are_inclusive(self):
        frame = outer_frame().query('model == "MDN32"').copy()
        frame['audit_h90'] = .899
        frame[['audit_area90_km2', 'audit_replica_area90_km2']] = 100.5
        result = selection._region_audits(frame, is_mdn=True)
        assert result['cross_reconstruction']['passed'] is True


    def test_outer_hierarchy_cannot_skip_failed_first_control(self):
        frame = outer_frame()
        set_energy(frame, frame.model.eq('LocalGaussian'), 96.)
        frame.loc[frame.model.eq('LocalGaussian'), 'audit_energy_km'] = 96.
        _, _, comparisons, acceptance = selection.summarize_outer(frame, 4)
        assert not bool(comparisons.iloc[0].eligible)
        assert bool(comparisons.iloc[1].eligible)
        assert not bool(comparisons.iloc[1].hierarchy_passed)
        assert acceptance['overall_retention'] is False


    def test_outer_interval_allowance_never_excuses_worse_point_quality(self):
        frame = outer_frame()
        frame.loc[frame.model.eq('MDN4'), 'h90'] = .899
        _, _, comparisons, acceptance = selection.summarize_outer(frame, 4)
        assert comparisons.statistical_guardrails.all()
        assert not comparisons.quality_preserved.any()
        assert acceptance['overall_retention'] is False


    def test_single_gaussian_alias_is_not_an_extra_success_model(self):
        _, _, comparisons, acceptance = selection.summarize_outer(outer_frame(), 1)
        assert len(comparisons) == 3
        assert acceptance['supports_added_components'] is False


    def test_outer_mismatched_query_rosters_fail_closed(self):
        frame = outer_frame()
        frame.loc[(frame.model == 'MDN32') & (frame.position == 0), 'id'] = 999
        with self.assertRaisesRegex(ValueError, 'roster'):
            selection.summarize_outer(frame, 4)
