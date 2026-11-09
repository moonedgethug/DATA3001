# Step 4 E1 v2 — Chronological Seasonal B2 Results

Date: 2 November 2026 (Australia/Sydney). **Engineering complete; scientific retention and stage closure await user review.**

The c=1 seasonal estimator did not achieve quality-preserving improvement at either horizon. Its nominal 90% regions are smaller, but Brier increases and actual hits decrease. This conclusion applies to the approved, unsmoothed seasonal estimator on this chronological development cohort; it does not establish that seasonal information is intrinsically unhelpful.

## Evidence and reproduction identity

- [Approved contract v2](seasonal_conditioning_s4_e1_contract.md), SHA256 `de652a290b454eb2073e4ac1d2ca4ed35ebb59729443c74f445507989f558aaf`; [execution approval](../provenance/reviews/seasonal_conditioning_s4_e1_v2_approval.json).
- Pilot: `seasonal_conditioning_s4_e1_pilot_20261102T004904_159217Z` — complete source/role verification; synthetic-target timing only, no actual validation scores.
- Primary: `seasonal_conditioning_s4_e1_primary_20261102T005104_943407Z` — [visual comparison](../results/deliverables/seasonal_conditioning_s4_e1/review.html), [sealed report](../results/runs/seasonal_conditioning_s4_e1_primary_20261102T005104_943407Z/REPORT.md).
- Replay: `seasonal_conditioning_s4_e1_replay_20261102T005135_081417Z` — 34 scientific artifacts agree within the contract's rules; all ten PNG figures are byte-identical.
- [Final audit and resource record](../provenance/reviews/seasonal_conditioning_s4_e1_v2_audit.json), [synthetic semantic tests](../provenance/reviews/seasonal_conditioning_s4_e1_v2_tests.txt), [fault-injection checks](../provenance/reviews/seasonal_conditioning_s4_e1_v2_fault_checks.json).

## Frozen design and populations

Both models fit raw qualified 2012–2019 pairs. Training labels requiring observations at or after 2020 are removed first; all IDs in the union of 7/30-day 2020–2022 validation cohorts are then excluded from both fits. Annual B2 pools these training seasons. Seasonal B2 uses only the matching UTC departure season, with c=1 and annual fallback only for an absent seasonal row.

| Cohort | 7 days | 30 days |
|---|---:|---:|
| Final training pairs / IDs / origins | 130,731 / 159 / 37 | 113,708 / 138 / 37 |
| Validation pairs / IDs / origins | 33,971 / 45 / 36 | 30,128 / 42 / 35 |
| Training label-boundary exclusions | 630 | 1,921 |
| Additional training ID-overlap exclusions | 2,947 | 1,656 |

All validation origins have annual training support. Evaluation averages eligible times within ID/origin, then IDs within origin, then origins equally. One ID does not get an additional full vote in each season. The 517 final-test IDs remain locked; no canonical trajectory was read. Available 2022 data do not cover a complete calendar year.

## Matched results

| Horizon | Model | Brier | Mean K90 cells | Actual H90 |
|---|---|---:|---:|---:|
| 7 days | Annual B2 | 0.996224 | 16.305556 | 72.5968% |
| 7 days | Seasonal B2, c=1 | 1.055179 | 10.864406 | 50.3417% |
| 30 days | Annual B2 | 1.017031 | 42.828571 | 38.8102% |
| 30 days | Seasonal B2, c=1 | 1.099687 | 16.819744 | 14.8399% |

| Seasonal minus annual | 7 days | 30 days |
|---|---:|---:|
| Delta Brier | +0.058955 (+5.92%) | +0.082656 (+8.13%) |
| Delta K90 | -5.441150 (-33.37%) | -26.008828 (-60.73%) |
| Delta H90 | -22.2551 percentage points | -23.9703 percentage points |
| Quality-preserving point improvement | No | No |
| Conditionally supported quality-preserving improvement | No | No |

Standard Brier has range 0–2; values above one are possible and are not percentages or a probability-normalisation failure. Mean issued region mass remains above 90% for all four results (about 90.85–92.03%). Small K90 therefore reflects greater concentration of the fitted distribution, while H90 shows substantial undercoverage on validation.

