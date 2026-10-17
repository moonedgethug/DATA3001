# Three-corner coastal SST reconstruction

## Approved decision and scope

The user approved two routes on 17 October 2026: use linear triangular
interpolation when a drifter position is inside the three available source
corners; otherwise use the original bilinear weights restricted to the three
available corners and normalized to sum to one. The second route is an
outside-triangle estimate, not evidence of equivalent accuracy. Neither route
has been established as optimal by the approval alone.

Data Contract v1.0 remains authoritative. Its frozen SHA256 is
`6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
This is an incremental, retrospective covariate reconstruction on top of
`sst_reconstruction_20261016_v1`. Preserve canonical tracks, all 130 fields,
the baseline run, labels, source standard errors and whole-ID pools. Do not
change GDP `sst1` or `sst2`, acquire new data, fit a destination model, commit
or push. Work in the user's current checkout, retaining its existing work.

Only baseline-unknown rows whose primary reason is the coastal-stencil
refusal are candidates. Exactly three of their four cached same-date OISST
corners must be finite after source-specific decoding. Four-corner, two-corner,
one-corner, mapping-unqualified and high-temperature-quarantine cases are not
part of this change. Native finite values previously rejected by existing QC
remain unmodified; only their separate reconstructed covariate may change.

## Equations and admission

Use the existing normalized cell coordinates `(u, v)` and the four source
centres `(0,0), (1,0), (0,1), (1,1)`. For available vertices, solve
`sum(lambda_i * vertex_i) = (u,v)` and `sum(lambda_i) = 1`.
If every lambda is at least `-1e-12`, treat the position as inside or on the
triangle, clip only floating-point-scale negative weights, renormalize, and
use `sum(lambda_i * T_i)`. Boundary positions use this first route.

Outside the triangle, retain bilinear weights
`((1-u)(1-v), u(1-v), (1-u)v, uv)`, discard the missing corner and divide
the others by their sum. A retained sum at or below `1e-12` is numerically
unsupported, not a temperature estimate. This numerical tolerance is not a
validated physical-support threshold. Retain the original available weight
sum and the weighted-centroid displacement as diagnostics.

The existing target position/mapping qualification must pass. Both frozen
GSHHG masks must classify the convex hull of the target and the three source
centres as water; this retains the no-cross-land requirement while removing
the missing land corner from the old full-rectangle test. Any land intersection
or mask conflict is a documented refusal, not a guessed correction. Do not
interpolate across the longitude seam under this extension. No radius search,
new neighbours, maximum-temperature fill, temporal extrapolation or learned
correction is added.

Apply source-only uncertainty propagation using the selected nonnegative
weights and the three source SDs. All three required SDs must be valid. The
weighted SD sum is an upper bound for source error with unspecified covariance;
it omits interpolation and representation errors. Total reconstructed SE
remains unknown.

## Evidence and validation

Reuse only the frozen development masking cases for method assessment. On
cases with four finite source temperatures and an accepted all-water stencil,
artificially remove each corner in turn. Compare the two routes, the approved
hybrid, full-stencil OISST and the maximum-corner proposal against retained GDP
temperature, with identical masks for paired comparisons. Report route,
season and R strata plus unique-ID counts. Keep every variant of an ID within
the development pool; final-test values do not select methods or parameters.

This is a simulated missing-corner diagnostic on previously accepted stencils,
not validation against independent coastal truth or a recreation of all real
coastal missingness. GDP and OISST may share source observations. Report actual
candidate geometry/weight support separately. No prediction-accuracy claim
follows from reconstruction agreement or semantic tests.

## Implementation and acceptance checklist

- [ ] Verify current contract, canonical manifest and baseline source receipts.
- [ ] Write and observe failing tests for barycentric geometry, outside estimates,
  zero support, missing-corner rotations and refusal to overwrite known values.
- [ ] Add independent three-corner primitives without modifying the hash-pinned
  baseline module or baseline run.
- [ ] Run semantic tests, then compute a new run under
  `results/runs/sst_coastal_extension_20261017_v1` with candidate and refusal ledgers.
- [ ] Emit complete replacement temperature sidecars for changed IDs only;
  inherit other IDs' temperature sidecars from the explicitly named baseline.
  Provide a reader that joins the temperature view with every canonical field.
- [ ] Check every canonical file hash and schema; verify the baseline run files,
  unchanged rows, sidecar keys, pool membership, formula outputs and error bounds.
- [ ] Save a concise English report with added coverage, unresolved records,
  validation limits, real worked cases, exact dependencies and read instructions.
- [ ] Update the existing data-layout reading entry; do not alter source assets,
  the feature drop decisions, research eligibility or Git history.

Implementation units: `src/data3001/sst_coastal.py` owns formulas and safe
sidecar updates; `src/data3001/sst_coastal_run.py` owns execution, ledgers and
verification; `tests/test_sst_coastal.py` owns scientific/merge regression tests.
The frozen baseline source is reused, not edited. Execute tests with
`.venv/bin/python -m unittest discover -s tests -p 'test_sst_coastal.py' -v`,
then execute the new module and the complete existing test suite. Final success
requires verification of real outputs, not test counts alone.
