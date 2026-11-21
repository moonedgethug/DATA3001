"""Rebuild Parts 2–4 presentation data from the preserved exporters and inputs.

Only Part 2's two machine-specific input paths are adapted in an execution copy.
The original exporters remain byte-identical. No fitting or score calculation
runs; Part 3 retains its original deterministic display-only sampling recipe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from reproduction.runner import run_command
from reproduction.workspace import ExecutionWorkspace, independent_copy, sha256, write_json


BUNDLE = "data/reference/presentation_inputs"
PRESENTATION = "report/presentation/assets"
SCRIPTS = "code/reporting/presentation/scripts"
GROUNDING_SOURCE = "../additional_research/grounding_scope_conclusion_20261110.md"
PART2_INPUTS = (
    "archive/region_screening_6h/region_data_audit.py",
    "archive/region_screening_6h/outputs/region-audit-summary.csv",
    "archive/region_screening_6h/outputs/gulf-stream-segment-summary.csv",
    "provenance/reviews/seasonal_temporal_support_20261102/annual_support.csv",
)


def _adapt_part2(source):
    replacements = [
        ("ROOT=Path('/Users/moonedgethug/Documents/UNSW/DATA3001/work_place')",
         "ROOT=Path(__file__).resolve().parents[2]/'workspace'"),
        ("Path('/tmp/data3001-ne-land.json')",
         "(ROOT/'data/reference/presentation_inputs/ne_50m_land.geojson')"),
    ]
    substitutions = []
    for before, after in replacements:
        if source.count(before) != 1:
            raise ValueError("The preserved Part 2 input-path literal changed; refusing an unreviewed adaptation")
        source = source.replace(before, after)
        substitutions.append({"before": before, "after": after, "occurrences": 1, "scope": "input path only"})
    return source, substitutions


def compare_payload(expected, actual):
    """Compare every numerical leaf and every non-numerical payload field."""
    differences = []
    numeric_count = numeric_changes = 0
    maximum_difference = 0.

    def visit(left, right, path):
        nonlocal numeric_count, numeric_changes, maximum_difference
        left_number = isinstance(left, (int, float)) and not isinstance(left, bool)
        right_number = isinstance(right, (int, float)) and not isinstance(right, bool)
        if left_number and right_number:
            numeric_count += 1
            if left != right:
                numeric_changes += 1
                maximum_difference = max(maximum_difference, abs(left - right))
                differences.append(path)
        elif isinstance(left, dict) and isinstance(right, dict):
            if set(left) != set(right):
                differences.append(path + ".keys")
            for name in sorted(set(left) & set(right)):
                visit(left[name], right[name], path + "." + name)
        elif isinstance(left, list) and isinstance(right, list):
            if len(left) != len(right):
                differences.append(path + ".length")
            for index, (x, y) in enumerate(zip(left, right)):
                visit(x, y, path + "[" + str(index) + "]")
        elif type(left) is not type(right) or left != right:
            differences.append(path)

    visit(expected, actual, "$")
    return {"payload_exact_equal": not differences, "numeric_exact_equal": numeric_changes == 0,
            "numeric_values_compared": numeric_count, "numeric_differences": numeric_changes,
            "maximum_absolute_numeric_difference": maximum_difference,
            "difference_count": len(differences), "differences": differences[:20]}


def _execution_copy(view, source, destination):
    destination = view.directory / destination
    independent_copy(source, destination)
    if sha256(source) != sha256(destination):
        raise ValueError("Presentation input copy changed bytes")
    return destination


def run(root, run_id=None, timeout=900):
    """Export all three presentation data parts to a fresh reproduction run."""
    view = ExecutionWorkspace(root, run_id)
    started = time.monotonic()
    try:
        view.status.update(task="presentation.export", mode="presentation_export", no_training=True,
                           adapter_sha256=sha256(Path(__file__)), final_test_access=False)
        view.materialize_sources()
        bundle_manifest = json.loads(view.mapping.resolve(BUNDLE + "/manifest.json").read_text())
        if bundle_manifest.get("schema_version") != 1:
            raise ValueError("Unsupported presentation reference bundle")
        view.bind(BUNDLE + "/manifest.json")
        bundle_files = {}
        for item in bundle_manifest["files"]:
            bundle_files[item["path"]] = view.bind(BUNDLE + "/" + item["path"], expected_sha256=item["sha256"])[0]
        references = {}
        for part in (2, 3, 4):
            path = PRESENTATION + "/pt" + str(part) + "/data.json"
            bound = view.bind(path)[0]
            references[part] = json.loads(bound.read_text())
        for part in (3, 4):
            for relative, expected_hash in references[part]["sources"].items():
                if relative == GROUNDING_SOURCE:
                    source = bundle_files["grounding_scope_conclusion_20261110.md"]
                    if sha256(source) != expected_hash:
                        raise ValueError("Portable grounding source differs from the published source identity")
                    destination = "additional_research/grounding_scope_conclusion_20261110.md"
                    if not (view.directory / destination).exists():
                        _execution_copy(view, source, destination)
                else:
                    view.bind(relative, expected_sha256=expected_hash)
        for relative in PART2_INPUTS:
            view.bind(relative)
        annual = PART2_INPUTS[-1]
        if sha256(view.path / annual) != references[2]["sources"]["annual_csv_sha256"]:
            raise ValueError("Part 2 annual support source changed")
        geography = view.bind(PRESENTATION + "/pt1/geography-wide.json")[0]
        _execution_copy(view, geography, "presentation/dist/assets/pt1/geography-wide.json")

        source_records = []
        for part in (2, 3, 4):
            relative = SCRIPTS + "/export-part" + str(part) + "-data.py"
            identities = [entry for entry in view.mapping.entries if entry["target"] == relative]
            if len(identities) != 1:
                raise ValueError("The original exporter identity is missing or ambiguous: " + relative)
            original_hash = identities[0]["sha256"]
            source = view.bind(relative, expected_sha256=original_hash)[0]
            execution_path = "presentation/scripts/export-part" + str(part) + "-data.py"
            destination = _execution_copy(view, source, execution_path)
            substitutions = []
            if part == 2:
                adapted, substitutions = _adapt_part2(destination.read_text())
                destination.write_text(adapted)
            source_records.append({"part": part, "original_source": relative,
                                   "original_sha256": original_hash, "execution_path": execution_path,
                                   "execution_sha256": sha256(destination), "substitutions": substitutions})
            (view.directory / "presentation/dist/assets" / ("pt" + str(part))).mkdir(parents=True, exist_ok=True)
        write_json(view.directory / "presentation_execution_sources.json", {"sources": source_records})
        view.save_inventory()
        comparisons, outputs = {}, {}
        for part in (2, 3, 4):
            script = view.directory / "presentation/scripts" / ("export-part" + str(part) + "-data.py")
            output = view.directory / "presentation/dist/assets" / ("pt" + str(part))
            arguments = ["-B", str(script)]
            if part != 2:
                arguments += ["--root", str(view.path), "--output", str(output)]
            run_command(view, arguments, label="presentation_part" + str(part) + "_export", timeout=timeout)
            actual = json.loads((output / "data.json").read_text())
            comparisons["pt" + str(part)] = compare_payload(references[part], actual)
            comparisons["pt" + str(part)]["data_json_byte_equal"] = (
                sha256(output / "data.json") == sha256(view.path / PRESENTATION / ("pt" + str(part)) / "data.json"))
            for path in sorted(output.iterdir()):
                if path.is_file():
                    outputs[path.relative_to(view.directory).as_posix()] = {"sha256": sha256(path), "bytes": path.stat().st_size}
        # CSV exports are direct copies, and should preserve the original bytes.
        for name in ("region-audit-summary.csv", "gulf-stream-segment-summary.csv", "annual_support.csv"):
            reference = view.mapping.resolve(PRESENTATION + "/pt2/" + name)
            generated = view.directory / "presentation/dist/assets/pt2" / name
            comparisons["pt2"][name + "_byte_equal"] = sha256(reference) == sha256(generated)
        all_equal = all(item["payload_exact_equal"] for item in comparisons.values())
        csv_equal = all(value for name, value in comparisons["pt2"].items() if name.endswith("csv_byte_equal"))
        for record in view.records.values():
            if sha256(view.path / record["execution_path"]) != record["sha256"]:
                raise ValueError("A frozen presentation input or original source was modified")
        for record in source_records:
            if sha256(view.directory / record["execution_path"]) != record["execution_sha256"]:
                raise ValueError("An execution exporter changed during export")
        verification = {"status": "passed" if all_equal and csv_equal else "failed",
                        "parts": comparisons, "original_sources_unchanged": True, "new_fits": [],
                        "scores_recomputed": False, "final_test_access": False,
                        "natural_earth_identity": bundle_manifest["files"][0]["identity_boundary"]}
        write_json(view.directory / "presentation_verification.json", verification)
        if verification["status"] != "passed":
            raise ValueError("Presentation export differs from the published payload; inspect presentation_verification.json")
        return view.finish("complete", outputs=outputs, presentation_verification=verification,
                           elapsed_seconds=time.monotonic() - started)
    except BaseException as error:
        view.finish("interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                    error=type(error).__name__ + ": " + str(error), elapsed_seconds=time.monotonic() - started)
        raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--run-id")
    args = parser.parse_args()
    print(json.dumps(run(args.root, args.run_id), indent=2))


if __name__ == "__main__":
    main()
