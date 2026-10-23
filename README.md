# DATA3001 — Where Things End Up

We study the probability distribution of surface-drifter destinations in the western North Atlantic. A **1° pooled 7/30-day endpoint baseline and its optimized B2/B1 blend have been fitted and evaluated using whole-drifter nested cross-validation**. The longer-term goal is integer-day forecasts from 1 to 365 days with annual and seasonal analysis; those extensions remain unvalidated.

## Latest progress — baseline model optimized

Open the [offline presentation page](results/deliverables/baseline_optimized/index.html) after downloading the repository. Double-click `index.html` in a browser; no server, Python runtime or internet connection is needed to view it. GitHub displays HTML source rather than running the page. The [scientific report](results/runs/baseline_blend_cv_20261022T160806_056571Z/REPORT.md) and [presentation guide](docs/baseline_presentation.md) explain the evidence and how to reuse the module.

The experiment compares B0 persistence, B1 whole-R endpoint frequencies, B2 origin-cell conditional frequencies and two B2/B1 blends. Five outer and four inner whole-ID folds keep tuning separate from held-out scoring. All models use identical eligible hourly pairs; the 517 final-test trajectories remain locked.

| Horizon | B2 held-out Brier | Grid blend Brier | Analytic blend Brier | B2 90% set hit | Analytic 90% set hit |
|---|---:|---:|---:|---:|---:|
| 7 days | 0.928878 | 0.928597 | 0.928845 | 87.48% | 93.85% |
| 30 days | 0.994400 | 0.989051 | 0.989005 | 67.20% | 86.20% |

Lower Brier is better; it is not percentage accuracy. At 30 days the analytic blend's mean 90% set expands from 64.9 to 128.4 geographic cells, so increased hit rate comes with reduced concentration. Seven-day Brier gains are small. Remaining zero-probability outcomes keep raw log loss infinite. The reported bootstrap intervals condition on saved OOF predictions and do not include refitting uncertainty.

Final full-development candidate weights in `p = (1 − λ) B2 + λ B1` are **Grid: 0.1 / 0.6** and **Analytic: 0.090942 / 0.585254** for 7 / 30 days. These are selected from all-development base OOF predictions, then used with refitted bases; their tuning loss is not an independent performance estimate. The map uses fold-specific weights for a valid held-out comparison. No environmental predictor, feature change or canonical-data modification was introduced.

## Research scope

The initial release region **R** is the southern Gulf Stream Corridor polygon intersected with `[-82, 30, -73, 35.5]` (longitude/latitude). The frozen GeoJSON polygon determines membership; this rectangle is its clipping envelope. The finite transport domain **D** is `20–55°N, 81–8°W`, with a target-specific outside state. D is distinct from both R and the larger acquisition envelope.

We start with supported cells in R, then consider regional expansion only after a new coverage, path, holdout and common-target validation audit. The broader motivation includes search planning and surface-material transport near the US East Coast, Florida–Bahamas and the northern Gulf. These are application motivations, not validated object-specific oil, container or life-raft forecasts.

## Current status

**Team download:** `main` includes the actual current files in `data/train/`
and `data/test/`, plus portable qualification evidence. Clone or pull this
repository, then follow [download and setup](docs/getting_started.md). There is
no separate data download or Git LFS requirement. The trajectories total about
3.75 GB; full raw caches and historical backups remain local.

- **Acquired source data:** 3,741 GDP IDs and 39,107,061 hourly records from the pinned NOAA GDP v2.01.1 asset, with original evidence retained. The current cleaned release contains **39,099,193** records after authorized vessel-recovery-tail deletion.
- **Current data layout:** `data/train/<id>.parquet` contains the 3,224 development IDs; `data/test/<id>.parquet` contains the same 517 final-test IDs. Each file now contains **62 columns** after the approved removal of 67 registered fields. Original `err_lat`, `err_lon`, `err_ve`, and `err_vn` values are retained, as are cleaned `drogue_status` and `sst`. All 39,099,193 rows and all remaining field values are unchanged. Exact parent files and qualification evidence remain outside active data. See [the data guide](docs/data_layout.md) and [projection verification](provenance/migrations/feature_pruning_20261017_v1/REPORT.md).
- **Drogue state:** `drogue_status` stores the exact previously approved labels: **1 drogued, 0 undrogued, -1 unknown**. The redundant `regime` column has been physically removed. No labels, loss dates or ID assignments were re-estimated. Original binary flags and the previous representation are archived. See the [column-consolidation report](provenance/migrations/drogue_status_inplace_20261017_v1/REPORT.md).
- **Split provenance:** the original 2,674 train / 550 validation / 517 test assignments are retained. Original train and validation share the development directory. The optimized baseline additionally freezes five outer and four inner whole-ID development folds; it does not change physical data membership. Of 463 R-visiting IDs, 396 are in development and 67 in final test. Eligible held-out support totals 387 IDs / 308,312 pairs at 7 days and 358 IDs / 287,004 pairs at 30 days.
- **Prepared assets:** source-linked cleaned records, independent endpoint/stopped ledgers, frozen geometry, origin/event records and support audits. Main modelling starts at 1°; 0.5° geometry is prepared for subsequent refinement assessment.
- **Modelling entry:** the current development-only audit supports beginning baseline experiments at 7/30 days in supported Corridor cells. Fixed-drogued endpoint support is 253 independent IDs at 7 days and 226 at 30 days; at 365 days it falls to 23 IDs (15 for the stopped target). These are eligibility counts, not model scores. Settle DEPTH-01 and freeze the model-stage validation protocol before a primary fit. See [the readiness assessment](results/deliverables/data_readiness_20261017/REPORT.md).
- **Current feature review:** cleaned total temperature is stored directly in **`sst`** (Kelvin), with no extra feature column or merge. On official eventual-grounding IDs, SST after the official last-good time is now numeric NA and must not be refilled: **16,059 records, including 47 in R**. SST outside this excluded context is unchanged. See the [current SST cutoff report](provenance/migrations/grounding_sst_na_20261017_v1/REPORT.md). Another 2,582 active temperature-quality comparisons remain unresolved (213 in R); the historical audit counted 2,584 before this cutoff. All other columns, rows and ID assignments are unchanged. Components are outside this step; vessel-recovery tails remain removed. No model selection or training is part of this cleaning task.
- **Limits:** DEPTH-01 remains pending. Long-horizon seasonal support includes empty or highly concentrated groups. More hourly records do not create more independent drifters. Pooled 7/30-day baselines now have development evidence; seasonal, grounding, object-specific, new-region and 365-day performance remain unvalidated.
- **Data migration:** the complete previous data tree is retained in `archive/data_before_release_20261016/`. See [the release acceptance](provenance/migrations/data_release_20261016/acceptance.md). The earlier [architecture migration](provenance/migrations/architecture_20261014/progress.md) remains historical evidence.

