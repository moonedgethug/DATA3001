"""Saved-output audit, resource projections and a diagnostic research figure."""
import hashlib
import json
import math
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

HERE=Path(__file__).resolve().parent
PROV=HERE.parent
ROOT=HERE.parents[3]
OUT=ROOT/'results/deliverables/conditional_mdn_s5_e3_optimization'
OUT.mkdir(parents=True,exist_ok=True)
read=lambda name:json.loads((HERE/name).read_text())
a,b,c=read('stage_A.json'),read('stage_B.json'),read('stage_C.json')
approval=read('approval.json')
legacy=json.loads((PROV/'pilot_result.json').read_text())
ledger=json.loads((PROV/'resource_ledger.json').read_text())


def sha(path):
    h=hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda:f.read(1024*1024),b''):h.update(chunk)
    return h.hexdigest()


changed=[p for p,h in approval['old_artifacts_sha256'].items() if sha(ROOT/p)!=h]
if changed:raise ValueError('Frozen files changed: '+str(changed))
assert c['queries']==128 and c['probe_records']==768 and c['all_exact_value_equal']
assert c['single_two_worker_identical'] and c['old_frozen_results_reproduced']
comparisons=[json.loads(p.read_text()) for p in sorted((HERE/'comparison_rows').glob('*.json'))]
assert len(comparisons)==128
raw_stats={}
for backend in ('old','new'):
    raw_stats[backend]={}
    for k in (1,2,4,8,16,32):
        timings=[next(x for x in r[backend] if x['K']==k)['timing'] for r in comparisons]
        raw_stats[backend][str(k)]={field:float(np.quantile([t[field] for t in timings],.95)) for field in timings[0]}
for row in comparisons:
    left=[{k:v for k,v in r.items() if k!='timing'} for r in row['old']]
    right=[{k:v for k,v in r.items() if k!='timing'} for r in row['new']]
    assert left==right
for row in b['rows']:
    delta=row['main']['energy_km']-row['reference']['energy_km']
    limit=3*math.sqrt(row['main']['variance']+row['reference']['variance'])
    assert delta==row['difference_km'] and limit==row['three_se_km'] and abs(delta)<=limit
assert len({(r['role'],r['position'],r['K'],r['count']) for r in b['rows']})==96
sum_reference_old=sum(r['reference'] for r in legacy['p95_worker_timing_seconds'].values())
refs={n:sum(float(np.quantile([r['seconds'] for r in b['rows'] if r['K']==k and r['count']==n],.95))
            for k in (1,2,4,8,16,32)) for n in (65536,262144)}
forecasts={}
# This is a conservative first-paired-job allowance, not isolated optimized startup latency.
cold=c['cold_plus_first_paired_query_seconds']
for backend,ts in raw_stats.items():
    energy=sum(t['energy']+t['parameters'] for t in ts.values())
    region=sum(t['region'] for t in ts.values())
    audit=sum(t['audit_energy']+t['audit_region']+t['parameters'] for t in ts.values())
    forecasts[backend]={
        'inner_scoring':1.5*(cold+86373*(energy+2*max(t['region'] for t in ts.values()))/2+300)/3600,
        'outer_scoring':1.5*(cold+33971*(energy+region)/2+300)/3600,
        'audit_original_reference':1.5*(cold+33971*audit/2+128*sum_reference_old/2+300)/3600}
    for n in refs:
        # Keep the old reference+IID allowance and ADD enhanced-reference cost:
        # conservative (double counts the old component part), explicitly labelled.
        forecasts[backend]['audit_if_reference_'+str(n)]=forecasts[backend]['audit_original_reference']+1.5*128*refs[n]/2/3600
total_time={backend:sum(sum(x['timing'].values()) for r in comparisons for x in r[backend])
            for backend in ('old','new')}
speedup=total_time['old']/total_time['new']
saved=1-total_time['new']/total_time['old']
stage_time={}
for e in ledger['entries']:
    if e['label'].startswith('optv1_'):
        stage=e['label'].split('_')[1];stage_time[stage]=stage_time.get(stage,0.)+e['elapsed_seconds']
peak=max(e.get('peak_process_tree_rss_bytes',0) for e in ledger['entries'] if e['label'].startswith('optv1_'))/2**30
failed_table=[]
for k in (1,2,4,16):
    at=[r for r in b['rows'] if r['role']=='C_T0' and r['position']==41760 and r['K']==k]
    high=next(r for r in at if r['count']==262144)
    old_delta=high['main']['energy_km']-high['original_reference']['energy_km']
    failed_table.append((k,old_delta,high['difference_km'],high['three_se_km']))

plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                     'axes.spines.right':False,'figure.facecolor':'white'})
fig,axs=plt.subplots(1,2,figsize=(13,5.6))
for k,color in zip((1,2,4,16),('#356886','#b87928','#737e43','#a46682')):
    rs=[r for r in b['rows'] if r['role']=='C_T0' and r['position']==41760 and r['K']==k]
    rs.sort(key=lambda r:r['count'])
    original=rs[0]['main']['energy_km']-rs[0]['original_reference']['energy_km']
    axs[0].plot([8192,65536,262144],[original]+[r['difference_km'] for r in rs],marker='o',color=color,
                label=f'K{k}'+(' pilot' if k==1 else ' fixture'))
