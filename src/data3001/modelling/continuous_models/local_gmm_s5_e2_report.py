"""Paired development decisions and fixed-example four-arm visual report."""
import html
import json
import os
import numpy as np
import pandas as pd
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_frame,save_json
from . import conditional_gaussian_s5_e1_full as io
from . import conditional_gaussian_s5_e1_analysis as prior_analysis
from . import conditional_gaussian_s5_e1_numerics as prior_num
from . import local_gmm_s5_e2 as model
from .local_gmm_s5_e2_selection import geographic_guard

MODELS=['ExactPoint','EndpointCI','LocalGaussian','LocalGMM']


def compare(table,numerical_pass):
    fields=[c for c in ['energy_km','h90','area90_km2','land_mass','outside_D_mass','fallback','auxiliary_loss',
        'ci_unavailable_mass','largest_id_share','independent_ids','pairs','model_mass90'] if c in table]
    per_id=table.groupby(['id','model'])[fields].mean().reset_index()
    summary=per_id.groupby('model')[fields].mean();ids=sorted(per_id.id.unique())
    g=per_id[per_id.model.eq('LocalGMM')].set_index('id').loc[ids]
    draws=np.random.default_rng(20261111).integers(len(ids),size=(10000,len(ids)))
    rows=[];sequence=True
    for base in ['LocalGaussian','ExactPoint','EndpointCI']:
        b=per_id[per_id.model.eq(base)].set_index('id').loc[ids]
        es=(g.energy_km-b.energy_km).to_numpy();hit=(g.h90-b.h90).to_numpy()
        ag=g.area90_km2.to_numpy();ab=b.area90_km2.to_numpy()
        ec=np.quantile(es[draws].mean(1),[.025,.975]);hc=np.quantile(hit[draws].mean(1),[.025,.975])
        ac=np.quantile(ag[draws].mean(1)/ab[draws].mean(1),[.025,.975])
        row=dict(baseline=base,es_delta=float(es.mean()),es_relative=float(es.mean()/b.energy_km.mean()),
            es_lower=float(ec[0]),es_upper=float(ec[1]),hit_delta=float(hit.mean()),hit_lower=float(hc[0]),
            hit_upper=float(hc[1]),area_ratio=float(ag.mean()/ab.mean()),area_lower=float(ac[0]),area_upper=float(ac[1]),
            land_delta=float((g.land_mass-b.land_mass).mean()),outside_delta=float((g.outside_D_mass-b.outside_D_mass).mean()))
        row.update(prior_analysis.decision(**{k:row[k] for k in ['es_delta','es_relative','es_upper','hit_delta',
            'hit_lower','area_ratio','area_upper','land_delta','outside_delta']},numerical=numerical_pass))
        gg=table[table.model.eq('LocalGMM')].sort_values(['id','query_position'] if 'query_position' in table else ['id'])
        bb=table[table.model.eq(base)].sort_values(['id','query_position'] if 'query_position' in table else ['id'])
        w=prior_num.id_weights(gg.id)
        hiterr=float(w@(gg.hit_disagreement.to_numpy()+bb.hit_disagreement.to_numpy()))
        areaerr=abs(float(w@(gg.area_replica_km2.to_numpy()-gg.area90_km2.to_numpy())))/(w@gg.area90_km2.to_numpy())
        areaerr+=abs(float(w@(bb.area_replica_km2.to_numpy()-bb.area90_km2.to_numpy())))/(w@bb.area90_km2.to_numpy())
        if base=='LocalGaussian' and 'replicate_means' in table:
            diff=np.asarray(gg.replicate_means.tolist())-np.asarray(bb.replicate_means.tolist())
            var=diff.var(1,ddof=1)/8
        else:var=gg.variance.to_numpy()+bb.variance.to_numpy()
        eserr=float(3*np.sqrt(w*w@var))
        row.update(hit_numerical_error=hiterr,area_numerical_error=float(areaerr),es_numerical_error=eserr,
            effect_resolved=eserr<=.1*abs(row['es_delta']),quality_resolved=bool(hiterr<=.1*abs(row['hit_delta']) and areaerr<=.1*abs(row['area_ratio']-1)),
            fallback_pass=bool(g.fallback.mean()<=.05))
        geography=geographic_guard(table,'LocalGMM',base)
        row['geographic_guardrails']=geography['passed']
        row['land_numerical_three_se']=geography['land_mass']['three_se_bound']
        row['outside_numerical_three_se']=geography['outside_D_mass']['three_se_bound']
        row['eligible']=bool(row['eligible'] and row['effect_resolved'] and row['quality_resolved'] and row['fallback_pass'] and geography['passed'])
        sequence=sequence and row['es_benefit'] and row['effect_resolved']
        row['sequential_superiority_allowed']=bool(sequence)
        rows.append(row)
    return summary,per_id,pd.DataFrame(rows)


