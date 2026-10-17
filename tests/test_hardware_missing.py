"""Hardware cleaning must not erase zeros, inferred specifications or other data."""
import importlib.util
import json
import unittest

import numpy as np
import pyarrow as pa

from data3001.recovery_storage import tables_equal


FIELDS = ['DragAreaAboveDrogue', 'DragAreaOfDrogue', 'DragAreaRatio',
          'DrogueBallast', 'DrogueCenterDepth', 'DrogueLength', 'FloatDiameter']


class HardwareMissing(unittest.TestCase):
    def normalize(self, table):
        self.assertIsNotNone(importlib.util.find_spec('data3001.hardware_missing'),
                             'Scoped hardware NA normalization is not implemented')
        from data3001.hardware_missing import normalize_hardware_missing
        return normalize_hardware_missing(table)

    def source(self):
        values = [None, np.nan, np.inf, -np.inf, -1., 0., 15., 999., 1e20]
        data = {name: pa.array(values, type=pa.float32(), from_pandas=False)
                for name in FIELDS}
        data.update(id=[7]*9, drogue_status=pa.array([-1, 0, 1]*3, type=pa.int8()),
                    sst=pa.array([np.nan, None, 301.]*3, from_pandas=False))
        return pa.table(data).replace_schema_metadata({b'unchanged': b'preserve'})

    def test_nonfinite_and_negative_hardware_become_null_but_zero_and_positive_survive(self):
        # Wrong invalid mask or a blanket zero-to-NA conversion must fail here.
        out = self.normalize(self.source())
        for name in FIELDS:
            self.assertEqual(out[name].to_pylist()[:8],
                             [None, None, None, None, None, 0., 15., 999.])
            self.assertGreater(out[name][8].as_py(), 1e19)

    def test_other_columns_types_order_and_metadata_are_not_modified(self):
        # Accidental whole-table normalization must not touch SST or status.
        before = self.source(); out = self.normalize(before)
        self.assertEqual(out.column_names, before.column_names)
        self.assertTrue(out.schema.equals(before.schema, check_metadata=True))
        self.assertTrue(tables_equal(out.drop(FIELDS), before.drop(FIELDS)))
        self.assertTrue(tables_equal(out, self.normalize(out)))

    def test_only_source_declared_finite_fill_codes_are_converted(self):
        before = self.source(); name = 'FloatDiameter'
        field = before.schema.field(name).with_metadata({b'source_attributes':
                    json.dumps({'missing_value': [999., 0.]}).encode()})
        before = before.set_column(before.schema.get_field_index(name), field, before[name])
        out = self.normalize(before)
        self.assertIsNone(out[name][7].as_py())
        self.assertEqual(out[name][5].as_py(), 0.)
        self.assertEqual(out['DrogueLength'][7].as_py(), 999.)
        self.assertEqual(out.schema.field(name).metadata, field.metadata)


if __name__ == '__main__':
    unittest.main()
