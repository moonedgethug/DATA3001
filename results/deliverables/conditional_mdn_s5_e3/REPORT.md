# Step 5 E3 · 条件 MDN 完整开发验证

事先由内层选择 **MDN1（K*=1）**；未达到预先规定的整体保留标准。本轮选择不支持增加成分；K*=1 不证明真实落点分布单峰。

最终主模型由内层结果冻结。外层较优的未选 K 只说明复杂度敏感性，不能在本轮改选。九种独特模型完整保留；K*=1 时不额外计入一个 MDN-K* 模型。

## 数据与模型

七天落点分布；全部 265,393 条训练配对 / 338 ID（2001–2019），全部 33,971 条外层开发查询 / 45 ID（2020–2022）。内层两个时间窗口共 86,373 条查询 / 104 个不同 ID；先在 ID/窗口内平均、再在同 ID 的窗口间平均，最后 ID 等权。训练为配对等权，评估为 drifter 等权。外层曾被多次检查，**不是独立最终测试**；517 个 final-test ID 保持锁定。

MDN1/2/4/8/16/32 使用相同 2→64 tanh→64 tanh→6K 网络，全训练区域共享参数；每角色每 K 三种子早停，然后用选定种子从头在完整角色训练池重拟合选定 epoch。经纬度输入，输出自身七天位移混合分布；CPU float64，标准化位移协方差下限 0.001。ExactPoint/EndpointCI/LocalGaussian 仍使用原有 100 km / 最多 8,000 donor 定义。

## 九模型完整结果

| model | energy_km | h90 | area90_km2 | land_mass | outside_D_mass |
| --- | --- | --- | --- | --- | --- |
| ExactPoint | 134.223563 | 0.913921 | 215,666.889355 | 0.000000 | 0.000000 |
| EndpointCI | 134.223517 | 0.913939 | 215,732.078194 | 0.000001 | 0.000000 |
| LocalGaussian | 134.777135 | 0.915438 | 216,097.009870 | 0.005988 | 0.002969 |
| MDN1 | 128.701716 | 0.876301 | 175,929.086543 | 0.003326 | 0.000623 |
| MDN2 | 128.812285 | 0.885144 | 180,504.571568 | 0.002294 | 0.000301 |
| MDN4 | 128.885061 | 0.883765 | 180,606.591779 | 0.001154 | 0.000075 |
| MDN8 | 130.330538 | 0.895375 | 183,201.870444 | 0.001070 | 0.000051 |
| MDN16 | 128.783605 | 0.896214 | 181,776.207418 | 0.001026 | 0.000065 |
| MDN32 | 130.115281 | 0.899540 | 192,974.262553 | 0.003214 | 0.000130 |

ES 单位 km，越低越好；H90 与面积必须一起看。90% 区域是完整预测分布在固定 LAEA 下的**单个公共分位椭圆**；不是成分椭圆并集或 HDR。陆地、域外和远尾概率完整保留，不能解释为真实搁浅或 observed-E。

## 主模型配对比较与区间

| baseline | es_delta | es_lower | es_upper | hit_delta | hit_lower | hit_upper | area_ratio | area_lower | area_upper | eligible |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| LocalGaussian | -6.075419 | -13.577949 | 1.198739 | -0.039137 | -0.066632 | -0.014266 | 0.814121 | 0.781440 | 0.842688 | False |
| ExactPoint | -5.521847 | -12.174476 | 0.943308 | -0.037620 | -0.066463 | -0.010233 | 0.815745 | 0.784491 | 0.842326 | False |
| EndpointCI | -5.521802 | -12.174418 | 0.943349 | -0.037638 | -0.066478 | -0.010233 | 0.815498 | 0.784258 | 0.842066 | False |

95% 区间为 10,000 次整条 ID 配对 bootstrap，条件于已拟合预测，不含重新训练的不确定性。eligible 是已冻结的综合验收结果，不能只由 ES 点估计推断成功。验收细节见 [acceptance.json](acceptance.json)。

数值误差与独立重复差异：

| baseline | es_three_se | es_audit_three_se | es_independent_delta_drift | hit_numerical_disagreement | area_numerical_relative_drift |
| --- | --- | --- | --- | --- | --- |
| LocalGaussian | 0.000662 | 0.000673 | 0.000165 | 0.000011 | 0.000001 |
| ExactPoint | 0.003012 | 0.003015 | 0.000649 | 0.000000 | 0.000000 |
| EndpointCI | 0.003012 | 0.003015 | 0.000648 | 0.000011 | 0.000004 |

ES 共 65,536 节点、8 次 scramble；区域共 65,536 节点。完整审计已经通过；统计差异不等于数值误差，二者分别报告。

## 内层选择与训练

在符合预定晋级条件的候选中，内层合并 ES 最优 K=1；1SE 暂选 K=1；按预定质量规则确定 K*=1。这不是未加约束的 ES 排名：合并 ES 较低的候选，仍可能因为某个时间窗口退化而被排除。各 K 的窗口得分与淘汰原因见 [selection.json](selection.json)。无外层调参。各角色完整训练诊断：

