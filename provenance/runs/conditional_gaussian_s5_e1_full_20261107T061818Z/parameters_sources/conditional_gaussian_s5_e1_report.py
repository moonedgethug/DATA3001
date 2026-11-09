"""Stopped-pilot evidence report. No forecasting or target access."""
import time
STARTED = time.monotonic()
import html
import importlib.metadata
import json
import os
import platform
import sys

import numpy as np
import pandas as pd

from data3001.modelling.common.runtime import save_json
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inputs


def report(name):
    paths, run, cfg, approval, guard = inputs.context(name)
    budget = inputs.Budget(run, cfg, 'report', STARTED)
    os.environ['MPLCONFIGDIR'] = str(run['provenance']/'plot_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,
                         'axes.spines.right':False,'figure.facecolor':'white'})
    root = run['results']
    gates = json.loads((root/'pilot_gates.json').read_text())
    audit = json.loads((run['provenance']/'pilot_independent_audit.json').read_text())
    pilot_resource = json.loads((run['provenance']/'pilot_resources.json').read_text())
    summaries = pd.read_csv(root/'pilot_summary.csv')
    models = ['ExactPoint','EndpointCI','LocalGaussian']
    colours = ['#617d96','#159f9a','#df8540']
    totals = summaries[summaries.scope.eq('all_pilot')].set_index('model').loc[models]
    saved_plots = []
    def save(fig, name):
        fig.tight_layout()
        paths.publish(root/name,lambda file:fig.savefig(file,format='png',dpi=165,bbox_inches='tight'))
        plt.close(fig)
        saved_plots.append(name)
    fig,axes = plt.subplots(1,3,figsize=(12,3.7))
    for ax,field,title,scale,unit in zip(axes,['energy_km','h90','area90_km2'],
            ['Energy Score (lower is better)','Observed hit rate','Mean 90% region area'],
            [1,100,1/1000],['km','%','thousand km²']):
        values = totals[field].to_numpy()*scale
        ax.bar(np.arange(3),values,color=colours,width=.64)
        ax.set_xticks(np.arange(3),models,rotation=15)
        ax.set_ylim(0,max(values)*1.2)
        ax.set_title(title,fontsize=11);ax.set_ylabel(unit)
        for x,y in enumerate(values):ax.text(x,y+max(values)*.025,f'{y:.2f}',ha='center',fontsize=10)
        if field=='h90':ax.axhline(90,ls='--',color='#87939f',lw=1)
    fig.suptitle('Engineering pilot only · 128 starts / 70 IDs · not the 2020–2022 comparison',fontsize=12,y=1.04)
    save(fig,'pilot_comparison.png')
    fig,axes = plt.subplots(1,2,figsize=(11,3.6))
    proj = gates['resource_projection']
    labels = ['Formal + required reserve','Independent audit']
    projected = np.array([proj['formal_with_twofold_reserve_seconds'],proj['audit_seconds']])/60
    allowed = np.array([120,30])
    x = np.arange(2)
    axes[0].bar(x-.18,projected,.36,label='Pilot projection',color='#df8540')
    axes[0].bar(x+.18,allowed,.36,label='Approved limit',color='#617d96')
    axes[0].set_xticks(x,labels);axes[0].set_ylabel('minutes');axes[0].legend(frameon=False,fontsize=9)
    for i,value in enumerate(projected):axes[0].text(i-.18,value+4,f'{value:.1f}',ha='center')
    axes[0].set_ylim(0,245)
    storage = proj['storage_bytes']/2**30
    axes[1].bar([0,1,2],[storage,2.5,5],color=['#df8540','#617d96','#b4c0ca'])
    axes[1].set_xticks([0,1,2],['Gross storage proxy','Preflight limit','Hard limit'])
    axes[1].set_ylabel('GiB');axes[1].set_ylim(0,storage*1.18)
    for i,value in enumerate([storage,2.5,5]):axes[1].text(i,value+.15,f'{value:.2f}',ha='center')
    fig.suptitle('Resource gate failed · formal run not started',fontsize=13,y=1.04)
    save(fig,'resource_gate.png')
    fig,axes=plt.subplots(1,2,figsize=(11,3.6))
    levels=sorted(map(int,gates['energy_checks']))
    se=[gates['energy_checks'][str(k)]['contrasts']['ExactPoint']['projected_three_se_km'] for k in levels]
    threshold=[gates['energy_checks'][str(k)]['contrasts']['ExactPoint']['threshold_km'] for k in levels]
    axes[0].plot(levels,se,'o-',label='Projected 3 × numerical SE',color=colours[2])
    axes[0].plot(levels,threshold,'--',label='Registered threshold',color=colours[0])
    axes[0].set_xscale('log',base=2);axes[0].set_ylabel('ES, km');axes[0].set_xlabel('Total paired draws per query')
    axes[0].legend(frameon=False,fontsize=8);axes[0].set_title('G − ExactPoint precision projection')
    rlevels=sorted(map(int,gates['region_checks']))
    for model,col in zip(models,colours):
        axes[1].plot(rlevels,[gates['region_checks'][str(k)]['models'][model]['mass_diagnostic'] for k in rlevels],
                     'o-',label=model,color=col)
    axes[1].axhline(.005,ls='--',color='#657080',label='Registered threshold')
    axes[1].set_xscale('log',base=2);axes[1].set_xlabel('Draws per region packet');axes[1].set_ylabel('Weighted mass diagnostic')
    axes[1].legend(frameon=False,fontsize=8);axes[1].set_title('90% region reconstruction')
    save(fig,'numerical_precision.png')
    def metric_table(scope):
        frame=summaries[summaries.scope.eq(scope)].set_index('model').loc[models]
        rows=''.join(f'<tr><th>{name}</th><td>{row.energy_km:.4f}</td><td>{row.h90*100:.2f}%</td><td>{row.area90_km2:,.0f}</td><td>{row.land_mass*100:.3f}%</td></tr>' for name,row in frame.iterrows())
        return '<div class="scroll"><table><thead><tr><th>模型</th><th>ES（km）↓</th><th>实际命中率</th><th>面积（km²）</th><th>陆地概率</th></tr></thead><tbody>'+rows+'</tbody></table></div>'
    energy_delta=totals.loc['LocalGaussian','energy_km']-totals.loc['ExactPoint','energy_km']
    hit_delta=100*(totals.loc['LocalGaussian','h90']-totals.loc['ExactPoint','h90'])
    area_delta=100*(totals.loc['LocalGaussian','area90_km2']/totals.loc['ExactPoint','area90_km2']-1)
    content=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Step 5 E1 · 试跑完成，正式实验暂停</title>
