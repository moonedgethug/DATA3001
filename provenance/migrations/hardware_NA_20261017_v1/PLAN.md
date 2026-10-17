# Seven-field hardware missing-value normalization

Authority: explicit user request on 2026-10-17 and Data Contract v1.0, clause 23.

1. Inspect all seven existing official hardware columns in all 3,741 current files.
2. Convert NaN, infinity, physically invalid negative dimensions/areas/masses/ratios and source-declared finite missing codes to typed Arrow null in those columns only. Preserve existing nulls, all zeros and every other finite value. No arbitrary upper cutoffs or imputation.
3. Preserve exactly 129 columns, all rows and order, all other 122 fields, source field attributes, corrected drogue states, SST and pool assignments. Do not introduce helper feature columns.
4. Back up affected parent files; stage and verify replacements before publication. Preserve untouched file hashes. Update canonical hashes and the explicit release policy without changing scientific contract.
5. Verify every current file, compare changed files column by column against archived parents, inspect retained zero codes and run the existing tests.

Observed before execution: 210 files contain NaN in the seven columns; no infinities, negative values or finite missing codes were found. Missingness normalization does not add measurements or prove forecast accuracy.

NA means a real nullable numeric value, not the literal string "NA". Data-frame displays may still show NaN, depending on the reader; isna() recognizes it.

Execution record: scoped audit and preflight complete. Preserve existing non-task Git changes. No commit or push.

Execution: 210 affected files published after staging/roundtrip checks; all 3741 current hashes and file constraints verified; all 172 tests passed. Independent final scoped review pending.

Final review: accepted with no material current-cohort findings. Independent review reproduced all 210 affected hardware comparisons and the public full-cohort verifier. No pending execution work.
