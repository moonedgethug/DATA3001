# Hardware specification source-recovery audit

## Decision

No active data were changed. All 210 IDs with incomplete hardware metadata were reviewed against frozen official NOAA specification snapshots. None of the 481 missing ID/field combinations met the approved restoration criteria. All remain numeric NA in their original columns. This is an evidence-based no-change result, not evidence that the missing values can never be recovered.

## Scope and outcome

| Check | Result |
|---|---:|
| Scoped IDs | 210 |
| Missing ID/field combinations | 481 |
| Exact ID matches in both official specification tables | 191 |
| Missing fields within those exact matches, also empty in official records | 444 |
| IDs requiring an unverified cross-identifier mapping | 19 |
| Missing fields among those 19 IDs | 37 |
| Accepted restorations | 0 |

The official drifter and drogue CSVs were cross-checked against separately parsed HTML copies. Their scoped rows agree. The CSV headers explicitly identify the field names and units; no unit conversion was guessed. Every current trajectory hash still matches the v6 manifest. Independent read-only review accepted the audit with no material findings and reproduced the complete ID/field inventory, source checks and data preservation results.

## Why values were not copied

1. **The official record is also incomplete.** The 191 exact ID matches contain no recorded replacement for their 444 missing fields. A manufacturer/model name alone cannot reconstruct a specification absent from the official record.
2. **A similar ID is not a proven identity mapping.** Nineteen current long-form IDs have plausible shorter-ID candidates. Matching the final digits is used only to locate candidates, never as an accepted joining rule. The evidence log also records WMO, manufacturer/model and directory information. No current ID was renamed or replaced.
3. **The only positive replacement candidate has unresolved conflicts.** Current ID `300534061551860` has seven candidate values under official ID `61551860` (WMO 4402879, source manufacturer SIO, model BD2GHI). The native manufacturer/model are blank and the original `SubsfcFloatPresence=1` conflicts with the candidate official record `No`. This candidate is not accepted; neither the seven NA fields nor the Boolean field were changed.
4. **Some exact matches have a WMO discrepancy.** Thirteen older IDs use different WMO representations in the source tables. These are recorded explicitly, not silently reformatted. Their missing target fields are blank in the official records anyway.
5. **Generic manufacturer specifications are insufficient.** No inspected manufacturer family information explicitly certified these historical ID-specific configurations. A product-family name or same-model sample consistency is not treated as a manufacturer-certified measurement.

## Missingness retained

| Existing field | IDs with NA |
|---|---:|
| `DragAreaAboveDrogue` | 95 |
| `DragAreaOfDrogue` | 101 |
| `DragAreaRatio` | 101 |
| `DrogueBallast` | 164 |
| `FloatDiameter` | 6 |
| `DrogueCenterDepth` | 4 |
| `DrogueLength` | 10 |

## Preserved data

- Active release remains `per-drifter-cleaned-20261017-v6`.
- All 3,741 current trajectory file hashes are unchanged: 39,099,193 rows and 129 columns.
- No feature columns, inferred values, row deletions, zero recodings, drogue-state changes, SST changes or train/test reassignment were introduced.
- Final Data Contract SHA-256 remains `6cfa91471a1399a9c3a1a8edfeb2e18cea17e0f4031ef0f8ca604ca4565a2446`.
- Unknown or conflicting hardware metadata do not automatically invalidate an otherwise eligible position pair.

## Inspectable evidence

- [One row per audited ID](../provenance/runs/hardware_source_recovery_20261017_v1/per_ID_audit.csv): original manufacturer/model, official candidates, identity checks and unresolved evidence.
- [One row per missing ID/field](../provenance/runs/hardware_source_recovery_20261017_v1/per_field_audit.csv): all 481 keep-NA decisions and reasons.
- [Complete source evidence](../provenance/runs/hardware_source_recovery_20261017_v1/evidence.json), [summary](../provenance/runs/hardware_source_recovery_20261017_v1/summary.json), [replayable audit](../provenance/runs/hardware_source_recovery_20261017_v1/audit.py).
- Downloaded NOAA source bytes, retrieval timestamps, URLs and SHA-256 receipts are stored under `provenance/runs/hardware_source_recovery_20261017_v1/sources/`, outside active data.

## Source and coverage limits

- [NOAA drifter specifications](https://www.aoml.noaa.gov/phod/dac/Drifter_Specifications.html) and [CSV](https://www.aoml.noaa.gov/ftp/pub/phod/pazos/deplog/Drifter_Specifications.csv).
- [NOAA drogue specifications](https://www.aoml.noaa.gov/phod/dac/Drogue_Specifications.html) and [CSV](https://www.aoml.noaa.gov/ftp/pub/phod/pazos/deplog/Drogue_Specifications.csv).
- [NOAA drifter directory](https://www.aoml.noaa.gov/phod/dac/dirall.html).
- A search-indexed Pacific Gyre SVP datasheet was considered as a generic lead, but direct retrieval returned HTTP 404. It was not accepted as per-ID restoration evidence; the failed request is recorded.
- The NOAA hourly ERDDAP metadata request timed out and was not used as evidence. The first drifter CSV request failed; its successful retry supplied the frozen CSV.
- No exhaustive claim is made about unpublished manufacturer records or every historical source on the internet. Recovery can be reopened if exact ID/configuration evidence or an authoritative identifier crosswalk becomes available. No prediction accuracy is evaluated.
