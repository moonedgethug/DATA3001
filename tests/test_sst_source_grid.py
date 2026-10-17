import copy
import unittest
import numpy as np
from data3001.sst_source_grid import decode_grid


class TestOfficialGridDecode(unittest.TestCase):
    def payload(self):
        return {'table': {'columnNames': ['time', 'latitude', 'longitude', 'analysed_sst'],
            'columnUnits': ['UTC', 'degrees_north', 'degrees_east', 'degree_C'],
            'rows': [['1998-08-17T12:00:00Z', y, x, z]
                     for y, x, z in [(34.625,283.575,28.1),(34.625,283.625,None),
                                     (34.675,283.575,51.),(34.675,283.625,27.9)]]}}

    def test_readonly_pandas_array_is_copied_and_fill_is_not_temperature(self):
        payload=self.payload(); original=copy.deepcopy(payload)
        x,y,t=decode_grid(payload,10455)
        np.testing.assert_equal(t,[[28.1,np.nan],[np.nan,27.9]])
        self.assertEqual(payload,original)
        self.assertTrue(t.flags.writeable)
        np.testing.assert_equal(x,[283.575,283.625])
        np.testing.assert_equal(y,[34.625,34.675])

    def test_wrong_date_or_units_are_execution_errors(self):
        with self.assertRaises(ValueError):decode_grid(self.payload(),10456)
        payload=self.payload();payload['table']['columnUnits'][-1]='K'
        with self.assertRaises(ValueError):decode_grid(payload,10455)

    def test_duplicate_or_incomplete_grid_is_rejected(self):
        payload=self.payload();payload['table']['rows'].append(payload['table']['rows'][0])
        with self.assertRaises(ValueError):decode_grid(payload,10455)
        payload=self.payload();payload['table']['rows'].pop()
        with self.assertRaises(ValueError):decode_grid(payload,10455)
