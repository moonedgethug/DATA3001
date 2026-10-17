# Recovery-tail exclusion and SST anomaly review

Authority: Data Contract v1.0 (SHA256 `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`), clauses 09, 18, 23 and 26, plus the user's 2026-10-17 instructions to remove vessel-recovery tails from model inputs and replace demonstrably anomalous SST using official matched temperatures.

## Decisions

- Preserve the source release and its 130 columns byte-for-byte. Delete recovery tails from the active model-facing reader, not the source evidence. For `typedeath == 2`, retain observations only through the numeric official `end_date`, inclusive. This is a conservative last-good-time cutoff, **not an inferred pickup timestamp**. Keep earlier valid drift. Unknown or inconsistent termination metadata must stop processing rather than silently invent a cutoff. Recovery is censoring, never a natural destination or an outside-domain transition.
- Recheck all 3,741 retained trajectories, both pools, using the same fixed rules. Do not use prediction outcomes, final-test scores or fitted thresholds. Preserve all split assignments.
- SST screening triggers: accepted native total SST above 40 C, below -2.05 C (the 0.05 C margin avoids float32 roundoff near -2 C), or either side of a change greater than 5 K across a positive interval no longer than one hour. These are **review triggers**, not automatic error labels. Review the existing 262 quarantined >45 C values too.
- Match actual observation coordinates to the same UTC date of NOAA OISST v2.1 final. Verify actual coordinates, daily timestamps, packing, fill values, product version and response hashes. This is a daily-background comparison, **not an exact hourly measurement** or independent sensor truth. Reuse source bytes where available; acquire only missing subsets. Reuse approved four/three/two/one-source interpolation without land-path vetoes.
- Automatically replace a >45 C native value only when a finite matched official background is in [-3,40] C and is at least 5 K cooler. Keep source total/components/errors unchanged; update the working SST and reconstruction provenance. A discrepancy alone at lower temperatures is insufficient for automatic replacement: retain its comparison and disposition for review. Neither lower-quality component flags nor a large native error alone proves a total-SST error.
- Exclude recovery-tail rows before model use regardless of whether they have a finite original or reconstructed temperature. Do not replace their SST merely to make them usable. Existing grounding semantics and model targets are unchanged.

## Implementation and acceptance

1. Add tests for inclusive numeric cutoffs, float precision, missing/contradictory metadata, preservation of ordinary trajectories, SST trigger boundaries and non-automatic replacement of ordinary ocean variability.
2. Implement pure review/exclusion functions and a versioned, source-receipted run. Save per-record exclusions, per-record SST comparisons, all replacement decisions and source metadata. Patch only explicitly reviewed working-temperature keys.
3. Make the current model-facing temperature reader apply the verified new temperature view and remove recovery-tail rows by default. Keep the source reader explicitly unfiltered. No old prepared label ledger is promoted to current: regenerate model labels from the filtered trajectories, so removed rows cannot become endpoints or paths.
4. Verify every native file hash, exact whole-ID pools, no changed original feature values, complete per-ID temperature joins and independent recomputation of each replacement. Run the complete test suite and actual-reader cases for recovered, high-temperature, ordinary and final-test trajectories. Do not fit a destination model in this task.

No new beaching model, object calibration, machine-learning architecture, seasonal support claim or 365-day accuracy claim is introduced. The recommended first modelling step remains an empirical destination-probability baseline followed by a validated seasonal transport operator; the model family and lag are not claimed to have been fitted or frozen by this data-cleaning amendment.
