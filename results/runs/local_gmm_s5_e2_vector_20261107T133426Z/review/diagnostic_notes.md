# Step 5 E2 diagnostic delivery

The frozen core release remains unchanged. This package adds the contract-required inner selection table, component support and covariance-floor diagnostics, whole-query fallback maps, per-year/support descriptive tables, and leave-one-ID-out sensitivity. No model, score, parameter, acceptance threshold or selection decision was changed.

Chosen K: 1; provisional K: 2; best ES candidate: 2.

## Inner selection

K,pooled_ES,C_T0_ES,C_T1_ES,C_T0_fallback,C_T1_fallback,eligible,reason
1,171.32918435514517,155.90445055153174,182.44930068454102,0.0,0.0,True,
2,170.5623604898372,155.77502414417472,180.96117830426493,0.037853328209595964,0.03947289787550118,True,
3,170.7073596428178,155.77479420940165,181.26587235738586,0.12857934922297454,0.14607194805159873,False,C_T0:FALLBACK; C_T1:FALLBACK


## Diagnostic scope

Component histograms count retained fitted components from both complete inner windows. Fallback, restart-status and covariance-floor rates are averaged first within drifter. Floor rates condition on retained mixture fits. Restart termination status distinguishes nonconvergence and component rejection; these issues can coexist, so termination categories are not exclusive causal explanations. Descriptive outer tables average each drifter within each displayed group; these are not additional hypothesis tests. Leave-one-ID-out summaries omit one complete drifter and retain all forecasts without refitting. The common single ellipse can contain low-density gaps and is not a highest-density union.

The final-test split remained locked. The core statistical decision and all primary metrics are authoritative. The report does not claim that selecting K=1 proves unimodality, or that K>1 identifies physical flow branches.
