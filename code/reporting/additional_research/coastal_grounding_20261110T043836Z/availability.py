"""Reconcile the preserved candidate ledger, never rebuild or alter model pairs."""
import json,time
import numpy as np
import pandas as pd
from pyproj import Geod
from diagnostic import *
from runtime import *

GEOD=Geod(ellps='WGS84')

def main():
    s,roster=start()
    try:
      with stage('availability') as check:
        assert json.loads((LOG/'preflight.json').read_text())['passed']
        dm=s.json(ROOT/'configs/dataset_manifest.json');qm=s.json(ROOT/'configs/qualification_manifest.json')
        boundary=s.frame(AUDIT/'boundary_assessment.csv').set_index('id')
        used_train=s.frame(E7/'training_coordinates.parquet',columns=KEY)
        used_valid=s.frame(E7/'query_coordinates.parquet',columns=KEY)
        used=pd.concat([used_train.assign(cohort='train'),used_valid.assign(cohort='validation')])
        label_receipt=s.json(ROOT/'provenance/runs/markov_input_20261025T095949_830292Z/outputs.json')['output_sha256']
        parts=[];events=[];tails=[];timings=[]
        cut=pd.Timestamp('2020-01-01',tz='UTC').timestamp()
        v_end=pd.Timestamp('2023-01-01',tz='UTC').timestamp()
        t_start=pd.Timestamp('2001-01-01',tz='UTC').timestamp()
        for number,row in enumerate(roster.sort_values('id').itertuples(index=False),1):
            t=time.monotonic();sid=str(row.id);r=dm['records'][sid];q=qm['records'][sid]
            track=s.frame(ROOT/r['path'],r['sha256'],columns=['id','source_obs','time','lon_normalized','lat','typedeath','end_date'])
            flags=s.frame(ROOT/q['path'],q['sha256'])
            assert np.array_equal(track[['source_obs','time']].to_numpy(),flags[['source_obs','time']].to_numpy())
            assert len(track)==r['rows'] and track.id.eq(row.id).all()
            assert not track.source_obs.duplicated().any()
            lp=LABELS/(sid+'.parquet')
            labels=s.frame(lp,label_receipt[str(lp.relative_to(ROOT))],filters=[('horizon_days','==',7)])
            assert labels.target.eq('stopped').all() and labels.scenario.eq('pooled').all() and labels.tolerance_hours.eq(0).all()
            assert not labels.duplicated(KEY).any()
            orig_mask=flags.analytical_row&flags.position_ok&flags.in_R
            start_epoch=t_start if row.cohort=='train' else cut
            end_epoch=cut if row.cohort=='train' else v_end
            time_mask=track.time.ge(start_epoch)&track.time.lt(end_epoch)
            expected=set(track.loc[orig_mask&time_mask,'source_obs'].astype('int64'))
            epoch=(labels.origin_time_UTC-pd.Timestamp('1970-01-01',tz='UTC')).dt.total_seconds()
            f=labels.loc[epoch.ge(start_epoch)&epoch.lt(end_epoch)].copy()
            assert set(f.origin_source_obs.astype('int64'))==expected,('candidate coverage',sid,len(f),len(expected))
            f['origin_epoch']=(f.origin_time_UTC-pd.Timestamp('1970-01-01',tz='UTC')).dt.total_seconds()
            f['cohort']=row.cohort
            f['role_excluded']=f.required_interval_end_epoch.ge(cut) if row.cohort=='train' else False
            f['used_by_original']=f.origin_source_obs.isin(used.loc[used.id==row.id,'origin_source_obs'])
            eligible=f.reason_code.eq(0)&~f.role_excluded
            assert np.array_equal(eligible,f.used_by_original),('frozen eligibility',sid)
            pos=pd.Index(track.source_obs).get_indexer(f.origin_source_obs);assert (pos>=0).all()
            f['lon']=track.lon_normalized.to_numpy()[pos];f['lat']=track.lat.to_numpy()[pos]
            analytical=track[flags.analytical_row.to_numpy()].copy()
            af=flags[flags.analytical_row.to_numpy()]
            assert not analytical.time.duplicated().any()
            ix=pd.Index(analytical.time).get_indexer(f.target_epoch)
            good=ix>=0;safe=np.maximum(ix,0)
            f['target_timestamp_present']=good
            f['endpoint_available']=good&af.position_ok.to_numpy()[safe]&af.mapping_ok.to_numpy()[safe]
            f['endpoint_lon_observed']=np.where(good,analytical.lon_normalized.to_numpy()[safe],np.nan)
            f['endpoint_lat_observed']=np.where(good,analytical.lat.to_numpy()[safe],np.nan)
            f['track_last_epoch']=track.time.max()
            f['past_retained_track_end']=f.target_epoch.gt(track.time.max())
            b=boundary.loc[row.id]
            code=b.official_typedeath;end=float(b.official_end_epoch)
            f['official_typedeath']=int(code) if pd.notna(code) else -1
            f['official_end_epoch']=end
            f['official_end_in_window']=np.isfinite(end)&f.origin_epoch.lt(end)&f.target_epoch.ge(end)
            f['official_target_after_boundary']=np.isfinite(end)&f.target_epoch.gt(end)
            f['grounding_related_window']=f.official_end_in_window&(code==1)
            f['event_time_relation']='event_time_unknown'
            f=availability_flags(f)
            f['grounding_related_missing']=f.missing_endpoint&f.grounding_related_window
            if int(code)==0:termination='alive_at_source_or_source_cutoff'
            elif not np.isfinite(end):termination='unresolved'
            else:termination='official_termination_recorded_cause_'+str(int(code))
            f['termination_evidence']=termination
            f['native_typedeath']=b.native_typedeath
            parts.append(f)
            finite_end=np.isfinite(end) and end>0
            tailmask=track.time.between(end-14*86400,end+7*86400) if finite_end else track.time.ge(track.time.max()-14*86400)
            tail=track.loc[tailmask].copy()
            tail['position_ok']=flags.loc[tailmask,'position_ok'].to_numpy()
            tail['mapping_ok']=flags.loc[tailmask,'mapping_ok'].to_numpy()
            tail['analytical_row']=flags.loc[tailmask,'analytical_row'].to_numpy()
            tails.append(tail)
            # Data quality and end metadata only; no inferred first-grounding time.
            ev={k:b[k] for k in ['cohort','native_typedeath','official_typedeath','official_end_epoch','official_end_lat','official_end_lon','native_end_epoch','boundary_status','assessment','source_file','source_line']}
            ev.update(id=int(row.id),official_status=official_status(code),
                canonical_last_epoch=float(track.time.max()),candidate_origins=len(f),
                used_pairs=int(f.used_by_original.sum()),risk_count=int(f.risk_set.sum()),missing_count=int(f.missing_endpoint.sum()),
                official_end_windows=int(f.official_end_in_window.sum()),grounding_related_missing=int(f.grounding_related_missing.sum()),
                event_lower_epoch=None,event_upper_epoch=None,event_time_precision='unknown',
                evidence_grade='official_marker_only' if code==1 else 'insufficient_evidence',manual_reviewed=False)
            conflict=metadata_conflict(b.native_typedeath,code,b.assessment)
            ev['metadata_conflict']=bool(conflict)
            if conflict:ev['evidence_grade']='source_conflict'
            valid=track[(flags.analytical_row&flags.position_ok).to_numpy()]
            endrow=valid[valid.time.le(end)].tail(1) if finite_end else valid.tail(1)
            ev.update(stagnation_check_available=False,stagnation_hint=False,window_hours=0,max_gap_hours=None,
                      net_7d_km=None,window_radius_km=None,observed_path_km=None)
            if len(endrow):
                t1=endrow.time.iloc[0];win=valid[valid.time.between(t1-168*3600,t1)].sort_values('time')
                gaps=np.diff(win.time.to_numpy())/3600;gap=float(gaps.max()) if len(gaps) else None
                available=len(win)>=136 and win.time.iloc[0]==t1-168*3600 and gap<=6
                ev.update(window_hours=len(win),max_gap_hours=gap,stagnation_check_available=bool(available))
                if available:
                    a=win.iloc[0];z=win.iloc[-1]
                    net=GEOD.inv(a.lon_normalized,a.lat,z.lon_normalized,z.lat)[2]/1000
                    distances=GEOD.inv(np.full(len(win),z.lon_normalized),np.full(len(win),z.lat),win.lon_normalized,win.lat)[2]/1000
                    travel=GEOD.inv(win.lon_normalized.to_numpy()[:-1],win.lat.to_numpy()[:-1],win.lon_normalized.to_numpy()[1:],win.lat.to_numpy()[1:])[2].sum()/1000
                    ev.update(net_7d_km=float(net),window_radius_km=float(max(distances)),observed_path_km=float(travel),stagnation_hint=bool(net<1))
            events.append(ev);timings.append(time.monotonic()-t)
            if number==10:
                estimate=float(sum(timings)/10*383)
                json_write(LOG/'ten_id_projection.json',{'ids':10,'seconds':sum(timings),'projected_all_seconds':estimate,'budget_stage_seconds':1800})
                if estimate>1800:raise RuntimeError('Full availability projected above stage budget')
            if number%25==0:print('Availability IDs',number,'seconds',round(sum(timings),1),flush=True)
            check()
        allf=pd.concat(parts,ignore_index=True)
        assert allf.groupby('cohort').used_by_original.sum().to_dict()=={'train':265393,'validation':33971}
        save_frame('origin_availability.parquet',allf)
        save_frame('id_evidence.csv',pd.DataFrame(events))
        save_frame('terminal_windows.parquet',pd.concat(tails,ignore_index=True))
        perid=availability_by_id(allf).merge(roster[['id','cohort']],on='id',validate='one_to_one')
        save_frame('availability_per_id.csv',perid)
        summary=[]
        for cohort,g in allf.groupby('cohort'):
            pi=perid[perid.cohort==cohort]
            summary.append(dict(cohort=cohort,ids=g.id.nunique(),candidates=len(g),used=int(g.used_by_original.sum()),
                administrative=int(g.administrative_excluded.sum()),known_exit=int(g.known_exit.sum()),risk=int(g.risk_set.sum()),
                missing=int(g.missing_endpoint.sum()),missing_pair_rate=float(g.missing_endpoint.sum()/g.risk_set.sum()),
                missing_id_equal_rate=float(pi.missing_rate.mean()),zero_risk_ids=int(pi.risk_count.eq(0).sum()),
                grounding_related_missing=int(g.grounding_related_missing.sum()),grounding_missing_ids=int(g[g.grounding_related_missing].id.nunique())))
        save_frame('availability_summary.csv',pd.DataFrame(summary))
        reasons=allf.groupby(['cohort','reason_code']).agg(origins=('id','size'),ids=('id','nunique')).reset_index()
        save_frame('original_reason_counts.csv',reasons)
        cross=allf.groupby(['cohort','official_typedeath']).agg(candidates=('id','size'),ids=('id','nunique'),
            used=('used_by_original','sum'),risk=('risk_set','sum'),missing=('missing_endpoint','sum'),
            official_end_windows=('official_end_in_window','sum'),grounding_related_missing=('grounding_related_missing','sum')).reset_index()
        save_frame('availability_by_death.csv',cross)
        json_write(LOG/'availability_checks.json',{'passed':True,'ids':len(events),'candidate_rows':len(allf),
            'all_candidate_keys_match_canonical_qualification':True,'used_keys_exactly_reconciled':True,
            'first_10_ids_projection_passed':True,'terminal_time_is_not_grounding_time':True})
        print(pd.DataFrame(summary).to_string(index=False),flush=True)
    finally:s.save()

if __name__=='__main__':main()
