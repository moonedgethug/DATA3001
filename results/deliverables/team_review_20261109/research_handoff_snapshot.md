> Historical snapshot: this document predates MDN completion. See the [completed MDN report](../conditional_mdn_s5_e3/REPORT.md) and [current index](../../../docs/modelling_results.md). Only local link destinations were made portable; original results and prose are retained.

# Where Things End Up — 五阶段研究成果汇报资料

核对日期：2026 年 11 月 9 日。用途：网站、presentation 和报告的内容依据。

按照 Baseline → 正则化 → 空间信息 → model selection → Gaussian / GMM / MDN 组织。下列数字来自已保存的结果表。本次核对模型定义、版本、汇总数值与可用图表，并复算了季节精确位置、Gaussian、GMM 三组报告的 45-ID 汇总。没有重新拟合或生成预测。

## 1. 使用哪一版结果

“最新”需要同时记录模型版本和评估版本。同一个 B2、Fixed 或 LocalEndpoint 后来接受了新的时间验证，其分数对应新的样本和权重。

| 阶段 | 当前应引用的成果 | 汇报用途 |
|---|---|---|
| Baseline | 10 月 24 日完整 pooled B0/B1/B2；10 月 29 日冻结的标准 B2；11 月的时间验证 | 解释三个基准、经验转移矩阵及后续对照 |
| Step 2 | E1–E4 完整结果；S4 E2 的 C/T 时间验证重新评估 Fixed/Adaptive | 说明 B1＋B2 融合、权重研究及覆盖—区域大小的权衡 |
| Step 3 | E1 的 Endpoint/Displacement 对照；E2–E4 的端点借用改进；C/T 时间验证 | 解释借用什么信息，以及后续权重优化结果 |
| Step 4 | E3 四季矩阵与季节调整、E7 精确起点、E8 修正后的误差实验、E9 完整四臂季节比较 | 展示信息选择、位置表示及测量误差的研究结论 |
| Step 5 | 完整 LocalGaussian E1；完整 GMM E2；MDN 正式流程进行中 | 比较经验分布与参数分布，保留 MDN 结果位置 |

现有数值都是开发验证结果。最终测试集没有进入这些结果。

## 2. Baseline — B0、B1、B2

- **B0 / persistence**：全部概率留在起点 cell，是无移动对照。
- **B1 / pooled endpoint distribution**：汇总 R 中所有合格起点的历史落点，每个起点使用同一分布。
- **B2 / empirical transition matrix**：分别统计每个起点 cell 到各落点 cell 的频率。

$$
P_{ij}^{(h)}=\frac{N_{ij}^{(h)}}{\sum_j N_{ij}^{(h)}},\qquad h\in\{7,30\}.
$$

B2 的每一行回答“已经位于 cell i 的 drifter，在 h 天后落在哪里”。7 天与 30 天分别估计；当前矩阵不是用日矩阵连乘得到。B0 是确定性基准，B1 是汇总经验分布，B2 才是按起点条件化的经验转移矩阵。

### 三个基准的最新完整 pooled 同场比较

| 天数 | 模型 | Brier ↓ | 实际 H90 | K90（格数） |
|---:|---|---:|---:|---:|
| 7 | B0 | 1.711584 | 14.421% | 1.00 |
| 7 | B1 | 0.979067 | 89.396% | 49.36 |
| 7 | B2 | 0.928878 | 87.485% | 18.35 |
| 30 | B0 | 1.929715 | 3.514% | 1.00 |
| 30 | B1 | 0.991638 | 85.677% | 138.94 |
| 30 | B2 | 0.994400 | 67.196% | 64.86 |

这组历史比较使用 7 天 308,312 配对 / 387 IDs，30 天 287,004 配对 / 358 IDs，按配对等权。B0/B1/B2 均为完整分布，该表的 Brier 与历史报告的 failure-penalized score 相等。

