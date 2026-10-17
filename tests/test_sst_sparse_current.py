import importlib
import unittest
import pandas as pd
import numpy as np

try:
    m=importlib.import_module('data3001.sst_sparse_current')
except ModuleNotFoundError:
    m=None


class OfficialEpochTests(unittest.TestCase):
    def setUp(self):
        self.assertIsNotNone(m,'Explicit epoch-unit conversion is not implemented')

    def test_microsecond_storage_is_not_misread_as_nanoseconds(self):
        value=pd.Series(pd.to_datetime(['2020-09-22T00:00:00Z'],utc=True)).dt.as_unit('us')
        np.testing.assert_array_equal(m.official_end_seconds(value),[1600732800.])

    def test_timezone_strings_produce_the_same_official_epoch(self):
        np.testing.assert_array_equal(m.official_end_seconds(
            ['2020-09-22T08:00:00+08:00','2020-09-22T00:00:00Z']),[1600732800.]*2)

    def test_missing_official_date_remains_unknown(self):
        self.assertTrue(np.isnan(m.official_end_seconds([None])[0]))
