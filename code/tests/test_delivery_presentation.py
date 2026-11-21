"""Portable presentation export checks; no scientific inputs or fitting."""

from pathlib import Path
import sys
import unittest


CODE = Path(__file__).resolve().parents[1]
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class PresentationExportTests(unittest.TestCase):
    def setUp(self):
        self.assertTrue((CODE / "reporting/delivery_presentation.py").is_file(), "Presentation adapter is missing")
        from reporting import delivery_presentation
        self.adapter = delivery_presentation

    def test_part2_adaptation_changes_only_two_declared_io_literals(self):
        source = "ROOT=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')\n"
        source += "geo=json.loads(Path('/tmp/data3001-ne-land.json').read_text())\n"
        source += "result = scientific_function(values)\n"
        adapted, substitutions = self.adapter._adapt_part2(source)
        self.assertEqual(len(substitutions), 2)
        self.assertIn("result = scientific_function(values)\n", adapted)
        for substitution in reversed(substitutions):
            adapted = adapted.replace(substitution["after"], substitution["before"])
        self.assertEqual(adapted, source)

    def test_changed_original_literal_fails_closed(self):
        with self.assertRaises(ValueError):
            self.adapter._adapt_part2("ROOT=Path('/different/source')")

    def test_numeric_comparison_detects_nested_payload_changes(self):
        original = {"models": [{"score": .25, "map": [[1, 2, .75]]}], "scope": "development", "fit": False}
        self.assertTrue(self.adapter.compare_payload(original, original)["payload_exact_equal"])
        changed = {"models": [{"score": .26, "map": [[1, 2, .75]]}], "scope": "development", "fit": False}
        report = self.adapter.compare_payload(original, changed)
        self.assertFalse(report["payload_exact_equal"])
        self.assertFalse(report["numeric_exact_equal"])
        self.assertIn("$.models[0].score", report["differences"])

    def test_structural_change_is_not_hidden_by_matching_numbers(self):
        report = self.adapter.compare_payload({"x": [1, 2]}, {"x": [1, 2], "extra": None})
        self.assertFalse(report["payload_exact_equal"])


if __name__ == "__main__":
    unittest.main()