| role | K | parameters | selected_seed | selected_epoch | seed_cap_count | mixture_entropy_mean_nats | mixture_entropy_min_nats | mixture_entropy_max_nats | effective_components_mean | near_floor_probability_mass | gradient_clip_rate | fit_epoch_seconds |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| C_T0 | 1 | 4742 | 20261122 | 59 | 0 | 0.000000 | -0.000000 | -0.000000 | 1.000000 | 0.000000 | 0.000000 | 79.917614 |
| C_T0 | 2 | 5132 | 20261122 | 20 | 0 | 0.280602 | 0.036444 | 0.693147 | 1.349127 | 0.000000 | 0.000000 | 58.782140 |
| C_T0 | 4 | 5912 | 20261121 | 21 | 0 | 0.742388 | 0.047383 | 1.102573 | 2.144246 | 0.000000 | 0.000000 | 69.851114 |
| C_T0 | 8 | 7472 | 20261122 | 14 | 0 | 1.136603 | 0.117056 | 1.789965 | 3.263553 | 0.000000 | 0.000000 | 78.733552 |
| C_T0 | 16 | 10592 | 20261123 | 13 | 0 | 1.938117 | 0.185662 | 2.329968 | 7.359888 | 0.000000 | 0.000000 | 99.206741 |
| C_T0 | 32 | 16832 | 20261121 | 20 | 0 | 2.069159 | 0.131340 | 2.881062 | 8.646233 | 0.000000 | 0.000000 | 184.665798 |
| C_T1 | 1 | 4742 | 20261123 | 83 | 0 | 0.000000 | -0.000000 | -0.000000 | 1.000000 | 0.000000 | 0.000000 | 173.769030 |
| C_T1 | 2 | 5132 | 20261123 | 17 | 0 | 0.296239 | 0.017831 | 0.693147 | 1.377383 | 0.000000 | 0.000000 | 72.811321 |
| C_T1 | 4 | 5912 | 20261121 | 28 | 0 | 0.672821 | 0.053718 | 1.318188 | 2.067025 | 0.000000 | 0.000000 | 107.882353 |
| C_T1 | 8 | 7472 | 20261122 | 15 | 0 | 1.061546 | 0.050629 | 1.754004 | 3.131521 | 0.000000 | 0.000000 | 101.105278 |
| C_T1 | 16 | 10592 | 20261123 | 12 | 0 | 1.510216 | 0.137141 | 2.282916 | 4.990412 | 0.000000 | 0.000000 | 114.947974 |
| C_T1 | 32 | 16832 | 20261121 | 9 | 0 | 2.014052 | 0.099855 | 3.063430 | 9.394758 | 0.000000 | 0.000000 | 184.649705 |
| C_outer | 1 | 4742 | 20261121 | 50 | 0 | 0.000000 | -0.000000 | -0.000000 | 1.000000 | 0.000000 | 0.000000 | 171.013813 |
| C_outer | 2 | 5132 | 20261122 | 79 | 0 | 0.488250 | 0.027969 | 0.693147 | 1.665681 | 0.000000 | 0.000000 | 225.880202 |
| C_outer | 4 | 5912 | 20261122 | 55 | 0 | 0.964005 | 0.050564 | 1.319222 | 2.668978 | 0.000000 | 0.000000 | 190.171443 |
| C_outer | 8 | 7472 | 20261122 | 10 | 0 | 1.243896 | 0.064754 | 1.677576 | 3.665304 | 0.000000 | 0.000000 | 107.587344 |
| C_outer | 16 | 10592 | 20261122 | 13 | 0 | 1.709015 | 0.198591 | 2.277057 | 5.832863 | 0.000000 | 0.000000 | 160.580836 |
| C_outer | 32 | 16832 | 20261123 | 10 | 0 | 2.046416 | 0.303905 | 3.121949 | 8.392786 | 0.000000 | 0.000000 | 243.137505 |

mixture_entropy_*_nats 报告成分概率熵的查询均值、最小值和最大值；effective_components_mean 是 exp(entropy) 的查询均值，不解释成真实洋流条数。near_floor_probability_mass 是最小标准化协方差特征值 ≤1.01×0.001 的成分概率质量（查询等权诊断）。触及 epoch 上限的种子不能声称已经收敛；三种子曲线说明优化敏感性，不提供全量 ES 的种子不确定性。

## 外推与资源

以下支撑诊断覆盖所有外层查询，不据此删样本、改权重或回退。距离为精确 WGS84，100 km 内 ID 计数不采用 8,000 配对截断。

```json
{
  "query_equal_means": {
    "nearest_training_start_km": 0.7221074594109116,
    "distinct_training_ids_within_100km": 139.5754319861058,
    "outside_training_lonlat_convex_hull": 0.00029436872626652146
  },
  "drifter_equal_means": {
    "nearest_training_start_km": 0.7183959930947434,
    "distinct_training_ids_within_100km": 158.79582392848383,
    "outside_training_lonlat_convex_hull": 0.00039791649469994524
  },
  "nearest_distance_max_km": 11.762329363313103,
  "local_id_count_min": 19,
  "convex_hull_definition": "Planar longitude/latitude convex hull of all outer training starts",
  "exclusion_or_fallback": false
}
```

