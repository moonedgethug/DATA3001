# Step 5 E1: full seven-day conditional Gaussian comparison

All 33,971 outer development starts and 45 drifters were retained. The fitting pool contains265,393 pairs/338 IDs from2001–2019; development validation is2020–2022. Locked final-test data were not accessed. The approved resource-only amendment changed limits, not the scientific design.

The Gaussian is a local analytic conditional transition kernel. It fits the same unchanged donor endpoints as the empirical controls, represented in a query-centred WGS84 metric chart. Mean and full covariance are Gaussian MLEs with n in the covariance denominator. No donor displacement transfer, regularisation, variance inflation, CI addition to G, land rejection or missing-support fallback was introduced. There are no epochs or neural optimiser in this experiment.

## Full results

|Model|ES km|H90|Mean area km²|Land mass|Outside-D mass|
|---|---:|---:|---:|---:|---:|
|ExactPoint|134.22322568|0.91392133|215666.8894|0.00000000|0.00000000|
|EndpointCI|134.22318762|0.91397276|215723.9006|0.00000064|0.00000000|
|LocalGaussian|134.77652632|0.91544955|216104.2291|0.00598664|0.00296933|

## Paired contrasts and decision

baseline,es_delta,es_relative,es_lower,es_upper,hit_delta,hit_lower,hit_upper,area_ratio,area_lower,area_upper,land_delta,outside_delta,es_benefit,quality_preserved,statistical_guardrails,geographic_guardrails,eligible,hit_numerical_uncertainty,area_ratio_numerical_drift,land_difference_three_se,outside_difference_three_se,es_improvement_numerically_resolved,hit_direction_resolved,area_direction_resolved,geographic_guardrails_resolved,regions_nondegenerate,superiority_claim_allowed
ExactPoint,0.5533006387046373,0.004122242152143,-1.4075792391333548,2.6263209158844067,0.0015282202716509,-0.0026633815785622,0.0064650761105178,1.0020278481174396,0.9894553318398452,1.0157367160331152,0.0059866416006469,0.0029693278753617,False,False,True,True,False,0.0001219866897724,3.365517170728083e-06,1.0874215670671834e-05,7.311941708294778e-06,False,True,False,True,True,False
EndpointCI,0.5533387026938499,0.0041225269084423,-1.4075441811856906,2.6263938287149,0.0014767900613279,-0.0027284659851526,0.0064355864940503,1.0017630332389524,0.9891891843272372,1.015462210678994,0.005986002500558,0.0029693278753617,False,False,True,True,False,0.0001908324347524,8.710319504112718e-06,1.087454861601828e-05,7.311941708294778e-06,False,False,False,True,True,False


Decision: **NO_SUPPORTED_NONDEGRADING_IMPROVEMENT**. No default was automatically replaced. G−ExactPoint is primary; G−EndpointCI cannot establish a superiority claim unless the primary ES criterion passes. A smaller region with lower observed coverage is a trade-off.

EndpointCI retained 15816 unavailable-error training pairs out of 265393 as point components with full votes. The reported fallback mass is query- and drifter-weighted, not this unweighted training fraction.

## Scoring, uncertainty and audit

ES uses the common full forecast law and zero-height WGS84 ECEF chord distance in kilometres. A/C retain the independently calibrated squared-distance control variate; G uses eight independent scrambled Sobol replicates. The nominal90% regions use the same LAEA mean/covariance and own-law Mahalanobis quantile ellipse. Regions are neither highest-density nor minimum-area sets;0.5° cells are display only. All six maps use predetermined keys and identical per-example extents and colour scales.

Evaluation averages times within each drifter, then all45 drifters equally. Fitting remains equal by selected pair. Paired intervals use10,000 whole-ID bootstrap draws at seed20261109 and fixed forecasts, omitting refitting uncertainty. The repeatedly inspected outer period supplies development evidence, not an independent final test.

The full Gaussian parameter set was independently reconstructed. All three region and ES calculations were repeated with separate arithmetic paths and numerical streams. Fixed128 outer keys additionally received exhaustive donor reconstruction and independent IID Gaussian ES checks. All numerical gates were checked before scientific claims. Auxiliary mean-squared diagnostics use two independent numerical mean estimates to avoid squared Monte Carlo bias. Geographical prediction mass is retained and reported; it is not reinterpreted as observed first-exit or grounding.

Complete per-ID aggregates, descriptive year/support/share strata, area quantiles and leave-one-ID-out sensitivities accompany this report. Model metadata, full local parameters and donor lineage are saved in the model manifest and parameter bundles. Raw data and prior experiment outputs remain referenced and immutable.
