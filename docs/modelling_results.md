# Modelling results — team handoff, 9 November 2026

本页是 report / presentation 的统一入口。按相同实验中的样本、评分和权重比较；保留负结果及未完成研究的边界。最新 MDN 已完成，早些时候的交互展示和汇报稿保留当时的进度快照。

## Five-stage evidence index

| Stage / experiment | Definition and results | Visual evidence |
|---|---|---|
| S1 B2 | [Results](empirical_b2_results.md) | [Comparison](../results/deliverables/empirical_b2/review.html) |
| S2 E1 Fixed / Adaptive | [Results](adaptive_b2_b1_results.md) | [Comparison](../results/deliverables/adaptive_b2_b1/review.html) |
| S2 E2 information / weight | [Results](b2_b1_e2_results.md) | [Comparison](../results/deliverables/b2_b1_e2/review.html) |
| S2 E3 equal drifter | [Results](drifter_shrinkage_e3_results.md) | [Comparison](../results/deliverables/drifter_shrinkage_e3/review.html) |
| S2 E4 partial weighting | [Results](partial_weighting_e4_results.md) | [Comparison](../results/deliverables/partial_weighting_e4/review.html) |
| S3 E1 Endpoint / Displacement | [Results](spatial_borrowing_s3_e1_results.md) | [Comparison](../results/deliverables/spatial_borrowing_s3_e1/review.html) |
| S3 E2 adaptive local borrowing | [Results](local_endpoint_adaptive_s3_e2_results.md) | [Comparison](../results/deliverables/local_endpoint_adaptive_s3_e2/review.html) |
| S3 E3 neighbour quality | [Results](local_endpoint_quality_s3_e3_results.md) | [Comparison](../results/deliverables/local_endpoint_quality_s3_e3/review.html) |
| S3 E4 joint constrained selection | [Results](local_endpoint_joint_s3_e4_results.md) | [Comparison](../results/deliverables/local_endpoint_joint_s3_e4/review.html) |
| S4 E1 seasonal B2 | [Results](seasonal_conditioning_s4_e1_results.md) | [Comparison](../results/deliverables/seasonal_conditioning_s4_e1/review.html) |
| S4 E2 temporal validation | [Results](temporal_validation_s4_e2_results.md) | [Comparison](../results/deliverables/temporal_validation_s4_e2/review.html) |
| S4 E3 seasonal information test | [Results](seasonal_information_s4_e3_results.md) | [Comparison](../results/deliverables/seasonal_information_s4_e3/review.html) |
| S4 E4 departure direction | [Results](departure_direction_s4_e4_results.md) | [Comparison](../results/deliverables/departure_direction_s4_e4/review.html) |
| S4 E7 precise origin | [Results](exact_origin_s4_e7_results.md) | [Comparison](../results/deliverables/exact_origin_s4_e7/review.html) |
| S4 E8 endpoint errors / CI | [Report](../results/deliverables/position_error_s4_e8/REPORT.md) | [Comparison](../results/deliverables/position_error_s4_e8/review.html) |
| S4 E9 exact-position seasonal closing | [Report](../results/runs/e9_formal_20261106T140607_806462Z/REPORT.md) | [Comparison](../results/runs/e9_formal_20261106T140607_806462Z/review.html) |
| S5 E1 LocalGaussian | [Report](../results/runs/conditional_gaussian_s5_e1_full_20261107T061818Z/technical_report.md) | [Comparison](../results/runs/conditional_gaussian_s5_e1_full_20261107T061818Z/review.html) |
| S5 E2 local GMM | [Report](../results/runs/local_gmm_s5_e2_vector_20261107T133426Z/technical_report.md) | [Comparison](../results/runs/local_gmm_s5_e2_vector_20261107T133426Z/review/final.html) |
| S5 E3 conditional MDN | [Report](../results/deliverables/conditional_mdn_s5_e3/REPORT.md) | [Comparison](../results/deliverables/conditional_mdn_s5_e3/review.html) |

S3 E5 exact-origin whole-path borrowing remains [incomplete/deferred](actual_origin_displacement_s3_e5_o1_results.md). The [speed proposal](departure_speed_s4_e5_plan.md), [wind proposal](alongshore_wind_s4_e6_plan.md) and [grid-translation contract](b2_grid_translation_contract.md) are not completed full predictive experiments. [Earlier M1 / M1vcat / iterative studies](markov_results.md) remain available separately.

## Latest conclusion

MDN1/2/4/8/16/32 all completed. Inner selection chose K=1 under the two-window eligibility rules; K=4/32 had slightly lower pooled inner ES but worsened in the later window. K=1 does not establish physical unimodality.

On the shared 45-drifter / 33,971-pair seven-day development cohort, selected MDN1 has **128.702 km ES / 87.63% actual coverage / 175,929 km² mean 90% area**. LocalGaussian has **134.777 km / 91.54% / 216,097 km²**. Mean ES and area improve, but coverage falls and the paired ES interval crosses zero. The preregistered quality-preserving acceptance fails. See [all scores](../results/deliverables/conditional_mdn_s5_e3/summary.csv), [paired intervals](../results/deliverables/conditional_mdn_s5_e3/comparisons.csv) and [audit](../results/deliverables/conditional_mdn_s5_e3/final_audit.json).

## Report-writing boundaries

1. State the target and horizon. Current continuous models estimate seven-day endpoints; older cell models also examine 30 days. Older stopped-domain operators estimate a different target.
2. State cohort and evaluation weights for every comparison. Recent fits use equal pairs and evaluation uses equal drifters. Earlier pair/equal-cell studies differ.
3. Present ES or Brier together with actual coverage, region size/area, uncertainty and support/fallback rules. A smaller region alone is not better; 90% model probability does not guarantee 90% observed coverage.
4. Treat 2020–2022 as repeatedly examined development validation. No independent final-test claim is supported.
5. Do not numerically rank different Brier grids, Brier versus ES, or Brolly's four-day global log score against our seven-day regional ES. See the [literature audit](brolly_miron_transport_methods_review.md).

## Team files and reproducibility

- [Portable team package](../results/deliverables/team_review_20261109/README.md): Chinese/English interactive snapshots, historical handoff and final MDN links.
- [MDN inference](../results/deliverables/conditional_mdn_s5_e3/inference_usage.md): selected network and all six final full-refit checkpoints are included; no retraining is required for new coordinates.
- Contracts, source, tests, compact scores, figures, saved parameters and audit receipts are published. [Publication inventory](../provenance/reviews/modelling_publication_20261109.json) records included artifacts and omitted caches.
- Historical audits can reference omitted immutable files by hash. These references do not promise that a fresh clone contains every donor lineage or integration shard. No data or experiment definition changed for publication.