[原始报告](<../../runs/baseline_neighbour_cv_20261024T065917_879042Z/REPORT.md>) · [结果表](<../../runs/baseline_neighbour_cv_20261024T065917_879042Z/outer_summary.csv>)

10 月 29 日重新冻结的标准 B2 使用严格 stopped-target 资格集合：7 天 303,288 配对 / 385 IDs，Brier **0.929001**；30 天 268,998 配对 / 337 IDs，Brier **0.994751**。已读取的后续正式结果未包含 B0、独立 B1 在当前时间验证上的完整重新评分。因此，展示三基准时采用上面的同场历史表，展示最新模型改进时采用该实验内重新评估的 B2。

[原始报告](<../../runs/empirical_b2_20261029T121555_976173Z/REPORT.md>) · [结果表](<../../runs/empirical_b2_20261029T121555_976173Z/summary.csv>)

## 3. Step 2 — B1＋B2 正则化

$$
\widetilde P_i=(1-\lambda_i)P_i+\lambda_i q,
$$

其中 P_i 是起点 cell 的 B2 分布，q 是 B1 的全 R 落点分布。融合通过更广泛的历史信息补充本地样本未覆盖的去向。

已完成的四轮研究都保留：E1 比较 Fixed 与 Adaptive；E2 比较 B1 的概率分配和支撑权重；E3 比较 EqualID；E4 比较 PartialID。自 E3 起采用新的评估权重，E4 沿用这一口径，汇报时需单独标明。

### 最后一次 Step 2 专项比较（E4）

| 天数 | 模型 | Brier ↓ | 实际 H90 | K90（格数） |
|---:|---|---:|---:|---:|
| 7 | B2 | 0.981297 | 74.838% | 17.56 |
| 7 | EqualID | 0.957266 | 81.369% | 20.91 |
| 7 | Fixed | 0.962457 | 89.956% | 42.71 |
| 7 | PartialID | 0.961860 | 80.174% | 19.65 |
| 30 | B2 | 1.017814 | 50.276% | 56.57 |
| 30 | EqualID | 1.008698 | 49.678% | 59.93 |
| 30 | Fixed | 0.994931 | 77.586% | 133.86 |
| 30 | PartialID | 1.008159 | 52.066% | 61.50 |

原始配对用于 B2/Fixed 拟合；评估先在 ID/起点内平均，再对 ID 和起点等权。PartialID 在拟合时以每条 drifter 在该起点的配对数平方根调节总贡献。

**结论**：Fixed 明显提高落点覆盖，同时扩大 90% 区域；EqualID / PartialID 提供了不同的评分与区域权衡。现有结果没有使这些方法在所有目标上同时占优。

[原始报告](<../../runs/partial_weighting_e4_20261030T082826_141410Z/REPORT.md>) · [结果表](<../../runs/partial_weighting_e4_20261030T082826_141410Z/summary.csv>)

### 后续时间验证中的最新 Fixed / Adaptive 结果

下面采用 S4 E2 的 C 块、T 策略。训练为 2001–2019，开发验证为 2020–2022，模型和参数只在训练期内选择。它适合与下文同一表中的邻格模型比较。

| 天数 | 模型 | Brier ↓ | 实际 H90 | K90（格数） |
|---:|---|---:|---:|---:|
| 7 | Adaptive | 0.970094 | 88.843% | 36.14 |
| 7 | B2 | 0.995653 | 75.015% | 18.17 |
| 7 | Fixed | 0.971059 | 90.211% | 44.86 |
| 7 | LocalEndpoint | 0.963748 | 89.856% | 27.61 |
| 7 | LocalEndpointAdaptive | 0.963748 | 89.856% | 27.61 |
| 30 | Adaptive | 0.996730 | 77.433% | 133.54 |
| 30 | B2 | 1.010730 | 49.422% | 61.03 |
| 30 | Fixed | 0.996014 | 78.121% | 135.37 |
| 30 | LocalEndpoint | 0.995798 | 74.521% | 105.54 |
| 30 | LocalEndpointAdaptive | 0.995838 | 74.795% | 106.00 |

