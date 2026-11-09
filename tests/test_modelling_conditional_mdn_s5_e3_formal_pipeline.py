import unittest
import pandas as pd


class JoinTests(unittest.TestCase):
    def test_audit_merge_preserves_primary_and_rejects_missing_queries(self):
        from data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_pipeline import join_audit
        a = pd.DataFrame(dict(role=['C_outer']*2, position=[0,1], id=[1,2], K=[1,1],
                              origin_source_obs=[100,200],horizon_days=[7,7],
                              energy_km=[10.,20.], h90=[True,False]))
        b = pd.DataFrame(dict(role=['C_outer']*2, position=[0,1], id=[1,2], K=[1,1],
                              origin_source_obs=[100,200],horizon_days=[7,7],
                              audit_energy_km=[10.1,20.1], audit_h90=[True,False]))
        out = join_audit(a,b)
        self.assertEqual(out.energy_km.tolist(), [10.,20.])
        self.assertEqual(out.audit_energy_km.tolist(), [10.1,20.1])
        with self.assertRaises(ValueError):
            join_audit(a,b.iloc[:1])
        b.loc[1,'origin_source_obs']=201
        with self.assertRaises(ValueError):
            join_audit(a,b)
        b.loc[1,'origin_source_obs']=200
        b.loc[1,'id']=3
        with self.assertRaises(ValueError):
            join_audit(a,b)

    def test_unregistered_precision_upgrade_is_not_allowed(self):
        from data3001.modelling.continuous_models.conditional_mdn_s5_e3_formal_pipeline import next_level
        self.assertEqual(next_level(65536),131072)
        self.assertEqual(next_level(131072),262144)
        with self.assertRaises(ArithmeticError):next_level(262144)
        with self.assertRaises(ValueError):next_level(32768)


if __name__ == '__main__':unittest.main()