```json
{
  "record_available": true,
  "completed_supervised_task_wall_seconds": 51572.76448166708,
  "prior_supervised_task_wall_seconds": 515.8821546636755,
  "active_snapshot_seconds": 0,
  "peak_process_tree_rss_gib": 2.1030731201171875,
  "peak_run_storage_gib": 1.5853725150227547,
  "active_stage": null,
  "resource_limit_seconds": null,
  "note": "Recorded supervised-task wall time only. Unsupervised checks and calendar gaps are excluded; these sums are not total CPU time or full calendar duration. Prior time includes pilot/optimization. The time ceiling was explicitly waived. Active entry is provisional.",
  "report_generation_seconds": 334.4498634999618
}
```

## 12 个预声明地图

按冻结源键排序取 floor(j×(33971−1)/11)，j=0,…,11；没有按命中或改善筛选。九模型、十二案例使用相同视域、0.5° 展示格和色标。白点为真实起点，星号为记录的七天终点，红线来自已保存的评分用 90% 椭圆。云图用独立固定种子的展示抽样，不重新计算指标，不截断后归一化；有限展示抽样不等于全部连续支持。成分是统计近似，不是识别出的洋流。

![outer_comparison.png](figures/outer_comparison.png)
![paired_effects.png](figures/paired_effects.png)
![per_id_effects.png](figures/per_id_effects.png)
![inner_es_complexity.png](figures/inner_es_complexity.png)
![training_curves_C_T0.png](figures/training_curves_C_T0.png)
![training_curves_C_T1.png](figures/training_curves_C_T1.png)
![training_curves_C_outer.png](figures/training_curves_C_outer.png)
![fixed_case_01.png](figures/fixed_case_01.png)
![fixed_case_02.png](figures/fixed_case_02.png)
![fixed_case_03.png](figures/fixed_case_03.png)
![fixed_case_04.png](figures/fixed_case_04.png)
![fixed_case_05.png](figures/fixed_case_05.png)
![fixed_case_06.png](figures/fixed_case_06.png)
![fixed_case_07.png](figures/fixed_case_07.png)
![fixed_case_08.png](figures/fixed_case_08.png)
![fixed_case_09.png](figures/fixed_case_09.png)
![fixed_case_10.png](figures/fixed_case_10.png)
![fixed_case_11.png](figures/fixed_case_11.png)
![fixed_case_12.png](figures/fixed_case_12.png)

## 与 Brolly 文献的关系

[Brolly (2023), Table 1](https://arxiv.org/html/2303.11480v2) 的全球四天验证平均 log score 为 TM/DTMC −1.74、GTGP −1.30、MDN1 −1.14、MDN32 −1.11（越高越好；原经纬度位移单位）。其 TM 全球比较排除了 7% 零概率验证样本。本项目是区域七天、时间划分、整 ID 评价的 Energy Score（越低越好），因此**不能把两组数值并排排名或声称数值复现**。借鉴的是位置条件混合分布方法。

## 可复用预测接口

保存权重和标准化器可直接接受真实 lon/lat，返回全部 K 权重、east/north 均值位移（km）、完整协方差（km²）和 WGS84 落点样本。接口不读取验证落点；样本不裁剪陆地或域外质量。参见 [inference_usage.md](inference_usage.md)。

## English technical summary

The inner-only procedure selected MDN1. The preregistered overall retention gate did not pass. All six MDN complexities and three unchanged local controls were evaluated on the same 33,971 seven-day outer-development queries from 45 drifters. Training uses pair-equal NLL; evaluation averages within drifter before equal-ID averaging. Each final network is a full-pool refit at its training-only selected seed and epoch. The fixed small network, covariance floor, AdamW regularisation and ID-held-out early stopping are experimental conditions, not assurances against overfitting. The final audit passed; all original boundaries remain in force.

Energy Score uses WGS84 ECEF chord distances in km. The common 90% region is one LAEA quantile ellipse derived solely from each forecast distribution. Land, outside-domain and tail probability remain in every forecast. Bootstrap intervals condition on fitted models. Unselected outer K values are sensitivity evidence only. K=1 selection does not establish physical unimodality; components do not identify current systems. The 12 source-order displays were fixed independently of outcomes. Support diagnostics do not change forecasts or the cohort. No final-test evidence is claimed.

已保留 12 条边界配对和 ID 75447 的一分钟起点差异：这是用户接受保留的来源备注，不是已经消除的来源冲突。七天位置条件 Markov 核不证明位置过程严格 Markov，也不证明任意时长递推准确，不能作为已验证油污风化模型。

运行：`conditional_mdn_s5_e3_20261108T055830_797628Z`。完整表格：[summary.csv](summary.csv)、[per_id.csv](per_id.csv)、[comparisons.csv](comparisons.csv)、[selection.json](selection.json)、[final_audit.json](final_audit.json)、[delivery_manifest.json](delivery_manifest.json)。
