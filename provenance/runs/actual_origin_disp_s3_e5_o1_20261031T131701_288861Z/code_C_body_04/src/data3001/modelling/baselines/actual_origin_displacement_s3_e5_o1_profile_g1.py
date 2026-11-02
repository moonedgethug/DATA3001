"""Timing-only G1 copy; original expressions retain their order."""
from data3001.modelling.baselines.actual_origin_displacement_s3_e5_o1 import *
class ProfiledG1(G1Kernel):

    def context(self, donors, query, fitting_ids, source_identity):
        ids = frozenset(map(int, fitting_ids))
        g = self.geometry
        if query.id in ids or not set(map(int, donors.id)).issubset(ids):
            raise PermissionError('Whole-ID leakage in context')
        if not donors.horizon_days.eq(query.horizon).all() or not donors.origin_cell_1.isin(neighbours(query.origin)).all():
            raise ValueError('Context horizon or neighbour mismatch')
        if len(donors) and (not (self.timer.call('context:sh.intersects_xy:g.region', sh.intersects_xy, g.region, donors.lon, donors.lat).all() and self.timer.call('context:sh.intersects_xy:g.domain', sh.intersects_xy, g.domain, donors.lon, donors.lat).all())):
            raise ValueError('Unqualified original donor start')
        if not self.timer.call('context:np.array_equal', np.array_equal, self.timer.call('context:cells', cells, donors.lon.to_numpy(), donors.lat.to_numpy()), donors.origin_cell_1):
            raise ValueError('Donor origin/source mismatch')
        arrays = {}
        for name in donors.columns:
            if name == 'full_interval':
                a = donors[name].to_numpy(bool, copy=True)
            else:
                a = donors[name].to_numpy(copy=True)
            a.flags.writeable = False
            arrays[name] = a
        digest = hashlib.sha256(str((source_identity, query.horizon, query.origin, sorted(ids))).encode())
        for name in sorted(arrays):
            digest.update(name.encode())
            digest.update(arrays[name].tobytes())
        folds = frozenset(map(int, donors.fold)) if 'fold' in donors else frozenset()
        ctx = DonorContext(MappingProxyType(arrays), ids, folds, query.origin, query.horizon, digest.hexdigest(), self.context_owner)
        return ctx

    def inside_domain(self, x, y):
        if self.rectangular_domain:
            return (x >= -81) & (x <= -8) & (y >= 20) & (y <= 55)
        return self.timer.call('inside_domain:sh.intersects_xy:self.geometry.domain', sh.intersects_xy, self.geometry.domain, x, y)

    def rectangle_safe(self, xmin, xmax, ymin, ymax, possible):
        g = self.geometry
        ix = self.timer.call('rectangle_safe:np.flatnonzero', np.flatnonzero, possible)
        good = self.timer.call('rectangle_safe:np.zeros', np.zeros, len(possible), bool)
        if not len(ix):
            return good
        boxes = self.timer.call('rectangle_safe:sh.box:xmin[ix]', sh.box, xmin[ix], ymin[ix], xmax[ix], ymax[ix])
        inside = (xmin[ix] >= -81) & (xmax[ix] <= -8) & (ymin[ix] >= 20) & (ymax[ix] <= 55) if self.rectangular_domain else self.timer.call('rectangle_safe:sh.covers:g.domain', sh.covers, g.domain, boxes)
        water = inside & ~self.timer.call('rectangle_safe:sh.intersects:g.high', sh.intersects, g.high, boxes) & ~self.timer.call('rectangle_safe:sh.intersects:g.intermediate', sh.intersects, g.intermediate, boxes)
        x0 = self.timer.call('rectangle_safe:np.floor', np.floor, xmin[ix] + 180).astype(int)
        x1 = self.timer.call('rectangle_safe:np.floor', np.floor, xmax[ix] + 180).astype(int) + 1
        y0 = self.timer.call('rectangle_safe:np.floor', np.floor, ymin[ix] + 90).astype(int)
        y1 = self.timer.call('rectangle_safe:np.floor', np.floor, ymax[ix] + 90).astype(int) + 1
        p = self.state_prefix
        n = p[y1, x1] - p[y0, x1] - p[y1, x0] + p[y0, x0]
        good[ix] = water & (n == (x1 - x0) * (y1 - y0))
        return good

    def certificates_context(self, q, c, sl):
        sx, sy = (c.lon[sl], c.lat[sl])
        xmin = q.lon + (c.x_min[sl] - sx)
        xmax = q.lon + (c.x_max[sl] - sx)
        ymin = q.lat + (c.y_min[sl] - sy)
        ymax = q.lat + (c.y_max[sl] - sy)
        possible = c.full_interval[sl] & (xmin >= -180) & (xmax < 180) & (ymin >= -90) & (ymax < 90)
        xmin = (xmin + 180) % 360 - 180
        xmax = (xmax + 180) % 360 - 180
        xmin -= 1e-10
        xmax += 1e-10
        ymin -= 1e-10
        ymax += 1e-10
        possible &= (xmin >= -180) & (xmax < 180) & (xmin <= xmax) & (ymin >= -90) & (ymax < 90)
        return self.rectangle_safe(xmin, xmax, ymin, ymax, possible)

    def classify_context(self, q, c, *, check=lambda: None, certificates=True):
        if c.owner is not self.context_owner:
            raise ValueError('Stale or foreign kernel context')
        if q.id in c.fitting_ids or q.fold in c.donor_folds:
            raise PermissionError('Query ID/fold in donors')
        if q.horizon != c.horizon or q.origin != c.origin:
            raise ValueError('Wrong context role')
        n = len(c)
        out = self.timer.call('classify_context:np.full', np.full, n, FALLBACK, np.int64)
        why = self.timer.call('classify_context:np.zeros', np.zeros, n, np.int16)
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
            cert = self.certificates_context(q, c, sl) if certificates else self.timer.call('classify_context:np.zeros', np.zeros, size, bool)
            ci = self.timer.call('classify_context:np.flatnonzero', np.flatnonzero, cert)
            sx = c.lon[sl]
            sy = c.lat[sl]
            if len(ci):
                ex = (q.lon + (c.end_lon[sl][ci] - sx[ci]) + 180) % 360 - 180
                ey = q.lat + (c.end_lat[sl][ci] - sy[ci])
                out[first + ci] = self.timer.call('classify_context:cells', cells, ex, ey)
            profile['certified'] += int(cert.sum())
            active = self.timer.call('classify_context:np.flatnonzero', np.flatnonzero, ~cert)
            profile['literal_pairs'] += len(active)
            starts = c.start[sl].astype(int, copy=False)
            ends = c.track_end[sl].astype(int, copy=False)
            epochs = c.epoch[sl]
            prevx = self.timer.call('classify_context:np.full', np.full, size, q.lon)
            prevy = self.timer.call('classify_context:np.full', np.full, size, q.lat)
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
                valid = t.valid[loc] & self.timer.call('classify_context:np.isfinite', np.isfinite, x) & self.timer.call('classify_context:np.isfinite', np.isfinite, y) & (y >= -90) & (y < 90)
                why[first + active[~valid]] = 1
                active = active[valid]
                x = x[valid]
                y = y[valid]
                if not len(active):
                    break
                inside = self.inside_domain(x, y)
                high = inside & self.timer.call('classify_context:sh.intersects_xy:g.high', sh.intersects_xy, g.high, x, y)
                mid = inside & self.timer.call('classify_context:sh.intersects_xy:g.intermediate', sh.intersects_xy, g.intermediate, x, y)
                code = self.timer.call('classify_context:cells', cells, x, y)
                reason = self.timer.call('classify_context:np.zeros', np.zeros, len(active), np.int16)
                registered = self.timer.call('classify_context:np.zeros', np.zeros, len(code), bool)
                in_bounds = (code >= 0) & (code < len(self.valid_states))
                registered[in_bounds] = self.valid_states[code[in_bounds]]
                reason[inside & ~registered] = 4
                reason[high & mid] = 2
                reason[high ^ mid] = 3
                xy = self.timer.call('classify_context:np.stack', np.stack, (self.timer.call('classify_context:np.column_stack', np.column_stack, (prevx[active], prevy[active])), self.timer.call('classify_context:np.column_stack', np.column_stack, (x, y))), axis=1)
                lines = self.timer.call('classify_context:sh.linestrings:xy', sh.linestrings, xy)
                high = self.timer.call('classify_context:sh.intersects:g.high_D', sh.intersects, g.high_D, lines)
                mid = self.timer.call('classify_context:sh.intersects:g.intermediate_D', sh.intersects, g.intermediate_D, lines)
                reason[high & mid] = 6
                reason[high ^ mid] = 10
                failed = reason > 0
                why[first + active[failed]] = reason[failed]
                exited = ~failed & ~inside
                out[first + active[exited]] = EXIT
                remain = ~failed & inside
                if step == 24 * q.horizon:
                    out[first + active[remain]] = code[remain]
                    active = self.timer.call('classify_context:np.array', np.array, [], int)
                else:
                    prevx[active[remain]] = x[remain]
                    prevy[active[remain]] = y[remain]
                    active = active[remain]
        if not self.timer.call('classify_context:np.array_equal', np.array_equal, out == FALLBACK, why > 0):
            raise AssertionError('Outcome/reason mismatch')
        return (out, why, profile)
