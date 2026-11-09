"""Render a diagnostic receipt from saved pilot outputs; never fit or integrate."""
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[3]
PROV = Path(__file__).resolve().parent
RESULTS = ROOT / 'results/runs' / PROV.name
OUT = ROOT / 'results/deliverables/conditional_mdn_s5_e3_pilot'
OUT.mkdir(parents=True, exist_ok=True)
read = lambda name: json.loads((PROV / name).read_text())
pilot = read('pilot_result.json')
ledger = read('resource_ledger.json')
approval = read('approval.json')
training = read('pilot_training_receipt.json')
cfg = read('run.json')['config']
rows = [row for path in sorted((RESULTS / 'pilot_numerics/N65536_M65536').glob('C_T*.json'))
        for row in json.loads(path.read_text())]
whitelist = read('pilot_query_whitelist.json')
keys = {(r['role'], r['position'], r['K']) for r in rows}
expected = {(r['role'], r['position'], k) for r in whitelist for k in cfg['candidates']}
assert keys == expected and len(rows) == len(keys) == 768
assert not pilot['passed'] and not pilot['resource_pass']
assert not pilot['is_model_selection'] and not pilot['is_full_experiment']
checks = [(int(k), r) for k, group in pilot['numerical_checks'].items()
          for r in group['reference_checks']]
refs = [(k, r) for k, r in checks if r['method'] == 'reference']
iids = [(k, r) for k, r in checks if r['method'] == 'iid']
failed = [(k, r) for k, r in refs if not r['passed']]
assert len(refs) == len(iids) == 48 and all(r['passed'] for _, r in iids)
assert [k for k, _ in failed] == [1, 2, 4, 16]
assert {(r['role'], r['position']) for _, r in failed} == {('C_T0', 41760)}

def digest(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()

protected = {p: {'expected': value, 'actual': digest(ROOT / p)}
             for p, value in approval['protected_files'].items()}
assert all(r['expected'] == r['actual'] for r in protected.values())
assert all(digest(ROOT / r['checkpoint']) == r['checkpoint_sha256'] for r in training.values())
compute_before_report = sum(r['elapsed_seconds'] for r in ledger['entries'])
peak_gib = max(r.get('peak_process_tree_rss_bytes', 0) for r in ledger['entries']) / 2**30

phases = ['inner_scoring', 'outer_scoring', 'audit']
hours = [pilot['projected_phase_seconds'][p] / 3600 for p in phases]
caps = [cfg['seconds'][p] / 3600 for p in phases]
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
                     'axes.spines.top': False, 'axes.spines.right': False,
                     'axes.titleweight': 'bold', 'figure.facecolor': 'white'})
fig, axes = plt.subplots(1, 2, figsize=(13.5, 5.6), gridspec_kw={'width_ratios': [1.15, 1]})
ax = axes[0]
y = np.arange(3)
ax.barh(y, hours, height=.5, color=['#416991', '#b87928', '#b87928'])
ax.scatter(caps, y, marker='|', color='#202b36', s=650, linewidths=2.4,
           label='Approved stage cap', zorder=3)
for i, (value, cap) in enumerate(zip(hours, caps)):
    ax.text(value + .15, i, f'{value:.2f} h', va='center')
    ax.text(cap, i - .33, f'cap {cap:g} h', ha='center', fontsize=9, color='#202b36')
ax.set(yticks=y, yticklabels=['Inner scoring', 'Outer scoring', 'Independent audit'],
       xlim=(0, 13.5), xlabel='Projected wall-clock hours', title='Resource preflight')
ax.invert_yaxis()
ax.grid(axis='x', alpha=.15)
ax.set_axisbelow(True)
ax.legend(loc='lower right', frameon=False, fontsize=9)
ax = axes[1]
ratios = [abs(r['difference_km']) / r['three_se_km'] for _, r in failed]
ax.barh(np.arange(4), ratios, height=.5, color='#b87928')
ax.axvline(1, color='#202b36', linewidth=1.5, linestyle='--')
for i, ratio in enumerate(ratios):
    ax.text(ratio + .025, i, f'{ratio:.2f}', va='center')
ax.set(yticks=np.arange(4), yticklabels=['K1 pilot', 'K2 fixture', 'K4 fixture', 'K16 fixture'],
       xlim=(0, 1.65), xlabel='Absolute ES difference / allowed 3SE',
       title='Four reference checks above threshold')
