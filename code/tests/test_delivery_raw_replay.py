"""Raw replay boundaries and evidence selection, using synthetic temporary inputs."""

import importlib.util
import json
from pathlib import Path
import sys
import tempfile
import unittest


CODE = Path(__file__).resolve().parents[1]
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))


class RawReplayTests(unittest.TestCase):
    def setUp(self):
        path = CODE / "reproduction/raw_replay.py"
        self.assertTrue(path.is_file(), "Raw replay adapter is missing")
        from reproduction import raw_replay
        self.replay = raw_replay
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name).resolve()

    def records(self):
        return {"10": {"pool": "train", "source_index": 1},
                "20": {"pool": "test", "source_index": 2},
                "30": {"pool": "train", "source_index": 0}}

    def test_default_selection_is_all_development_in_source_order(self):
        self.assertEqual(self.replay._select_development_ids(self.records(), None), ["30", "10"])

    def test_test_unknown_and_duplicate_ids_are_rejected(self):
        for ids, error in (([20], PermissionError), ([99], ValueError), ([10, 10], ValueError), ([], ValueError)):
            with self.subTest(ids=ids), self.assertRaises(error):
                self.replay._select_development_ids(self.records(), ids)

    def test_legacy_mapping_uses_most_specific_directory(self):
        mapping = {"file_map": {"one.json": "reference/one.json"},
                   "directory_map": {"raw": "archive/raw", "raw/nested": "archive/special"}}
        self.assertEqual(self.replay._legacy_target(mapping, "one.json"), "reference/one.json")
        self.assertEqual(self.replay._legacy_target(mapping, "raw/nested/file"), "archive/special/file")

    def test_raw_binding_only_selects_needed_observation_chunks(self):
        import numpy as np
        import zarr
        base = self.root / "archive/raw/source.zarr"
        group = zarr.open_group(str(base), mode="w")
        for name, values, dimension, chunk in (
            ("id", [10, 20, 30], "traj", 3), ("rowsize", [2, 2, 2], "traj", 3),
            ("time", [0, 1, 2, 3, 4, 5], "obs", 3),
        ):
            array = group.create_dataset(name, data=np.array(values), chunks=(chunk,))
            array.attrs["_ARRAY_DIMENSIONS"] = [dimension]
        zarr.consolidate_metadata(str(base))
        bound = []
        class Mapping:
            def resolve(_, relative):
                return self.root / relative
        class View:
            mapping = Mapping()
            def bind(_, relative, **kwargs):
                bound.append(relative)
        result = self.replay._bind_raw_chunks(View(), "archive/raw/source.zarr", ["10"])
        self.assertIn("archive/raw/source.zarr/time/0", bound)
        self.assertNotIn("archive/raw/source.zarr/time/1", bound)
        self.assertEqual(result["selected_ids"], ["10"])
        self.assertTrue(result["shared_raw_chunks_may_contain_other_ids"])

    def test_comparison_distinguishes_content_metadata_and_bytes(self):
        import pyarrow as pa
        left = pa.table({"x": [1., None, float("nan")]})
        right = left.replace_schema_metadata({b"creator": b"different"})
        comparison = self.replay._compare_tables(left, right)
        self.assertTrue(comparison["content_equal"])
        self.assertFalse(comparison["schema_metadata_equal"])
        changed = pa.table({"x": [2., None, float("nan")]})
        self.assertFalse(self.replay._compare_tables(left, changed)["content_equal"])

    def test_preparation_roundtrip_preserves_historical_timestamp_storage(self):
        import pandas as pd
        frame = pd.DataFrame({"time_UTC": pd.to_datetime([0., 3600.], unit="s", utc=True), "value": [1, 2]})
        self.assertTrue(hasattr(self.replay, "_prepared_storage_roundtrip"))
        restored = self.replay._prepared_storage_roundtrip(frame)
        self.assertEqual(str(restored.time_UTC.dtype), "datetime64[ms, UTC]")
        self.assertEqual(restored.value.tolist(), [1, 2])


if __name__ == "__main__":
    unittest.main()
