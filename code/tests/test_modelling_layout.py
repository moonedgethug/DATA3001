"""Layout compatibility must not duplicate implementations or load neural models."""
import importlib
from pathlib import Path
import subprocess
import sys
import unittest


class ModellingLayoutTests(unittest.TestCase):
    def test_historical_modules_alias_canonical_owners(self):
        pairs = {
            "markov": "markov_models.markov",
            "markov_velocity": "markov_models.markov_velocity",
            "run_markov": "markov_models.run_markov",
            "run_blend_cv": "baselines.run_blend_cv",
            "markov_scoring": "common.markov_scoring",
            "experiment": "common.experiment",
            "continuous": "continuous_models.continuous",
            "run_continuous": "continuous_models.run_continuous",
        }
        for old, new in pairs.items():
            with self.subTest(module=old):
                self.assertIs(importlib.import_module("data3001.modelling." + old),
                              importlib.import_module("data3001.modelling." + new))

    def test_shared_exports_have_one_owner(self):
        from data3001.modelling.common.runtime import ReadOnlyInputs, verified_run
        from data3001.modelling.common.geometry import EndpointMapper, mapper_for
        from data3001.modelling.common.probability import score_distribution
        from data3001.modelling import run_blend_cv, run_neighbourhood, neighbourhood
        from data3001.modelling import run_markov_position, evaluate
        self.assertIs(ReadOnlyInputs, run_blend_cv.ReadOnlyInputs)
        self.assertIs(verified_run, run_neighbourhood.verified_run)
        self.assertIs(EndpointMapper, neighbourhood.EndpointMapper)
        self.assertIs(mapper_for, run_markov_position.mapper_for)
        self.assertIs(score_distribution, evaluate.score_distribution)

    def test_markov_import_does_not_require_optional_torch(self):
        code = """
import sys
class DenyTorch:
    def find_spec(self, fullname, path=None, target=None):
        if fullname == 'torch' or fullname.startswith('torch.'):
            raise AssertionError('Markov code attempted to import PyTorch')
sys.meta_path.insert(0, DenyTorch())
import data3001.modelling.markov_models.run_markov_velocity
import data3001.modelling.run_markov
assert 'torch' not in sys.modules
"""
        subprocess.run([sys.executable, "-B", "-c", code], check=True,
                       capture_output=True, text=True)

    def test_old_and_new_cli_help_are_equivalent(self):
        for name in ("run_markov", "run_markov_velocity"):
            outputs = []
            for prefix in ("data3001.modelling.", "data3001.modelling.markov_models."):
                result = subprocess.run([sys.executable, "-B", "-m", prefix + name, "--help"],
                                        check=True, capture_output=True, text=True)
                outputs.append(result.stdout)
                self.assertEqual(result.stderr, "")
            self.assertEqual(*outputs)

    def test_native_source_and_chart_assets_resolve_after_move(self):
        from data3001.modelling.markov_models.markov_neighbour_native import SOURCE
        from data3001.modelling.baselines import showcase
        self.assertTrue(SOURCE.is_file())
        asset = Path(showcase.__file__).resolve().parents[1] / "assets/d3-7.9.0.min.js"
        self.assertTrue(asset.is_file())


if __name__ == "__main__":
    unittest.main()
