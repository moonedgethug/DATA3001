# 图2：区域选择与R、D

用途：W03两阶段区域筛选及R/D定义。左图展示原Gulf Stream走廊的南、中、北三个候选窗口；右图展示冻结R、D及数据获取范围。

- R：30°–35.5°N、81°–73°W之间的实际多边形，等于南段候选区。
- D：20°–55°N、81°–8°W。
- 数据获取范围：15°–60°N、86°–3°W，用于发现和下载轨迹。
- 候选边界来自[原筛选代码](../../../work_place/archive/region_screening_6h/gulf_stream_segment_audit.py)，R/D/海岸线来自[注册资产](../../../work_place/configs/assets.json)。海岸线为GSHHG 2.3.7，坐标为WGS84；各面板按中纬度调整纵横比。

[PNG](figure_w03_region_and_domain_zh.png) · [PDF](figure_w03_region_and_domain_zh.pdf) · [脚本](figure_w03_region_and_domain.py) · [来源与哈希](figure_w03_region_and_domain_provenance.json)

在DATA3001目录运行：

```bash
work_place/.venv/bin/python 'Final Report/figures/W03_region_and_domain/figure_w03_region_and_domain.py'
```

脚本读取几何定义并核对资产哈希，不读取drifter轨迹或模型预测。图注及正文引用保存在[W03](../../drafts/W03_region_selection_and_domain.md)。最终图号、英文标签和缩放随完整报告统一。

核验：注册资产与图文件哈希一致，南段等于冻结R，D包含R；已实际查看最终PNG，图例、标签和经纬度可读。
