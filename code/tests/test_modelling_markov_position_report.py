import unittest
import pandas as pd
from data3001.modelling.markov_position_report import comparison_table,report_text


class PositionReportTests(unittest.TestCase):
    def test_integration_and_issued_forecasts_are_distinct(self):
        s=pd.DataFrame([{'horizon_days':7,'model':'exact-position','repeat':r,
            'S_integration':.8+r*.01,'S_issued':.83+r*.01,'U_mass':.02,'E_mass':.01,
            'region90_available':.9,'region90_hit':.85,'region90_cells':20,
            'eligible_pairs':100,'independent_ids':10} for r in [0,1]])
        table=comparison_table(s)
        self.assertAlmostEqual(table.S_estimate.iloc[0],.805)
        self.assertAlmostEqual(table.repeat_range.iloc[0],.01)
        text=report_text(table,pd.DataFrame())
        for required in ['Monte Carlo','not a continuous-velocity','not independently','not proven structural','No final-test']:
            self.assertIn(required,text)


if __name__=='__main__':unittest.main()
