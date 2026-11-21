# 代码迁移与复现验收

更新：2026-11-22，Australia/Sydney。迁移按 `code_delivery_plan.md` 实施。本文件记录实际检查，完整任务状态由 `python code/workflow.py list` 给出。

**当前入口：**按用户最新决定，教授已有Python3.12和可运行的Notebook内核。首个配置单元只安装与检查项目依赖、初始化运行入口。此前自动安装Python及VS Code自动绑定方案已退出正式流程；下文相关记录保留为历史检查。

## 已完成检查

| 检查 | 实际结果 | 证据 |
|---|---|---|
| 原科学实现 | 已迁移源码保持原字节；运行入口在独立目录恢复原相对布局 | `migration_manifest.json`；`../provenance/migrations/code_delivery_20261122/source_and_archive_check.json` |
| archive保留 | 79,758项路径、大小、修改时间和链接与迁移前一致 | 同上；`archive_before.json` |
| 新环境 | Python3.12.14；锁定依赖；9个主要计算库的小型运算与C++17/Accelerate编译运行通过 | `code/environment/check.py`；新环境准备记录 |
| 原科学测试 | 928项中927项通过；1项真实封存测试集SST检查跳过 | `results/reproduced/delivery_scientific_verification_pass/command_001.log` |
| 新交付检查 | 68项环境、调度、原始数据重放、图表和真实进程中断检查全部通过 | `code/tests/test_delivery*.py` |
| 原始数据重放 | 5条开发集轨迹，27,002行原始记录生成26,994行v7；五份轨迹SHA256与原文件一致，资格标记内容一致 | `results/reproduced/raw_replay_development_validation_20261122_v1/run.json` |
| 季节矩阵重新拟合 | 新pilot与primary均完成，原合同、拟合与评分流程通过 | `results/reproduced/delivery_seasonal_refit_check2/` |
| 早期任务选择版Notebook | 当时全部执行单元成功，运行一次冻结22成分模型预测；此记录不代表当前完整流程已运行通过 | `results/reproduced/notebook_validation/executed_notebook.ipynb` |
| 分章节Notebook初版 | 当时结构有效，44个代码单元可编译，41个任务均有独立入口；8项模拟调用检查通过，未执行实验 | `notebook_entry_check.json`；`code/tests/test_delivery_notebook_entry.py` |
| 独立目录预测 | 复制519项必要文件到含空格的新目录，成功加载冻结22成分模型 | `portable_inference_check.json` |
| 经验矩阵重新拟合 | 全部5折、12个矩阵；最大概率误差0，最大Brier误差6.66e-16 | `results/reproduced/delivery_step1_refit_check/` |
| 报告图表 | 原脚本重新生成10张图；PNG逐字节一致，PDF已重绘 | `results/reproduced/report_replay_20261122_verified/report_verification.json` |
| R区域重新积分 | 37个有支持起点格，77,594,624个积分终点；另用303,104个样本独立验证；概率与原结果一致 | `results/reproduced/report_region_recomputed_20261122_verified/report_verification.json` |
| Presentation导出 | PT2/3/4的JSON和3份CSV与发布版字节一致；38,260个数值零差异 | `results/reproduced/presentation_export_validation_20261122_v1/presentation_verification.json` |
| 已跟踪结果保留 | 8,231项原Git结果在新位置完整保留，文件或符号链接内容与Git记录一致 | `tracked_results_check.json` |
| 未解析释放权重 | 0.008605277291120008，约0.86%；保留在总概率中 | 同上 |
| 打包 | Python、C++及运行资产在wheel中保持原哈希；仓库README不属于运行资产 | `wheel_check.json` |

以上证据文件中未写完整路径的JSON位于 `provenance/migrations/code_delivery_20261122/`。新运行目录位于仓库根目录下，不会覆盖原结果。

## 当前保留方式

- `archive/`保留原样，包括迁移对照所需内容。
- 旧 `src/`、`tests/`、配置和结果位置保留兼容链接；可阅读的代码实体集中在 `code/`。
- 受冻结保护的最终模型实验目录仍保留原物理位置，新结果目录引用它。交付模型权重在 `saved_models/`提供哈希相同的独立文件。
- 原科学文件使用历史路径和源码校验。执行入口因此创建独立的历史布局，并记录每项输入来源；不修改模型计算以适应目录。
- 正式Word移至 `report/`，原位置保留链接，内容未重写。已确认图表移至 `results/reference/report/figures/`，由 `report/figures`导航。

