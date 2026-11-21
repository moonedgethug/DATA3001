"""One public Notebook/CLI entry point for DATA3001 delivery tasks.

The task registry states whether a task loads, reuses, prepares or refits.
Historical algorithms execute only in a real, isolated original-layout copy.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

CODE = Path(__file__).resolve().parent
if str(CODE) not in sys.path:
    sys.path.insert(0, str(CODE))

from reproduction.registry import REGISTRY
from reproduction.operations import execute, inspect_task as _inspect_task


def project_root(root=None):
    return Path(root).resolve() if root is not None else CODE.parent


def list_tasks(*, root=None):
    tasks = {task.id: task.describe() for task in REGISTRY.values()}
    receipts = []
    for path in (project_root(root) / "results/reproduced").glob("*/run.json"):
        try:
            record = json.loads(path.read_text())
        except (OSError, ValueError):
            continue
        if record.get("task") in tasks:
            receipts.append((record.get("created_utc", ""), path, record))
    for _, path, record in sorted(receipts):
        task = tasks[record["task"]]
        task["last_execution"] = {"status": record["status"], "receipt": str(path),
                                  "mode": record.get("mode"), "elapsed_seconds": record.get("elapsed_seconds"),
                                  "failure_category": record.get("failure_category")}
        task.pop("current_blocker", None)
        if record["status"] == "failed" and record.get("failure_category"):
            task["current_blocker"] = record["failure_category"]
        if record["status"] == "complete" and record["task"] == "full.refit" and not record.get("all_completed_experiments_selected"):
            if task["execution_validation"] == "not_yet_run_in_this_delivery":
                task["execution_validation"] = "recorded_subset_success"
            task["last_subset_receipt"] = str(path)
        elif record["status"] == "complete":
            task["execution_validation"] = "recorded_success"
            task["last_successful_receipt"] = str(path)
        elif record["status"] == "prepared":
            task["initialization_validation"] = "recorded_success_without_fitting"
            task["initialization_receipt"] = str(path)
    return list(tasks.values())


def inspect_task(task, *, root=None):
    return _inspect_task(project_root(root), task)


def run_task(task="predict.final_mdn22", *, root=None, **options):
    late_task = task.startswith("stage2.step5.") or task in {"stage2.step4.position_error", "stage2.step4.seasonal_exact"}
    if options.get("prepare_only") and not late_task:
        raise ValueError("prepare_only applies only to Step5 or Step4 position_error/seasonal_exact; use inspect_task for a suite plan")
    if task in {"stage1.all", "stage2.all"}:
        from reproduction.full import run
        prefix = task.split(".")[0] + "."
        selected = [item.id for item in REGISTRY.values() if item.id.startswith(prefix)
                    and item.mode in {"refit", "prepare", "score"} and item.id != "stage2.step5.mdn6"]
        if "tasks" in options:
            raise ValueError("Phase aliases select the whole phase; use full.refit with tasks for a subset")
        return run(project_root(root), tasks=selected, task_id=task, **options)
    if task == "presentation.export":
        from reporting.delivery_presentation import run
        return run(project_root(root), **options)
    if task == "full.refit":
        from reproduction.full import run
        return run(project_root(root), **options)
    if task == "report.rebuild":
        from reporting.delivery_report import run
        return run(project_root(root), **options)
    if task == "data.raw_cleaning":
        from reproduction.raw_replay import run
        return run(project_root(root), **options)
    return execute(project_root(root), task, **options)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path)
    actions = parser.add_subparsers(dest="action", required=True)
    listing = actions.add_parser("list", help="List tasks and their actual execution scope")
    listing.add_argument("--json", action="store_true")
    inspect = actions.add_parser("inspect", help="Inspect a task without executing models")
    inspect.add_argument("task", choices=list(REGISTRY))
    run = actions.add_parser("run", help="Execute one explicitly selected task")
    run.add_argument("task", choices=list(REGISTRY), nargs="?", default="predict.final_mdn22")
    run.add_argument("--run-id")
    run.add_argument("--longitude", type=float)
    run.add_argument("--latitude", type=float)
    run.add_argument("--samples", type=int)
    run.add_argument("--seed", type=int)
    run.add_argument("--recover-task", choices=list(REGISTRY))
    run.add_argument("--timeout", type=float, help="Optional wall-time limit per scientific subprocess; never alters scientific settings")
    run.add_argument("--ids", nargs="+", help="Development IDs for raw cleaning (default: all development IDs)")
    run.add_argument("--figures", nargs="+", help="Report figure groups to rebuild")
    run.add_argument("--recompute-region", action="store_true", help="Recompute the frozen-model regional analysis")
    run.add_argument("--prepare-only", action="store_true", help="Verify and initialize a fresh late-model run without training")
    run.add_argument("--tasks", nargs="+", help="Explicit subset of stage tasks for full.refit")
    run.add_argument("--with-raw-replay", action="store_true", help="Also replay development raw cleaning before a refit suite")
    args = parser.parse_args(argv)
    if args.action == "list":
        tasks = list_tasks(root=args.root)
        if args.json:
            print(json.dumps(tasks, indent=2))
        else:
            for task in tasks:
                state = task.get("current_blocker") or ("available" if task["implemented"] else "adapter pending")
                print(f"{task['id']:35} {task['mode']:11} {state:16} {task['title']}")
    elif args.action == "inspect":
        print(json.dumps(inspect_task(args.task, root=args.root), indent=2))
    else:
        try:
            options = {"run_id": args.run_id, "timeout": args.timeout}
            if args.task == "predict.final_mdn22":
                options.update(origins=[[-78.0 if args.longitude is None else args.longitude,
                                        33.0 if args.latitude is None else args.latitude]],
                               samples=1000 if args.samples is None else args.samples,
                               seed=20261126 if args.seed is None else args.seed)
            elif args.task == "results.recover":
                options["recover_task"] = args.recover_task
            elif args.task == "data.raw_cleaning":
                options["ids"] = args.ids
            elif args.task == "report.rebuild":
                options.update(figures=args.figures, recompute_region=args.recompute_region)
            elif args.task == "full.refit":
                options.update(tasks=args.tasks, with_raw_replay=args.with_raw_replay)
            if args.prepare_only:
                options["prepare_only"] = True
            if args.ids is not None and args.task != "data.raw_cleaning":
                raise ValueError("--ids applies only to data.raw_cleaning")
            if args.task != "predict.final_mdn22" and any(value is not None for value in
                    (args.longitude, args.latitude, args.samples, args.seed)):
                raise ValueError("Prediction options apply only to predict.final_mdn22")
            if args.recover_task is not None and args.task != "results.recover":
                raise ValueError("--recover-task applies only to results.recover")
            if (args.figures is not None or args.recompute_region) and args.task != "report.rebuild":
                raise ValueError("Report options apply only to report.rebuild")
            if (args.tasks is not None or args.with_raw_replay) and args.task != "full.refit":
                raise ValueError("Suite options apply only to full.refit")
            result = run_task(args.task, root=args.root, **options)
        except (Exception, KeyboardInterrupt) as error:
            print(f"{type(error).__name__}: {error}", file=sys.stderr)
            return 1
        print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
