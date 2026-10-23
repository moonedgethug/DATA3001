"""Export an offline presentation from a sealed development experiment.

No model is fitted, no trajectory is opened and no scientific artifact is
changed. Only the two owned presentation files are refreshed on a later export.
"""
import argparse
import hashlib
import html
import json
import os
from pathlib import Path
import re
import tempfile

import pandas as pd

from data3001.modelling.report import _standalone
from data3001.paths import file_sha256, project_paths

VENDOR_HASH = "f2094bbf6141b359722c4fe454eb6c4b0f0e42cc10cc7af921fc158fceb86539"
D3_SCRIPT = '<script src="https://cdn.jsdelivr.net/npm/d3@7.9.0/dist/d3.min.js"></script>'


def _verify_run(paths, run_id):
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", run_id):
        raise ValueError("Invalid run identifier.")
    run = paths.root / "results/runs" / run_id
    provenance = paths.root / "provenance/runs" / run_id
    receipt_path = provenance / "outputs.json"
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("completed") is not True or receipt.get("final_test_access") is not False:
        raise ValueError("The source must be a completed development-only run.")
    hashes = receipt.get("output_sha256", {})
    if not hashes:
        raise ValueError("The source has no output checksums.")
    for name, expected in hashes.items():
        source = (paths.root / name).resolve()
        if not any(source.is_relative_to(base.resolve()) for base in (run, provenance)):
            raise PermissionError("A report receipt cannot authorize reads outside its experiment.")
        if file_sha256(source) != expected:
            raise ValueError(f"Source checksum mismatch: {name}")
    for name in ("comparison-inline.html", "outer_summary.csv", "final_lambda_selection.csv", "REPORT.md"):
        if str((run / name).relative_to(paths.root)) not in hashes:
            raise ValueError(f"Required presentation input is not sealed: {name}")
    config = json.loads((provenance / "run.json").read_text())["config"]
    if config.get("final_test_access") is not False:
        raise ValueError("The experiment configuration does not lock the final test.")
    return run, receipt_path


