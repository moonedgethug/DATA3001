# Phase 1 Region Audit — Source Receipt

Retrieved and checked on 2026-09-26.

## Drifter trajectories

- Provider: NOAA Atlantic Oceanographic and Meteorological Laboratory, Global Drifter Program
- Public access page: https://www.aoml.noaa.gov/phod/gdp/data.php
- Dataset used: `s3://noaa-oar-hourly-gdp-pds/experimental/gdp6h_ragged_may25.zarr`
- DOI: `10.25921/7ntx-z961`
- Local source manifest: `source_manifest.json` in the separately maintained May 2025 audit cache
- Version recorded by the manifest: `version May 2025. Metadata from dirall.dat and deplog.dat`
- Time coverage recorded by the manifest: 1979-02-15 to 2025-06-12
- Grain: 28,728 ragged trajectories and 48,887,074 six-hour observations

NOAA states that the six-hour dataset is quality controlled and interpolated at six-hour intervals. This audit still verifies finite coordinates, finite timestamps and the exact same-trajectory 7-day or 30-day timestamp difference.

## Offshore platform context

- Provider: BOEM/BSEE
- Layer: OCS Drilling Platforms
- Layer metadata: https://gis.boem.gov/arcgis/rest/services/BOEM_BSEE/GOA_Layers/MapServer/0
- Layer scope stated by BOEM/BSEE: structures used for exploration and resource extraction in federal Outer Continental Shelf waters
- Query filter: `REMOVAL_DATE IS NULL`
- Query envelope: `-92.5,25,-85,30`
- Query result: 1,108 point features
- Stored response: `outputs/boem-current-platforms.geojson`

The platform points provide application context. They are not drifter observations, do not include state-water facilities, and do not prove that a spill occurred.

## Oceanographic framing

- NOAA Loop Current overview: https://oceanservice.noaa.gov/facts/loopcurrent.html
- NOAA Gulf Stream overview: https://oceanservice.noaa.gov/facts/gulfstreamspeed.html
- NOAA Tides & Currents Gulf Stream description: https://www.tidesandcurrents.noaa.gov/faq.html

NOAA describes the Loop Current as entering the Gulf, passing the Florida Keys and Florida Straits, joining the Gulf Stream and continuing north along the US Atlantic coast. This supports treating the three proposed zones as connected functional stages. It does not define the screening boundaries used in this audit.

## Coastline visualization

- Natural Earth 1:110m land polygons, used only as map background

## Derived outputs

- `outputs/region-audit-summary.csv`: region-level unique-trajectory support
- `outputs/region-audit-cell-support.csv`: 1° origin-cell support, temporal concentration and exploratory dispersion proxies
- `outputs/region-audit-grid-sensitivity.csv`: 0.25°, 0.5°, 1° and 2° support sensitivity
- `outputs/region-audit-grid-cell-support.csv`: cell-level support at all four audited resolutions
- `outputs/region-audit-map-0p5.png`: 0.5° support map
- `outputs/region-audit-map-0p5-vs-1deg.png`: direct 0.5° versus 1° comparison under one shared colour scale
- `outputs/north-central-gulf-platform-cell-overlap-0p5.csv`: 0.5° platform/trajectory overlap
- `outputs/north-central-gulf-platform-resolution-comparison.csv`: 0.5° versus 1° platform-cell threshold comparison
- `outputs/gulf-stream-segment-summary.csv`: unique-trajectory results for three bounded Gulf Stream candidate windows
- `outputs/gulf-stream-segment-cell-support.csv`: 0.5° and 1° support within those windows
- `outputs/gulf-stream-segment-grid-summary.csv`: comparable cell-support statistics by window and resolution
- `outputs/gulf-stream-segment-support-0p5-vs-1deg.png`: direct visual comparison of the candidate windows
- `outputs/gulf-stream-segment-audit.md`: interpretation and provisional recommendation
- `outputs/north-central-gulf-platform-cell-overlap.csv`: North-Central Gulf drifter/platform cell overlay
- `outputs/region-audit-checks.json`: structural integrity checks
- `outputs/region-audit-map.png`: screening boundaries, cell support and BOEM/BSEE platform context
- `outputs/region-audit-comparison.png`: regional comparison

All region boundaries are analytical screening choices recorded in `region_data_audit.py`; they are not official ocean-current boundaries.

Regional counts overlap when the same trajectory enters multiple functional zones and must not be summed. Cell-level counts retain one record per trajectory-origin-cell; a trajectory that traverses multiple cells can therefore contribute once to each traversed cell.
