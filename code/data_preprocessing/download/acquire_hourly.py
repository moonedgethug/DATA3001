"""Version-pinned NOAA GDP acquisition. Source objects remain byte-identical.

The only imported historic information is the release polygon's vertices.
IDs are discovered by scanning coordinates from this hourly asset itself.
"""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import argparse
import ast
import concurrent.futures as cf
import hashlib
import json
import math
import os
import sys
import threading
import time
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
import xml.etree.ElementTree as ET

import numpy as np
import pandas as pd
import requests
from numcodecs import get_codec
from shapely import Polygon, box, intersects_xy
from shapely.geometry import mapping, shape
from data3001.acquisition.rules import canonical_id, split_id

ROOT = project_paths().root
BUCKET = 'https://noaa-oar-hourly-gdp-pds.s3.amazonaws.com/'
PREFIX = 'latest/gdp-v2.01.1.zarr/'
THREAD = threading.local()
LOCK = threading.Lock()


def utcnow():
    return datetime.now(timezone.utc).isoformat()


@frozen_action
def json_save(path, obj):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.part')
    temp.write_text(json.dumps(obj, indent=2, ensure_ascii=False, allow_nan=False) + '\n')
    temp.replace(path)


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for block in iter(lambda: f.read(8 << 20), b''):
            h.update(block)
    return h.hexdigest()


def session():
    if not hasattr(THREAD, 'session'):
        THREAD.session = requests.Session()
    return THREAD.session


@frozen_action
def get(url, etag=None):
    for attempt in range(5):
        try:
            r = session().get(url, headers={'If-Match': etag} if etag else {}, timeout=(20, 90))
            if r.status_code in (409, 412):
                raise RuntimeError('Source mutation detected: ' + url)
            r.raise_for_status()
            if etag and r.headers.get('ETag') != etag:
                raise RuntimeError('ETag mismatch: ' + url)
            return r
        except (requests.RequestException,) as exc:
            if attempt == 4:
                raise
            time.sleep(min(2**attempt, 15))


