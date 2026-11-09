# Total SST: official-reference comparison and missingness labels

Scope: total SST only, within data cleaning. No component reconstruction, native-error modification, model selection or fitting was performed. The current temperature view inherits `sst_anomaly_recovery_20261017_v2`; current source files, whole-ID pools and the Data Contract remain unchanged.

## Point-by-point comparison

All **2,633 remaining review points**, including **227 in R**, were rechecked against the retained actual official NOAA OISST v2.1 final source nodes. Source coordinates, UTC date, node values and nonnegative interpolation weights were checked, and every matched background was recomputed. `total_SST_point_comparisons.csv` contains every result; `comparison_readable.csv` is a compact human-readable table.

| Absolute difference from daily background, before this run's corrections | Records |
|---|---:|
| >5 to 10 K | 1,413 |
| >10 to 20 K | 983 |
| >20 K | 237 |

The total >10 K count is **1,220**. These are comparison bands, not universal NOAA error thresholds. A same-day daily background is not an exact measurement at the drifter's observation hour. OISST's noon coordinate denotes daily temporal support; the exact observation time and this distinction are recorded rather than relabelled as an hourly match.

### Additional evidence at the observation hour

The retained official GDP hourly observations were inspected for other instrument IDs at exactly the candidate timestamp within 50 km. Donors require native total-SST QC 5, finite total SST in [-2.05,40] C, and no post-last-good grounding context. Different instrument IDs are not guaranteed independent processing or error sources. The distance and complete selected donor records are preserved in `same_hour_official_neighbours.parquet`.

- 125 candidates have at least one such same-hour neighbour; 50 have at least two.
- 42 candidates have at least two neighbour IDs with total-temperature spread <=2 K, a median within 2 K of the daily background, and a target-to-neighbour difference >5 K.
- Eight candidates have an isolated native-total hourly spike between two QC4/5 adjacent hourly anchors: anchors agree within 2 K and each lies within 3 K of background, while the target differs by >5 K from both. This overlaps the neighbour-supported set by one point.
- The union is **49 points across 14 IDs, including 14 points in R**. None is after the official last-good time of a grounding ID.

The 49 working total-SST values were updated using the already approved source-count interpolation of actual OISST values. This is a sourced background reconstruction, not recovered instantaneous sensor truth. Original native `sst`, `sst1`, `sst2`, QC flags and native errors remain unchanged. All other earlier working temperatures were preserved exactly.

Example: ID 60350 at 2006-07-01 12:00 UTC has native total SST 1.514001 C. Four other IDs at the same hour within 50 km have median 28.534998 C and range 1.002991 K; the same-date OISST reconstruction is 27.785621 C. The working value now uses 27.785621 C while the original source value remains available.

**2,584 points remain compared but unresolved, including213 in R.** They are not unexamined, and they are not all proven errors. The daily-reference discrepancy alone is insufficient to erase real fronts, coastal gradients or diurnal variations. Two have post-last-good grounding context. Further source/context verification is needed before treating all of these as valid or replacing them all.

## Grounding is not identical to stopped transmission

Official `typedeath=1` describes the instrument's eventual termination cause. `end_date` is the last good date/time identified by DAC QC. Grounding may invalidate natural ocean-drift measurements while transmissions continue from a stationary location. Some instruments instead cease transmitting when they strand. Neither metadata field alone supplies the exact first-grounding hour, and a final grounding code must not be applied as an hourly state to the preceding ocean trajectory.

The current frozen files contain **16,059 records across 822 eventual-grounding IDs after their official last-good time**. Only **5,547** of those have missing working total SST. The other 10,512 have a finite working value; finiteness does not establish that they are valid floating-ocean temperature observations. The full context ledger is `post_last_good_grounding_context.parquet`. These are after-last-good context labels, not exact observed grounding-event labels. No grounding-tail records were deleted by this total-temperature instruction.

## Numeric NA and reason labels

The **5,547 missing working totals remain numeric NA**. The Parquet label table has 5,547 numeric nulls in a `double` field. Human-facing CSV uses the display token `NA`. No zero, -999 or literal text value was inserted into a numerical temperature column.

The current reader now gives these rows the existing `sst_reason` code:

```text
unavailable_after_last_good_on_grounding_ID
```

This identifies the reconstruction withholding context. It does not assert that grounding physically caused the sensor's missing reading, nor does it identify the grounding hour. Other missingness reasons are not overwritten, and known temperatures are not converted into missing values. Event context and a missing temperature are separate pieces of information.

Use `data3001.sst_sparse_current.read_sst_track` for the current total-temperature view and reason labels. `missing_total_SST_labels.csv` and `.parquet` contain all 5,547 affected keys. The original source columns and archived temperature sidecars retain their original meanings.

## Verification and present status

All 3,741 current source hashes and split assignments were preserved. All 49 replacements and all 5,547 missing-reason labels were verified through the actual current reader. The complete suite passed 161 tests. The source receipt states the matching rules, exact dependencies and limitations. No Git commit/push was performed.

Working total SST remains complete in R, but **temperature-quality cleaning is still open** for the compared-but-unresolved records. Component temperatures are outside this step and are not a blocker imposed on the total-SST work.

## Primary references

- [NOAA OISST](https://www.ncei.noaa.gov/products/optimum-interpolation-sst): daily gridded analysis and input observations.
- [NOAA GDP metadata definitions](https://erddap.aoml.noaa.gov/hdb/erddap/info/drifter_6h/index.html): eventual termination cause and last-good-time fields.
- [Lumpkin, Maximenko and Pazos 2012](https://journals.ametsoc.org/view/journals/atot/29/2/jtech-d-11-00100_1.xml): grounding and stopped-transmission categories are not interchangeable.
