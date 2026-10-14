# DATA3001 Phase 1 Region and Data Audit

## Status

This is a screening audit, not the final model dataset. It tests whether the three proposed functional zones have enough independent drifter trajectories to justify further work.

## Source and grain

- Source: NOAA Global Drifter Program six-hour ragged trajectory collection
- DOI: `10.25921/7ntx-z961`
- Source version: `version May 2025. Metadata from dirall.dat and deplog.dat`
- Coverage: `1979-02-15:00:00:00Z` to `2025-06-12:06:00:00Z`
- Source trajectories: `28,728`
- Source observations: `48,887,074`
- Audit grain: unique trajectory within a proposed zone, plus unique trajectory per 1° origin cell

An entering trajectory has at least one finite position inside a zone. A 7-day or 30-day-valid trajectory has at least one origin inside the zone and a finite position at the exact horizon on the same six-hour trajectory. The future endpoint may be outside the zone. Leaving a zone is therefore not misclassified as data loss.

## Preliminary screening boundaries

- **North-Central Gulf:** 25.0–30.0°N, 92.5–85.0°W
- **Florida-Bahamas:** 22.5–30.0°N, 85.0–75.0°W
- **Gulf Stream Corridor:** a non-rectangular corridor from offshore Florida to approximately 42.5°N in the western North Atlantic; exact vertices are recorded in `region_data_audit.py`

These are non-overlapping analytical screening zones, not claims that ocean-current systems have hard boundaries.

## Core results

| Region | Entering | Valid 7d | Valid 7d (%) | Valid 30d | Valid 30d (%) | Drogued valid 30d | 1° cells >=25 valid 30d | 1° cells touched | Median valid 30d per touched cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| North-Central Gulf | 288 | 278 | 96.5 | 225 | 78.1 | 110 | 30 | 40 | 51.0 |
| Florida-Bahamas | 782 | 736 | 94.1 | 613 | 78.4 | 376 | 42 | 71 | 56.0 |
| Gulf Stream Corridor | 1117 | 1092 | 97.8 | 1044 | 93.5 | 711 | 127 | 137 | 132.0 |


## BOEM platform overlap

The BOEM/BSEE federal OCS layer contains **1,108 platform points without a removal date** inside the North-Central Gulf screening box. Of these, **1,108** fall in a 1° cell touched by at least one audited drifter trajectory. These points are application-context evidence, not drifter observations. **11** 1° cells contain at least one such platform and at least 25 unique 30-day-valid drifter trajectories. State-water facilities are outside the layer's stated scope.

The overlap table is saved as `north-central-gulf-platform-cell-overlap.csv`. Candidate source cells should be selected from this table only after checking temporal and experiment concentration.


### Platform-cell resolution comparison

| Grid | Minimum valid 30d | Qualifying platform cells | Platforms in qualifying cells | Share of 1,108 platforms |
| --- | ---: | ---: | ---: | ---: |
| 0.5° | 10 | 27 | 255 | 23.0% |
| 0.5° | 25 | 15 | 41 | 3.7% |
| 0.5° | 50 | 0 | 0 | 0.0% |
| 1° | 10 | 15 | 761 | 68.7% |
| 1° | 25 | 11 | 183 | 16.5% |
| 1° | 50 | 5 | 34 | 3.1% |

`Platforms in qualifying cells` means platform points located inside a cell that meets the stated trajectory threshold. It is not a spill count or an additional trajectory count.


## Grid-resolution sensitivity

Transition-block support changes materially with grid size. The 1° cell results above are therefore a screening view rather than a frozen model resolution.

