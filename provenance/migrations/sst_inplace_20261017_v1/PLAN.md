# Store approved SST cleaning in the existing column

**Authority:** User instruction: remove `sst_use_K` from active data and write approved temperature fills/corrections directly to `sst`. The Excel Data Contract and all scientific decisions remain unchanged.

- [x] Test key alignment, missing/duplicate-key rejection, preservation of unrelated fields, numerical precision and the current reader's single-column interface.
- [x] Freeze current manifests/configurations and original ID files outside `data/`; resolve and hash-check the already approved temperature evidence. No new interpolation or anomaly decisions.
- [x] Stage all 3,741 files. Replace only `sst`; retain its Kelvin units and use float64 to avoid rounding previously approved estimates. Preserve all other 129 columns, row keys/order, drogue labels and train/test assignments.
- [x] Verify staged files against the exact approved values and original remaining columns, then activate the files and update hashes/schema/index consistently. Keep a resumable publication journal.
- [x] Make ordinary and compatibility readers return the stored cleaned `sst` without adding temperature columns. Keep historical reconstruction evidence for audit only.
- [x] Update current documentation, run the complete regression suite, and independently verify every current file. Do not commit or push.

Unresolved temperature-quality cases and the 5,547 remaining NA values retain their previous decisions. No new post-grounding NA policy is introduced. Original temperature quality flags/errors and already deferred derived fields remain source audit information; this migration does not recalculate or select them.
