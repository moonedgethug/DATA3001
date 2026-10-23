# Optimized baseline — demonstration and reuse

## Open the presentation

Download or pull `main`, then open `results/deliverables/baseline_optimized/index.html` in a browser. This is a complete offline presentation: it embeds the probability snapshot, coastline and pinned D3 library. No Python, server, API key, login or network connection is needed for viewing. GitHub's file viewer shows source; open the downloaded file to use its controls.

The scientific source is `baseline_blend_cv_20261022T160806_056571Z`. Its result and provenance directories are retained under `results/runs/` and `provenance/runs/`. The complete drifter records stay in the existing data directories. The page does not fit models or open trajectories.

## Suggested class demonstration

1. Explain the question: given a release cell in the southern Gulf Stream Corridor, estimate the historical endpoint distribution at 7 or 30 days. The current result is a pooled historical drifter baseline, not a precise-point or object-specific forecast.
2. The initial view uses the 30-day Grid blend, outer fold 0 and an origin selected using training support only. Switch from B2 to Grid or Analytic while keeping horizon, origin and fold fixed. The left panel is the forecast; the right is the endpoint frequency among the matched held-out IDs.
3. Explain the controls: B0 predicts no cell movement; B1 pools all R origins; B2 conditions on the origin cell. The blend borrows whole-R information through `p = (1 − λ) B2 + λ B1`. The two maps share one explicit per-cell color scale. A change in the scale ceiling changes color intensity, not the probabilities themselves.
4. Discuss the all-fold table. At 30 days the analytic blend improves Brier from 0.994400 to 0.989005 and nominal-90% set hit rate from 67.20% to 86.20%. Its mean set size increases from 64.9 to 128.4 geographic cells. These are different measures, not one percentage-accuracy score.
5. Show the inner tuning curve. Grid search evaluates 0, 0.1, ..., 1. Analytic selection minimizes the same quadratic Brier objective continuously. Its optimum is guaranteed only on the tuning cases; the grid is slightly better in the 7-day outer comparison.
6. Show the final candidate weights below the maps. Grid uses 0.1 / 0.6; Analytic uses 0.090942 / 0.585254 for 7 / 30 days. These full-development candidates differ from the map's independently selected fold weights. The saved bases are refitted on all development data; the displayed score evaluates the nested tuning procedure.
7. End with limits and next steps: zero-probability failures remain, raw log loss is infinite, 30-day 90% sets still under-cover, and seven-day Brier gains are small. The 517 final-test IDs remain unused. Seasonal, annual, grounding and object-specific capability require separate work.

## Rebuild the same entry after another approved experiment

From the repository root, after the normal Python setup:

```bash
.venv/bin/python -B -m data3001.modelling.showcase --run-id baseline_blend_cv_20261022T160806_056571Z
```

Pass a later approved completed run ID when refreshing the presentation. The exporter verifies the source's sealed output hashes and final-test policy before publishing. It uses the existing saved comparison, summary and final weights; it does not recalculate scientific results. It refreshes only `index.html` and `site_manifest.json` in this fixed deliverable directory. Manual edits are detected and preserved rather than silently overwritten.

`src/data3001/modelling/showcase.py` owns this export. The chart library is vendored under the modelling package with its upstream license and source checksums. The intermediate land mask required by the original report builder is also included in the repository with its unchanged catalog checksum.

## Reproduce the scientific experiment

```bash
.venv/bin/python -B -m data3001.modelling.run_blend_cv
```

This creates a fresh immutable result/provenance run, reuses the existing data qualification and endpoint rules, and keeps the final test locked. It is separate from presentation export. Test with:

```bash
.venv/bin/python -B -m unittest discover -s tests -p 'test_modelling_*.py' -v
```

The Data Contract remains authoritative. Publishing a page does not change the release region, transport domain, inputs, feature choices, eligibility or validation target.
