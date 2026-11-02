"""G2: exact component indexes, preserving the original land sets and holes."""
import numpy as np
import shapely as sh
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1 import G1Kernel,ExclusiveTimer
from data3001.preprocessing.prep_core import cells
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import FALLBACK
from data3001.modelling.common.qualified_count_inputs import EXIT


def components(geometry):
    if geometry.is_empty:return []
    if geometry.geom_type.startswith('Multi') or geometry.geom_type=='GeometryCollection':
        return [part for g in sh.get_parts(geometry) for part in components(g)]
    return [geometry]


class G2Kernel(G1Kernel):
    __slots__=('indexes','timer')

    def __init__(self,*args,**kwargs):
        super().__init__(*args,**kwargs);self.timer=None;self.indexes={}
        for name in ('high','intermediate','high_D','intermediate_D'):
            parts=np.asarray(components(getattr(self.geometry,name)),dtype=object)
            sh.prepare(parts);parts.flags.writeable=False
            self.indexes[name]=(parts,sh.STRtree(parts))

    def _call(self,name,fn,*args,**kwargs):
        return fn(*args,**kwargs) if self.timer is None else self.timer.call(name,fn,*args,**kwargs)

    def land_intersects(self,name,objects,eligible=None,stage='hourly_segment'):
        answer=np.zeros(len(objects),bool)
        chosen=np.arange(len(objects)) if eligible is None else np.flatnonzero(eligible)
        if not len(chosen):return answer
        parts,tree=self.indexes[name]
        pairs=self._call(stage+':index',tree.query,objects[chosen])
        if pairs.shape[1]:
            query_index,part_index=pairs
            hit=self._call(stage+':exact_predicate',sh.intersects,parts[part_index],objects[chosen[query_index]])
            np.logical_or.at(answer,chosen[query_index],hit)
        return answer

    def land_points(self,name,x,y,inside):
        answer=np.zeros(len(x),bool);ix=np.flatnonzero(inside)
        if len(ix):
            points=self._call('hourly_point:construction',sh.points,x[ix],y[ix])
            # Inside D, L intersect point equals (L intersect D) intersect point.
            answer[ix]=self.land_intersects(name+'_D',points,stage='hourly_point')
        return answer

    def rectangle_safe(self, xmin, xmax, ymin, ymax, possible):
        g = self.geometry
        ix = np.flatnonzero(possible)
        good = np.zeros(len(possible), bool)
        if not len(ix):
            return good
        boxes = sh.box(xmin[ix], ymin[ix], xmax[ix], ymax[ix])
        inside = (xmin[ix] >= -81) & (xmax[ix] <= -8) & (ymin[ix] >= 20) & (ymax[ix] <= 55) if self.rectangular_domain else sh.covers(g.domain, boxes)
        water = inside & ~self.land_intersects('high_D', boxes, inside, 'certificate') & ~self.land_intersects('intermediate_D', boxes, inside, 'certificate')
        x0 = np.floor(xmin[ix] + 180).astype(int)
        x1 = np.floor(xmax[ix] + 180).astype(int) + 1
        y0 = np.floor(ymin[ix] + 90).astype(int)
        y1 = np.floor(ymax[ix] + 90).astype(int) + 1
        p = self.state_prefix
        n = p[y1, x1] - p[y0, x1] - p[y1, x0] + p[y0, x0]
        good[ix] = water & (n == (x1 - x0) * (y1 - y0))
        return good

    def classify_context(self, q, c, *, check=lambda: None, certificates=True):
        if c.owner is not self.context_owner:
            raise ValueError('Stale or foreign kernel context')
        if q.id in c.fitting_ids or q.fold in c.donor_folds:
            raise PermissionError('Query ID/fold in donors')
        if q.horizon != c.horizon or q.origin != c.origin:
            raise ValueError('Wrong context role')
        n = len(c)
        out = np.full(n, FALLBACK, np.int64)
        why = np.zeros(n, np.int16)
        profile = dict(donors=n, certified=0, literal_pairs=0, hourly_steps=0)
        if not self.query_safe(q):
            why[:] = 11
            return (out, why, profile)
        g, t = (self.geometry, self.tracks)
        for first in range(0, n, self.batch_size):
            check()
            last = min(first + self.batch_size, n)
            sl = slice(first, last)
            size = last - first
            cert = self.certificates_context(q, c, sl) if certificates else np.zeros(size, bool)
            ci = np.flatnonzero(cert)
            sx = c.lon[sl]
            sy = c.lat[sl]
            if len(ci):
                ex = (q.lon + (c.end_lon[sl][ci] - sx[ci]) + 180) % 360 - 180
                ey = q.lat + (c.end_lat[sl][ci] - sy[ci])
                out[first + ci] = cells(ex, ey)
            profile['certified'] += int(cert.sum())
            active = np.flatnonzero(~cert)
            profile['literal_pairs'] += len(active)
            starts = c.start[sl].astype(int, copy=False)
            ends = c.track_end[sl].astype(int, copy=False)
            epochs = c.epoch[sl]
            prevx = np.full(size, q.lon)
            prevy = np.full(size, q.lat)
            for step in range(1, 24 * q.horizon + 1):
                if not len(active):
                    break
                if step % 16 == 0:
                    check()
                profile['hourly_steps'] += len(active)
                loc = starts[active] + step
                present = loc < ends[active]
                why[first + active[~present]] = 7
                active = active[present]
                loc = loc[present]
                if not len(active):
                    break
                timed = t.time[loc] == epochs[active] + 3600 * step
                why[first + active[~timed]] = 5
                active = active[timed]
                loc = loc[timed]
                if not len(active):
                    break
                x = (q.lon + (t.lon[loc] - sx[active]) + 180) % 360 - 180
                y = q.lat + (t.lat[loc] - sy[active])
                valid = t.valid[loc] & np.isfinite(x) & np.isfinite(y) & (y >= -90) & (y < 90)
                why[first + active[~valid]] = 1
                active = active[valid]
                x = x[valid]
                y = y[valid]
                if not len(active):
                    break
                inside = self.inside_domain(x, y)
                high = inside & self.land_points('high', x, y, inside)
                mid = inside & self.land_points('intermediate', x, y, inside)
                code = cells(x, y)
                reason = np.zeros(len(active), np.int16)
                registered = np.zeros(len(code), bool)
                in_bounds = (code >= 0) & (code < len(self.valid_states))
                registered[in_bounds] = self.valid_states[code[in_bounds]]
                reason[inside & ~registered] = 4
                reason[high & mid] = 2
                reason[high ^ mid] = 3
                xy = np.stack((np.column_stack((prevx[active], prevy[active])), np.column_stack((x, y))), axis=1)
                lines = sh.linestrings(xy)
                high = self.land_intersects('high_D', lines)
                mid = self.land_intersects('intermediate_D', lines)
                reason[high & mid] = 6
                reason[high ^ mid] = 10
                failed = reason > 0
                why[first + active[failed]] = reason[failed]
                exited = ~failed & ~inside
                out[first + active[exited]] = EXIT
                remain = ~failed & inside
                if step == 24 * q.horizon:
                    out[first + active[remain]] = code[remain]
                    active = np.array([], int)
                else:
                    prevx[active[remain]] = x[remain]
                    prevy[active[remain]] = y[remain]
                    active = active[remain]
        if not np.array_equal(out == FALLBACK, why > 0):
            raise AssertionError('Outcome/reason mismatch')
        return (out, why, profile)


class ProfiledG2(G2Kernel):
    __slots__=()
    def classify_context(self,*args,**kwargs):
        return self.timer.call('classify_context:residual',super().classify_context,*args,**kwargs)
    def rectangle_safe(self,*args,**kwargs):
        return self.timer.call('certificate:residual',super().rectangle_safe,*args,**kwargs)