<style>body{{margin:0;background:#f4f6f8;color:#223044;font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1120px;margin:auto;padding:40px 24px 64px}}h1{{font-size:34px;line-height:1.3;margin:12px 0}}h2{{font-size:23px;margin:0 0 16px}}p{{max-width:920px}}section{{background:white;padding:28px;border-radius:14px;margin-top:24px}}.eyebrow{{color:#717d89;font-size:13px;letter-spacing:.08em}}.notice{{border-left:4px solid #df8540;padding-left:18px}}.muted{{color:#667383}}.pill{{display:inline-block;background:#fff0dd;color:#8b511a;padding:4px 12px;border-radius:18px;font-size:13px}}img{{width:100%;height:auto}}table{{width:100%;border-collapse:collapse;white-space:nowrap;font-size:14px}}th,td{{padding:11px;text-align:right;border-bottom:1px solid #e5eaf0}}th:first-child{{text-align:left}}thead{{background:#f2f5f8}}.scroll{{overflow:auto}}summary{{cursor:pointer;font-weight:600;margin:14px 0}}a{{color:#176b9b}}.grid{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.stat{{border-top:2px solid #d5dfe8;padding-top:12px}}.stat b{{display:block;font-size:28px}}footer{{font-size:12px;color:#667383;overflow-wrap:anywhere;margin-top:24px}}@media(max-width:680px){{main{{padding:22px 12px}}section{{padding:20px 14px}}h1{{font-size:26px}}.grid{{grid-template-columns:1fr}}}}</style></head><body><main>
<div class="eyebrow">WHERE THINGS END UP · STEP 5 E1 · 7 NOV 2026</div><h1>试跑与数值复核完成，正式比较尚未开始</h1><span class="pill">暂停原因：资源预检未通过</span>
<p class="notice">高斯模型的估计与积分可以正常计算，128 个试跑起点未出现无支撑或协方差退化。但合同要求的时间余量、复核时间和保守存储预检未通过，故没有启动 33,971 个正式验证起点的实验。<strong>目前不能判断高斯模型是否带来了质量不退化的改善。</strong></p>
<div class="grid"><div class="stat">内部试跑<b>128 / 128</b>70 条独立 drifter</div><div class="stat">试跑实际耗时<b>{pilot_resource['elapsed_seconds']:.1f} 秒</b>含前置测试累计 85.4 秒</div><div class="stat">本轮新增外层落点评分<b>0</b>正式验证与 final-test 均未读取</div></div>
<section><h2>为什么暂停</h2><img src="resource_gate.png" alt="正式预算与试跑资源外推对比"><p>单次正式计算的外推约为 <strong>{proj['formal_seconds']/60:.1f} 分钟</strong>，但批准的预检要求是“两倍估计 ≤ 120 分钟”；当前约 {proj['formal_with_twofold_reserve_seconds']/60:.1f} 分钟。独立复核外推约 {proj['audit_seconds']/60:.1f} 分钟，超过 30 分钟。</p><p>存储 {storage:.2f} GiB 是把试跑全部层级、检查点及固定文件外推并加倍的粗略保守值，<strong>并非正式运行实际需要的空间</strong>。本次试跑实际保留约 {pilot_resource['retained_bytes']/2**20:.1f} MiB。运行估计也尚未完整实测所有读写开销，因此这些估计足以支持暂停，不能作为今后放行的证明。</p></section>
<section><h2>内部试跑三组对照</h2><p class="notice">以下为两个训练期内验证窗口各 64 个固定工程样本，按 drifter 等权汇总。它们用于检查计算，不代表完整 2020–2022 验证结果，也不应与历史完整实验分数直接比较。</p><img src="pilot_comparison.png" alt="三组模型的内部试跑 ES、实际命中率和面积">{metric_table('all_pilot')}<p>在这组小样本中，相对 ExactPoint，高斯的 ES 增加 {energy_delta:.3f} km、命中率提高 {hit_delta:.2f} 个百分点、面积扩大 {area_delta:.2f}%。这是覆盖与面积的权衡，没有在这组样本中同时改善三项指标。<strong>不据此接受或否定高斯模型。</strong></p>
<details><summary>分验证窗口查看</summary><p>C_T0：2001–2013 训练，2014–2016 内部验证；64 起点、37 IDs。</p>{metric_table('C_T0')}<p>C_T1：2001–2016 训练，2017–2019 内部验证；64 起点、37 IDs。两个窗口有部分 ID 重合，合计唯一 ID 为 70。</p>{metric_table('C_T1')}</details></section>
<section><h2>数值精度通过；资源门槛未通过</h2><img src="numerical_precision.png" alt="ES 和区域积分层级的精度检查"><p>ES 最低通过层级为每起点 8,192 对抽样；区域最低通过层级为每个重建包 32,768 点。高斯 ES 使用 8 个独立扰乱 Sobol 序列，区域有独立重复重建和 IID 概率检查。</p><p>这些门槛控制的是计算误差，不是模型的预测误差。主重复与独立重复的试跑命中判定一致；独立 IID 高斯积分与精细 RQMC 的汇总差为 {audit['iid_minus_rqmc_km']:.4f} km，三倍数值标准误为 {audit['iid_three_se_km']:.4f} km，结果相容。</p></section>
<section><h2>独立复核与模型边界</h2><ul><li>全部 128 组参考记录经穷举距离核对一致；每组 1,955–8,000 对观测、17–193 个独立训练 drifter。</li><li>全部高斯参数独立重算一致；最大协方差条件数 80.383，远低于合同暂停线。未使用协方差修补、全局回退或新增权重。</li><li>384 个保存区域的面积与命中判定独立核对通过；ExactPoint 的离散 90% 分位另行重算。</li><li>EndpointCI 的不可用 error 参考记录保留原点质量；试跑平均回退质量为 {audit['weighted_ci_fallback_mass']*100:.3f}%。高斯没有回退。</li><li>独立代码审阅发现异常停止时的诊断保存和计时完整性有工程缺口；已补充实现及测试，但没有重新运行试跑，也没有覆盖原始证据。改进后的资源计时仍需重新验证后才能作为放行依据。</li></ul>
<details><summary>公式与本次实际完成范围</summary><p>同一精确起点、同一 100 km / k=8,000 参考集；三组保留逐配对等权训练。LocalGaussian 对历史原始终点的查询中心 WGS84 东北坐标，解析估计 μ=平均值、Σ=中心化交叉乘积/n。它不转移历史轨迹、不加入位置 error、不截去陆地或域外概率。</p><p>评分使用 ECEF 弦距离 Energy Score；区域是共用 LAEA 投影中包含本模型至少 90% 概率的分位椭圆。0.5° cell 不参与训练或评分。本轮未执行正式参数冻结、外层评分、正式 bootstrap 或预选外层案例地图。正式实验执行器尚未继续开发；当前交付的是试跑、复核与暂停证据。</p></details></section>
<section><h2>下一步需要决定什么</h2><p>先审阅资源问题：可以在保持三组分布、完整样本和精度不变的前提下，另行规划计算复用和紧凑存储，并用完整计时验证；也可以讨论调整预算。当前没有实施优化、改变合同或启动重跑。</p><p><a href="pilot_summary.csv">试跑汇总 CSV</a> · <a href="pilot_gates.json">原始门槛结果</a> · <a href="technical_report.md">English technical report</a> · <a href="../../../provenance/runs/{name}/pilot_independent_audit.json">独立数值复核</a></p></section>
<footer>Run: {html.escape(name)}<br>Evidence: pilot_energy.parquet / pilot_regions.parquet / pilot_support.csv / independent audit. Historical inputs and the approved contract are hash-protected. No scientific conclusion or default-model replacement is authorised by this report.</footer></main></body></html>'''
    paths.publish(root/'review.html',lambda f:f.write(content.encode()))
    md=f'''# Step 5 E1: engineering pilot stopped before formal comparison

Status: **INCOMPLETE — resource preflight failed**. The 128-case internal pilot and its independent numerical audit completed. No outer target was opened; no final-test data were accessed. The formal executor was not continued after the failed pilot.

The same donor endpoints and pair-equal fitting weights were used for ExactPoint, EndpointCI and LocalGaussian. All approved scientific definitions remain unchanged. The Gaussian uses the query-centred WGS84 metric chart, analytic full n-divisor covariance and complete geographic pushforward; ES uses ECEF chord kilometres. Region evaluation retains the common LAEA 90% quantile ellipse. Pilot summaries average times within ID, then IDs.

## Evidence boundary

The pilot contains 64 fixed starts per internal role, 128 starts and 70 distinct IDs overall. It is an engineering roster, not the complete outer cohort of 33,971 starts/45 IDs. Pilot scores are descriptive only. No significance test, model selection, fresh outer comparison or claim of quality preservation is supported.

|Model|Pilot ES km|Pilot H90|Pilot area km²|
|---|---:|---:|---:|
'''+''.join(f'|{model}|{totals.loc[model,"energy_km"]:.6f}|{totals.loc[model,"h90"]:.6f}|{totals.loc[model,"area90_km2"]:.3f}|\n' for model in models)+f'''
Gaussian-minus-ExactPoint pilot ES is +{energy_delta:.6f} km; H90 is +{hit_delta:.4f} percentage points and area is +{area_delta:.4f}%. This is not a completed negative scientific result.

## Precision and audit

Minimum passing levels: ES 8,192 pairs/query, region 32,768 points/packet. All 128 donor sets were independently reconstructed exhaustively. Means/covariances and all 384 saved region areas/membership decisions were independently checked. A separate 65,536-draw IID Gaussian calculation per pilot case used an eigen root and an independent ellipsoidal ECEF formula. Its weighted difference from RQMC is {audit['iid_minus_rqmc_km']:.6f} km, within 3 SE={audit['iid_three_se_km']:.6f} km. This comparison is an integration check, not a confidence interval for predictive improvement.

No covariance failure was observed; support ranges 1,955–8,000 pairs and 17–193 donor IDs. Maximum covariance condition is 80.383. The average unavailable-CI point-fallback mass is {audit['weighted_ci_fallback_mass']:.8f}; no donor was discarded or assigned a different vote.

## Resources and review findings

Pilot execution: {pilot_resource['elapsed_seconds']:.3f}s; cumulative pilot including preparation/tests: 85.406s. Peak process-tree RSS was {pilot_resource['peak_process_tree_rss_bytes']/2**30:.3f} GiB. Original full-run screening estimate: {proj['formal_seconds']/60:.2f} min, or {proj['formal_with_twofold_reserve_seconds']/60:.2f} min with required twofold reserve (limit120); audit {proj['audit_seconds']/60:.2f} min (limit30). Gross storage proxy {storage:.2f} GiB (preflight2.5, hard5). This is not actual selected-level storage: it scales all pilot levels and fixed files. Original runtime estimates also omitted measured early-loading and some I/O costs, so must not become a later passing certificate.

Fresh code review found missing diagnostic persistence on unobserved support failures, incomplete resource timing/components and a coarse storage proxy. Diagnostic persistence and component/I/O timing were corrected in current source with regression tests; the executed pilot source snapshots and outputs were preserved. No model or pilot was rerun. Any resumed execution must validate the revised engineering estimates under a reviewed plan; the present failure receipt remains binding. The storage proxy was disclosed rather than silently replaced.

Full outer support/parameters, numerical replication, paired whole-ID bootstrap, scientific acceptance tests and six prespecified outer example maps remain unperformed. Neither Gaussian superiority nor inferiority is established. Existing controls, model defaults, stage ledger, raw data and final-test reservations were not changed.
'''
    paths.publish(root/'technical_report.md',lambda f:f.write(md.encode()))
    environment=dict(python=sys.version,platform=platform.platform(),
        packages={name:importlib.metadata.version(name) for name in ['numpy','pandas','scipy','pyproj','shapely','psutil','matplotlib','pyarrow']},
        blas_threads={name:os.environ.get(name) for name in ['OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS']},
        captured_after_pilot=True,packages_installed_or_changed_during_task=False)
    save_json(paths,run['provenance']/'environment.json',environment)
    inputs.freeze_sources(paths,run,'handoff')
    inputs.verify(approval)
    budget.finish(paths,'report_build',True,guard)
    print(json.dumps(dict(report=str(root/'review.html'),plots=saved_plots)),flush=True)


if __name__ == '__main__': report(sys.argv[1])
