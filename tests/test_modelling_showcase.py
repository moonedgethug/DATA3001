"""Presentation export must preserve evidence and remain usable offline."""
import importlib
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

import pandas as pd

from data3001.paths import ProjectPaths, file_sha256


class ShowcaseTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "configs").mkdir()
        (self.root / "configs/assets.json").write_text('{"schema_version":1,"assets":{}}')
        self.paths = ProjectPaths(self.root)
        self.run = self.root / "results/runs/fixture"
        self.provenance = self.root / "provenance/runs/fixture"
        self.run.mkdir(parents=True)
        self.provenance.mkdir(parents=True)
        self.fragment = ('<div id="data3001-nested-blend-review">'
                         '<script type="application/json" id="nested-blend-data">{"observed":{"n":123}}</script>'
                         '<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script></div>')
        (self.run / "comparison-inline.html").write_text(self.fragment)
        (self.run / "REPORT.md").write_text("# Frozen scientific report\n")
        pd.DataFrame([
            [h, m, score, hit, cells] for h in [7, 30]
            for m, score, hit, cells in [("B2", 1.0, 60.0, 60), ("Grid", .99, 85.0, 120),
                                         ("Analytic", .989, 86.0, 121)]
        ], columns=["horizon_days", "model", "brier_failure_penalized", "region90_hit_pct", "mean_region90_cells"]).to_csv(self.run / "outer_summary.csv", index=False)
        pd.DataFrame([[7, "Grid", .1], [30, "Grid", .6], [7, "Analytic", .09], [30, "Analytic", .58]],
                     columns=["horizon_days", "method", "lambda_value"]).to_csv(self.run / "final_lambda_selection.csv", index=False)
        (self.provenance / "run.json").write_text(json.dumps({"config": {"final_test_access": False}}))
        self.receipt = {"completed": True, "final_test_access": False,
                        "output_sha256": {str(p.relative_to(self.root)): file_sha256(p)
                                          for p in [*self.run.iterdir(), self.provenance / "run.json"]}}
        (self.provenance / "outputs.json").write_text(json.dumps(self.receipt))

    def api(self):
        name = "data3001.modelling.showcase"
        self.assertIsNotNone(importlib.util.find_spec(name), "Reusable showcase exporter is missing")
        return importlib.import_module(name)

    def test_offline_export_preserves_the_embedded_scientific_payload(self):
        api = self.api()
        before = {p: file_sha256(p) for p in self.run.iterdir()}
        output = api.build_showcase("fixture", paths=self.paths)
        html = output.read_text()
        self.assertNotIn('<script src="http', html)
        self.assertIn('id="nested-blend-data">{"observed":{"n":123}}', html)
        self.assertIn("0.600000", html)
        self.assertIn("not an independent evaluation", html)
        self.assertEqual(before, {p: file_sha256(p) for p in self.run.iterdir()})
        self.assertEqual(output, api.build_showcase("fixture", paths=self.paths))

    def test_corrupt_source_is_rejected_before_publishing(self):
        api = self.api()
        (self.run / "outer_summary.csv").write_text("corrupt")
        with self.assertRaisesRegex(ValueError, "checksum"):
            api.build_showcase("fixture", paths=self.paths)
        self.assertFalse((self.root / "results/deliverables/baseline_optimized/index.html").exists())

    def test_receipt_cannot_authorize_a_final_test_read(self):
        api = self.api()
        self.receipt["output_sha256"]["data/test/secret.parquet"] = "irrelevant"
        (self.provenance / "outputs.json").write_text(json.dumps(self.receipt))
        with self.assertRaises(PermissionError):
            api.build_showcase("fixture", paths=self.paths)

    def test_manual_presentation_edits_are_not_silently_overwritten(self):
        api = self.api()
        output = api.build_showcase("fixture", paths=self.paths)
        output.write_text("manual edit")
        with self.assertRaisesRegex(ValueError, "edited"):
            api.build_showcase("fixture", paths=self.paths)
        self.assertEqual(output.read_text(), "manual edit")


if __name__ == "__main__":
    unittest.main()
