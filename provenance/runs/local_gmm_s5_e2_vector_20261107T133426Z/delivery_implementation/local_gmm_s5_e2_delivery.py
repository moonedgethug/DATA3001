"""Supplementary contract-required diagnostics after the frozen experiment passes.

This module does not fit, select, score or alter a forecast. It reads the released
results, supplies diagnostic figures and ID-level sensitivity tables, and writes
a separately hashed review package without overwriting the core release.
"""
import html
import json
import os
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd

FIELDS=['energy_km','h90','area90_km2']
BASELINES=['LocalGaussian','ExactPoint','EndpointCI']


def descriptive_summary(table,groups):
    per_id=table.groupby(groups+['id','model'],observed=True)[FIELDS].mean()
    summary=per_id.groupby(groups+['model'],observed=True).mean()
    counts=table.groupby(groups+['model'],observed=True).agg(
        independent_ids=('id','nunique'),queries=('id','size'))
    return summary.join(counts).reset_index()


def leave_one_id_out(per_id):
    ids=sorted(per_id.id.unique())
    if len(ids)<2:raise ValueError('At least two independent drifters required')
    candidate=per_id[per_id.model.eq('LocalGMM')].set_index('id').loc[ids]
    if candidate.index.duplicated().any():raise ValueError('Duplicate candidate ID mean')
    records=[]
    for name in BASELINES:
        baseline=per_id[per_id.model.eq(name)].set_index('id').loc[ids]
        if baseline.index.duplicated().any():raise ValueError('Duplicate baseline ID mean')
        for identity in ids:
            a=candidate.drop(identity)[FIELDS].mean()
            b=baseline.drop(identity)[FIELDS].mean()
            records.append(dict(omitted_id=int(identity),baseline=name,
                es_delta=float(a.energy_km-b.energy_km),hit_delta=float(a.h90-b.h90),
                area_ratio=float(a.area90_km2/b.area90_km2)))
    return pd.DataFrame(records)


def collect_fit_diagnostics(run,budget):
    from .conditional_gaussian_s5_e1_full import read_bundle
    fits=[];components=[]
    for role in ['C_T0','C_T1']:
        for batch,path in enumerate(sorted((run['results']/role/'parameters').glob('*.json.gz'))):
            for record in read_bundle(path):
                for k in [2,3]:
                    packet=record['models'][str(k)]
                    restart=next((r for r in packet['restarts'] if r['restart']==packet.get('chosen_restart')),None)
                    fits.append(dict(role=role,id=record['id'],query_position=record['query_position'],K=k,
                        lon=record['origin'][0],lat=record['origin'][1],fallback=packet['fallback'],
                        covariance_floor_active=bool(restart and restart['floor_active']>0),
                        pairs=record['pairs'],independent_ids=record['independent_ids']))
                    if not packet['fallback']:
                        for probability,diagnostic in zip(packet['weights'],packet['component_diagnostics']):
                            components.append(dict(role=role,id=record['id'],K=k,probability=probability,
                                effective_ids=diagnostic['effective_ids'],responsibility_count=diagnostic['responsibility_count'],
                                largest_id_share=diagnostic['largest_id_share'],condition=diagnostic['condition']))
            if batch%64==0:budget.check()
        print('DELIVERY_DIAGNOSTICS',role,'complete',flush=True)
    component_fields=['role','id','K','probability','effective_ids','responsibility_count','largest_id_share','condition']
    return pd.DataFrame(fits),pd.DataFrame(components,columns=component_fields)