axs[0].axhline(0,color='#333333',lw=1)
axs[0].set(xscale='log',xticks=[8192,65536,262144],xticklabels=['8,192','65,536','262,144'],
           xlabel='Reference nodes per component / pair',ylabel='Main minus reference ES (km)',
           title='Same query; main ES remains unchanged')
axs[0].legend(frameon=False,fontsize=9)
fields=['energy','region','audit_energy','audit_region']
names=['Main ES','Main region','Audit ES','Audit region']
y=np.arange(4)
for i,backend in enumerate(('old','new')):
    means=[np.mean([x['timing'][field] for r in comparisons for x in r[backend]])*1000 for field in fields]
    axs[1].barh(y+(i-.5)*.32,means,height=.30,label='Original' if i==0 else 'Optimized',
                 color='#8b939b' if i==0 else '#356886')
axs[1].set(yticks=y,yticklabels=names,xlabel='Mean milliseconds per query / distribution',
           title='Matched two-worker measurements')
axs[1].invert_yaxis();axs[1].legend(frameon=False,fontsize=9)
for ax in axs:ax.grid(axis='x',alpha=.15);ax.set_axisbelow(True)
fig.suptitle('MDN numerical diagnosis and equivalent optimization',x=.055,ha='left',weight='bold',fontsize=16)
fig.text(.055,.08,'All 48 reference checks pass at both higher levels. All 768 old/new outputs are exactly value-equal.',fontsize=10)
fig.text(.055,.04,'Engineering validation only: no K selection, formal training or predictive-performance comparison.',fontsize=10)
fig.subplots_adjust(left=.075,right=.98,bottom=.24,top=.82,wspace=.42)
fig.savefig(OUT/'diagnostics.png',dpi=180);plt.close(fig)

ft='\n'.join(f'| K{k}'+(' 试跑网络' if k==1 else ' 合成分布')+f' | {d0:+.6f} | {d1:+.6f} | {lim:.6f} | 通过 |'
             for k,d0,d1,lim in failed_table)
forecast_table='\n'.join(f"| {label} | {forecasts['old'][key]:.2f} h | {forecasts['new'][key]:.2f} h | {cap} h |"
    for key,label,cap in [('inner_scoring','内层评分',12),('outer_scoring','外层评分',5),('audit_original_reference','独立复核（原参考检查）',4)])
