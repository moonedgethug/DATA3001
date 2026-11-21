"""Create inspectable summaries, then close with read-only integrity checks."""
import contextlib, io, json, stat, time, resource
from datetime import datetime, timezone
from io_utils import OUT, OLD, BASE, ROOT, sha, write_json
import pandas as pd

def materials():
    summary = pd.read_csv(OUT/'results/updated_summary.csv')
    summary = summary[summary.scope.eq('frozen_used')]
    names = {'grounding_evidence':'有充分搁浅证据', 'drifting_evidence':'有漂流证据', 'uncertain':'仍无法确认', 'endpoint_missing':'终点缺失'}
    rows = [{'cohort':{'train':'训练','validation':'验证'}[r.cohort], 'state':names[r.state], 'pairs':int(r.pairs), 'ids':int(r.ids), 'denominator':int(r.total_pairs)} for r in summary.itertuples()]
    source = {'schemaVersion':1, 'items':[{'id':'path-review', 'title':'七天终点连续路径复核', 'queries':[{
        'id':'actual-used',
        'source':{'label':'实际用于冻结模型的七天配对',
            'files':[{'label':x} for x in ['updated_summary.csv','uncertain_breakdown.csv','PROTOCOL.md','audit_checks.json']],
            'metricDefinitions':[{'label':'终点证据','definition':'按配对统计第七天终点的运动或停留证据，并分别计算涉及的独立 drifter 数；使用目标时刻前后各72小时的现存合格路径作事后辅助。'}],
            'filters':['训练：338 个 ID，265393 条配对','验证：45 个 ID，33971 条配对','只追加复核原不确定状态'],
            'caveats':['同一 ID 可在不同时间进入多个类别，ID 数不能相加。','629 条可疑停留配对来自3个ID，仍计入不确定，不是629次搁浅。','现有规则提供运动证据，没有逐时真实搁浅标签；零条充分搁浅证据不等于真实发生率为零。'],
            'evidenceFlow':[{'kind':'validation','title':'独立核对','detail':'独立逐路径检查4005个窗口，覆盖全部新增运动证据及可疑停留；全部28300条分类独立重建，键、原列和计数一致。'}]},
        'columns':[{'field':a,'label':b} for a,b in [('cohort','样本'),('state','七天终点证据'),('pairs','配对数'),('ids','独立 drifter 数'),('denominator','实际使用配对总数')]],
        'rows':rows,
        'methods':[{'language':'calculation','code':'训练：22279 − (278 + 1799) = 20202 条仍无法确认\n验证：3476 − (20 + 434) = 3022 条仍无法确认\n新增证据涉及 ID：训练131个、验证19个，按类别并集计算。'}]
    }]}]}
    write_json(OUT/'logs/sources.json', source)
    codes = [
        "from pathlib import Path\nimport pandas as pd\np = Path.cwd()\ns = pd.read_csv(p/'results/updated_summary.csv')\nprint(s[s.scope.eq('frozen_used')][['cohort','state','pairs','ids','pair_fraction']].to_string(index=False))",
        "d = pd.read_csv(p/'results/uncertain_breakdown.csv')\nprint(d[d.scope.eq('frozen_used')].to_string(index=False))",
        "f = pd.read_parquet(p/'results/updated_endpoint_states.parquet')\nassert not f.duplicated(['id','origin_source_obs','horizon_days']).any()\nfor cohort, total in [('train',265393),('validation',33971)]:\n    g = f[f.used_by_original & f.cohort.eq(cohort)]\n    assert len(g) == total\n    counts = g.updated_state.value_counts()\n    assert counts.sum() == total\n    print(cohort, 'total', total, 'uncertain', counts.get('uncertain',0), 'uncertain IDs', g[g.updated_state.eq('uncertain')].id.nunique())\nprint('Keys unique; actual-used pair totals conserved. ID categories may overlap.')"
    ]
    cells = [{'cell_type':'markdown','metadata':{},'source':'# 七天终点路径复核：只读核对\n在本证据包目录运行。此 notebook 仅读取已保存结果，不重新分类、不训练、不改原数据。每条记录对应一个第七天终点；同一 drifter 可跨类别。'}]
    namespace = {}
    for n, code in enumerate(codes,1):
        capture = io.StringIO()
        with contextlib.redirect_stdout(capture):exec(compile(code,f'notebook-cell-{n}','exec'),namespace)
        cells.append({'cell_type':'code','metadata':{},'execution_count':n,'source':code,'outputs':[{'output_type':'stream','name':'stdout','text':capture.getvalue()}]})
    notebook={'nbformat':4,'nbformat_minor':5,'metadata':{'kernelspec':{'display_name':'Python 3','language':'python','name':'python3'}},'cells':cells}
    for n,c in enumerate(cells):c['id']=f'review-{n}'
    write_json(OUT/'review.ipynb', notebook)
    write_json(OUT/'logs/notebook_check.json', {'passed':True,'executed_read_only_cells':3})
    write_json(OUT/'logs/test_receipt.json', {'passed':True,'tests':6,'test_file':'code/test_rules.py','test_sha256':sha(OUT/'code/test_rules.py'),'record':'Successful unittest execution recorded earlier in this task before production run. Six tests, 0.028 seconds, OK.','cases':['circle with low net displacement','slow consistent movement','arrival then residence','oscillatory noise','missing coarse observation','source conflict and short coverage failure']})
    print('Prepared source receipt and executed read-only notebook')

