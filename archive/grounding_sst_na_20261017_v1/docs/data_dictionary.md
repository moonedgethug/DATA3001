# Complete column dictionary

Applies to **per-drifter-20261016-v1**. All 130 columns are retained in every ID file. This dictionary describes storage and existing rules; it does not select prediction features. See [data usage](data_layout.md) and [the authoritative contract](contract/data_contract_v1.0.xlsx).

Native meanings, units, flag attributes and NumPy types come from the frozen source/schema. Original special values are preserved. A flag is not a substitute for the independent endpoint/stopped qualification rules. In particular, `regime = 0` means undrogued, whereas source `drogue_lost_date = 0` denotes uncertain source metadata.

Role labels: `native_hourly` = acquired observation field; `native_trajectory` = repeated acquired ID-level metadata/provenance; `existing_prepared` = existing derived field; `decoded_metadata_companion` = added readable text without replacing bytes; `release_annotation` = storage/provenance annotation.

| Column | Arrow type | Role | Meaning / rule | Units / convention |
|---|---|---|---|---|
| `drogue_status` | int8 | native_hourly | Status indicating the presence of the drogue; source flag values 1,0; source flag meanings drogued, undrogued; raw product flag retained separately from corrected regime | - |
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
| `sst` | double | cleaned_official_hourly | Total SST with approved fills and anomaly repairs in this column; original values archived; unresolved NA retained | Kelvin |
| `sst1` | float | native_hourly | Fitted non-diurnal sea water temperature; frozen source fill NaN retained | Kelvin |
| `sst2` | float | native_hourly | Fitted diurnal sea water temperature anomaly; frozen source fill NaN retained | Kelvin |
| `time` | double | native_hourly | Time; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `ve` | float | native_hourly | Eastward velocity; frozen source fill NaN retained | m/s |
| `vn` | float | native_hourly | Northward velocity; frozen source fill NaN retained | m/s |
| `original_within_traj_obs` | int32 | existing_prepared | Original zero-based row position within the acquired trajectory, before time sorting. | index |
| `source_obs` | int64 | existing_prepared | Original global source observation index. | index |
| `duplicate_status` | int8 | existing_prepared | 0 representative; 1 exact duplicate; 2 conflicting duplicate. All rows retained. | code |
| `time_ok` | bool | existing_prepared | Finite source time within the existing representable bounds. | boolean |
| `analytical_row` | bool | existing_prepared | Representative duplicate status and usable time; other qualification is separate. | boolean |
| `lon_normalized` | double | existing_prepared | Position-derived longitude in [-180, 180); invalid source coordinates remain unusable. | degrees_east |
| `position_ok` | bool | existing_prepared | Finite in-range source coordinates and analytical-row eligibility. | boolean |
| `velocity_ok` | bool | existing_prepared | Both native velocity components finite; not a physical outlier adjudication. | boolean |
| `sst_ok` | bool | existing_prepared | Finite SST, source flag 4 or 5, and converted temperature from -2 to 50 Celsius. | boolean |
| `sst_celsius` | double | existing_prepared | Native absolute SST minus 273.15; use sst_ok separately. | degrees_Celsius |
| `sst1_ok` | bool | existing_prepared | Finite non-diurnal SST, source flag 4 or 5, and -2 to 50 Celsius. | boolean |
| `sst1_celsius` | double | existing_prepared | Native non-diurnal absolute SST minus 273.15; use sst1_ok separately. | degrees_Celsius |
| `sst2_ok` | bool | existing_prepared | Finite diurnal anomaly and source flag 5; negative anomalies are retained. | boolean |
| `sst2_anomaly_K` | double | existing_prepared | Native diurnal SST anomaly retained without subtracting 273.15. | Kelvin anomaly |
| `err_lon_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_lon_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_lat_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_lat_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_ve_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_ve_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_vn_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_vn_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_sst_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_sst1_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst1_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `err_sst2_ok` | bool | existing_prepared | Finite, non-negative native uncertainty; original value remains unchanged. | boolean |
| `err_sst2_negative_unresolved` | bool | existing_prepared | Native uncertainty is finite and negative; preserved unresolved special value. | boolean |
| `regime` | int8 | existing_prepared | Approved research state: 1 drogued, 0 undrogued, -1 unknown; includes official evidence corrections. | code |
| `in_R` | bool | existing_prepared | Frozen release-polygon intersection and usable position; not membership of the larger acquisition envelope. | boolean |
| `wet_high` | bool | existing_prepared | Water classification from the frozen high-resolution land mask. | boolean |
| `coast_resolution_disagreement` | bool | existing_prepared | High- and intermediate-resolution water classifications disagree. | boolean |
| `mapping_ok` | bool | existing_prepared | Usable position, water in the high-resolution mask, and no mask-resolution disagreement. | boolean |
| `geometry_uncertain` | bool | existing_prepared | Usable source position but geometric mapping not qualified. | boolean |
| `cell_1` | int32 | existing_prepared | Aligned global 1-degree position-derived cell ID; -1 if source position is unusable. D membership is separate. | index |
| `visit_cell_1` | int32 | existing_prepared | Zero-based visit number; increments on cell change, invalid cell or non-hourly interval. | index |
| `cell_05` | int32 | existing_prepared | Aligned global 0.5-degree position-derived cell ID; -1 if source position is unusable. D membership is separate. | index |
| `visit_cell_05` | int32 | existing_prepared | Zero-based visit number at 0.5 degrees, using the same gap/cell rule. | index |
| `net_displacement_km` | double | existing_prepared | WGS84 geodesic displacement from previous retained row; interval average, not an interpolated path. | km |
| `interval_net_ve` | double | existing_prepared | Eastward component of geodesic displacement divided by the actual elapsed interval. | m/s |
| `interval_net_vn` | double | existing_prepared | Northward component of geodesic displacement divided by the actual elapsed interval. | m/s |
| `elapsed_seconds_from_previous` | double | existing_prepared | Difference between consecutive retained source timestamps; first row is missing. | seconds |
| `absent_hours_before` | int32 | existing_prepared | Elapsed positive whole-hour interval minus one; -1 when undefined/non-hourly. Does not fill absent rows. | hours |
| `time_UTC` | timestamp[ms, tz=UTC] | existing_prepared | UTC datetime derived from source epoch seconds; invalid conversion remains missing. | UTC |
| `season` | int8 | existing_prepared | UTC departure season: 0 DJF, 1 MAM, 2 JJA, 3 SON; -1 when unknown. | code |
| `departure_day_UTC` | int64 | existing_prepared | Floor of source epoch seconds divided by 86400; nullable integer. | days since epoch |
| `departure_year` | int16 | existing_prepared | UTC calendar year of source time; nullable integer. | year |
| `BuoyTypeManufacturer` | binary | native_trajectory | Buoy type manufacturer | - |
| `BuoyTypeManufacturer_text` | string | decoded_metadata_companion | Exact UTF-8 decode of BuoyTypeManufacturer. Invalid decode remains null; original binary column is retained. | text |
| `BuoyTypeSensorArray` | binary | native_trajectory | Buoy type sensor array | - |
| `BuoyTypeSensorArray_text` | string | decoded_metadata_companion | Exact UTF-8 decode of BuoyTypeSensorArray. Invalid decode remains null; original binary column is retained. | text |
| `CurrentProgram` | int32 | native_trajectory | Current Program; frozen source fill -1 retained | - |
| `DeployingCountry` | binary | native_trajectory | Deploying country | - |
| `DeployingCountry_text` | string | decoded_metadata_companion | Exact UTF-8 decode of DeployingCountry. Invalid decode remains null; original binary column is retained. | text |
| `DeployingShip` | binary | native_trajectory | Name of deployment ship | - |
| `DeployingShip_text` | string | decoded_metadata_companion | Exact UTF-8 decode of DeployingShip. Invalid decode remains null; original binary column is retained. | text |
| `DeploymentComments` | int16 | native_trajectory | Deployment comments | - |
| `DeploymentStatus` | binary | native_trajectory | Deployment status | - |
| `DeploymentStatus_text` | string | decoded_metadata_companion | Exact UTF-8 decode of DeploymentStatus. Invalid decode remains null; original binary column is retained. | text |
| `DragAreaAboveDrogue` | float | native_trajectory | Drag area above drogue.; frozen source fill NaN retained | m^2 |
| `DragAreaOfDrogue` | float | native_trajectory | Drag area drogue.; frozen source fill NaN retained | m^2 |
| `DragAreaRatio` | float | native_trajectory | Drag area ratio; frozen source fill NaN retained | m |
| `DrogueBallast` | float | native_trajectory | Weight of the drogue's ballast.; frozen source fill NaN retained | kg |
| `DrogueCenterDepth` | float | native_trajectory | Average depth of the drogue.; frozen source fill NaN retained | m |
| `DrogueDetectSensor` | binary | native_trajectory | Drogue detection sensor | - |
| `DrogueDetectSensor_text` | string | decoded_metadata_companion | Exact UTF-8 decode of DrogueDetectSensor. Invalid decode remains null; original binary column is retained. | text |
| `DrogueLength` | float | native_trajectory | Length of drogue.; frozen source fill NaN retained | m |
| `DrogueType` | binary | native_trajectory | DrogueType | - |
| `DrogueType_text` | string | decoded_metadata_companion | Exact UTF-8 decode of DrogueType. Invalid decode remains null; original binary column is retained. | text |
| `FloatDiameter` | float | native_trajectory | Diameter of surface floater; frozen source fill NaN retained | cm |
| `ManufactureMonth` | int16 | native_trajectory | Manufacture month; frozen source fill -1 retained | - |
| `ManufactureSensorType` | binary | native_trajectory | Manufacture Sensor Type | - |
| `ManufactureSensorType_text` | string | decoded_metadata_companion | Exact UTF-8 decode of ManufactureSensorType. Invalid decode remains null; original binary column is retained. | text |
| `ManufactureVoltage` | int16 | native_trajectory | Manufacture voltage; frozen source fill -1 retained | V |
| `PurchaserFunding` | binary | native_trajectory | Purchaser funding | - |
| `PurchaserFunding_text` | string | decoded_metadata_companion | Exact UTF-8 decode of PurchaserFunding. Invalid decode remains null; original binary column is retained. | text |
| `SensorUpgrade` | binary | native_trajectory | Sensor upgrade | - |
| `SensorUpgrade_text` | string | decoded_metadata_companion | Exact UTF-8 decode of SensorUpgrade. Invalid decode remains null; original binary column is retained. | text |
| `SubsfcFloatPresence` | int8 | native_trajectory | Subsurface Float Presence | - |
| `Transmissions` | binary | native_trajectory | Transmissions | - |
| `Transmissions_text` | string | decoded_metadata_companion | Exact UTF-8 decode of Transmissions. Invalid decode remains null; original binary column is retained. | text |
| `WMO` | int32 | native_trajectory | World Meteorological Organization buoy identification number | - |
| `deploy_date` | float | native_trajectory | Deployment date and time; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `deploy_lat` | float | native_trajectory | Deployment latitude; frozen source fill NaN retained | degrees_north |
| `deploy_lon` | float | native_trajectory | Deployment longitude; frozen source fill NaN retained | degrees_east |
| `drogue_lost_date` | float | native_trajectory | Date and time of drogue loss; frozen source fill NaN retained; interpret through audited evidence, not a generic NaN/zero replacement | seconds since 1970-01-01 00:00:00 |
| `end_date` | float | native_trajectory | Last good date and time derived by DAC quality control; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `end_lat` | float | native_trajectory | Last good latitude derived by DAC quality control; frozen source fill NaN retained | degrees_north |
| `end_lon` | float | native_trajectory | Last good longitude derived by DAC quality control; frozen source fill NaN retained | degrees_east |
| `expno` | int32 | native_trajectory | Experiment number | - |
| `id` | int64 | native_trajectory | Global Drifter Program Buoy ID | - |
| `location_type` | int8 | native_trajectory | Satellite-based location system | - |
| `rowsize` | int32 | native_trajectory | Number of observations per trajectory | - |
| `source_obs_start_global` | int64 | native_trajectory | Derived source provenance index; not a forecast feature | not specified in source attributes |
| `source_traj_index` | int64 | native_trajectory | Derived source provenance index; not a forecast feature | not specified in source attributes |
| `start_date` | float | native_trajectory | First good date and time derived by DAC quality control; frozen source fill NaN retained | seconds since 1970-01-01 00:00:00 |
| `start_lat` | float | native_trajectory | Last good latitude derived by DAC quality control; frozen source fill NaN retained | degrees_north |
| `start_lon` | float | native_trajectory | First good longitude derived by DAC quality control; frozen source fill NaN retained | degrees_east |
| `typebuoy` | binary | native_trajectory | Buoy type (see https://www.aoml.noaa.gov/phod/dac/dirall.html) | - |
| `typebuoy_text` | string | decoded_metadata_companion | Exact UTF-8 decode of typebuoy. Invalid decode remains null; original binary column is retained. | text |
| `typedeath` | int8 | native_trajectory | Type of death | - |
| `historical_split` | string | release_annotation | Original whole-ID train/validation/test assignment, preserved as provenance. | label |
| `pool` | string | release_annotation | Current physical directory: train (development) or test (final test). | label |
| `regime_pre_official_correction` | int8 | release_annotation | Original preparation-1.0 state before the two approved official correction steps. | code |
| `regime_unknown_reason` | string | release_annotation | Null for known states; uncertain_from_start, unresolved_boundary or beyond_attached_evidence otherwise. | label |
| `regime_annotation_version` | string | release_annotation | Version(s) identifying the state annotation procedure for this ID. | provenance |
| `regime_annotation_source` | string | release_annotation | Recorded source description for the state annotation; not a fitted-model inference. | provenance |
| `official_regime_decision` | string | release_annotation | Accepted official boundary disposition; null for baseline, unresolved and the separate 44-ID fill correction (identified in the source/version fields). | label |
| `official_loss_epoch` | double | release_annotation | Documented nominal loss time where established; not a physically exact detachment time. | UTC epoch seconds |
| `official_attached_through_epoch` | double | release_annotation | Bound through which the scoped official evidence supports attachment; not a loss date. | UTC epoch seconds |

The [machine-readable schema](../configs/dataset_schema.json) retains complete native attributes. Native fixed-byte fields use Parquet binary storage with exact scalar bytes, while their original fixed-width dtype remains recorded in field metadata and the immutable source archive. Neither text decoding nor repeated scalar storage changes the scientific values.
