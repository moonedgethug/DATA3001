# Complete column dictionary

Applies to **per-drifter-cleaned-20261017-v7**. Every ID file has 62 columns after the approved removal of 67 registered fields; the redundant `regime` was removed after its exact values were copied into `drogue_status`. This dictionary describes storage and existing rules; it does not select prediction features. See [data usage](data_layout.md) and [the authoritative contract](contract/data_contract_v1.0.xlsx).

Native meanings, units, flag attributes and NumPy types come from the frozen source/schema. Original source values remain archived; current `sst` and `drogue_status` contain approved cleaning results. Source attributes describe the original product, while cleaned attributes describe the current fields. A flag is not a substitute for the independent endpoint/stopped qualification rules. In particular, `drogue_status = 0` means undrogued, whereas source `drogue_lost_date = 0` denotes uncertain source metadata.

Role labels: `native_hourly` = acquired observation field; `native_trajectory` = repeated acquired ID-level metadata/provenance; `existing_prepared` = existing derived field; `decoded_metadata_companion` = added readable text without replacing bytes; `release_annotation` = storage/provenance annotation.

| Column | Arrow type | Role | Meaning / rule | Units / convention |
|---|---|---|---|---|
| `drogue_status` | int8 | cleaned_official_hourly | Exact approved drogue state: -1 unknown, 0 undrogued, 1 drogued; copied unchanged from the former regime column; original binary flags archived | categorical |
| `err_lat` | float | native_hourly | 95% confidence interval in latitude; frozen source fill NaN retained | degrees_north |
| `err_lon` | float | native_hourly | 95% confidence interval in longitude; frozen source fill NaN retained | degrees_east |
| `err_sst` | float | native_hourly | Standard uncertainty of fitted sea water temperature; frozen source fill NaN retained | Kelvin |
| `err_sst1` | float | native_hourly | Standard uncertainty of fitted non-diurnal sea water temperature; frozen source fill NaN retained | Kelvin |
| `err_sst2` | float | native_hourly | Standard uncertainty of fitted diurnal sea water temperature anomaly; frozen source fill NaN retained | Kelvin |
| `err_ve` | float | native_hourly | 95% confidence interval in eastward velocity; frozen source fill NaN retained | m/s |
| `err_vn` | float | native_hourly | 95% confidence interval in northward velocity; frozen source fill NaN retained | m/s |
| `flg_sst` | int8 | native_hourly | Fitted sea water temperature quality flag; source flag values 0, 1, 2, 3, 4, 5; source flag meanings no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range | - |
| `flg_sst1` | int8 | native_hourly | Fitted non-diurnal sea water temperature quality flag; source flag values 0, 1, 2, 3, 4, 5; source flag meanings no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range | - |
| `flg_sst2` | int8 | native_hourly | Fitted diurnal sea water temperature anomaly quality flag; source flag values 0, 1, 2, 3, 4, 5; source flag meanings no-estimate, no-uncertainty-estimate, estimate-not-in-range-uncertainty-not-in-range, estimate-not-in-range-uncertainty-in-range estimate-in-range-uncertainty-not-in-range, estimate-in-range-uncertainty-in-range | - |
| `gap` | float | native_hourly | Time interval between previous and next location; frozen source fill NaN retained | s |
| `lat` | double | native_hourly | Latitude; frozen source fill NaN retained | degrees_north |
| `lon` | double | native_hourly | Longitude; frozen source fill NaN retained | degrees_east |
| `sst` | double | cleaned_official_hourly | Total SST with approved fills/repairs; numeric NA after valid official last-good time for eventual-grounding IDs; no refilling of that interval; originals archived | Kelvin |
| `time` | double | native_hourly | Time; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `ve` | float | native_hourly | Eastward velocity; frozen source fill NaN retained | m/s |
| `vn` | float | native_hourly | Northward velocity; frozen source fill NaN retained | m/s |
| `original_within_traj_obs` | int32 | existing_prepared | Original zero-based row position within the acquired trajectory, before time sorting. | index |
| `source_obs` | int64 | existing_prepared | Original global source observation index. | index |
| `lon_normalized` | double | existing_prepared | Position-derived longitude in [-180, 180); invalid source coordinates remain unusable. | degrees_east |
| `err_sst_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_sst1_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst1_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_sst2_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst2_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `cell_1` | int32 | existing_prepared | Aligned global 1-degree position-derived cell ID; -1 if source position is unusable. D membership is separate. | index |
| `cell_05` | int32 | existing_prepared | Aligned global 0.5-degree position-derived cell ID; -1 if source position is unusable. D membership is separate. | index |
| `net_displacement_km` | double | existing_prepared | WGS84 geodesic displacement from previous retained row; interval average, not an interpolated path. | km |
| `interval_net_ve` | double | existing_prepared | Eastward component of geodesic displacement divided by the actual elapsed interval. | m/s |
| `interval_net_vn` | double | existing_prepared | Northward component of geodesic displacement divided by the actual elapsed interval. | m/s |
| `elapsed_seconds_from_previous` | double | existing_prepared | Difference between consecutive retained source timestamps; first row is missing. | seconds |
| `absent_hours_before` | int32 | existing_prepared | Elapsed positive whole-hour interval minus one; -1 when undefined/non-hourly. Does not fill absent rows. | hours |
| `time_UTC` | timestamp[ms, tz=UTC] | existing_prepared | UTC datetime derived from source epoch seconds; invalid conversion remains missing. | UTC |
| `season` | int8 | existing_prepared | UTC departure season: 0 DJF, 1 MAM, 2 JJA, 3 SON; -1 when unknown. | code |
| `departure_day_UTC` | int64 | existing_prepared | Floor of source epoch seconds divided by 86400; nullable integer. | days since epoch |
| `departure_year` | int16 | existing_prepared | UTC calendar year of source time; nullable integer. | year |
| `DragAreaAboveDrogue` | float | native_trajectory | Drag area above drogue.; missing values normalized to numeric NA in this column; finite values and zeros retained | m^2 |
| `DragAreaOfDrogue` | float | native_trajectory | Drag area drogue.; missing values normalized to numeric NA in this column; finite values and zeros retained | m^2 |
| `DragAreaRatio` | float | native_trajectory | Drag area ratio; missing values normalized to numeric NA in this column; finite values and zeros retained | m |
| `DrogueBallast` | float | native_trajectory | Weight of the drogue's ballast.; missing values normalized to numeric NA in this column; finite values and zeros retained | kg |
| `DrogueCenterDepth` | float | native_trajectory | Average depth of the drogue.; missing values normalized to numeric NA in this column; finite values and zeros retained | m |
| `DrogueLength` | float | native_trajectory | Length of drogue.; missing values normalized to numeric NA in this column; finite values and zeros retained | m |
| `FloatDiameter` | float | native_trajectory | Diameter of surface floater; missing values normalized to numeric NA in this column; finite values and zeros retained | cm |
| `deploy_date` | float | native_trajectory | Deployment date and time; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `deploy_lat` | float | native_trajectory | Deployment latitude; frozen source fill NaN retained | degrees_north |
| `deploy_lon` | float | native_trajectory | Deployment longitude; frozen source fill NaN retained | degrees_east |
| `drogue_lost_date` | float | native_trajectory | Date and time of drogue loss; frozen source fill NaN retained; interpret through audited evidence, not a generic NaN/zero replacement | seconds since 1970-01-01 00:00:00 |
| `end_date` | float | native_trajectory | Last good date and time derived by DAC quality control; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `end_lat` | float | native_trajectory | Last good latitude derived by DAC quality control; frozen source fill NaN retained | degrees_north |
| `end_lon` | float | native_trajectory | Last good longitude derived by DAC quality control; frozen source fill NaN retained | degrees_east |
| `id` | int64 | native_trajectory | Global Drifter Program Buoy ID | - |
| `rowsize` | int32 | native_trajectory | Number of observations per trajectory | - |
| `source_obs_start_global` | int64 | native_trajectory | Derived source provenance index; not a forecast feature | not specified in source attributes |
| `source_traj_index` | int64 | native_trajectory | Derived source provenance index; not a forecast feature | not specified in source attributes |
| `start_date` | float | native_trajectory | First good date and time derived by DAC quality control; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `start_lat` | float | native_trajectory | Last good latitude derived by DAC quality control; frozen source fill NaN retained | degrees_north |
| `start_lon` | float | native_trajectory | First good longitude derived by DAC quality control; frozen source fill NaN retained | degrees_east |
| `typedeath` | int8 | native_trajectory | Type of death | - |
| `historical_split` | string | release_annotation | Original whole-ID train/validation/test assignment, preserved as provenance. | label |
| `pool` | string | release_annotation | Current physical directory: train (development) or test (final test). | label |

The [machine-readable schema](../configs/dataset_schema.json) retains complete native attributes. Removed fields and their native attributes remain in the exact archived parent files. The four original position/velocity uncertainty values remain active; derived QC annotations removed from active storage remain available for qualification audits.
