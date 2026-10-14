# DATA3001 official hourly data acquisition

## Current handover additions (2026-10-13)

The core preprocessing was accepted by the architecture audit. Read [the versioned handover addendum](preparation/remediation_20261013/README.md) for regional wet-area release weights, depth/hardware audits, short-lag ID support, 365-day limitations and the source-position reason correction. The original baseline remains preserved. Primary depth-mixture policy is pending architecture decision; predictive accuracy remains untested. The acquisition-stage narrative below describes historical stage status; final D is now frozen as documented in the preparation package.

This folder contains the downloaded NOAA GDP hourly data and its acquisition evidence. The research authority remains the final Data Contract v1.0 Excel, identified in `manifests/authority.json`.

## Downloaded data

The main data file is the directory **`raw/hourly_subset_v2.01.1.zarr`**. It is a complete, locally readable ragged-array subset of the verified official v2.01.1 asset. All **60 source fields** are retained: 20 observation fields and 40 trajectory metadata fields. Two additional trajectory arrays record the original source indices.

| Cohort | IDs | Full available hourly records |
|---|---:|---:|
| All acquired trajectories | 3,741 | 39,107,061 |
| Trajectories with an hourly observation in R | 463 | 6,243,277 |
| Additional downstream trajectories, without an R visit | 3,278 | Included in the total above |

Every selected ID retains its **entire available source trajectory**, including history before R, later re-entry, and observations beyond 365 days after its initial R visit. The data have not been restricted to records lying inside R or the acquisition envelope. No source values, flags or uncertainty fields were edited or removed.

`raw/source_objects/` preserves downloaded, byte-identical compressed objects from the official source. It also contains global coordinates used to discover IDs. This cache is a **partial global asset**, not a complete global dataset; use the complete local subset for ordinary analysis. Cached observations belonging to unselected neighbouring IDs are not additional training data.

## Source and selection

