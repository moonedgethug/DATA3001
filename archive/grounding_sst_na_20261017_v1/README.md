# DATA3001 — Where Things End Up

We are studying the probability distribution of surface-drifter destinations in the western North Atlantic. The planned product is a surface-transport operator with separate endpoint-occupancy and stopped-process outputs for **integer horizons from 1 to 365 days**, including annual and seasonal analysis. It is a research product; prediction accuracy has not yet been evaluated.

## Research scope

The initial release region **R** is the southern Gulf Stream Corridor polygon intersected with `[-82, 30, -73, 35.5]` (longitude/latitude). The frozen GeoJSON polygon determines membership; this rectangle is its clipping envelope. The finite transport domain **D** is `20–55°N, 81–8°W`, with a target-specific outside state. D is distinct from both R and the larger acquisition envelope.

We start with supported cells in R, then consider regional expansion only after a new coverage, path, holdout and common-target validation audit. The broader motivation includes search planning and surface-material transport near the US East Coast, Florida–Bahamas and the northern Gulf. These are application motivations, not validated object-specific oil, container or life-raft forecasts.

## Current status

- **Acquired source data:** 3,741 GDP IDs and 39,107,061 hourly records from the pinned NOAA GDP v2.01.1 asset, with original evidence retained. The current cleaned release contains **39,099,193** records after authorized vessel-recovery-tail deletion.
- **Current data layout:** `data/train/<id>.parquet` contains the 3,224 development IDs; `data/test/<id>.parquet` contains the same 517 final-test IDs. Each file retains all 130 columns, with cleaned total temperature in the existing `sst` column; earlier valid drift is retained and recovery tails are physically removed. See [the data guide](docs/data_layout.md).
- **Split provenance:** the original 2,674 train / 550 validation / 517 test assignments are retained. Original train and validation now share the development directory; no new validation split has been made. Of 463 R-visiting IDs, 396 are in development and 67 in final test. Future validation experiments must group by complete ID and save their allocation before fitting.
- **Prepared assets:** source-linked cleaned records, independent endpoint/stopped ledgers, frozen geometry, origin/event records and support audits. Main modelling starts at 1°; 0.5° geometry is prepared for subsequent refinement assessment.
- **Current feature review:** approved total-temperature fills and repairs are stored directly in the existing **`sst`** column (Kelvin) of every current data file. No separate temperature feature or merge is required; use `data3001.dataset.read_track` or read the Parquet file directly. The [SST storage report](provenance/migrations/sst_inplace_20261017_v1/REPORT.md) verifies unchanged rows, other fields and ID pools. SST has no gaps in R; 5,547 NA values remain after official last-good times on eventual-grounding IDs. Another 2,584 compared temperature-quality cases remain unresolved (213 in R). Components are outside this step. The 7,868 vessel-recovery-tail records remain removed. No model selection or training is part of this cleaning task.
- **Limits:** DEPTH-01 remains pending. Long-horizon seasonal support includes empty or highly concentrated groups. More hourly records do not create more independent drifters. No fitted-model, calibration or validated 365-day accuracy claim is made.
- **Data migration:** the complete previous data tree is retained in `archive/data_before_release_20261016/`. See [the release acceptance](provenance/migrations/data_release_20261016/acceptance.md). The earlier [architecture migration](provenance/migrations/architecture_20261014/progress.md) remains historical evidence.

## Start here

| Need | Entry point |
|---|---|
| Research definitions and binding rules | [Data Contract v1.0](docs/contract/data_contract_v1.0.xlsx) |
| Chinese translation for internal discussion | [Chinese contract](docs/contract/data_contract_v1.0_zh.xlsx) |
| Read one complete drifter file | [Data layout and usage](docs/data_layout.md) |
| Find IDs, rows and historical assignments | [Dataset index](configs/dataset_index.csv) |
| Understand all 130 columns | [Data dictionary](docs/data_dictionary.md) |
| Data meaning, restrictions and modelling handover | [Preprocessing guide](docs/preprocessing.md) |
| Repository rules, environments, migration and recovery | [Architecture guide](docs/architecture.md) |
| Exact active data versions and table roles | [Asset catalog](configs/assets.json) |
| Current migration acceptance | [SST storage report](provenance/migrations/sst_inplace_20261017_v1/REPORT.md) |
| Original versus augmented table selection | `state_index` and `lag_support` in the asset catalog |
| Submission proposal copy | [Proposal](results/deliverables/proposal/proposal_final.docx) |
| Historical plans and six-hour screening | `archive/` — reference only |

The controlled English Excel copy has SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`. Its original authority remains unchanged. Neither this README nor an older Markdown contract replaces it. Proposal remains a brief overview.

## Workspace

```text
src/data3001/  reusable acquisition/preprocessing code and safe entry points
configs/      versioned asset locations and pinned environment
data/train/  one complete Parquet per development ID
data/test/   one complete Parquet per locked final-test ID
results/     separate experiment runs and versioned deliverables
tests/       scientific rules and architecture boundary checks
docs/        current stage guides and controlled contract copies
provenance/  source receipts, frozen evidence and run/migration records
archive/     complete previous data tree, historical plans and report bundles
```

Large data, environments, caches and routine experiment outputs are excluded from Git. Retain the data/provenance bundle with its checksums; cloning the repository alone does not supply the raw or processed corpus.

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
