# Step 4 E8：err_lon / err_lat 来源与缩放追溯

## 审计范围与结论

- 日期：2026-11-06，Australia/Sydney。
- 类型：原始定义、发布文件和本地转换的只读审计。没有训练、预测或模型实验；没有修改 canonical 数据、模型代码、工程 contract 或研究阶段记录。
- 本地观测范围：冻结 E7 训练资料中的 drifter；数值对照使用冻结训练终点。没有读取外层验证 endpoint error 或锁定 final-test。
- 承接：[首次尺度审计](position_error_s4_e8_data_audit.md)。本报告补充并更新该报告中“尚不能定位上游环节”的判断。

**已确认：我们使用的 error 存在上游版本／发布渠道之间的缩放不一致，不能按当前数值直接解释为物理 CI。主要差异是 100,000 倍，不是本地清洗造成，也不能用正常的方差、标准差、CI 换算解释。**

**高可信解释：部分发布过程对已换算为“度”的 error 又做了一次 `×10⁻⁵`，同时存在缺失值处理异常。尚未找到对应 v2.01 的完整生产转换代码，因此“重复换算的具体代码行”仍是推断，不是已获得的源码事实。**

不能统一乘以 100,000：本轮已经发现保持旧尺度的正值及异常负值。修复必须以逐记录来源核对为依据。

## 1. 原始字段到底是什么

官方 [v1.04 MATLAB README 的本地快照](../provenance/reviews/position_error_s4_e8_source_trace/sources/README_1.04.txt) 明确区分：

- MATLAB 的 `LON_ERR` / `LAT_ERR` 使用 **10⁻⁵ 度**作为编码单位，用于形成 95% CI。
- 原生 NetCDF 的 `err_lon` / `err_lat` 则标为 **度**，名称为对应经纬度的 95% confidence interval。
- 它们描述已估计的位置的不确定性；不是未来七天漂流的空间分布，也不是速度误差。

