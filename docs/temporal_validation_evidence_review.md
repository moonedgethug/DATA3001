# Temporal training windows and Markov validation: evidence review

Date: 3 November 2026 (Australia/Sydney).

Status: preliminary literature and existing-data review for discussion. This note does not amend the approved S4 E1 contract, select a new date cutoff, authorise training, or close a research stage. No model was fitted or rerun for this review. The protected research ledger and sealed runs are unchanged.

## 1. Question and current judgement

The task is to predict a stopped 7- or 30-day destination distribution from an arbitrary qualified time inside the release region. Three separate choices must be distinguished:

1. Which observations are scientifically eligible?
2. Which historical years provide useful training information?
3. Which validation design represents the intended use of the forecast?

Preliminary judgement: retain the existing eligible historical data. The sources reviewed provide evidence of Gulf Stream variability and some longer-term changes, but do not establish a 2012 breakpoint in this project's cell-conditioned destination distributions. A chronological validation boundary does not require discarding all earlier training years. Whole-ID historical validation and forward validation answer different questions; neither the Markov property nor the label "time series" resolves their choice by itself.

## 2. Relevant geography and external evidence

The verified release polygon has bounds 81–73 degrees W and 30–35.5 degrees N; the polygon is not its rectangular bounding box. The stopped transport domain extends farther downstream, to 8 degrees W and 55 degrees N. Sources: [release geometry](../archive/data_before_release_20261016/reference/acquisition/geometry/release_R.geojson), [transport geometry](../archive/data_before_release_20261016/reference/preparation_v1/geometry/transport_D.geojson). Downstream evidence can be relevant to endpoints without directly describing changes in the release cells.

