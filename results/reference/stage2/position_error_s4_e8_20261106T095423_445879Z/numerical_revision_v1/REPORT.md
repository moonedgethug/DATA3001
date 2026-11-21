# Step 4 E8 v2 — Endpoint position uncertainty

Status: practically tiny effect; no useful improvement demonstrated.

EndpointCI minus ExactPoint: ES -0.024109 metres (paired 95% interval -0.096115 to +0.042850); actual H90 +0.002881 percentage points; mean area +0.018188%. The predeclared minimum useful ES reduction was 0.1%; the observed relative reduction is +0.000018%. The estimated numerical standard error of this ES contrast is 0.036090 metres. The displayed ES change is not resolved beyond numerical sampling uncertainty. The reported regions use corrected exact 90% cumulative-probability arithmetic. Earlier region results are preserved as superseded; all Energy Scores, model distributions, donors, weights and random streams are unchanged.

The added location-error clouds did not establish a practically useful improvement. Preserve the point estimator; do not increase error widths to search for a win. A small or unresolved effect does not prove that measurement uncertainty is irrelevant.

## Complete matched result

All 33,971 seven-day cases from 45 validation IDs are retained. Training is 2001–2019; validation is the previously used 2020–2022 development period. Evaluation gives equal weight to each drifter after averaging its times. See [summary.csv](summary.csv), [paired intervals](contrasts.csv), and [visual review](review.html).

| Model | Energy Score (km) | Actual H90 (%) | Mean area (km²) | Auxiliary loss | H90 minus nominal (pp) |
| --- | --- | --- | --- | --- | --- |
| EndpointCI | 134.219187 | 91.395013 | 215,706.114512 | 7.222626 | 1.395013 |
| ExactPoint | 134.219212 | 91.392133 | 215,666.889355 | 7.222626 | 1.392133 |
| MatchedSpread | 134.219151 | 91.395013 | 215,705.102906 | 7.222625 | 1.395013 |
| B2Point | 144.003238 | 88.424628 | 212,639.990708 | 8.171167 | -1.575372 |

## Scientific interpretation

This is a fixed-lag Markov kernel over exact positions. EndpointCI adds only verified historical endpoint location uncertainty, preserving all original votes. ExactPoint is the main reference; MatchedSpread separates generic spreading from record-specific width allocation; B2Point is a historical anchor rescored in the same continuous space. No origin errors or validation endpoint errors enter prediction or scoring.

Energy Score uses Euclidean WGS84 ECEF chord distances in kilometres. The auxiliary loss is ES/100 + squared mean error/10000. The common 90% region is a distribution-quantile ellipse in WGS84 LAEA, with continuous area and exact-point hits. It is not an HDR. 0.5-degree cells are display only.

## Fallback and numerical evidence

Training endpoint-error fallback: 15,816/265,393 pairs (5.959462%). Actual forecast-weighted fallback: 6.212692%. All original votes are retained; no complete-case-only analysis, land rejection or renormalization was performed. See [fallback_summary.json](fallback_summary.json), [period/source coverage](formal/training_error_availability.csv), [year strata](year_strata.csv), and [availability strata](availability_strata.csv).

Independent region replay covers all 33,971 cases; independent Energy Score checks cover 128 fixed queries. The numerical audit status is True. Pilot: 163.7 s over 4 preserved attempts plus a nonzero-rho diagnostic covariance correction. Formal: 3407.7 s. Independent audit: 1122.8 s. Peak observed process RSS: 0.88 GiB.

The corrected error amplitudes characterize observation-location uncertainty, not transport uncertainty. The normal working kernel is not an identified posterior or deconvolution. A negligible effect is not proof that uncertainty is universally irrelevant. No model replacement or Step 5 transition is made.

## Provenance

Run: position_error_s4_e8_20261106T095423_445879Z/numerical_revision_v1

Contract: 55c4c96b807421ea0647aa06029db91208901da9d4d1ab5db20ce5a6cd6a3e19

Repair overlay: cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3

Frozen forecasts precede outer endpoint scoring. Protected canonical data, approved contract, ledger, repair outputs and E7 inputs remain unchanged. The final-test pool and outer endpoint errors remain unread. Figures reuse the six E7 example keys. All earlier pilot attempts are preserved.
