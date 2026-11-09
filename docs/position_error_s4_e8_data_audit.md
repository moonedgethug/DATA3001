# Step 4 E8：位置 error 的定义与尺度核验

> 2026-11-06 后续追溯更新：已确认上游发布文件之间约 100,000 倍的尺度差异，并发现缺失值／例外处理不一致。原因与证据见 [来源与缩放追溯](position_error_s4_e8_source_trace.md)。下文保留首次审计时的发现；“尚无法定位上游”的状态以新报告为准。尚未修改数据或运行模型。

## Material Passport

- Origin Skill / Mode: academic-research-suite / experiment-agent, plan
- 日期：2026-11-06，Australia/Sydney
- 状态：只读数据审计完成；物理尺度解释未通过；没有开发或运行预测实验。
- 对象：冻结 E7 的 2001–2019 拟合资料；没有读取本轮外层验证的 endpoint error，没有访问锁定 final-test。

## 1. 当前结论

**字段名称和标注单位已核实，不能因此说物理 CI 的尺度已经核实。**

本地原始元数据与 [NOAA 官方变量字典](https://erddap.aoml.noaa.gov/gdp/erddap/info/drifter_hourly_qc/index.html) 一致：`err_lon`、`err_lat` 分别标注为经度、纬度的 95% confidence interval，单位为 `degrees_east`、`degrees_north`。它们不是速度误差，不是七天后的漂流范围，也不同于 SST 的标准误字段。

但本轮拟合资料的多数数值按这个单位换算后只有毫米量级。原始缓存和官方在线查询也出现相同数值。**当前证据不足以把它们当成已校准的真实位置不确定性，不能据此承诺 CI 扩散会改善预测。**

## 2. 覆盖范围与实测数值

使用冻结运行 `exact_origin_s4_e7_primary_20261105T074326_829211Z` 的 `training_coordinates.parquet`：265,393 个七天配对、338 个 drifter、355,247 个去重后的起终点观测。逐一核对全部 338 个 canonical 文件 SHA256；起终点 key、时间、坐标连接全部通过。

下表按配对出现次数统计，不是按独立 drifter 统计的预测性能。正值的经纬度幅度分别通过 WGS84 地理距离换算；尚未将幅度解释为标准差或二维半径。

| 字段位置 | 幅度中位数 | P95 | P99 | 缺失/非有限 | 负值 |
|---|---:|---:|---:|---:|---:|
| 起点 err_lon | 0.002036 m | 0.010627 m | 0.019530 m | 342 | 0 |
| 起点 err_lat | 0.001563 m | 0.007528 m | 0.014406 m | 338 | 11 |
| 终点 err_lon | 0.002035 m | 0.010629 m | 0.019589 m | 474 | 0 |
| 终点 err_lat | 0.001576 m | 0.007768 m | 0.015233 m | 470 | 10 |

- 起点至少一轴不可用：353 / 265,393，0.1330%。
- 终点至少一轴不可用：484 / 265,393，0.1824%。两轴不可用事件重叠，不能简单相加。
- 当前训练配对没有 E；合法训练终点的七天位移中位数为 **140.002 km**，P95 为 696.404 km。
- 终点纬度误差仍有 4 条超过 1 m，其中最大幅度约 1,324 m。中位数很小不代表所有记录都很小。
- 以上是描述性统计，不是“CI 没用”的假设检验结果。

完整分位数、分时期统计、字段属性和文件校验记录见 [审计 JSON](../provenance/reviews/position_error_s4_e8_preflight/training_error_scale_audit.json)。[审计脚本](../provenance/reviews/position_error_s4_e8_preflight/audit_training_errors.py) 只读取冻结训练 key，不拟合模型。

## 3. 来源追溯

抽查训练终点，canonical 与原始 source_objects 的 float32 值完全相等：

| ID | source_obs | err_lon | err_lat |
|---|---:|---:|---:|
| 7647 | 5,294,393 | 1.1070000028e-7 | 6.4399998223e-8 |
| 99004 | 85,825,358 | 7.3000001599e-9 | 5.0000004137e-9 |
| 300234066710170 | 167,620,111 | 5.8000000358e-9 | 5.0000004137e-9 |

2026-11-06 对 NOAA ERDDAP 查询 ID 7647、2002-04-03 15:00 UTC，返回 `1.107E-7`、`6.44E-8`，标注单位仍为度。[原始字节抽查记录](../provenance/reviews/position_error_s4_e8_preflight/source_spot_checks.json) 和 [在线查询回执](../provenance/reviews/position_error_s4_e8_preflight/official_spot_check.json) 已保存。

检查本地 source、subset、canonical 属性，未发现这两个字段声明额外 `scale_factor`。现有 acquisition exporter 按原始值复制并保留校验，不在此处调整误差单位。上述证据排除了所抽查记录的本地转换差异，**不能证明上游所有版本都正确，也不能证明哪个上游环节存在错误**。

不擅自乘以 10^5、不擅自开平方，也不把小值替换成“看起来合理”的定位精度。若发现正式转换错误，必须另立数据修订及重建审批，不能在模型中隐藏修正。

## 4. 文献和作者代码能确认到哪里

[NOAA release notes](https://www.aoml.noaa.gov/phod/gdp/hourly_data_release_notes.php) 说明 GPS 位置误差由估计程序产生正式 95% CI，并记录过旧版本误差计算修正。它不是每条记录都直接使用 22 m 的常数。

作者公开的 [LatLonLocalWess.m](https://github.com/selipot/hourly-drifters/blob/master/LatLonLocalWess.m#L133-L139) 用 t 分位数乘估计标准误，并输出相对中心的坐标差；这支持“± 半宽”的历史方法解释。[GPS 主程序](https://github.com/selipot/hourly-drifters/blob/master/global_interpolation_GPS_1.01.m#L81-L103) 和 [piecelinvar.m](https://github.com/selipot/hourly-drifters/blob/master/piecelinvar.m#L24-L32) 继续传播这些误差。

[Argos 示例程序](https://github.com/selipot/hourly-drifters/blob/master/global_interpolation_wmle_errors_1.01.m#L103-L113) 又有不同的 CI 系数及文本输出缩放。这些是旧版示例，**尚未闭合到当前 v2.01.1 的完整生产转换链**。文件 blob SHA 见 [作者源码回执](../provenance/reviews/position_error_s4_e8_preflight/author_source_receipts.json)。

[Elipot et al. (2016)](https://doi.org/10.1002/2016JC011716) 讨论的原始定位误差、插值误差和估计方差属于不同对象；不能把论文某个典型误差距离直接填入当前字段。[Elipot et al. (2022)](https://www.nature.com/articles/s41597-022-01670-2) 也区分位置/速度的 CI 与 SST 的标准不确定性。

因此 `sigma = error / 1.96` 只能是将已确认 95% 半宽映射成一个正态工作核的约定，不是已证明恢复了原始估计标准误。CI 本身也不能识别二维相关性、尾部形状或真实位置的后验分布。

## 5. 进入模型前的门槛

需要针对当前产品厘清：毫米数值是否为正确物理幅度，是否存在未说明的编码/换算，以及半宽解释是否适用于当前字段。可靠依据应来自对应版本的生产转换代码、官方说明或提供者确认，不能靠验证集成绩选择解释。

此前 U02 已把负误差列为未决来源异常；继续保留合法位置配对，误差负值/缺失单独标记，不取绝对值。[原始未决记录](../provenance/frozen/preparation_v1/metadata/unresolved_questions.json)。

当前交付的是 [待审工程 contract](position_error_s4_e8_contract.md)。**即使认可科学设计，物理尺度门槛尚未通过时，也不能把基于这些字段的实验称为已验证 CI 的效果检验。** 可继续来源审计；若用户希望先测试字面数值，应另行明确批准为数值敏感性实验，而不是悄悄改称物理误差建模。