| Primary source | Result relevant to the question | Implication and boundary for this project |
|---|---|---|
| [Todd and Ren (2023)](https://www.nature.com/articles/s41558-023-01835-w), with [2024 correction](https://doi.org/10.1038/s41558-024-02009-y) | In situ observations from 2001–2023 show warming and a shoreward Gulf Stream shift west of 68 degrees W. The corrected shift estimate is about 6 ± 3 km per decade. | Geographic overlap makes long-term change plausible. A gradual regional trend is not a dated break in our 7/30-day transition probabilities, nor proof that pre-2012 records harm forecasts. |
| [Gangopadhyay et al. (2019)](https://www.nature.com/articles/s41598-019-48661-9) | A regional chart census reports a warm-core-ring formation shift around 2000 between 75 and 55 degrees W: about 18 rings/year before 2000 versus 33 thereafter. | This concerns ring formation, largely downstream of the release region. It is a candidate physical context, not an approved date filter. Our pre-2000 qualified sample is too small for a strong internal before/after test. |
| [Perez et al. (2024)](https://doi.org/10.1029/2023JC020761) | Global altimetry eddy-tracking products do not reproduce the census ring-count shift; difficulties distinguishing rings from other eddies matter. Other altimetry-derived kinetic-energy and velocity diagnostics show changes near 2000. | Product and observable choice affect the inferred change. Do not treat one detected breakpoint as a universal ocean-state boundary. |
| [Volkov et al. (2024)](https://www.nature.com/articles/s41467-024-51879-5) | Correcting geomagnetic effects in the Florida Current cable record removes much of the apparent decline. The updated article reports a nonsignificant 1982–2023 volume-transport trend of −0.1 ± 0.2 Sv/decade. | This is upstream transport at 27 degrees N, not local surface-particle destinations. It illustrates measurement-related trend risk; stable integrated transport does not imply stable path, temperature or transition probabilities. |
| [Andres (2021)](https://doi.org/10.1029/2021JC017579), [NOAA-hosted paper](https://repository.library.noaa.gov/view/noaa/44652/noaa_44652_DS1.pdf) | Observations near Cape Hatteras identify approaching meanders with periods below 15 days and substantial spatial/temporal variability. | Short-term flow conditions can matter on our prediction horizons. Calendar year alone cannot describe all relevant current-state information. |
| [van Westen and Dijkstra (2026)](https://www.nature.com/articles/s43247-026-03309-1) | A high-resolution ocean simulation produces an abrupt Gulf Stream shift before a simulated AMOC collapse; the paper separately analyses observed longer-term path trends. | The simulated abrupt shift is not an observed historical cutoff in our 1998–2022 data. It must not be used to assign a real-world break year. |

Access and version notes: the Todd/Ren NOAA-hosted manuscript was inspected for geographic coverage; its numerical shift estimate is superseded by the 2024 correction, whose text was read in [this correction-page copy](https://bura.brunel.ac.uk/bitstream/2438/28973/1/Correction.pdf). The updated Volkov article was accessible and lists a [2025 correction](https://doi.org/10.1038/s41467-025-58976-z), but the correction text itself could not be retrieved with the browser tool. Conclusions above use the accessible updated article. Publisher search excerpts were used for the Perez findings and the 2026 simulation/observation distinction. This is a bounded initial review, not an exhaustive literature search.

## 3. Markov dependence is not time homogeneity

For a proposed state X and horizon h, the Markov assumption removes extra dependence on the preceding state history once the present is known:

$$
\Pr(X_{t+h}=j\mid X_t=i,\text{preceding history})=P_{t,h}(i,j).
$$

This does not imply equal transition kernels at different calendar times t and s. Time homogeneity is an additional assumption. A homogeneous transition kernel also does not, by itself, make every sampled marginal distribution stationary or every observation independent. [Pitman's Berkeley lecture notes](https://www.stat.berkeley.edu/~pitman/s205s03/lecture1.pdf) explicitly distinguish a time-indexed kernel from a homogeneous kernel.

Illustrative counterexample, not fitted project data: a cell can have an 80% northward transition probability in one period and 40% in another while obeying a Markov rule within each time-dependent process. No earlier position need enter either probability.

Our B2 state is only a 1-degree origin cell. It does not encode exact within-cell position, initial velocity, wind, current field or drogue state. Consequently, the same observed cell need not represent the same physical state. If Z denotes omitted conditions, the cell-level law averages P(destination | cell, Z) over the conditions observed in that cell and period. Changes in that mixture can change estimated cell transitions without proving a change in the underlying physical laws. Markov adequacy of the cell representation is a modelling approximation, not an established physical property.

## 4. Is later-year training and earlier-year validation necessarily wrong?

No. If the aim is retrospective estimation of a stable historical conditional law, later-calendar observations from separate, appropriately held-out trajectories can help estimate it. Every trajectory pair still runs forward from t0 to t0+h. Mixing calendar years is not the same operation as using the validation endpoint as a predictor, and is not automatically target leakage.

Such evaluation needs a defensible common sampling target, group isolation, and control of remaining shared-event dependence. A stable conditional law alone does not ensure that overall scores are comparable when origin/season/deployment mixtures differ.

For a claim about predictions available at a historical cutoff, observations collected after that cutoff were unavailable. A model trained with them is not a faithful reconstruction of that forecasting exercise. Forward validation tests transportability to a later period and the actual information restriction. Its score can be worse or better; chronology alone does not guarantee a direction of bias.

Different drifter IDs may share the same ocean event. Whole-ID exclusion addresses repeated observations from one drifter, but not all dependence from common forcing. Neither evaluation should count hourly pairs as independent realizations.

Recommended interpretation:

- Historical whole-ID validation: performance on other sampled drifters from the historical mixture; useful for comparing estimators under that target.
- Forward, whole-ID-isolated validation: performance on later-period drifters using only earlier information; important evidence for the intended prospective application.
- Repeatedly inspected development periods remain development evidence. A different split of the same records is not an untouched final test.

## 5. What the existing project records establish

The read-only review grouped saved source-keyed [origin features](../results/deliverables/seasonal_conditioning_s4_e1/origin_features.parquet) by UTC origin year and joined [role membership](../results/deliverables/seasonal_conditioning_s4_e1/role_membership.parquet) on ID, source observation and horizon. No destination-distribution change test was performed.

- Full qualified development inventory: 303,288 / 268,998 pairs at 7 / 30 days. Earliest qualified origins are in 1998 / 2000; latest are in October 2022. No 1999 qualified pairs occur in this inventory. This is not the temporal coverage of the entire raw database.
- Before 2000, only 231 qualified 7-day pairs from one ID and no 30-day pairs are available. This cannot robustly test the published circa-2000 ring regime change.
- The 2011 inventory contains 50,338 / 46,862 pairs from 51 / 47 IDs, accounting for 16.60% / 17.42% of all 7 / 30-day qualified pairs. Such concentration is evidence of uneven sampling, not a diagnosed oceanic breakpoint.
- In 2022, the qualified inventory contains only 6 / 5 IDs and is an incomplete year. Calendar labels do not guarantee balanced or independently replicated conditions.
- Under the approved chronological and ID exclusions, recent training contains 130,731 / 113,708 pairs. The previously sealed support audit reports 265,740 / 235,293 if all available pre-2020 years were retained under the same exclusions. Restricting the start to 2012 therefore roughly halves the available training pairs. This is a cost of a window choice, not a requirement of forward validation.
- Training and validation IDs remain disjoint. The current split uses 2012–2019 training and 2020–2022 validation, with labels requiring 2020-or-later observations excluded from training. The new review did not alter these roles.

Counts and audit scope: [temporal support audit](../provenance/reviews/seasonal_temporal_support_20261102/README.md). Existing fitted evidence: [S4 E1 results](seasonal_conditioning_s4_e1_results.md). The annual-versus-seasonal comparison is matched within that cohort; comparing its score to older historical CV cannot isolate the effect of chronology or training sample size.

The pooled drifter scenario also warrants composition checks before attributing temporal differences to ocean dynamics. NOAA documents that drogue loss increases wind/wave influence: [GDP FAQ](https://www.aoml.noaa.gov/phod/gdp/FAQ.php). This is a reason to audit status mix, not evidence that our cleaned release is erroneous, and not permission to change the pooled scenario. Exact-origin motion/status distributions were not re-read or compared in this review; their contribution remains unknown.

## 6. Discussion proposals, not an execution contract

1. Preserve eligible old data. Keep scientific quality exclusions separate from optional age-based training windows. There is no demonstrated physical reason here for automatically rejecting everything before 2012.
2. Before selecting dates, compare support and composition by year: distinct IDs, origin cells, season, within-cell positions, initial motion, drogue status and dominant-record contributions. Compare like conditions before interpreting endpoint differences as temporal drift. Source fields and availability must be audited first.
3. If an external current/path series is later used, require geographic overlap or a defensible downstream connection, documented processing corrections, and evidence that the proposed change is relevant to 7/30-day surface transport. A significant trend is not necessarily a change point; neither establishes a predictive benefit from deletion.
4. A small, separately approved annual-B2 comparison on the same forward validation roster can test all available pre-cutoff training against 2012-onward training. Other controls and evaluation weights should be fixed. This tests the predictive utility of historical data, not a causal ocean-regime hypothesis.
5. Preserve historical grouped evaluation as complementary evidence and forward evaluation for prospective claims. Define any internal rolling cutoffs and training-window selection in advance, using only the fitting period. Do not search for a flattering split after observing 2020–2022 scores.

No new cutoff, formal change-point test, model development, refitting, external environmental download, final-test access or publication was performed. The next engineering contract should be drafted only after the research target and evaluation roles are agreed.
