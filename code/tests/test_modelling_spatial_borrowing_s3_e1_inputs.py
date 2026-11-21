import unittest
from unittest.mock import patch
import sys
import numpy as np
import pandas as pd
from shapely.geometry import box, GeometryCollection
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import (
    Geometry, classify_windows, neighbours, translated_cell, union_view, FALLBACK,
    source_hashes,
)
from data3001.paths import project_paths


def frame(x,y=None,t=None):
    n=len(x)
    return pd.DataFrame(dict(id=1,source_obs=np.arange(n),time=np.arange(n)*3600 if t is None else t,
                            lon=x,lat=np.ones(n)*.4 if y is None else y,position_ok=True,mapping_ok=True))


def labels(start=0,target=7200):
    return pd.DataFrame(dict(origin_source_obs=[start],target_epoch=[target]))


class SpatialInputTests(unittest.TestCase):
    def test_source_inventory_includes_module_entry_point(self):
        paths=project_paths()
        entry='src/data3001/modelling/baselines/run_spatial_borrowing_s3_e1.py'
        with patch.object(sys.modules['__main__'],'__file__',str(paths.root/entry)):
            inventory=source_hashes(paths)
        self.assertIn(entry,inventory)
        self.assertIn('src/data3001/modelling/baselines/spatial_borrowing_s3_e1_inputs.py',inventory)

    def geometry(self,land=None,mid=None,domain=None):
        if land is None: land=GeometryCollection()
        if mid is None: mid=land
        return Geometry(box(-2,-2,4,2),domain if domain is not None else box(-2,-2,4,2),land,mid,
                        set(cells(np.tile(np.arange(-2,4)+.5,4),np.repeat(np.arange(-2,2)+.5,6))))

    def run_window(self,f,geo=None,dx=0,dy=0,start=0,target=7200):
        g=geo or self.geometry();e=g.events(f,dx,dy)
        expected=cells(np.array([f.lon.iloc[start]+dx]),np.array([f.lat.iloc[start]+dy]))
        return classify_windows(f,labels(start,target),expected,e),e

    def test_neighbours_exclude_self_and_wrap(self):
        c=int(cells(np.array([0.2]),np.array([0.2]))[0])
        self.assertEqual(len(neighbours(c)),8); self.assertNotIn(c,neighbours(c))
        self.assertIn(translated_cell(c,1,-1),neighbours(c)); self.assertEqual(len(neighbours(0)),5)

    def test_translation_preserves_subcell_and_increments(self):
        f=frame([.2,.5,1.2]);(out,why,*_),e=self.run_window(f,dx=1)
        np.testing.assert_allclose(e['x'],[1.2,1.5,2.2]);self.assertEqual(out[0],cells(np.array([2.2]),np.array([.4]))[0]);self.assertEqual(why[0],0)
        np.testing.assert_allclose(np.diff(e['x']),np.diff(f.lon))

    def test_exit_remains_absorbing_after_return(self):
        (out,why,*_),_=self.run_window(frame([.2,5,.2]))
        self.assertEqual(out[0],-2);self.assertEqual(why[0],0)

    def test_segment_crossing_water_endpoints_is_fallback(self):
        geo=self.geometry(box(.9,0,1.1,1));(out,why,*_),_=self.run_window(frame([.2,1.5,2]),geo)
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],6)

    def test_mask_disagreement_is_distinct(self):
        geo=self.geometry(box(.9,0,1.1,1),GeometryCollection());(out,why,*_),_=self.run_window(frame([.2,1.5,2]),geo)
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],10)

    def test_gap_before_exit_is_not_exit(self):
        (out,why,*_),_=self.run_window(frame([.2,5],t=[0,7200]))
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],5)

    def test_land_after_exit_does_not_reverse_exit(self):
        geo=self.geometry(box(.9,0,1.1,1));(out,why,*_),_=self.run_window(frame([.2,-3,1]),geo)
        self.assertEqual(out[0],-2)

    def test_land_before_exit_overrides_later_exit(self):
        geo=self.geometry(box(.9,0,1.1,1));(out,why,*_),_=self.run_window(frame([.2,5,5]),geo)
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],6)

    def test_incoming_edge_not_part_of_new_release(self):
        geo=self.geometry(box(.9,0,1.1,1));(out,why,*_),_=self.run_window(frame([.2,1.5,2]),geo,start=1)
        self.assertGreaterEqual(out[0],0);self.assertEqual(why[0],0)

    def test_missing_continuation_is_fallback(self):
        (out,why,*_),_=self.run_window(frame([.2,.3]),target=7200)
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],7)

    def test_invalid_start_not_fabricated_exit(self):
        (out,why,*_),_=self.run_window(frame([5,5,5]))
        self.assertEqual(out[0],FALLBACK);self.assertEqual(why[0],8)

    def test_union_view_preserves_disjoint_windows(self):
        f=frame(np.ones(10))
        ls=pd.DataFrame(dict(origin_source_obs=[0,7],target_epoch=[3600,9*3600]))
        self.assertEqual(union_view(f,ls).source_obs.tolist(),[0,1,7,8,9])

    def test_domain_excursion_between_observations_not_exit(self):
        # Nonconvex domain: a segment crosses a domain gap but both observed ends are inside.
        dom=box(-1,-1,1,1).union(box(2,-1,4,1))
        (out,why,*_),_=self.run_window(frame([.2,2.2,2.4]),self.geometry(domain=dom))
        self.assertGreaterEqual(out[0],0);self.assertEqual(why[0],0)


if __name__=='__main__': unittest.main()
