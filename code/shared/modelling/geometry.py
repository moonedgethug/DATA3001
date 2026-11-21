"""Shared endpoint geometry; mapper sentinels are distinct from model states."""
from dataclasses import dataclass
import json
import numpy as np
import shapely as sh
from shapely.geometry import shape
from data3001.preprocessing.prep_core import cells
OUTSIDE = -2
UNRESOLVED = -1

@dataclass
class EndpointMapper:
    domain: object
    land: object = None
    _land_cell_class: object = None

    def __post_init__(self):
        # GEOS may lazily construct mutable spatial indexes on first use even
        # after prepare(). Workers must not share those native objects.
        self._domain_wkb = sh.to_wkb(self.domain)
        self._land_wkb = sh.to_wkb(self.land) if self.land is not None else None
        sh.prepare(self.domain)
        if self.land is not None:
            sh.prepare(self.land)
            if self._land_cell_class is None:
                # Exact accelerator: a CLOSED cell is proven wholly water,
                # wholly land, or mixed. Only mixed cells need point predicates.
                x0, y0, x1, y1 = self.domain.bounds
                xx, yy = np.meshgrid(np.arange(max(-180, int(np.floor(x0))),
                                                min(179, int(np.floor(x1)))+1),
                                      np.arange(max(-90, int(np.floor(y0))),
                                                min(89, int(np.floor(y1)))+1))
                xx, yy = xx.ravel(), yy.ravel()
                boxes = sh.box(xx, yy, xx+1, yy+1)
                grid = np.ones(64800, dtype=np.uint8)  # 0 water, 1 mixed/unknown, 2 land
                keys = (yy+90)*360+xx+180
                hit = sh.intersects(self.land, boxes)
                grid[keys[~hit]] = 0
                full = sh.covers(self.land, boxes[hit])
                grid[keys[hit][full]] = 2
                grid.flags.writeable = False
                self._land_cell_class = grid

    def worker_copy(self):
        return EndpointMapper(sh.from_wkb(self._domain_wkb),
                              sh.from_wkb(self._land_wkb) if self._land_wkb is not None else None,
                              self._land_cell_class)

    def __call__(self, lon, lat):
        lon, lat = np.broadcast_arrays(np.asarray(lon, float), np.asarray(lat, float))
        shape = lon.shape
        x, y = lon.ravel(), lat.ravel()
        result = np.full(len(x), UNRESOLVED, dtype=np.int32)
        good = np.isfinite(x) & np.isfinite(y) & (y >= -90) & (y < 90)
        ix = np.flatnonzero(good)
        x = (x + 180) % 360 - 180
        inside = sh.intersects_xy(self.domain, x[ix], y[ix])
        result[ix[~inside]] = OUTSIDE
        local = ix[inside]
        codes = cells(x[local], y[local], res=1)
        if self.land is not None:
            # Geometric lookup must use the box actually containing the point.
            # floor(lat+90) can round a nextafter-below-integer point into the
            # next scientific cell. Keep those frozen labels, not that lookup.
            lookup = ((np.floor(y[local]).astype(np.int64)+90)*360
                      + np.floor(x[local]).astype(np.int64)+180)
            kind = self._land_cell_class[lookup]
            on_land = kind == 2
            mixed = kind == 1
            on_land[mixed] = sh.intersects_xy(self.land, x[local[mixed]], y[local[mixed]])
            local, codes = local[~on_land], codes[~on_land]
        result[local] = codes
        return result.reshape(shape)



def mapper_for(paths):
    domain=shape(json.loads(paths.asset('transport_D',verify=True).read_text())['features'][0]['geometry'])
    return EndpointMapper(domain,sh.from_wkb(paths.asset('land_mask_high',verify=True).read_bytes()))
