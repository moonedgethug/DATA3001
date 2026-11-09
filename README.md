# DATA3001 — Where Things End Up

**Latest modelling handoff: 9 November 2026.** Empirical Markov, regularisation, spatial borrowing, exact-position/error/seasonal, LocalGaussian, local GMM and conditional MDN experiments are available for the team report and presentation. Completed experiments are evidence, not a claim that every method improved prediction.

## Start here / 组员阅读入口

- **[All modelling results / 全部建模成果总目录](docs/modelling_results.md)** — methods, original results and comparison limits.
- **[Team review package / 组员审阅包](results/deliverables/team_review_20261109/README.md)** — portable Chinese/English interactive snapshots and final MDN evidence.
- **[Completed MDN report](results/deliverables/conditional_mdn_s5_e3/REPORT.md)** · [visual report](results/deliverables/conditional_mdn_s5_e3/review.html) · [nine-model results](results/deliverables/conditional_mdn_s5_e3/summary.csv) · [saved-model usage](results/deliverables/conditional_mdn_s5_e3/inference_usage.md).

GitHub renders Markdown and images but shows HTML source. Download/clone this repository before opening the HTML reports. The interactive snapshots predate MDN completion; the separate completed MDN report supplies the final results.

## Five-stage research programme

| Stage | Research question | Completed evidence / boundary |
|---|---|---|
| 1 — Empirical transition matrices | Where did drifters from this 1° origin cell end up? | Frozen B2 at 7/30 days; Brier, support and 90% regions. |
| 2 — Regularisation | Can broader evidence and adjusted contributions stabilise estimates? | Fixed/Adaptive B2–B1, information allocation, equal/partial ID weighting. |
| 3 — Spatial information | What can neighbouring origins contribute? | Endpoint/displacement benchmark and endpoint refinements. Exact-origin whole-path E5 remains incomplete/deferred. |
| 4 — Conditioning and precise position | Do season, direction, exact coordinates or position errors help? | Temporal, seasonal/direction, exact-origin, repaired endpoint-error and seasonal closing comparisons. Wind/speed proposals are not completed experiments. |
| 5 — Parametric continuous transition distributions | Can Gaussian, GMM or neural conditional estimation improve the location distribution? | Complete LocalGaussian, local GMM and MDN1/2/4/8/16/32 seven-day comparisons. |

Step 5 retains a position-conditioned Markov transition-kernel interpretation in continuous space. Step numbers are research stages, not forecast horizons. Long-horizon recursive accuracy, physical grounding, oil weathering and object-specific operational performance remain unvalidated.

## Latest MDN finding

Inner selection chose **K=1 among eligible candidates**. Larger mixtures did not satisfy the two-window rules; K=4/32 had slightly lower pooled inner ES but worsened in the later window. All six complexities were nevertheless trained and evaluated. The experiment contains 72 fits; final training uses 265,393 pairs / 338 drifters (2001–2019), and development validation uses 33,971 pairs / 45 drifters (2020–2022).

Against LocalGaussian, MDN1 reduces mean ES from **134.777 to 128.702 km** and mean 90% ellipse area from **216,097 to 175,929 km²**, but observed coverage falls from **91.54% to 87.63%**. The paired ES interval crosses zero. **Quality-preserving improvement was not established.** Negative results, numerical checks and uncertainties are retained.

These are development results. The 517-ID final-test set remains locked. Different cohorts, evaluation weights, Brier grid resolutions and ES are not one leaderboard. See the [historical Markov publication](docs/markov_results.md) for earlier methods and evidence.

## Data and implementation

The canonical release remains `per-drifter-cleaned-20261017-v7`: 3,741 IDs, 39,099,193 hourly records and 62 columns. The [Data Contract](docs/contract/data_contract_v1.0.xlsx), [data dictionary](docs/data_dictionary.md), [preprocessing guide](docs/preprocessing.md) and [data layout](docs/data_layout.md) preserve definitions and limitations. Position-error repair is an additive supplement; original data are retained.

The release polygon R has bounds `[-81, 30, -73, 35.5]`; domain D spans `81–8°W, 20–55°N`. Polygon membership defines eligible starts. Older stopped-domain and newer direct endpoint targets must be distinguished.

Source is organised into shared `common/`, empirical `baselines/`, iterative `markov_models/` and Gaussian/GMM/MDN `continuous_models/` under `src/data3001/modelling/`. See the [code guide](docs/code_guide.md). Contracts, configurations and tests accompany the results. The protected stage ledger remains the historical approval record; this publication index does not rewrite approved hypotheses.

## Read, reuse and reproduce

Reading reports requires no training. For Python, follow [getting started](docs/getting_started.md), use Python 3.12 and an isolated environment:

```sh
python -m pip install -e '.[continuous,data-repair]'
python -m unittest discover -s tests -v
```

The publication check passed **902 tests**. Six final MDN checkpoints and manifests are published at their original run paths; the [inference guide](results/deliverables/conditional_mdn_s5_e3/inference_usage.md) loads the selected model without training data or validation outcomes. Saved local Gaussian/GMM query parameters and scored summaries are also available.

The [publication inventory](provenance/reviews/modelling_publication_20261109.json) records included artifacts and omitted caches. Full experimental replay requires the matching omitted input/lineage caches or an approved rebuild. Large donor lineages, per-node scoring caches, local app runtimes and duplicate interrupted outputs remain local. No fitting, original-data change or final-test evaluation was performed for this publication.
