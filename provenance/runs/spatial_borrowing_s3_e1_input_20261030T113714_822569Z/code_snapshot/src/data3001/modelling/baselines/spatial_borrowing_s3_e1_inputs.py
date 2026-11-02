"""Approved S3 grid-path transfer; deterministic events and guarded preparation."""
from dataclasses import dataclass
from datetime import datetime, timezone
import argparse
import hashlib
import json
import resource
import signal
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod
import shapely as sh
from shapely.geometry import shape

from data3001.paths import project_paths, file_sha256
from data3001.dataset import manifest, track_path
from data3001.feature_pruning import qualification_arrays
from data3001.preprocessing.prep_core import cells, next_index
from data3001.modelling.common.runtime import save_frame, save_json, _seal, verified_run
from data3001.modelling.common.qualified_count_inputs import ExperimentGuard, load_inputs, read_frame, EXIT

FALLBACK = -3
REASONS = {0: 'resolved', 1: 'source_position', 2: 'land_point', 3: 'mask_disagreement',
           4: 'unindexed_state', 5: 'missing_hour', 6: 'land_segment',
           7: 'missing_continuation', 8: 'start_outside_R_D', 9: 'wrong_start_cell',
           10: 'segment_mask_disagreement'}
OFFSETS = tuple((dx, dy) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if dx or dy)
GEOD = Geod(ellps='WGS84')


def translated_cell(cell, dx, dy):
    y, x = divmod(int(cell), 360)
    return (y+dy)*360 + (x+dx) % 360 if 0 <= y+dy < 180 else -1


def neighbours(cell):
    return tuple(sorted(c for dx, dy in OFFSETS if (c := translated_cell(cell, dx, dy)) >= 0))


@dataclass
class Geometry:
    region: object
    domain: object
    high: object
    intermediate: object
    states: set

    def __post_init__(self):
        self.high_D = sh.intersection(self.high, self.domain)
        self.intermediate_D = sh.intersection(self.intermediate, self.domain)
        for g in (self.region, self.domain, self.high, self.intermediate, self.high_D, self.intermediate_D):
            sh.prepare(g)

    @classmethod
    def load(cls, paths, states):
        poly = lambda key: shape(json.loads(paths.asset(key, verify=True).read_text())['features'][0]['geometry'])
        return cls(poly('release_R'), poly('transport_D'),
                   sh.from_wkb(paths.asset('land_mask_high', verify=True).read_bytes()),
                   sh.from_wkb(paths.asset('land_mask_intermediate', verify=True).read_bytes()), set(map(int, states)))

    def events(self, frame, dx, dy):
        """One outgoing-window event index per fixed spatial offset; no path sampling."""
        x = (frame.lon.to_numpy(float)+dx+180) % 360-180
        y = frame.lat.to_numpy(float)+dy
        t = frame.time.to_numpy(float)
        valid = frame.position_ok.to_numpy(bool) & np.isfinite(x) & np.isfinite(y) & (y >= -90) & (y < 90)
        inside = valid & sh.intersects_xy(self.domain, x, y)
        in_R = valid & sh.intersects_xy(self.region, x, y)
        high = inside & sh.intersects_xy(self.high, x, y)
        mid = inside & sh.intersects_xy(self.intermediate, x, y)
        codes = cells(x, y)
        reason = np.zeros(len(frame), dtype=np.int16)
        reason[inside & ~np.isin(codes, list(self.states))] = 4
        reason[high & mid] = 2
        reason[high ^ mid] = 3
        reason[~valid] = 1
        event_reason = reason.copy()
        event_time = t.copy()
        # Invalid coordinate pairs are handled by source-position events, never geometry.
        usable = valid[:-1] & valid[1:] & (np.diff(t) == 3600)
        ix = np.flatnonzero(usable)+1
        segment_reason = np.zeros(len(frame), dtype=np.int16)
        for chunk in range(0, len(ix), 8192):
            loc = ix[chunk:chunk+8192]
            xy = np.stack([np.column_stack((x[loc-1],y[loc-1])), np.column_stack((x[loc],y[loc]))],axis=1)
            lines = sh.linestrings(xy)
            # intersect(line, land intersect D) equals clipping the line to D first.
            h = sh.intersects(self.high_D, lines)
            m = sh.intersects(self.intermediate_D, lines)
            segment_reason[loc[h & m]] = 6
            segment_reason[loc[h ^ m]] = 10
        event_reason[segment_reason > 0] = segment_reason[segment_reason > 0]
        gap = np.r_[False, np.diff(t) != 3600]
        event_reason[gap] = 5
        event_time[gap] = t[np.flatnonzero(gap)-1]+3600
        exit_point = valid & ~inside & (event_reason == 0)
        event = (event_reason > 0) | exit_point
        return dict(x=x,y=y,t=t,codes=codes,valid=valid,inside=inside,in_R=in_R,
                    point_reason=reason,event_reason=event_reason,event_time=event_time,
                    exit_point=exit_point,next_event=next_index(event),segment_reason=segment_reason)


