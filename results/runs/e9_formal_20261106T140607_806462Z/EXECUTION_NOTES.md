# E9 execution and verification notes

## Material Passport

- Status: complete; both seasonal models fail the registered scientific acceptance criteria.
- The four models, full sample, votes and scientific definitions remained fixed.
- The user explicitly approved proceeding despite the twofold runtime precheck, and subsequently approved removal of the 2.5 GiB storage precheck while retaining the 5 GiB hard storage budget.

## Execution receipts

Cumulative measured execution before final sealing: 70.403 minutes, including earlier E9 pilots and all recorded failed attempts. Phase totals: pilot 3.416 min; formal 42.963 min; audit/presentation 24.024 min. Peak measured single-worker RSS: 1.027 GiB. Retained formal artifacts: 2.815 GiB. Wall time spent awaiting user decisions is not execution time. Final sealing is recorded separately in the matching provenance.

## Preserved failures and narrow repairs

1. The full donor inventory reached the 2.5 GiB storage precheck. It was preserved and reused after the user's explicit waiver; no donor selection was rerun.
2. A duplicate keyword prevented preflight metadata from being saved after its 128 checks. An isolated correction removed that duplicate, retained the failed source/output and repeated the outcome-blind checks to recover timing. Both numerical-check tables agree exactly.
3. An area-summary quantile function confused a pandas index label with an array position. Every forecast and all 135,884 case scores had already been saved. The isolated correction converts the sorting input to a NumPy array; the regression fixture reproduces the old failure and verifies the correction. Existing contrast/precision tables were reused only after byte equality, and all reported area quantiles were independently checked. No forecast or score was rerun or altered for this repair.

## Verification

The 35 semantic tests passed. All 33,971 annual donor sets match E7 and all compressed lineage records passed bitwise roundtrip checks. All selected donor seasons, radii and votes were checked, plus independent full-distance neighbour reconstruction on 128 fixed outer and 128 prior pilot cases. All 135,884 region hit/area records were replayed; all queries received a second numerical stream; 128 outer cases received separate 65,536-pair ES checks. The 10,000-draw paired bootstrap was independently reconstructed. All numerical gates passed. AnnualExactPoint reproduces the authoritative corrected E8 mean area and H90 to numerical precision.

All nine PNG figures were visually inspected. Their titles, legends, metric units, four-arm comparisons and common per-example map extents/colour scales are readable. HTML image and download references were checked structurally; no browser-rendering validation is claimed. The support histograms use evaluation-weight shares on their vertical axes.

All protected sources and inputs are unchanged. Final-test data and validation-endpoint errors were not accessed. The study is development evidence, not an independent final test. The research-stage ledger was not amended; no model was replaced, no further experiment was started, and no Git publication was performed.

See [the report](REPORT.md), [the visual review](review.html), and the matching provenance run for immutable receipts and source snapshots.
