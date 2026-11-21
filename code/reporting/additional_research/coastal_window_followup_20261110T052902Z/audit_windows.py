"""Read-only seven-day window alignment, preserving all original definitions."""
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import resource
import time
import numpy as np
import pandas as pd

OUT = Path(__file__).resolve().parent
PRIOR = OUT.parent / 'coastal_grounding_20261110T043836Z'
ROOT = OUT.parent.parent / 'work_place'
BOUNDARY = ROOT / 'provenance/reviews/official_time_boundary_cohort_20261108'
KEY = ['id', 'origin_source_obs', 'horizon_days']

def sha(p):
    h = hashlib.sha256()
    with p.open('rb') as f:
        while block := f.read(8 * 1024**2):
            h.update(block)
    return h.hexdigest()

def main():
    start = time.monotonic()
    previous = json.loads((PRIOR / 'logs/output_manifest.json').read_text())
    for record in previous['files']:
        assert sha(PRIOR / record['path']) == record['sha256'], record['path']
    watched = [PRIOR / 'logs/output_manifest.json'] + [PRIOR / x['path'] for x in previous['files']]
    inputs = {}
    for path in watched:
        inputs[str(path)] = sha(path)
    manifest = json.loads((PRIOR / 'logs/input_manifest.json').read_text())
    ledger_path = BOUNDARY / 'boundary_ledger.csv'
    assert sha(ledger_path) == manifest[str(ledger_path.relative_to(ROOT))]['sha256']
    inputs[str(ledger_path)] = sha(ledger_path)
    ledger = pd.read_csv(ledger_path).set_index('id')
    directories = {}
    for name in ledger.source_file.unique():
        path = BOUNDARY / 'sources' / name
        assert sha(path) == manifest[str(path.relative_to(ROOT))]['sha256']
        inputs[str(path)] = sha(path)
        directories[name] = path.read_text().splitlines()
    for ident, row in ledger.iterrows():
        line = directories[row.source_file][int(row.source_line) - 1]
        assert line.strip() == row.official_row.strip()
        tokens = line.split()
        assert int(tokens[0]) == ident and int(tokens[-1]) == row.official_typedeath
        parsed = pd.Timestamp(' '.join(tokens[8:10]), tz='UTC').timestamp()
        assert parsed == row.official_end_epoch
    a = pd.read_parquet(PRIOR / 'results/origin_availability.parquet')
    e = pd.read_csv(PRIOR / 'results/id_evidence.csv')
    assert len(a) == 313029 and not a.duplicated(KEY).any()
    assert a.id.dtype.kind in 'iu' and e.id.dtype.kind in 'iu'
    assert a.groupby('cohort').id.nunique().to_dict() == {'train':338, 'validation':45}
    assert np.array_equal(a.target_epoch - a.origin_epoch, np.full(len(a), 7*86400))
    direct_end = a.id.map(ledger.official_end_epoch)
    direct_code = a.id.map(ledger.official_typedeath)
    assert np.array_equal(direct_end, a.official_end_epoch)
    assert np.array_equal(direct_code, a.official_typedeath)
    a['endpoint_vs_official_end'] = np.select(
        [a.target_epoch < direct_end, a.target_epoch == direct_end],
        ['before_last_good', 'at_last_good'], default='after_last_good')
    a['grounding_marker_window'] = direct_code.eq(1) & a.origin_epoch.lt(direct_end) & a.target_epoch.ge(direct_end)
    assert np.array_equal(a.grounding_marker_window, a.grounding_related_window)
    assert not (a.used_by_original & a.target_epoch.gt(direct_end)).any()
    assert a[a.used_by_original].groupby('cohort').size().to_dict() == {'train':265393, 'validation':33971}
    used_counts = a[a.used_by_original].groupby(['cohort','official_typedeath','endpoint_vs_official_end']).agg(pairs=('id','size'), ids=('id','nunique')).reset_index()
    used_counts.to_csv(OUT / 'used_window_relation.csv', index=False)
    relevant = a[a.grounding_marker_window].copy()
    relevant['target_UTC'] = pd.to_datetime(relevant.target_epoch, unit='s', utc=True)
    relevant['official_last_good_UTC'] = pd.to_datetime(relevant.official_end_epoch, unit='s', utc=True)
    columns = KEY + ['cohort','origin_time_UTC','target_UTC','official_last_good_UTC','used_by_original','endpoint_available','missing_endpoint','risk_set','reason_code','secondary_predicates','endpoint_vs_official_end','endpoint_lon_observed','endpoint_lat_observed']
    relevant[columns].to_csv(OUT / 'all_marker_window_candidates.csv', index=False)
    boundary = relevant[relevant.used_by_original].merge(e[['id','source_file','source_line','distance_lower_m','distance_upper_m','evidence_grade']], on='id',validate='many_to_one')
    boundary[columns + ['source_file','source_line','distance_lower_m','distance_upper_m','evidence_grade']].to_csv(OUT / 'used_boundary_cases.csv',index=False)
    records=[]
    for ident, g in a.groupby('id'):
        u=g[g.used_by_original]; w=g[g.grounding_marker_window]
        records.append({'id':int(ident),'cohort':g.cohort.iloc[0],'official_typedeath':int(g.official_typedeath.iloc[0]),
            'used_pairs':len(u),'used_before_last_good':int(u.endpoint_vs_official_end.eq('before_last_good').sum()),
            'used_at_last_good':int(u.endpoint_vs_official_end.eq('at_last_good').sum()),
            'used_after_last_good':int(u.endpoint_vs_official_end.eq('after_last_good').sum()),
            'grounding_marker_windows':len(w),'marker_window_missing':int(w.missing_endpoint.sum()),
            'marker_window_used':int(w.used_by_original.sum()),
            'marker_window_available_unused':int((w.endpoint_available & ~w.used_by_original).sum()),
            'event_time_known':False})
    ids = pd.DataFrame(records); ids.to_csv(OUT / 'per_id_window_audit.csv',index=False)
    summaries=[]
    for cohort,g in a.groupby('cohort'):
        u=g[g.used_by_original]; b=u[u.official_typedeath.eq(1)]; w=g[g.grounding_marker_window]
        summaries.append({'cohort':cohort,'ids':g.id.nunique(),'used_pairs':len(u),'eventual_grounding_ids':g[g.official_typedeath.eq(1)].id.nunique(),
            'used_pairs_from_eventual_grounding_ids':len(b),
            'used_grounding_before_last_good':int(b.endpoint_vs_official_end.eq('before_last_good').sum()),
            'used_grounding_at_last_good':int(b.endpoint_vs_official_end.eq('at_last_good').sum()),
            'used_grounding_after_last_good':int(b.endpoint_vs_official_end.eq('after_last_good').sum()),
            'marker_window_candidates':len(w),'marker_window_missing':int(w.missing_endpoint.sum()),
            'marker_window_missing_ids':w[w.missing_endpoint].id.nunique(),
            'marker_window_available_unused':int((w.endpoint_available&~w.used_by_original).sum())})
    summary=pd.DataFrame(summaries); summary.to_csv(OUT / 'summary.csv',index=False)
    # Independent row-wise arithmetic uses a dictionary from the original source ledger.
    second={c:{'before':0,'equal':0,'after':0,'missing':0,'all_windows':0} for c in ['train','validation']}
    for r in a.itertuples(index=False):
        end=float(ledger.at[r.id,'official_end_epoch']);code=int(ledger.at[r.id,'official_typedeath'])
        if code!=1: continue
        if r.used_by_original:
            label='before' if r.target_epoch<end else 'equal' if r.target_epoch==end else 'after'
            second[r.cohort][label]+=1
        if r.origin_epoch<end<=r.target_epoch:
            second[r.cohort]['all_windows']+=1
            second[r.cohort]['missing']+=int(r.missing_endpoint)
    for r in summary.itertuples(index=False):
        assert second[r.cohort]=={'before':r.used_grounding_before_last_good,'equal':r.used_grounding_at_last_good,'after':r.used_grounding_after_last_good,'missing':r.marker_window_missing,'all_windows':r.marker_window_candidates}
    assert e.event_lower_epoch.isna().all() and e.event_upper_epoch.isna().all()
    assert len(boundary)==2
    for path,digest in inputs.items(): assert sha(Path(path))==digest,path
    elapsed=time.monotonic()-start
    assert elapsed<300 and resource.getrusage(resource.RUSAGE_SELF).ru_maxrss < 6*1024**3
    (OUT/'verification.json').write_text(json.dumps({'passed':True,'recorded_at_utc':datetime.now(timezone.utc).isoformat(),'seconds':elapsed,
       'peak_rss_bytes':resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,'prior_artifacts_verified':len(previous['files']),
       'all_383_original_official_source_rows_reparsed':True,'independent_rowwise_counts_passed':True,'source_changes':0,
       'known_grounding_event_times':0,'new_predictions':0,'new_scores':0,'inputs':inputs},indent=2)+'\n')
    print(summary.to_string(index=False))
    print('verification passed',round(elapsed,3),'seconds')

if __name__=='__main__':main()
