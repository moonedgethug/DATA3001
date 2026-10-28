"""Source-keyed diagnostic cohorts and lag decisions; synthetic tracks only."""
import importlib
import importlib.util
import unittest

import numpy as np
import pandas as pd

from data3001.preprocessing.prep_core import event_bounds
from data3001.preprocessing.prep_pairs import generate
from data3001.modelling.markov_scoring import SpatialScorer


def api(module):
    name = 'data3001.modelling.' + module
    if importlib.util.find_spec(name) is None:
        raise AssertionError('Missing diagnostic implementation: ' + module)
    return importlib.import_module(name)


def ledgers(origins=(0,), gap=None):
    hours = np.arange(8*24+1)
    if gap is not None:
        hours = hours[hours != gap]
    times = 1600000000 + hours*3600
    frame = pd.DataFrame({'id': 1, 'source_obs': hours, 'time': times,
                          'time_UTC': pd.to_datetime(times, unit='s', utc=True),
                          'cell_1': np.where(hours < 24, 10, 20), 'season': 'SON'})
    arrays = {'time': times, 'position_ok': np.ones(len(times), bool),
              'mapping_ok': np.ones(len(times), bool),
              'inside_D': ~((hours >= 48) & (hours < 72)),
              'in_R': hours < 24, 'regime': np.ones(len(times), np.int8),
              'loss': float(times[-1] + 86400), 'visit_cell_1': (hours >= 24).astype(int)}
    events = event_bounds(arrays)
    return {h: generate(frame, arrays, events, 1, np.array(origins), h, 'pooled')[1]
            for h in (1, 2, 3, 5, 7, 30)}


class CohortTests(unittest.TestCase):
    def test_absorbed_exit_cannot_reenter_later_controlled_phase(self):
        m = api('markov_diagnostic_inputs')
        table = m.controlled_counts(ledgers(), {0})
        for population in ('D', 'R'):
            part = table.loc[table.population.eq(population)].set_index('kind')
            self.assertEqual(part.loc['step0', 'destination_cell_1'], 20)
            self.assertEqual(part.loc['step1', 'destination_cell_1'], -2)
            self.assertEqual(part.loc['step2', 'origin_cell_1'], -2)
            self.assertEqual(part.loc['step2', 'destination_cell_1'], -2)
            self.assertTrue(part.pair_count.eq(1).all())

    def test_gap_cannot_enter_matched_cohorts(self):
        m = api('markov_diagnostic_inputs')
        data = ledgers(gap=12)
        self.assertTrue(m.controlled_counts(data, {0}).empty)
        counts, keys = m.matched_release_counts(data)
        self.assertTrue(counts.empty)
        self.assertTrue(keys.empty)

    def test_release_intersection_uses_source_keys_not_row_order(self):
        m = api('markov_diagnostic_inputs')
        data = ledgers(origins=(0, 1, 2))
        data[3].loc[data[3].origin_source_obs.eq(1), ['reason_code', 'destination_cell_1']] = [6, -1]
        data[1] = data[1].iloc[::-1].reset_index(drop=True)
        counts, keys = m.matched_release_counts(data)
        self.assertEqual(sorted(keys.origin_source_obs), [0, 2])
        self.assertEqual(counts.groupby('horizon_days').pair_count.sum().tolist(), [2]*6)
        bad = dict(data)
        bad[7] = pd.concat([data[7], data[7].iloc[:1]])
        with self.assertRaises(ValueError):
            m.matched_release_counts(bad)


