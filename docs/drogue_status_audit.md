# Scoped drogue restoration and source audit — 16 October 2026

Storage update: these original correction contributions and source receipts are retained in the archive. Their approved labels and evidence are consolidated in the [current per-ID release](data_layout.md); do not apply the overlays twice.

This report records the preceding 44/68-ID task. The subsequently authorised boundary-cohort correction and current combined counts are in the [official boundary audit](drogue_boundary_audit.md). The current consolidated files already include both corrections; use the canonical reader described in the data guide.

## Decision and scope

**Group 1 is restored using official source evidence. Group 2 remains unknown in Dataset A; historical reassessment dates are retained as qualified evidence, not substituted as confirmed loss times.** No learned imputation or forecasting was performed.

The user authorised correction of the 44 official-fill IDs and source investigation of the 68 zero-loss IDs. The 3,137 hourly loss-boundary records and their precision rule were excluded from this change. Contract v1.0, geometry, source observations, split assignments and depth policy remain unchanged.

## Group 1: 44 official-fill IDs

All 44 original NOAA NetCDF files store `drogue_lost_date = -999999`, declare the same value as `_FillValue`, and explicitly define that code as **drogue still attached**. Original IDs and row counts match the local records. The preceding 42-file audit was retained; the two earlier cases were retrieved again for this correction.

| Item | Result |
|---|---:|
| Corrected IDs | 44 |
| Retained hourly records | 339,263 |
| Train / validation / test IDs | 34 / 7 / 3 |
| Changed hourly observation column | `regime`, from -1 to 1 |
| Original hourly fields or source metadata changed | None |
| Native local loss-date value | NaN, retained with explicit source interpretation |

The interpretation applies to the available historical trajectory. It is not proof that the instrument remains attached today. The interval rule is bounded by the last retained analytical observation. Missing path hours, unusable positions, termination and geometry uncertainty retain their existing meaning. Undrogued requests become known scenario mismatches; pooled target results remain unchanged.

The version is `official-drogue-attached-44-v1`:

- Development replacements: `archive/data_before_release_20261016/processed/drogue_attached_44_v1/`.
- Locked-test replacements: `archive/data_before_release_20261016/restricted_test/drogue_attached_44_v1/`.
- [Per-ID restoration table](../archive/data_before_release_20261016/reference/drogue_status_20261016/group1_restoration.csv).
- [Active correction manifest](../archive/data_before_release_20261016/reference/drogue_status_20261016/official_attached_44_manifest.json).

These archived directories contain only the 44 replacements. Existing baseline files remain frozen. Use `data3001.dataset.read_track(id)` for the complete current frame, `prep_pairs.load_track(source, id)` for analytical arrays, or `drogue_correction.prepared_track_path(id, historical_split, allow_test=False)` for the consolidated physical file. The release manifest pins each file hash and embedded correction evidence; the old replacement route remains a historical fallback. Test access requires explicit permission. The ordinary development `pair` command remains locked against test IDs.

Origins, compact event bounds, existing R anchor ledgers, per-ID anchor support at both retained resolutions, sensitivity support and short-lag support were regenerated for these IDs. Direct paired-target generation for any integer horizon from 1 to 365 days uses the corrected interval rule.

Only two of the 44 IDs visited R. Both are already members of the training partition; the correction does not create new independent drifters. Their additional eligible R-origin cases are:

| Horizon | Endpoint pairs gained | Stopped pairs gained |
|---|---:|---:|
| 7 days | 925 | 925 |
| 30 days | 904 | 824 |
| 90 days | 925 | 807 |
| 180 days | 925 | 711 |
| 365 days | 103 | 0 |

These are preparation-label counts, not forecast performance. Their non-monotonicity reflects horizon-specific endpoint and path eligibility. One of the 44 IDs still lacks a recorded drogue depth; attachment restoration does not settle DEPTH-01.

**Summary-version warning:** the frozen global support, depth/fold and census tables predate this correction. They were deliberately not overwritten. Current aggregates must replace these 44 old per-ID contributions with the new contributions, never add both. The scoped eligibility deltas are in each correction directory under `support/eligibility_delta.parquet`. No claim that the old global support tables have been refreshed is made.

## Group 2: 68 zero-loss IDs

