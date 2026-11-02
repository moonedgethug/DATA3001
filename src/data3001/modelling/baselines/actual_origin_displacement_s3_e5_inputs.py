"""E5 exact actual-origin transfers and development-only prepared-input views."""
from dataclasses import dataclass
import json
import time

import numpy as np
import pandas as pd
from scipy.ndimage import minimum_filter1d, maximum_filter1d
import shapely as sh

from data3001.paths import file_sha256
from data3001.preprocessing.prep_core import cells
from data3001.modelling.common.qualified_count_inputs import (
    read_frame, verify_file, counts_from_labels, KEYS, EXIT,
)
from data3001.modelling.baselines.spatial_borrowing_s3_e1_inputs import (
    Geometry, neighbours, original_integrity, FALLBACK, REASONS,
)

E5_REASONS = {**REASONS, 11: 'unsafe_query_geometry'}


@dataclass(frozen=True)
class Query:
    id: int
    source_obs: int
    horizon: int
    origin: int
    lon: float
    lat: float
    epoch: float
    fold: int


@dataclass
class TrackArrays:
    lon: np.ndarray
    lat: np.ndarray
    time: np.ndarray
    valid: np.ndarray


def prepared_allowlist(paths, config):
    root = paths._resolve(config['prepared_input'])
    return [paths.root/'provenance/runs'/root.name/'outputs.json',
            *sorted((root/'paths').glob('*.parquet')),
            *sorted((root/'labels').glob('*.parquet'))]


def load_prepared(paths, config, counts, folds, geometry, inventory, check=lambda: None):
    """Reconcile every source-keyed pair without opening canonical trajectories."""
    root = paths._resolve(config['prepared_input'])
    receipt_path = paths.root/'provenance/runs'/root.name/'outputs.json'
    receipt = json.loads(receipt_path.read_text())
    if receipt.get('completed') is not True or receipt.get('final_test_access') is not False:
        raise ValueError('Unsealed or non-development prepared input')
    inventory[str(receipt_path.relative_to(paths.root))] = file_sha256(receipt_path)
    expected = set(map(int, counts.id))
    label_paths = sorted((root/'labels').glob('*.parquet'))
    if {int(p.stem) for p in label_paths} != expected:
        raise ValueError('Prepared source ID inventory mismatch')
    fold_lookup = folds.set_index('id').outer_fold.to_dict()
    tables, coordinates, rebuilt = [], [], []
    offset = 0
    for label_path in label_paths:
        check()
        ident = int(label_path.stem)
        path = root/'paths'/label_path.name
        for p in (path, label_path):
            verify_file(paths, p, receipt['output_sha256'], inventory)
        f, labels = read_frame(path), read_frame(label_path)
        if not f.id.eq(ident).all() or not labels.id.eq(ident).all():
            raise ValueError('Wrong ID in prepared file')
        if not labels.reason_code.eq(0).all():
            raise ValueError('Unqualified donor in prepared input')
        original_integrity(f, labels)
        rebuilt.append(counts_from_labels(labels))
        o = pd.Index(f.source_obs).get_indexer(labels.origin_source_obs)
        x, y = f.lon.to_numpy(float), f.lat.to_numpy(float)
        t = f.time.to_numpy(float)
        valid = f.position_ok.to_numpy(bool)
        if not (sh.intersects_xy(geometry.region, x[o], y[o]).all()
                and sh.intersects_xy(geometry.domain, x[o], y[o]).all()
                and f.in_R.to_numpy(bool)[o].all()
                and np.array_equal(cells(x[o], y[o]), labels.origin_cell_1)):
            raise ValueError('Original donor/query start is not the qualified R start')
        table = labels[['id','origin_source_obs','horizon_days','origin_cell_1',
                        'target_epoch','destination_cell_1']].copy()
        table['lon'], table['lat'], table['epoch'] = x[o], y[o], t[o]
        table['start'], table['track_end'], table['fold'] = offset+o, offset+len(f), fold_lookup[ident]
        # Forward bounds certify only complete, gap-free, valid intervals.
        bad = np.r_[0, np.cumsum(~valid | ~np.isfinite(x) | ~np.isfinite(y))]
        gap = np.r_[0, np.cumsum(np.r_[False, np.diff(t) != 3600])]
        for h in (7,30):
            loc = np.flatnonzero(labels.horizon_days.to_numpy() == h)
            st = o[loc]; en = st+24*h
            clipped = np.minimum(en, len(f)-1)
            full = ((en < len(f)) & (t[clipped] == t[st]+24*h*3600)
                    & ((bad[clipped+1]-bad[st]) == 0)
                    & ((gap[clipped+1]-gap[st+1]) == 0))
            table.loc[table.index[loc], 'full_interval'] = full
            for name, values in [('x',x), ('y',y)]:
                for kind, filt, cval in [('min',minimum_filter1d,np.inf),
                                         ('max',maximum_filter1d,-np.inf)]:
                    bound = filt(values, size=24*h+1, origin=-12*h,
                                 mode='constant', cval=cval)
                    table.loc[table.index[loc], name+'_'+kind] = bound[st]
            table.loc[table.index[loc], 'end_lon'] = x[clipped]
            table.loc[table.index[loc], 'end_lat'] = y[clipped]
        tables.append(table)
        coordinates.append((x,y,t,valid))
        offset += len(f)
    actual = pd.concat(rebuilt, ignore_index=True).sort_values(KEYS).reset_index(drop=True)
    pd.testing.assert_frame_equal(counts.sort_values(KEYS).reset_index(drop=True), actual,
                                  check_dtype=False, check_exact=True)
    donors = pd.concat(tables, ignore_index=True)
    donors['full_interval'] = donors.full_interval.astype(bool)
    tracks = TrackArrays(*(np.concatenate([r[k] for r in coordinates]) for k in range(4)))
    # This view deliberately contains no destination or future coordinates.
    queries = donors[['id','origin_source_obs','horizon_days','origin_cell_1',
                      'lon','lat','epoch','fold']].copy()
    return tracks, donors, queries