作者 [Argos 输出代码](https://github.com/selipot/hourly-drifters/blob/714b15e871f23ccabe5be01fdf3227a818ea1160/global_interpolation_wmle_errors_1.01.m#L103-L113) 对 CI 幅度乘 10⁵、取整后写入文本。这种整数形式换成度时应乘一次 10⁻⁵。例如：

`文本编码 1107 → 0.01107°`。

但已经存成 `0.01107°` 的 NetCDF 数值不应再次按这个文本编码换算。这是当前差异的关键线索；这里的 1107 是按源码规则说明编码的例子，并非本轮已经读取到的该观测原始文本行。

作者 [GPS 估计代码](https://github.com/selipot/hourly-drifters/blob/714b15e871f23ccabe5be01fdf3227a818ea1160/LatLonLocalWess.m#L118-L139) 先由观测方差得到估计方差，再开平方、乘 t 分位数，最后输出相对中心位置的经纬度幅度。虽然变量名含 `var`，此处输出已经是 CI 半宽性质的量，不能因为变量名而再次开平方。

[官方发布说明](https://www.aoml.noaa.gov/phod/gdp/hourly_data_release_notes.php) 确认 GPS 提供正式 95% CI，并记载 v1.01–1.02 的 GPS 误差计算问题已在 v1.03 修正。本次定位的是之后发布链中的另一个尺度问题，不能把两者混为一谈。

## 2. 数值证据：同一个观测差了十万倍

以 ID **7647**、**2002-04-03 15:00 UTC** 为例，两份官方文件中的时刻和位置一致：

| 字段 | 原生 v2.00 | ERDDAP 原生 v2.01／本地 canonical | 旧值 ÷ 当前值 |
|---|---:|---:|---:|
| err_lon | 0.0110700000° | 0.0000001107° | 约 100,000 |
| err_lat | 0.0064400001° | 0.0000000644° | 约 100,000 |

纬度幅度因此从约 **714 m** 变成约 **7.1 mm**。这是同一字段的跨发布文件比较，不是两个模型的预测结果。

进一步核对三个训练 ID 的全部冻结训练终点：

| ID | 定位方式（原生文件元数据） | 训练终点数 | 两轴可比正值 | 相差约 100,000 倍 |
|---|---|---:|---:|---:|
| 7647 | Argos | 160 | 320 | 320 |
| 99004 | Argos | 1,064 | 2,128 | 2,128 |
| 300234066710170 | GPS | 380 | 760 | 760 |
| 合计 | | **1,604** | **3,208** | **3,208** |

时间全部对应；坐标在 canonical 的 float32 精度上全部一致。比值约在 99,999.9943–100,000.0056，差异符合浮点表示精度。不能据此声称全球每一条记录都遵循同一规则。

对 NCEI 存档也独立核查：三个 ID 的 60 个训练终点在 archive 1.1、2.2、3.3 中匹配。对应产品分别为 v2.00、v2.01、v2.01.1；2.2、3.3 的 error 与本地相同，1.1 的可比正值大约大十万倍。**NCEI 存档版本号与产品版本号不是同一套编号。**

## 3. 转换链定位

| 环节 | 本轮核查 | 判断 |
|---|---|---|
| 作者估计与旧文本编码 | 方差开平方、CI 系数、文本乘 10⁵ | 输出目标是位置 CI 幅度；旧编码有明确缩放 |
| v1.04c／v2.00 原生文件 | 读取原生 NetCDF；v1.04c 补查 ID 7647，v2.00 下载五个训练 ID | 已以度保存，具有较大的旧尺度；原生字段标为 95% CI |
| v2.01 ERDDAP 原生文件 | 下载文件，不使用 tabledap 重格式化；关闭自动 mask/scale | 文件原始数值已经很小，没有 `scale_factor` / `add_offset` 可解释该差异 |
| NCEI 合并发布文件 | 通过字节范围读取指定训练 ID，按时间匹配 | 同样存在跨版本尺度差异；不能归因于 ERDDAP 在线查询格式 |
| 本地 source_objects → subset | 原始字节抽查；审阅 exporter 的逐字段复制与 hash 校验 | 未发现额外误差缩放 |
| subset → canonical → E7 key | 原字段保留，另加有效性标记；前轮已核对 338 个文件 hash | 清洗没有平方、开平方或调整 error 单位 |

本地相关实现：[export_subset.py](../src/data3001/acquisition/export_subset.py)、[prep_run.py](../src/data3001/preprocessing/prep_run.py)。前轮原始 source_objects 对照见 [source_spot_checks.json](../provenance/reviews/position_error_s4_e8_preflight/source_spot_checks.json)。

还有一个需要保留的事实：2026-11-06 从官方 FTP 的 `hourly_product/v2.01.1/` 下载 ID 7647、36606，error 与旧 v2.00 一致，但内部 `history` 仍写 v2.00。它们与当前 ERDDAP／本地来源链数值不同。**不能只看目录中的“v2.01.1”就认定是同一份内容，也不能据此宣称官方已经发布了明确的修复。** 后续应锁定完整 URL、内部元数据和 SHA256。

## 4. 缺失值与例外：为什么不能全部乘十万

扩大检查到 **19 个训练 ID、65 个观测、130 个两轴字段值**，专门纳入已发现的负值、较大正值和缺失值。该检查是诊断取样，不是总体比例估计。

| 类型 | 字段值数 | 旧存档 → 当前 canonical |
|---|---:|---|
| 常规正值 | 90 | 缩小约 100,000 倍 |
| 保持旧尺度的正值 | 4 | 纬度 error 数值不变，同时经度 error 从 0 变缺失 |
| 异常负值 | 10 | 纬度 error 从 0 变成约 −9.99999 |
| 上述四个观测的经度 | 4 | 0 变缺失 |
| 其他缺失 | 22 | 旧填充值约 −10³⁴ → 当前缺失 |

`−9.99999 = −999999 × 10⁻⁵` 与新发布文件的填充值及缩放因子吻合。这是“缺失标记也进入缩放流程”的强线索，不是合法的负不确定性。

保持旧尺度的四个纬度值为 0.00166°、0.00080°、0.00118°、0.01194°。全部乘十万会把它们变成 166°、80°、118°、1,194°，显然不能作为统一修复方法。

这 65 个观测在 NCEI archive 3.3 中的两轴 error 与本地全部一致（按填充值映射缺失）；当前坐标也全部一致。旧版中 11 个双轴缺失的 GPS 观测坐标有所不同，不能将其当成“位置完全相同的尺度证据”；其余 54 个观测坐标精确一致。核心 1,604 个终点比较已单独检查坐标。

## 5. 方差、标准差、CI 的结论

**没有证据表明本次毫米数值只是“把方差当标准差”。**

- 方差的单位应为度²，公开字段单位是度。
- 作者代码已有开平方和 CI 系数步骤；其输出不是待开平方的原始方差。
- 平方／开平方不会对所有不同幅度的正值产生相同的十万倍比例。
- 正态近似下的 1.96、历史代码中的 t 分位数，或半宽／全宽的 2 倍，均解释不了固定的十万倍。

**确有元数据命名冲突：**NCEI v2.00 合并文件把这两列称为 standard error；同版本原生单 drifter 文件称为 95% CI，作者代码也构造 CI。不能根据合并文件的单一名称再乘 1.96。对当前产品应保留这个冲突及来源证据；历史方法支持“CI 半宽”的解释，不代表已经证明其真实覆盖率或二维分布形状。

## 6. 现在能否用于构造 CI

1. **本地现有原值：暂不能直接用。** 已存在系统尺度差异及非统一例外。
2. **正确来源的字段：有作为位置估计不确定性使用的依据。** 优先按 ID、时间和坐标从核实后的原生发布文件恢复／核对字段，比在模型中全局乘一个常数更可靠。需另列数据修订记录，处理版本差异、不可用值和追溯标记；本轮未执行修复。
3. **边界仍然存在：**逐轴 95% CI 不自动给出二维相关性、正态分布或联合 95% 区域；它描述观测位置误差，不能独自决定七天后的落点分布范围。CI 恢复和 CI 是否改善预测，是两个需要分别验证的问题。

因此，本轮先前“典型 error 只有毫米，所以对预测可能太小”的物理解释不能继续沿用。毫米数值是当前发布链的字面数值，尚不能当作 drifter 真实定位精度。也不能反过来宣称恢复较大的 CI 就一定提高预测质量。

## 7. 可复核证据与剩余未知

- [汇总与断言复核](../provenance/reviews/position_error_s4_e8_source_trace/source_trace_summary.json)
- [原生 v2.00 元数据与 SHA256](../provenance/reviews/position_error_s4_e8_source_trace/legacy_v2_00_native_inspection.json)
- [不同下载渠道对照](../provenance/reviews/position_error_s4_e8_source_trace/current_delivery_route_comparison.json)
- [旧版异常记录逐条对照](../provenance/reviews/position_error_s4_e8_source_trace/ncei_1_1_exceptions.json)
- [当前存档逐条对照](../provenance/reviews/position_error_s4_e8_source_trace/ncei_3_3_exceptions.json)
- [作者源码片段与固定 commit](../provenance/reviews/position_error_s4_e8_source_trace/author_code_snippets.json)
- [证据文件校验清单](../provenance/reviews/position_error_s4_e8_source_trace/sha256_manifest.json)

NCEI 原文件：[archive 1.1 / v2.00](https://www.ncei.noaa.gov/data/oceans/archive/arc0199/0248584/1.1/data/0-data/gdp_v2.00.nc)、[archive 2.2 / v2.01](https://www.ncei.noaa.gov/data/oceans/archive/arc0199/0248584/2.2/data/0-data/gdp_hourly.nc)、[archive 3.3 / v2.01.1](https://www.ncei.noaa.gov/data/oceans/archive/arc0199/0248584/3.3/data/0-data/gdp_hourly.nc)。这些是大文件；本轮使用远程范围读取，未下载全球观测文件。

仍未知：v2.01 生产转换的具体错误代码行、全部记录的可修复规则、官方不同发布渠道差异的完整说明、恢复字段后实际 CI 覆盖率。本轮未联系数据提供者，也没有把这些未知当成已确认结论。
