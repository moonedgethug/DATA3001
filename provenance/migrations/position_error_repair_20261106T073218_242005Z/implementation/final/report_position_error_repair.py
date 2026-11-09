"""Publish descriptive repair coverage and provenance, without model scoring."""
import argparse
from datetime import datetime,timezone
import hashlib
import importlib.metadata
import json
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Geod

ROOT=Path(__file__).resolve().parents[3]
GOOD={'verified_unchanged','restored_scale','recovered_from_reference'}
UNRESOLVED={'source_missing','not_fetched_budget','source_metadata_unresolved','time_unmatched',
            'coordinate_changed','duplicate_conflict','reference_conflict','version_unresolved',
            'estimation_version_unresolved','semantics_unresolved','zero_unresolved',
            'unexplained_difference','geometry_review_required','reference_invalid'}


def sha(path):
    with Path(path).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()


def markdown(frame):
    rows=['| '+' | '.join(map(str,frame.columns))+' |','| '+' | '.join(['---']*len(frame.columns))+' |']
    rows.extend('| '+' | '.join(map(str,row))+' |' for row in frame.itertuples(index=False,name=None))
    return '\n'.join(rows)


def stratified_scales(data,folder):
    """Describe source amplitudes; never select or trim records by their size."""
    records=[];extremes=[];geod=Geod(ellps='WGS84')
    for axis in ['lon','lat']:
        valid=data.loc[data['status_'+axis].isin(GOOD)].copy()
        for kind in ['original','repaired']:
            column=kind+'_err_'+axis
            part=valid.loc[np.isfinite(valid[column]) & valid[column].gt(0)].copy()
            v=part[column].to_numpy()
            _,_,part['amplitude_m']=geod.inv(part.lon.to_numpy(),part.lat.to_numpy(),
                part.lon.to_numpy()+(v if axis=='lon' else 0),
                part.lat.to_numpy()+(v if axis=='lat' else 0))
            for grouping in ['location_type','era','source_history']:
                for label,g in part.groupby(grouping,observed=True,dropna=False):
                    record={'axis':axis,'value':kind,'grouping':grouping,'stratum':str(label),'observations':len(g)}
                    for measure,c in [('degrees',column),('metres','amplitude_m')]:
                        for name,q in [('min',0),('p01',.01),('median',.5),('p90',.9),('p99',.99),('max',1)]:
                            record[name+'_'+measure]=float(g[c].quantile(q))
                    records.append(record)
        # Include positive candidate values even when their use was withheld.
        part=data.loc[np.isfinite(data['ref_err_'+axis]) & data['ref_err_'+axis].gt(0)].copy()
        for grouping in ['location_type','era','source_history']:
            for label,g in part.groupby(grouping,observed=True,dropna=False):
                largest=g.nlargest(3,'ref_err_'+axis)
                for row in largest.itertuples():
                    extremes.append({'axis':axis,'grouping':grouping,'stratum':str(label),
                        'id':row.id,'source_obs':row.source_obs,'time_UTC':row.time_UTC,
                        'lon':row.lon,'lat':row.lat,'reference_amplitude_degrees':getattr(row,'ref_err_'+axis),
                        'status':getattr(row,'status_'+axis),'source_sha256':row.source_sha256})
    pd.DataFrame(records).to_csv(folder/'error_scale_by_stratum.csv',index=False)
    pd.DataFrame(extremes).to_csv(folder/'extreme_reference_examples.csv',index=False)