def as_query(row):
    return Query(int(row.id),int(row.origin_source_obs),int(row.horizon_days),
                 int(row.origin_cell_1),float(row.lon),float(row.lat),
                 float(row.epoch),int(row.fold))


class ActualOriginKernel:
    """Exact rectangle certificates plus batched chronological hourly checks."""
    def __init__(self, geometry, tracks):
        self.geometry, self.tracks = geometry, tracks
        valid = np.zeros((180,360),dtype=np.int32)
        for cell in geometry.states:
            if 0 <= cell < 64800:
                valid[cell//360,cell%360] = 1
        self.state_prefix = np.pad(np.cumsum(np.cumsum(valid,axis=0),axis=1),((1,0),(1,0)))

    def query_safe(self, query):
        g = self.geometry
        if (not np.isfinite([query.lon,query.lat]).all() or
            not -180 <= query.lon < 180 or not -90 <= query.lat < 90 or
            int(cells(np.array([query.lon]),np.array([query.lat]))[0]) != query.origin or query.origin not in g.states or
            not sh.intersects_xy(g.region,query.lon,query.lat) or
            not sh.intersects_xy(g.domain,query.lon,query.lat)):
            raise ValueError('Invalid actual prediction-time coordinate')
        return not (sh.intersects_xy(g.high,query.lon,query.lat) or
                    sh.intersects_xy(g.intermediate,query.lon,query.lat))

    def certificates(self, query, donors):
        """A fully valid path inside a water/state rectangle needs no hourly checks."""
        g = self.geometry
        sx,sy=donors.lon.to_numpy(),donors.lat.to_numpy()
        xmin,xmax = query.lon+(donors.x_min.to_numpy()-sx),query.lon+(donors.x_max.to_numpy()-sx)
        ymin,ymax = query.lat+(donors.y_min.to_numpy()-sy),query.lat+(donors.y_max.to_numpy()-sy)
        possible = (donors.full_interval.to_numpy(bool) & (xmin >= -180) & (xmax < 180)
                    & (ymin >= -90) & (ymax < 90))
        xmin=(xmin+180)%360-180;xmax=(xmax+180)%360-180
        # Outward-only certificate padding is conservative, not trajectory rounding.
        xmin-=1e-10;xmax+=1e-10;ymin-=1e-10;ymax+=1e-10
        possible &= (xmin>=-180)&(xmax<180)&(xmin<=xmax)&(ymin>=-90)&(ymax<90)
        ix = np.flatnonzero(possible)
        good = np.zeros(len(donors),dtype=bool)
        if not len(ix): return good
        boxes = sh.box(xmin[ix],ymin[ix],xmax[ix],ymax[ix])
        water = (sh.covers(g.domain,boxes) & ~sh.intersects(g.high,boxes)
                 & ~sh.intersects(g.intermediate,boxes))
        # Every grid cell touched by the rectangle must be a registered state.
        x0=np.floor(xmin[ix]+180).astype(int); x1=np.floor(xmax[ix]+180).astype(int)+1
        y0=np.floor(ymin[ix]+90).astype(int); y1=np.floor(ymax[ix]+90).astype(int)+1
        p=self.state_prefix
        number=p[y1,x1]-p[y0,x1]-p[y1,x0]+p[y0,x0]
        good[ix] = water & (number == (x1-x0)*(y1-y0))
        return good

    def classify(self, query, donors, fitting_ids, *, certificates=True, check=lambda: None):
        """Predict using one query start and only fitting donor paths; no query truth."""
        fitting_ids=set(map(int,fitting_ids))
        if query.id in fitting_ids or not set(map(int,donors.id)).issubset(fitting_ids):
            raise PermissionError('Whole-ID leakage in displacement donor role')
        if (not donors.horizon_days.eq(query.horizon).all() or
            not donors.origin_cell_1.isin(neighbours(query.origin)).all()):
            raise ValueError('Wrong horizon or non-neighbour donor')
        if len(donors) and not (sh.intersects_xy(self.geometry.region,donors.lon,donors.lat).all()
                               and sh.intersects_xy(self.geometry.domain,donors.lon,donors.lat).all()):
            raise ValueError('Original donor outside permitted R/D')
        n=len(donors);out=np.full(n,FALLBACK,dtype=np.int64);why=np.zeros(n,dtype=np.int16)
        profile=dict(donors=n,certified=0,literal_pairs=0,hourly_steps=0)
        if not self.query_safe(query):
            why[:]=11
            return out,why,profile
        if not n: return out,why,profile
        g,t=self.geometry,self.tracks
        for first in range(0,n,2048):
            check();last=min(first+2048,n);part=donors.iloc[first:last]
            cert=self.certificates(query,part) if certificates else np.zeros(len(part),dtype=bool)
            ci=np.flatnonzero(cert)
            sx=part.lon.to_numpy();sy=part.lat.to_numpy()
            if len(ci):
                ex=(query.lon+(part.end_lon.to_numpy()[ci]-sx[ci])+180)%360-180
                ey=query.lat+(part.end_lat.to_numpy()[ci]-sy[ci])
                out[first+ci]=cells(ex,ey)
            profile['certified']+=int(cert.sum())
            active=np.flatnonzero(~cert);profile['literal_pairs']+=len(active)
            starts=part.start.to_numpy(int);ends=part.track_end.to_numpy(int)
            epochs=part.epoch.to_numpy(float)
            prevx=np.full(len(part),query.lon);prevy=np.full(len(part),query.lat)
            for step in range(1,24*query.horizon+1):
                if not len(active):break
                if step%16==0:check()
                profile['hourly_steps']+=len(active)
                loc=starts[active]+step
                present=loc<ends[active]
                why[first+active[~present]]=7
                active=active[present];loc=loc[present]
                if not len(active):break
                timed=t.time[loc]==epochs[active]+3600*step
                why[first+active[~timed]]=5
                active=active[timed];loc=loc[timed]
                if not len(active):break
                x=(query.lon+(t.lon[loc]-sx[active])+180)%360-180;y=query.lat+(t.lat[loc]-sy[active])
                valid=t.valid[loc]&np.isfinite(x)&np.isfinite(y)&(y>=-90)&(y<90)
                why[first+active[~valid]]=1
                active=active[valid];x=x[valid];y=y[valid]
                if not len(active):break
                inside=sh.intersects_xy(g.domain,x,y)
                high=inside&sh.intersects_xy(g.high,x,y)
                mid=inside&sh.intersects_xy(g.intermediate,x,y)
                code=cells(x,y);reason=np.zeros(len(active),dtype=np.int16)
                reason[inside&~np.isin(code,list(g.states))]=4
                reason[high&mid]=2;reason[high^mid]=3
                xy=np.stack((np.column_stack((prevx[active],prevy[active])),
                             np.column_stack((x,y))),axis=1)
                lines=sh.linestrings(xy)
                high=sh.intersects(g.high_D,lines);mid=sh.intersects(g.intermediate_D,lines)
                reason[high&mid]=6;reason[high^mid]=10
                failed=reason>0;why[first+active[failed]]=reason[failed]
                exited=~failed&~inside;out[first+active[exited]]=EXIT
                remain=~failed&inside
                if step==24*query.horizon:
                    out[first+active[remain]]=code[remain]
                    active=np.array([],dtype=int)
                else:
                    prevx[active[remain]]=x[remain];prevy[active[remain]]=y[remain]
                    active=active[remain]
        if not np.array_equal(out==FALLBACK,why>0):
            raise AssertionError('Transfer outcome/reason mismatch')
        return out,why,profile


def reference_distribution(outcomes, b2, states):
    """Retain every donor, returning each failed vote to the supported B2 row."""
    p=np.asarray(b2,float);states=np.asarray(states,int)
    if not len(outcomes):return p.copy(),1.
    failure=float(np.mean(outcomes==FALLBACK));v=np.zeros(len(p));index={s:k for k,s in enumerate(states)}
    for dest,n in zip(*np.unique(outcomes[outcomes!=FALLBACK],return_counts=True)):
        if dest not in index:raise ValueError('Unregistered successful destination')
        v[index[dest]]=n/len(outcomes)
    q=v+failure*p
    if not np.isclose(q.sum(),1,atol=1e-12,rtol=0):raise AssertionError('Lost donor probability mass')
    return q,failure
