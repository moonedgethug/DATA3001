"""Assemble verified optimization evidence; no forecast or model computation."""
import hashlib
import json
from pathlib import Path
from datetime import datetime,timezone

root=Path.cwd();p=Path(__file__).resolve().parent;prov=p.parent
v=json.loads((p/'validation.json').read_text())
assert v['passed'] and not v['full_experiment_resumed'] and not v['outer_targets_read']
for name,h in json.loads((p/'source_hashes.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h, name
for name,h in json.loads((prov/'source_hashes.json').read_text()).items():
    assert hashlib.sha256((root/name).read_bytes()).hexdigest()==h, name
resources=[json.loads(f.read_text()) for f in prov.glob('scoreopt_*_resources.json')]
elapsed=sum(r['elapsed_seconds'] for r in resources)
assert elapsed<600
speed=v['same_workload_speedup'];reduction=100*(1-1/speed)
historical_reduction=100*(1-1/v['historical_batch_speedup'])
geo=v['new_profile_128_queries']['geography_ecef']/v['matched_new_worker_seconds']
remaining=86373-2176
batch_hours=v['retained_cost']['wall_seconds']/2176*remaining/3600
matched_hours=v['matched_new_worker_seconds']/128*remaining/2/3600
old=json.loads((prov/'resource_amendment_proposal.json').read_text())
es_p95=old['estimated_remaining_inner_energy_hours']['p95']/speed
new_min=min(batch_hours,matched_hours);new_max=max(batch_hours,matched_hours,es_p95)
spent_inner=old['spent_hours']['inner'];audit=old['estimated_inner_audit_hours']
projection=dict(remaining_inner_ES_hours=[new_min,new_max],matched_128_compute_only_hours=matched_hours,
    retained_2176_batch_wall_projection_hours=batch_hours,old_p95_divided_by_matched_speedup_hours=es_p95,
    cumulative_inner_without_optional_regions_hours=[spent_inner+new_min+audit,spent_inner+new_max+audit],
    cumulative_inner_with_K2_regions_hours=[spent_inner+new_min+audit+old['optional_K2_region_hours']['mean'],
        spent_inner+new_max+audit+old['optional_K2_region_hours']['p95']],
    whole_experiment_cumulative_planning_hours=[9,16],remaining_whole_experiment_rough_hours=[6,13],
    limitations=['Timing is not a full-cohort guarantee','Retained 2176 cases contain only two IDs; fixed128 spans both windows and 70 distinct IDs',
        'Region and independent-audit costs are previous proxies, not newly measured','No formal runner activation or resource amendment'])
(p/'runtime_projection.json').write_text(json.dumps(projection,indent=2)+'\n')
peak=max(r.get('peak_process_tree_rss_bytes',0) for r in resources)/2**30
report=f'''# Step 5 E2：ES 评分优化与等价性验证

状态：**验证通过，收益有限；完整实验继续暂停，等待用户审阅。**

## 实测结果

| 检查 | 原实现 | 优化实现 | 结论 |
|---|---:|---:|---|
| 固定 128 查询的同负载调用耗时之和 | {v['matched_old_worker_seconds']:.3f} worker-seconds | {v['matched_new_worker_seconds']:.3f} worker-seconds | {speed:.3f} 倍速，时间减少 {reduction:.2f}% |
| 既有 2,176 查询的批次耗时之和 | {v['retained_old_worker_seconds']:.3f} worker-seconds | {v['retained_new_worker_seconds']:.3f} worker-seconds | 历史对比 {v['historical_batch_speedup']:.3f} 倍速，时间减少 {historical_reduction:.2f}% |
| 新实现核对 2,176 查询的实际墙钟 | — | {v['retained_cost']['wall_seconds']:.3f} 秒 | 两个 spawn worker，包含批次读取和核对 |
| 逐组积分均值、ES、方差最大绝对差 | — | 全部 0 | 本次测试输出逐值一致 |

固定 128 查询沿用两个内层窗口的预定源键，共覆盖 70 个独立 ID；候选均包含 K=1/2/3及合法回退。原/新计时在查询间交替顺序，不把历史硬件负载差异当作确定加速。2,176 查询只覆盖 2 个 ID，因此它主要验证已完成结果可复用；速度判断以跨窗口的配对 128 查询为主。两组检查有少量重合，不称作 2,304 个不同查询。

## 瓶颈证据

优化实现中，地理映射与 ECEF 转换占固定 128 查询评分时间的 **{geo*100:.2f}%**。共享基础 Sobol 节点、批量坐标调用和编译后的距离累加均已实现，但不同高斯成分的预测点仍须分别完成 WGS84 地理映射。因而未达到此前 1.2–1.5 倍的待验证目标。

主评分继续使用原 WGS84 地理库、完整独立双样本和全部 K² 项，没有改用平面距离、解析近似、低精度浮点、减小 N/M 或删除组件。新接口仅准备评分所需冻结参数，不建立邻近搜索、训练陆地缓存或解压 donor lineage。正式 runner 的资源目录扫描没有修改，本轮也未宣称获得这部分加速；原预算监控继续生效。

## 精度与安全

- N=M=65,536，8 个独立 replicate；参数、权重、种子、基础节点和完整样本定义不变。
- 固定 128 查询及全部已完成 2,176 查询均核对全部候选；各 replicate、ES、方差、drifter 等权汇总及配对数值误差一致。
- 固定 128 查询的单进程/双进程输出逐值完全一致。
- 758 项项目测试通过。唯一显示的警告是旧测试的 pandas 参数兼容性提示，不影响本轮结果。
- 独立只读代码审阅发现进程组清理问题：现已通过实际孤儿子进程回归测试修正，并在上限内预留清理时间。
- 一次项目测试被资源监控的 PermissionError 安全中断，10.915 秒已计入预算；增强异常记录后原检查重跑通过，未绕过监控。该次异常没有完整堆栈，因此不宣称已证明其根因。
- 核对了 {v['original_files_verified']} 个既有输出/配置文件以及正式源文件清单；全部保持原哈希。没有读取外层目标或锁定 final-test，没有重新拟合模型。
- 已完成模型和 ES 保留；本次核对结果只保存在独立验证目录，没有追加为完整实验的新评分结果。

## 资源与预计耗时

生成本报告前，全部新增可执行检查累计 **{elapsed:.3f} 秒（{elapsed/60:.2f} 分钟）**，包括失败尝试、编译、测试和数值验证；报告命令的最终耗时另计入同一收据，最终总数见 `completion.json`。仍受原 checks 预算和新增 600 秒上限约束。检查进程树监测峰值约 {peak:.3f} GiB，低于 8 GiB 硬上限。

| 后续阶段 | 更新估计 | 依据 |
|---|---:|---|
| 剩余完整内层 ES | {new_min:.2f}–{new_max:.2f} 小时 | 新批次吞吐量、跨窗口同负载计时及旧 p95 的保守换算 |
| 内层独立审计 | 约 {audit:.2f} 小时 | 之前的审计成本推算，本轮未重跑 |
| 若 K=2 进入区域验收 | 另加约 3.48–3.96 小时 | 历史 E1 同精度成本代理，未宣称已实测加速 |
| 全部实验累计 | 仍约 9–16 小时 | 包含已发生计算；外层/区域/审计仍有明显估计不确定性 |
| 从当前继续至完整交付 | 约 6–13 小时 | 粗略规划，不是运行许可或完成保证 |

按配对计时，剩余内层 ES 预计节约约 10–12 分钟；历史批次对比给出约 20 分钟量级的乐观参考。计算层优化可以保留，但没有消除高精度几何积分的主要成本。

不加入额外安全余量时，完整内层累计预计 {projection['cumulative_inner_without_optional_regions_hours'][0]:.2f}–{projection['cumulative_inner_without_optional_regions_hours'][1]:.2f} 小时；若需要 K=2 区域验收则约 {projection['cumulative_inner_with_K2_regions_hours'][0]:.2f}–{projection['cumulative_inner_with_K2_regions_hours'][1]:.2f} 小时。因此不能认定原 6 小时内层预算已足够。

## 交付与边界

新增评分器：`src/data3001/modelling/continuous_models/local_gmm_s5_e2_scoreopt.py`。原正式程序、配置、已保存分布和评分未改变。优化器处于独立可验证状态，尚未接入完整实验入口；没有改变 K 选择、区域定义或独立审计路径。本次不是新的模型性能实验，也没有关于 GMM 优劣的结论。

详细证据：`validation.json`、`equivalence.csv`、`runtime_projection.json`、`independent_review.json`、`source_hashes.json`、`preserved_outputs.json` 和对应资源收据。
'''
(p/'report.md').write_text(report)
(p/'report_checks.json').write_text(json.dumps(dict(passed=True,source_hashes_verified=True,formal_sources_unchanged=True,
    formal_execution_paused=True,reported_at=datetime.now(timezone.utc).isoformat(),validation_sha256=hashlib.sha256((p/'validation.json').read_bytes()).hexdigest()),indent=2)+'\n')
print(json.dumps(dict(report=str(p/'report.md'),speedup=speed,time_reduction_percent=reduction,
    geography_fraction=geo,remaining_ES_hours=[new_min,new_max],checks_seconds_before_reporting=elapsed)))
