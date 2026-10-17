# Total SST after the grounding-related validity bound

**Completed and verified.** Active release: `per-drifter-cleaned-20261017-v4`.
The user's approved rule is physically applied in the existing **`sst`** column
in both `data/train/` and `data/test/`. No feature column has been added.

## Exact rule

Set `sst` to numeric NA when all of the following hold:

- `typedeath == 1`: official eventual termination is running aground.
- `time` and `end_date` are finite, and `end_date > 0`.
- `time > end_date`: strictly after the official last-good timestamp.

Keep the cleaned SST at and before the bound. Do not refill the excluded
interval. A missing or invalid cutoff and a different termination type do not
trigger this rule. The bound is not asserted to be an observed first-grounding
hour; low speed alone has not been used to classify grounding.

## Verified effects

| Item | Result |
|---|---:|
| ID files containing changed SST values | 822 |
| Finite SST values newly set to NA | 10,512 |
| Previously existing SST NA values | 5,547 |
| Total SST NA after the rule | 16,059 |
| Total SST NA inside R | 47 |
| Retained IDs | 3,741, unchanged |
| Retained hourly records | 39,099,193, unchanged |
| Columns per file | 130, unchanged |
| Train / final-test IDs | 3,224 / 517, unchanged |
| Regression tests | 166 passed |

All selected SST values are numeric nulls, never a text sentinel or zero.
Every SST outside the rule is unchanged. All other 129 columns, their values,
types and missingness, every record key/order, all schema metadata and all
train/test assignments remain unchanged. The other 2,919 files are byte-identical
to the preceding release. Components and native temperature errors/flags were
not edited. Previously removed vessel-recovery tails remain absent.

No SST NA remains outside this excluded context. This is a completeness statement,
not a temperature-quality or prediction-accuracy result. The historical audit's
2,584 unresolved temperature comparisons include two now covered by this cutoff;
2,582 remain active unresolved temperature comparisons, including 213 in R.
These two exclusions are not newly validated temperature repairs.

Positions and timestamps remain available for event audits. Their retention
does not approve these tail observations as free-drift training samples or
establish the exact beaching time. The Data Contract and research targets are
unchanged; no model has been fitted by this task.

## Evidence

- `verification.json`: independent full-cohort checks, selected NA counts and preservation assertions.
- `changes.parquet`: exactly the 10,512 changed keys, previous SST values and rule reason. This ledger is outside active data.
- `receipt.json`: preceding manifest, original-file hashes and changed-file backups.
- `tests.txt`: the complete passing test output.
- `quality_review_context.json`: the two historical review points removed from active SST use by this rule.
- `archive/grounding_sst_na_20261017_v1/`: originals of affected files and preceding configurations/guides.

The current README, data guide, schema and SST feature-review entry describe
this policy. Historical SST runs and their original receipts remain unchanged.
No Git commit or push was performed.
