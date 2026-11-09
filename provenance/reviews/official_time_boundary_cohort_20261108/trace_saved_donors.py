"""Locate the one-minute boundary pair in saved donor lists, without fitting."""
from pathlib import Path
import hashlib
import json
import struct
import numpy as np
import pandas as pd
import pyarrow as pa

OUT=Path(__file__).resolve().parent
ROOT=OUT.parents[2]
RUNS=ROOT/'results/runs'
E7=RUNS/'exact_origin_s4_e7_primary_20261105T074326_829211Z'
E8=RUNS/'position_error_s4_e8_20261106T095423_445879Z/formal'
E9=RUNS/'e9_formal_20261106T140607_806462Z'
E2=RUNS/'local_gmm_s5_e2_vector_20261107T133426Z'
KEY=['id','origin_source_obs','horizon_days']
fit=pd.read_parquet(E7/'training_coordinates.parquet').sort_values(KEY).reset_index(drop=True)
query=pd.read_parquet(E7/'query_coordinates.parquet').sort_values(KEY).reset_index(drop=True)
roles=pd.read_parquet(E7/'roles.parquet')
target=fit[(fit.id==75447)&(fit.origin_source_obs==56919282)]
assert len(target)==1
target_index=int(target.index[0]);summary={}


def save(name,roster,counts,sizes):
    counts=np.asarray(counts);sizes=np.asarray(sizes)
    assert len(counts)==len(roster) and (sizes>0).all()
    keep=counts>0
    s=dict(queries=int(keep.sum()),query_IDs=int(roster.loc[keep,'id'].nunique()),
           total_queries=len(roster),max_training_weight=float(np.max(counts/sizes)),
           donor_occurrences=int(counts.sum()))
    summary[name]=s
    records=roster[KEY].copy();records['flagged_donors']=counts;records['donor_count']=sizes
    records[keep].to_csv(OUT/(name+'_affected_queries.csv'),index_label='query_position')
    print(name,json.dumps(s),flush=True)


diag=pd.read_parquet(E8/'donor_diagnostics.parquet').sort_values('query_position').reset_index(drop=True)
assert diag[['id','origin_source_obs']].equals(query[['id','origin_source_obs']])
raw=np.memmap(E8/'donors.i32',dtype='<i4',mode='r');counts=[];sizes=[]
e7_roster=pd.read_parquet(E7/'outer_roster.parquet')
assert e7_roster.lineage_digest.tolist()==diag.lineage_digest.tolist()
for row in diag.itertuples(index=False):
    ix=raw[row.donor_offset:row.donor_offset+row.donors]
    assert hashlib.sha256(np.asarray(ix,dtype='<i8').tobytes()).hexdigest()==row.lineage_digest
    counts.append(int(np.sum(ix==target_index)));sizes.append(len(ix))
save('E7_E8_outer',query,counts,sizes)
cell=int(target.origin_cell_1.iloc[0]);n=int((fit.origin_cell_1==cell).sum())
save('E8_B2Point_outer',query,(query.origin_cell_1==cell).astype(int),query.origin_cell_1.map(fit.groupby('origin_cell_1').size()))

for name,folder,pool,roster in [('S5_E1_outer',RUNS/'conditional_gaussian_s5_e1_full_20261107T061818Z',fit,query),
                                ('S5_E2_outer',E2/'C_outer',fit,query)]:
    counts=[];sizes=[]
    for path in sorted((folder/'lineage').glob('*.npz')):
        with np.load(path,allow_pickle=False) as saved:
            ix,offsets=saved['indices'],saved['offsets']
            cs=np.r_[0,np.cumsum(ix==target_index,dtype=np.int64)]
            counts.extend((cs[offsets[1:]]-cs[offsets[:-1]]).tolist());sizes.extend(np.diff(offsets).tolist())
    save(name,roster,counts,sizes)

for role in ['C_T0','C_T1']:
    rr=roles[(roles.role_name==role)&(roles.horizon_days==7)]
    pool=rr[rr.role=='train'][KEY].merge(fit,on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
    roster=rr[rr.role=='validation'][KEY].merge(fit[KEY],on=KEY,validate='one_to_one').sort_values(KEY).reset_index(drop=True)
    ix_target=int(pool.index[(pool.id==75447)&(pool.origin_source_obs==56919282)][0])
    counts=[];sizes=[]
    for path in sorted((E2/role/'lineage').glob('*.npz')):
        with np.load(path,allow_pickle=False) as saved:
            ix,offsets=saved['indices'],saved['offsets']
            cs=np.r_[0,np.cumsum(ix==ix_target,dtype=np.int64)]
            counts.extend((cs[offsets[1:]]-cs[offsets[:-1]]).tolist());sizes.extend(np.diff(offsets).tolist())
    save('S5_E2_'+role,roster,counts,sizes)

assert pd.read_parquet(E9/'fit_keys_seasons.parquet')[KEY].equals(fit[KEY])
codec=pa.Codec('zstd');counts=[[],[]];sizes=[[],[]]
with (E9/'donor_lineage.zst').open('rb') as stream:
    for row in pd.read_parquet(E9/'lineage_offsets.parquet').itertuples(index=False):
        stream.seek(row.offset);blob=stream.read(row.length);n,m,fallback=struct.unpack('<IIB',blob[:9])
        raw_bytes=memoryview(codec.decompress(blob[9:],(n+m)*12));position=0;selected=[]
        for count in ([n] if fallback else [n,m]):
            delta=np.frombuffer(raw_bytes[position:position+4*count],'u1').reshape(4,count).T.copy().ravel().view('<u4')
            selected.append(np.cumsum(delta,dtype=np.int64));position+=12*count
        if fallback:selected.append(selected[0])
        for i,ix in enumerate(selected):counts[i].append(int(np.sum(ix==target_index)));sizes[i].append(len(ix))
save('E9_annual',query,counts[0],sizes[0]);save('E9_seasonal',query,counts[1],sizes[1])
(OUT/'boundary_pair_donor_usage.json').write_text(json.dumps(summary,indent=2)+'\n')