def report(paths,run,cfg,budget):
    from . import local_gmm_s5_e2_pipeline as pipe
    from data3001.modelling.baselines import position_error_s4_e8 as geo_math
    from data3001.modelling.baselines import position_error_s4_e8_inputs as inputs
    from data3001.modelling.baselines import seasonal_exact_position_s4_e9_esopt as opt
    from data3001.modelling.baselines.position_error_s4_e8_geometry import Geography
    import shapely
    from shapely.geometry import box
    os.environ['MPLCONFIGDIR']=str(run['provenance']/'plot_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    from matplotlib.collections import LineCollection
    audit=json.loads((run['provenance']/'full_audit.json').read_text())
    if not audit['passed']:raise ValueError('Cannot publish unverified results')
    choice=json.loads((run['provenance']/'selection.json').read_text())
    table=pd.read_parquet(run['results']/'metrics.parquet');summary,per_id,contrasts=compare(table,True)
    # Claim-specific independent numerical replication must also resolve each gain.
    for i,r in contrasts.iterrows():
        g=audit['models']['LocalGMM'];b=audit['models'][r.baseline]
        drift=abs(g['es_difference']-b['es_difference'])
        contrasts.loc[i,'independent_es_drift']=drift
        contrasts.loc[i,'eligible']=bool(r.eligible and drift<=.1*abs(r.es_delta))
    success=bool(contrasts.eligible.all())
    for name,frame in [('summary.csv',summary.reset_index()),('per_id.csv',per_id),('comparisons.csv',contrasts)]:save_frame(paths,run['results']/name,frame)
    decision=dict(selected_k=choice['selected_k'],quality_non_degrading_improvement=success,
        decision='SUPPORTED_NONDEGRADING_IMPROVEMENT' if success else 'NO_SUPPORTED_NONDEGRADING_IMPROVEMENT',
        development_only=True,default_automatically_replaced=False)
    save_json(paths,run['provenance']/'decision.json',decision)
    colours=['#657c91','#269c9a','#dd944b','#845ab0'];plots=[]
    def save(fig,name):
        paths.publish(run['results']/name,lambda f:fig.savefig(f,format='png',dpi=150,bbox_inches='tight'))
        plt.close(fig);plots.append(name);budget.check()
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,field,label in zip(axes,['energy_km','h90','area90_km2'],['Energy Score (km) — lower','Observed 90% hit rate','Mean 90% ellipse area (km²)']):
        vals=summary.loc[MODELS,field];ax.bar(MODELS,vals,color=colours);ax.set_title(label,fontsize=10)
        ax.tick_params(axis='x',rotation=24);ax.grid(axis='y',alpha=.15)
    save(fig,'full_comparison.png')
    fig,axes=plt.subplots(1,3,figsize=(13,4))
    for ax,field,lo,hi,zero,label in zip(axes,['es_delta','hit_delta','area_ratio'],['es_lower','hit_lower','area_lower'],
        ['es_upper','hit_upper','area_upper'],[0,0,1],['GMM − baseline ES','GMM − baseline hit rate','GMM / baseline area']):
        v=contrasts[field].to_numpy();ax.errorbar(v,np.arange(3),xerr=np.vstack([v-contrasts[lo],contrasts[hi]-v]),fmt='o',color='#845ab0')
        ax.axvline(zero,color='#777',lw=.8);ax.set_yticks(range(3),contrasts.baseline);ax.set_title(label,fontsize=10)
    save(fig,'paired_effects.png')
    pivot=per_id.pivot(index='id',columns='model',values='energy_km');delta=pivot.LocalGMM-pivot.ExactPoint
    fig,ax=plt.subplots(figsize=(12,4));ax.bar(range(len(delta)),delta,color=np.where(delta<0,'#269c9a','#dd944b'))
    ax.axhline(0,color='#777');ax.set_ylabel('LocalGMM − ExactPoint ES (km)');ax.set_xlabel('All 45 drifters');save(fig,'per_id_effects.png')
    # Gather descriptive fit diagnostics, without using them to change the chosen model.
    diag=[]
    for p in sorted((run['results']/'C_outer/parameters').glob('*.json.gz')):
        for r in io.read_bundle(p):
            m=r['models'][str(choice['selected_k'])]
            diag.append(dict(id=r['id'],query_position=r['query_position'],K_requested=m['K_requested'],K_effective=m['K_effective'],
                fallback=m['fallback'],fallback_reason=m['fallback_reason'],pairs=r['pairs'],independent_ids=r['independent_ids'],
                largest_id_share=r['largest_id_share'],ci_unavailable_mass=r['ci_unavailable_mass'],
                component_weights=m['weights'],component_diagnostics=m['component_diagnostics']))
    diagnostics=pd.DataFrame(diag);save_frame(paths,run['results']/'fit_diagnostics.parquet',diagnostics)
    summary_fallback=dict(query_fraction=float(diagnostics.fallback.mean()),drifter_equal_fraction=float(diagnostics.groupby('id').fallback.mean().mean()),
        affected_ids=int(diagnostics.loc[diagnostics.fallback,'id'].nunique()),total_ids=45,
        ci_unavailable_vote_mass=float(summary.loc['EndpointCI','ci_unavailable_mass']))
    save_json(paths,run['provenance']/'fallback_summary.json',summary_fallback)
    # Only the six previously frozen E1 examples are rendered.
    examples=json.loads((run['provenance']/'example_selection.json').read_text())['examples']
    pipe.verify_freeze(run['provenance'],'C_outer',33971)
    approval=json.loads((run['provenance']/'approval.json').read_text())
    # Parent guards are held by run_phase; release only after the complete freeze was verified.
    for guard in pipe.ACTIVE_GUARDS:guard.outcomes_allowed=True
    truth=inputs.release_outer_targets(run,cfg,approval).sort_values(inputs.KEY).reset_index(drop=True)
    train,_=inputs.load_training(cfg);geo=Geography(paths);cache=opt.cache(train,geo);maps=[]
    for number,example in enumerate(examples,1):
        pos=int(example['query_position']);batch,j=divmod(pos,cfg['batch_size']);files=pipe.batch_paths(run,'C_outer',batch)
        r=io.read_bundle(files['parameters'])[j];forecast=io.read_bundle(files['regions'])[j]
        for key in inputs.KEY:
            if int(r[key])!=int(example[key]):raise ValueError('Frozen example changed')
        with np.load(files['lineage']) as f:ix=io.unpack_lineage(f['indices'],f['offsets'],j)
        pool=cache.take(ix);key=tuple(r['key'])
        clouds={'ExactPoint':(pool.points,np.full(len(pool.points),1/len(pool.points)))}
        p,w,_=geo_math.component_cloud(pool.points,pool.sd,pool.usable,65536,('s5_e2_v1',*key,'display_ci'))
        clouds['EndpointCI']=(p,w)
        for name,K in [('LocalGaussian',1),('LocalGMM',choice['selected_k'])]:
            packet=r['models'][str(K)];p=np.concatenate(model.draw_components(packet,model.normals(65536,2,(*key,'display'))))
            clouds[name]=(p,np.repeat(np.asarray(packet['weights'])/65536,65536))
        labels={'ExactPoint':'ExactPoint','EndpointCI':'EndpointCI','LocalGaussian':'1','LocalGMM':str(choice['selected_k'])}
        boundaries={}
        for name,label in labels.items():
            b=geo_math.ellipse_boundary(forecast['regions'][label]['region'])
            boundaries[name]=np.column_stack(geo_math.INVERSE.transform(b[:,0]*1000,b[:,1]*1000))
        y=truth.iloc[pos][['endpoint_lon','endpoint_lat']].to_numpy(float)
        extent=np.vstack([c[0] for c in clouds.values()]+list(boundaries.values())+[np.array([r['origin'],y])])
        x0,y0=np.floor(extent.min(0)*2)/2-.5;x1,y1=np.ceil(extent.max(0)*2)/2+.5
        xb=np.arange(x0,x1+.25,.5);yb=np.arange(y0,y1+.25,.5)
        hist={name:np.histogram2d(p[:,0],p[:,1],bins=(xb,yb),weights=w)[0].T for name,(p,w) in clouds.items()}
        for h in hist.values():np.testing.assert_allclose(h.sum(),1.,atol=1e-10)
        maximum=max(h.max() for h in hist.values());lines=[]
        for polygon in shapely.get_parts(geo.land.intersection(box(x0,y0,x1,y1))):
            if polygon.geom_type=='Polygon':lines.append(np.asarray(polygon.exterior.coords))
        fig,axes=plt.subplots(2,2,figsize=(11,9),sharex=True,sharey=True,layout='constrained')
        for ax,name in zip(axes.ravel(),MODELS):
            mesh=ax.pcolormesh(xb,yb,np.ma.masked_equal(hist[name],0),vmin=0,vmax=maximum,cmap='viridis')
            ax.add_collection(LineCollection(lines,colors='#384b5c',linewidths=.5));ax.plot(*boundaries[name].T,color='#e45381',lw=1.2)
            ax.scatter(*r['origin'],s=30,facecolor='white',edgecolor='black');ax.scatter(*y,marker='*',s=95,color='#ff7955',edgecolor='black')
            ax.set_xlim(x0,x1);ax.set_ylim(y0,y1);ax.set_title(name);ax.set_xlabel('Longitude');ax.set_ylabel('Latitude')
            ax.set_aspect(1/np.cos(np.deg2rad((y0+y1)/2)))
        fig.colorbar(mesh,ax=axes.ravel().tolist(),shrink=.7,label='Probability per 0.5° display cell')
        fig.suptitle(f'Fixed example {number} · drifter {r["id"]} · day 7')
        filename=f'example_{number:02d}.png';save(fig,filename);maps.append(filename)
    table_html=summary.loc[MODELS,['energy_km','h90','area90_km2','land_mass','outside_D_mass']].to_html(float_format=lambda x:f'{x:,.6f}')
    verdict='达到质量不退化改善标准' if success else '未达到质量不退化改善标准'
    content=f'''<!doctype html><html lang="zh"><meta charset="utf-8"><title>Step 5 E2 局部 GMM</title>
<style>body{{font:16px/1.7 system-ui;background:#f4f6f8;color:#233244;margin:0}}main{{max-width:1150px;margin:auto;padding:36px}}section{{background:white;padding:24px;margin:20px 0;border-radius:12px}}img{{width:100%;height:auto}}table{{border-collapse:collapse;width:100%;font-size:14px}}th,td{{padding:8px;border-bottom:1px solid #ddd;text-align:right}}h1{{font-size:30px}}.note{{color:#526679}}</style><main>
<h1>Step 5 E2 · 局部高斯混合</h1><p>训练期选出 K={choice['selected_k']}。{verdict}。</p>
<p class="note">七天预测；2001–2019 训练、2020–2022 开发验证；完整 33,971 个起点、45 条 drifter。近邻、原始终点及配对训练票数保持不变。K=1 时 LocalGMM 与 LocalGaussian 是同一模型。</p>
<section><h2>四组完整结果</h2>{table_html}<img src="full_comparison.png"><p>ES 越低越好；命中率与面积须一起判断。区域统一为完整分布的单个 90% 分位椭圆，0.5° cell 仅用于展示。</p></section>
<section><h2>配对效果与不确定性</h2><img src="paired_effects.png"><img src="per_id_effects.png"><p>区间来自 10,000 次整条 ID 重抽；这里是开发验证证据，不是独立最终测试。</p></section>
<section><h2>支撑与回退</h2><p>GMM 查询回退：{summary_fallback['query_fraction']:.3%}；drifter 等权回退：{summary_fallback['drifter_equal_fraction']:.3%}；涉及 {summary_fallback['affected_ids']} / 45 条 drifter。EndpointCI 不可用 error 的保留点质量：{summary_fallback['ci_unavailable_vote_mass']:.3%}。两种回退含义不同。</p></section>
<section><h2>六个预先固定案例</h2><p>白点为真实起点，星号为七天后记录位置，红线为共同定义的 90% 椭圆。每例四组使用相同范围与色标。</p>{''.join('<img src="'+p+'">' for p in maps)}</section>
<section><h2>可复核文件</h2><p><a href="summary.csv">汇总</a> · <a href="comparisons.csv">配对验收</a> · <a href="fit_diagnostics.parquet">拟合诊断</a> · <a href="technical_report.md">技术报告</a></p></section><footer>{html.escape(run['results'].name)}</footer></main></html>'''
    paths.publish(run['results']/'review.html',lambda f:f.write(content.encode()))
    text=f'''# Step 5 E2: complete local Gaussian mixture experiment

Training-only selection chose K={choice['selected_k']}; candidates were 1, 2, 3. The user's explicit amendment removed the resource pilot. Integration counts were frozen at the highest registered levels before fitting: ES 65,536 per component pair; region 65,536 per component. No model or donor rule was changed.

All 86,373 inner validation starts and 33,971 outer development starts were retained. Pair-equal training and drifter-equal evaluation are distinct. The final-test data remained locked. Local mixtures fit original donor endpoints, using five deterministic constrained-EM starts, full covariance and predeclared component support/fallback rules. No MDN, displacement transfer, CI addition to GMM or environmental features were used.

## Results

{summary.to_csv()}

## Paired comparisons

{contrasts.to_csv(index=False)}

Decision: **{decision['decision']}**. K=1 means the selected candidate is identical to the single Gaussian; it does not prove the physical destination distribution is unimodal. Components are statistical approximations, not identified current systems. A single common 90% ellipse can cover low-density gaps between components; it is not an HDR.

Fallback: {json.dumps(summary_fallback)}

ES uses the complete geographic forecast in zero-height WGS84 ECEF kilometres. All probability on land and outside the domain is retained. Bootstrap uncertainty conditions on fitted forecasts and omits refitting uncertainty. The repeatedly inspected outer period is development evidence only. The independent audit reconstructs all final fit arithmetic and all outer scores/regions, and independently refits fixed subsets rather than claiming a global optimum.
'''
    paths.publish(run['results']/'technical_report.md',lambda f:f.write(text.encode()))
    manifest=dict(run=run['results'].name,selected_k=choice['selected_k'],models=MODELS,
        contract_sha256=cfg['contract_sha256'],full_audit_passed=True,model_parameters='C_outer/parameters',
        donor_lineage='C_outer/lineage',regions='C_outer/regions',final_test_access=False)
    save_json(paths,run['results']/'model_manifest.json',manifest)
    for path,h in approval['protected_files'].items():
        if file_sha256(pipe.ROOT/path)!=h:raise ValueError('Protected file modified')
    save_json(paths,run['provenance']/'release_manifest.json',dict(complete=True,decision=decision,
        contract_sha256=cfg['contract_sha256'],final_test_access=False,
        result_sha256={str(p.relative_to(pipe.ROOT)):file_sha256(p) for p in run['results'].rglob('*') if p.is_file()}))
    print(json.dumps(dict(report=str(run['results']/'review.html'),decision=decision)),flush=True)
