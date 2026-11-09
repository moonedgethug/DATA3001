"""Layout-only presentation of frozen scores; no fit, score, or selection changes."""
import time
START=time.monotonic()
import json,os
from pathlib import Path
import pandas as pd
import numpy as np
from data3001.paths import file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.continuous_models import local_gmm_s5_e2_pipeline as pipe
NAME='local_gmm_s5_e2_vector_20261107T133426Z'
paths,run,cfg,approval,guard=pipe.context(NAME)
budget=pipe.Budget(run,cfg,'report','presentation',START);complete=False
try:
    folder=run['results']/'review'
    source=folder/'index.html'
    release=run['provenance']/'delivery_release.json'
    receipt=json.loads(release.read_text());assert receipt['complete']
    for path,h in receipt['result_sha256'].items():assert file_sha256(pipe.ROOT/path)==h
    os.environ['MPLCONFIGDIR']=str(run['provenance']/'delivery_plot_cache')
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    comparisons=pd.read_csv(run['results']/'comparisons.csv')
    sensitivity=pd.read_csv(folder/'leave_one_id_out.csv')
    outputs=[]
    def save(fig,name):
        paths.publish(folder/name,lambda f:fig.savefig(f,format='png',dpi=160,bbox_inches='tight'))
        plt.close(fig);outputs.append(folder/name);budget.check()
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    for ax,field,lo,hi,zero,label in zip(axes,['es_delta','hit_delta','area_ratio'],['es_lower','hit_lower','area_lower'],['es_upper','hit_upper','area_upper'],[0,0,1],['Selected model minus baseline ES (km)','Selected model minus baseline hit rate','Selected model / baseline area']):
        v=comparisons[field].to_numpy()
        ax.errorbar(v,np.arange(3),xerr=np.vstack([v-comparisons[lo],comparisons[hi]-v]),fmt='o',color='#845ab0',capsize=3)
        ax.axvline(zero,color='#777',lw=.8);ax.set_yticks(range(3),comparisons.baseline);ax.set_title(label,fontsize=10);ax.grid(axis='x',alpha=.12)
    fig.suptitle('Outer development validation: 95% paired drifter bootstrap intervals')
    save(fig,'paired_effects_readable.png')
    fig,axes=plt.subplots(1,3,figsize=(15,4),layout='constrained')
    baselines=['LocalGaussian','ExactPoint','EndpointCI']
    for ax,field,zero,label in zip(axes,['es_delta','hit_delta','area_ratio'],[0,0,1],['Selected model minus baseline ES (km)','Selected model minus baseline hit rate','Selected model / baseline area']):
        for j,baseline in enumerate(baselines):
            values=sensitivity[sensitivity.baseline.eq(baseline)][field]
            ax.scatter(values,np.full(len(values),j),s=12,alpha=.55,color='#845ab0')
        ax.axvline(zero,color='#777',lw=.8);ax.set_yticks(range(3),baselines);ax.set_title(label,fontsize=10);ax.grid(axis='x',alpha=.12)
    fig.suptitle('Leave-one-drifter-out sensitivity: fixed predictions, no refitting')
    save(fig,'leave_one_id_out_readable.png')
    original=source.read_text()
    content=original.replace('../paired_effects.png','paired_effects_readable.png').replace('src="leave_one_id_out.png"','src="leave_one_id_out_readable.png"')
    explanation='<section><h2>本轮结论</h2><p>K=2 在内部验证中将平均 ES 从 171.329 降至 170.562 km（约 0.45%），但两个时间窗口的实际命中率分别下降 0.081、0.306 个百分点。按预先锁定的“不下降”要求，最终回到 K=1；K=3 因回退率超过 5% 未获晋级资格。</p><p>因此，外层的 LocalGMM 与 LocalGaussian 是同一个模型。相较 ExactPoint，ES 点估计约高 0.41%，命中率高约 0.152 个百分点，面积大约 0.20%；未达到质量不退化的改善标准。这不是证明多峰分布没有价值，而是本轮定义与验收规则没有支持采用多成分。</p><p>完整训练与独立复核已完成。报告生成阶段的类型与启动衔接问题已恢复；模型、所有样本、训练权重、评分精度及验收门槛均未改变。</p></section>'
    content=content.replace('<section><h2>1. 训练期如何选择 K</h2>',explanation+'<section><h2>1. 训练期如何选择 K</h2>')
    paths.publish(folder/'final.html',lambda f:f.write(content.encode()))
    outputs.append(folder/'final.html')
    save_json(paths,run['provenance']/'presentation_release.json',dict(complete=True,layout_only=True,model_or_scores_changed=False,
        base_html_sha256=file_sha256(source),delivery_release_sha256=file_sha256(release),
        source_sha256=file_sha256(Path(__file__)),result_sha256={str(f.relative_to(pipe.ROOT)):file_sha256(f) for f in outputs}))
    complete=True;print('PRESENTATION_COMPLETE',folder/'final.html',flush=True)
finally:budget.finish(paths,'presentation',complete,guard)
