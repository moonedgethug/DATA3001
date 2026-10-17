# Pilot SST completion: authorized scope

The user approved this incremental work on 17 October 2026:

1. Reconstruct the 795 remaining pilot-R observations with four finite OISST
   source temperatures using the existing bilinear equation. The user explicitly
   waived the former all-water-stencil refusal for these keys. Preserve target
   position/QC admission, source decoding, the original values and the geometry
   diagnostics. This approval is not independent evidence of coastal accuracy.
2. Investigate finer official SST for the remaining 81 coastal pilot observations
   (45 two-corner and 36 three-corner cases). If qualified source data exist,
   estimate the background temperature directly or with bilinear / inside-triangle
   linear / outside-triangle normalized weights. Do not change the high-temperature
   quarantine or the two position-mapping cases in this task.
3. Investigate how confirmed grounding should affect training and outcome labels;
   do not delete raw rows, discard an entire ultimately grounded ID, infer a
   grounding hour from a trajectory-level death code, or add a new absorbing
   outcome to the frozen research contract without a separate definition.

The source of truth remains Data Contract v1.0, SHA256
`6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
Preserve all canonical ID files, 130 fields, 39,107,061 rows, existing temperature
runs, whole-ID pools, source flags and source uncertainty fields. Use a new run
and a complete, versioned reading path. No Git commit or push is requested.

## Finer-source admission

Use only an official NOAA provider with actual metadata and actual coordinate
arrays. Freeze the variable, delivered version, day/night meaning, coordinate
order, packing, fills and quality conventions before use. Same-date daily fields
are retrospective background covariates, not recovered hourly sensor readings.
Do not silently claim equivalence between differently named products or fill a
temperature from a climatology/anomaly variable. New source error fields must
not be substituted for GDP standard errors; absent fine-source uncertainty
remains unknown.

First examine only the 7 UTC dates and two small windows needed for the 81
remaining coastal rows. Check direct coordinate matches or bracket the target
using actual source coordinates. Four valid corners use bilinear weights;
three valid corners use the approved triangle / normalized equations. Target
mapping must remain qualified. Retain geometry-risk diagnostics for four-corner
estimates; for three-corner estimates retain the prior no-cross-land support
gate. Zero, one or two valid fine-grid corners remain unresolved. Do not start
a larger-neighbour or temporal extrapolation method under this authorization.

Use a small deterministic selection of the existing development-only GDP masking
references for an additional fine-source diagnostic; freeze those keys before
fetching their values. Compare source estimates against the same native
references and existing OISST values where available. This is reconstruction
agreement with potentially shared source observations, not independent truth
or proof of better destination forecasts. Do not fit a correction or select a
threshold using final-test data. Network failure is an explicit unavailable
source result, never a generated temperature.

## Execution and verification

- Select the exact 795 four-corner and 81 remaining coastal keys by anti-joining
  the existing changed-key ledger; do not resample or broaden their scope.
- Cache exact source responses, URLs, retrieval times and SHA256 values.
- Use methods 6 (authorized coastal OISST four-corner), 7 (fine exact-point),
  8 (fine bilinear), 9 (fine triangle), and 10 (fine normalized outside triangle).
  Keep method/source identity outside the default model predictor selection.
- Change only previously unknown derived temperature-sidecar keys, retaining
  complete sidecars for affected IDs and inheriting other IDs from the prior run.
- Check every new formula, preserved rows, original file hashes, parent run
  hashes, units, source times, temperature components/errors and ID assignments.
- Report added coverage, unavailable-source cases and geometry flags separately;
  temperature unknowns do not themselves remove otherwise valid position pairs.
- Explain grounding policy and any remaining unconfirmed event timing to the
  user. Do not implement an unapproved beaching target or a destructive deletion.