## Start here

| Need | Entry point |
|---|---|
| Present the optimized baseline | [Offline interactive page](results/deliverables/baseline_optimized/index.html) and [presentation guide](docs/baseline_presentation.md) |
| Inspect the latest held-out evidence | [Nested-CV report](results/runs/baseline_blend_cv_20261022T160806_056571Z/REPORT.md) |
| Research definitions and binding rules | [Data Contract v1.0](docs/contract/data_contract_v1.0.xlsx) |
| Chinese translation for internal discussion | [Chinese contract](docs/contract/data_contract_v1.0_zh.xlsx) |
| Read one complete drifter file | [Data layout and usage](docs/data_layout.md) |
| Download the actual data and verify a new checkout | [Team setup](docs/getting_started.md) |
| Find IDs, rows and historical assignments | [Dataset index](configs/dataset_index.csv) |
| Understand all 62 active columns | [Data dictionary](docs/data_dictionary.md) |
| Data meaning, restrictions and modelling handover | [Preprocessing guide](docs/preprocessing.md) |
| Evidence for starting baseline experiments | [Current modelling readiness](results/deliverables/data_readiness_20261017/REPORT.md) |
| Repository rules, environments, migration and recovery | [Architecture guide](docs/architecture.md) |
| Exact active data versions and table roles | [Asset catalog](configs/assets.json) |
| Current migration acceptance | [Hardware missing-value normalization](provenance/migrations/hardware_NA_20261017_v1/REPORT.md) |
| Original versus augmented table selection | `state_index` and `lag_support` in the asset catalog |
| Submission proposal copy | [Proposal](results/deliverables/proposal/proposal_final.docx) |
| Historical plans and six-hour screening | `archive/` — reference only |

The controlled English Excel copy has SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. Its original authority remains unchanged. Neither this README nor an older Markdown contract replaces it. Proposal remains a brief overview.

## Workspace

```text
src/data3001/  reusable data, modelling, scoring and presentation code
configs/      versioned asset locations and pinned environment
data/train/  one complete Parquet per development ID
data/test/   one complete Parquet per locked final-test ID
results/     separate experiment runs and versioned deliverables
tests/       scientific rules and architecture boundary checks
docs/        current stage guides and controlled contract copies
provenance/  source receipts, frozen evidence and run/migration records
archive/     complete previous data tree, historical plans and report bundles
```

The active cleaned train/test release and selected baseline runs are published with their checksums. Raw acquisition caches, complete cleaning backups, environments and routine or superseded experiment runs remain local. The verified intermediate display basemap is included for report reconstruction.

## Local use

Python **3.12.14** and the scientific dependency versions are preserved. The current local environment is `.venv/`. For a new machine, install the pinned requirements and package following [the architecture guide](docs/architecture.md#environment).

```bash
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m data3001 inspect
```

These commands do not fit a model or regenerate frozen data. `python -m data3001 verify-migration` verifies every current file against its archived predecessor and the approved SST decisions, including other fields, ID assignments, the contract hash and recovery exclusions. It requires the complete local migration inventory and retained history.

Read a development trajectory without opening a global table:

```python
from data3001.dataset import read_track, development_ids
frame = read_track(22165)  # all rows and columns; no automatic filtering
ids = development_ids()   # 3,224 complete development IDs
```

Development label generation uses a separate entry point:

```bash
.venv/bin/python -m data3001 pair --id <development-ID> --days 7 --population R
```

It reports independent target qualification without saving by default. Add a unique `--run-id` to save derived labels under `results/runs/` with provenance. This is label preparation, not a probability forecast. Final-test trajectories are denied by this entry point.

## Team

The current team has four members: **Junxi Xiao, Han Wang, Ming Yue and Yi Cheng Zhang**. Architecture decisions, implementation, validation and writing are coordinated across the team. Review rule changes against the authoritative contract before changing data eligibility or model inputs.
