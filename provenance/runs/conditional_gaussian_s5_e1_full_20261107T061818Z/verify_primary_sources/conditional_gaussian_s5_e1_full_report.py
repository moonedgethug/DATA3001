"""Source-backed full-cohort figures and bilingual report, after audit only."""
import time
STARTED=time.monotonic()
import html
import json
import os
import sys
import traceback

import numpy as np
import pandas as pd

from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json,save_frame
from data3001.modelling.baselines import position_error_s4_e8 as old
from data3001.modelling.baselines import position_error_s4_e8_inputs as old_inputs
from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1 as gaussian
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_inputs as inp
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_numerics as num
from data3001.modelling.continuous_models import conditional_gaussian_s5_e1_full as full


def report(name):
    paths,run,cfg,approval,guard=inp.context(name);budget=inp.Budget(run,cfg,'report',STARTED)
    completed=False
    try:
        build_report(paths,run,cfg,approval,guard,budget)
        completed=True
    except BaseException as error:
        save_json(paths,run['provenance']/'full_report_stopped.json',dict(error=repr(error),traceback=traceback.format_exc(),outer_targets_read=guard.outcomes_read))
        raise
    finally:budget.finish(paths,'full_report',completed,guard)


def build_report(paths,run,cfg,approval,guard,budget):
    name=run['results'].name
    root=run['results'];decision=json.loads((run['provenance']/'scientific_decision.json').read_text())
    if not decision['engineering_complete']:raise PermissionError('No verified full experiment to report')
    os.environ['MPLCONFIGDIR']=str(run['provenance']/'plot_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    import shapely as sh
    from shapely.geometry import box
    plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    summary=pd.read_csv(root/'summary.csv').set_index('model').loc[list(num.MODELS)]
    comparisons=pd.read_csv(root/'comparisons.csv');per_id=pd.read_csv(root/'per_id.csv')
    metrics=pd.read_parquet(root/'metrics.parquet')
    checks=json.loads((run['provenance']/'full_independent_checks.json').read_text())
    prec=json.loads((run['provenance']/'primary_numerical_checks.json').read_text())
    support=json.loads((run['provenance']/'full_support_check.json').read_text())
    resources=[json.loads(p.read_text()) for p in run['provenance'].glob('*_resources.json')]
    phases={s:sum(r['elapsed_seconds'] for r in resources if r['phase']==s) for s in ['pilot','formal','audit','report']}
    colours=['#617d96','#189d99','#dd8041'];models=list(num.MODELS);plots=[]
    def save(fig,filename):
        paths.publish(root/filename,lambda f:fig.savefig(f,format='png',dpi=165,bbox_inches='tight'))
        plt.close(fig);plots.append(filename);budget.check()
    fig,axes=plt.subplots(1,3,figsize=(12,4))
    for ax,field,title,scale,unit in zip(axes,['energy_km','h90','area90_km2'],
        ['Energy Score (lower is better)','Observed 90% region hit rate','Mean 90% region area'],[1,100,.001],['km','%','thousand km²']):
        values=summary[field].to_numpy()*scale
        ax.bar(np.arange(3),values,color=colours,width=.65);ax.set_xticks(np.arange(3),models,rotation=15)
        ax.set_ylabel(unit);ax.set_title(title,fontsize=10);ax.set_ylim(0,max(values)*1.2)
        for x,y in enumerate(values):ax.text(x,y+max(values)*.025,f'{y:.3f}' if field=='energy_km' else f'{y:.2f}',ha='center')
        if field=='h90':ax.axhline(90,ls='--',color='#8894a0',lw=1)
    fig.suptitle('Full seven-day development comparison · 33,971 starts / 45 drifters',y=1.04,fontsize=13)
    fig.tight_layout();save(fig,'full_comparison.png')
    fig,axes=plt.subplots(1,3,figsize=(12,3.5))
    for ax,field,lo,hi,title,scale,offset in zip(axes,['es_delta','hit_delta','area_ratio'],
        ['es_lower','hit_lower','area_lower'],['es_upper','hit_upper','area_upper'],
        ['Paired ES difference (km)','Paired hit difference (percentage points)','Mean area difference (%)'],[1,100,100],[0,0,1]):
        values=(comparisons[field].to_numpy()-offset)*scale
        lower=(comparisons[lo].to_numpy()-offset)*scale;upper=(comparisons[hi].to_numpy()-offset)*scale
        ax.errorbar(values,[1,0],xerr=[values-lower,upper-values],fmt='o',capsize=4,color=colours[2])
        ax.axvline(0,color='#8a96a2',ls='--',lw=1);ax.set_yticks([1,0],['G − ExactPoint','G − EndpointCI']);ax.set_title(title,fontsize=10)
        ax.set_ylim(-.5,1.5)
    fig.suptitle('Paired 95% intervals · 10,000 whole-drifter bootstrap draws',y=1.04,fontsize=13)
    fig.tight_layout();save(fig,'paired_effects.png')
    values=per_id.pivot(index='id',columns='model',values='energy_km')
    delta=(values.LocalGaussian-values.ExactPoint).sort_values()
    fig,ax=plt.subplots(figsize=(12,3.8));ax.bar(np.arange(len(delta)),delta.to_numpy(),color=np.where(delta.to_numpy()<0,'#189d99','#dd8041'))
    ax.axhline(0,color='#506070',lw=.8);ax.set_xlabel('Drifters ordered by paired effect (all 45 retained)');ax.set_ylabel('G − ExactPoint ES (km)')
    ax.set_title('Between-drifter variation in the Gaussian effect');fig.tight_layout();save(fig,'per_id_effects.png')
    # Frozen examples were selected before this experiment's outer target release.
    selection=json.loads((run['provenance']/'example_selection.json').read_text())
    full.verify_freeze(run,approval);guard.outcomes_allowed=True
    truth=old_inputs.release_outer_targets(run,cfg,approval).sort_values(inp.KEY).reset_index(drop=True)
    train,_=old_inputs.load_training(cfg);geo=Geography(paths);cache=opt.cache(train,geo)
    example_meta=[]
    for number,example in enumerate(selection['examples'],1):
        position=int(example['query_position']);batch=position//cfg['batch_size'];j=position%cfg['batch_size'];files=full.files_for_batch(run,batch)
        record=full.read_bundle(files['parameters'])[j];forecast=full.read_bundle(files['forecasts'])[j]
        if any(int(record[k])!=int(example[k]) for k in inp.KEY):raise ValueError('Example key changed')
        with np.load(files['lineage']) as f:ix=full.unpack_lineage(f['indices'],f['offsets'],j)
        pool=cache.take(ix);key=tuple(record['key'])
        clouds={'ExactPoint':(pool.points,np.full(len(pool.points),1/len(pool.points)))}
        p,w,_=old.component_cloud(pool.points,pool.sd,pool.usable,65536,('s5_e1_v1',*key,'display_ci',0));clouds['EndpointCI']=(p,w)
        p=gaussian.draw(record['gaussian'],gaussian.sobol_normals(65536,2,(*key,'display_gaussian',0)));clouds['LocalGaussian']=(p,np.full(len(p),1/len(p)))
        y=truth.iloc[position][['endpoint_lon','endpoint_lat']].to_numpy(float)
        bounds=np.vstack([v[0] for v in clouds.values()]+[np.array([record['origin'],y])])
        x0,y0=np.floor(bounds.min(axis=0)*2)/2-.5;x1,y1=np.ceil(bounds.max(axis=0)*2)/2+.5
        xb=np.arange(x0,x1+.25,.5);yb=np.arange(y0,y1+.25,.5)
        hist={m:np.histogram2d(p[:,0],p[:,1],bins=(xb,yb),weights=w)[0].T for m,(p,w) in clouds.items()}
        for m,v in hist.items():np.testing.assert_allclose(v.sum(),1.,atol=1e-10)
        maximum=max(v.max() for v in hist.values())
        region_boundary={}
        for m in models:
            xy=old.ellipse_boundary(forecast['regions'][m]['region'])
            region_boundary[m]=np.column_stack(old.INVERSE.transform(xy[:,0]*1000,xy[:,1]*1000))
        land=geo.land.intersection(box(x0,y0,x1,y1));lines=[]
        for polygon in sh.get_parts(land):
            if polygon.geom_type=='Polygon':
                lines.append(np.asarray(polygon.exterior.coords))
                lines.extend(np.asarray(ring.coords) for ring in polygon.interiors)
        fig,axes=plt.subplots(1,3,figsize=(14,5),sharex=True,sharey=True,layout='constrained')
        for ax,m in zip(axes,models):
            mesh=ax.pcolormesh(xb,yb,np.ma.masked_equal(hist[m],0),cmap='viridis',vmin=0,vmax=maximum,rasterized=True)
            ax.add_collection(LineCollection(lines,colors='#394b58',linewidths=.45))
            boundary=region_boundary[m];ax.plot(*boundary.T,color='#e75d83',lw=1.3,label='Continuous 90% region')
            ax.scatter(*record['origin'],marker='o',s=35,facecolor='white',edgecolor='#16212e',label='Exact start',zorder=5)
            ax.scatter(*y,marker='*',s=90,facecolor='#fa6b43',edgecolor='#16212e',label='Observed day 7',zorder=6)
            ax.set_xlim(x0,x1);ax.set_ylim(y0,y1);ax.set_aspect(1/np.cos(np.deg2rad((y0+y1)/2)))
            ax.set_title(m);ax.set_xlabel('Longitude');ax.grid(alpha=.15)
        axes[0].set_ylabel('Latitude');axes[0].legend(fontsize=7,loc='best',framealpha=.85)
        fig.colorbar(mesh,ax=axes,shrink=.7,label='Probability per 0.5° display cell')
        fig.suptitle(f'Preselected example {number} · drifter {record["id"]} · {record["origin_time_UTC"][:10]}',fontsize=12)
        filename=f'example_{number:02d}.png';save(fig,filename)
        example_meta.append(dict(number=number,query_position=position,id=record['id'],origin_source_obs=record['origin_source_obs'],date=record['origin_time_UTC'][:10],figure=filename,display_mass={m:float(v.sum()) for m,v in hist.items()},outcome_used_for_selection=False))
    save_json(paths,run['provenance']/'example_display_checks.json',example_meta)
    successful=decision['quality_non_degrading_improvement']
    title='完整实验支持高斯带来质量不退化的改善' if successful else '完整实验完成；高斯未达到质量不退化的改善标准'
    verdict='全部预先规定的比较及保护条件通过，可进入默认模型讨论。' if successful else '本轮保留原有模型，不自动替换默认模型。下面分别报告 ES、实际命中率和面积，避免把指标间的取舍称为全面改善。'
    table=''.join(f'<tr><th>{m}</th><td>{summary.loc[m,"energy_km"]:.6f}</td><td>{summary.loc[m,"h90"]*100:.3f}%</td><td>{summary.loc[m,"area90_km2"]:,.1f}</td><td>{summary.loc[m,"land_mass"]*100:.3f}%</td><td>{summary.loc[m,"outside_D_mass"]*100:.3f}%</td></tr>' for m in models)
    contrasts=''
    for row in comparisons.to_dict('records'):
        contrasts+=f'<tr><th>G − {row["baseline"]}</th><td>{row["es_delta"]:+.5f}<br><small>[{row["es_lower"]:+.5f}, {row["es_upper"]:+.5f}]</small></td><td>{row["hit_delta"]*100:+.3f}<br><small>[{row["hit_lower"]*100:+.3f}, {row["hit_upper"]*100:+.3f}]</small></td><td>{(row["area_ratio"]-1)*100:+.3f}%<br><small>[{(row["area_lower"]-1)*100:+.3f}%, {(row["area_upper"]-1)*100:+.3f}%]</small></td><td>{"通过" if row["eligible"] else "未通过"}</td></tr>'
    why=[]
    label={'es_benefit':'ES 的实用增益与置信区间','quality_preserved':'命中率不下降且面积不扩大','statistical_guardrails':'命中率／面积的不劣区间','geographic_guardrails':'陆地／域外概率保护条件','es_improvement_numerically_resolved':'ES 改善的数值分辨率','hit_direction_resolved':'命中方向的数值分辨率','area_direction_resolved':'面积方向的数值分辨率','geographic_guardrails_resolved':'地理保护条件的数值分辨率','regions_nondegenerate':'非退化区域','superiority_claim_allowed':'主要 ES 检验先行的优越性声明条件'}
    for row in comparisons.to_dict('records'):
        failed=[text for field,text in label.items() if not row[field]]
        why.append(f'<li>相对 {row["baseline"]}：'+('全部条件通过。' if not failed else '未满足 '+ '、'.join(failed)+'。')+'</li>')
    cards=''.join(f'<figure id="example-{r["number"]}" class="example" {"hidden" if r["number"]!=1 else ""}><img src="{r["figure"]}" alt="预选案例 {r["number"]} 的三个模型对照"><figcaption>案例 {r["number"]} · drifter {r["id"]} · {r["date"]}。同一范围、同一概率色标；红色边界来自连续分布，网格仅用于展示。</figcaption></figure>' for r in example_meta)
    buttons=''.join(f'<button type="button" onclick="showExample({r["number"]})">案例 {r["number"]}</button>' for r in example_meta)
    content=f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Step 5 E1 · 全量高斯实验</title><style>
body{{margin:0;background:#f3f6f8;color:#223044;font:16px/1.7 -apple-system,BlinkMacSystemFont,"PingFang SC",sans-serif}}main{{max-width:1160px;margin:auto;padding:40px 24px 60px}}h1{{font-size:32px;line-height:1.35}}h2{{font-size:23px;margin:0 0 16px}}section{{background:white;padding:28px;border-radius:14px;margin:24px 0}}p{{max-width:960px}}.muted,small,figcaption{{color:#697683}}.notice{{border-left:4px solid #dd8041;padding-left:18px}}img{{width:100%;height:auto}}figure{{margin:16px 0}}table{{width:100%;border-collapse:collapse;font-size:14px;white-space:nowrap}}td,th{{text-align:right;padding:12px;border-bottom:1px solid #e2e8ee}}th:first-child{{text-align:left}}thead{{background:#eef3f7}}.scroll{{overflow:auto}}.stats{{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}}.stats b{{display:block;font-size:27px}}button{{background:#eaf0f5;border:1px solid #cdd8e2;border-radius:7px;padding:9px 16px;margin:4px;cursor:pointer}}summary{{cursor:pointer;font-weight:600}}a{{color:#176b9b}}footer{{font-size:12px;overflow-wrap:anywhere}}@media(max-width:680px){{main{{padding:20px 12px}}section{{padding:18px 12px}}h1{{font-size:25px}}.stats{{grid-template-columns:1fr}}}}</style></head><body><main>
<p class="muted">WHERE THINGS END UP · STEP 5 E1 · SEVEN-DAY CONDITIONAL TRANSITION</p><h1>{title}</h1><p>{verdict}</p>
<div class="stats"><div>全部验证起点<b>33,971 / 33,971</b></div><div>评估独立 drifter<b>45</b></div><div>训练参考记录<b>265,393 / 338 IDs</b></div></div>
<p class="notice">2001–2019 训练、2020–2022 开发验证；七天直接预测。三组使用同样的精确起点和历史终点参考记录。本轮结果属于反复研究过的开发验证，未访问最终测试集。</p>
<section><h2>三组模型的完整结果</h2><img src="full_comparison.png" alt="三组模型全量 ES、命中率和面积"><div class="scroll"><table><thead><tr><th>模型</th><th>ES（km）↓</th><th>90% 实际命中率</th><th>平均面积（km²）</th><th>陆地概率</th><th>域外概率</th></tr></thead><tbody>{table}</tbody></table></div><p>每条 drifter 内先平均，再给 45 条 drifter 相同评估权重。训练仍按参考配对等权。域外预测概率不等于观测到的首次退出事件；陆地概率也不代表已经发生搁浅。</p></section>
<section><h2>是否达到了预先规定的改善标准</h2><img src="paired_effects.png" alt="高斯相对两个对照的配对置信区间"><div class="scroll"><table><thead><tr><th>比较</th><th>ES 差值与 95% 区间</th><th>命中差值（百分点）</th><th>平均面积变化与 95% 区间</th><th>综合验收</th></tr></thead><tbody>{contrasts}</tbody></table></div><ul>{''.join(why)}</ul><p>主要比较是 G − ExactPoint，只有该主要 ES 检验通过，才允许作出 G − EndpointCI 的追加优越性结论。所有数值都会报告，不能挑选表现有利的对照。置信区间基于固定预测、10,000 次整条 drifter 配对重采样，不包含重新训练的不确定性。</p></section>
<section><h2>不同 drifter 的表现</h2><img src="per_id_effects.png" alt="45条 drifter 的配对 ES 差异"><p>图中每一条柱对应一条完整保留的验证 drifter。分年份、训练支撑量和单条参考 drifter 贡献比例的结果仅作描述，不用于重新选择模型。</p><p><a href="per_id.csv">逐 ID 指标</a> · <a href="descriptive_strata.csv">分层描述</a> · <a href="leave_one_id_out.csv">逐 ID 留一敏感性</a> · <a href="area_quantiles.csv">区域面积分位数</a></p></section>
<section><h2>六个事先选定的案例</h2><p>这些案例沿用已有固定清单，在读取本轮真实落点前锁定。0.5° cell 仅用于呈现概率，不参与训练、ES 或区域命中判定。</p><nav>{buttons}</nav>{cards}</section>
<section><h2>独立复核与回退</h2><ul><li>全部 33,971 个高斯参数独立重算；全部三个模型的区域和 ES 重新计算并对照，固定 128 个起点另做逐一距离核对及独立 IID 高斯积分。</li><li>每个起点 {support['pairs_min']:,}–{support['pairs_max']:,} 对参考观测，{support['donor_ids_min']}–{support['donor_ids_max']} 个独立训练 drifter；最大协方差条件数 {support['condition_max']:.3f}。无高斯支撑回退、协方差修补或样本删减。</li><li>EndpointCI 的不可用 error 记录保留原终点与完整投票；平均回退概率质量 {summary.loc['EndpointCI','ci_unavailable_mass']*100:.3f}%。</li><li>ES 使用 8,192 对积分样本／起点；每个区域重建包为 32,768 点。数值精度检查通过；真实落点在全量预测冻结后才被读取。</li></ul><p>累计正式执行 {phases['formal']/60:.1f} 分钟、独立复核 {phases['audit']/60:.1f} 分钟。仅资源上限按你的批准调整；模型、样本、训练权重、评分与验收定义未变。</p>
<details><summary>模型究竟训练了什么</summary><p>这轮是解析估计，不是神经网络的多轮迭代训练。在每个查询起点的 100 km、最多最近 8,000 对参考记录（保留距离并列）中，对历史原始终点相对查询位置的 WGS84 东北坐标，估计一个均值向量和完整协方差矩阵。协方差除以 n，保留非对角项，没有加入 ridge、膨胀、误差方差、全局回退或模型融合。</p><p>高斯分布映射回地球后完整保留尾部、陆地和域外概率。共同评分是 ECEF 弦距离 Energy Score；90% 区域是共同 LAEA 坐标中的分布分位椭圆，不是最小面积区域。模型包保存输入身份、完整参数和参考记录关系；它不是只含一组全局均值与协方差的模型。</p></details></section>
<section><h2>可复核交付物</h2><p><a href="summary.csv">完整汇总</a> · <a href="comparisons.csv">配对比较与验收条件</a> · <a href="gaussian_parameters.parquet">全部高斯参数</a> · <a href="model_manifest.json">模型包清单</a> · <a href="technical_report.md">English technical report</a></p></section><footer class="muted">Run: {html.escape(name)}<br>Input hashes, forecast freeze, numerical checks, full independent audit and resource receipts are preserved under the matching provenance run. Default-model selection remains a research decision.</footer></main><script>function showExample(n){{document.querySelectorAll('.example').forEach((e)=>e.hidden=e.id!=='example-'+n);}}</script></body></html>'''
    paths.publish(root/'review.html',lambda f:f.write(content.encode()))
    records=[record for p in sorted((root/'parameters').glob('*.json.gz')) for record in full.read_bundle(p)]
    parameter_table=[]
    for record in records:
        packet=record['gaussian'];cov=packet['covariance']
        parameter_table.append(dict(query_position=record['query_position'],id=record['id'],origin_source_obs=record['origin_source_obs'],
            lon=record['origin'][0],lat=record['origin'][1],mu_east_km=packet['mean'][0],mu_north_km=packet['mean'][1],
            cov_ee_km2=cov[0][0],cov_en_km2=cov[0][1],cov_nn_km2=cov[1][1],pairs=record['pairs'],
            donor_digest=record['donor_digest'],condition_number=packet['condition_number']))
    save_frame(paths,root/'gaussian_parameters.parquet',pd.DataFrame(parameter_table))
    manifest=dict(model='LocalGaussian',stage='Step5 E1',horizon_seconds=604800,fit_period='2001-2019',fitting_pairs=265393,fitting_ids=338,
        query_parameters=33971,parameter_table='gaussian_parameters.parquet',parameter_directory='parameters',donor_lineage_directory='lineage',
        controls=['ExactPoint','EndpointCI'],forecast_directory='forecasts',training_rule='k8000 nearest origins within WGS84 100km, retaining distance ties; equal pair votes',
        law='Full-covariance Gaussian MLE in query-centred WGS84 east/north kilometre coordinates; n-divisor covariance; full geographic pushforward',
        global_neural_network=False,new_position_usage='Load pinned fitting coordinates and the verified NeighbourIndex; select unchanged endpoints; call conditional_gaussian_s5_e1.fit([lon,lat], endpoints). Retain the same support/rank stopping rules.',
        fitting_coordinates=str(inp.ROOT/'results/runs'/cfg['e7_run']/'training_coordinates.parquet'),
        fitting_coordinates_sha256=inp.HASHES['training_coordinates.parquet'],contract_sha256=cfg['contract_sha256'],
        evaluation='2020-2022 development only; no locked final-test access',scientific_decision=decision,
        source_snapshot=str(run['provenance']/'parameters_sources'),data_copied=False)
    save_json(paths,root/'model_manifest.json',manifest)
    text='''# Step 5 E1: full seven-day conditional Gaussian comparison

All 33,971 outer development starts and 45 drifters were retained. The fitting pool contains265,393 pairs/338 IDs from2001–2019; development validation is2020–2022. Locked final-test data were not accessed. The approved resource-only amendment changed limits, not the scientific design.

The Gaussian is a local analytic conditional transition kernel. It fits the same unchanged donor endpoints as the empirical controls, represented in a query-centred WGS84 metric chart. Mean and full covariance are Gaussian MLEs with n in the covariance denominator. No donor displacement transfer, regularisation, variance inflation, CI addition to G, land rejection or missing-support fallback was introduced. There are no epochs or neural optimiser in this experiment.

## Full results

|Model|ES km|H90|Mean area km²|Land mass|Outside-D mass|
|---|---:|---:|---:|---:|---:|
'''+''.join(f'|{m}|{summary.loc[m,"energy_km"]:.8f}|{summary.loc[m,"h90"]:.8f}|{summary.loc[m,"area90_km2"]:.4f}|{summary.loc[m,"land_mass"]:.8f}|{summary.loc[m,"outside_D_mass"]:.8f}|\n' for m in models)
    text+='\n## Paired contrasts and decision\n\n'+comparisons.to_csv(index=False)+'\n\nDecision: **'+decision['decision']+'**. No default was automatically replaced. G−ExactPoint is primary; G−EndpointCI cannot establish a superiority claim unless the primary ES criterion passes. A smaller region with lower observed coverage is a trade-off.\n'
    text+=f'\nEndpointCI retained {int((~train.ci_2d_usable).sum())} unavailable-error training pairs out of {len(train)} as point components with full votes. The reported fallback mass is query- and drifter-weighted, not this unweighted training fraction.\n'
    text+='''
## Scoring, uncertainty and audit

ES uses the common full forecast law and zero-height WGS84 ECEF chord distance in kilometres. A/C retain the independently calibrated squared-distance control variate; G uses eight independent scrambled Sobol replicates. The nominal90% regions use the same LAEA mean/covariance and own-law Mahalanobis quantile ellipse. Regions are neither highest-density nor minimum-area sets;0.5° cells are display only. All six maps use predetermined keys and identical per-example extents and colour scales.

Evaluation averages times within each drifter, then all45 drifters equally. Fitting remains equal by selected pair. Paired intervals use10,000 whole-ID bootstrap draws at seed20261109 and fixed forecasts, omitting refitting uncertainty. The repeatedly inspected outer period supplies development evidence, not an independent final test.

The full Gaussian parameter set was independently reconstructed. All three region and ES calculations were repeated with separate arithmetic paths and numerical streams. Fixed128 outer keys additionally received exhaustive donor reconstruction and independent IID Gaussian ES checks. All numerical gates were checked before scientific claims. Auxiliary mean-squared diagnostics use two independent numerical mean estimates to avoid squared Monte Carlo bias. Geographical prediction mass is retained and reported; it is not reinterpreted as observed first-exit or grounding.

Complete per-ID aggregates, descriptive year/support/share strata, area quantiles and leave-one-ID-out sensitivities accompany this report. Model metadata, full local parameters and donor lineage are saved in the model manifest and parameter bundles. Raw data and prior experiment outputs remain referenced and immutable.
'''
    paths.publish(root/'technical_report.md',lambda f:f.write(text.encode()))
    inp.freeze_sources(paths,run,'report')
    inp.verify(approval);budget.check()
    print(json.dumps(dict(report=str(root/'review.html'),plots=plots,decision=decision['decision'])),flush=True)


if __name__=='__main__':report(sys.argv[1])