## 检查范围

加载冻结模型、恢复已有结果、重新绘图、重新拟合是不同任务，运行回执分别记录。一次成功预测不等于所有模型都已重新拟合。完整实验的发布还需要核对Git版本及大型输入的获取方式；本次不上传数据或发布远程版本。

原测试中有一项需要读取封存测试ID60350的SST记录。默认迁移验收保留该测试但不提供其真实输入；模型开发和报告复现不读取封存测试轨迹。合成测试中的虚构test ID只用于检查访问保护。

原始数据重放使用已批准的SST修复决定，不重新执行海温插值方法研究。Zarr源文件按共享块存储；开发轨迹所需块可能包含相邻ID的字节，运行记录因此分别标明共享块范围和实际请求的开发ID，不将此写成“从未接触任何测试字节”。

## 必要的工程适配

- 原实验审批所需的旧版Markov结果说明和研究日志已按已存哈希恢复到执行输入包；未覆盖当前说明。旧日志的一份版本通过撤回后续已知追加内容恢复，并与原审批SHA256完全一致。
- 季节精确位置实验的旧检查还登记了两个Finder生成的`.DS_Store`文件。这两份旧字节无法恢复，新执行记录明确排除这两项操作系统显示元数据；所有科学源码、数据、配置检查仍保留。原审批文件不修改。
- Presentation第二部分的原导出程序写死了作者路径。执行副本只替换这两处输入路径，并记录原脚本和执行副本哈希；原程序保持不变。临时Natural Earth原文件已不存在，现已补入固定上游版本；恢复的地图几何和最终JSON与发布版完全一致。
- 原Git中8,231项结果的迁移另有发布清单和忽略规则，确保它们不会因移动到新目录而在后续提交中丢失。新产生的长时运行和完整本地缓存不会自动加入Git。

## 长时重训的实际状态

41个入口均已实现。`stage1.all`、`stage2.all`与`full.refit`提供分组执行；默认完整流程包括31个模型、输入或评分阶段，随后重建报告与Presentation。两阶段的小型组合已经实际运行通过，完整长时流程未执行。

Gaussian、Gaussian mixture及网络模型，以及位置误差和精确位置季节模型已通过真实初始化及原合同输入检查。Gaussian的128项数值对照和私有进程一致性均通过；空闲复查预计正式计算含原余量为16,566.78秒，高于原14,400秒上限，程序因此停止。第一次有并行测试时预计18,224.9秒；两次失败均保留。没有修改上限、拟合目标、参数或训练次数，也没有将初始化写成已完成重训。

完整入口使用各模型原先固定的输入；新清洗结果不会自动替换后续哈希绑定的输入。每项运行记录`dependency_mode=frozen_published_inputs`和`upstream_refresh=false`。MDN的12种成分数量比较会先重新训练原六组模型，再训练六组新增模型；不是复制父网络后宣称全部重新训练。

## Notebook直接运行入口修订

2026-11-22按用户要求取消任务选择器。当前顺序为环境配置、完整流程、数据预处理、Stage 1、Stage 2、最终模型与报告图表。总入口依次重放清洗、运行两轮实验并重建展示结果；各模型均有独立单元，保留原合同及固定输入。

当前“Run All”会启动完整研究流程。新增的Notebook控制层在整组成功后显示已有结果，避免后续单模型单元重复拟合；失败的分组不记作完成。8项检查采用模拟执行器，覆盖环境阻止、分组复用、失败处理、单项重跑、不同参数以及当前Notebook的实际调用顺序。另检查所有任务覆盖、代码语法、章节顺序、默认注释的安装单元和空白执行输出。

本轮未安装环境、运行数据处理或拟合模型，也未执行新版Notebook的完整流程。原Gaussian预算限制保持不变，早期冻结模型Notebook的成功记录不作为新版全流程验收依据。

## 首次安装与本地启动修复

2026-11-22用户在VS Code连接Colab后，已保存的错误显示远程内核找不到项目目录，随后环境结果及Notebook入口变量未定义。当前安装和部分原生计算依赖macOS，因此不能通过远程内核直接使用本地项目。