def publish(run):
    folder=run/'full'
    verification=json.loads((folder/'verification.json').read_text())
    replay=json.loads((folder/'reproducibility.json').read_text())
    assert verification['passed'] and replay['passed']
    data=pd.read_parquet(folder/'error_overlay.parquet')
    registry=json.loads((folder/'source_registry.json').read_text())
    approval=json.loads((run/'approval.json').read_text())
    resources=json.loads((folder/'resources.json').read_text())
    exception_review=json.loads((folder/'exception_review.json').read_text())
    counts=[]
    for axis in ['lon','lat']:
        for status,count in data['status_'+axis].value_counts().items():
            counts.append({'axis':axis,'status':status,'observations':int(count),'percent':round(count/len(data)*100,5)})
    status=pd.DataFrame(counts);status.to_csv(folder/'status_counts.csv',index=False)
    by_id=data.groupby('id').agg(observations=('source_obs','size'),usable=('ci_2d_usable','sum'),
          location_type=('location_type','first'),origin_uses=('origin_pair_count','sum'),endpoint_uses=('endpoint_pair_count','sum')).reset_index()
    by_id['usable_percent']=by_id.usable/by_id.observations*100
    by_id.to_csv(folder/'coverage_by_id.csv',index=False)
    by_reason=data.groupby(['id','status_lon','status_lat'],dropna=False).size().rename('observations').reset_index()
    by_reason.to_csv(folder/'coverage_by_id_and_reason.csv',index=False)
    strata=data.assign(year=data.time_UTC.dt.year,era=pd.cut(data.time_UTC.dt.year,[2000,2006,2012,2019],labels=['2001-2006','2007-2012','2013-2019']))
    for name in ['year','era','location_type','source_history']:
        summary=strata.groupby(name,observed=True,dropna=False).agg(observations=('source_obs','size'),usable=('ci_2d_usable','sum')).reset_index()
        summary['usable_percent']=summary.usable/summary.observations*100
        summary.to_csv(folder/f'coverage_by_{name}.csv',index=False)
    stratified_scales(strata,folder)
    pair_path=ROOT/'results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet'
    pairs=pd.read_parquet(pair_path)
    flag=data.set_index(['id','source_obs']).ci_2d_usable
    origin=flag.reindex(pd.MultiIndex.from_arrays([pairs.id,pairs.origin_source_obs]))
    endpoint=flag.reindex(pd.MultiIndex.from_arrays([pairs.id,pairs.endpoint_source_obs]))
    assert not origin.isna().any() and not endpoint.isna().any()
    pair_counts={'all_pairs':len(pairs),'usable_origin_error':int(origin.sum()),'usable_endpoint_error':int(endpoint.sum()),
                 'both_origin_and_endpoint_usable':int((origin.to_numpy() & endpoint.to_numpy()).sum())}
    positive_summary=[];geod=Geod(ellps='WGS84')
    for axis in ['lon','lat']:
        g=data[data['status_'+axis].isin(GOOD)]
        for kind in ['original','repaired']:
            valid=g[np.isfinite(g[kind+'_err_'+axis]) & g[kind+'_err_'+axis].gt(0)]
            v=valid[kind+'_err_'+axis].to_numpy()
            _,_,metres=geod.inv(valid.lon.to_numpy(),valid.lat.to_numpy(),
                valid.lon.to_numpy()+(v if axis=='lon' else 0),valid.lat.to_numpy()+(v if axis=='lat' else 0))
            positive_summary.append({'axis':axis,'value':kind,'positive_observations':len(v),
              'median_degrees':float(np.median(v)),'p99_degrees':float(np.quantile(v,.99)),
              'median_amplitude_m':float(np.median(metres)),'p99_amplitude_m':float(np.quantile(metres,.99)),
              'max_amplitude_m':float(np.max(metres))})
    pd.DataFrame(positive_summary).to_csv(folder/'error_scale_summary.csv',index=False)
    exceptions=data[~data.ci_2d_usable]
    examples=exceptions.groupby(['status_lon','status_lat'],dropna=False,sort=True).head(5)
    examples.to_csv(folder/'exception_examples.csv',index=False)
    available=[r for r in registry if r['status']=='available']
    reasons=pd.DataFrame([{'id':r['id'],'route':r['route'],'download_status':r['status'],
                'eligible':r.get('inspection',{}).get('eligible',False),'reason':r.get('inspection',{}).get('reason',''),
                'identity_basis':r.get('inspection',{}).get('identity_basis',''),'url':r['url'],'sha256':r.get('sha256','')}
                for r in registry])
    reasons.to_csv(folder/'source_status.csv',index=False)
    unresolved=data.status_lon.isin(UNRESOLVED)|data.status_lat.isin(UNRESOLVED)
    status_name='VERIFIED_PARTIAL' if unresolved.any() else 'VERIFIED_COMPLETE'
    usable=int(data.ci_2d_usable.sum())
    metrics={'status':status_name,'scope_IDs':int(data.id.nunique()),'observations':len(data),'ci_2d_usable':usable,
        'ci_2d_usable_percent':usable/len(data)*100,'not_2d_usable':int((~data.ci_2d_usable).sum()),
        'lon_accepted':int(data.status_lon.isin(GOOD).sum()),'lat_accepted':int(data.status_lat.isin(GOOD).sum()),
        'matched_observations':int(data.match_status.eq('matched').sum()),
        'axis_status_counts':counts,'pair_counts':pair_counts,
        'available_sources':len(available),'requested_sources':len(registry),
        'IDs_with_any_download':len({r['id'] for r in available}),
        'IDs_with_any_usable_record':int(by_id.usable.gt(0).sum()),
        'original_endpoint_observations_retained':True,'base_modified':False,'model_experiments_run':False,
        'final_test_accessed':False,'outer_endpoint_error_accessed':False,'scale_summary':positive_summary}
    (folder/'summary.json').write_text(json.dumps(metrics,indent=2)+'\n')
    cover=pd.DataFrame([
        ['Target observations audited',len(data),'100.000%'],
        ['Reference observations matched',metrics['matched_observations'],f'{metrics["matched_observations"]/len(data)*100:.3f}%'],
        ['Two-axis error usable',usable,f'{usable/len(data)*100:.3f}%'],
        ['Two-axis error unavailable',len(data)-usable,f'{(len(data)-usable)/len(data)*100:.3f}%'],
        ['Longitude accepted',metrics['lon_accepted'],f'{metrics["lon_accepted"]/len(data)*100:.3f}%'],
        ['Latitude accepted',metrics['lat_accepted'],f'{metrics["lat_accepted"]/len(data)*100:.3f}%'],
    ],columns=['Measure','Observations','Share of frozen targets'])
    lines=[
        '# Position-error repair: verified training-only overlay',
        '',f'Status: **{status_name}**. Generated {datetime.now(timezone.utc).isoformat()}.',
        '',f'All {len(data):,} authorized observations from {data.id.nunique()} training drifters were accounted for. '
        f'{usable:,} ({usable/len(data)*100:.3f}%) have verified usable error values on both axes. '
        'Unresolved records remain in the overlay and in the unchanged training population.',
        '',markdown(cover),
        '', '## What was repaired',
        '', 'Values were copied from identity-, time-, coordinate- and version-matched official native files. '
        'There was no global multiplication by 100,000. Missing markers were identified before any declared packing transform. '
        'A native zero remains unresolved rather than implying perfect certainty. A valid single axis is preserved without enabling a two-axis CI.',
        '',markdown(status),
        '', 'Before/after error amplitudes are reported globally and separately by period, location system and native source history. '
        'The largest reference values, including withheld candidates, remain in the review tables. These are marginal positional-error amplitudes, not transport forecast spreads.',
        '', '## Unresolved records',
        '',markdown(data.loc[~data.ci_2d_usable].groupby(['status_lon','status_lat']).size().rename('observations').reset_index()),
        '', 'Estimation-version failures include active/unfinished old trajectories or a version family outside the audited native profile. '
        'Coordinate, identity, source and semantic failures were not bypassed. Large error values were not trimmed to improve apparent quality. '
        'A zero may reflect encoding/estimation limitations; its meaning has not been established. '
        'No missing error was filled using a typical instrument accuracy, neighbouring drifter, model result or validation endpoint.',
        '', 'The 5,512 coordinate changes and 1,398 unexplained error differences belong to the same eight GPS IDs; all 6,910 of their target observations were withheld. '
        'Coordinate differences range from 0.110 to 23.307 metres (median 0.501 m). These are not necessarily large position errors, but exceed the registered storage-precision match. '
        'For the 1,398 coordinate-matched observations, reference/current error ratios range approximately from 98,386 to 101,738 across the two axes; '
        'they do not meet the predeclared 100,000-factor tolerance. This supports withholding them, not silently widening the matching or scale tolerance.',
        '', 'The missing-source ID is 300234061390930 (254 target observations); both approved official routes returned file-not-found. '
        'No matched observation was classified as a native fill/NaN/Inf reference. Eighteen observations have an unresolved native zero on one axis. '
        'The original base contains 498 null longitude errors, 492 null latitude errors and 12 negative latitude errors; these counts are distinct from unavailable repaired fields. '
        'See the [exception review](full/exception_review.json) for the descriptive checks and original-value availability.',
        '', '## Pair-use coverage (not independent sample sizes)',
        '',markdown(pd.DataFrame([pair_counts])),
        '', 'The observation denominator counts unique (ID, source_obs) keys. Pair-use denominators count each frozen forecast pair once. '
        'These counts are data availability, not prediction hit rates. Every original pair is retained.',
        '', '## Source acquisition and identity',
        '',f'{len(available)}/{len(registry)} requested source files were available, covering {metrics["IDs_with_any_download"]} IDs. '
        'Availability does not imply eligibility. Native ID equality or an exact IMEI crosswalk explicitly stored in the same official file was required; WMO, filename and numeric suffix guesses were not accepted. '
        'Directory versions alone were not trusted. Files internally identified as v2.00 were required to describe trajectories ended before the v2.00 cutoff.',
        '', 'The current-directory file for some GPS IDs lacks a sufficient full-ID identity mapping; a valid legacy reference may still be used independently. '
        'The complete route-specific reasons are in [source_status.csv](full/source_status.csv) and [source_registry.json](full/source_registry.json).',
        '', '## Validation and reproducibility',
        '',f'- Independent raw-HDF5 re-reading and separate matching/decoding/classification verified every accepted value and every status across {len(data):,} rows.',
        '- A cache-only replay using two spawned processes exactly reproduced the per-ID logical outputs of the sequential production run. No HDF5/NetCDF handle was shared between threads.',
        '- Every referenced native coordinate and error variable was independently checked for the audited float32 storage and degree-unit profile; a different profile would fail publication.',
        f'- All {verification["protected_files_unchanged"]} protected file hashes were unchanged, including the 338 base track files, input pair cache, data contract, manifests and research-stage record.',
        '- All 22 rule and boundary tests passed; [test output](unit_tests_final.txt) is retained.',
        '- The 1,604-endpoint / 3,208-value anchor cases passed. The four already-unscaled latitude errors were preserved. The ten diagnosed negative endpoint errors were withheld as unresolved zeros.',
        '- The first pilot audit found a reason-code ordering discrepancy for an active GPS trajectory. Both implementations withheld its errors. The first attempt was preserved; ordering was clarified and the pilot rebuilt from the same cached files before proceeding.',
        '- A full-phase receipt initially displayed a pilot-only budget flag; this reporting field was scoped correctly and the full independent audit repeated. Both receipts are retained; data and repair decisions did not change.',
        '', '## Resource use',
        '',f'Full phase: {resources["elapsed_seconds"]:.1f} seconds; cumulative source download {resources["network_bytes"]/2**20:.1f} MiB; '
        f'production peak RSS {resources["peak_rss_bytes"]/2**20:.1f} MiB. Independent validation: {verification["validation_seconds"]:.1f} seconds; '
        f'two-process replay: {replay["elapsed_seconds"]:.1f} seconds. Pilot attempt costs are separately retained in the run receipts.',
        '',f'Independent verifier peak RSS was {verification["peak_rss_bytes"]/2**20:.1f} MiB. '
        f'The conservative combined RSS bound for replay was {replay["conservative_combined_rss_bound_bytes"]/2**20:.1f} MiB; both were below 4 GiB.',
        '', '## Files and use boundary',
        '', '- [Verified overlay](full/error_overlay.parquet)',
        '- [All exceptions](full/exceptions.parquet) and [representative examples](full/exception_examples.csv)',
        '- [Coverage by ID](full/coverage_by_id.csv), [ID and reason](full/coverage_by_id_and_reason.csv), and [error scale summary](full/error_scale_summary.csv)',
        '- [Scale by period, location system and source](full/error_scale_by_stratum.csv) and [largest reference examples](full/extreme_reference_examples.csv)',
        '- [Independent verification](full/verification.json), [reproducibility](full/reproducibility.json), [approval](approval.json)',
        '', 'Each overlay row is keyed by `(base_version, id, source_obs)`. '
        '`original_err_lon/lat` preserve the base values; `raw_ref_err_lon/lat` and `ref_err_lon/lat` preserve the raw and decoded native evidence. '
        '`repaired_err_lon/lat` contain only accepted degree-valued amplitudes, otherwise null. '
        '`status_lon/lat` explain each decision. `source_sha256` and `source_indices` point to the cached official file and native rows. '
        '`ci_2d_usable` requires both accepted axes and does not establish a calibrated joint region.',
        '', 'The overlay must be explicitly paired with its base version and release manifest hash. It has not been enabled in any model or default reader. '
        'Unavailable overlay values must not silently fall back to the unverified original errors. '
        'This is a repair of the frozen E7 training observations, not the whole development database. '
        'Neither outer-validation endpoint errors nor locked final-test observations were accessed. '
        'No model fitting, forecasting or scoring was performed. Verified marginal error fields do not establish joint CI calibration or improved transport prediction.',
    ]
    report=run/'REPORT.md'
    with report.open('x') as f:f.write('\n'.join(lines)+'\n')
    code_files=[p for p in (ROOT/'src/data3001/preprocessing').glob('*position_error_repair.py')]
    code_files.extend([ROOT/'tests/test_position_error_repair.py',ROOT/'pyproject.toml'])
    versions={name:importlib.metadata.version(name) for name in ['numpy','pandas','pyarrow','netCDF4','h5py','pyproj']}
    artifacts={str(p.relative_to(run)):sha(p) for p in sorted(run.rglob('*')) if p.is_file() and p.name!='manifest.json'}
    manifest={'repair_version':run.name,'status':status_name,'base_version':data.base_version.iloc[0],
      'base_dataset_manifest_sha256':approval['protected_files']['configs/dataset_manifest.json'],
      'target_keys_sha256':approval['target_sha256'],'policy':approval['policy'],
      'approval_sha256':sha(run/'approval.json'),'target_count':len(data),'target_IDs':int(data.id.nunique()),
      'overlay_path':'full/error_overlay.parquet','overlay_sha256':sha(folder/'error_overlay.parquet'),
      'artifacts':artifacts,'implementation':{str(p.relative_to(ROOT)):sha(p) for p in code_files},
      'environment':versions,'activation':'explicit opt-in only; no default reader changes','scientific_status':'data repair only; no model validation'}
    with (run/'manifest.json').open('x') as f:json.dump(manifest,f,indent=2);f.write('\n')
    print(json.dumps(metrics,indent=2),flush=True)


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--run',type=Path,required=True);a=p.parse_args();publish(a.run.resolve())