- Official source: [NOAA GDP hourly data](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php).
- Exact asset: `https://noaa-oar-hourly-gdp-pds.s3.amazonaws.com/latest/gdp-v2.01.1.zarr/`.
- Dataset DOI: [10.25921/x46c-3620](https://doi.org/10.25921/x46c-3620).
- The actual asset history identifies **v2.01.1**, created on 2024-07-30. The measured full-corpus time range is **1987-10-02 13:00 UTC to 2022-10-31 00:00 UTC**. Downloading in 2026 does not extend that cutoff. All source time chunks were checked in `metadata/corpus_time_coverage.json`; use this actual cutoff for subsequent administrative-immaturity labels.
- R is the existing Gulf Stream corridor polygon intersected with 30–35.5°N, 82–73°W. Geometry uses longitude, latitude in CRS84 and includes the polygon boundary.
- R IDs were discovered by scanning all 197,214,787 hourly coordinates in this asset. Six-hour screening supplied only the historical polygon vertices, not an ID whitelist.
- All 19,396 official int64 GDP buoy IDs were assigned before domain selection. Hash input is ASCII `20261004:<canonical-positive-decimal-ID>`; the unsigned SHA-256 digest divided by 2^256 maps to train `[0,0.70)`, validation `[0.70,0.85)`, and test `[0.85,1)`. No existing assignment was changed to balance proportions.

| Split | R IDs | All acquired IDs |
|---|---:|---:|
| Train | 323 | 2,674 |
| Validation | 73 | 550 |
| Locked test | 67 | 517 |

The additional acquisition envelope is **86°W–3°W, 15°N–60°N**. It was derived from the union of 365-day future windows after all hourly R origins in the 396 train/validation trajectories, then rounded and conservatively padded. Zero test IDs were used to choose the envelope. Nested acquisition candidates and observed path cells are recorded separately.

**This envelope is for data collection. Final model D is not frozen.** Its padding is an engineering allowance, not a transport confidence bound or an optimal domain claim. A subsequent support and boundary audit must select the actual model D using development evidence.

## Checks and evidence

- Eight training-only pilot trajectories contained 41,619 rows. Source interval lengths, timestamp order and distinct endpoint/stopped labels were checked before expansion.
- Nine boundary tests cover stable ID assignment, grid boundaries, exact/tolerant matching, known exit followed by disappearance, return, later drogue loss, unknown-state exclusion, and source chunk crossings.
- Each source object was fetched with its frozen `If-Match` ETag and recorded with its URL, size and local SHA-256. `manifests/downloaded_objects.jsonl` records individual receipts.
- `manifests/subset_export.json` records source-selected and re-read output value hashes for every field.
- **`audit/acquisition_verification.json`** contains the final independent readback, full source checksums, per-ID row reconciliation, source/configuration/geometry/code hashes, and current limitations. Its existence and `PASS` are required for a completed acquisition claim.

Important files:

| File | Meaning |
|---|---|
| `manifests/global_id_split.csv` | Immutable assignment and source offsets for every official ID |
| `manifests/R_ids.csv` | R cohort discovered from the hourly asset |
| `manifests/acquired_ids.csv` | Exact selected IDs represented in the local subset |
| `metadata/variable_dictionary.json` | Source attributes, units, flags and storage encodings |
| `geometry/release_R.geojson` | Frozen release geometry |
| `geometry/acquisition_envelope.geojson` | Provisional development-derived acquisition geometry |
| `audit/pilot_label_examples.csv` | Real pilot examples; R is used only as an illustrative stopping domain |
| `audit/acquired_trajectory_profile.csv` | Acquisition profile, separately identifying train/validation/test |
| `contract_mapping.tsv` | Existing contract clauses mapped to fields, decisions, edge cases and evidence |

## Interpretation and next step

This is a **raw acquisition**, not a completed scientific preprocessing or modelling result. Hourly source values are processed estimates, not independent hourly physical measurements. Retain the source flags separately from subsequent derived flags.

Missing SST does not invalidate a usable position. `gap` is the interval between original location observations and must not be confused with a missing hourly timestamp. The source's 0/1 drogue field is preserved, together with loss dates; the absence of an unknown flag code does not prove that every loss-date convention or physical state is resolved.

Formal preprocessing must next implement full QC/eligibility ledgers, decode missing and zero loss-date conventions, audit cell/season/regime/horizon support, compare candidate D boundaries, and prepare the contractual lag/remainder and direct-reference pairs. Unknown/switching intervals must remain in storage even when excluded from fixed-regime estimates. Endpoint occupancy and stopped-process labels must remain separate.

No model has been fitted and no final test prediction has been evaluated.

The acquisition profile found **13,276 non-hourly adjacent time intervals**, with zero duplicated or nonincreasing timestamps. The original gaps remain intact; `audit/time_gap_diagnostic.json` records their durations. A gap before an otherwise possible first exit cannot supply a complete path label. **1,366,330 records** have usable position/time but missing SST and are retained. These findings do not constitute the full cell/season/regime/horizon support audit.

## Read and reproduce

The environment versions are frozen in `metadata/environment_lock.txt`. A local acquisition environment is available at `.venv/`. The standard-reader check uses the tested compatible pair xarray 2025.3.1 / Zarr-Python 2.18.7; its recorded dimensions are 3,741 trajectories and 39,107,061 observations. The data themselves follow the Zarr v2 storage format.

For raw values with original encodings:

```python
import xarray as xr
ds = xr.open_zarr(
    "raw/hourly_subset_v2.01.1.zarr",
    consolidated=True, chunks=None,
    decode_cf=False, decode_times=False, mask_and_scale=False,
)
```

The source is ragged: trajectory `i` occupies observations between cumulative `rowsize` offsets. The observation index alone is not a drifter ID. Raw time is seconds since 1970-01-01 00:00:00 UTC.

Scripts retain source checks and support interrupted downloads. Resume this **same frozen run** only. A changed geometry or source requires a fresh query namespace/manifest; cached discovery files are not an automatic way to change the contract or dataset selection.

```text
.venv/bin/python scripts/acquire_hourly.py verify
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/verify_acquisition.py
```

Large raw data and the local environment are excluded from ordinary Git commits. Keep the source receipts and downloaded files when moving or archiving this project.


## Formal preparation, 2026-10-12

The full official-hourly preparation is now in `preparation/`. Begin with `preparation/READINESS_REPORT.md` and `preparation/docs/MODELLING_HANDOVER.md`. Acquisition receipts above remain historical records of the acquisition stage; their cleaning/D flags describe that earlier stage and are not rewritten. Current geometry/rule versions and readiness are in the preparation freeze and verification records.
