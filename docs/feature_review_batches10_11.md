# Feature review: deployment context and lifecycle metadata

## Current decision and scope

The user approved excluding group 10 from the current prediction-input set after
considering any research or quality-control value. All 15 group-10 stored
columns are now on the existing `exclude_current_core` list. This adds 15
entries, taking the registry total from 57 to 72. No source field was deleted,
renamed, imputed or recoded. The prior group-09/10 report remains the historical
audit before this approval; this document records the subsequent decision.

`DeploymentStatus` remains useful as deployment-quality evidence. Its four
development `failed on deployment` cases still require source interpretation
before any proposed row exclusion. Core input exclusion does not authorize
dropping their trajectories. Blank or semantically unresolved funding,
upgrade, transmission and comments metadata remain unchanged.

The final Excel Data Contract v1.0 remains authoritative, with SHA-256
`6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
The active data remain `per-drifter-cleaned-20261017-v6`: 3,741 IDs,
39,099,193 rows and 129 columns. Group 11 retention is now agreed; selection of next-stage inputs remains
pending. Its audited role recommendations do not mean every field is a
release-time predictor. This review does not begin modelling.

## Group 11: all ten fields

Counts below use 3,224 development IDs and the 396 R-visiting development IDs.
These are ID-level metadata repeated hourly, not independent hourly features.

| Field | Meaning | Missing development IDs (R visitors) | Proposed role and handling |
|---|---|---:|---|
| `deploy_date` | Original operator-reported deployment time. | 36 (4) | Provenance; exclude from ordinary core predictors. Do not replace an unknown deployment time with first QC time or first hourly time. |
| `deploy_lat` | Operator-reported deployment latitude. | 1 (0) | Provenance. Do not invent the actual release coordinate by copying the first retained position. |
| `deploy_lon` | Operator-reported deployment longitude. | 1 (0) | Provenance; same principle as deployment latitude. |
| `start_date` | First good observational time identified by DAC quality control. | 0 (0) | Lifecycle/QC reference. It need not equal the first estimated hourly time or the selected model origin. No imputation needed. |
| `start_lat` | Latitude of the first good observational position in the `start_*` family. | 0 (0) | Lifecycle/QC reference. Its native long-name attribute says 'Last good latitude'; this inconsistency is documented, not silently edited. |
| `start_lon` | Longitude of the first good observational position. | 0 (0) | Lifecycle/QC reference. No imputation needed. |
| `end_date` | Last-good observational time in the lifecycle metadata. | 163 (11) | Essential cleanup/censoring evidence. It is retrospective, not an origin-time predictor or a verified first grounding/pickup timestamp. No invented future end. |
| `end_lat` | Last-good observational latitude. | 163 (11) | Retrospective source/event evidence. Never substitute it for an observed fixed-horizon destination. |
| `end_lon` | Last-good observational longitude. | 163 (11) | Same role as end latitude. |
| `typedeath` | Eventual termination classification at the metadata snapshot. | 0 (0) | Essential source/fate interpretation and existing cleanup control. Do not supply eventual fate to a predictor at an earlier origin. |

The deployment-coordinate nulls occur in the same ID; 35 additional development
IDs have a missing deployment time but recorded coordinates. All 163 missing
end-time cases also lack end coordinates and have `typedeath=0`, meaning still
alive in that metadata snapshot. These are not evidence of a zero-length track
or proof that an unobserved future location can be reconstructed.

No development coordinate is outside its latitude/longitude range, no populated
date is nonpositive, no development first-QC date is after a populated last-QC
date, and all development termination codes are in the documented range 0–6.
Those validity checks do not establish perfect positional or event-time accuracy.

## Distinguish deployment, QC start and the forecast origin

An instrument might be deployed on 1 June, first obtain a QC-accepted position
on 2 June and provide a chosen R origin on 10 July. The forecast origin uses the
hourly `time`, `lat` and `lon` at that 10 July observation. Neither `deploy_*`
nor `start_*` replaces those existing origin fields.

NOAA explicitly distinguishes operator deployment coordinates, first-good QC
coordinates and the first estimated hourly record. In the current development
data, the first retained hourly time differs from `start_date` for 3,178 IDs.
That difference alone is not a missing-value error or authorization to overwrite
the source metadata. Missing deployment metadata likewise does not invalidate
an otherwise qualified observed origin/endpoint pair.

## Termination evidence and unavailable future information

| `typedeath` code | Native documented meaning | Development IDs |
|---:|---|---:|
| 0 | Buoy still alive | 163 |
| 1 | Ran aground | 796 |
| 2 | Picked up by vessel | 135 |
| 3 | Stopped transmitting | 2,091 |
| 4 | Sporadic transmissions | 1 |
| 5 | Bad batteries | 0 |
| 6 | Inactive status | 38 |

`typedeath=1` describes eventual grounding; it does not mean the instrument was
grounded throughout its earlier trajectory. Likewise, stopped transmissions,
battery problems and an administrative snapshot do not establish beaching or
a physical absorbing location. Existing endpoint and path qualification rules
remain separate.

The last retained hourly observation in the corpus is
2022-10-31 00:00 UTC. Nevertheless, 118 development IDs, including 11 R visitors,
have finite `end_date` metadata beyond that global observed-hourly cutoff
(137 IDs across the entire corpus). A later date in lifecycle metadata does not
supply missing hourly observations or support an observed one-year destination.
Eligibility must continue to use actual available, qualified trajectory data.

Passing `end_lat`, `end_lon`, future `end_date` or eventual `typedeath` as origin
predictors would disclose information about the future outcome. They should be
excluded from the predictor matrix while remaining available to explicitly
defined source, cleanup, censoring and outcome-audit procedures. No exact
physical event hour is inferred from a last-good timestamp. No current contract
target, split, eligibility rule or horizon is changed by this recommendation.

## Verification of existing cleanup rules

The read-only scan checked the ten lifecycle columns on every retained row and
confirmed that each is constant within its ID. It also checked the existing
time/SST cleanup boundaries without changing them:

- No vessel-recovery ID has retained hours strictly after its valid official
  last-good cutoff. The previous conservative recovery-tail deletion remains
  effective; the cutoff is not relabelled as an exact observed pickup time.
- For eventual-grounding IDs, all 16,059 corpus hours strictly beyond their
  valid last-good bound retain unavailable `sst`, including 47 R hours. No
  finite SST remains under that existing exclusion rule.
- Position/time records retained for event audits are not automatically
  approved as freely drifting training examples. Eventual grounding and the
  last-good bound alone do not establish a first physical beaching time.

The audit used final-test metadata only for authorized preprocessing consistency
checks. No model predictions, fixed-horizon outcome labels, model scores or
test-guided parameter selection were used. All data-file sizes and modification
times, plus manifest/schema/contract hashes, remain unchanged. No active data
feature column was created or removed.

## Evidence

- [Current feature decision registry](../configs/feature_review.csv).
- [Full field profile and cross-checks](../results/runs/feature_review_batch11_20261017_v1/profile.json).
- [Per-ID evidence](../results/runs/feature_review_batch11_20261017_v1/per_ID_metadata.csv)
  and [replayable read-only audit](../results/runs/feature_review_batch11_20261017_v1/audit.py).
- [Registry change verification](../results/runs/feature_review_batch11_20261017_v1/registry_update.json).
- Native definitions and termination-code comments in the frozen
  [dataset schema](../configs/dataset_schema.json).
- [NOAA hourly-product documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php),
  especially the v2.01 release notes defining `start_*` versus `deploy_*`.


## Follow-up: retention and recovery feasibility

The user approved retaining all ten lifecycle fields for selective next-stage
use. At that retention checkpoint, active imputation had not been requested; the later authorized source-recovery execution is recorded below. Every group-11 registry
entry now records agreed retention with downstream input selection pending.
No group-11 entry has been added to the predictor drop list.

A fresh official deployment-log snapshot was obtained and frozen alongside a
URL, retrieval timestamp, response size and SHA-256 receipt. The entire corpus
has 44 missing deployment dates: 36 development IDs and eight final-test IDs.
Thirty have unique exact-ID log matches; fourteen long-form IDs have no exact
match in this inspected log. No suffix-based identity mapping was accepted.

For the 30 exact candidates, all experiment numbers agree, and all recorded
native deployment coordinates agree with the degree/minute log coordinates
within their combined rounding precision. Twenty-five also have matching
positive WMO numbers. These are identity checks, not certification of the date.

All 30 log dates are later than the current first-QC dates; 26 are later than
the first retained hourly observation. The log contains calendar dates without
a time of day. Midnight representations in the evidence are only comparison
helpers, not precise observed deployment timestamps. The remaining four cases
that do not follow the first retained hour still need source/precision and
identity interpretation; they are not declared false merely by this check.

The four affected R-visiting development IDs illustrate the unresolved dates:

| ID | First QC date | Deployment-log date |
|---|---|---|
| 122609 | 2013-05-06 | 2013-05-13 |
| 122603 | 2013-05-22 | 2013-05-23 |
| 135914 | 2014-02-01 | 2014-02-03 |
| 114790 | 2014-08-16 | 2014-08-18 |

The exact reason for the missing product dates or these source differences is
not established. Reporting mistakes, source revisions, date conventions or
early onboard/processed positions remain hypotheses. No candidate was written.
An applicable original deployment sheet, cruise report, corrected official
record or product-processing explanation would be needed to resolve them.

The sole missing deployment-coordinate pair belongs to ID 300534061551860,
which has no exact-ID match in the inspected log. Its first QC coordinates do
not prove the physical deployment location; no substitution was made.

All 190 missing end triplets in the full corpus (163 development IDs) accompany
source `typedeath=0`. They represent unavailable termination information at the
frozen metadata snapshot. They are not filled using the last retained hourly
position or a guessed failure date. A later official termination record would
be a versioned lifecycle update, not evidence that an unobserved hourly target
was present in the original snapshot.

Cross-feature checks can corroborate identity, dates, coordinate units, source
precision and current termination evidence. Manufacturer/model, funding,
programme, ship identity, temperature, velocity and drogue state do not uniquely
determine another instrument's actual deployment or termination event. No
mean/nearest-neighbour/backtracking estimate is approved as an observed event.
No active feature column was added, dropped or changed by this follow-up.

See [the source candidates and identity/chronology checks](../results/runs/feature_review_batch11_20261017_v1/deployment_source_candidates.json)
and [NOAA's deployment log](https://www.aoml.noaa.gov/phod/dac/deployed.html).


## Completed official-source recovery

**Result: zero accepted fills. All existing numeric missing values remain
unchanged.** The missing scope comprises 227 distinct IDs and 616 ID/field cases.
The active release is still v6, with 3,741 IDs, 39,099,193 rows and 129 columns.
No active data file, feature, finite value, row order or split assignment changed.

| Field | IDs retaining missing values, entire corpus | Decision |
|---|---:|---|
| `deploy_date` | 44 (36 development, eight test) | All 44 original NOAA hourly NetCDF files declare the value missing. Thirty exact-ID log candidates retain unresolved date discrepancies; fourteen have no exact-ID log match in the inspected snapshot. |
| `deploy_lat` | 1 | The same official original file also declares deployment latitude missing. First QC latitude is a different event. |
| `deploy_lon` | 1 | Same case and distinction as deployment latitude. |
| `end_date` | 190 (163 development, 27 test) | All have original snapshot `typedeath=0`; no termination is fabricated. |
| `end_lat` | 190 | Same 190 unfinished lifecycle records. |
| `end_lon` | 190 | Same 190 unfinished lifecycle records. |

The original files were retrieved from NOAA's published v2.01 hourly directory.
All 44 variable IDs and global ID attributes matched the intended ID exactly;
WMO and experiment metadata also matched. Source `_FillValue` / `missing_value`
attributes explicitly identify the missing native codes (including -999999).
These codes are not physical coordinates or times. Existing cloud-product
missing values are consequently not evidence of accidental local cleaning loss.
All 616 scoped cases also match the retained official acquisition metadata,
including the 190 unfinished end triplets. The v2.01 original files and the
v2.01.1 cloud asset are identified separately; their checked lifecycle values
agree after the cloud product's documented numeric representation. No metadata
from a later lifecycle version was silently substituted.

This does not prove which source is responsible for every date discrepancy.
The 30 calendar-date log candidates remain source evidence rather than restored
event timestamps. No unpublished record or unverified identifier mapping is
presumed. Source retrieval failures were recorded; all 44 required original
files were eventually retrieved and verified after bounded retries.

The accepted change set is empty. Therefore no physical data rewrite, new data
release or arbitrary normalization pass was performed. Existing numeric NaN
and Arrow null are retained as missing values; neither a literal string `NA`
nor a physical zero was inserted. The later training pipeline must handle their
missingness explicitly without pretending an unobserved event has been measured.
No helper feature column was added.

The final replay checked every one of the 3,741 current data-file hashes against
the unchanged manifest. The scientific contract, schema, hourly SST, cleaned
drogue state, rows and whole-ID pools remain unchanged. This recovery audit does
not evaluate prediction accuracy or certify model readiness beyond its scope.

[Per-ID results](../provenance/runs/lifecycle_source_recovery_20261017_v1/per_ID_audit.csv)
· [all 616 field decisions](../provenance/runs/lifecycle_source_recovery_20261017_v1/per_field_audit.csv)
· [raw official metadata evidence](../provenance/runs/lifecycle_source_recovery_20261017_v1/original_NetCDF_evidence.json)
· [summary](../provenance/runs/lifecycle_source_recovery_20261017_v1/summary.json)
· [replayable audit](../provenance/runs/lifecycle_source_recovery_20261017_v1/audit.py).
Original source bytes and URL/time/SHA-256 receipts are stored beside the audit,
outside active data. [NOAA hourly dataset documentation](https://www.aoml.noaa.gov/phod/gdp/hourly_data.php)
provides product access and release notes.
