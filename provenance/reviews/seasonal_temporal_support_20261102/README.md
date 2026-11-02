# Seasonal temporal support: planning-only audit

Date: 2 November 2026 (Australia/Sydney).

This audit counts existing qualified development pairs. No probability matrix was fitted, no predictions or scores were generated, no model experiment was run, and no final-test trajectories or labels were read. It does not approve a revised contract or establish predictive improvement. Existing contracts and the research-stage ledger were not modified.

## Inputs and verification

Source: `results/runs/markov_input_20261025T095949_830292Z`, release `per-drifter-cleaned-20261017-v7`. All 396 source label files, the per-ID count table, and the development source inventory were checked against the sealed output receipt. Source metadata reconciles with all 3,224 development IDs. Qualified counts reconstructed from labels exactly match the sealed annual table: 303,288 / 268,998 pairs, 385 / 337 IDs, 4,451 / 3,974 ID-origin units, 37 observed origins (7 / 30 days). UTC season and exact horizon timing identities were checked.

The 517 locked final-test IDs remain outside the audit. These development observations have been used in prior project work: a future chronological comparison here is a development backtest, not a newly untouched final test.

`audit.json` records the input hashes, boundary definitions, source counts, and support statistics. `annual_support.csv` and `training_cell_season_support.csv` supply detailed counts. `audit_support.py` reproduces the calculation using temporary output files; it does not overwrite this report directory.

## Non-overlapping time bins

Interpret bins as departure dates in [1998-01-01, 2002-01-01), [2002-01-01, 2012-01-01), and [2012-01-01, 2023-01-01). Thus labels below are inclusive calendar years. The last bin only includes observations actually available in 2022; it is not a complete year. An ID may appear in multiple bins; their ID counts must not be added as distinct individuals. Counts are an inventory by departure date, before chronological training purges.

| Departure years | 7-day pairs / IDs | 30-day pairs / IDs |
|---|---:|---:|
| 1998-2001 | 1,929 / 5 | 911 / 3 |
| 2002-2011 | 133,080 / 184 | 120,674 / 160 |
| 2012-2022 | 168,279 / 204 | 147,413 / 180 |

1998-2001 is too sparse to recommend as a standalone seasonal training cohort. Later cohorts permit an initial empirical comparison; raw pair counts are not counts of independent realizations. Neither the dates nor this support audit demonstrate a physical change in transport between decades.

## Proposed 2020 boundary: support, not an approved split

Training origins: [2012-01-01, 2020-01-01). Validation origins: [2020-01-01, 2023-01-01), limited to available qualified labels.

1. Keep a training label only if its `required_interval_end_epoch` is strictly before 2020-01-01 UTC. There are 630 / 1,921 excluded training pairs (7 / 30 days).
2. Define validation IDs as the union of eligible validation IDs across both horizons. Remove all training records for these IDs from both horizons. After the label purge, this removes another 2,947 / 1,656 training pairs, involving 6 / 4 IDs respectively. The final train/validation ID sets are disjoint.

| Role | 7-day pairs / IDs / origins | 30-day pairs / IDs / origins |
|---|---:|---:|
| Recent training after both exclusions | 130,731 / 159 / 37 | 113,708 / 138 / 37 |
| Validation | 33,971 / 45 / 36 | 30,128 / 42 / 35 |
| All earlier training after identical exclusions (support diagnostic only) | 265,740 / 340 / 37 | 235,293 / 295 / 37 |

All validation origins have annual training support. Of 37 globally observed origins x 4 seasons = 148 potential rows, the recent training set has 2 / 3 empty seasonal rows and 50 / 60 rows with 1-9 distinct IDs (7 / 30 days). The 10-ID boundary is a descriptive bin, not a statistical adequacy criterion.

Under the existing hierarchy of equal times within ID/origin, equal IDs within origin and equal origins:

- 7 days: 41 validation pairs lack same-season local training support. They are 0.121% of pairs but 2.778% of evaluation weight. Another 30.704% of evaluation weight has 1-9 same-season training IDs.
- 30 days: no evaluated cases lack same-season training support; 36.757% of evaluation weight has 1-9 same-season training IDs.
- Validation MAM support is 9 distinct IDs at each horizon; 2022 alone has only 6 / 5 IDs. A single year or season cannot be assumed to deliver precise comparisons.

## Suggested simplified comparison (requires a revised contract and approval)

Compare annual B2 with departure-season B2 at fixed seasonal weight c=1. Retain raw-pair training counts, existing equal-ID/equal-origin evaluation, exact 7/30 days, standard Brier, fixed 90% region, and matched cases. No seasonal weight search, B1 fusion, velocity, SST, new geometry or nested parameter search is needed for these two untuned models.

For a missing seasonal row with annual support, a proposed operational fallback is annual B2 with explicit fallback reporting; the resulting system is seasonal where supported, not a fully seasonal estimate on every case. Do not drop those 41 cases silently. A common seasonal-supported subset can be a secondary diagnostic.

Keep the recent training window fixed in both models to isolate the effect of season. Preserve earlier data; testing whether older training helps is a separate, later comparison on the same validation roster. Use whole-ID uncertainty estimation rather than treating hourly pairs as independent. Do not declare physical seasonality solely from a difference in held-out scores or claim that failure of c=1 proves seasonality absent.
