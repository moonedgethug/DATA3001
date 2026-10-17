# Consolidate the cleaned drogue state into its original column

Authority: the user explicitly requires copying the completed `regime` values
without alteration into `drogue_status` and physically removing `regime`.

1. Freeze the v4 manifest, current source files/configurations and representative
   endpoint/stopped label fingerprints before changing data or the reader.
2. Test exact int8 three-state transfer (including -1), rejection of incomplete
   labels, removal of the redundant column, and unchanged unrelated values.
3. Stage all ID files. Preserve every row and other field, transfer the exact
   existing state values, update cleaned-field metadata and publish checksums.
4. Adapt current label generation to read `drogue_status` without recreating a
   `regime` column. Preserve historical data/code interpretation and test access.
5. Verify all 3,741 files against their parents; compare representative paired
   outputs, SST exclusions and whole-ID splits; run the complete regression suite.

No further imputation, relabelling, loss-date change, ancillary-field removal,
Data Contract content change, Git commit or push is authorized by this task.
Historical sources and qualification evidence stay outside active feature data.
