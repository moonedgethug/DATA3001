"""Coordinate provenance and stopped-target integration checks for E7."""
import unittest
import numpy as np
import pandas as pd
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.exact_origin_s4_e7_inputs import attach_starts, attach_endpoints, coordinates


class CoordinateChecks(unittest.TestCase):
    def setUp(self):
        self.t0=1577836800.
        self.positions=pd.DataFrame({'id':[1,1], 'source_obs':[20,10],
            'time':[self.t0+604800,self.t0], 'cell_1':cells(np.array([-75.2,-76.2]),np.array([32.8,32.1])),
            'lon_normalized':[-75.2,-76.2],'lat':[32.8,32.1]})
        self.labels=pd.DataFrame({'id':[1], 'origin_source_obs':[10], 'endpoint_source_obs':[20],
            'horizon_days':[7], 'origin_time_UTC':[pd.Timestamp(self.t0,unit='s',tz='UTC')],
            'origin_cell_1':[self.positions.iloc[1].cell_1], 'destination_cell_1':[self.positions.iloc[0].cell_1],
            'target_epoch':[self.t0+604800], 'outside':[False]})

    def test_source_keys_preserve_real_positions_despite_input_order(self):
        starts=attach_starts(self.labels,self.positions)
        result=attach_endpoints(starts,self.positions)
        self.assertEqual(result.iloc[0].lon,-76.2)
        self.assertEqual(result.iloc[0].endpoint_lon,-75.2)
        self.assertEqual(result.iloc[0].destination_cell_05,int(cells(np.array([-75.2]),np.array([32.8]),res=.5)[0]))

    def test_wrong_start_or_endpoint_time_is_rejected(self):
        for row in [0,1]:
            wrong=self.positions.copy();wrong.loc[row,'time']+=1
            with self.assertRaises(AssertionError):
                attach_endpoints(attach_starts(self.labels,wrong),wrong)

    def test_exit_never_uses_a_later_endpoint(self):
        labels=self.labels.copy();labels['outside']=True;labels['destination_cell_1']=-2;labels['endpoint_source_obs']=-1
        empty=coordinates(None,None,pd.DataFrame({'id':pd.Series(dtype='int64'),'source_obs':pd.Series(dtype='int64')}),{})
        result=attach_endpoints(labels,empty)
        self.assertEqual(len(result),1)
        self.assertEqual(result.iloc[0].destination_cell_05,-2)
        self.assertTrue(np.isnan(result.iloc[0].endpoint_lon))


if __name__=='__main__':unittest.main()
