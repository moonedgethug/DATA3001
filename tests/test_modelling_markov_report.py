"""Human-facing score semantics and comparable probability-map rendering."""
import importlib
import importlib.util
import unittest
from xml.etree import ElementTree as ET


class ReportTests(unittest.TestCase):
    def api(self):
        name = 'data3001.modelling.markov_report'
        if importlib.util.find_spec(name) is None:
            raise AssertionError('Required M1 report renderer is absent')
        return importlib.import_module(name)

    def test_map_uses_shared_scale_and_distinct_outside_unresolved(self):
        m = self.api()
        panels = [('M1', {44744: .1, -2: .2}, .7),
                  ('Observed held-out', {44744: .1, 44745: .9}, 0.)]
        svg = m.map_svg(panels, [], [], 44744, 7, 0)
        ET.fromstring(svg)
        self.assertIn('Shared scale', svg)
        self.assertIn('90.0%', svg)
        self.assertIn('OUTSIDE 20.000%', svg)
        self.assertIn('unresolved 70.000%', svg)
        self.assertIn('7 days', svg)
        self.assertIn('stopped', svg)


if __name__ == '__main__':
    unittest.main()
