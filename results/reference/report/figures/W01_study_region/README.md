# W01-F1：研究区域定位图

日期：2026-11-19。用途：W01引言中的地理定位与释放区定义。图为中文讨论版；建议按报告通栏放置，宽约17–18 cm，最终组装时统一图号。

## 内容与来源

左图显示墨西哥湾、Florida、Bahamas和美国东岸的地理关系；右图放大正式释放区R。蓝色边界直接读取冻结的GeoJSON，虚线表示该多边形的经纬度外包框。图采用WGS84经纬坐标，按各面板中纬度调整纵横比。

- **正式R外包范围：**30°–35.5°N、81°–73°W。
- **正式R顶点（经度、纬度）：**(-80,32)、(-77.375,35.5)、(-73,35.5)、(-73,31.333333333333332)、(-75,30)、(-81,30)，最后闭合回起点。
- **来源定义：**原始Gulf Stream Corridor与[-82,30,-73,35.5]裁剪窗口的交集；裁剪窗口和所得多边形外包框分别保存。
- **海岸线：**项目已有GSHHG 2.3.7中分辨率L1陆地几何。
- **数据使用：**读取注册的区域与海岸几何，未读取drifter轨迹或模型预测。

[区域GeoJSON](../../../work_place/archive/data_before_release_20261016/reference/acquisition/geometry/release_R.geojson) · [海岸线几何](../../../work_place/archive/data_before_release_20261016/reference/preparation_v1/geometry/gshhg_i_land.wkb) · [资产注册表](../../../work_place/configs/assets.json)

## 文件与复现

- [PNG预览](figure_w01_region_zh.png)
- [SVG矢量版](figure_w01_region_zh.svg)
- [PDF矢量版](figure_w01_region_zh.pdf)
- [绘图脚本](figure_w01_region.py)
- [来源、版本与哈希记录](figure_w01_region_provenance.json)

在DATA3001工作区执行：

```bash
work_place/.venv/bin/python 'Final Report/figures/W01_study_region/figure_w01_region.py'
```

脚本使用现有项目环境中的matplotlib和shapely，先核对两项资产的注册SHA256，再导出图和来源记录。中文字体优先Arial Unicode MS，也支持Noto Sans CJK SC或PingFang HK；本轮使用Arial Unicode MS。

## 图注

**图1　研究区域的地理位置与正式释放区R。**（a）墨西哥湾、佛罗里达与美国东岸的地理关系；（b）Gulf Stream南段释放区放大图。蓝色轮廓为研究采用的R多边形，虚线为其经纬度外包框：30°–35.5°N、81°–73°W。区域边界来自项目冻结GeoJSON；海岸线为GSHHG 2.3.7，坐标采用WGS84。

## 核验

本轮已执行绘图脚本，两个输入哈希均与资产注册表一致；R几何有效，外包范围与顶点已核对。PNG已实际查看：中文、经纬度、图例与两个面板清晰可读，标注完整。终稿缩放和英文图注在全文组装时核验。