class Snapshot:
    @frozen_action
    def __init__(self):
        inv_path = legacy_path('metadata/object_inventory.json')
        if not inv_path.exists():
            ns = {'s':'http://s3.amazonaws.com/doc/2006-03-01/'}
            inventory = {}
            token = None
            while True:
                query = {'list-type':'2', 'prefix':PREFIX, 'max-keys':'1000'}
                if token:
                    query['continuation-token'] = token
                r = get(BUCKET+'?'+urlencode(query))
                node = ET.fromstring(r.content)
                for item in node.findall('s:Contents', ns):
                    key = item.findtext('s:Key', namespaces=ns)[len(PREFIX):]
                    inventory[key] = {'etag':item.findtext('s:ETag', namespaces=ns),
                                      'size':int(item.findtext('s:Size', namespaces=ns)),
                                      'last_modified':item.findtext('s:LastModified', namespaces=ns)}
                if node.findtext('s:IsTruncated', namespaces=ns) != 'true':
                    break
                token = node.findtext('s:NextContinuationToken', namespaces=ns)
            json_save(inv_path, {'asset':BUCKET+PREFIX, 'listed_utc':utcnow(), 'objects':inventory})
        self.inventory = json.loads(inv_path.read_text())['objects']
        self.receipts = {}
        receipt_path = legacy_path('manifests/downloaded_objects.jsonl')
        if receipt_path.exists():
            for line in receipt_path.read_text().splitlines():
                item = json.loads(line)
                self.receipts[item['key']] = item
        self.meta = json.loads(self.fetch('.zmetadata'))['metadata']
        if 'version 2.01.1.' not in self.meta['.zattrs']['history']:
            raise RuntimeError('Unexpected dataset version')
        json_save(legacy_path('metadata/variable_dictionary.json'), {
            k[:-8]: {'attributes':v, 'storage':self.meta[k[:-8]+'/.zarray']}
            for k,v in self.meta.items() if k.endswith('/.zattrs')})

    def fetch(self, key):
        info = self.inventory[key]
        path = legacy_path('raw/source_objects', key)
        if path.exists():
            record = self.receipts.get(key)
            if not record or record['etag'] != info['etag'] or path.stat().st_size != info['size']:
                raise RuntimeError('Unrecorded or inconsistent existing source object: ' + key)
            return path.read_bytes()
        r = get(BUCKET+PREFIX+key, info['etag'])
        body = r.content
        if len(body) != info['size']:
            raise RuntimeError('Incomplete source object: '+key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temp = path.with_name(path.name+'.part')
        temp.write_bytes(body)
        temp.replace(path)
        record = {'key':key, **info, 'sha256':hashlib.sha256(body).hexdigest(),
                  'url':BUCKET+PREFIX+key, 'retrieved_utc':utcnow(),
                  'version_id':r.headers.get('x-amz-version-id')}
        with LOCK:
            with (legacy_path('manifests/downloaded_objects.jsonl')).open('a') as f:
                f.write(json.dumps(record)+'\n')
            self.receipts[key] = record
        return body

    def spec(self, var):
        return self.meta[var+'/.zarray']

    def chunk(self, var, number):
        spec = self.spec(var)
        raw = get_codec(spec['compressor']).decode(self.fetch(f'{var}/{number}'))
        for codec in reversed(spec.get('filters') or []):
            raw = get_codec(codec).decode(raw)
        values = np.frombuffer(raw, dtype=np.dtype(spec['dtype']))
        n = min(spec['chunks'][0], spec['shape'][0]-number*spec['chunks'][0])
        return values[:n]

    def all(self, var):
        spec = self.spec(var)
        return np.concatenate([self.chunk(var,k) for k in range(math.ceil(spec['shape'][0]/spec['chunks'][0]))])

    def verify(self):
        failures = []
        for key, record in self.receipts.items():
            path = legacy_path('raw/source_objects', key)
            if sha(path) != record['sha256']:
                failures.append(key)
        if failures:
            raise RuntimeError('Local source object checksum failures: '+str(failures))
        return len(self.receipts)


@frozen_action
def freeze_geometry():
    output = legacy_path('geometry/release_R.geojson')
    if output.exists():
        return shape(json.loads(output.read_text())['features'][0]['geometry'])
    source = ROOT.parent/'analysis/region_data_audit.py'
    tree = ast.parse(source.read_text())
    vertices = None
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(isinstance(t,ast.Name) and t.id=='REGIONS' for t in node.targets):
            for k,v in zip(node.value.keys, node.value.values):
                if ast.literal_eval(k)=='Gulf Stream Corridor':
                    vertices=ast.literal_eval(v.args[0])
    if vertices is None:
        raise RuntimeError('Original corridor vertices not found')
    region = Polygon(vertices).intersection(box(-82,30,-73,35.5))
    json_save(output, {'type':'FeatureCollection','name':'release_R', 'crs':{'type':'name','properties':{'name':'urn:ogc:def:crs:OGC:1.3:CRS84'}},
        'features':[{'type':'Feature','properties':{'coordinate_order':'longitude,latitude','polygon_boundary':'included',
            'definition':'Original Gulf Stream Corridor intersected with [-82,30,-73,35.5]',
            'corridor_source_sha256':sha(source)},'geometry':mapping(region)}]})
    return region


@frozen_action
def metadata(snap):
    path = legacy_path('metadata/trajectory_metadata.npz')
    if not path.exists():
        values = {k[:-8]:snap.all(k[:-8]) for k,v in snap.meta.items()
                  if k.endswith('/.zattrs') and v.get('_ARRAY_DIMENSIONS')==['traj']}
        np.savez_compressed(path, **values)
    meta = dict(np.load(path,allow_pickle=False))
    ids = meta['id']
    if len(set(ids.tolist())) != len(ids) or np.any(ids<=0):
        raise RuntimeError('Official ID uniqueness/normalization failed')
    offsets = np.concatenate([[0], np.cumsum(meta['rowsize'],dtype=np.int64)])
    if offsets[-1] != snap.spec('lon')['shape'][0]:
        raise RuntimeError('Ragged trajectory size mismatch')
    path = legacy_path('manifests/global_id_split.csv')
    frame = pd.DataFrame({'id':ids.astype(str),'source_traj_index':np.arange(len(ids)),
        'source_obs_start':offsets[:-1], 'source_obs_end_exclusive':offsets[1:],
        'source_rowsize':meta['rowsize'].astype(np.int64), 'split':[split_id(i) for i in ids]})
    if path.exists():
        old = pd.read_csv(path,dtype={'id':str})
        if not frame.equals(old):
            raise RuntimeError('Existing global ID split manifest changed')
    else:
        frame.to_csv(path,index=False)
    return meta, offsets, frame


@frozen_action
def discover(snap, region, offsets, frame, name, workers):
    path = legacy_path(f'manifests/{name}_ids.csv')
    if path.exists():
        return pd.read_csv(path,dtype={'id':str})
    spec = snap.spec('lon')
    chunk_size = spec['chunks'][0]
    total_chunks = math.ceil(spec['shape'][0]/chunk_size)
    counts = Counter()
    bbox = region.bounds
    started = time.monotonic()
    def scan(k):
        lon = snap.chunk('lon',k)
        lat = snap.chunk('lat',k)
        lon = (lon+180)%360-180
        mask = np.isfinite(lon)&np.isfinite(lat)&(lon>=bbox[0])&(lon<=bbox[2])&(lat>=bbox[1])&(lat<=bbox[3])
        indices = np.flatnonzero(mask)
        if len(indices):
            indices = indices[intersects_xy(region,lon[indices],lat[indices])]
        obs = k*chunk_size+indices
        traj = np.searchsorted(offsets[1:],obs,side='right')
        unique,n = np.unique(traj,return_counts=True)
        return dict(zip(unique.tolist(), n.tolist()))
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(scan,k) for k in range(total_chunks)]
        for done,f in enumerate(cf.as_completed(futures),1):
            counts.update(f.result())
            if done%50==0 or done==total_chunks:
                print(f'{name} discovery {done}/{total_chunks} coordinate chunks; {len(counts)} IDs; {time.monotonic()-started:.1f}s',flush=True)
    selected = frame.iloc[sorted(counts)].copy()
    selected['discovery_positions_in_geometry']=[counts[i] for i in sorted(counts)]
    selected.to_csv(path,index=False)
    json_save(legacy_path(f'manifests/{name}_query.json'), {'asset':BUCKET+PREFIX, 'method':'Complete scan of lon/lat from the pinned hourly asset',
        'source_coordinates_scanned':spec['shape'][0], 'source_chunks_scanned':total_chunks,
        'coordinate_rule':'Finite lon/lat, longitude normalized to [-180,180), polygon boundary included',
        'geometry':mapping(region),'ids_found':len(selected),'split_counts':selected['split'].value_counts().to_dict(),
        'completed_utc':utcnow(), 'id_selection_does_not_use_six_hourly_data':True})
    return selected