def classify_windows(frame, labels, target_cells, events):
    """Classify windows with next-event queries; incoming edges at start are excluded."""
    n = len(frame)
    lookup = pd.Index(frame.source_obs)
    origins = lookup.get_indexer(labels.origin_source_obs)
    if (origins < 0).any():
        raise ValueError('Missing original qualified source key')
    target_cells = np.asarray(target_cells, dtype=np.int64)
    target_time = labels.target_epoch.to_numpy(float)
    out = np.full(len(labels), FALLBACK, dtype=np.int64)
    why = np.zeros(len(labels), dtype=np.int16)
    start = origins
    why[~events['in_R'][start] | ~events['inside'][start]] = 8
    why[events['codes'][start] != target_cells] = 9
    badstart = events['point_reason'][start] > 0
    why[badstart] = events['point_reason'][start][badstart]
    eidx = np.r_[events['next_event'],n][np.minimum(start+1,n)]
    et = np.r_[events['event_time'],np.inf][eidx]
    active = why == 0
    hit = active & (et <= target_time)
    er = np.r_[events['event_reason'],0][eidx]
    why[hit] = er[hit]
    out[hit & (er == 0)] = EXIT
    end = np.searchsorted(events['t'], target_time)
    exists = (end < n) & (events['t'][np.minimum(end,n-1)] == target_time)
    complete = active & ~hit & exists
    out[complete] = events['codes'][end[complete]]
    why[active & ~hit & ~exists] = 7
    decision = np.where(hit,et,np.where(complete,target_time,events['t'][start]))
    return out, why, origins, end, decision


def union_view(frame, labels):
    """Minimal union of observed coordinate windows, retaining genuine gaps."""
    t = frame.time.to_numpy(float)
    if not np.isfinite(t).all() or (np.diff(t) <= 0).any():
        raise ValueError('Analytical track timestamps are not strictly increasing')
    starts = pd.Index(frame.source_obs).get_indexer(labels.origin_source_obs)
    if (starts < 0).any():
        raise ValueError('Qualified origin absent from analytical track')
    ends = np.searchsorted(t, labels.target_epoch.to_numpy(float), side='right')
    delta = np.zeros(len(t)+1,dtype=np.int64)
    np.add.at(delta,starts,1); np.add.at(delta,ends,-1)
    return frame.loc[np.cumsum(delta[:-1])>0].reset_index(drop=True)


