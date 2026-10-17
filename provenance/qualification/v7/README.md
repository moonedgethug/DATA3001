# Portable qualification evidence and data publication

As of 18 October 2026, main contains the actual 3,741 current Parquet files:
3,224 in data/train and 517 in data/test, with 39,099,193 rows and 62 columns.
All 3,741 Git blob hashes match the exact existing files. No data value, row,
column, missingness decision, split or scientific rule changed during upload.
Seven bounded pushes published 3,750,136,787 bytes of active data.

These qualification files are exact projections of previously audited
annotations: id, source_obs, time, analytical_row, position_ok, mapping_ok, in_R
and visit_cell_1. They are analysis-eligibility evidence, not additional
features in data/train or data/test. All values, types, nulls and source keys
were compared with the complete archived parent and with current track keys.

configs/qualification_manifest.json binds each file, its pool and checksum
to the unchanged current dataset manifest. Development and restricted_test
remain separate and the normal reader still denies test access by default.
The pair adapter reads these arrays in memory without adding data columns.
Full historical parents remain local and available for deeper migration audits.

A clean-download simulation with no original raw cache or complete parent
passed verify-data for all files, all 180 tests, the pair command at 7/30/365
days and saving a new pair run. An additional exact comparison preserved all
156,024 representative endpoint/stopped rows from the pre-publication baseline.
These are distribution and regression checks, not fitted-model validation.

See publication_receipt.json, export_receipt.json and download_acceptance.json
for hashes, commit receipts and scope. recorded_export.py preserves the
executed projection procedure. Use docs/getting_started.md for teammate setup.