def render(name):
    from data3001.paths import file_sha256
    from data3001.modelling.common.runtime import save_frame,save_json
    from . import local_gmm_s5_e2_pipeline as pipe
    started=time.monotonic()
    paths,run,cfg,approval,guard=pipe.context(name)
    source_manifest=run['provenance']/'delivery_source_hashes.json'
    for source,digest in json.loads(source_manifest.read_text()).items():
        if file_sha256(pipe.ROOT/source)!=digest:raise ValueError('Delivery implementation changed')
    core_path=run['provenance']/'release_manifest.json'
    core=json.loads(core_path.read_text());audit=json.loads((run['provenance']/'full_audit.json').read_text())
    if not core['complete'] or not audit['passed']:raise ValueError('Complete audited core release required')
    for source,digest in core['result_sha256'].items():
        if file_sha256(pipe.ROOT/source)!=digest:raise ValueError('Core result changed')
    folder=run['results']/'review';budget=pipe.Budget(run,cfg,'report','delivery',started);completed=False
    try:
        choice=json.loads((run['provenance']/'selection.json').read_text())
        decision=json.loads((run['provenance']/'decision.json').read_text())
        scores=pd.read_parquet(run['results']/'metrics.parquet')
        per_id=pd.read_csv(run['results']/'per_id.csv')
        summary=pd.read_csv(run['results']/'summary.csv')
        comparisons=pd.read_csv(run['results']/'comparisons.csv')
        outer_fallback=json.loads((run['provenance']/'fallback_summary.json').read_text())
        selection_rows=[]
        for k in [1,2,3]:
            selection_rows.append(dict(K=k,pooled_ES=choice['pooled_scores'][str(k)],
                C_T0_ES=choice['role_scores'][f'C_T0:{k}'],C_T1_ES=choice['role_scores'][f'C_T1:{k}'],
                C_T0_fallback=choice['fallback_rates'][f'C_T0:{k}'],C_T1_fallback=choice['fallback_rates'][f'C_T1:{k}'],
                eligible=k in choice['eligible'],reason='; '.join(choice['ineligibility'][str(k)])))
        selection_table=pd.DataFrame(selection_rows)
        save_frame(paths,folder/'inner_selection.csv',selection_table)
        save_json(paths,folder/'selection_receipt.json',choice)
        sensitivity=leave_one_id_out(per_id)
        save_frame(paths,folder/'leave_one_id_out.csv',sensitivity)
        descriptive=scores.copy()
        descriptive['year']=pd.to_datetime(descriptive.origin_time_UTC,utc=True).dt.year
        descriptive['donor_pair_band']=pd.cut(descriptive.pairs,[0,99,999,3999,np.inf],labels=['1–99','100–999','1000–3999','4000+'])
        descriptive['donor_id_band']=pd.cut(descriptive.independent_ids,[0,3,10,30,np.inf],labels=['1–3','4–10','11–30','31+'])
        descriptive['largest_id_share_band']=pd.cut(descriptive.largest_id_share,[0,.25,.5,.75,1.],include_lowest=True,
            labels=['0–25%','25–50%','50–75%','75–100%'])
        for field in ['year','donor_pair_band','donor_id_band','largest_id_share_band']:
            save_frame(paths,folder/f'descriptive_{field}.csv',descriptive_summary(descriptive,[field]))
        fits,components=collect_fit_diagnostics(run,budget)
        save_frame(paths,folder/'inner_fit_diagnostics.parquet',fits)
        save_frame(paths,folder/'component_diagnostics.parquet',components)
        fallback=fits.groupby(['role','id','K']).fallback.mean().groupby(['role','K']).mean()
        valid=fits[~fits.fallback]
        floor=valid.groupby(['role','id','K']).covariance_floor_active.mean().groupby(['role','K']).mean()
        fit_summary=pd.concat([fallback.rename('fallback_id_equal'),floor.rename('floor_active_id_equal_among_valid')],axis=1).reset_index()
        save_frame(paths,folder/'fit_diagnostic_summary.csv',fit_summary)
        os.environ['MPLCONFIGDIR']=str(run['provenance']/'delivery_plot_cache')
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        def save(fig,filename):
            paths.publish(folder/filename,lambda f:fig.savefig(f,format='png',dpi=150,bbox_inches='tight'))
            plt.close(fig);budget.check()
        fig,axes=plt.subplots(2,3,figsize=(13,7))
        for row,k in enumerate([2,3]):
            data=components[components.K.eq(k)]
            for ax,field,label in zip(axes[row],['probability','effective_ids','largest_id_share'],
                    ['Component probability','Effective drifter IDs','Largest drifter share']):
                ax.hist(data[field],bins=35,color='#537c9a',alpha=.85)
                ax.set_title(f'K={k}: {label}',fontsize=10);ax.set_ylabel('Fitted components')
                ax.grid(axis='y',alpha=.15)
        fig.suptitle('Inner-candidate component diagnostics — descriptive record counts')
        save(fig,'component_support.png')
        fig,axes=plt.subplots(1,2,figsize=(11,4));labels=[f'{r.role} / K={r.K}' for r in fit_summary.itertuples()]
        axes[0].bar(labels,fit_summary.fallback_id_equal,color='#c97a58');axes[0].set_title('ID-equal whole-query fallback rate')
        axes[1].bar(labels,fit_summary.floor_active_id_equal_among_valid,color='#537c9a');axes[1].set_title('Covariance floor active among valid fits')
        for ax in axes:ax.tick_params(axis='x',rotation=25);ax.grid(axis='y',alpha=.15)
        save(fig,'fallback_and_floor.png')
        fig,axes=plt.subplots(2,2,figsize=(11,8),sharex=True,sharey=True)
        for row,role in enumerate(['C_T0','C_T1']):
            for col,k in enumerate([2,3]):
                data=fits[fits.role.eq(role)&fits.K.eq(k)];ax=axes[row,col]
                for state,colour,label in [(False,'#aab8c2','Mixture retained'),(True,'#c65d49','Whole-query G1 fallback')]:
                    d=data[data.fallback.eq(state)];ax.scatter(d.lon,d.lat,s=2,c=colour,alpha=.5,label=label,rasterized=True)
                ax.set_title(f'{role}, K={k}');ax.set_xlabel('Origin longitude');ax.set_ylabel('Origin latitude')
                ax.legend(fontsize=7,markerscale=3)
        fig.suptitle('Fallback locations — all inner validation origins')
        save(fig,'fallback_locations.png')
        fig,axes=plt.subplots(1,3,figsize=(13,4))
        for ax,field,zero,label in zip(axes,['es_delta','hit_delta','area_ratio'],[0,0,1],
                ['GMM − baseline ES (km)','GMM − baseline hit rate','GMM / baseline area']):
            for j,baseline in enumerate(BASELINES):
                values=sensitivity[sensitivity.baseline.eq(baseline)][field]
                ax.scatter(values,np.full(len(values),j),s=12,alpha=.55,color='#845ab0')
            ax.axvline(zero,color='#777',lw=.8);ax.set_yticks(range(3),BASELINES);ax.set_title(label,fontsize=10)
        fig.suptitle('Leave-one-drifter-out sensitivity — fixed forecasts, no refitting')
        save(fig,'leave_one_id_out.png')
        verdict='达到合同中的质量不退化改善标准' if decision['quality_non_degrading_improvement'] else '未达到合同中的质量不退化改善标准'
        table=lambda frame:frame.to_html(index=False,escape=True,float_format=lambda x:f'{x:,.6f}')
        maps=''.join(f'<img loading="lazy" src="../example_{j:02d}.png">' for j in range(1,7))
        content=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Step 5 E2 完整实验报告</title><style>body{{margin:0;background:#eef2f5;color:#243649;font:16px/1.7 system-ui}}main{{max-width:1180px;margin:auto;padding:30px}}section{{background:white;padding:24px;margin:20px 0;border-radius:12px}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:13px}}td,th{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}.scroll{{overflow:auto}}.note{{color:#596b7b}}a{{color:#21688b}}</style><main>
<h1>Step 5 E2 · 局部高斯混合完整实验</h1><p>最终 K={choice['selected_k']}；{verdict}。</p>
<p class="note">全部 86,373 个内层起点及 33,971 个外层起点；外层 45 条 drifter 等权。七天预测、完整近邻、原始终点及训练配对权重保持不变。未使用 MDN，未读取最终测试集。</p>
<section><h2>1. 训练期如何选择 K</h2><div class="scroll">{table(selection_table)}</div>
<p>最佳 ES 候选 K={choice['best_es_k']}；一倍标准误规则暂选 K={choice['provisional_k']}；质量约束后最终 K={choice['selected_k']}。回退列为 drifter 等权比例。两个窗口及跨窗口汇总遵守合同中的 ID 等权规则。</p>
<p>K=1 时 LocalGMM 与 LocalGaussian 是同一个分布。这表示本轮选择规则没有支持增加成分，不能据此证明海洋落点单峰；K 也不等于真实洋流分支的数量。</p><a href="selection_receipt.json">完整冻结选择记录</a></section>
<section><h2>2. 四组七天预测结果</h2><div class="scroll">{table(summary[['model','energy_km','h90','area90_km2','land_mass','outside_D_mass']])}</div>
<img src="../full_comparison.png"><p>ES 单位为 km，越低越好；h90 为比例；面积单位为 km²。90% 区域统一为各自完整分布的单个分位椭圆，可能包含多峰之间的低密度地带。</p>
<img src="../paired_effects.png"><p>区间来自 10,000 次整条 drifter 配对重抽。主比较为 GMM 对单高斯，然后是 ExactPoint、EndpointCI；验收要求 ES 改善及命中、面积和地理质量约束同时满足。</p>
<div class="scroll">{table(comparisons[['baseline','es_delta','es_lower','es_upper','hit_delta','area_ratio','eligible']])}</div></section>
<section><h2>3. 组件支撑、协方差与回退</h2><p>外层 GMM 的 drifter 等权回退比例：{outer_fallback['drifter_equal_fraction']:.3%}；查询回退比例：{outer_fallback['query_fraction']:.3%}。EndpointCI 中 error 不可用、保留为原始点的质量：{outer_fallback['ci_unavailable_vote_mass']:.3%}。</p><p>以下诊断展示完整内层 K=2、3 候选；直方图为拟合组件记录数，仅用于描述，不参与验收。回退位置图展示所有起点。</p>
<img src="component_support.png"><img src="fallback_and_floor.png"><img src="fallback_locations.png">
<p>五次重启均未通过预先定义的支撑或收敛要求时，整个查询按合同退回 G1；所有这些查询保留在评分中。</p></section>
<section><h2>4. 是否被个别 drifter 主导</h2><img src="../per_id_effects.png"><img src="leave_one_id_out.png">
<p>每个点省略一条 drifter 后重新汇总固定预测结果；没有重新训练，也不以此追加选择模型。</p></section>
<section><h2>5. 六个预先固定的示例</h2><p>白点为起点、星号为七天后记录位置、红线为90%椭圆。每例四组共用范围和色标；0.5° cell 仅用于展示。</p>{maps}</section>
<section><h2>6. 可复核数据</h2><p><a href="../technical_report.md">核心技术报告</a> · <a href="diagnostic_notes.md">诊断说明</a> · <a href="../model_manifest.json">模型清单</a> · <a href="../independent_per_id.csv">独立逐 ID 复核</a></p>
<p><a href="inner_selection.csv">内层选择表</a> · <a href="leave_one_id_out.csv">逐 ID 省略敏感性</a> · <a href="descriptive_year.csv">按年份</a> · <a href="descriptive_donor_pair_band.csv">按配对支撑量</a> · <a href="descriptive_donor_id_band.csv">按独立 drifter 支撑量</a> · <a href="descriptive_largest_id_share_band.csv">按最大 drifter 占比</a></p>
<p class="note">分组表在各组内给予 drifter 等权，仅作描述。外层期间已用于多轮开发，因此这里是开发验证证据，不能当作独立最终测试。</p></section><footer>{html.escape(name)}</footer></main></html>'''
        paths.publish(folder/'index.html',lambda f:f.write(content.encode()))
        notes=f'''# Step 5 E2 diagnostic delivery

The frozen core release remains unchanged. This package adds the contract-required inner selection table, component support and covariance-floor diagnostics, whole-query fallback maps, per-year/support descriptive tables, and leave-one-ID-out sensitivity. No model, score, parameter, acceptance threshold or selection decision was changed.

Chosen K: {choice['selected_k']}; provisional K: {choice['provisional_k']}; best ES candidate: {choice['best_es_k']}.

## Inner selection

{selection_table.to_csv(index=False)}

## Diagnostic scope

Component histograms count retained fitted components from both complete inner windows. Fallback and covariance-floor rates are averaged first within drifter. Floor rates condition on retained mixture fits. Descriptive outer tables average each drifter within each displayed group; these are not additional hypothesis tests. Leave-one-ID-out summaries omit one complete drifter and retain all forecasts without refitting. The common single ellipse can contain low-density gaps and is not a highest-density union.

The final-test split remained locked. The core statistical decision and all primary metrics are authoritative. The report does not claim that selecting K=1 proves unimodality, or that K>1 identifies physical flow branches.
'''
        paths.publish(folder/'diagnostic_notes.md',lambda f:f.write(notes.encode()))
        budget.check()
        save_json(paths,run['provenance']/'delivery_release.json',dict(complete=True,core_release_sha256=file_sha256(core_path),
            delivery_source_manifest_sha256=file_sha256(source_manifest),contract_sha256=cfg['contract_sha256'],
            model_or_selection_changed=False,final_test_access=False,
            result_sha256={str(p.relative_to(pipe.ROOT)):file_sha256(p) for p in folder.rglob('*') if p.is_file()}))
        completed=True;print('DELIVERY_COMPLETE',folder/'index.html',flush=True)
    finally:
        budget.finish(paths,'delivery',completed,guard)


if __name__=='__main__':
    if len(sys.argv)!=2:raise SystemExit('Usage: local_gmm_s5_e2_delivery RUN_NAME')
    render(sys.argv[1])