[原始报告](<../../runs/temporal_validation_s4_e2_primary_20261103T004920_642021Z/REPORT.md>) · [结果表](<../../runs/temporal_validation_s4_e2_primary_20261103T004920_642021Z/summary.csv>)

## 4. Step 3 — 借用邻格终点与运动信息

**LocalEndpoint** 保留八个邻格中 drifter 的实际终点，并与本地 B2 融合。**LocalDisplacement** 平移邻格的完整轨迹到目标 cell，检查路径及边界，无法转移的权重返回 B2。两者使用相同的邻格来源，可以比较“借终点”与“借运动方式”。

### 完整 Endpoint / Displacement 对照

| 天数 | 模型 | Brier ↓ | 实际 H90 | K90（格数） |
|---:|---|---:|---:|---:|
| 7 | Adaptive | 0.966486 | 88.572% | 37.55 |
| 7 | B2 | 0.981297 | 74.838% | 17.56 |
| 7 | Fixed | 0.962457 | 89.956% | 42.71 |
| 7 | LocalDisplacement | 0.975131 | 82.202% | 23.13 |
| 7 | LocalEndpoint | 0.958288 | 88.191% | 27.36 |
| 30 | Adaptive | 0.995303 | 77.737% | 130.93 |
| 30 | B2 | 1.017814 | 50.276% | 56.57 |
| 30 | Fixed | 0.994931 | 77.586% | 133.86 |
| 30 | LocalDisplacement | 1.007012 | 69.961% | 96.17 |
| 30 | LocalEndpoint | 0.993751 | 76.283% | 104.68 |

**结论**：这轮中 Endpoint 的 Brier 和命中率优于 Displacement。相对全 R 的 Fixed 融合，Endpoint 用更小区域获得较低 Brier，同时实际命中率略低。展示时同时呈现这三个量。

[原始报告](<../../runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/REPORT.md>) · [结果表](<../../runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/summary.csv>)

后续 E2 加入自适应邻格权重，E3 调整邻格信息质量，E4 联合选择权重并设置覆盖与区域约束。最后一轮 **E4 的受约束方案在全部 10 个外层选择中返回 LocalEndpointAdaptive**，没有产生满足全部要求的新模型。最新时间验证分数见上一节 C/T 表。

[原始报告](<../../runs/local_endpoint_joint_s3_e4_20261031T021237_761696Z/REPORT.md>) · [结果表](<../../runs/local_endpoint_joint_s3_e4_20261031T021237_761696Z/summary.csv>)

另有“以真实起点转移整条运动路径”的 E5/O1 工程研究，完成了部分加速核对，但没有完整 CV 预测结果。它与上面已完成的 cell-centre LocalDisplacement 是不同实验，汇报目录会分别标记。来源：[E5/O1 状态](<../../../docs/actual_origin_displacement_s3_e5_o1_results.md>)。

## 5. Step 4 — 季节、精确位置与位置误差

### 5.1 四季矩阵与季节调整

最新 cell 模型季节比较采用 2001–2019 训练、2020–2022 开发验证。Annual 汇总全年，HardSeason 按出发季节使用四季矩阵，Adjusted 采用训练期选出的季节调整强度。

| 天数 | 模型 | Brier ↓ | 实际 H90 | K90（格数） |
|---:|---|---:|---:|---:|
| 7 | Adjusted | 0.995189 | 75.808% | 18.07 |
| 7 | Annual | 0.995653 | 75.015% | 18.17 |
| 7 | HardSeason | 1.025687 | 61.413% | 14.19 |
| 30 | Adjusted | 1.010764 | 47.781% | 60.34 |
| 30 | Annual | 1.010730 | 49.422% | 61.03 |
| 30 | HardSeason | 1.057511 | 25.086% | 29.41 |

