# Part 2 sources and interpretation

Geographic context: Natural Earth 1:50m land, public domain. Existing cached source simplified for this presentation. https://github.com/nvkelso/natural-earth-vector/blob/master/geojson/ne_50m_land.geojson . Land is geographic context, not the model's coastal mask.

R: frozen project release_R polygon, retained from existing Part 1 geography. Source hash retained in data.json. D: [-81,20,-8,55]. Gulf Stream segment polygons are intersections from the original regional audit, not equal-length geographic bands.

Region totals: work_place/archive/region_screening_6h/outputs/region-audit-summary.csv and gulf-stream-segment-summary.csv, supplied here unchanged. Historical May 2025 six-hour GDP screening, not the hourly model cohort. Distinct entering trajectories and distinct trajectories with at least one valid 7-day pair. Do not add across overlapping regions or interpret raw totals as a fair quality rank.

Annual bars: work_place/provenance/reviews/seasonal_temporal_support_20261102/annual_support.csv, horizon_days=7. The sealed development-label audit uses reason_code=0, stopped targets, 1-degree cells, exact horizons, grouped by origin year. The audit script loads all qualified years before applying proposed splits. Missing years 1990–1997 and 1999 are zeros only within that inventory. Total 303,288 seven-day pairs, 385 IDs. 2022 incomplete. Annual distinct-ID counts are not additive. These bars precede final boundary purges and whole-ID exclusions.

Final continuous model counts: work_place/docs/final_mdn_model.md and docs/temporal_validation_s4_e2_results.md. Fit 2001–2019: 338 IDs / 265,393 pairs; development validation 2020–2022: 45 IDs / 33,971 pairs. Final-test IDs remain sealed; no final-test trajectory records are exported or inspected here.

Cleaning: work_place/docs/preprocessing.md, docs/data_dictionary.md, docs/drogue_status_audit.md; results/runs/sst_sparse_completion_20261017_v2/REPORT.md; provenance/migrations/recovery_tail_removal_20261017_v1/acceptance.json; provenance/migrations/grounding_sst_na_20261017_v1/REPORT.md. State encodings, official SST backgrounds, actual-time velocity derivation and lifecycle distinctions retain the documented semantics. No claim that SST reconstruction improved the final location-only MDN.

Unlocated evidence: comparable quantitative audits for the other early candidate regions. Keep the visible placeholder. Southern Corridor is the selected pilot, not the most populated screening window or a demonstrated easiest-to-predict region.

Visual assets reuse Part 1's Three.js library, water normals, Poly Haven daylight HDR and authored buoy. See ../pt1/SOURCES.md and ../SOURCES.md. Cutaway, grid interpolation sketch, waves and route line are illustrations. No fabricated observations, temperatures or forecast paths.
