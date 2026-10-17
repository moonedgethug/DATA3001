# Official drogue time and end-marker audit — 16 October 2026

Storage update: these original correction contributions and source receipts are retained in the archive. Their approved labels and evidence are consolidated in the [current per-ID release](data_layout.md); do not apply the overlays twice.

## Outcome

The approved 3,137-ID boundary cohort was audited. **3,128 previously unknown boundary hours now have source-backed retrospective labels; nine remain unresolved.** The correction also fixes other hours affected by the same date interpretation. It does not estimate drogue status from velocity, change positions, or establish forecast accuracy.

| Disposition | IDs | Treatment |
|---|---:|---|
| Documented nominal loss time, with unchanged loss calendar day | 2,008 | Use the official recorded minute: drogued before that time; undrogued at or after it |
| Official loss field equals the precise end field | 1,120 | Interpret as attached at the end; do not create a loss event |
| Loss calendar day differs between source snapshots | 8 | Retain the frozen record and its unknown boundary label; store the newer date as a candidate requiring reconciliation |
| Exact ID absent from the retrieved precise directories | 1 | Retain the frozen record and its unknown boundary label |

These are metadata-based historical annotations. A recorded minute is **not** proof that physical drogue loss was observed with minute accuracy. The precise source is an auxiliary reference snapshot, not a replacement trajectory release.

## Evidence and acceptance rule

All 3,137 frozen cases have exactly one unknown hour at the local positive loss value. All those values are UTC midnight. Their source flags are 3,083 undrogued and 54 drogued. A source flag alone was not accepted as an independent sensor observation.

The four NOAA `dirfl` directories contain **3,136 exact integer-ID matches**. All matched rows also agree with the frozen WMO number and first-good-record calendar day. Of these, 3,128 retain the frozen loss calendar day. Only these unchanged-day cases were accepted for deterministic refinement. The later standard directory has 1,968 exact matches; all its loss calendar days agree with the precise directory rows. It does not cover all long-form IDs by exact ID, so missing matches were not guessed from aliases.

Fourteen original v2.01 hourly NetCDF files were additionally retrieved, covering all nine unresolved cases, the changed end-marker interpretation for ID 75186, and four examples. Their native loss fields remain consistent with the coarse frozen values. Thus, the eight changed-day cases are real cross-source/version discrepancies; they are not silently treated as rounding corrections. The unmatched ID is 300534067902500. Its original hourly file exists, but supplies no finer loss time that resolves its boundary.

The NOAA standard-directory legend explicitly distinguishes unknown sensor interpretation, off-since-deployment, attached-at-end and attached-while-alive conventions. In particular, equality with the ending time denotes attachment at the end. It does **not** mean the instrument became undrogued immediately afterward.

The previous half-float32-ULP guard remains the fallback outside this audited scope. Within the accepted cases, a documented nominal minute or an end-marker interpretation replaces that guard. Fourteen retrieved float64 originals still use midnight loss values: the uncertainty cannot be explained solely as float32 conversion error.

## Exact changes and unresolved coverage

Only derived `regime` annotations change. All native fields, including source `drogue_status`, loss metadata, observation keys, timestamps, positions, velocity, depth, QC flags and missing values remain unchanged.

| Transition in derived annotation | Hourly records |
|---|---:|
| Unknown → drogued | 2,945 |
| Unknown → undrogued | 183 |
| Undrogued → drogued after official time/marker refinement | 33,830 |
| Undrogued → unknown beyond proven attached-end coverage | 683 |
| Total revised annotations | **37,641** |

Attachment evidence ends at the earlier of the precise official ending time and the last retained hour. It is not extended to later hourly estimates. Consequently, 683 retained tail hours have unknown status. These occur in 44 boundary-cohort IDs; **they are different IDs from the earlier 44-ID official-fill restoration**. No positions or path hours were fabricated.

The original unknown boundary is restored in every accepted case. Nine original boundary hours remain unknown. The 68 zero-code IDs from the preceding audit retain all 495,555 unknown hours. Across the entire retained corpus, after both official corrections:

| Historical annotation | Hourly records |
|---|---:|
| Drogued | 19,268,207 |
| Undrogued | 19,342,607 |
| Unknown | 496,247 |
| Retained total | **39,107,061** |

The unknown total is 495,555 zero-code hours + nine unresolved boundary hours + 683 unproven tail hours. No drifter or observation was dropped. Some drifters occur in more than one state, so counts of IDs with each state must not be summed as mutually exclusive groups.

