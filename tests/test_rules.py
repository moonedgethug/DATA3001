import sys
import unittest
from pathlib import Path
from data3001.acquisition import rules


class ContractRules(unittest.TestCase):
    def test_existing_id_assignments_survive_added_ids_and_reordering(self):
        old = {v: rules.split_id(v) for v in [123, 456, 789]}
        expanded = {v: rules.split_id(v) for v in [789, 999, 456, 123]}
        self.assertEqual(old, {v: expanded[v] for v in old})
        self.assertEqual(rules.split_id('000123'), rules.split_id(123))
        with self.assertRaises(ValueError):
            rules.canonical_id(123.5)

    def test_grid_wrap_and_half_open_boundaries(self):
        self.assertEqual(rules.grid_cell(-180, 0), (0, 90))
        self.assertEqual(rules.grid_cell(180, 0), (0, 90))
        self.assertEqual(rules.grid_cell(-179, 1), (1, 91))
        self.assertEqual(rules.grid_cell(-179, 1, 0.5), (2, 182))

    def test_exit_before_death_remains_stopped_outside(self):
        times = list(range(121))
        inside = [True] * 120 + [False]
        stopped = rules.classify(times, inside, [True]*121, [1]*121, 720, 1, 'stopped')
        endpoint = rules.classify(times, inside, [True]*121, [1]*121, 720, 1, 'endpoint')
        self.assertEqual(stopped, 'outside')
        self.assertEqual(endpoint, 'missing_endpoint')

    def test_gap_before_exit_does_not_prove_stopped_outside(self):
        self.assertEqual(rules.classify([0, 2], [True, False], [True, True], [1, 1], 720, 1, 'stopped'), 'unresolved_path')

    def test_later_drogue_loss_and_return_do_not_undo_exit(self):
        self.assertEqual(rules.classify([0, 1, 2, 3], [True, False, True, True], [True]*4, [1, 1, 0, 0], 3, 1, 'stopped'), 'outside')
        self.assertEqual(rules.classify([0, 1, 2, 3], [True, False, True, True], [True]*4, [1, 1, 0, 0], 3, 1, 'endpoint'), 'regime_ineligible')

    def test_endpoint_can_survive_intermediate_gap(self):
        self.assertEqual(rules.classify([0, 2], [True, True], [True]*2, [1]*2, 2, 1, 'endpoint'), 'inside')
        self.assertEqual(rules.classify([0, 2], [True, True], [True]*2, [1]*2, 2, 1, 'stopped'), 'unresolved_path')

    def test_equal_distance_endpoint_tie_chooses_earlier(self):
        self.assertEqual(rules.closest_endpoint([0, 23, 25], [True]*3, 24, 1), (1, -1))
        self.assertEqual(rules.closest_endpoint([0, 23, 25], [True]*3, 24, 0), (None, None))

    def test_chunk_spans_preserve_adjacent_trajectory_rows(self):
        self.assertEqual(rules.copy_spans([(2,6,0),(7,10,4)],4,4), [(0,2,2,4),(3,4,4,5)])
        self.assertEqual(rules.copy_spans([(2,6,0),(7,10,4)],10,4), [])

    def test_unknown_state_is_never_a_fixed_regime(self):
        for target in ['endpoint', 'stopped']:
            self.assertEqual(rules.classify([0,1], [True,True], [True,True], [None,None], 1, None, target), 'regime_ineligible')


if __name__ == '__main__':
    unittest.main()