All 68 original hourly NetCDF files were retrieved and inspected. All IDs, observation counts and zero loss codes match the frozen local source, representing **495,555 hourly records**. The field explicitly defines zero as **drogue status uncertain from beginning**. It is not a 1970 loss date, confirmed undrogued status, or a known transition with only its time missing.

The audit also located all 68 IDs by exact ID in the standard NOAA directory and deployment log. The directory page identifies its creation as 22 June 2026, although its title and row dates are not fully consistent; it is used as a later published metadata cross-check, not a new hourly data version. All 68 directory loss fields are `01 01 1979`. Its legend defines this as inability to interpret the drogue sensor readings. This directory encoding must not be confused with the different zero convention in the hourly NetCDF product.

There is additional historical evidence: all 68 appear in the **30 June 2013 drogue reassessment** file. For every ID, the manual reassessment date equals the frozen first-good-record date. The automatic dates are later than that first-good date for all 68. The manual dates therefore do not establish an observed drogued interval followed by an identifiable loss inside the analysed record.

| Source or interpretation | IDs |
|---|---:|
| Original hourly code explicitly unknown from beginning | 68 |
| Later standard directory explicitly unknown | 68 |
| Historical manual date equals first-good-record date | 68 |
| Confirmed observed drogued-to-undrogued transitions recovered | 0 |
| Reliable transition timestamps accepted into Dataset A | 0 |

The archive's `README_final.TXT` directs users to the standard directory for the most updated assessment. Consequently, an older automatic or manual date must not silently override the later unknown designation. The audit cannot establish why the metadata treatment differs for each ID; no per-ID physical failure explanation is invented.

All 68 have a good-deployment flag, which does not establish drogue attachment throughout the record. Recorded sensor types are 60 submergence, six tether strain and two unknown. The current hourly product does not contain the underlying submergence/strain sensor time series needed for independent sensor-level adjudication.

**Decision:** retain these 68 IDs and their original status codes. Their usable positions can contribute to the contracted pooled historical-mixture analysis. They cannot be treated as confirmed constant-regime samples. If later inference is authorised, the historical reassessment is a qualified prior/candidate source and must remain distinct from official confirmed labels. Further raw telemetry or an authoritative clarification could change this conclusion; the present audit does not prove physical status is inherently unknowable.

- [68-ID evidence table](../archive/data_before_release_20261016/reference/drogue_status_20261016/group2_source_audit.csv): original source hashes, current directory rows, deployment rows, historical automatic/manual dates and the per-ID disposition.
- [Group 2 summary](../archive/data_before_release_20261016/reference/drogue_status_20261016/group2_source_audit.json).

## Verification and evidence

The baseline inventory covers 63,439 existing scientific entries. The scope check found no changed or missing original entries. Content checks cover the 112 targeted baseline tracks and 11 authority/split/geometry files. Corrected hourly frames are identical to their originals in every column except `regime`. All 3,741 ID routes were checked; only the approved 44 select replacement tracks. Sixty R anchor ledgers were independently reproduced through the current reader. Test access remains locked by default.

The final verification receipt and source excerpts are retained under `provenance/runs/drogue_status_20261016/`. Failed reference fetches remain recorded; the directory HTML, deployment log and June 2013 archive were subsequently obtained successfully. The older April 2013 archive timed out and was not used. Only the authorised target rows are retained from cross-cohort reference tables.

| Official source | Role |
|---|---|
| [NOAA hourly product](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php) | v2.01.1 changes `location_type` only; other variables match v2.01 |
| [Original per-drifter NetCDF directory](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/hourly_product/v2.01/) | Per-ID native loss codes, definitions, IDs and counts |
| [Standard directory and legend](https://www.aoml.noaa.gov/phod/dac/dirall.html) | All 68 currently retain the unknown sensor-interpretation designation |
| [Deployment log](https://www.aoml.noaa.gov/phod/dac/deployed.html) | Identity and deployment context; not an attachment timeline |
| [2013 reassessment](https://www.aoml.noaa.gov/ftp/phod/lumpkin/droguedetect/2013_06_30_drogueoff.dat) | Historical candidate dates for the same 68 IDs |
| [Reassessment README](https://www.aoml.noaa.gov/ftp/phod/lumpkin/droguedetect/README.TXT) and [final notice](https://www.aoml.noaa.gov/ftp/phod/lumpkin/droguedetect/README_final.TXT) | Field definitions and priority of the standard metadata directory |