## Retained correction evidence and current use

The correction version is `official-drogue-boundary-v1`, composed with `official-drogue-attached-44-v1`. Both are incorporated in `per-drifter-20261016-v1`. Frozen preparation and the original sparse overlays remain intact as evidence:

- [Per-ID decision and source table](../archive/data_before_release_20261016/reference/drogue_boundary_20261016/per_ID_audit.csv).
- [Evidence manifest](../archive/data_before_release_20261016/reference/drogue_boundary_20261016/manifest.json).
- [Current per-ID label census](../archive/data_before_release_20261016/reference/drogue_boundary_20261016/current_label_census.csv).
- Development annotations: `archive/data_before_release_20261016/processed/drogue_boundary_v1/regime_overlay.parquet`.
- Locked-test annotations: `archive/data_before_release_20261016/restricted_test/drogue_boundary_v1/regime_overlay.parquet`.

Use `data3001.dataset.read_track(id)` for the complete current frame, or `prep_pairs.load_track(source, id)` for analytical arrays and freshly derived event bounds. `drogue_boundary.read_prepared_track(id, historical_split, allow_test=False)` also routes to the canonical file. In this release, `prepared_track_path` returns the consolidated physical file, with the approved labels already included. The release manifest pins its hash; the embedded evidence retains the provenance-qualified interval rule. The old baseline-plus-overlay route remains only as a fallback for historical fixtures.

The interval rule uses the same refined time or bounded attachment interpretation as the hourly labels. Fixed-regime intervals crossing a genuine recorded loss remain excluded. Endpoint and stopped-process targets stay separate; missing paths, uncertain mapping, termination, observed exit and pooled analysis retain their previous rules. Retrospective loss information is not a forecast-time feature. Test preparation was technically audited under this authorisation; development entry points still deny test access.

**Frozen global support tables and old materialised ledgers are historical.** They were not overwritten and must not be mixed with these annotations as though they were current. On-demand generation uses the corrected rules. The current [R anchor eligibility deltas](../archive/data_before_release_20261016/reference/drogue_boundary_20261016/R_anchor_eligibility_delta.csv) cover all 393 corrected R-visiting IDs at 7/30/90/180/365 days, preserving split and target. They are scoped contributions, not full-cohort totals. To rebuild totals, replace the old per-ID contributions, also retaining the separate earlier 44-ID correction.

For these 393 IDs, the 365-day drogued endpoint count increases by 53 and the stopped count by 14. This modest increase does not resolve annual/seasonal support limitations or establish prediction accuracy. The [365-day cell-season support file](../archive/data_before_release_20261016/reference/drogue_boundary_20261016/R_365d_drogued_support.csv) is likewise scoped to these corrected IDs. DEPTH-01 remains pending.

## Verification

All 3,128 accepted per-ID overlays were independently reproduced by reparsing the retained official rows. The audit found **63,815 existing scientific file entries unchanged**, and 123 protected source/contract/split/geometry hashes unchanged. All 3,741 routes were checked: 3,128 use the boundary overlay, 44 use the preceding official-fill replacement, and 569 retain baseline routing. Full-column invariance was checked on 12 real examples, including held cases. Pooled R anchor outputs were unchanged at every checked horizon. The regression suite passes **77 tests**.

Source excerpts, fetch hashes, native-file metadata extracts, executable audit steps and verification receipts are under `provenance/runs/drogue_boundary_20261016/`. The complete native-file receipt is `original_conflict_audit_v2.json`; the explicitly incomplete earlier extract is not used. No model was trained or evaluated.

## Primary references

- [NOAA hourly product and v2.01.1 release notes](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php): v2.01.1 changes location type only; v2.01 originals are applicable to the audited loss metadata.
- [NOAA standard directory and status legend](https://www.aoml.noaa.gov/phod/dac/dirall.html).
- NOAA precise QC metadata: [IDs 1–5000](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/dirfl_1_5000.dat), [5001–10000](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/dirfl_5001_10000.dat), [10001–15000](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/dirfl_10001_15000.dat), [15001 onward](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/dirfl_15001_current.dat). Retained receipts include response dates and last-modified headers.
- [Original hourly NetCDF files](https://www.aoml.noaa.gov/ftp/pub/phod/buoydata/hourly_product/v2.01/).
- [CloudDrift GDP adapter source](https://clouddrift.org/_modules/clouddrift/adapters/gdp.html): documents a derived-flag implementation; it is not independent physical confirmation or a verified build commit for the frozen asset.
