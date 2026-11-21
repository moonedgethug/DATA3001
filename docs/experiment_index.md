# Experiment execution index

Current registry: 41 tasks. “Initialized” means setup and original input contracts passed; it does not mean a completed fit.

| Task | Description | Mode | Verified execution | Current limit |
|---|---|---|---|---|
| `predict.final_mdn22` | Predict with the frozen final 22-component model | inference | recorded_success |  |
| `data.inspect` | Inspect the delivered data identity and development split | inspection | recorded_success |  |
| `results.recover` | Recover the recorded experiment summaries | reuse | recorded_success |  |
| `stage1.baselines` | First round: fit B0/B1/B2 from development tracks | refit | recorded_success |  |
| `stage1.validation` | First round: rescore the fixed historical validation split | score | recorded_success |  |
| `stage1.blend` | First round: nested cross-validation of B1/B2 blending | refit | not_yet_run_in_this_delivery |  |
| `stage1.neighbourhood` | First round: spatial neighbourhood models | refit | not_yet_run_in_this_delivery |  |
| `stage1.drogue` | First round: drogue regime comparisons | refit | not_yet_run_in_this_delivery |  |
| `stage1.markov_inputs` | Rebuild qualified Markov input counts from v7 | prepare | not_yet_run_in_this_delivery |  |
| `stage1.markov` | First round: daily Markov baseline | refit | not_yet_run_in_this_delivery |  |
| `stage1.markov_diagnostics` | First round: Markov lag diagnostics | refit | not_yet_run_in_this_delivery |  |
| `stage1.velocity` | First round: velocity-state Markov models | refit | not_yet_run_in_this_delivery |  |
| `stage1.position` | First round: exact-position propagation | refit | not_yet_run_in_this_delivery |  |
| `stage1.iteration` | First round: 99 iteration-order comparisons | refit | not_yet_run_in_this_delivery |  |
| `stage1.continuous` | First round: hourly continuous models | refit | not_yet_run_in_this_delivery |  |
| `stage2.step1` | Step1: empirical transition matrix | refit | recorded_success |  |
| `stage2.step2.adaptive` | Step2: Adaptive B1/B2 blending | refit | recorded_success |  |
| `stage2.step2.allocation` | Step2: B1 information allocation | refit | not_yet_run_in_this_delivery |  |
| `stage2.step2.equal_id` | Step2: Equal-drifter shrinkage | refit | not_yet_run_in_this_delivery |  |
| `stage2.step2.partial_id` | Step2: Partial drifter weighting | refit | not_yet_run_in_this_delivery |  |
| `stage2.step3.spatial` | Step3: Spatial endpoint and displacement sharing | refit | not_yet_run_in_this_delivery |  |
| `stage2.step3.adaptive` | Step3: Adaptive local endpoint weights | refit | not_yet_run_in_this_delivery |  |
| `stage2.step3.quality` | Step3: Local endpoint information quality | refit | not_yet_run_in_this_delivery |  |
| `stage2.step3.joint` | Step3: Joint local endpoint constraints | refit | not_yet_run_in_this_delivery |  |
| `stage2.step4.seasonal` | Step4: seasonal | refit | recorded_success |  |
| `stage2.step4.temporal` | Step4: temporal | refit | not_yet_run_in_this_delivery |  |
| `stage2.step4.seasonal_information` | Step4: seasonal information | refit | not_yet_run_in_this_delivery |  |
| `stage2.step4.direction` | Step4: direction | refit | not_yet_run_in_this_delivery |  |
| `stage2.step4.exact_origin` | Step4: exact origin | refit | not_yet_run_in_this_delivery |  |
| `stage2.step4.position_error` | Step4: position error | refit | initialized_without_fitting |  |
| `stage2.step4.seasonal_exact` | Step4: seasonal exact | refit | initialized_without_fitting |  |
| `stage2.step5.gaussian` | Step5: Conditional Gaussian distributions | refit | initialized_without_fitting | resource_gate_failed |
| `stage2.step5.gmm` | Step5: Local Gaussian mixture distributions | refit | initialized_without_fitting |  |
| `stage2.step5.mdn6` | Step5: Mixture density networks: six candidate component counts | refit | not_yet_run_in_this_delivery |  |
| `stage2.step5.mdn12` | Step5: Mixture density networks: twelve candidate counts, including the final 22-component model | refit | initialized_without_fitting |  |
| `stage1.all` | Run all completed first-round modelling tasks | suite | not_yet_run_in_this_delivery |  |
| `stage2.all` | Run all completed second-round modelling tasks | suite | not_yet_run_in_this_delivery |  |
| `data.raw_cleaning` | Replay native track cleaning into a new output | prepare | recorded_success |  |
| `report.rebuild` | Rebuild report figures and analyses | report | recorded_success |  |
| `presentation.export` | Rebuild portable presentation data exports | report | recorded_success |  |
| `full.refit` | Refit all completed experiments under their frozen input contracts | refit | recorded_subset_success |  |

The live status is available with `.venv/bin/python code/workflow.py list --json`. See [reproduction_audit.md](reproduction_audit.md) for actual measurements.

All original experiments keep their own targets, weights and validation definitions. Full suites refit against frozen published inputs; raw replay and upstream regeneration are separately recorded. Network task names `mdn6` and `mdn12` count candidate architectures, not mixture components in the final model.
