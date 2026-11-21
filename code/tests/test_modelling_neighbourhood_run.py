"""Source-key joins must not confuse row positions with native source keys."""
import unittest

import numpy as np
import pandas as pd

from data3001.modelling.run_neighbourhood import join_coordinates, validate_parent_receipt


class SourceJoinTests(unittest.TestCase):
    def fixture(self):
        track = pd.DataFrame({"id": [42, 42, 42], "source_obs": [8, 17, 99],
                              "time": [0., 7*86400., 30*86400.],
                              "lon_normalized": [.2, 2.2, 3.2], "lat": [.2, .2, .2],
                              "cell_1": [32580, 32582, 32583]})
        ledger = pd.DataFrame({"id": [42, 42, 42], "horizon_days": [7, 30, 7],
                               "origin_source_obs": [8, 8, 17], "endpoint_source_obs": [17, 99, -1],
                               "origin_cell_1": [32580, 32580, 32582],
                               "destination_cell_1": [32582, 32583, -1], "reason_code": [0, 0, 7]})
        return track, ledger

    def test_join_uses_source_keys_and_preserves_horizons(self):
        track, ledger = self.fixture()
        joined = join_coordinates(ledger, track)
        self.assertEqual(len(joined), 2)
        np.testing.assert_array_equal(joined.endpoint_lon, [2.2, 3.2])
        np.testing.assert_array_equal(joined.origin_lon, [.2, .2])
        self.assertEqual(joined.origin_source_obs.tolist(), [8, 8])

    def test_bad_timestamp_or_ambiguous_source_key_is_rejected(self):
        track, ledger = self.fixture()
        wrong = track.copy()
        wrong.loc[1, "time"] += 1
        with self.assertRaises(ValueError):
            join_coordinates(ledger, wrong)
        with self.assertRaises(ValueError):
            join_coordinates(ledger, pd.concat([track, track.iloc[[0]]]))
        wrong = ledger.copy()
        wrong.loc[0, "origin_cell_1"] = 123
        with self.assertRaises(ValueError):
            join_coordinates(wrong, track)

    def test_source_outside_endpoint_keeps_actual_coordinates(self):
        track, ledger = self.fixture()
        ledger.loc[0, "destination_cell_1"] = -2
        joined = join_coordinates(ledger, track)
        self.assertEqual(joined.iloc[0].destination_cell_1, -2)
        self.assertEqual(joined.iloc[0].endpoint_lon, 2.2)

    def test_incomplete_or_test_enabled_parent_receipt_is_rejected(self):
        for receipt in ({"completed": False, "final_test_access": False},
                        {"completed": True, "final_test_access": True}, {}):
            with self.assertRaises(ValueError):
                validate_parent_receipt(receipt)


if __name__ == "__main__":
    unittest.main()