new=forecasts['new'];sum_score=new['inner_scoring']+new['outer_scoring']+new['audit_original_reference']
sum_score_enhanced=new['inner_scoring']+new['outer_scoring']+new['audit_if_reference_65536']
profile=a['profile'];operation=sum(profile['operation_totals'].values())
geo=profile['function_timings']['to_geographic']['seconds']/operation
land=profile['function_timings']['geography_masses']['seconds']/operation
report=f'''# Step 5 E3：数值诊断与等价优化复核

**本轮有界验证已完成；正式实验仍停止。没有训练新模型、选择 K 或生成正式预测性能结论。**

![诊断与耗时对照]({OUT/'diagnostics.png'})

## 4 项 ES 差异的原因判断

证据支持原 8,192 节点参考积分在该查询的随机化误差较大。48 项同节点对照最大 ES 分项差 {max(x['max_term_difference_km'] for x in a['matched_node_checks']):.3g} km，未发现相同输入下的算法差异。主计算、模型参数、权重和种子未变；对原全部 48 项参考检查增加预定的 65,536、262,144 两档节点后，两档均 48/48 通过。

| 原失败分布 | 原差值 km | 262,144 参考节点时差值 km | 当前允许合并 3SE km | 结果 |
|---|---:|---:|---:|---|
{ft}

四项来自同一查询，K2/4/16 是由 K1 构造的合成测试分布，不能作为四次独立模型失败。结果强烈支持“参考计算分辨率不足／相关随机化波动”，没有证据表明主 ES 公式错误；有限数值验证不等于证明任何输入都无错误。原 8,192 节点的失败记录与原始门槛状态全部保留，增强参考只是本轮诊断，未自动改写正式合同。

## 数值一致性

- 完整固定 128 查询 × 六组分布，共 768 条对照，主/审计 ES 和区域全部**逐项数值完全相等**；没有使用允许的舍入容差来掩盖差异。
- 原实现精确复现历史试跑输出；新旧区域参数、分类点坐标、权重和质量输出相同，因此相同几何函数得到的逐点分类相同。
- 单 worker 与双 worker 一致性在完整比较之前通过；主计算与独立审计保持独立随机流。
- 46 项 MDN 回归测试和 2 项验证程序停止/完整比较检查通过。两项复核发现已修复：异常时取消剩余任务，以及拒绝任何遗漏字段的结果差异。
- 全部 {len(approval['old_artifacts_sha256'])} 个冻结文件校验值不变。新增优化入口独立保存，尚未接入正式实验入口。

## 实际加速与瓶颈

同机、双 worker、交替新旧执行顺序的完整对照，包含参数准备及主/审计 ES、区域操作：**加速 {speedup:.3f} 倍，操作耗时减少 {saved*100:.2f}%**。这是完整试跑数值操作的实测值，不是整个实验的加速承诺；不包括进程启动及落盘。参数准备已计入。

分项分析中，WGS84 地理映射约占 {geo*100:.1f}%，陆地／域外判定约占 {land*100:.1f}%。缓存随机数/正态变换与直接寻找区域分位数确实减少重复工作，但没有减少这些主要几何操作。保持完整节点、真实地理定义与所有样本时，不能靠缓存宣称数量级加速。每 worker 同时保留的查询缓存峰值 {c['peak_combined_query_cache_bytes']/2**20:.1f} MiB，查询结束即清空。

## 全量耗时预测及边界

| 阶段 | 本轮匹配测速的原实现 | 本轮优化实现 | 合同上限 |
|---|---:|---:|---:|
{forecast_table}

以上使用重新核对的 p95 操作耗时、完整查询数、最多两 worker、1.5 倍安全余量和原有 300 秒阶段杂项预留。额外使用“启动至首个新旧成对任务完成”作保守启动余量，不能把该值称作优化实现的独立启动耗时。与上次预估差异也包含本次测量波动，应看同次新旧对照。

若未来正式审计采用增强参考，保守地在原参考/IID预留之外追加新参考成本：65,536 档审计约 {new['audit_if_reference_65536']:.2f} h；262,144 档约 {new['audit_if_reference_262144']:.2f} h。这里含少量重复预留，不能据此减少检查。两种参考变更都未自动授权正式运行。

现有定义下，评分与复核预计合计 **{sum_score:.2f} h**；若未来审阅采用 65,536 节点参考检查，约 **{sum_score_enhanced:.2f} h**。正式训练的收敛/早停耗时尚未测得；若另外按原训练阶段共 9 h、报告 1 h 预留，后续资源规划约 **{sum_score_enhanced+10:.2f} h**，另加已经消耗的试跑时间。这不是实测完工承诺，也不是建议直接批准该总数。任何阶段预计超限仍需停下审阅，不能借用其他阶段余额。不得把只完成十轮的旧试跑网络当作已训练完成的模型。

## 本轮资源与下一步

报告生成前，本次新增活跃计算 {sum(stage_time.values()):.2f} 秒（{sum(stage_time.values())/60:.2f} 分钟）；报告/复核自身耗时继续记入原资源台账。进程树峰值 {peak:.3f} GiB，新增计算上限 20 分钟、原试跑累计上限 1 小时均未改变。报告生成后的最终用量见资源汇总。

建议根据本轮证据修订**数值核验与资源条款**后再决定恢复：保留模型、K、全部样本和评分标准；加强参考积分，区分主精度与参考一致性失败，避免只增加主积分点数。缓存优化本身不等于资源闸门通过。**本轮不会恢复正式实验。**

- [数值及资源汇总]({HERE/'validation_summary.json'})
- [阶段 B 全部参考检查]({HERE/'stage_B.json'})
- [阶段 C 完整对照摘要]({HERE/'stage_C.json'})
- [原始失败记录]({PROV/'pilot_result.json'})
- [原始资源台账]({PROV/'resource_ledger.json'})
'''
(OUT/'REPORT.md').write_text(report)
summary={'status':'BOUNDED_VALIDATION_COMPLETE_FORMAL_STOPPED','formal_next_stage':None,
    'reference_pass_counts':b['counts'],'matched_node_max_term_difference_km':max(x['max_term_difference_km'] for x in a['matched_node_checks']),
    'equivalent_probe_records':768,'all_exact_value_equal':True,'all_old_hashes_match':True,
    'frozen_files':len(approval['old_artifacts_sha256']),'timing_basis':'matched alternating2worker operation timings including parameter preparation, excluding launch and writes',
    'speedup':speedup,'operation_time_reduction_fraction':saved,'p95_seconds':raw_stats,
    'projected_hours':forecasts,'scoring_audit_hours':sum_score,'full_training_expected_hours':None,
    'scoring_audit_hours_if_reference_65536':sum_score_enhanced,
    'planning_future_hours_with_existing_training_report_allowances':sum_score_enhanced+10,
    'additional_stage_seconds_before_report':stage_time,
    'independent_review_receipt':str(HERE/'independent_review.json'),
    'original_gate_changed':False,'new_model_training':False,'selected_K':None,'new_outer_target_access':False,
    'report':str(OUT/'REPORT.md')}
(HERE/'validation_summary.json').write_text(json.dumps(summary,indent=2))
print(json.dumps({k:summary[k] for k in ('status','speedup','operation_time_reduction_fraction','projected_hours','scoring_audit_hours')}))