新增根目录`START_HERE.command`，首次启动不依赖已安装的Python或Notebook内核。它调用原统一环境脚本，自动准备Python、依赖和项目内核，打开本地Notebook。缺少Apple编译工具时调起系统安装窗口；启动阶段不运行实验。`launch.py`只修正Notebook内核登记，保留单元、内容及已保存输出。

29项环境检查测试与4项首次启动测试通过；测试覆盖无Python可执行程序的启动路径、自动准备入口、错误退出、内核修正与单元输出保留。当前Mac上实际运行启动器后，本地Jupyter服务及Notebook会话成功建立；另在真实新内核中执行Notebook原环境检查与入口初始化，两项均通过，解释器为项目Python3.12.14。证据见`provenance/migrations/code_delivery_20261122/first_launch_check.json`。该验证没有运行模型，也未在全新无配置Mac或Colab上执行完整安装。

## VS Code正式入口与单一配置单元

用户明确要求保留VS Code，取消必须手动运行command和查找Python路径的交付路线。新增`.vscode/tasks.json`，打开完整项目后调用统一准备脚本；工作区设置预设项目`.venv`，扩展清单推荐Microsoft Python与Jupyter。Notebook合并为一个环境检查及入口初始化单元，删除原手动安装与切换说明，研究单元保留。

当前VS Code实际打开项目后，自动准备任务已启动。首次运行显示了项目Python3.12.14的推荐内核，仍需确认；本次由助手完成绑定后，在VS Code中点击首个检查单元，实际输出`Environment: ready`，计算库及编译检查通过。合并后的配置单元也在同一项目解释器中单独运行通过，未调用研究任务。该结果证明当前机器可运行，不证明全新VS Code能完全省略首次信任、任务授权或内核确认。

另发现本机VS Code用户设置含两个并列JSON对象，导致“无法写入用户设置”。已修复对象拼接语法，核对28项设置值全部保留，并在系统临时目录保存原文件。此为本机修复，不作为项目依赖或分发内容。当前验收记录见`provenance/migrations/code_delivery_20261122/vscode_startup_check.json`。


## 已有Python下的依赖配置（当前方案）

2026-11-22用户停止Python安装和内核管理工作，改为假设教授已有Python。正式Notebook首个配置单元现在调用`code/environment/configure.py`，向当前解释器安装`uv.lock`规定的依赖并初始化实验入口。接受Python3.12系列，记录实际补丁版本；不再要求解释器位于项目`.venv`。

已移除`.vscode/tasks.json`中的自动安装任务及`.vscode/settings.json`中的专属解释器预设。Notebook只修改开头两段说明和配置单元，后续全部研究单元与Notebook内核元数据保持不变。README和正式规划已同步。此前启动脚本保留为历史对照，不再进入正式流程。

实际验收：

- 从已有Python3.12.14建立一个位于系统临时目录、没有项目依赖的环境，实际运行正式配置单元：141项依赖及项目安装完成，计算库与编译检查通过，入口显示Ready。
- 在该独立环境的真实Jupyter内核中连续运行配置单元两次，均通过。该环境不在项目`.venv`内，证明当前入口无需专属解释器路径。
- 另在当前项目Python中运行正式配置单元，通过。6项当前Python配置检查、29项原环境回归检查及8项Notebook调度检查均通过，共43项。
- 测试首次获取包安装工具时，原官方脚本下载返回HTTP403。已改为获取官方PyPI上的固定Apple Silicon wheel并核对SHA256；真实下载、提取和版本检查通过，错误校验值会阻止使用。
- `pyproject.toml`、`uv.lock`和`.python-version`未改变；后续研究单元的整体哈希未改变。未运行数据处理、模型训练或报告分析，未修改原科学代码、数据、冻结模型及archive。

证据保存于`provenance/migrations/code_delivery_20261122/notebook_packages_check.json`。支持平台仍为Apple Silicon、macOS14及以上和原计算所需Apple编译工具。本轮没有重新验证VS Code重启后的内核选择，用户已将该问题移出任务范围。依赖更新若涉及内核已加载的包，配置单元提示重启当前内核后重跑；不要求切换到其他内核。
