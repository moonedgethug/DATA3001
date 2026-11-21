# Step 5 E2: complete local Gaussian mixture experiment

Training-only selection chose K=1; candidates were 1, 2, 3. The user's explicit amendment removed the resource pilot. Integration counts were frozen at the highest registered levels before fitting: ES 65,536 per component pair; region 65,536 per component. No model or donor rule was changed.

All 86,373 inner validation starts and 33,971 outer development starts were retained. Pair-equal training and drifter-equal evaluation are distinct. The final-test data remained locked. Local mixtures fit original donor endpoints, using five deterministic constrained-EM starts, full covariance and predeclared component support/fallback rules. No MDN, displacement transfer, CI addition to GMM or environmental features were used.

## Results

model,energy_km,h90,area90_km2,land_mass,outside_D_mass,fallback,auxiliary_loss,ci_unavailable_mass,largest_id_share,independent_ids,pairs,model_mass90
EndpointCI,134.2235174020079,0.9139387434655221,215732.07819412934,6.162293584165717e-07,0.0,0.0,7.222668929403485,0.06212691519850882,0.06601104497334358,114.40900245832017,7969.271554379093,0.8999947913706019
ExactPoint,134.2235628922719,0.9139213279308652,215666.88935491562,0.0,0.0,0.0,7.222669384877331,0.06212691519850882,0.06601104497334358,114.40900245832017,7969.271554379093,0.9000013013654556
LocalGMM,134.77713493141582,0.915438158032233,216097.00986990923,0.005988467794845874,0.0029685085219103833,0.0,7.227975748546314,0.06212691519850882,0.06601104497334358,114.40900245832017,7969.271554379093,0.9000038710991937
LocalGaussian,134.77713493141582,0.915438158032233,216097.00986990923,0.005988467794845874,0.0029685085219103833,0.0,7.227975748546314,0.06212691519850882,0.06601104497334358,114.40900245832017,7969.271554379093,0.9000038710991937


## Paired comparisons

baseline,es_delta,es_relative,es_lower,es_upper,hit_delta,hit_lower,hit_upper,area_ratio,area_lower,area_upper,land_delta,outside_delta,es_benefit,quality_preserved,statistical_guardrails,geographic_guardrails,eligible,hit_numerical_error,area_numerical_error,es_numerical_error,effect_resolved,quality_resolved,fallback_pass,land_numerical_three_se,outside_numerical_three_se,sequential_superiority_allowed,independent_es_drift
LocalGaussian,0.0,0.0,0.0,0.0,0.0,0.0,0.0,1.0,1.0,1.0,0.0,0.0,False,True,True,True,False,2.2780340566091464e-05,2.360158438636397e-06,0.0,True,False,True,1.537499905192298e-05,1.0340084736071283e-05,False,0.0
ExactPoint,0.5535720391439377,0.004124253798777758,-1.365443937709361,2.5881339485743693,0.0015168301013679423,-0.002637049778792006,0.006511499637767679,1.0019943743626119,0.9895509546668692,1.015614058702391,0.005988467794845876,0.002968508521910383,False,False,True,True,False,1.1390170283045732e-05,1.1800792193181986e-06,0.002988701965240213,True,True,True,7.68749952596149e-06,5.1700423680356415e-06,False,0.00048389845125813104
EndpointCI,0.5536175294079008,0.004124594110805346,-1.3653994923751525,2.5881682877549843,0.001499414566711029,-0.0026561473919590756,0.006478567513799678,1.0016915967195732,0.9892511870093343,1.0153150259586226,0.005987851565487458,0.002968508521910383,False,False,True,True,False,1.1390170283045732e-05,4.874976342792563e-06,0.002988799416923183,True,True,True,7.688066001901654e-06,5.1700423680356415e-06,False,0.00048257634589925685


Decision: **NO_SUPPORTED_NONDEGRADING_IMPROVEMENT**. K=1 means the selected candidate is identical to the single Gaussian; it does not prove the physical destination distribution is unimodal. Components are statistical approximations, not identified current systems. A single common 90% ellipse can cover low-density gaps between components; it is not an HDR.

Fallback: {"query_fraction": 0.0, "drifter_equal_fraction": 0.0, "affected_ids": 0, "total_ids": 45, "ci_unavailable_vote_mass": 0.06212691519850882}

ES uses the complete geographic forecast in zero-height WGS84 ECEF kilometres. All probability on land and outside the domain is retained. Bootstrap uncertainty conditions on fitted forecasts and omits refitting uncertainty. The repeatedly inspected outer period is development evidence only. The independent audit reconstructs all final fit arithmetic and all outer scores/regions, and independently refits fixed subsets rather than claiming a global optimum.