def _document(run_id, fragment, summary, weights):
    vendor = Path(__file__).with_name("assets") / "d3-7.9.0.min.js"
    if file_sha256(vendor) != VENDOR_HASH:
        raise ValueError("Vendored chart library checksum mismatch.")
    if fragment.count(D3_SCRIPT) != 1:
        raise ValueError("Expected exactly one pinned chart-library script.")
    fragment = fragment.replace(D3_SCRIPT, '<script data-vendor="d3@7.9.0">\n' +
                                vendor.read_text().replace("</script", "<\\/script") + "\n</script>")
    # The view is a presentation choice. The origin remains chosen exclusively
    # from training support and all five held-out fold summaries remain visible.
    fragment = fragment.replace("let state={model:'Analytic',horizon:7,", "let state={model:'Grid',horizon:30,")
    if set(zip(weights["horizon_days"], weights["method"])) != {
            (7, "Grid"), (7, "Analytic"), (30, "Grid"), (30, "Analytic")} or len(weights) != 4:
        raise ValueError("Expected exactly four final horizon/method weights.")
    rows = "".join(f"<tr><td>{int(row.horizon_days)} days</td><td>{html.escape(row.method)}</td>"
                   f"<td>{row.lambda_value:.6f}</td></tr>"
                   for row in weights.sort_values(["horizon_days", "method"]).itertuples())
    thirty = summary.loc[summary["horizon_days"].eq(30)].set_index("model")
    b2, mixed = thirty.loc["B2"], thirty.loc["Analytic"]
    source = f"../../runs/{run_id}"
    header = f"""<style>
.presentation-weights {{ border-collapse:collapse; width:min(100%,32rem); }}
.presentation-weights th,.presentation-weights td {{ text-align:left; padding:.5rem .75rem; border-bottom:1px solid var(--border); }}
</style><header>
<h1>Where Things End Up</h1>
<p>Southern Gulf Stream Corridor · 1° release cells · 7- and 30-day endpoint distributions</p>
<p><strong>Development cross-validation. The final test remains locked.</strong></p>
<nav aria-label="Presentation sections"><a href="#data3001-nested-blend-review">Probability maps</a> ·
<a href="#final-weights">Final candidate weights</a> · <a href="#method">Method and scope</a> ·
<a href="#evidence">Evidence</a></nav>
<p>Given a release cell in R, estimate the historical distribution of the observed future endpoint.
The maps compare a forecast fitted without the displayed holdout IDs with endpoints from those same held-out IDs.</p>
<p><strong>30-day all-fold result (Analytic blend):</strong> blending increases the held-out hit rate of the nominal 90% probability set
from {b2.region90_hit_pct:.2f}% to {mixed.region90_hit_pct:.2f}%, while its mean geographic size increases
from {b2.mean_region90_cells:.1f} to {mixed.mean_region90_cells:.1f} cells. Wider coverage has a cost in concentration.</p>
</header><hr>
"""
    footer = f"""<hr><section id="final-weights"><h2>Final candidate weights</h2>
<p><code>p = (1 − λ) × B2 + λ × B1</code>. Lambda is the weight assigned to the whole-R endpoint marginal.</p>
<table class="presentation-weights"><thead><tr><th>Horizon</th><th>Selection method</th><th>Final λ</th></tr></thead><tbody>{rows}</tbody></table>
<p>These weights were selected using all-development base out-of-fold predictions, then the bases were refitted on all development data.
Their tuning score is not an independent evaluation. The maps above use each outer fold's independently tuned weight, so its displayed lambda can differ.</p></section>
<section id="method"><h2>Method and scope</h2>
<p>Empirical conditional endpoint model: <code>P_B2(j | i,h) = N_ij(h) / Σ_k N_ik(h)</code>.
Here i is the origin cell, j the destination, h the horizon and N the eligible training-pair count.
For a complete forecast, <code>Brier = 1 − 2p_j + Σ_k p_k²</code>, with j the observed destination.</p>
<ul><li><strong>B0:</strong> persistence in the origin cell. <strong>B1:</strong> endpoint frequencies pooled across R.
<strong>B2:</strong> endpoint frequencies conditional on the origin cell.</li>
<li><strong>Optimization:</strong> compare a 0.1-step lambda grid with the continuous minimum of the same quadratic Brier objective.
Five outer and four inner whole-ID folds separate evaluation from weight selection. All eligible hourly pairs have equal weight.</li>
<li><strong>Reading the results:</strong> smaller Brier is better; it is not percentage accuracy.
Set hit rate, forecast availability and region size answer different questions. Raw zero probabilities remain visible and give infinite log loss.</li>
<li><strong>Limits:</strong> these are nonseasonal, pooled, historical drifter endpoint forecasts at 7 and 30 days.
The release prior follows sampled positions inside each cell. Annual, seasonal, grounding and object-specific performance are not validated here.
The paired bootstrap is conditional on saved OOF predictions and does not repeat training.</li></ul>
<h3>Next research checkpoints</h3><p>Investigate residual zero-probability outcomes and calibration; then test justified seasonal and longer-horizon extensions.
These are planned comparisons, not demonstrated capabilities.</p></section>
<section id="evidence"><h2>Evidence and reuse</h2>
<p>Source experiment: <code>{html.escape(run_id)}</code>.</p>
<p><a href="{source}/REPORT.md">Scientific report</a> · <a href="{source}/outer_summary.csv">Held-out summary CSV</a> ·
<a href="{source}/final_lambda_selection.csv">Final weights CSV</a> ·
<a href="../../../provenance/runs/{run_id}/final_qa.json">Verification record</a></p>
<p>The page includes its chart library and snapshot, works offline, and does not fit a model or read trajectories.
Source tables remain available with the repository checkout. To refresh this fixed presentation entry after an approved experiment,
run <code>python -B -m data3001.modelling.showcase --run-id YOUR_COMPLETED_RUN_ID</code>.</p>
</section>
"""
    return _standalone(header + fragment + footer).replace(
        "<title>Developmental nested-CV endpoint comparison</title>",
        "<title>Where Things End Up — Baseline Optimized</title>")


def _atomic_write(path, content):
    descriptor, temporary = tempfile.mkstemp(prefix=".showcase-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(content)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        Path(temporary).unlink(missing_ok=True)


def build_showcase(run_id, *, paths=None):
    """Refresh only the owned offline page from a checksum-verified saved run."""
    paths = paths or project_paths()
    run, receipt = _verify_run(paths, run_id)
    document = _document(run_id, (run / "comparison-inline.html").read_text(),
                         pd.read_csv(run / "outer_summary.csv"),
                         pd.read_csv(run / "final_lambda_selection.csv")).encode("utf-8")
    folder = paths.root / "results/deliverables/baseline_optimized"
    if folder.is_symlink() or not folder.resolve().is_relative_to(paths.root):
        raise PermissionError("Presentation destination escaped the project.")
    index, manifest = folder / "index.html", folder / "site_manifest.json"
    if folder.exists() and set(p.name for p in folder.iterdir()) - {index.name, manifest.name}:
        raise ValueError("The presentation folder contains unowned files.")
    if index.exists() or manifest.exists():
        if not index.is_file() or not manifest.is_file() or file_sha256(index) != json.loads(manifest.read_text()).get("index_sha256"):
            raise ValueError("The presentation was manually edited; preserve that edit before refreshing.")
    record = {"schema_version": 1, "source_run": run_id,
              "source_outputs_receipt_sha256": file_sha256(receipt),
              "source_comparison_inline_sha256": file_sha256(run / "comparison-inline.html"),
              "index_sha256": hashlib.sha256(document).hexdigest(), "d3_version": "7.9.0",
              "d3_sha256": VENDOR_HASH, "offline": True, "final_test_access": False}
    folder.mkdir(parents=True, exist_ok=True)
    _atomic_write(index, document)
    _atomic_write(manifest, (json.dumps(record, indent=2) + "\n").encode())
    return index


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    args = parser.parse_args()
    print(build_showcase(args.run_id))


if __name__ == "__main__":
    main()
