"""Synthetic label reconciliation and per-instrument count conservation."""
import importlib
import importlib.util
import unittest

import numpy as np
import pandas as pd

from data3001.preprocessing.prep_core import event_bounds
from data3001.preprocessing.prep_pairs import generate


def api():
    name = 'data3001.modelling.markov_inputs'
    if importlib.util.find_spec(name) is None:
        raise AssertionError('Required stopped count adapter is absent')
    return importlib.import_module(name)


def path(remove_hour=None):
    hours = np.arange(8*24+1)
    if remove_hour is not None:
        hours = hours[hours != remove_hour]
    t = 1600000000 + hours*3600
    inside = ~((hours >= 48) & (hours < 72))
    cells = np.where(hours < 24, 10, 20)
    frame = pd.DataFrame({'id': 1, 'source_obs': hours, 'time': t,
                          'time_UTC': pd.to_datetime(t, unit='s', utc=True),
                          'cell_1': cells, 'season': 'SON'})
    arrays = {'time': t, 'position_ok': np.ones(len(t), bool),
              'mapping_ok': np.ones(len(t), bool), 'inside_D': inside,
              'in_R': hours < 24, 'regime': np.ones(len(t), np.int8),
              'loss': float(t[-1] + 86400), 'visit_cell_1': (hours >= 24).astype(int)}
    return frame, arrays, event_bounds(arrays)


class InputTests(unittest.TestCase):
    def test_exit_return_is_stopped_outside_not_endpoint(self):
        m = api()
        frame, arrays, events = path()
        endpoint, stopped = generate(frame, arrays, events, 1, np.array([0]), 7, 'pooled')
        self.assertEqual(endpoint.destination_cell_1.iloc[0], 20)
        self.assertEqual(stopped.destination_cell_1.iloc[0], -2)
        counts = m.count_pairs(stopped)
        self.assertEqual(counts.destination_cell_1.tolist(), [-2])
        self.assertEqual(counts.pair_count.tolist(), [1])

    def test_gap_before_exit_is_excluded_without_fabricated_destination(self):
        m = api()
        frame, arrays, events = path(remove_hour=12)
        endpoint, stopped = generate(frame, arrays, events, 1, np.array([0]), 7, 'pooled')
        self.assertEqual(endpoint.reason_code.iloc[0], 0)
        self.assertEqual(stopped.reason_code.iloc[0], 6)
        self.assertTrue(m.count_pairs(stopped).empty)
        audit = m.audit_pairs(stopped, 'R')
        self.assertEqual(audit.reason_code.tolist(), [6])
        self.assertEqual(audit.candidate_count.tolist(), [1])

    def test_known_exit_survives_later_track_termination(self):
        m = api()
        frame, arrays, events = path()
        _, stopped = generate(frame, arrays, events, 1, np.array([0]), 30, 'pooled')
        self.assertEqual(stopped.reason_code.iloc[0], 0)
        self.assertEqual(m.count_pairs(stopped).destination_cell_1.iloc[0], -2)

    def test_all_candidates_accounted_for_and_duplicate_keys_rejected(self):
        m = api()
        frame, arrays, events = path()
        _, stopped = generate(frame, arrays, events, 1, np.arange(20), 7, 'pooled')
        counts = m.count_pairs(stopped)
        audit = m.audit_pairs(stopped, 'D')
        self.assertEqual(int(counts.pair_count.sum()), 20)
        self.assertEqual(int(audit.candidate_count.sum()), 20)
        with self.assertRaises(ValueError):
            m.count_pairs(pd.concat([stopped, stopped.iloc[:1]], ignore_index=True))
        with self.assertRaises(ValueError):
            bad = stopped.copy()
            bad['target'] = 'endpoint'
            m.count_pairs(bad)

    def test_secondary_failures_are_retained_as_nondisjoint_counts(self):
        m = api()
        self.assertTrue(hasattr(m, 'secondary_audit'), 'Missing secondary predicate ledger')
        frame, arrays, events = path(remove_hour=12)
        _, stopped = generate(frame, arrays, events, 1, np.array([0]), 30, 'pooled')
        self.assertEqual(stopped.reason_code.iloc[0], 6)
        audit = m.secondary_audit(stopped, 'D').set_index('predicate')
        self.assertEqual(int(audit.loc['track_termination', 'flagged_count']), 1)
        self.assertEqual(int(audit.loc['incomplete_path', 'flagged_count']), 1)
        self.assertEqual(int(audit.loc['path_timestamp_gap', 'flagged_count']), 1)


if __name__ == '__main__':
    unittest.main()
