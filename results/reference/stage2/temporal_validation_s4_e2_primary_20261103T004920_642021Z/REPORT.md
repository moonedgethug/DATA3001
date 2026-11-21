# Existing Step 1–3 models: validation-policy comparison

G uses whole-ID, calendar-mixed internal CV. T uses forward, ID-isolated internal CV. Each block uses identical final fitting data and later validation cases. This is a model-selection-policy comparison, not a new model, a physical ocean change-point test, or an untouched final test. All models retain annual pooling. Outer metrics use equal times within drifter/origin, equal drifters within origin, and equal origins. Intervals condition on fitted forecasts; training and selection uncertainty and common forcing are not fully represented. B2 equality across policies is a required control. Similarity margins do not relax the quality-preserving improvement criterion.

## Policy-selected future predictions

```csv
block,policy,horizon_days,brier,k90,h90,zero_truth,unsupported_pairs
A,G,7,0.9696852222372543,25.499999999999993,0.8164503671428818,0.015849988716880772,0
A,G,30,0.9961189425119709,123.79999999999997,0.7130399553481568,0.0383580602575098,0
A,T,7,0.9734663580795491,25.63888888888888,0.8107072313271273,0.015849988716880772,0
A,T,30,0.9966062099837625,123.17142857142855,0.6953691956266423,0.0383580602575098,0
B,G,7,0.9723878899851801,26.59459459459461,0.8008032754292689,0.009994965965537372,0
B,G,30,0.9973663662825392,100.16216216216222,0.717105783180225,0.10434007526703434,0
B,T,7,0.9721515146384245,27.459459459459453,0.8084511312667488,0.009994965965537372,0
B,T,30,0.9980003360740319,129.62162162162156,0.7387141981877641,0.0464968491160294,0
C,G,7,0.9647158103702396,27.138888888888864,0.8974173190653925,0.0,0
C,G,30,0.9958382917800065,105.99999999999997,0.7479501340512247,0.05121851260532885,0
C,T,7,0.9637477868118814,27.611111111111097,0.8985601037981088,0.0,0
C,T,30,0.9958382917800065,105.99999999999997,0.7479501340512247,0.05121851260532885,0
```

## Inner-selected models and parameters

```csv
block,policy,horizon_days,model,parameter_a,parameter_gamma,inner_selection_brier
A,G,7,LocalEndpointAdaptive,0.6,0.5,0.9611825657040501
A,G,30,Fixed,0.9,0.0,0.9955423726953008
A,T,7,LocalEndpoint,0.65,0.0,0.9622401852862421
A,T,30,Adaptive,0.9,0.0,0.9956804745231624
B,G,7,LocalEndpointAdaptive,0.6,2.0,0.9609807019402946
B,G,30,LocalEndpointAdaptive,0.85,2.0,0.9951449775316826
B,T,7,LocalEndpointAdaptive,0.75,2.0,0.9630190749114894
B,T,30,Adaptive,0.9,0.0,0.9950622592251868
C,G,7,LocalEndpoint,0.6,0.0,0.9580969156042809
C,G,30,LocalEndpointAdaptive,0.85,2.0,0.9935148981080265
C,T,7,LocalEndpoint,0.65,0.0,0.966127227244142
C,T,30,LocalEndpointAdaptive,0.85,2.0,0.9973958290414013
```

## Primary decisions

```csv
block,horizon_days,delta_brier,delta_h90,delta_k90,relative_k90,quality_point_gain,quality_supported,equivalent_supported,status
A,7,0.0037811358422947805,-0.005743135815754474,0.13888888888888573,0.005446623093681795,False,False,False,NOT_RESOLVED_OR_TRADEOFF
A,30,0.0004872674717916192,-0.01767075972151444,-0.6285714285714192,-0.005077313639510657,False,False,False,NOT_RESOLVED_OR_TRADEOFF
B,7,-0.00023637534675557959,0.0076478558374799555,0.8648648648648418,0.03252032520325115,False,False,False,NOT_RESOLVED_OR_TRADEOFF
B,30,0.0006339697914927722,0.021608415007539072,29.45945945945934,0.29411764705882215,False,False,False,NOT_RESOLVED_OR_TRADEOFF
C,7,-0.000968023558358122,0.0011427847327163398,0.4722222222222321,0.017400204708291064,False,False,False,NOT_RESOLVED_OR_TRADEOFF
C,30,0.0,0.0,0.0,0.0,False,False,True,EQUIVALENCE_SUPPORTED
```

See summary.csv, uncertainty.csv, decisions.csv, selections.csv, role_roster.csv and review.html for complete evidence.
