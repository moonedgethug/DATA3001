"""Read-only audit of a small training cohort; no D selection from test labels."""
from data3001.paths import legacy_path, asset_path, project_paths, ensure_output_path, frozen_action
import json
import time
import resource
import sys
from pathlib import Path
import numpy as np
import pandas as pd
from shapely import intersects_xy
from data3001.acquisition.acquire_hourly import ROOT, Snapshot, metadata, trajectory, freeze_geometry, json_save, sha
from data3001.acquisition.rules import classify


@frozen_action
def main():
    started=time.monotonic()
    snap=Snapshot()
    meta,offsets,frame=metadata(snap)
    region=freeze_geometry()
    selected=pd.read_csv(legacy_path('manifests/R_ids.csv'),dtype={'id':str})
    pilot=selected[selected.split=='train'].sort_values('id').head(8)
    variables=[k[:-8] for k,v in snap.meta.items() if k.endswith('/.zattrs') and v.get('_ARRAY_DIMENSIONS')==['obs']]
    profiles=[]
    examples=[]
    required_days=[1,2,3,4,5,6,7,10,14,15,21,30,90,180,365]
    for row in pilot.itertuples():
        arrays=trajectory(snap,row,variables)
        t=arrays['time']; lon=(arrays['lon']+180)%360-180;lat=arrays['lat']
        valid=np.isfinite(t)&np.isfinite(lon)&np.isfinite(lat)&(lat>=-90)&(lat<90)
        if len(t)!=row.source_rowsize:
            raise RuntimeError('Truncated trajectory')
        changes=np.diff(t)
        finite=t[np.isfinite(t)]
        inside=np.zeros(len(t),dtype=bool)
        inside[valid]=intersects_xy(region,lon[valid],lat[valid])
        origins=np.flatnonzero(inside&valid)
        missing_sst=~np.isfinite(arrays['sst'])
        info={'id':row.id,'split':row.split,'source_records':len(t),'finite_position_time':int(valid.sum()),
            'duplicate_timestamps':int(len(finite)-len(np.unique(finite))),
            'nonincreasing_steps':int(np.count_nonzero(changes<=0)),
            'nonhourly_steps':int(np.count_nonzero(changes!=3600)),
            'start_utc':pd.to_datetime(np.nanmin(t),unit='s',utc=True).isoformat(),
            'end_utc':pd.to_datetime(np.nanmax(t),unit='s',utc=True).isoformat(),
            'R_candidate_origins':len(origins),'missing_sst_but_position_valid':int((missing_sst&valid).sum()),
            'source_drogue_status_values':','.join(str(int(v)) for v in np.unique(arrays['drogue_status'])),
            'source_drogue_status_switches':int(np.count_nonzero(np.diff(arrays['drogue_status'])!=0))}
        # Source time units are exact epoch seconds. Match using timestamps only.
        for days in required_days:
            labels=t[origins]+days*86400
            destinations=np.searchsorted(t,labels)
            bounded=destinations<len(t)
            matched=np.zeros(len(origins),dtype=bool)
            matched[bounded]=(t[destinations[bounded]]==labels[bounded])&valid[destinations[bounded]]
            info[f'exact_endpoint_pairs_{days}d']=int(matched.sum())
        profiles.append(info)
        # One real origin per pilot ID, with R as an explicitly illustrative D.
        # This does not set the formal transport domain.
        if len(origins):
            origin=int(origins[0]);origin_time=t[origin]
            stop=np.searchsorted(t,origin_time+365*86400,side='right')
            hours=((t[origin:stop]-origin_time)/3600).tolist()
            if all(h==round(h) for h in hours):
                hours=[int(h) for h in hours]
                for days in [7,30,365]:
                    regime=arrays['drogue_status'][origin:stop].tolist()
                    args=(hours,inside[origin:stop].tolist(),valid[origin:stop].tolist(),regime,days*24,regime[0])
                    examples.append({'id':row.id,'origin_epoch_seconds':float(origin_time),'horizon_days':days,
                        'illustration_only_domain':'R; not a final D','regime':'source state at origin held fixed for this retrospective check',
                        'endpoint_result':classify(*args,'endpoint'),'stopped_result':classify(*args,'stopped')})
    pd.DataFrame(profiles).to_csv(legacy_path('audit/pilot_trajectory_profile.csv'),index=False)
    pd.DataFrame(examples).to_csv(legacy_path('audit/pilot_label_examples.csv'),index=False)
    df=pd.DataFrame(profiles)
    gate=bool((df.duplicate_timestamps==0).all() and (df.nonincreasing_steps==0).all() and
              (df.source_records==df.finite_position_time).all() and all(r.split=='train' for r in pilot.itertuples()))
    summary={'status':'PASS' if gate else 'FAIL','pilot_ids':len(pilot),'pilot_records':int(df.source_records.sum()),
        'source_fields_retained':variables,'profile':str((legacy_path('audit/pilot_trajectory_profile.csv')).relative_to(ROOT)),
        'label_examples':'audit/pilot_label_examples.csv','label_example_count':len(examples),
        'label_example_scope':'R used only as an illustrative domain; no final D and no model predictions',
        'literal_contract_boundary_tests':'tests/test_rules.py; nine passing tests recorded in audit/rules_green.log',
        'elapsed_seconds':round(time.monotonic()-started,2),'raw_bytes_currently_cached':sum(r['size'] for r in snap.receipts.values()),
        'peak_RSS_bytes':int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)*(1 if sys.platform=='darwin' else 1024),
        'formal_QC_and_support_audit_complete':False,
        'snapshot_metadata_sha256':sha(legacy_path('raw/source_objects/.zmetadata')),
        'source_gap_semantics':'gap is previous-to-next original location interval in seconds; not a missing-hour indicator',
        'source_drogue_status_semantics':'Source flag 1=presence, 0=absence. Retain raw flags and drogue_lost_date. Do not treat a missing loss date as an observed switch.',
        'cautions':['The small training cohort is an engineering check, not a representativeness or model-accuracy claim.',
                    'Source gap values and missing/zero drogue-loss dates require explicit provenance in formal cleaning.',
                    'No empirical minimum support threshold has been imposed.']}
    json_save(legacy_path('audit/pilot_gate.json'),summary)
    print(json.dumps(summary,indent=2))
    if not gate:
        raise SystemExit(1)


if __name__=='__main__':
    main()
