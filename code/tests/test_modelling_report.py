"""Guard the held-out comparison, lossless display packing and basemap winding."""
import json

import numpy as np
import pandas as pd
from pathlib import Path
import tempfile
import unittest
from shapely import to_wkb
from shapely.geometry import MultiPolygon, Polygon, mapping, shape

from data3001.modelling.report import (
    _compact_models, _default_origins, _geometry, _json_safe, _observed,
)


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.tmp_path = Path(self.temp.name)

    def test_observed_panel_keeps_matching_outer_holdout_and_pair_weights(self):
        counts = pd.DataFrame([
            [101, 7, 44744, 44744, 3], [101, 7, 44744, -2, 1],
            [102, 7, 44744, 44744, 1000], [103, 30, 44744, 44745, 2],
        ], columns=["id", "horizon_days", "origin_cell_1", "destination_cell_1", "pair_count"])
        folds = pd.DataFrame({"id": [101, 102, 103], "outer_fold": [0, 1, 0]})
        observed = _observed(counts, folds)
        assert observed["0:7:44744"] == {"n": 4, "ids": 1, "counts": [[-2, 1], [44744, 3]]}
        assert observed["1:7:44744"]["n"] == 1000
        assert observed["0:30:44744"]["counts"] == [[44745, 2]]
        with self.assertRaisesRegex(ValueError, "without outer-fold"):
            _observed(counts, folds.iloc[:2])


    def test_default_origin_uses_worst_horizon_training_id_support_then_cell_id(self):
        support = pd.DataFrame([
            [0, 7, 10, 1, 100], [0, 30, 10, 1, 1],
            [0, 7, 20, 1, 7], [0, 30, 20, 1, 6],
            [0, 7, 30, 1, 6], [0, 30, 30, 1, 8],
        ], columns=["outer_fold", "horizon_days", "origin_cell_1", "pair_count", "independent_ids"])
        assert _default_origins(support, [0]) == {"0": 20}


    def test_integer_probability_encoding_is_lossless_and_rejects_other_models(self):
        support = pd.DataFrame([[0, 7, 10, 3, 2]], columns=[
            "outer_fold", "horizon_days", "origin_cell_1", "pair_count", "independent_ids"])
        distribution = {"10": 2 / 3, "-2": 1 / 3}
        models = {"0": {"B1": {"7": distribution}, "B2": {"7:10": distribution}}}
        packed = _compact_models(models, [0], support)
        for model, key in [("B1", "7"), ("B2", "7:10")]:
            item = packed["0"][model][key]
            assert {str(cell): n / item["n"] for cell, n in item["counts"]} == distribution
        models["0"]["B1"]["7"] = {"10": .5, "-2": .5}
        with self.assertRaisesRegex(ValueError, "losslessly"):
            _compact_models(models, [0], support)
        assert _json_safe({"loss": np.inf, "missing": np.nan}) == {"loss": None, "missing": None}


    def test_display_winding_is_fixed_after_rounding_thin_islands(self):
        tmp_path = self.tmp_path
        # These two real display triangles reverse orientation at four decimals.
        # A clockwise pre-rounding ring alone is therefore not a sufficient guard.
        thin_a = Polygon([(-70.056799, 43.754099), (-70.045801, 43.765099),
                          (-70.061901, 43.749101)])
        thin_b = Polygon([(-64.203901, 44.350901), (-64.229099, 44.356299),
                          (-64.204899, 44.351099)])
        collapsed = Polygon([(-69.000001, 40.000001), (-69.000002, 40.000001),
                             (-69.000001, 40.000002)])
        mainland = Polygon([(-79, 39), (-78, 39), (-78, 40), (-79, 40)])
        land_path, region_path = tmp_path / "land.wkb", tmp_path / "region.geojson"
        land_path.write_bytes(to_wkb(MultiPolygon([thin_a, thin_b, collapsed, mainland])))
        region_path.write_text(json.dumps({"type": "FeatureCollection", "features": [
            {"type": "Feature", "geometry": mapping(mainland), "properties": {}}]}))
        display = _geometry(land_path, region_path)
        land = shape(display["land"])
        parts = list(land.geoms) if land.geom_type == "MultiPolygon" else [land]
        assert all(part.is_valid and part.area > 0 for part in parts)
        assert all(not part.exterior.is_ccw for part in parts)
        assert all(hole.is_ccw for part in parts for hole in part.interiors)
        assert display["geometry_display"]["degenerate_land_parts_removed"] >= 1
        assert not land.contains(shape({"type": "Point", "coordinates": [-60, 35]}))