Adjusted 的 7 / 30 天强度为 0.098574 / 0.114911。7 天 ΔBrier 为 −0.0004646，条件 95% 区间 [−0.0012836, +0.0003378]；30 天为 +0.0000338，区间 [−0.0004374, +0.0004845]。两者均未通过预先规定的季节收益检验。HardSeason 的较小区域伴随明显较低命中率。

[原始报告](<../../runs/seasonal_information_s4_e3_primary_20261104T142729_626118Z/REPORT.md>) · [结果表](<../../runs/seasonal_information_s4_e3_primary_20261104T142729_626118Z/summary.csv>)

### 5.2 lon / lat — 精确起点近邻模型

给定真实起点，按 WGS84 距离寻找 100 km 内的历史起点，训练期从 500 / 2,000 / 8,000 选择近邻数，最终选中 8,000。保留这些历史记录的实际终点。

以下为原 1° 输出网格下的同场七天比较：

| 天数 | 模型 | Brier ↓ | 实际 H90 | 面积（km²） |
|---:|---|---:|---:|---:|
| 7 | Annual | 0.995653 | 75.015% | 184,906.98 |
| 7 | Exact | 0.953154 | 85.751% | 207,827.57 |

Brier 降低约 **4.27%**，命中率增加 **10.737 个百分点**，海面区域面积增加约 **12.40%**。这是精确起点驱动的近邻选择方法的结果，包含位置表示和历史记录选择方式两项变化。0.5° 辅助比较也保存在结果索引中；两种分辨率各自比较对应的模型。

[原始报告](<../../runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/REPORT.md>) · [结果表](<../../runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/summary.csv>)

### 5.3 err_lon / err_lat — 历史终点测量误差

EndpointCI 在历史终点周围加入经核实的位置误差分布，误差不可用时保留原始点及其权重。这里使用的是历史**终点**的位置误差，不是把四个数值一起交给回归模型，也没有使用验证终点的误差。

以下采用 E8 已修正的 90% 区域计算结果：

| 天数 | 模型 | ES（km）↓ | 实际 H90 | 面积（km²） |
|---:|---|---:|---:|---:|
| 7 | B2Point | 144.003238 | 88.425% | 212,639.99 |
| 7 | EndpointCI | 134.219187 | 91.395% | 215,706.11 |
| 7 | ExactPoint | 134.219212 | 91.392% | 215,666.89 |
| 7 | MatchedSpread | 134.219151 | 91.395% | 215,705.10 |

EndpointCI 相对 ExactPoint 的 ES 差约 **−0.024 米**，条件 95% 区间 **[−0.096, +0.043] 米**，该差异未超出数值采样不确定性。当前误差处理没有带来有实用幅度的预测提升。此处评估已改为 drifter 等权、连续空间 ES 和统一 90% 椭圆，面积为整个椭圆面积。

[原始报告](<../position_error_s4_e8/REPORT.md>) · [结果表](<../../runs/position_error_s4_e8_20261106T095423_445879Z/numerical_revision_v1/summary.csv>)

### 5.4 最新完整结果 — 精确位置 × 季节 × 终点误差

此正式四臂实验已完成，取代早期“试跑停止”作为本研究线的当前结果。季节按七天区间内占时最长的 UTC 季节定义；先选同季节历史记录，再按相同 100 km / 8,000 规则选近邻。

| 天数 | 模型 | ES（km）↓ | 实际 H90 | 面积（km²） |
|---:|---|---:|---:|---:|
| 7 | AnnualEndpointCI | 134.225740 | 91.397% | 215,706.73 |
| 7 | AnnualExactPoint | 134.225735 | 91.392% | 215,666.89 |
| 7 | SeasonalEndpointCI | 147.890977 | 91.749% | 240,482.18 |
| 7 | SeasonalExactPoint | 147.891025 | 91.753% | 240,468.13 |

