"""Observed cell reversals and uncertain gap crossings; never changes origins."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import numpy as np
import pandas as pd
from data3001.preprocessing.prep_io import Source, OUT, parquet, save_json, now
from data3001.preprocessing.prep_run import directory

@frozen_action
def run(split='development'):
    s=Source();rows=[];gaps=[];root=legacy_path('preparation', 'restricted_test') if split=='test' else OUT
    for id in s.ids:
        id=int(id)
        if (s.cohort.loc[id,'split']=='test')!=(split=='test'):continue
        d=pd.read_parquet(directory(split)/f'{id}.parquet',columns=['source_obs','time','cell_1','cell_05','position_ok','geometry_uncertain'])
        t=d.time.to_numpy();dt=np.diff(t)
        for res,col in [(1,'cell_1'),(.5,'cell_05')]:
            cell=d[col].to_numpy();nx=int(360/res)
            ix=cell%nx;iy=cell//nx
            xdiff=np.minimum(abs(ix[1:]-ix[:-1]),nx-abs(ix[1:]-ix[:-1]))
            adjacent=(xdiff<=1)&(abs(iy[1:]-iy[:-1])<=1)
            pattern=(cell[:-2]==cell[2:])&(cell[1:-1]!=cell[:-2])&(cell[:-2]>=0)&(cell[1:-1]>=0)&adjacent[:-1]&adjacent[1:]&(dt[:-1]==3600)&(dt[1:]==3600)
            for j in np.flatnonzero(pattern)+1:
                rows.append({'id':id,'source_obs':int(d.source_obs.iloc[j]),'time':float(t[j]),'resolution':res,'previous_cell':int(cell[j-1]),'current_cell':int(cell[j]),'next_cell':int(cell[j+1]),'interpretation':'observed adjacent A-B-A reversal, not proof of spurious jitter','action':'retain unsmoothed assignment and all origins'})
            for j in np.flatnonzero((dt!=3600)&(cell[:-1]!=cell[1:]))+1:
                gaps.append({'id':id,'before_source_obs':int(d.source_obs.iloc[j-1]),'after_source_obs':int(d.source_obs.iloc[j]),'before_epoch':float(t[j-1]),'after_epoch':float(t[j]),'resolution':res,'before_cell':int(cell[j-1]),'after_cell':int(cell[j]),'crossing_time':'unobserved within missing interval','action':'no invented crossing time or first-exit evidence'})
    parquet(pd.DataFrame(rows),root/'audit/cell_reversal_diagnostics.parquet');parquet(pd.DataFrame(gaps),root/'audit/uncertain_cell_crossings.parquet')
    save_json(root/'audit/boundary_diagnostics.json',{'utc':now(),'observed_reversal_patterns':len(rows),'uncertain_gap_crossings':len(gaps),'sampling_or_labels_changed':False})

if __name__=='__main__':run()
