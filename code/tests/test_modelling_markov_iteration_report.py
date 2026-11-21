import unittest
import pandas as pd
from data3001.modelling.markov_iteration_report import report_text


class IterationReportTests(unittest.TestCase):
    def test_report_separates_optimisation_from_position_and_test_claims(self):
        s=pd.DataFrame([{'model':'position-CV','S':.98,'eligible_pairs':20,'independent_ids':3}])
        text=report_text(s,pd.DataFrame(),[])
        for words in ['independently optimised','matched-setting','adaptive development','not final-test',
                      'conditional component count','No path was eliminated','not percentage accuracy']:
            self.assertIn(words,text)


if __name__=='__main__':unittest.main()
