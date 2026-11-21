# Part 3 source-backed visualization export

- S2 maps are all-development fitted illustrations; metric cards summarize held-out whole-ID CV.
- S3 metrics use equal cells and equal IDs within cell, unlike S2 pair weighting.
- E7 ExactPoint is the 1° stopped-target experiment, not the later continuous ES control.
- MDN22 map is newly exported from saved forecasts for the original first fixed case; it is not a new model run.
- EndpointCI uses the saved 8,000-donor lineage: 7,487 usable historical error kernels and 513 unchanged point masses. Each donor retains 1/8,000 weight.
- All continuous displayed maps use deterministic display-only samples; original scores and saved ellipses are retained.
- Different targets, grids and aggregation weights cannot be pooled into a universal model ranking.
- No locked final-test data, refitting, model selection or recomputed scores were used.

## Reproduction

Run `work_place/.venv/bin/python scripts/export-part3-data.py --root <work_place>` from the Site checkout. Requires numpy, pandas, pyarrow and pyproj already present in the research environment.

MDN/Gaussian display sample count: 65,536. Seeds: 20261116 plus 1, 22 or 100. Mixture parameters describe east/north geodesic displacements in km; WGS84 forward geodesics yield endpoints. Saved 90% ellipses use the original LAEA projection centered on 75°W, 35°N. Binning does not renormalize viewports.

EndpointCI reproduces the original E3 display recipe with budget 32,768 and seed 20261126: the native antithetic component_cloud produces 30,461 weighted nodes (7,487 usable donors × 4 nodes, plus 513 point fallbacks). Each donor keeps exactly 1/8,000 total weight. The saved region is copied, not refitted. Errors are repaired historical 95% marginal half-widths, matched to independent normal kernels using 1.9599639845; they are not model-parameter confidence intervals. No held-out endpoint-error fields were read. The fixed example key is [300234063731750,139319181,7], position 0 of the original 12 outcome-independent source-order cases.

Latest MDN22 interval and whole-R gaps remain. Departure heading is omitted from the presentation at user request; research artifacts are preserved. B1 standalone metrics were not reported by the S2 comparison.

## Source SHA256

- `results/runs/adaptive_b2_b1_20261030T044950_931787Z/summary.csv` — `54f074d8737a1db384e5b6c5e3f1c682c34e032447b60ffe1df34efe5f6d7fca`
- `results/runs/adaptive_b2_b1_20261030T044950_931787Z/matrices/all_development_candidate_B2.parquet` — `10d412ace7c14f1d64d17f3e95bcf6fbc43c8f79175e0d25eeb6f1f1db8d4221`
- `results/runs/adaptive_b2_b1_20261030T044950_931787Z/matrices/all_development_candidate_Fixed.parquet` — `03e6c02e717c0e61a9c40edf9063931bbf373628f902a9524eb784f3b76d0d1c`
- `results/runs/adaptive_b2_b1_20261030T044950_931787Z/matrices/all_development_candidate_Adaptive.parquet` — `163efd184fa3ef62007080a2ac45c28049b4e9403324590bc5d9dc4edc67ce4b`
- `results/runs/adaptive_b2_b1_20261030T044950_931787Z/bases/all_development_candidate_b1.parquet` — `f78312b90a41f6a05cf749c4da607138d9d96e80ce8a77ff9a0e876ec64d01e8`
- `results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/summary.csv` — `a68b90050b004bb6a62e040af5bc70a26006544cdc08fdd3d39a6d741c1bea57`
- `results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/matrices/all_development_candidate_LocalEndpoint.parquet` — `2530a5dc330c87c1ebde3bd04613e1cbe1a0e20cf9910d1bd4fd6f3018180f17`
- `results/runs/spatial_borrowing_s3_e1_20261030T114538_900248Z/matrices/all_development_candidate_LocalDisplacement.parquet` — `f020b5364c2bc069e62a06c32b08a11393a99daf957f317e0ad7158503ace9ad`
- `results/deliverables/seasonal_information_s4_e3/summary.csv` — `62f1d2a3bf68e793253cd3f7ccb2d08e4a46c6104eea1dea0d4b62088b9ac85f`
- `results/deliverables/seasonal_information_s4_e3/forecast_keys.csv` — `ad0f4cb26e399de40e32b6f0b1f22d46b3061d98a3f867d3f79dd7cf334e5cf8`
- `results/deliverables/seasonal_information_s4_e3/forecast_vectors.npy` — `88acecf817274a35e9faa3971bf99323f5a891e7eebb8b88d4fc365ca3f8d5b8`
- `results/deliverables/seasonal_information_s4_e3/states.npy` — `3667a3e7b24554e1a7f015c22cdf068f90b1af4527b7ffc4dd017fc94093f388`
- `results/deliverables/seasonal_information_s4_e3/region_masks.npy` — `2f5cf2f7137c48b900120e875d12b73b0e804f6e9cf81d01cb77f02134542a56`
- `results/deliverables/exact_origin_s4_e7_visual_report/src/data.json` — `0a1ab78b0abe92141b5afd5524b3dce0b2a7a45108ae20ceca5171ca174e59a2`
- `results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/summary.csv` — `5c2bffb47b55968b510466b10fb6058699a47c55b2a5af8f8e1c5dc9c173670c`
- `results/runs/local_gmm_s5_e2_vector_20261107T133426Z/summary.csv` — `b45d456014f7fc493c8bbd510d0accab7a6a4f0dc15dd58e3a3f55e1d5133bc7`
- `results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/outer_targets.parquet` — `ac4d6dde254a4b785862e8d1de168e9c06690f1798e3463e14c956731627d342`
- `results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/C_outer/outer_score/N65536_M65536/scores.parquet` — `16786551321246048f97a71fd763b072aebeb859b268fd75405f9db9eb5e3a2c`
- `results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/C_outer/K1/parameters.npz` — `13864f3897220562cbd1bf706def04f12bdc717f35396d2ab15a48ce1823f20d`
- `results/runs/conditional_mdn_s5_e4_20261109T082930_653149Z/formal_v1/C_outer/K22/parameters.npz` — `f95d84c8aec9f564148f89e422806f825237910659a73eadc742edcbd9f1d829`
- `results/runs/local_gmm_s5_e2_vector_20261107T133426Z/C_outer/parameters/00000.json.gz` — `bb25242bdebe443d9536278aec3439f15e455eb7e464fd299e0d401bee069d5a`
- `results/runs/local_gmm_s5_e2_vector_20261107T133426Z/C_outer/regions/00000.json.gz` — `ab1d1b72ad7a9874c536d271322c3324b92efe550dc47c16570216b155d42558`
- `results/runs/local_gmm_s5_e2_vector_20261107T133426Z/C_outer/lineage/00000.npz` — `4a1ee3ffda24c55337aeb4c4efb3b036f3b9d3b3a20f61ceee6b38d8d18b0935`
- `results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet` — `8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d`
- `provenance/migrations/position_error_repair_20261106T073218_242005Z/full/error_overlay.parquet` — `cf77af02d7af69b255d84b40f49bd5d7c4ad41f35816e00a58926ad6f47dd8f3`
- `src/data3001/modelling/baselines/position_error_s4_e8.py` — `0bf190afee883be8fdaf0dd13a44241c9f8a2c073fa1f3397ed1f98b44ff6c5a`