SeasonalEndpointCI 相对 AnnualEndpointCI，ES 增加 **13.665237 km（10.181%）**，条件 95% 区间 **[6.574529, 21.259693] km**；命中率增加约 **0.352 个百分点**，面积增加约 **11.486%**。季节筛选后，平均历史 ID 支撑约从 114.4 降至 48.1，最远被选起点的平均距离约从 60.0 km 升至 97.9 km。这些诊断可用于解释样本代价，不能单独分解其因果贡献。

[原始报告](<../../runs/e9_formal_20261106T140607_806462Z/REPORT.md>) · [结果表](<../../runs/e9_formal_20261106T140607_806462Z/summary.csv>)

### 5.5 model selection 的补充结果

初始方向实验也已完成，值得在网站的展开部分保留：七天 Brier 从 **0.995653** 降至 **0.992948**，命中率增加 **1.463 个百分点**，K90 减少 **0.110 格**，通过该轮预先规定的 Brier 检验。因此整体结论应是“不同信息的收益取决于引入方式和样本支撑”。方向实验来源：[原始报告](<../../runs/departure_direction_s4_e4_primary_20261104T153104_398790Z/REPORT.md>) · [结果表](<../../runs/departure_direction_s4_e4_primary_20261104T153104_398790Z/summary.csv>)。

本次未定位到 speed-only 的完整正式结果，工作区保留的是计划文件；不作为完成的模型结果展示。

## 6. Step 5 — Gaussian、GMM、MDN

### 6.1 LocalGaussian

使用同一批历史近邻终点，在查询点附近的公里坐标中估计均值和完整协方差，形成单高斯转移分布。均值与协方差通过解析估计得到。

| 天数 | 模型 | ES（km）↓ | 实际 H90 | 面积（km²） |
|---:|---|---:|---:|---:|
| 7 | EndpointCI | 134.223188 | 91.397% | 215,723.90 |
| 7 | ExactPoint | 134.223226 | 91.392% | 215,666.89 |
| 7 | LocalGaussian | 134.776526 | 91.545% | 216,104.23 |

完整单高斯实验已经结束，拟合、开发验证和独立复核均有保存记录。相对 ExactPoint，ES 差约 +0.5533 km，区间跨零，未达到该轮全部改进要求。

[原始报告](<../../runs/conditional_gaussian_s5_e1_full_20261107T061818Z/technical_report.md>) · [结果表](<../../runs/conditional_gaussian_s5_e1_full_20261107T061818Z/summary.csv>)

### 6.2 LocalGMM — 当前最新完整高斯比较

在同一近邻规则下拟合 K=1、2、3 个高斯成分。两个训练期窗口完成参数选择，最终选中 **K=1**，随后完成全部 33,971 个外层起点、45 条 drifter 的开发验证。

| 天数 | 模型 | ES（km）↓ | 实际 H90 | 面积（km²） |
|---:|---|---:|---:|---:|
| 7 | EndpointCI | 134.223517 | 91.394% | 215,732.08 |
| 7 | ExactPoint | 134.223563 | 91.392% | 215,666.89 |
| 7 | LocalGMM | 134.777135 | 91.544% | 216,097.01 |
| 7 | LocalGaussian | 134.777135 | 91.544% | 216,097.01 |

K=2 的内部平均 ES 比 K=1 约低 0.45%，但两个窗口命中率分别下降约 0.081、0.306 个百分点；K=3 的回退率为 12.86%、14.61%，超过门槛。因此最终保留 K=1，其外层预测与 LocalGaussian 相同。K=2、3 的结果属于内部选择阶段，没有独立外层效果表。

最终 GMM 相对 ExactPoint 的 ES 差 **+0.553572 km**，条件 95% 区间 **[−1.365444, +2.588134] km**。本轮完成了研究，但没有支持替换经验对照的预测改善。选择 K=1 也不代表真实洋流落点只有一个峰。

[原始报告](<../../runs/local_gmm_s5_e2_vector_20261107T133426Z/technical_report.md>) · [结果表](<../../runs/local_gmm_s5_e2_vector_20261107T133426Z/summary.csv>)

### 6.3 MDN — 正式实验进行中