| Region | Grid | Cells touched | Cells >=10 valid 30d | Cells >=25 valid 30d | Cells >=50 valid 30d | Cells >=25 drogued valid 30d | Median valid 30d per touched cell | Median drogued valid 30d per touched cell |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| North-Central Gulf | 0.25° | 561 | 434 | 162 | 0 | 0 | 19.0 | 8.0 |
| North-Central Gulf | 0.5° | 144 | 118 | 92 | 28 | 28 | 32.5 | 15.0 |
| North-Central Gulf | 1° | 40 | 36 | 30 | 21 | 19 | 51.0 | 23.5 |
| North-Central Gulf | 2° | 15 | 15 | 13 | 10 | 9 | 75.0 | 34.0 |
| Florida-Bahamas | 0.25° | 891 | 517 | 379 | 217 | 233 | 16.0 | 9.0 |
| Florida-Bahamas | 0.5° | 245 | 156 | 125 | 100 | 106 | 27.0 | 16.0 |
| Florida-Bahamas | 1° | 71 | 51 | 42 | 37 | 37 | 56.0 | 33.0 |
| Florida-Bahamas | 2° | 24 | 21 | 19 | 17 | 17 | 105.0 | 57.0 |
| Gulf Stream Corridor | 0.25° | 1869 | 1729 | 1568 | 839 | 953 | 47.0 | 25.0 |
| Gulf Stream Corridor | 0.5° | 493 | 463 | 442 | 399 | 414 | 83.0 | 44.0 |
| Gulf Stream Corridor | 1° | 137 | 133 | 127 | 116 | 122 | 132.0 | 70.0 |
| Gulf Stream Corridor | 2° | 41 | 41 | 39 | 39 | 39 | 201.0 | 116.0 |

## Integrity checks

```json
{
  "source_trajectory_rows": 28728,
  "source_distinct_ids": 28728,
  "source_observation_rows": 48887074,
  "ragged_lengths_match": true,
  "region_counts_nested": true,
  "drogued_counts_bounded": true,
  "grid_counts_nested": true,
  "grid_drogued_counts_bounded": true
}
```

## Interpretation rules

- Counts are unique trajectories, not six-hour observations.
- A trajectory can enter more than one functional zone, so regional totals overlap and must not be summed.
- Within the cell table, a trajectory is counted once per origin cell and may appear in more than one cell if it traverses the study area.
- A 1° cell threshold of 25 valid 30-day trajectories is a transparent screening threshold, not a universal statistical guarantee.
- Destination entropy and direction concentration are exploratory dispersion proxies. They do not by themselves measure full oceanographic complexity.
- Region totals are not directly comparable without considering zone area and origin-cell support.
- Drogued-valid counts require drogue status at both the origin and horizon endpoint; they do not prove uninterrupted drogue attachment between those times.

## Evidence-based findings

1. **The statement that the North-Central Gulf has no drifter data is false for the audited NOAA dataset.** The zone contains hundreds of entering trajectories and substantial exact 7-day and 30-day support.
2. **North-Central Gulf is not automatically a high-quality release zone at every location.** Support must still be checked cell by cell, particularly near the coast and at the edges of the zone.
3. **Florida-Bahamas has more trajectories than North-Central Gulf, but raw volume alone does not make it the best first pilot.** Pilot-cell selection should require high support, acceptable trajectory concentration, and a clear application scenario.
4. **Gulf Stream Corridor has the strongest regional support in this screening geometry.** Its larger area and corridor definition contribute to the raw total, so cell-level support is the more relevant comparison.
5. **Starting with the most statistically dispersed zone is not inherently easier.** A high-support but relatively stable cell is preferable for validating the pipeline before testing more dispersed or multimodal locations.
6. **Transition-cell resolution changes the feasibility conclusion.** At 0.25°, North-Central Gulf has no cell with 50 or more unique 30-day-valid trajectories, while it has 21 such cells at 1°. The project must select cell size together with its minimum-support rule rather than after modeling begins.
7. **The 0.5° grid preserves more spatial structure but fragments the platform-source evidence.** In North-Central Gulf, no platform-containing 0.5° cell has 50 valid 30-day trajectories, and only 41 of 1,108 platform points fall in a 0.5° cell with at least 25. For a single-cell empirical pilot, 1° is the safer primary resolution; 0.5° should remain a sensitivity analysis or be used with explicit spatial pooling.

## Next decisions

- Retain the three-zone functional classification for screening, but describe it as source, transition and downstream zones rather than separate oceans.
- Carry forward two or three North-Central Gulf source-cell candidates from `north-central-gulf-platform-cell-overlap.csv`; do not select from regional totals alone.
- Review the candidate cells' season, year, experiment and drogue-status concentration before freezing one pilot cell.
- Choose the transition-cell resolution and minimum support together; retain a coarser fallback if a fine grid fragments the data.
- Use 1° for the first single-cell empirical baseline and compare it with 0.5° before any final-resolution claim.
- Confirm whether 7 and 30 days are sufficient for the intended downstream question.
- Only then freeze the first pilot cell and begin model construction.
