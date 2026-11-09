# Saved MDN prediction

From the work_place Python environment:

```python
from data3001.modelling.continuous_models.conditional_mdn_s5_e3_inference import load_selected_model
model = load_selected_model('conditional_mdn_s5_e3_20261108T055830_797628Z')
mixture = model.mixture([[-75.0, 35.0]])
endpoints = model.sample([[-75.0, 35.0]], count=1000, seed=20261126)
```

`weights`: Q×K; `means_km`: Q×K×2 east/north geodesic displacement;
`covariances_km2`: Q×K×2×2; samples: Q×count×2 longitude/latitude.
The stored scaler and completed full-refit weights are loaded. No validation
targets, raw training data or validation coordinates are needed by this API.
All components participate; land and outside-domain samples are retained.
This is a seven-day, position-only model. Prediction outside training support
is extrapolation and has not been independently validated.

Selected checkpoint: `/Users/moonedgethug/Documents/UNSW/DATA3001/work_place/results/runs/conditional_mdn_s5_e3_20261108T055830_797628Z/formal_v1/C_outer/K1/full_refit/checkpoint.pt`.
