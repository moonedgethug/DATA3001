import unittest
import numpy as np
import pandas as pd


class NeighbourReportTests(unittest.TestCase):
    def fixture(self):
        rows=[]
        for h in [7,30]:
            for sid,n in [(1,2),(2,8)]:
                for rep in [0,1]:
                    for model,score in [('self-CV',1.),('neighbour-CV',.9),('self-at-neighbour',.95)]:
                        rows.append((h,0,sid,model,rep,n,n*score))
        return pd.DataFrame(rows,columns=['horizon_days','outer_fold','id','model','repeat','pairs','S_integration_sum'])

    def test_ID_intervals_separate_horizons_and_preserve_all_pairs(self):
        from data3001.modelling.markov_neighbour_report import intervals
        table=intervals(self.fixture(),20)
        main=table.loc[table.comparison.eq('neighbour-CV minus self-CV')]
        self.assertEqual(set(main.horizon_days),{7,30});np.testing.assert_allclose(main.delta_S,-.1)
        np.testing.assert_allclose(main.lower_95,-.1);np.testing.assert_allclose(main.upper_95,-.1)

    def test_unmatched_case_counts_are_not_silently_compared(self):
        from data3001.modelling.markov_neighbour_report import intervals
        f=self.fixture();f.loc[0,'pairs']=3
        with self.assertRaises(ValueError):intervals(f,20)

    def test_cell_and_ID_tables_keep_both_improvements_and_worsenings(self):
        from data3001.modelling.markov_neighbour_report import heterogeneity
        rows=[]
        for sid,cell,delta in [(1,44000,-.1),(2,44001,.2)]:
            for rep in [0,1]:
                for model,s in [('self-CV',1.),('neighbour-CV',1+delta)]:
                    rows.append((7,0,sid,0,cell,model,rep,s))
        frame=pd.DataFrame(rows,columns=['horizon_days','outer_fold','id','origin_source_obs','origin_cell_1','model','repeat','S_integration'])
        a,b=heterogeneity(frame)
        np.testing.assert_allclose(a.sort_values('origin_cell_1').delta_S,[-.1,.2])
        self.assertEqual(set(b.id),{1,2});self.assertTrue(a.pairs.eq(1).all())


if __name__=='__main__':unittest.main()
