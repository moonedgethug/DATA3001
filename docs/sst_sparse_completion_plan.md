# SST sparse-source completion implementation plan

**Authority:** The user's explicit four-point decision on 17 October 2026
supersedes the extra temperature-specific water-stencil/support-hull gates.
Data Contract v1.0 remains the research authority. This extension changes
temperature reconstruction admission only, not frozen research geometry,
trajectory/endpoint eligibility, ID pools, source QC, or native observations.

**Goal:** Reconstruct the remaining total-SST covariate using qualified official
source temperatures, without requiring interpolation paths to avoid land.

**Architecture:** A new run inherits `sst_pilot_completion_20261017_v2` and
changes previously unknown temperature-sidecar keys only. Canonical records,
all 130 native/retained fields, all 39,107,061 rows, parent runs and pools remain
unchanged. No commit/push or destructive action is requested.

## Fixed equations and scope

- Inspect all 35,984 current unknown keys in both pools. Retain original
  coordinates and actual UTC calendar-day matching. A native position must
  remain finite/valid; a land-mask conflict alone does not block temperature.
- Four finite OISST corners: unchanged bilinear interpolation.
- Three finite corners: unchanged inside-triangle linear interpolation or
  normalized available bilinear weights outside the triangle, without the
  former water-support-hull refusal. If the available bilinear weight sum is
  zero, use inverse-distance weights on the three actual available corners.
- Two finite corners: geodesic inverse-distance weights, exponent 1:
  `w1=d2/(d1+d2)`, `w2=d1/(d1+d2)`; equivalently normalize `1/d`.
  An exact valid-source coordinate has weight 1; never divide by zero.
- One finite corner: use that actual source value; explicitly mark the coarse
  one-source approximation. Do not fabricate a missing source-corner value.
- Zero finite OISST corners: inspect small official finer-source windows for
  the required dates. Actual source version, axes, units, fills and timestamps
  must be verified. Apply the same four/three/two/one rules to that stencil;
  if the enclosing fine stencil is empty, use the nearest actual finite source
  within the received 0.1-degree halo as a marked one-source approximation.
  Do not expand that search unboundedly. No value is invented if all received
  official source nodes are missing. For post-2021 dates, use the actual NOAA
  STAR CoralTemp v3.1 daily files if the small-window archive does not cover the
  date; retrieve only the three specifically needed daily files, not an archive.
- Do not overwrite the 262 previously quarantined native >45 C observations,
  including the one whose primary reason is mapping; this task addresses
  source/geometry gaps rather than resolving finite native-temperature anomalies.

## Official termination evidence

Use the retained official `typedeath` and `end_date`; do not infer grounding
from GSHHG or turn an eventual grounding category into an hourly state.
For `typedeath=1` (grounding) or `2` (vessel recovery), observations on later
UTC dates than the official last-good date are outside the retained official
last-good period and are not filled as floating-ocean records. This is not a
claim that `end_date` timestamps the first grounding/recovery instant.

On the terminal calendar date, the exact event hour is unresolved. Background
temperature may be estimated, but that timing uncertainty remains explicit in
the decision ledger and is not promoted to confirmed floating status or
training eligibility. Earlier observations retain a pre-terminal-date context,
not an independent guarantee that no earlier beaching occurred. Other official
termination categories do not prove grounding. No raw rows are removed and no
beaching absorbing state or training filter is implemented.

## Provenance and uncertainty

Use method codes 11 (four), 12 (triangle), 13 (three normalized), 14 (two
inverse-distance), 15 (one source), and 16 (three distance fallback). Keep
source node keys/coordinates/values/weights, distance, source family, and
termination context in a per-observation decision ledger. Daily background
temperature is not a recovered hourly sensor measurement. Methods are not
automatically added as model predictors.

Propagate only the available source-only SD bound `sum(abs(w)*sigma)` when
every positively weighted source provides its SD. Never equate it with total
reconstruction error. Missing uncertainty remains unknown; native components
and native error columns remain unchanged.

## Execution sequence and acceptance

1. Test source-count routes, exact-point handling, weight/value bounds, zero
   support, original-value preservation and terminal-day context before coding.
2. Verify the contract, current unknown-key audit, source caches and parent
   artifact identities; freeze the exact target list and implementation hashes.
3. Calculate/cache official-source estimates, write complete sidecars only for
   affected IDs, and inherit the current parent for all other IDs.
4. Independently recompute every added value/weight, check native bytes and all
   rows/fields/pools, verify unchanged parent sidecar rows, and reconcile counts.
5. Publish a plain-English report and current reader instructions. Report
   terminal-date uncertainty, held official post-termination records, source
   absences and finite-native quarantines separately. Coverage is not accuracy.

Use the existing repository Python environment. Execute directly in this
session, as requested by the user; no additional approval gate or agent
delegation is needed for this specified extension.