def original_integrity(frame, labels):
    t=frame.time.to_numpy(float); keys=pd.Index(frame.source_obs)
    o=keys.get_indexer(labels.origin_source_obs)
    if (o<0).any(): raise ValueError('Source origin absent')
    expected=labels.target_epoch.to_numpy(float)-labels.horizon_days.to_numpy()*86400
    if not np.array_equal(t[o],expected): raise ValueError('Origin timestamp/qualification mismatch')
    required=labels.required_interval_end_epoch.to_numpy(float)
    j=np.searchsorted(t,required)
    if (j>=len(t)).any() or not np.array_equal(t[j],required): raise ValueError('Missing originally required path endpoint')
    bad=~frame.position_ok.to_numpy(bool)|~frame.mapping_ok.to_numpy(bool)
    prefix=np.r_[0,np.cumsum(bad)]
    gaps=np.r_[0,np.cumsum(np.r_[False,np.diff(t)!=3600])]
    if np.any(prefix[j+1]-prefix[o]) or np.any(gaps[j+1]-gaps[o+1]):
        raise ValueError('Frozen qualified required path contradicts canonical evidence')
    actual_end=keys.get_indexer(labels.endpoint_source_obs)
    inside=~labels.outside.to_numpy(bool)
    if (actual_end[inside]<0).any(): raise ValueError('Qualified physical endpoint absent')
    if not np.array_equal(cells(frame.lon.to_numpy()[actual_end[inside]],frame.lat.to_numpy()[actual_end[inside]]),labels.loc[inside,'destination_cell_1'].to_numpy()):
        raise ValueError('Observed endpoint no longer matches frozen state')


def make_transfers(frame, labels, geometry, origins):
    tables=[]
    origins=set(map(int,origins))
    for dx,dy in OFFSETS:
        target=np.array([translated_cell(c,dx,dy) for c in labels.origin_cell_1],dtype=np.int64)
        keep=np.isin(target,list(origins))
        if not keep.any(): continue
        local=labels.loc[keep].reset_index(drop=True); target=target[keep]
        events=geometry.events(frame,dx,dy)
        dest,why,start,end,when=classify_windows(frame,local,target,events)
        rows=pd.DataFrame(dict(id=local.id,horizon_days=local.horizon_days,
            donor_cell_1=local.origin_cell_1,origin_cell_1=target,
            origin_source_obs=local.origin_source_obs,original_destination_cell_1=local.destination_cell_1,
            destination_cell_1=dest,reason_code=why,dx=dx,dy=dy,decision_epoch=when))
        rows['distance_change_m']=np.nan; rows['azimuth_change_deg']=np.nan; rows['zero_distance']=False
        resolved=np.flatnonzero(dest>=0)
        if len(resolved):
            st=start[resolved]; en=end[resolved]
            az,_,dist=GEOD.inv(frame.lon.to_numpy()[st],frame.lat.to_numpy()[st],frame.lon.to_numpy()[en],frame.lat.to_numpy()[en])
            a2,_,d2=GEOD.inv(events['x'][st],events['y'][st],events['x'][en],events['y'][en])
            rows.loc[resolved,'distance_change_m']=np.asarray(d2)-np.asarray(dist)
            rows.loc[resolved,'zero_distance']=np.asarray(dist)==0
            rows.loc[resolved,'azimuth_change_deg']=np.where(np.asarray(dist)>0,(np.asarray(a2)-np.asarray(az)+180)%360-180,np.nan)
        tables.append(rows)
    if not tables: return pd.DataFrame()
    return pd.concat(tables,ignore_index=True)


def base_allowlist(paths, config):
    counts=paths._resolve(config['counts_path']); folds=paths._resolve(config['folds_path'])
    allowed=[counts,folds,counts.parent/'source_ID_summary.csv',*sorted((counts.parent/'release_labels').glob('*.parquet'))]
    for p in (counts,folds): allowed += [paths.root/'provenance/runs'/p.parent.name/n for n in ('outputs.json','run.json')]
    allowed += [paths.asset(k) for k in config['source_assets']]
    return allowed


def source_hashes(paths):
    files={Path(m.__file__).resolve() for k,m in list(sys.modules.items()) if k.startswith('data3001') and getattr(m,'__file__',None) and str(m.__file__).endswith('.py')}
    # Python -m loads the command entry point as __main__, outside the package prefix.
    entry=getattr(sys.modules.get('__main__'),'__file__',None)
    if entry and Path(entry).is_file() and Path(entry).resolve().is_relative_to(paths.root/'src/data3001'):
        files.add(Path(entry).resolve())
    files.add(Path(__file__).resolve())
    return {p.relative_to(paths.root).as_posix():file_sha256(p) for p in sorted(files)}


