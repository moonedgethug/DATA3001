"""Report replay boundaries and probability accounting; no model fitting."""
from pathlib import Path
import importlib.util
import sys
import tempfile
import unittest

CODE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CODE))


class DeliveryReportTests(unittest.TestCase):
    def adapter(self):
        path = CODE / "reporting/delivery_report.py"
        self.assertTrue(path.is_file(), "The report reproduction adapter is missing")
        spec = importlib.util.spec_from_file_location("delivery_report_test", path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_unknown_figure_is_rejected_before_creating_a_run(self):
        report = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(ValueError):
                report.run(directory, figures=["not-a-figure"])
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_all_figures_are_selected_once_and_explicit_selection_is_preserved(self):
        report = self.adapter()
        self.assertEqual(len(report.select_figures(None)), 6)
        self.assertEqual(report.select_figures(["regional_distribution", "regional_distribution"]),
                         ["regional_distribution"])

    def test_unresolved_release_mass_is_retained(self):
        report = self.adapter()
        rows = [{"scenario": "area_release", "category": name, "probability": value}
                for name, value in [("R_water", .674), ("D_water_outside_R", .314),
                                    ("D_land", .003), ("outside_D", .0004), ("unresolved", .0086)]]
        result = report.check_probability_rows(rows, .0086)
        self.assertAlmostEqual(result["unresolved_weight"], .0086)
        self.assertAlmostEqual(result["scenario_totals"]["area_release"], 1.)

    def test_dropping_or_renormalizing_unresolved_mass_fails(self):
        report = self.adapter()
        for rows in [
            [{"scenario": "area_release", "category": "R_water", "probability": 1.}],
            [{"scenario": "area_release", "category": "R_water", "probability": 1.},
             {"scenario": "area_release", "category": "unresolved", "probability": .0086}],
        ]:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                report.check_probability_rows(rows, .0086)

    def test_bundle_is_portable_data_only_and_rejects_changed_bytes(self):
        report = self.adapter()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            folder = root / "data/prepared/report_inputs"
            folder.mkdir(parents=True)
            (folder / "table.csv").write_text("value\n1\n")
            entry = {"path": "table.csv", "sha256": "0" * 64,
                     "execution_path": "Final Report/figures/table.csv"}
            with self.assertRaises(ValueError):
                report.validate_bundle_entry(root, entry)
            for bad in ["../elsewhere.csv", "/tmp/elsewhere.csv", "script.py"]:
                with self.subTest(path=bad), self.assertRaises(ValueError):
                    report.validate_bundle_entry(root, dict(entry, path=bad))


if __name__ == "__main__":
    unittest.main()