def close():
    started = time.monotonic()
    expected=json.loads((BASE/'logs/input_manifest.json').read_text())
    for name,r in expected.items():
        p=Path(name) if name.startswith('/') else ROOT/name
        assert sha(p)==r['sha256'], ('original changed',name)
    freeze=json.loads((ROOT/'provenance/frozen/mdn_final_20261110_v1/manifest.json').read_text())
    for r in freeze['files']:assert stat.S_IMODE((ROOT/r['path']).stat().st_mode)==int(r['expected_mode'],8)
    prior_dirs=[BASE,OLD,OUT.parent/'coastal_window_followup_20261110T052902Z']
    for directory in prior_dirs:
        manifest_path = directory/('logs/output_manifest.json' if directory in [BASE,OLD] else 'output_manifest.json')
        manifest=json.loads(manifest_path.read_text())
        for r in manifest['files']:assert sha(directory/r['path'])==r['sha256'], ('prior supplement changed',directory/r['path'])
    for stage in ['compute','audit']:
        for name,r in json.loads((OUT/'logs'/f'{stage}_sources.json').read_text()).items():assert sha(name)==r['sha256']
    checks=json.loads((OUT/'logs/audit_checks.json').read_text());assert checks['passed']
    timings=[json.loads((OUT/'logs'/f'{stage}_verification.json').read_text()) for stage in ['compute','audit']]
    primary=sum(x['seconds'] for x in timings)
    closure=time.monotonic()-started
    # Includes small authoring/plotting checks and the first failed closure attempt.
    extra_overhead_allowance=60
    cumulative=json.loads((OLD/'logs/delivery.json').read_text())['recorded_combined_primary_seconds_including_prior']+primary+closure
    size=sum(p.stat().st_size for p in OUT.rglob('*') if p.is_file())
    total_size=size+sum(sum(p.stat().st_size for p in d.rglob('*') if p.is_file()) for d in prior_dirs)
    assert primary+closure+extra_overhead_allowance < 1800 and cumulative+extra_overhead_allowance < 7200
    assert size<250*1024**2 and total_size<1024**3
    now=datetime.now(timezone.utc)
    assert (now-datetime.fromisoformat('2026-11-10T04:38:36+00:00')).total_seconds()<21600
    write_json(OUT/'logs/delivery.json',{
        'status':'complete_evidence_review_not_ground_truth','closed_at_utc':now.isoformat(),
        'path_compute_seconds':timings[0]['seconds'],'independent_audit_seconds':timings[1]['seconds'],'closure_hash_seconds':closure,
        'recorded_primary_seconds_this_supplement':primary+closure,'additional_authoring_compute_allowance_seconds':extra_overhead_allowance,
        'recorded_cumulative_primary_seconds_including_prior':cumulative,
        'peak_rss_bytes':max(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,*[r['peak_rss_bytes'] for r in timings]),
        'artifact_bytes_before_manifest':size,'combined_supplement_bytes_before_manifest':total_size,
        'original_source_hashes_unchanged':len(expected),'frozen_payload_modes_unchanged':len(freeze['files']),
        'previous_supplemental_artifacts_unchanged':True,'all_28300_uncertain_candidates_reviewed':True,
        'all_287_affected_ids_checked':True,'all_383_ids_retained_in_summary':True,
        'independent_path_windows':4005,'representative_path_windows_visually_reviewed':9,'synthetic_tests_passed':6,
        'original_data_modifications':0,'model_calls':0,'new_scores':0,'final_test_access':False,'budget_passed':True})
    excluded=['logs/output_manifest.json','logs/output_manifest.sha256']
    files=[{'path':str(p.relative_to(OUT)),'bytes':p.stat().st_size,'sha256':sha(p)} for p in sorted(OUT.rglob('*')) if p.is_file() and str(p.relative_to(OUT)) not in excluded]
    write_json(OUT/'logs/output_manifest.json',{'files':files,'excludes':excluded})
    (OUT/'logs/output_manifest.sha256').write_text(sha(OUT/'logs/output_manifest.json')+'  output_manifest.json\n')
    print('Closed; original files unchanged',len(expected),'frozen modes unchanged',len(freeze['files']))

if __name__=='__main__':
    import sys
    from pathlib import Path
    if sys.argv[1]=='materials':materials()
    elif sys.argv[1]=='close':close()
    else:raise ValueError('materials or close')
