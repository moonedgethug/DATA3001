import importlib
import importlib.util
import sys
import unittest
from pathlib import Path
import numpy as np
import pandas as pd
import pyarrow as pa
import duckdb
from shapely.geometry import box, Polygon

class Handover(unittest.TestCase):
    def module(self):
        self.assertIsNotNone(importlib.util.find_spec('data3001.preprocessing.prep_handover'), 'Regional area/support implementation is missing')
        return importlib.import_module('data3001.preprocessing.prep_handover')

    def test_boundary_contact_has_zero_release_area(self):
        h=self.module();cell=box(0,0,1,1)
        a=h.region_area_fields(cell,cell,box(1,0,2,1),box(0,0,2,2))
        self.assertTrue(a['R_boundary_only']);self.assertFalse(a['R_positive_area'])
        self.assertEqual(a['wet_area_in_R'],0);self.assertGreater(a['wet_area_in_D'],12000)

    def test_land_only_region_overlap_has_no_water_release(self):
        h=self.module();cell=box(0,0,1,1);water=box(.5,0,1,1)
        a=h.region_area_fields(cell,water,box(0,0,.4,1),cell)
        self.assertTrue(a['R_positive_area']);self.assertFalse(a['R_boundary_only'])
        self.assertEqual(a['wet_area_in_R'],0)
        self.assertTrue(np.allclose(h.release_weights([0,2,1]),[0,2/3,1/3]))

    def test_polygon_hole_is_subtracted_from_area(self):
        h=self.module();wet=Polygon([(0,0),(1,0),(1,1),(0,1)],holes=[[(.25,.25),(.75,.25),(.75,.75),(.25,.75)]])
        a=h.region_area_fields(box(0,0,1,1),wet,box(0,0,1,1),box(0,0,1,1))
        self.assertGreater(a['wet_area_in_R'],9100);self.assertLess(a['wet_area_in_R'],9400)
        self.assertEqual(a['wet_area_in_R'],a['wet_area_in_D'])

    def test_zero_total_or_negative_release_area_is_rejected(self):
        h=self.module()
        for x in [[0,0],[2,-1],[1,float('nan')]]:
            with self.assertRaises(ValueError):h.release_weights(x)

    def test_annual_IDs_and_concentration_use_ID_union(self):
        h=self.module();con=duckdb.connect()
        f=pd.DataFrame({'id':[1,1,2],'cell':[10,10,10],'season':[0,1,0],
                        'candidates':[7,6,8],'eligible':[5,5,3]})
        con.register('p',pa.Table.from_pandas(f))
        row=h.support_summary(con,'p',['cell']).iloc[0]
        self.assertEqual(row.eligible_IDs,2);self.assertEqual(row.candidates,21)
        self.assertEqual(row.eligible,13);self.assertEqual(row.dominant_ID_pairs,10)
        self.assertAlmostEqual(row.dominant_ID_share,10/13)
        con.close()

    def test_zero_eligible_IDs_have_undefined_concentration(self):
        h=self.module();con=duckdb.connect()
        con.register('p',pa.Table.from_pandas(pd.DataFrame({'id':[1],'cell':[10],'candidates':[4],'eligible':[0]})))
        row=h.support_summary(con,'p',['cell']).iloc[0]
        self.assertEqual(row.eligible_IDs,0);self.assertTrue(np.isnan(row.dominant_ID_share))
        con.close()

    def test_recorded_depth_is_not_inferred_from_hardware(self):
        h=self.module()
        self.assertEqual(h.depth_stratum(15),'recorded_15m')
        self.assertEqual(h.depth_stratum(10),'recorded_10m')
        self.assertEqual(h.depth_stratum(40),'other_positive_recorded_depth')
        self.assertEqual(h.depth_stratum(np.nan),'missing_depth')
        self.assertEqual(h.depth_stratum(0),'nonpositive_or_nonfinite_depth_unresolved')

    def test_lag_view_keeps_targets_separate(self):
        h=self.module();con=duckdb.connect()
        con.register('native',pa.Table.from_pandas(pd.DataFrame({'id':[1],'split':['train'],'cell':[10],
            'season':[0],'days':[1],'scenario':['drogued'],'candidates':[4],'endpoint_eligible':[3],'stopped_eligible':[2]})))
        h.lag_view(con,'native')
        self.assertEqual(con.execute('SELECT target,eligible FROM lag ORDER BY target').fetchall(),[('endpoint',3),('stopped',2)])
        con.close()

    def test_position_census_checks_native_values_separately(self):
        h=self.module();con=duckdb.connect()
        con.register('p',pa.Table.from_pandas(pd.DataFrame({'lon':[0.,9999.,np.nan],'lat':[30.,30.,30.],
                                                           'position_ok':[True,False,True]})))
        self.assertEqual(h.position_census(con,'p'),{'rows':3,'bad_positions':1,'native_invalid':2})
        con.close()

    def test_batched_days_preserve_annual_ID_unions(self):
        h=self.module();con=duckdb.connect()
        con.register('p',pa.Table.from_pandas(pd.DataFrame({'id':[1,1,2,1],'days':[1,1,1,7],
            'season':[0,1,0,0],'cell':[10,10,10,10],'candidates':[7,6,8,2],'eligible':[5,5,3,1]})))
        rows=h.batched_summary(con,'p',['cell','days']).sort_values('days')
        self.assertEqual(rows.eligible.tolist(),[13,1]);self.assertEqual(rows.eligible_IDs.tolist(),[2,1])
        self.assertEqual(rows.dominant_ID_pairs.tolist(),[10,1]);con.close()

if __name__=='__main__':unittest.main()