### Paired uncertainty

10,000 shared Exp(1) multipliers over the sorted 45-ID validation union; PCG64 seed 20261102. Fits are held fixed. Original times are averaged within ID/origin, multipliers normalised within origin, and origins remain equal. The predeclared six directional screens and ordinary intervals are in [uncertainty.csv](../results/runs/seasonal_conditioning_s4_e1_primary_20261102T005104_943407Z/uncertainty.csv).

| Contrast | Conditional 95% interval, 7 days | Conditional 95% interval, 30 days |
|---|---:|---:|
| Delta Brier | [+0.041196, +0.075484] | [+0.069053, +0.095611] |
| Delta H90, percentage points | [-27.4090, -17.7339] | [-27.7194, -20.0889] |
| Delta K90, cells | [-5.982041, -4.937006] | [-26.942531, -25.181188] |

The adverse Brier/hit directions are not a borderline point-estimate result under these conditional intervals. These intervals omit training/refitting uncertainty, shared ocean forcing and prior development adaptation; they are not independent final-test or physical-causality evidence.

## Fallback and information support

| Seasonal fallback | 7 days | 30 days |
|---|---:|---:|
| Cases | 41 | 0 |
| Raw pair fraction | 0.1207% | 0% |
| Primary evaluation weight | 2.7778% | 0% |
| Distinct IDs / origins | 1 / 1 | 0 / 0 |

All 41 cases occur in origin 44742 during JJA. Annual and seasonal forecasts and all three case scores are identical there; they remain in the main evaluation. Missing-season rows visible in other illustrative maps are not necessarily visited by validation cases, explaining why a map may show fallback while the 30-day evaluation fallback count is zero.

The evaluation-weighted fraction of real endpoints receiving **zero** predicted probability increases from 8.04% to 29.46% at 7 days and from 44.76% to 76.50% at 30 days. The four descriptive seasonal slices each show higher Brier for c=1 than annual B2. These are diagnostics, not additional selected models or confirmatory subgroup tests.

The observed pattern is consistent with narrower, sparse empirical seasonal support excluding useful possibilities. Seasonal training rows have a median 13 / 11 contributing IDs across the 148 observed-origin/season combinations at 7 / 30 days, including empty rows. Support fragmentation is a plausible explanation, not a proven decomposition of sampling variability versus real temporal change.

Annual B2 itself has poor 30-day actual coverage on this forward validation cohort. The comparison does not certify annual B2 as adequate, prove decade-scale drift, or isolate year effects from changes in deployments and within-cell departure conditions. Older pooled-ID CV numbers use different training/validation populations and must not be treated as matched controls.

## Engineering review and resources

| Stage | Measured process completion time | Conservative budget charge |
|---|---:|---:|
| Complete-roster pilot | 66.57 s | 77 s |
| Primary | 11.29 s | 22 s |
| Fresh replay | 11.75 s | 22 s |
| Total | 89.61 s | 121 s |

Charges include an explicit closeout reserve and remain below the 2,400-second total cap. Peak process RSS was 0.85 GiB versus the 8 GiB cap. The pilot projected 137.25 seconds per complete run including a 2x reserve. Its synthetic targets create many distinct audit groups, so the conservative pilot audit is slower than the actual-data primary audit.

Seven synthetic semantic tests passed, including hand-computable weights/probabilities, seasonal/label boundaries, cross-horizon ID exclusion, region ties/E, annual fallback, paired multipliers and repeatable figures. Additional fault checks reject changed code/config, incomplete pilot receipts and altered replay scores, IDs and images. Original-key roles, Counter-based counts, squared-error Brier, regions, weights, uncertainty and acceptance were independently reconstructed. All 195 sealed files across the three runs were checksum-verified; historical implementation files and the execution fingerprint remain unchanged. All ten figures and local report links were inspected.

## Review conclusion

The implementation and experiment are complete. Neither horizon meets the prescribed improvement criterion, so this run does not support replacing annual B2 with raw c=1 seasonal B2. It also does not justify automatic SST development under the existing positive-signal gate. Further smoothing, feature work, model retention or stage closure remain separate user decisions. No additional model search, later-stage development, Git publication or final-test access was performed.
