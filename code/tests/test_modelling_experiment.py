"""Synthetic whole-ID partition checks; no dataset access"""

import importlib
import importlib.util
import unittest

class ExperimentTests(unittest.TestCase):
    def module(self):
        name = "data3001.modelling.experiment"
        self.assertIsNotNone(
            importlib.util.find_spec(name),
            "The experiment module has not been created yet.",
        )
        return importlib.import_module(name)
    
    def test_assignment_is_deterministic_and_order_independent(self):
        m = self.module()
        ids = list(range(1001, 1401))
        
        first = m.make_nested_folds(ids)
        second = m.make_nested_folds(list(reversed(ids)))
        
        self.assertEqual(first, second)
        self.assertEqual(m.fold_digest(*first), m.fold_digest(*second))
        
    def test_outer_holdout_never_enters_inner_folds(self):
        m = self.module()
        ids = set(range(1001, 1401))
        outer, inner = m.make_nested_folds(sorted(ids))
        seen = set()
        
        for fold in range(5):
            heldout = {
                sid for sid, value in outer.items() if value == fold
            }
            
            self.assertTrue(heldout)
            self.assertFalse(seen & heldout)
            seen |= heldout
            
            self.assertEqual(set(inner[fold]), ids - heldout)
            self.assertFalse(heldout & set(inner[fold]))
            self.assertEqual(set(inner[fold].values()), set(range(4)))
            
        self.assertEqual(seen, ids)
        
    def test_invalid_id_input_is_rejected(self):
        m = self.module()
        
        for ids in (
            [1, 1, 2, 3, 4, 5],
            [1, 2],
            [1.5, 2, 3, 4, 5],
        ):
            with self.subTest(ids=ids):
                with self.assertRaises(ValueError):
                    m.make_folds(ids)
                    
                    

if __name__ == "__main__":
    unittest.main()