当前方案从起点经纬度学习条件混合分布，候选 K=1、2、4、8、16、32，与 ExactPoint、EndpointCI、LocalGaussian 比较。以负对数似然训练，在训练期选择 K，再作外层评估。

2026 年 11 月 9 日读取「Markov Transition Model」时，最新记录为内层 ES 评分接近 90%，仍待选 K、外层验证与独立复核。该百分比只是本次读取时的进度快照。汇报中标记为 **In progress**，不填入最终评分或模型胜出结论。来源：[MDN contract](<../../../docs/conditional_mdn_s5_e3_contract.md>)。

## 7. 汇总及作图时保留的口径

| 比较组 | 评价单位与指标 | 可直接比较的内容 |
|---|---|---|
| 早期 B0/B1/B2、S1、S2 E1/E2 | 原始配对等权；各自资格样本；Brier | 各次实验自己的模型与对照 |
| S2 E3/E4、S3 | ID/起点内平均，ID 等权，起点等权；Brier | 相同资格样本和相同聚合的配套结果 |
| S4 E1/E2/E3/E4/E7 | 时间留出；ID/起点和起点等权；Brier | 同训练窗口、同验证总体、同分辨率的对照 |
| S4 E8/E9、S5 | 时间留出；直接 drifter 等权；ES、椭圆 H90 与面积 | 每次正式实验共同计算的模型与对照 |

网站图表会把比较组固定下来：选同一组中的模型才形成性能差异。跨阶段展示研究路线时，分别解释问题、方法和发现。E7 的海面 cell-union 面积和 E8 以后的总椭圆面积采用不同定义。

ES 的单位是 km，但它评价整个概率分布，不等同于平均落点距离误差。H90 是实际落点进入名义 90% 区域的比例。K90 是格数，面积是 km²。预测区域越大通常越容易命中，所以命中率与区域大小共同展示。

## 8. 已有可视化入口

- Baseline 历史展示：[B0/B1/B2 与融合](<../baseline_optimized/index.html>)。
- 正则化最后专项比较：[PartialID / EqualID / Fixed](<../partial_weighting_e4/review.html>)。
- 最新时间验证：[三个时间窗口与五类模型](<../temporal_validation_s4_e2/review.html>)。
- 邻格两种信息：[Endpoint / Displacement](<../spatial_borrowing_s3_e1/review.html>)。
- 邻格最后联合选择：[Joint / Constrained](<../local_endpoint_joint_s3_e4/review.html>)。
- 四季矩阵：[HardSeason / Adjusted](<../seasonal_information_s4_e3/review.html>)。
- 精确位置：[B2 / exact position](<../exact_origin_s4_e7/review.html>)。
- 终点误差修订版：[ExactPoint / EndpointCI](<../position_error_s4_e8/review.html>)。
- 季节精确位置正式版：[四臂完整结果](<../seasonal_exact_position_s4_e9_formal/review.html>)。
- 单高斯：[LocalGaussian 完整比较](<../../runs/conditional_gaussian_s5_e1_full_20261107T061818Z/review.html>)。
- GMM 最终报告：[模型选择、结果与案例地图](<../../runs/local_gmm_s5_e2_vector_20261107T133426Z/review/final.html>)。

本次确认这些入口文件存在；新的汇总网站尚未搭建，浏览器交互也没有在本轮重新验收。

## 9. 本资料包

- `reported_metrics.csv`：19 组实验的已报告汇总数值；保留模型、比较组、时间窗口、指标单位和源文件。历史基准组只摘取 B0/B1/B2。
- `evidence_manifest.json`：来源、读取时 SHA256、原始汇总行、封存匹配记录和版本说明。
- `verification.json`：三组连续模型的 ID 汇总复算，共 33 项；已识别封存记录的文件匹配共 32 项。

后续 MDN 完成或其他模型按新数据重跑后，应以新的完整报告更新对应实验记录，保留本快照及历史比较口径。
