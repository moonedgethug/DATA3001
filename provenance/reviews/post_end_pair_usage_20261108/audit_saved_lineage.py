"""Read saved artifacts only. No fitting, prediction, scoring, or source changes."""
from pathlib import Path
import gzip
import hashlib
import json
import struct
import time

import numpy as np
import pandas as pd
import pyarrow as pa

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
RUNS = ROOT / 'results/runs'
E7 = RUNS / 'exact_origin_s4_e7_primary_20261105T074326_829211Z'
E8 = RUNS / 'position_error_s4_e8_20261106T095423_445879Z/formal'
E9 = RUNS / 'e9_formal_20261106T140607_806462Z'
S1 = RUNS / 'conditional_gaussian_s5_e1_full_20261107T061818Z'
S2 = RUNS / 'local_gmm_s5_e2_vector_20261107T133426Z'
ID = 300234066312880
KEYS = ['id', 'origin_source_obs', 'horizon_days']


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_json(name, value):
    (OUT / name).write_text(json.dumps(value, indent=2, ensure_ascii=False, default=str) + '\n')


start = time.monotonic()
frozen = [ROOT / 'data/train' / f'{ID}.parquet', E7 / 'training_coordinates.parquet',
          E7 / 'query_coordinates.parquet', S2 / 'model_manifest.json',
          ROOT / 'provenance/runs/local_gmm_s5_e2_vector_20261107T133426Z/selection.json']
before = {str(p.relative_to(ROOT)): sha(p) for p in frozen}
fit = pd.read_parquet(E7 / 'training_coordinates.parquet').sort_values(KEYS).reset_index(drop=True)
query = pd.read_parquet(E7 / 'query_coordinates.parquet').reset_index(drop=True)
bad = fit[(fit.id == ID) & (fit.matched_endpoint_epoch > 1559001600)]
assert len(bad) == 12
bad.to_csv(OUT / 'flagged_pairs.csv', index_label='fit_row_index')
bad_indices = bad.index.to_numpy()
assert np.array_equal(bad_indices, np.arange(262342, 262354))
roles = pd.read_parquet(E7 / 'roles.parquet').merge(bad[KEYS], on=KEYS)
roles.to_csv(OUT / 'roles.csv', index=False)
weights = 1 / (query.groupby('id').id.transform('size').to_numpy() * query.id.nunique())
summary = dict(flagged_pairs=len(bad), training_pairs=len(fit), validation_pairs=len(query),
               training_fraction=len(bad) / len(fit), role_counts=roles.groupby(['role_name','role']).size().to_dict().__str__())


def tally(name, counts, sizes, per_pair):
    counts, sizes = np.asarray(counts), np.asarray(sizes)
    assert len(counts) == len(query) and (sizes > 0).all()
    affected = counts > 0
    mass = counts / sizes
    result = dict(queries=int(affected.sum()), independent_query_ids=int(query.loc[affected,'id'].nunique()),
                  query_fraction=float(affected.mean()), evaluation_weight_affected=float(weights @ affected),
                  donor_occurrences=int(counts.sum()), max_donor_mass=float(mass.max()),
                  mean_donor_mass_equal_id=float(weights @ mass), per_pair_occurrences=per_pair.tolist())
    summary[name] = result
    frame = query[KEYS + ['origin_cell_1']].copy()
    frame['flagged_donors'] = counts
    frame['donors'] = sizes
    frame['flagged_mass'] = mass
    frame['evaluation_weight'] = weights
    frame[affected].to_csv(OUT / f'{name}_affected_queries.csv', index_label='query_position')
    print(name, json.dumps(result), flush=True)


raw = np.memmap(E8 / 'donors.i32', dtype='<i4', mode='r')
diag = pd.read_parquet(E8 / 'donor_diagnostics.parquet').sort_values('query_position')
assert diag[['id','origin_source_obs']].reset_index(drop=True).equals(query[['id','origin_source_obs']])
counts, sizes, pair_counts = [], [], np.zeros(12, dtype=np.int64)
digest_match = True
for row in diag.itertuples(index=False):
    ix = raw[row.donor_offset:row.donor_offset+row.donors]
    selected = ix[(ix >= bad_indices[0]) & (ix <= bad_indices[-1])]
    pair_counts += np.bincount(selected-bad_indices[0], minlength=12)
    counts.append(len(selected)); sizes.append(len(ix))
    digest_match &= hashlib.sha256(np.asarray(ix,dtype='<i8').tobytes()).hexdigest() == row.lineage_digest