ax.invert_yaxis()
ax.text(.99, .03, 'Pass threshold = 1', ha='right', transform=ax.transAxes, fontsize=9)
ax.grid(axis='x', alpha=.15)
ax.set_axisbelow(True)
fig.suptitle('MDN pilot: STOPPED BEFORE FORMAL TRAINING', x=.04, ha='left', fontsize=18, weight='bold')
fig.text(.04, .865, 'Engineering feasibility and numerical checks only; no model selection or predictive ranking.', fontsize=11)
fig.text(.04, .10, 'Left: conservative projections include the required 1.5 safety factor; these are not hours spent.', fontsize=10)
fig.text(.04, .06, 'Right: all four failures share one query. K2 / K4 / K16 are synthetic probes, not trained MDNs.', fontsize=10)
fig.subplots_adjust(left=.14, right=.98, bottom=.23, top=.73, wspace=.55)
fig.savefig(OUT / 'pilot_diagnostics.png', dpi=180)
fig.savefig(OUT / 'pilot_diagnostics.svg')
plt.close(fig)

failed_table = '\n'.join(f"| K{k}{' 试跑网络' if k == 1 else ' 合成测试分布'} | {r['difference_km']:.6f} | {r['three_se_km']:.6f} |"
                         for k, r in failed)
budget_table = '\n'.join(f"| {name} | {h:.3f} 小时 | {cap:g} 小时 | {'通过' if h <= cap else '未通过'} |"
                         for name, h, cap in zip(['内层评分', '外层评分', '独立复核'], hours, caps))
