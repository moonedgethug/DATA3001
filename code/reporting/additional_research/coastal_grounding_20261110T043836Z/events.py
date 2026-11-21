"""Evidence-only event review, with no synthetic event time or negative labels."""
import numpy as np
import pandas as pd
import shapely as sh
from pyproj import Geod
from runtime import *

GEOD=Geod(ellps='WGS84')

def main():
    s,roster=start()
    try:
      with stage('events') as check:
        f=pd.read_csv(RES/'id_evidence.csv')
        f['end_near_5km']=f.distance_upper_m.le(5000)
        f['end_on_mapped_land']=f.group.eq('land_or_boundary')
        # A source conflict and eventual code stay separate; no automatic relabelling.
        raw=s.frame(AUDIT/'boundary_ledger.csv').set_index('id')
        receipts=s.json(AUDIT/'source_receipts.json')
        directories={}
        for r in receipts:
            p=s.verified(AUDIT/'sources'/r['name'],r['sha256'])
            directories[r['name']]=p.read_text().splitlines()
        for row in f.itertuples(index=False):
            b=raw.loc[row.id]
            line=directories[b.source_file][int(b.source_line)-1]
            assert line.strip()==str(b.official_row).strip(),('official source text',row.id)
            fields=line.split();assert int(fields[0])==row.id and int(fields[-1])==int(row.official_typedeath)
        selected=[];used=set()
        for category,mask in [('official_grounding',f.official_typedeath.eq(1)),
                ('unknown_coastal',f.official_typedeath.isin([3,4])&f.end_near_5km),
                ('conflict',f.metadata_conflict)]:
            candidates=f[mask&~f.id.isin(used)].assign(relevant=lambda x:x.official_end_windows.gt(0))
            picked=candidates.sort_values(['relevant','id'],ascending=[False,True]).head(4)
            used.update(picked.id);selected.extend([(int(i),category) for i in picked.id])
        tail=pd.read_parquet(RES/'terminal_windows.parquet')
        review=[];samples=[]
        for ident,category in selected:
            row=f.set_index('id').loc[ident]
            z=tail[tail.id.eq(ident)].sort_values('time')
            valid=z[z.position_ok&z.analytical_row]
            before=valid[valid.time.le(row.official_end_epoch)]
            last=before.iloc[-1]
            separation=GEOD.inv(last.lon_normalized,last.lat,row.lon,row.lat)[2]/1000
            post=valid[valid.time.gt(row.official_end_epoch)]
            if row.metadata_conflict:
                grade='source_conflict'
                note='原生与目录结束信息存在已登记冲突；保留双方。当前已用配对在既有共同有效范围内；不能以本轮推断修复标签。'
            elif category=='official_grounding':
                grade='official_marker_only'
                note='官方最终搁浅标记保留；末段没有足够证据确定首次持续停留时刻。官方最后有效时间与实际搁浅时间不得等同。'
                if row.distance_lower_m>5000:
                    note+=' 最后有效坐标距映射海岸超过5 km；可能涉及最后海上定位、浅滩或其他未核实机制，本轮未引入水深证据。'
                if not row.stagnation_check_available:note+=' 七天停滞筛查窗口不完整，不能计算停滞提示。'
            else:
                grade='suspected_unconfirmed'
                note='停止发报且最后有效坐标靠岸，是复核候选；未发现足够证据把它确认为搁浅，不能作为未搁浅阴性样本。'
            i=f.index[f.id.eq(ident)][0]
            f.loc[i,'manual_reviewed']=False;f.loc[i,'evidence_grade']=grade
            record=dict(id=ident,cohort=row.cohort,review_category=category,official_typedeath=int(row.official_typedeath),
                source_reference=f'{row.source_file}:{int(row.source_line)}',official_end_epoch=row.official_end_epoch,
                last_retained_before_epoch=last.time,last_retained_before_source_obs=int(last.source_obs),
                last_retained_before_lon=last.lon_normalized,last_retained_before_lat=last.lat,
                last_to_official_coordinate_km=float(separation),post_boundary_records=len(post),
                event_location=row.event_location,end_coast_distance_lower_km=row.distance_lower_m/1000,
                end_coast_distance_upper_km=row.distance_upper_m/1000,window_hours=int(row.window_hours),max_gap_hours=row.max_gap_hours,
                net_7d_km=row.net_7d_km,window_radius_km=row.window_radius_km,stagnation_hint=bool(row.stagnation_hint),
                official_end_windows=int(row.official_end_windows),grounding_related_missing=int(row.grounding_related_missing),
                event_lower_epoch=None,event_upper_epoch=None,evidence_grade=grade,review_note=note,review_status='ready_for_individual_review')
            review.append(record)
            wanted=[row.official_end_epoch-x*86400 for x in [14,7,3,1,0]]
            positions=set(int(np.argmin(np.abs(valid.time.to_numpy()-t))) for t in wanted)
            for p in sorted(positions):
                v=valid.iloc[p]
                samples.append(dict(id=ident,source_obs=int(v.source_obs),time_epoch=v.time,time_UTC=pd.Timestamp(v.time,unit='s',tz='UTC').isoformat(),lon=v.lon_normalized,lat=v.lat))
            check()
        save_frame('id_evidence.csv',f)
        save_frame('case_review.csv',pd.DataFrame(review));save_frame('case_timeline_samples.csv',pd.DataFrame(samples))
        counts=f.groupby(['cohort','official_typedeath','official_status','evidence_grade'],dropna=False).agg(ids=('id','size'),used_pairs=('used_pairs','sum')).reset_index()
        counts['cohort_id_fraction']=counts.ids/counts.cohort.map({'train':338,'validation':45})
        save_frame('official_status_summary.csv',counts)
        save_frame('grounding_location_summary.csv',f[f.official_typedeath.eq(1)].groupby(['cohort','event_location'],dropna=False).agg(ids=('id','size'),windows=('official_end_windows','sum'),missing=('grounding_related_missing','sum')).reset_index())
        json_write(LOG/'event_checks.json',{'passed':True,'ids':len(f),'all_official_rows_verified_against_cached_source':True,
            'manual_reviewed':0,'review_ready':len(review),'unreviewed_conflict_ids':f[f.metadata_conflict&~f.manual_reviewed].id.astype('int64').tolist(),
            'precise_grounding_intervals_established':0,'automatic_training_labels_created':0,'new_source_downloads':0})
        print(pd.DataFrame(review)[['id','review_category','evidence_grade','grounding_related_missing','last_to_official_coordinate_km']].to_string(index=False),flush=True)
    finally:s.save()

if __name__=='__main__':main()