assert digest_match
e7_roster = pd.read_parquet(E7 / 'outer_roster.parquet')
assert e7_roster.lineage_digest.tolist() == diag.lineage_digest.tolist()
summary['E7_E8_saved_donor_digests_match_all_queries'] = True
tally('E7_E8_exact_family', counts, sizes, pair_counts)

cell_counts = fit.groupby('origin_cell_1').size()
b2sizes = query.origin_cell_1.map(cell_counts).to_numpy()
b2counts = np.where(query.origin_cell_1 == 44023, 12, 0)
tally('E8_B2Point', b2counts, b2sizes, np.full(12, np.sum(b2counts > 0)))

for name, folder, chunk_size in [('S5_E1', S1, 128), ('S5_E2', S2/'C_outer', 32)]:
    counts, sizes, pair_counts = [], [], np.zeros(12, dtype=np.int64)
    mismatch = 0
    for path in sorted((folder/'lineage').glob('*.npz')):
        with np.load(path, allow_pickle=False) as data:
            ix, offsets = data['indices'], data['offsets']
            mask = (ix >= bad_indices[0]) & (ix <= bad_indices[-1])
            cs = np.r_[0,np.cumsum(mask,dtype=np.int64)]
            local_counts = cs[offsets[1:]] - cs[offsets[:-1]]
            pair_counts += np.bincount(ix[mask].astype(np.int64)-bad_indices[0],minlength=12)
            begin = len(counts)
            for local in range(len(offsets)-1):
                j = begin+local; d = diag.iloc[j]
                saved = raw[int(d.donor_offset):int(d.donor_offset+d.donors)]
                mismatch += not np.array_equal(ix[offsets[local]:offsets[local+1]], saved)
            counts.extend(local_counts.tolist()); sizes.extend(np.diff(offsets).tolist())
    assert len(counts) == len(query)
    summary[name+'_donor_array_mismatch_vs_E8'] = int(mismatch)
    assert mismatch == 0
    tally(name,counts,sizes,pair_counts)

# Decode stored indices only; this does not repeat neighbour selection.
codec = pa.Codec('zstd')
offsets = pd.read_parquet(E9/'lineage_offsets.parquet')
season_fit = pd.read_parquet(E9/'fit_keys_seasons.parquet')
assert season_fit[KEYS].equals(fit[KEYS])
annual_counts, seasonal_counts, annual_sizes, seasonal_sizes = [], [], [], []
annual_pairs, seasonal_pairs = np.zeros(12,dtype=np.int64), np.zeros(12,dtype=np.int64)
fallback_count = 0
with (E9/'donor_lineage.zst').open('rb') as stream:
    for row in offsets.itertuples(index=False):
        stream.seek(row.offset); blob=stream.read(row.length)
        n,m,fallback=struct.unpack('<IIB',blob[:9])
        unpacked=memoryview(codec.decompress(blob[9:],(n+m)*12))
        position=0; selections=[]
        for count in ([n] if fallback else [n,m]):
            delta=np.frombuffer(unpacked[position:position+4*count],'u1').reshape(4,count).T.copy().ravel().view('<u4')
            ix=np.cumsum(delta,dtype=np.int64);position+=12*count
            selections.append(ix)
        if fallback: selections.append(selections[0]); fallback_count+=1
        for ix,cnts,sz,pcs in [(selections[0],annual_counts,annual_sizes,annual_pairs),(selections[1],seasonal_counts,seasonal_sizes,seasonal_pairs)]:
            selected=ix[(ix>=bad_indices[0])&(ix<=bad_indices[-1])]
            cnts.append(len(selected));sz.append(len(ix))
            pcs+=np.bincount(selected-bad_indices[0],minlength=12)
summary['E9_fallback_queries']=fallback_count
tally('E9_annual',annual_counts,annual_sizes,annual_pairs)
tally('E9_seasonal',seasonal_counts,seasonal_sizes,seasonal_pairs)
after={str(p.relative_to(ROOT)):sha(p) for p in frozen}
assert before==after
write_json('source_integrity.json',dict(before=before,after=after,unchanged=True))
summary['elapsed_seconds']=time.monotonic()-start
write_json('usage_summary.json',summary)
print('DONE',summary['elapsed_seconds'],flush=True)
