"""Sequential genuine refits against each experiment's published input contract.

This does not imply that recomputed upstream byte streams replace the frozen
downstream inputs. The distinction is retained in every suite receipt.
"""
from __future__ import annotations

import time

from .operations import execute as run_stage
from .registry import REGISTRY, get_task
from .workspace import ExecutionWorkspace, write_json


def task_plan(tasks=None):
    default = [task.id for task in REGISTRY.values()
               if task.id.startswith("stage") and task.mode in {"refit", "prepare", "score"}
               and task.id != "stage2.step5.mdn6"]
    selected = list(tasks) if tasks is not None else default
    if not selected or len(selected) != len(set(selected)):
        raise ValueError("A refit suite needs distinct completed-experiment task IDs")
    for identifier in selected:
        task = get_task(identifier)
        if not identifier.startswith("stage") or task.mode not in {"refit", "prepare", "score"} or not task.implemented:
            raise ValueError("Task is not an available completed-experiment refit: " + identifier)
    if "stage2.step5.mdn6" in selected and "stage2.step5.mdn12" in selected:
        raise ValueError("MDN12 already refits all six parent models; do not schedule duplicate MDN6 fits")
    return {"tasks": selected, "all_completed_experiments_selected": selected == default,
            "followup_tasks": ["report.rebuild", "presentation.export"] if tasks is None else [],
            "report_input_mode": "frozen_published_inputs_not_fresh_score_integration",
            "dependency_mode": "frozen_published_inputs", "upstream_refresh": False,
            "mdn6_included_within_mdn12": "stage2.step5.mdn12" in selected,
            "stopped_or_uncompleted_experiments_included": False}


def run(root, *, run_id=None, tasks=None, with_raw_replay=False, timeout=None, task_id="full.refit"):
    if task_id not in {"full.refit", "stage1.all", "stage2.all"}:
        raise ValueError("Unknown suite identity")
    plan = task_plan(tasks)
    view = ExecutionWorkspace(root, run_id)
    started = time.monotonic()
    completed = []
    view.status.update(task=task_id, mode="refit" if task_id == "full.refit" else "suite", **plan, completed_tasks=completed,
        scope="Sequential fresh fits under each original frozen input contract; regenerated raw/prepared outputs are not silently substituted.",
        raw_replay_requested=bool(with_raw_replay))
    write_json(view.directory / "execution_plan.json", plan)
    write_json(view.directory / "run.json", view.status)
    identifiers = (["data.raw_cleaning"] if with_raw_replay else []) + plan["tasks"] + plan["followup_tasks"]
    try:
        for index, identifier in enumerate(identifiers, 1):
            view.status.update(status="running", current_task=identifier)
            write_json(view.directory / "run.json", view.status)
            child_id = view.directory.name[:75] + f"_stage_{index:02d}"
            if identifier == "data.raw_cleaning":
                from .raw_replay import run as raw_run
                result = raw_run(root, run_id=child_id, timeout=timeout)
            elif identifier == "report.rebuild":
                from reporting.delivery_report import run as report_run
                result = report_run(root, run_id=child_id, timeout=timeout)
            elif identifier == "presentation.export":
                from reporting.delivery_presentation import run as presentation_run
                result = presentation_run(root, run_id=child_id, timeout=timeout)
            else:
                result = run_stage(root, identifier, run_id=child_id, timeout=timeout)
            if result.get("status") != "complete":
                raise RuntimeError("Child stage did not complete: " + identifier)
            completed.append({"task": identifier, "receipt": result["output_directory"] + "/run.json",
                              "new_fits": result.get("new_fits", []), "status": result["status"]})
            view.status["completed_tasks"] = completed
            write_json(view.directory / "run.json", view.status)
        fitted = [fit for child in completed for fit in child["new_fits"]]
        return view.finish("complete", current_task=None, fitting_performed=bool(fitted),
                           completed_tasks=completed, new_fits=fitted,
                           elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        view.finish("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    completed_tasks=completed, error=f"{type(error).__name__}: {error}",
                    elapsed_seconds=time.monotonic() - started)
        raise
