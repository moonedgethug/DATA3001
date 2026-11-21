"""Scientific fixtures for the first, mandatory full-roster support gate."""
import unittest
import numpy as np
import pandas as pd

from data3001.modelling.baselines.b2_grid_translation import (
    EXIT, translated_cells, translation_table, fitting_counts,
    query_support, evaluation_weights, require_complete_support)
from data3001.preprocessing.prep_core import cells


class GridTranslationTests(unittest.TestCase):
    def fixture(self):
        return pd.DataFrame(dict(id=[1, 1, 2, 2], lon=[-75.8]*4, lat=[32.2]*4,
            endpoint_lon=[-74.8, -74.8, -73.8, np.nan],
            endpoint_lat=[33.2, 33.2, 34.2, np.nan], outside=[False, False, False, True]))

    def test_original_mapping_is_frozen_including_float_edges(self):
        x = np.array([-75., np.nextafter(-75., -np.inf), 180., -180.])
        y = np.array([32., np.nextafter(32., -np.inf), 20., 55.])
        np.testing.assert_array_equal(translated_cells(x, y), cells(x, y, res=1))

    def test_half_open_translated_edges(self):
        x = np.array([-75.76, -75.75, -75.74])
        y = np.array([32.4]*3)
        got = translated_cells(x, y, (.25, .25))
        self.assertEqual(got[0]+1, got[1]); self.assertEqual(got[1], got[2])

    def test_both_start_and_endpoint_grid_change_without_moving_data(self):
        t = self.fixture(); before = t.copy(deep=True)
        c0, _ = fitting_counts(t, (0., 0.)); c1, _ = fitting_counts(t, (.5, .5))
        self.assertFalse(np.array_equal(c0.origin, c1.origin))
        self.assertNotEqual(set(c0.destination)-{EXIT}, set(c1.destination)-{EXIT})
        pd.testing.assert_frame_equal(t, before)

    def test_pair_votes_and_exit_preserved(self):
        counts, support = fitting_counts(self.fixture(), (.4, .4))
        self.assertEqual(support.pairs.iloc[0], 4)
        self.assertEqual(support.ids.iloc[0], 2)
        self.assertEqual(sorted(counts['count']), [1, 1, 2])
        self.assertEqual(counts.loc[counts.destination.eq(EXIT), 'probability'].iloc[0], .25)

    def test_zero_row_is_unresolved_not_exit_or_fallback(self):
        _, support = fitting_counts(self.fixture(), (0., 0.))
        q = pd.DataFrame(dict(lon=[-75.8, -70.2], lat=[32.2, 40.2]))
        result = query_support(q, support, (0., 0.))
        self.assertEqual(result.supported.tolist(), [True, False])
        self.assertEqual(result.unresolved_mass.tolist(), [0., 1.])

    def test_one_pair_support_is_accepted(self):
        _, support = fitting_counts(self.fixture().iloc[:1], (0., 0.))
        self.assertTrue(query_support(self.fixture().iloc[:1], support, (0., 0.)).supported.iloc[0])

    def test_mean_gate_requires_every_component(self):
        counts = np.ones((101, 3), dtype=int)
        require_complete_support(counts)
        counts[79, 2] = 0
        with self.assertRaisesRegex(ValueError, 'Unsupported'):
            require_complete_support(counts)

    def test_equal_id_evaluation_not_equal_pair(self):
        q = pd.DataFrame(dict(id=[1, 1, 1, 2], origin_source_obs=[1, 2, 3, 1], horizon_days=[7]*4))
        np.testing.assert_allclose(evaluation_weights(q), [1/6, 1/6, 1/6, 1/2])

    def test_fixed_shift_count_range_and_lossless_serialization(self):
        table = translation_table()
        self.assertEqual(table.shape[0], 100)
        for col in ['delta_lon', 'delta_lat']:
            self.assertTrue(((table[col] >= 0) & (table[col] < 1)).all())
            np.testing.assert_array_equal(table[col], table[col+'_hex'].map(float.fromhex))
        pd.testing.assert_frame_equal(table, translation_table())

    def test_invalid_coordinates_fail_instead_of_disappearing(self):
        with self.assertRaises(ValueError):
            translated_cells([np.nan], [32.])
        with self.assertRaises(ValueError):
            translated_cells([-75.], [90.])

    def test_independent_id_audit_handles_large_noaa_identifiers(self):
        from data3001.modelling.baselines.b2_grid_translation_audit import independent_id_support
        ids=np.array([300234011009950,300234011009950,300234099999999,300234099999999],dtype=np.int64)
        counts,largest=independent_id_support(np.array([44000,44000,44000,44001]),ids)
        self.assertEqual(counts[44000],2);self.assertEqual(largest[44000],2)
        self.assertEqual(counts[44001],1);self.assertEqual(largest[44001],1)


if __name__ == '__main__':
    unittest.main()
