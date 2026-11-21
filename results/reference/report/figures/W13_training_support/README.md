# W13年度训练资料图

图9用于说明最终七天模型训练资料的年度分配，同时区分配对数量与不同漂流器数量。仅汇总已有训练起点；没有模型训练、预测重评分或独立最终测试访问。

- 来源：`work_place/results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet`。
- 范围：2001–2019年，265,393组配对、338条独立漂流器。
- 分组：UTC出发年份；配对为行数，漂流器为每年不同ID数。各年漂流器集合可以重叠。
- [年度数据](annual_training_support.csv)；[输入指纹与方法](provenance.json)。
- [中文PNG](figure09_annual_training_support_zh.png)；[矢量PDF](figure09_annual_training_support_zh.pdf)。
- [复现程序](render_training_support.py)。在DATA3001根目录运行：

```sh
work_place/.venv/bin/python 'Final Report/figures/W13_training_support/render_training_support.py'
```

配对数按千组显示，独立漂流器数量按条显示；两个面板均从零起绘。19个年份全部保留，年份标签每两年显示一次。2011年的标注来自实际最大配对数，表示样本集中，未标为海况变化点。同一统计也保存在W13审计中。
