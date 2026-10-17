# Approved feature projection: completed

The active train/test files now contain 62 existing columns. Exactly 67
registered columns were removed following explicit user approval. The four
original uncertainty fields `err_lat`, `err_lon`, `err_ve`, and `err_vn` were
retained unchanged. No other unlisted field was removed. Historical `regime`
was already absent and was not counted as a new removal.

| Check | Result |
|---|---|
| Parent / active columns | 129 / 62 |
| IDs | 3,741, unchanged |
| Development / final-test IDs | 3,224 / 517, unchanged |
| Hourly records | 39,099,193, unchanged |
| Retained values, types, nulls, field metadata, keys and order | Exact comparison passed for all 3,741 files |
| Drogued / undrogued / unknown labels | Unchanged |
| Intentional SST NA values | 16,059, unchanged |
| Added feature columns / deleted records / new splits | 0 / 0 / 0 |
| Representative endpoint and stopped-process labels | 156,024 rows exactly unchanged |
| Automated suite | 175 tests passed |
| Independent read-only review | No critical or important findings |
| Pair-label CLI | 7-day R smoke test passed |
| Final Excel Data Contract | Same SHA-256 as parent |

## Removed active fields

**01_identity_and_provenance (3)**

`WMO`, `expno`, `CurrentProgram`.

**02_time_and_record_integrity (3)**

`time_ok`, `duplicate_status`, `analytical_row`.

**03_position_grid_and_geometry (8)**

`position_ok`, `in_R`, `wet_high`, `coast_resolution_disagreement`, `mapping_ok`, `geometry_uncertain`, `visit_cell_1`, `visit_cell_05`.

**04_velocity_and_intervals (1)**

`velocity_ok`.

**05_position_and_velocity_uncertainty (8)**

`err_lat_ok`, `err_lat_negative_unresolved`, `err_lon_ok`, `err_lon_negative_unresolved`, `err_ve_ok`, `err_ve_negative_unresolved`, `err_vn_ok`, `err_vn_negative_unresolved`.

**06_temperature_and_quality (8)**

`sst_ok`, `sst_celsius`, `sst1`, `sst1_ok`, `sst1_celsius`, `sst2`, `sst2_ok`, `sst2_anomaly_K`.

**07_drogue_state_and_evidence (7)**

`regime_pre_official_correction`, `regime_unknown_reason`, `regime_annotation_version`, `regime_annotation_source`, `official_regime_decision`, `official_loss_epoch`, `official_attached_through_epoch`.

**09_hardware_and_tracking_types (14)**

`BuoyTypeManufacturer`, `BuoyTypeManufacturer_text`, `BuoyTypeSensorArray`, `BuoyTypeSensorArray_text`, `DrogueDetectSensor`, `DrogueDetectSensor_text`, `DrogueType`, `DrogueType_text`, `ManufactureSensorType`, `ManufactureSensorType_text`, `typebuoy`, `typebuoy_text`, `SubsfcFloatPresence`, `location_type`.

**10_deployment_and_program_context (15)**

`DeployingCountry`, `DeployingCountry_text`, `DeployingShip`, `DeployingShip_text`, `DeploymentStatus`, `DeploymentStatus_text`, `PurchaserFunding`, `PurchaserFunding_text`, `SensorUpgrade`, `SensorUpgrade_text`, `Transmissions`, `Transmissions_text`, `DeploymentComments`, `ManufactureMonth`, `ManufactureVoltage`.

## Retained active fields

`drogue_status`, `err_lat`, `err_lon`, `err_sst`, `err_sst1`, `err_sst2`, `err_ve`, `err_vn`, `flg_sst`, `flg_sst1`, `flg_sst2`, `gap`, `lat`, `lon`, `sst`, `time`, `ve`, `vn`, `original_within_traj_obs`, `source_obs`, `lon_normalized`, `err_sst_ok`, `err_sst_negative_unresolved`, `err_sst1_ok`, `err_sst1_negative_unresolved`, `err_sst2_ok`, `err_sst2_negative_unresolved`, `cell_1`, `cell_05`, `net_displacement_km`, `interval_net_ve`, `interval_net_vn`, `elapsed_seconds_from_previous`, `absent_hours_before`, `time_UTC`, `season`, `departure_day_UTC`, `departure_year`, `DragAreaAboveDrogue`, `DragAreaOfDrogue`, `DragAreaRatio`, `DrogueBallast`, `DrogueCenterDepth`, `DrogueLength`, `FloatDiameter`, `deploy_date`, `deploy_lat`, `deploy_lon`, `drogue_lost_date`, `end_date`, `end_lat`, `end_lon`, `id`, `rowsize`, `source_obs_start_global`, `source_traj_index`, `start_date`, `start_lat`, `start_lon`, `typedeath`, `historical_split`, `pool`.

## Qualification compatibility and recovery

Removed eligibility and visit annotations remain in exact pre-projection
Parquet parents under `archive/feature_pruning_20261017_v1/development/` and
`archive/feature_pruning_20261017_v1/restricted_test/`. The input adapter reads
only the requested archived arrays, checks ID/pool, source observation keys and
timestamps, and leaves the normal 62-column reader result untouched. Mathematical
endpoint/stopped rules and frozen geometry were not changed.

The representative before/after comparison used development IDs 139080,
9825497 and 17503, horizons 7/30/365 days, pooled/drogued/undrogued scenarios,
and both target types. This is a regression check, not prediction validation.
All final-test files received the same predeclared projection without any
model fitting, scoring or policy selection. Default test access remains locked.

The parent configurations, exact source attributes and every original 129-column
file remain recoverable outside active data. `scope.json`, `receipt.json`,
`verification.json`, `label_equivalence.json`, and `acceptance.json` contain
the exact scope, hashes and checks. The registry and active dictionary have
been synchronized. Old migration reports remain historical and were not rewritten.
No Git commit, push or branch change was performed.

Retained fields are not automatically approved forecast inputs. In particular,
lifecycle dates and future-derived context remain subject to forecast-time
availability rules. This task does not change prior depth, annual-seasonal
support or unresolved temperature-quality limitations.
