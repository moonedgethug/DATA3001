"""Actual experiment entry points and their separately stated reproduction scope."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

PREFIX = "data3001.modelling."
MARKOV_INPUT = "markov_input_20261025T095949_830292Z"
MARKOV_FIT = "markov_m1_1d_20261025T100248_328450Z"
E7 = "exact_origin_s4_e7_primary_20261105T074326_829211Z"
E3 = "conditional_mdn_s5_e3_20261108T055830_797628Z"
E4 = "conditional_mdn_s5_e4_20261109T082930_653149Z"


@dataclass(frozen=True)
class Task:
    id: str
    title: str
    mode: str
    module: str = ""
    arguments: tuple = ()
    config: str = ""
    runs: tuple = ()
    needs_tracks: bool = False
    recorded_run: str = ""
    implemented: bool = True
    scope: str = ""
    gap: str = ""
    historical_hours: float | None = None
    preflight_argument: str = ""
    preflight_prefix: str = ""
    staged: bool = False
    extra_inputs: tuple = ()

    def describe(self):
        value = asdict(self)
        value["execution_validation"] = "not_yet_run_in_this_delivery"
        return value


TASKS = [
    Task("predict.final_mdn22", "Predict with the frozen final 22-component model", "inference",
         scope="Loads the exact frozen checkpoint; no training or validation outcomes."),
    Task("data.inspect", "Inspect the delivered data identity and development split", "inspection",
         scope="Reads manifests only; no trajectory content or final-test files."),
    Task("results.recover", "Recover the recorded experiment summaries", "reuse",
         scope="Copies saved summaries and reports with source hashes; performs no fitting or rescoring."),
    Task("stage1.baselines", "First round: fit B0/B1/B2 from development tracks", "refit",
         PREFIX + "baselines.run_round1", needs_tracks=True,
         recorded_run="baseline_pooled_20261018T150758_752931Z",
         scope="Rebuilds qualified training pairs and empirical fits; fixed-split scoring is available separately as stage1.validation."),
    Task("stage1.validation", "First round: rescore the fixed historical validation split", "score",
         PREFIX + "baselines.evaluate", needs_tracks=True,
         runs=("baseline_pooled_20261018T150758_752931Z",),
         recorded_run="baseline_validation_20261019T052149_527052Z",
         scope="Rebuilds qualified validation pairs and computes new scores using the original frozen empirical tables; no new fit is claimed."),
    Task("stage1.blend", "First round: nested cross-validation of B1/B2 blending", "refit",
         PREFIX + "baselines.run_blend_cv", needs_tracks=True,
         runs=("baseline_pooled_20261018T150758_752931Z", "baseline_validation_20261019T052149_527052Z"),
         recorded_run="baseline_blend_cv_20261022T160806_056571Z",
         scope="Rebuilds pairs and fits all nested folds; saved initial counts are equality controls."),
    Task("stage1.neighbourhood", "First round: spatial neighbourhood models", "refit",
         PREFIX + "baselines.run_neighbourhood", ("--input-run", "neighbour_input_20261024T062737_251970Z"),
         runs=("neighbour_input_20261024T062737_251970Z",),
         recorded_run="baseline_neighbour_cv_20261024T065917_879042Z",
         scope="Refits using the published qualified input snapshot."),
    Task("stage1.drogue", "First round: drogue regime comparisons", "refit",
         PREFIX + "baselines.run_regimes", ("--input-run", "regime_input_20261024T080243_439468Z"),
         runs=("regime_input_20261024T080243_439468Z",),
         recorded_run="baseline_regime_comparison_20261024T085357_553047Z",
         scope="Refits the regime experiment using the published qualified input snapshot."),
    Task("stage1.markov_inputs", "Rebuild qualified Markov input counts from v7", "prepare",
         PREFIX + "markov_models.run_markov", ("--prepare-only",), "configs/markov_m1.json",
         needs_tracks=True, recorded_run=MARKOV_INPUT,
         scope="Regenerates the qualified development labels and transition counts."),
    Task("stage1.markov", "First round: daily Markov baseline", "refit",
         PREFIX + "markov_models.run_markov", ("--input-run", MARKOV_INPUT),
         "configs/markov_m1.json", (MARKOV_INPUT,), recorded_run=MARKOV_FIT,
         scope="Refits from the published prepared input snapshot."),
    Task("stage1.markov_diagnostics", "First round: Markov lag diagnostics", "refit",
         PREFIX + "markov_models.run_markov_diagnostics",
         ("--input-run", "markov_diagnostic_input_20261025T113812_255111Z"),
         "configs/markov_m1_diagnostics.json", ("markov_diagnostic_input_20261025T113812_255111Z",),
         recorded_run="markov_diagnosis_20261025T114721_490747Z"),
    Task("stage1.velocity", "First round: velocity-state Markov models", "refit",
         PREFIX + "markov_models.run_markov_velocity",
         ("--input-run", "markov_vcat_input_20261026T155040_667626Z"),
         "configs/markov_m1_vcat.json", ("markov_vcat_input_20261026T155040_667626Z",),
         recorded_run="markov_vcat_cv_20261026T155955_651594Z"),
    Task("stage1.position", "First round: exact-position propagation", "refit",
         PREFIX + "markov_models.run_markov_position",
         ("--input-run", "markov_position_input_20261027T093543_211496Z"),
         "configs/markov_m1_position.json", ("markov_position_input_20261027T093543_211496Z",),
         recorded_run="markov_position_cv_20261027T094335_386746Z"),
    Task("stage1.iteration", "First round: 99 iteration-order comparisons", "refit",
         PREFIX + "markov_models.run_markov_iteration",
         ("--geometry-run", "markov_iteration_geometry_20261027T114759_607891Z"),
         "configs/markov_m1_iteration.json", ("markov_iteration_geometry_20261027T114759_607891Z",),
         recorded_run="markov_iteration_cv_20261027T120356_034230Z"),
    Task("stage1.continuous", "First round: hourly continuous models", "refit",
         PREFIX + "continuous_models.run_continuous",
         ("--input-run", "continuous_input_20261028T143429_995267Z"),
         runs=("continuous_input_20261028T143429_995267Z",),
         recorded_run="continuous_cv_20261028T143556_027911Z"),
    Task("stage2.step1", "Step1: empirical transition matrix", "refit",
         PREFIX + "baselines.run_empirical_b2", (), "configs/empirical_b2.json",
         (MARKOV_INPUT, MARKOV_FIT), recorded_run="empirical_b2_20261029T121555_976173Z",
         scope="Reconstructs counts from saved qualified labels, refits all five held-out folds, scores and audits them."),
]

for key, title, module, reference in [
    ("adaptive", "Adaptive B1/B2 blending", "adaptive_b2_b1", "adaptive_b2_b1_20261030T044950_931787Z"),
    ("allocation", "B1 information allocation", "b2_b1_e2", "b2_b1_e2_20261030T060621_291294Z"),
    ("equal_id", "Equal-drifter shrinkage", "drifter_shrinkage_e3", "drifter_shrinkage_e3_20261030T074159_751985Z"),
    ("partial_id", "Partial drifter weighting", "partial_weighting_e4", "partial_weighting_e4_20261030T082826_141410Z")]:
    TASKS.append(Task("stage2.step2." + key, "Step2: " + title, "refit",
                      PREFIX + "baselines.run_" + module, (), "configs/" + module + ".json",
                      (MARKOV_INPUT, MARKOV_FIT), recorded_run=reference,
                      scope="New fit and scores from frozen qualified inputs; preceding experiment outputs remain comparison controls.",
                      preflight_argument="--preflight-run" if key != "adaptive" else "",
                      preflight_prefix=module + "_preflight_" if key != "adaptive" else ""))

for key, title, module, reference in [
    ("spatial", "Spatial endpoint and displacement sharing", "spatial_borrowing_s3_e1", "spatial_borrowing_s3_e1_20261030T114538_900248Z"),
    ("adaptive", "Adaptive local endpoint weights", "local_endpoint_adaptive_s3_e2", "local_endpoint_adaptive_s3_e2_20261030T135819_234829Z"),
    ("quality", "Local endpoint information quality", "local_endpoint_quality_s3_e3", "local_endpoint_quality_s3_e3_20261031T005527_091650Z"),
    ("joint", "Joint local endpoint constraints", "local_endpoint_joint_s3_e4", "local_endpoint_joint_s3_e4_20261031T034349_606438Z")]:
    TASKS.append(Task("stage2.step3." + key, "Step3: " + title, "refit",
                      PREFIX + "baselines.run_" + module,
                      ("--input-run", "spatial_borrowing_s3_e1_input_20261030T113714_822569Z") if key == "spatial" else (),
                      "configs/" + module + ".json", (MARKOV_INPUT, MARKOV_FIT,
                      "spatial_borrowing_s3_e1_input_20261030T113714_822569Z"),
                      recorded_run=reference,
                      preflight_argument="--pilot-run" if key != "spatial" else "",
                      preflight_prefix=module + "_pilot_" if key != "spatial" else ""))

for key, module, reference in [
    ("seasonal", "seasonal_conditioning_s4_e1", "seasonal_conditioning_s4_e1_primary_20261102T005104_943407Z"),
    ("temporal", "temporal_validation_s4_e2", "temporal_validation_s4_e2_primary_20261103T004920_642021Z"),
    ("seasonal_information", "seasonal_information_s4_e3", "seasonal_information_s4_e3_primary_20261104T142729_626118Z"),
    ("direction", "departure_direction_s4_e4", "departure_direction_s4_e4_primary_20261104T153104_398790Z"),
    ("exact_origin", "exact_origin_s4_e7", E7),
    ("position_error", "position_error_s4_e8", "position_error_s4_e8_20261106T095423_445879Z"),
    ("seasonal_exact", "seasonal_exact_position_s4_e9", "e9_formal_20261106T140607_806462Z")]:
    TASKS.append(Task("stage2.step4." + key, "Step4: " + key.replace("_", " "), "refit",
                      PREFIX + "baselines.run_" + module, (), "configs/" + module + ".json",
                      runs=(MARKOV_INPUT, MARKOV_FIT),
                      needs_tracks=key in {"direction", "exact_origin"},
                      recorded_run=reference,
                      preflight_argument="--pilot", preflight_prefix=module + "_pilot_", staged=True,
                      extra_inputs=("provenance/reviews/" + (module + "_v2" if key == "seasonal" else module) + "_execution_freeze.json",)
                          if key not in {"position_error", "seasonal_exact"} else (),
                      scope="Fresh original fits and audit from approved input snapshots; final numerical implementation and specifically approved recoveries retained. Full-duration run not yet verified in this delivery."
                          if key in {"position_error", "seasonal_exact"} else ""))

STEP5_TITLES = {
    "gaussian": "Conditional Gaussian distributions",
    "gmm": "Local Gaussian mixture distributions",
    "mdn6": "Mixture density networks: six candidate component counts",
    "mdn12": "Mixture density networks: twelve candidate counts, including the final 22-component model",
}

for key, module, reference, hours in [
    ("gaussian", "conditional_gaussian_s5_e1_full", "conditional_gaussian_s5_e1_full_20261107T061818Z", 1.007),
    ("gmm", "local_gmm_s5_e2_pipeline", "local_gmm_s5_e2_vector_20261107T133426Z", 12.64),
    ("mdn6", "conditional_mdn_s5_e3_formal_pipeline", E3, 14.33),
    ("mdn12", "conditional_mdn_s5_e4_formal_pipeline", E4, 33.34)]:
    TASKS.append(Task("stage2.step5." + key, "Step5: " + STEP5_TITLES[key], "refit",
                      PREFIX + "continuous_models." + module, recorded_run=reference,
                      implemented=True, historical_hours=hours,
                      scope="Fresh initialization, original full fitting/scoring and independent audit from frozen approved cohorts. MDN12 refits its six-model parent first; historical comparator results are explicit inputs. Full-duration run not yet verified in this delivery."))

TASKS.extend([
    Task("stage1.all", "Run all completed first-round modelling tasks", "suite",
         scope="Sequential first-round fits, input preparation and fixed-split scoring from their frozen published input contracts."),
    Task("stage2.all", "Run all completed second-round modelling tasks", "suite",
         scope="Sequential Step1–Step5 refits from frozen published inputs; MDN12 includes its six-model parent. Full phase not yet executed in this delivery."),
    Task("data.raw_cleaning", "Replay native track cleaning into a new output", "prepare",
         scope="Replays development raw cleaning, approved SST decisions and qualification; preserves historical disabled writers and discloses mixed raw storage chunks."),
    Task("report.rebuild", "Rebuild report figures and analyses", "report",
         scope="Rebuilds all 10 approved figures from frozen inputs; optional K22 regional integration and independent verification, no fits."),
    Task("presentation.export", "Rebuild portable presentation data exports", "report",
         scope="Executes the original presentation exporters from frozen approved inputs in an isolated workspace; no model fitting."),
    Task("full.refit", "Refit all completed experiments under their frozen input contracts", "refit",
         scope="Sequential fresh experiment fits, each from its own frozen published inputs; optional separate raw replay. MDN12 includes fresh MDN6. Does not claim an integrated refreshed upstream pipeline; full suite has not been executed in this delivery."),
])

REGISTRY = {task.id: task for task in TASKS}


def get_task(identifier):
    try:
        return REGISTRY[identifier]
    except KeyError:
        raise ValueError("Unknown task: " + identifier) from None
