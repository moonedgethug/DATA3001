"""Runner configuration and human report fixtures without dataset access."""
import importlib
import unittest
import pandas as pd


class RunTests(unittest.TestCase):
    def test_configuration_rejects_unapproved_predictors_or_loss(self):
        m = importlib.import_module('data3001.modelling.run_markov_velocity')
        from data3001.paths import project_paths
        settings = m.settings(project_paths())
        self.assertEqual(settings['velocity_classes'], 9)
        for key, value in [('predictors', ['origin_cell_1', 've', 'vn', 'sst']),
                            ('primary_metric', 'linear_quadratic_reference'),
                            ('final_test_access', True), ('velocity_classes', 17)]:
            bad = dict(settings); bad[key] = value
            with self.subTest(key=key), self.assertRaises(ValueError): m.validate_settings(bad)

    def test_report_explicitly_limits_query_and_refit_claims(self):
        m = importlib.import_module('data3001.modelling.markov_velocity_report')
        text = m.report_text(pd.DataFrame(), pd.DataFrame(), pd.DataFrame(), {7: (3, .2), 30: (5, .4)}, .25)
        for phrase in ['initial velocity', 'not independently', 'categorical', 'final test', 'linear', '365']:
            self.assertIn(phrase, text)


if __name__ == '__main__': unittest.main()
