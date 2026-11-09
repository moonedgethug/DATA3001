"""Support-only visualization for a halted G1 run; no performance claims."""
import json
from pathlib import Path
import sys
import time

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from data3001.paths import project_paths,file_sha256
from data3001.modelling.common.runtime import save_json
from data3001.modelling.baselines.b2_grid_translation_inputs import ROOT,Guard,Budget


def report(name):
    started=time.monotonic()
    if Path(name).name!=name or not name.startswith('b2_grid_translation_'):
        raise ValueError('Invalid run identity')
    paths=project_paths()
    run={'results':ROOT/'results/runs'/name,'provenance':ROOT/'provenance/runs'/name}
    cfg=json.loads((run['provenance']/'run.json').read_text())['config']
    guard=Guard(ROOT,run);sys.addaudithook(guard)
    budget=Budget(run,cfg,'report',started=started)
    result=json.loads((run['results']/'support_gate.json').read_text())
    audit=json.loads((run['provenance']/'support_independent_audit.json').read_text())
    assert result['status']=='STOPPED_UNSUPPORTED_ORIGIN'
    assert audit['status']=='VERIFIED_SUPPORT_FAILURE'
    summary=pd.read_csv(run['results']/'support_summary.csv')
    failed=summary.loc[summary.unsupported_queries.gt(0)].copy()
    q=pd.read_parquet(run['results']/'query_starts.parquet')
    affected=pd.read_parquet(run['results']/'affected_queries.parquet')
    base=ROOT/'results/runs'/cfg['source_run']
    with (base/'training_coordinates.parquet').open('rb') as stream:
        train=pd.read_parquet(stream,columns=['lon','lat'])
    arrays=np.load(run['results']/'query_support_arrays.npz')
    source_cells,support=arrays['cells'],arrays['pairs']
    coast=json.loads(paths.asset('release_R').read_text())['features'][0]['geometry']['coordinates'][0]
    coast=np.asarray(coast)

    fig,axes=plt.subplots(1,2,figsize=(13.5,5.2),layout='constrained')
    s=summary.iloc[1:]
    axes[0].bar(s.grid,s.unsupported_queries,color=np.where(s.unsupported_queries.gt(0),'#d66a22','#d1d9e2'),width=.8)
    for row in failed.itertuples():
        axes[0].annotate(str(row.unsupported_queries),(row.grid,row.unsupported_queries),xytext=(0,5),
                         textcoords='offset points',ha='center',fontsize=9)
    axes[0].set(xlabel='Prespecified random grid (1–100)',ylabel='Unsupported validation starts',
                title='5 of 100 translated grids have support gaps',ylim=(0,225))
    axes[0].grid(axis='y',alpha=.2);axes[0].set_axisbelow(True)
    axes[1].scatter(train.lon,train.lat,s=1,c='#b9c4d0',alpha=.22,rasterized=True,label='Qualified training starts')
    axes[1].plot(coast[:,0],coast[:,1],color='#334b65',lw=1.3,label='Release region R')
    axes[1].scatter(affected.lon,affected.lat,s=22,c='#cf5823',edgecolors='white',linewidths=.35,label='Affected validation starts')
    axes[1].set(xlabel='Longitude',ylabel='Latitude',title='267 starts across 3 drifter IDs',
                xlim=(-81.5,-72.5),ylim=(29.6,35.9),aspect=1/np.cos(np.deg2rad(33)))
    axes[1].legend(loc='lower right',fontsize=8)
    fig.suptitle('B2 grid translation — support gate only; forecast scoring not started',fontsize=13)
    paths.publish(run['results']/'support_overview.png',lambda f:fig.savefig(f,format='png',dpi=160))
    plt.close(fig)

    # Explain the largest prespecified support gap, without opening endpoints.
    grid=int(failed.loc[failed.unsupported_queries.idxmax(),'grid'])
    row=summary.loc[summary.grid.eq(grid)].iloc[0]
    missing=support[grid]==0
    codes=np.unique(source_cells[grid,missing])
    boxes=[]
    for code in codes:
        west=-180+row.delta_lon+int(code)%360
        south=-90+row.delta_lat+int(code)//360
        boxes.append((west,south,west+1,south+1))
    x0=min(b[0] for b in boxes)-.2;y0=min(b[1] for b in boxes)-.2
    x1=max(b[2] for b in boxes)+.2;y1=max(b[3] for b in boxes)+.2
    local=train.lon.between(x0,x1)&train.lat.between(y0,y1)
    fig,ax=plt.subplots(figsize=(7.2,6),layout='constrained')
    ax.scatter(train.loc[local,'lon'],train.loc[local,'lat'],s=2,c='#617c91',alpha=.3,label='Training starts')
    for k,(west,south,east,north) in enumerate(boxes):
        ax.add_patch(Rectangle((west,south),1,1,facecolor='#fce9d9',alpha=.5,edgecolor='#c45920',lw=2,
                              label='Shifted cell: zero training starts' if k==0 else None))
    ax.plot(coast[:,0],coast[:,1],color='#334b65',lw=1.1,label='Release region R')
    ax.scatter(q.loc[missing,'lon'],q.loc[missing,'lat'],s=20,c='#d64c22',edgecolors='white',lw=.3,label='Unsupported validation starts')
    ax.set(xlim=(x0,x1),ylim=(y0,y1),xlabel='Longitude',ylabel='Latitude',
           title=f'Grid {grid}: {int(missing.sum())} starts fall into an empty training cell',
           aspect=1/np.cos(np.deg2rad(33)))
    ax.legend(fontsize=8,loc='best')
    paths.publish(run['results']/'support_gap_detail.png',lambda f:fig.savefig(f,format='png',dpi=160))
    plt.close(fig)
    pilot=json.loads((run['provenance']/'pilot_support_resources.json').read_text())
    audit_resource=json.loads((run['provenance']/'support_audit_resources.json').read_text())
    pilot_time=pilot['elapsed_seconds']+pilot['prior_stage_seconds']
    audit_time=audit_resource['elapsed_seconds']+audit_resource['prior_stage_seconds']
    table=failed[['grid','unsupported_queries','unsupported_ids','unsupported_weight']].copy()
    table['unsupported_weight']=table.unsupported_weight.map(lambda x:f'{100*x:.4f}%')
    table.columns=['平移编号','无支撑起点数','涉及 drifter 数','评估权重占比']
    rows='\n'.join('| '+' | '.join(map(str,row))+' |' for row in table.itertuples(index=False,name=None))
    md=f'''# B2 网格变换：支撑检查未通过，正式实验暂停

Run: `{name}`。这是资源试跑前段的支撑诊断，**不是完整实验结果**。

原始 B2 对全部 33,971 个验证起点均有训练支撑。100 个平移网格中，95 个完整支撑，5 个出现缺口。跨网格去重后涉及 **267 个起点（{result['affected_query_fraction']*100:.4f}%）/ 3 条 drifter**，占 drifter 等权评估权重 **{result['affected_evaluation_weight']*100:.4f}%**。

| 平移编号 | 无支撑起点数 | 涉及 drifter 数 | 评估权重占比 |
|---|---:|---:|---:|
{rows}

表中是逐网格计数：合计 294 个“网格—起点”组合，不能当作 294 个不同起点。267 个起点中，240 个缺 1 个分量，27 个缺 2 个分量；其余平移网格并非全部失效。

## 原因与处理

网格移动后，部分验证起点被划入历史训练起点未进入的格子，因此该 B2 行的分母为零，无法形成经验概率。原始网格没有此问题。

按已批准合同第 5 节，完整支撑检查不通过时暂停正式评分：不回退、不删除样本、不重新分配 1/100 权重，也不重新抽取更有利的网格。真实验证落点和锁定最终测试数据均未读取。

**Brier、90% 实际命中率和面积尚未计算。不能据此判断随机平移改善或损害预测质量。** 几何精度与完整资源试跑也未开始，因此尚无可靠的完整实验耗时估计。

## 复核与资源

11 项基础/回归测试通过。独立实现重新构建全部 101 张计数表，核对 3,431,071 个网格—起点支撑记录，计数及支撑差异均为零；核对随机种子、评估权重及输入哈希。

独立审计首次对较大原始 drifter ID 进行整数打包时发生溢出；修正为一一对应的紧凑 ID 编码，并增加回归测试后复核通过。该修正只涉及校验实现，未改变主运行计数、ID 分组、模型或实验定义。失败记录与原代码已保留。

支撑检查与初始测试累计 **{pilot_time:.3f} 秒**；独立复核（含失败尝试和回归测试）累计 **{audit_time:.3f} 秒**。支撑阶段峰值进程树内存 **{pilot['peak_process_tree_rss_bytes']/2**30:.3f} GiB**。此阶段远低于预算，暂停原因是无支撑规则，不是耗时。

## 可视化

![全部网格支撑与受影响起点](support_overview.png)

![最大缺口网格的起点分布](support_gap_detail.png)

后续继续需要先审议无支撑规则并明确批准修改；本次没有实施替代处理。现有代码交付范围为分箱、计数、支撑门槛、独立复核及诊断报告，完整几何重映射与正式评分流程未开发/运行。
'''
    paths.publish(run['results']/'SUPPORT_REPORT.md',lambda f:f.write(md.encode()))
    html=f'''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>B2 网格变换 · 支撑诊断</title><style>body{{font:16px/1.7 system-ui,sans-serif;background:#f3f6fa;color:#203044;margin:0}}main{{max-width:1150px;margin:auto;padding:38px 24px}}h1{{font-size:29px}}.note{{background:#fff3e5;border-left:5px solid #d66a22;padding:17px}}.cards{{display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin:22px 0}}.card,section{{background:white;padding:22px;border-radius:10px;margin-bottom:18px}}strong.big{{display:block;font-size:30px;color:#244b72}}table{{border-collapse:collapse;width:100%}}th,td{{padding:11px;text-align:right;border-bottom:1px solid #dde4ec}}img{{width:100%;height:auto}}a{{color:#235b91}}small{{color:#617186}}@media(max-width:720px){{.cards{{grid-template-columns:repeat(2,1fr)}}}}</style>
<main><small>G1 · 七天预测 · 2001–2019 训练 / 2020–2022 验证</small><h1>支撑检查未通过，正式实验已暂停</h1>
<p class="note">这是一份支撑诊断，不是预测质量报告。Brier、90% 实际命中率和面积尚未计算；正式实验已暂停，模型与实验定义均未改变。</p>
<div class="cards"><div class="card">原始 B2 支撑<strong class="big">100%</strong></div><div class="card">完整支撑的平移网格<strong class="big">95 / 100</strong></div><div class="card">受影响起点<strong class="big">267</strong>占起点数 {result['affected_query_fraction']*100:.4f}%</div><div class="card">受影响评估权重<strong class="big">{result['affected_evaluation_weight']*100:.4f}%</strong>涉及 3 条 drifter</div></div>
<section><h2>哪些平移存在缺口</h2>{table.to_html(index=False,border=0)}<p>逐网格合计 294 次缺口，去重后为 267 个起点；240 个缺 1 个分量，27 个缺 2 个分量。</p><img src="support_overview.png" alt="100 个平移网格的支撑缺口，以及受影响验证起点的位置"></section>
<section><h2>为什么原始 B2 有支撑，平移后没有</h2><p>网格边界变化，让部分验证起点落入没有历史训练起点的格子。该格的经验转移概率分母为零。下图仅展示真实起点及训练格子，不使用验证落点。</p><img src="support_gap_detail.png" alt="第 15 个平移网格的无训练支撑格子"></section>
<section><h2>独立复核与暂停边界</h2><p>全部 101 张计数表、3,431,071 个网格—起点支撑记录经独立实现复核，差异为零。11 项基础/回归测试通过。原始数据和历史代码未改，未读取验证落点或最终测试数据。</p><p>校验代码曾出现较大 drifter ID 的整数打包溢出，已改为等价的紧凑编码并复核；主实验计数和模型定义未改。</p><p>支撑检查及初始测试 {pilot_time:.3f} 秒，独立复核累计 {audit_time:.3f} 秒；支撑阶段峰值内存 {pilot['peak_process_tree_rss_bytes']/2**30:.3f} GiB。几何精度试跑尚未开始，不能外推完整实验耗时。</p><p>依据合同：不删除无支撑样本，不回退，不重新分配权重，不重新抽取网格。继续前须先审阅并批准新的无支撑处理规则。</p></section>
<p><a href="SUPPORT_REPORT.md">完整诊断报告</a> · <a href="support_summary.csv">全部 101 个网格支撑数据</a> · <a href="support_gate.json">暂停状态记录</a></p><small>{name}</small></main></html>'''
    paths.publish(run['results']/'support_review.html',lambda f:f.write(html.encode()))
    source=Path(__file__)
    paths.publish(run['provenance']/'report_sources'/source.name,lambda f:f.write(source.read_bytes()))
    save_json(paths,run['provenance']/'support_report_resources.json',budget.check())
    print(str(run['results']/'support_review.html'),flush=True)


if __name__=='__main__':report(sys.argv[1])