report = f'''# Step 5 E3 MDN：资源试跑与停止报告

**状态：STOPPED_PREFLIGHT。正式实验未启动，尚未选择 K，也没有可与 ExactPoint、EndpointCI、LocalGaussian 比较的正式 ES、90% 实际命中率和面积。**

本报告只使用已经保存的试跑结果，不重新训练、不重新积分。研究合同、训练配对、模型定义和历史结果均保持不变。本次停止不代表 MDN 预测效果不好。

![MDN 试跑诊断图]({OUT / 'pilot_diagnostics.png'})

## 已完成的范围

- 完成 MDN、训练/早停与恢复、积分/区域计算及资源守卫的试跑实现；38 项自动检查通过，并完成独立规格、代码和已存结果复核。
- K=1 和 K=32 各训练 10 个工程试跑 epoch，均使用完整 C_T0 训练池：170,978 配对、234 个 drifter ID。训练耗时分别为 {training['1']['elapsed_seconds']:.2f} 秒和 {training['32']['elapsed_seconds']:.2f} 秒，不包含启动等开销。它们不是最终收敛模型。
- 固定 128 个内层查询 × 六组积分测试分布，共 768 条数值记录；K=2/4/8/16 是合成压力测试分布，不能当作训练好的候选 MDN。
- 报告生成前，必要检查与试跑累计 {compute_before_report:.3f} 秒（{compute_before_report/60:.2f} 分钟）；峰值内存 {peak_gib:.3f} GiB。报告生成的少量耗时另记在资源台账中。
- 没有启动正式内层/外层训练、K 选择或新的外层目标评分；没有访问 final-test。正式全量训练与汇报流程尚未完成。

## 为什么必须停止

| 阶段 | 保守预计耗时 | 已批准上限 | 结果 |
|---|---:|---:|---|
{budget_table}

以上使用实测每个操作的 p95 耗时、最多两个评分进程、合同规定的工作量和 1.5 倍安全余量。它们是预计值，不是已经消耗的时间。总预算尚未耗尽，但合同禁止阶段预算自动互借。评分与复核三阶段预计合计 {sum(hours):.2f} 小时，**不含尚未实测的正式完整训练与报告耗时，不能当作整个实验的可靠完工预测**。

预计完整存储 {pilot['projected_storage_bytes']/2**30:.3f} GiB，存储和内存预检通过。停止原因是外层评分/独立复核阶段预计超限，同时有数值一致性检查未通过。

## 数值检查结果

- 48 项成分分解参考积分检查：44 项通过、4 项未通过，全部发生在同一个查询 C_T0 / position 41760。
- 48 项独立 IID 检查全部通过，但其误差范围较宽，不能排除上述小幅差异。
- 六组分布的区域精度检查通过；768 条记录均可重建区域，区域重建的命中判定无分歧。**这指计算的一致性，不是预测命中率为 100%。**
- 最大加权面积相对变化为 {max(r['area_relative_change'] for r in pilot['numerical_checks'].values())*100:.4f}%，低于 0.5% 门槛；独立对照 ES 的全样本精度投影通过，但这仍是试跑投影，不是正式全样本实测。

| 未通过的分布检查 | 主计算减参考值 ES（km） | 允许差异：合并 3SE（km） |
|---|---:|---:|
{failed_table}

主计算使用总计 65,536 节点，成分参考积分使用每成分/成分对总计 8,192 节点，均分为 8 次随机化重复。相同位置的失败共享抽样流且相关；独立的两套 65,536 节点计算在该位置相符。**粗参考积分的随机波动是可能原因，尚未证明。现有证据既不能确认实现有误，也不足以取消未通过的检查。** 更高的预登记精度层级没有运行，因为当前最低层级的资源预检已经未通过。

## 已知耗时来源与下一步建议

在本轮数值试跑中，每查询/每分布的 p95 耗时约为：ES 主计算 0.043–0.045 秒、90% 区域计算 0.112–0.115 秒、独立 ES 重建 0.043–0.044 秒；成分参考积分从 K1 的 0.047 秒升至 K32 的 0.273 秒。区域计算的耗时高于主 ES。坐标转换与多套抽样几何计算可能值得复用，但尚无函数级分析，不能声称已确认加速倍数。

建议先针对这个固定位置厘清参考积分差异，再检查区域和评分的重复计算；保留全部样本、六个 K、权重和精度要求。通过新的有界数值/耗时核验后，再判断是否需要只调整资源预算。**本轮未实施这些优化，也未扩大预算。**

## 独立复核与保留证据

独立复核从已存记录重新核对 768 条唯一记录、48+48 项交叉检查、四个失败位置、训练检查点及全部耗时投影；投影算术与原记录一致。{len(protected)} 个受保护文件的 SHA-256 均与批准时一致，两个试跑权重文件的校验值匹配。

- [原始试跑结果]({PROV / 'pilot_result.json'})
- [独立复核与停止状态]({PROV / 'pilot_independent_review.json'})
- [实时资源台账]({PROV / 'resource_ledger.json'})
- [批准的工程合同]({ROOT / 'docs/conditional_mdn_s5_e3_contract.md'})

原始试跑结果中的 `allowed_next_stage` 是“通过时可进入”的通用标签，不构成继续授权；`passed=false`，本轮实际下一阶段为 `none`。有效状态以独立停止记录为准。
'''
(OUT / 'REPORT.md').write_text(report)
(PROV / 'STOP_REPORT.md').write_text(report)
review = {
    'status': 'STOPPED_PREFLIGHT', 'effective_next_stage': None,
    'formal_training_started': False, 'selected_K': None,
    'formal_predictive_comparison_available': False,
    'verification_scope': 'saved_outputs_only_no_training_or_integration_rerun',
    'independent_reviewer': '/root/mdn_spec_review',
    'root_rechecked_unique_rows': len(rows), 'reference_checks': len(refs),
    'reference_passed': len(refs)-len(failed), 'iid_passed': len(iids),
    'failed_checks': [{'K': k, **r} for k, r in failed],
    'protected_hashes': protected,
    'checkpoint_hashes_match': True,
    'projected_phase_hours': dict(zip(phases, hours)),
    'compute_seconds_before_report': compute_before_report,
    'report': str(OUT / 'REPORT.md'),
    'limitations': [
        'No selected K or formal MDN predictive performance exists.',
        'Coarse-reference fluctuation is plausible but unproven.',
        'IID checks cannot resolve the small reference discrepancies.',
        'No reliable complete training-time estimate yet.',
        'Raw pilot allowed_next_stage is conditional on passed=true; effective next stage is none.'
    ]
}
(PROV / 'pilot_independent_review.json').write_text(json.dumps(review, indent=2))
print(json.dumps({'report': str(OUT / 'REPORT.md'), 'protected_hashes_match': len(protected),
                  'rows_verified': len(rows), 'status': review['status']}))