@frozen_action
def retrieve(snap, selected, frame, name, workers, only=None):
    if only is not None:
        selected = selected[selected['id'].isin(only)]
    variables = [k[:-8] for k,v in snap.meta.items() if k.endswith('/.zattrs') and v.get('_ARRAY_DIMENSIONS')==['obs']]
    needed = []
    for var in variables:
        chunk = snap.spec(var)['chunks'][0]
        numbers = set()
        for row in selected.itertuples():
            numbers.update(range(int(row.source_obs_start)//chunk, (int(row.source_obs_end_exclusive)-1)//chunk+1))
        needed.extend((var,k) for k in sorted(numbers))
    pending = [(v,k) for v,k in needed if f'{v}/{k}' not in snap.receipts]
    size = sum(snap.inventory[f'{v}/{k}']['size'] for v,k in pending)
    json_save(legacy_path(f'manifests/{name}_download_plan.json'), {'asset':BUCKET+PREFIX,'ids':selected['id'].tolist(),
        'variables':variables,'selection':'Full source trajectory for every selected ID, without time/spatial clipping',
        'required_chunks':len(needed),'additional_chunks':len(pending),'additional_source_bytes':size,
        'metadata_sha256':sha(legacy_path('raw/source_objects/.zmetadata')), 'split_manifest_sha256':sha(legacy_path('manifests/global_id_split.csv'))})
    print(f'{name}: {len(selected)} complete trajectories; {len(pending)} new chunks; {size/1e9:.3f} GB compressed source',flush=True)
    started = time.monotonic()
    def download_object(var, number):
        snap.fetch(f'{var}/{number}')
        # Do not retain compressed byte buffers in completed Future objects.
        return None
    with cf.ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(download_object,v,k) for v,k in pending]
        for done,f in enumerate(cf.as_completed(futures),1):
            f.result()
            if done%100==0 or done==len(pending):
                print(f'{name} download {done}/{len(pending)} chunks; {time.monotonic()-started:.1f}s',flush=True)
    return selected


def trajectory(snap, row, variables):
    result = {}
    a,b = int(row.source_obs_start),int(row.source_obs_end_exclusive)
    for var in variables:
        chunk=snap.spec(var)['chunks'][0]
        parts=[]
        for k in range(a//chunk,(b-1)//chunk+1):
            values=snap.chunk(var,k)
            parts.append(values[max(a-k*chunk,0):min(b-k*chunk,len(values))])
        result[var]=np.concatenate(parts)
    return result


@frozen_action
def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('stage',choices=['discover','pilot','R','verify'])
    parser.add_argument('--workers',type=int,default=12)
    args=parser.parse_args()
    snap=Snapshot()
    region=freeze_geometry()
    meta,offsets,frame=metadata(snap)
    if args.stage=='verify':
        n=snap.verify(); print('Verified byte hashes for',n,'source objects');return
    selected=discover(snap,region,offsets,frame,'R',args.workers)
    if args.stage=='pilot':
        pilot=selected[selected.split=='train'].sort_values('id').head(8)
        retrieve(snap,pilot,frame,'pilot',args.workers)
    elif args.stage=='R':
        retrieve(snap,selected,frame,'R',args.workers)
    json_save(legacy_path('manifests/source_snapshot.json'), {'asset':BUCKET+PREFIX, 'doi':snap.meta['.zattrs']['doi'],
        'source_attributes':snap.meta['.zattrs'], 'metadata_sha256':sha(legacy_path('raw/source_objects/.zmetadata')),
        'inventory_sha256':sha(legacy_path('metadata/object_inventory.json')), 'R_geometry_sha256':sha(legacy_path('geometry/release_R.geojson')),
        'split_manifest_sha256':sha(legacy_path('manifests/global_id_split.csv')), 'source_IDs':len(frame),
        'source_observations':int(offsets[-1]), 'R_IDs':len(selected), 'time_units':snap.meta['time/.zattrs']['units'],
        'split_rule':'SHA256 ASCII("20261004:" + canonical positive integer GDP id); uint256 digest / 2^256; [0,.70), [.70,.85), [.85,1)',
        'id_representation':'Official int64 GDP buoy ID; canonical positive base-10 string without leading zeros; no float conversion',
        'source_pin':'Frozen consolidated metadata and object inventory; conditional GET If-Match per object; local SHA256 receipts',
        'updated_utc':utcnow(),'final_D_frozen':False})


if __name__=='__main__':
    main()
