# Completed Step 5 E2 execution

The approved full experiment, independent audits, and presentation are complete. The model definition, donor records, weights, integration counts, and acceptance rules were unchanged. Final training-only selection returned K=1 after provisional K=2 failed the no-hit-decrease gate. No automatic default-model replacement or final-test access occurred.

## Recoveries retained

1. The full independent audit completed all query calculations, but its IID summary failed because mixed nullable batch columns had object dtype. Revision 5 converts the four numerical operands to float64 at that boundary. The 128 actual IID cases passed independent scalar arithmetic; 18,815 existing outputs were verified unchanged. The regression was reproduced before the fix; the complete suite then passed 763 tests. One suite attempt was interrupted by a resource-monitor process-exit race; its resource receipt and traces are retained. No lingering process was found, and the clean retry passed.
2. The standalone report CLI loaded the pipeline both as __main__ and under its canonical package name, separating the active guard registries. The protected outer-target read was correctly denied. The completed forecast freeze was then reverified through the existing report logic, using the canonical imported run_phase entry from report_recovery/resume_report.py. Original partial report outputs were archived and numerical tables verified identical after recovery. Forecasts and scores were not recalculated. For report recovery, use this saved canonical launcher rather than the direct -m pipeline report command.
3. Paired-effect and sensitivity figures received separate readable-layout copies. review/final.html uses those copies. Original core and delivery manifests remain valid and unchanged; presentation_release.json records the additions.

Approved phase and cumulative caps include failed attempts and recovery checks. See completion.json for final resource accounting and final_verification.json for manifest, link, figure, and preserved-output verification.
