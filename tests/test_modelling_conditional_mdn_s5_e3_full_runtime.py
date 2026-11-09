import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

from data3001.modelling.continuous_models import conditional_mdn_s5_e3_full_runtime as runtime


class FormalRuntimeTests(unittest.TestCase):
    def setup_run(self, root):
        name = 'conditional_mdn_s5_e3_synthetic'
        folder = root/'provenance/runs'/name/'formal_v1'
        folder.mkdir(parents=True)
        (root/'results/runs'/name).mkdir(parents=True)
        (folder/'authorization.json').write_text(json.dumps(dict(
            full_experiment_authorized=True, resource_time_limit_seconds=None)))
        (folder.parent/'resource_ledger.json').write_text(json.dumps(dict(
            entries=[dict(elapsed_seconds=12.5)], active=None)))
        return name, folder

    def test_command_records_prior_usage_without_time_cutoff(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            name, folder = self.setup_run(root)
            with patch.object(runtime, 'ROOT', root):
                result = runtime.supervise(name, 'small', [sys.executable, '-c', 'print("ok")'])
            ledger = json.loads((folder/'resource_ledger.json').read_text())
            self.assertEqual(result, 0)
            self.assertEqual(ledger['prior_compute_seconds'], 12.5)
            self.assertIsNone(ledger['resource_limit_seconds'])
            self.assertIsNone(ledger['active'])
            self.assertEqual((folder/'small.log').read_text().strip(), 'ok')

    def test_failure_is_not_marked_complete_or_left_running(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            name, folder = self.setup_run(root)
            with patch.object(runtime, 'ROOT', root):
                result = runtime.supervise(name, 'failure', [sys.executable, '-c', 'raise SystemExit(7)'])
            ledger = json.loads((folder/'resource_ledger.json').read_text())
            self.assertEqual(result, 7)
            self.assertIsNone(ledger['active'])
            self.assertEqual(ledger['entries'][0]['returncode'], 7)


if __name__ == '__main__':
    unittest.main()