def budget_check(run, config, start, cap):
    rss=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    if rss>config['max_rss_bytes']: raise MemoryError('Approved 8 GiB RSS limit exceeded')
    size=sum(p.stat().st_size for d in run.values() for p in d.rglob('*') if p.is_file())
    if size>config['max_new_artifact_bytes']: raise RuntimeError('Approved artifact size limit exceeded')
    if time.monotonic()-start>cap: raise TimeoutError('Approved compute cap exceeded')
    return rss,size


def prepare(paths,config,run_id,preflight=False,pilot_run=None):
    start=time.monotonic(); cap=config['preflight_cap_seconds'] if preflight else config['preparation_cap_seconds']
    if file_sha256(paths._resolve(config['approved_plan']))!=config['approved_plan_sha256']: raise ValueError('Approved plan hash mismatch')
    current=manifest(); qpath=paths.asset('current_qualification_manifest',verify=True)
    qual=json.loads(qpath.read_text())
    labels_root=paths._resolve(config['counts_path']).parent/'release_labels'
    labels={}
    for p in sorted(labels_root.glob('*.parquet')):
        f=read_frame(p); f=f[f.reason_code.eq(0)&f.horizon_days.isin([7,30])].copy()
        if len(f): labels[int(p.stem)]=f
    ids=sorted(labels)
    if any(current['records'][str(i)]['pool']!='train' for i in ids): raise PermissionError('Non-development input')
    allowed=base_allowlist(paths,config)+[qpath]
    for i in ids:
        allowed += [paths.root/current['records'][str(i)]['path'],paths.root/qual['records'][str(i)]['path']]
    run=paths.create_run(run_id,{**config,'mode':'preparation_pilot' if preflight else 'preparation'})
    guard=ExperimentGuard(paths,run,allowed); sys.addaudithook(guard)
    try:
        counts,folds,origin_index,destinations,reasons,inventory=load_inputs(paths,config)
        inventory[qpath.relative_to(paths.root).as_posix()]=file_sha256(qpath)
        geometry=Geometry.load(paths,destinations.cell)
        code=source_hashes(paths)
        if not preflight:
            if not pilot_run: raise ValueError('Approved-budget pilot required')
            guard.input_files.update(p.resolve() for d in ('results','provenance') for p in (paths.root/d/'runs'/pilot_run).rglob('*') if p.is_file())
            prior=paths.root/'provenance/runs'/pilot_run
            rec=json.loads((prior/'verification.json').read_text())
            if not rec['preflight_only'] or rec['projected_preparation_seconds']>=cap: raise ValueError('Pilot exceeds cap')
            if json.loads((prior/'source_sha256.json').read_text())!=code: raise ValueError('Preparation code changed since pilot')
            verified_run(paths,pilot_run)
        selected=ids
        if preflight:
            train=set(folds.loc[~folds.outer_fold.isin([0,1]),'id'])
            ranked=sorted((i for i in ids if i in train),key=lambda i:(-len(labels[i]),i))
            coastal=set(int(c) for c in origin_index.cell if sh.intersects(geometry.high,sh.box(c%360-180,c//360-90,c%360-179,c//360-89)))
            coast=sorted((i for i in ranked if labels[i].origin_cell_1.isin(coastal).any()),key=lambda i:(-int(labels[i].origin_cell_1.isin(coastal).sum()),i))
            selected=list(dict.fromkeys([ranked[0],coast[0] if coast else ranked[-1]]))
            if len(selected)==1 and len(ranked)>1: selected.append(ranked[1])
        summaries=[]; grouped=[]; samples=[]; load_seconds=0.; geometry_seconds=0.; raw_rows=0; window_rows=0; observed_offsets=set()
        for num,ident in enumerate(selected,1):
            tick=time.monotonic(); p=track_path(ident,allow_test=False)
            with p.open('rb') as stream: frame=pd.read_parquet(stream,columns=['id','source_obs','time','lon_normalized','lat'])
            raw_rows+=len(frame)
            frame.attrs['data3001']={'pool':'train'}
            flags=qualification_arrays(ident,frame,['analytical_row','position_ok','mapping_ok','in_R'],allow_test=False)
            frame=frame.assign(**flags).loc[flags['analytical_row']].rename(columns={'lon_normalized':'lon'}).reset_index(drop=True)
            frame=union_view(frame,labels[ident]); window_rows+=len(frame)
            original_integrity(frame,labels[ident]); load_seconds+=time.monotonic()-tick
            tick=time.monotonic(); transfers=make_transfers(frame,labels[ident],geometry,origin_index.cell)
            geometry_seconds+=time.monotonic()-tick
            inventory[p.relative_to(paths.root).as_posix()]=file_sha256(p)
            if inventory[p.relative_to(paths.root).as_posix()]!=current['records'][str(ident)]['sha256']: raise ValueError('Canonical track changed')
            qp=paths.root/qual['records'][str(ident)]['path']; inventory[qp.relative_to(paths.root).as_posix()]=file_sha256(qp)
            if inventory[qp.relative_to(paths.root).as_posix()]!=qual['records'][str(ident)]['sha256']: raise ValueError('Qualification sidecar changed')
            save_frame(paths,run['results']/'paths'/f'{ident}.parquet',frame)
            save_frame(paths,run['results']/'labels'/f'{ident}.parquet',labels[ident])
            if len(transfers):
                observed_offsets.update(zip(transfers.dx.astype(int),transfers.dy.astype(int)))
                save_frame(paths,run['results']/'transfers'/f'{ident}.parquet',transfers)
                group=transfers.groupby(['id','horizon_days','origin_cell_1','donor_cell_1','destination_cell_1','reason_code'],as_index=False).size().rename(columns={'size':'pair_count'})
                grouped.append(group)
                samples.append(transfers.sort_values(['horizon_days','origin_source_obs','origin_cell_1']).groupby(['horizon_days','reason_code'],sort=True).head(2))
                for h,g in transfers.groupby('horizon_days'):
                    good=g[g.destination_cell_1.ge(0)]
                    summaries.append(dict(id=ident,horizon_days=int(h),transfers=len(g),fallback=int(g.destination_cell_1.eq(FALLBACK).sum()),
                        distance_change_abs_sum_m=float(good.distance_change_m.abs().sum()),distance_change_abs_max_m=float(good.distance_change_m.abs().max()) if len(good) else 0.,
                        azimuth_change_abs_sum_deg=float(good.azimuth_change_deg.abs().sum()),azimuth_defined=int(good.azimuth_change_deg.notna().sum()),zero_distance=int(good.zero_distance.sum()),resolved_in_D=len(good)))
            budget_check(run,config,start,cap)
            if num%20==0 or preflight or num==len(selected): print(f'Prepared {num}/{len(selected)} IDs; {window_rows:,} unique window observations; {time.monotonic()-start:.1f}s',flush=True)
        total_raw=sum(current['records'][str(i)]['rows'] for i in ids)
        def hours(g):
            intervals=sorted(zip(g.target_epoch.to_numpy()-g.horizon_days.to_numpy()*86400,g.target_epoch.to_numpy()))
            total=0.; lo=hi=None
            for a,b in intervals:
                if lo is None: lo,hi=a,b
                elif a<=hi+3600: hi=max(hi,b)
                else: total+=(hi-lo)/3600+1; lo,hi=a,b
            return total+(hi-lo)/3600+1 if lo is not None else 0
        total_hours=sum(hours(g) for g in labels.values())
        projected=(load_seconds*total_raw/max(raw_rows,1)+geometry_seconds*total_hours/max(window_rows,1))*1.25+60
        rss,size=budget_check(run,config,start,cap)
        projected_size=size*total_hours/max(window_rows,1)
        if preflight and (projected>=config['preparation_cap_seconds'] or projected_size>config['max_new_artifact_bytes']):
            raise RuntimeError(f'Pilot budget gate: projected {projected:.1f}s, {projected_size/1024**3:.2f}GiB')
        if observed_offsets != set(OFFSETS): raise AssertionError('Preparation did not cover all eight offsets')
        all_counts=pd.concat(grouped,ignore_index=True)
        sample=pd.concat(samples,ignore_index=True).sort_values(['horizon_days','reason_code','id','origin_source_obs','origin_cell_1']).groupby(['horizon_days','reason_code']).head(3)
        save_frame(paths,run['results']/'transfer_counts_by_id.parquet',all_counts)
        save_frame(paths,run['results']/'transfer_diagnostics.csv',pd.DataFrame(summaries))
        save_frame(paths,run['results']/'audit_sample.csv',sample)
        save_frame(paths,run['results']/'counts_by_id.parquet',counts)
        save_frame(paths,run['results']/'folds.csv',folds)
        save_frame(paths,run['results']/'source_index.csv',origin_index)
        save_frame(paths,run['results']/'destination_cells.csv',destinations)
        save_json(paths,run['provenance']/'input_inventory.json',inventory)
        save_json(paths,run['provenance']/'source_sha256.json',code)
        for rel in code:
            paths.publish(run['provenance']/'code_snapshot'/rel,lambda out,rel=rel:out.write((paths.root/rel).read_bytes()))
        save_json(paths,run['results']/'config.json',config)
        for rel,digest in {**inventory,**code}.items():
            if file_sha256(paths.root/rel)!=digest: raise ValueError('Preparation input mutated')
        verification=dict(preflight_only=preflight,projected_preparation_seconds=projected,projected_artifact_bytes=projected_size,
            elapsed_seconds=time.monotonic()-start,raw_rows=raw_rows,unique_window_observations=window_rows,load_seconds=load_seconds,geometry_seconds=geometry_seconds,
            canonical_ids_read=sorted(guard.read_ids),final_test_trajectories_read=0,max_rss_bytes=rss,artifact_bytes=size,
            all_eight_offsets=sorted(observed_offsets),
            qualified_IDs=len(ids),prepared_IDs=len(selected),denied_operations=guard.denied,source_hashes_unchanged=True)
        _seal(paths,run,verification)
        print(json.dumps({'run_id':run_id,**{k:verification[k] for k in ('elapsed_seconds','projected_preparation_seconds','max_rss_bytes','prepared_IDs')}}),flush=True)
        return run
    except Exception as error:
        save_json(paths,run['provenance']/'FAILED.json',dict(type=type(error).__name__,message=str(error),denied_operations=guard.denied))
        raise
    finally: guard.active=False


def main():
    parser=argparse.ArgumentParser(description=__doc__); parser.add_argument('--pilot',action='store_true'); parser.add_argument('--pilot-run');parser.add_argument('--run-id')
    a=parser.parse_args(); paths=project_paths(); config=json.loads((paths.root/'configs/spatial_borrowing_s3_e1.json').read_text())
    prefix='spatial_borrowing_s3_e1_input_pilot_' if a.pilot else 'spatial_borrowing_s3_e1_input_'
    run_id=a.run_id or prefix+datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S_%fZ')
    if not run_id.startswith(prefix): raise ValueError('Wrong S3 preparation namespace')
    def timeout(*args): raise TimeoutError('Preparation time cap reached')
    signal.signal(signal.SIGALRM,timeout); signal.alarm(config['preflight_cap_seconds'] if a.pilot else config['preparation_cap_seconds'])
    try: prepare(paths,config,run_id,a.pilot,a.pilot_run)
    finally: signal.alarm(0)


if __name__=='__main__': main()