class LagTests(unittest.TestCase):
    def counts(self):
        return pd.DataFrame([[sid, h, 10, 20, 2] for sid in range(1, 7) for h in (1, 2, 3, 5, 7)]
                            + [[sid, h, 20, 20, 2] for sid in range(1, 7) for h in (1, 2, 3, 5, 7)],
                            columns=['id', 'horizon_days', 'origin_cell_1', 'destination_cell_1', 'pair_count'])

    def releases(self):
        return pd.DataFrame([[sid, h, 10, 20, 1] for sid in range(1, 7) for h in (7, 30)],
                            columns=self.counts().columns)

    def test_lag_forecast_uses_exact_remainder_and_training_ids(self):
        m = api('markov_diagnostics')
        kernels = m.fit_kernels(self.counts(), {1, 2}, [10, 20])
        self.assertEqual(m.forecast_lag(kernels, 10, 7, 5), ({20: 1.}, 0.))
        self.assertEqual(kernels[2].training_ids, frozenset({1, 2}))
        with self.assertRaises(ValueError):
            m.forecast_lag({5: kernels[5]}, 10, 7, 5)

    def test_selection_is_horizon_specific_and_does_not_discard_failures(self):
        m = api('markov_diagnostics')
        rows = []
        for h in (7, 30):
            for lag in (1, 3, 5, 7):
                loss = 0.2 if lag == (3 if h == 7 else 5) else 1.
                rows.append([2, h, 10, 20, 1, lag, loss])
        table = pd.DataFrame(rows, columns=list(self.counts().columns)+['lag_days', 'brier_failure_penalized'])
        self.assertEqual(m.choose_lags(table), {7: 3, 30: 5})
        table['brier_failure_penalized'] = .4
        self.assertEqual(m.choose_lags(table), {7: 1, 30: 1})
        with self.assertRaises(ValueError):
            m.choose_lags(table.iloc[:-1])

    def test_nested_selection_never_fits_outer_or_inner_held_ids(self):
        m = api('markov_diagnostics')
        outer = {sid: (sid-1)//2 for sid in range(1, 7)}
        inner = {f: {sid: sid % 2 for sid in outer if outer[sid] != f} for f in range(3)}
        scorer = SpatialScorer([10, 20], np.array([[0., 0., 0.], [100., 0., 0.]]))
        result = m.nested_evaluate(self.counts(), self.releases(), [10, 20], outer, inner, scorer,
                                   progress=lambda *a, **k: None)
        for record in result['fit_records']:
            self.assertFalse(set(record['fitting_ids']) & set(record['evaluation_ids']))
            if record['role'] == 'inner':
                self.assertFalse(any(outer[sid] == record['outer_fold'] for sid in record['fitting_ids']))
        self.assertTrue(result['choices'].lag_days.eq(1).all())
        scores = result['scores']
        self.assertEqual(set(scores.model), {'B0', 'B1', 'B2', 'M1-1d', 'M1-3d', 'M1-5d', 'M1-7d', 'M1-selected'})
        self.assertTrue(scores.loc[scores.model.eq('M1-selected'), 'brier_failure_penalized'].eq(0).all())


class DiagnosticTests(unittest.TestCase):
    def test_fully_absorbed_phase_still_has_an_absorbing_operator(self):
        inputs = api('markov_diagnostic_inputs')
        m = api('markov_diagnostics')
        one = inputs.controlled_counts(ledgers(), {0})
        two = one.copy(); two['id'] = 2
        scores, gaps = m.controlled_evaluate(pd.concat([one, two], ignore_index=True), [10, 20], {1: 0, 2: 1})
        self.assertTrue(scores.loc[scores.model.eq('Phase-composed'), 'brier_failure_penalized'].eq(0).all())
        self.assertTrue(scores.destination_cell_1.eq(-2).all())

    def test_fitting_supported_map_without_validation_starts_is_available(self):
        core = api('markov_diagnostics'); report = api('markov_diagnostic_report')
        self.assertTrue(hasattr(report, 'illustrative_panels'))
        fixture = LagTests()
        releases = fixture.releases().loc[lambda x: x.id.isin([1, 2])].copy()
        releases.loc[releases.id.eq(1), 'origin_cell_1'] = 20
        kernels = core.fit_kernels(fixture.counts(), {2}, [10, 20])
        result = {'predictions': {0: {}}, 'operators': {0: kernels},
                  'choices': pd.DataFrame({'outer_fold': [0, 0], 'horizon_days': [7, 30], 'lag_days': [1, 1]})}
        panels = report.illustrative_panels(result, releases, {1: 0, 2: 1}, 10, 7)
        self.assertEqual(len(panels), 4)
        self.assertEqual(panels[0][1], {20: 1.})
        self.assertIn('No eligible', panels[-1][0])

    def test_phase_composition_preserves_matched_window_dynamics(self):
        m = api('markov_diagnostics')
        rows = []
        phases = [('step0', 1, 10, 10, 1), ('step0', 1, 10, 20, 1),
                  ('step1', 1, 10, 20, 1), ('step1', 1, 20, 20, 1),
                  ('step2', 1, 20, 20, 2), ('direct2', 2, 10, 20, 2), ('direct3', 3, 10, 20, 2)]
        for sid in (1, 2):
            for population in ('D', 'R'):
                for kind, h, a, b, count in phases:
                    rows.append([sid, h, a, b, count, kind, population])
        frame = pd.DataFrame(rows, columns=m.CASE_KEYS+['pair_count', 'kind', 'population'])
        scores, differences = m.controlled_evaluate(frame, [10, 20], {1: 0, 2: 1})
        self.assertTrue(scores.loc[scores.model.isin(['Direct', 'Phase-composed']), 'brier_failure_penalized'].eq(0).all())
        self.assertTrue(scores.loc[scores.model.eq('Pooled-composed'), 'brier_failure_penalized'].gt(0).all())
        self.assertTrue(differences.loc[differences.model.eq('Phase-composed'), 'total_variation_from_direct'].eq(0).all())

    def test_bias_chart_is_parseable_and_labels_conditioning(self):
        import xml.etree.ElementTree as ET
        m = api('markov_diagnostic_report')
        table = pd.DataFrame([{'horizon_days': h, 'model': model, 'centre_bias_km': h,
                               'predicted_RMS_km': h*2, 'observed_RMS_km': h*3}
                              for h in (1, 2, 3, 5, 7, 30) for model in ('B2', 'M1-1d')])
        svg = m.bias_svg(table)
        ET.fromstring(svg)
        self.assertIn('Descriptive', svg)
        self.assertIn('categorical', svg)

    def test_missing_bias_values_do_not_become_nan_svg_coordinates(self):
        m = api('markov_diagnostic_report')
        table = pd.DataFrame([{'horizon_days': h, 'model': model, 'centre_bias_km': np.nan,
                               'predicted_RMS_km': np.nan, 'observed_RMS_km': np.nan}
                              for h in (1, 2, 3, 5, 7, 30) for model in ('B2', 'M1-1d')])
        svg = m.bias_svg(table)
        self.assertNotIn('nan', svg)
        self.assertIn('Unavailable', svg)


if __name__ == '__main__':
    unittest.main()
