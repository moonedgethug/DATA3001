"""Render report figures from saved summaries; no fitting or forecast scoring."""
from pathlib import Path
import hashlib
import json
import textwrap

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
RESULTS = ROOT / "work_place/results"
SOURCES = {
    "trace": RESULTS / "runs/continuous_diagnostic_report_20261029T055315_213458Z/trace_summary.csv",
    "one_step": RESULTS / "runs/continuous_diagnostics_20261029T054731_635202Z/one_step_summary.csv",
    "spatial": RESULTS / "deliverables/spatial_borrowing_s3_e1/summary.csv",
    "exact": RESULTS / "deliverables/exact_origin_s4_e7/summary.csv",
}
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 10, "axes.spines.top": False,
                     "axes.spines.right": False, "pdf.fonttype": 42})


def save(fig, name):
    for extension in ("png", "pdf"):
        fig.savefig(HERE / f"{name}.{extension}", dpi=180, bbox_inches="tight")
    plt.close(fig)


def diagnostic_figure():
    frame = pd.read_csv(SOURCES["trace"])
    # This is exactly the original figure's mean over its two saved repeats.
    frame = frame.loc[frame.model.eq("MDN3_l2_0")].groupby("hour").mean(numeric_only=True).reset_index()
    one = pd.read_csv(SOURCES["one_step"])
    fig, axes = plt.subplots(2, 2, figsize=(13, 9), layout="constrained")
    for ax, observed, predicted, control, title in [
        (axes[0, 0], "observed_speed_m_s", "predicted_speed_m_s", "control_expected_speed_m_s", "Mean speed (m/s)"),
        (axes[0, 1], "observed_vn_m_s", "predicted_vn_m_s", "control_vn_m_s", "Mean northward velocity (m/s)"),
    ]:
        ax.plot(frame.hour, frame[observed], "-o", color="#183844", label="Observed")
        ax.plot(frame.hour, frame[predicted], "-o", color="#c3593e", label="Mixture density network: free iteration")
        ax.plot(frame.hour, frame[control], "--o", color="#2a8b75", label="Previous observed state supplied at each step")
        ax.set(ylabel=title)
        ax.legend(fontsize=8.5)
    ax = axes[1, 0]
    ax.plot(frame.hour, 100 * frame.reason_2_fraction, "-o", color="#c3593e", label="Probability stopped by land checks")
    ax.plot(frame.hour, 100 * frame.reason_1_fraction, "-o", color="#5267a5", label="Probability of first exit from the study domain")
    ax.set(ylabel="Predicted probability (%)")
    ax.legend(fontsize=8.5)
    for ax in [axes[0, 0], axes[0, 1], axes[1, 0]]:
        ax.set(xscale="log", xticks=frame.hour, xticklabels=frame.hour.astype(int), xlabel="Hours since release")
        ax.grid(alpha=.18)
    row = one.loc[one.model.eq("MDN3_l2_0") & one.scope.eq("R") & one.speed_band.eq(2)].iloc[0]
    ax = axes[1, 1]
    ax.bar(["Observed", "Mixture density network"], [row.observed_parallel_dv, row.predicted_parallel_dv], color=["#183844", "#c3593e"])
    ax.axhline(0, color="#777", lw=.7)
    ax.set(ylabel="One-hour velocity change along initial direction (m/s)",
           title="Release-region origins with initial speed ≥ 0.75 m/s")
    fig.suptitle("Hourly mixture density network: local prediction and repeated propagation", fontsize=15)
    save(fig, "figure04_hourly_propagation")


def spatial_figure():
    frame = pd.read_csv(SOURCES["spatial"])
    names = {
        "B2": "Empirical Transition Baseline",
        "Fixed": "Mixture with a Fixed Weight",
        "Adaptive": "Mixture with Adaptive Weights",
        "LocalEndpoint": "Neighbour Endpoint Sharing",
        "LocalDisplacement": "Neighbour Path-displacement Sharing",
    }
    colors = ["#647986", "#c57b32", "#8a62b0", "#239d8f", "#2568b5"]
    fields = [("brier", "Brier Score (lower is better)", 1),
              ("region90_cells", "Mean Number of Cells in the 90% Prediction Region", 1),
              ("region90_hit", "Observed Coverage of the 90% Prediction Region (%)", 100)]
    fig, axes = plt.subplots(2, 3, figsize=(19, 11), layout="constrained")
    for row, days in enumerate((7, 30)):
        selected = frame.loc[frame.horizon_days.eq(days)].set_index("model").loc[list(names)]
        for ax, (metric, label, scale) in zip(axes[row], fields):
            values = selected[metric].to_numpy() * scale
            if metric == "brier":
                ax.scatter(range(5), values, c=colors, s=55, zorder=3)
                pad = max(.003, (values.max() - values.min()) * .25)
                ax.set_ylim(values.min() - pad, values.max() + 2 * pad)
            else:
                ax.bar(range(5), values, color=colors)
                ax.set_ylim(0, 105 if scale == 100 else values.max() * 1.2)
            for x, value in enumerate(values):
                ax.annotate(f"{value:.6f}" if metric == "brier" else f"{value:.2f}",
                            (x, value), xytext=(0, 7), textcoords="offset points", ha="center", fontsize=10)
            tick_labels = ["Empirical\nTransition\nBaseline", "Mixture with\na Fixed\nWeight",
                           "Mixture with\nAdaptive\nWeights", "Neighbour\nEndpoint\nSharing",
                           "Neighbour\nPath-\ndisplacement\nSharing"]
            ax.set_xticks(range(5), tick_labels, fontsize=9)
            ax.set_xlim(-.6, 4.6)
            ax.set_title(f"{days} days\n" + textwrap.fill(label, 39), fontsize=12)
            ax.grid(axis="y", alpha=.15)
    fig.suptitle("Spatial information sharing: score, prediction-region size and observed coverage", fontsize=16)
    save(fig, "figure05_spatial_information")


def exact_figure():
    frame = pd.read_csv(SOURCES["exact"])
    fields = [("brier", "Brier Score", 1),
              ("h90", "Observed Coverage of the 90% Prediction Region (%)", 100),
              ("k90", "Mean Number of Cells in the 90% Prediction Region", 1),
              ("area90", "Mean Sea Area within the 90% Prediction Region (km²)", 1)]
    fig, axes = plt.subplots(2, 4, figsize=(19, 10), layout="constrained")
    for row, resolution in enumerate((1., .5)):
        selected = frame.loc[frame.resolution.eq(resolution)].set_index("model").loc[["Annual", "Exact"]]
        for ax, (metric, label, factor) in zip(axes[row], fields):
            values = selected[metric].to_numpy() * factor
            bars = ax.bar(["Empirical Transition\nBaseline", "Exact-origin\nNeighbourhood Model"], values, color=["#33657e", "#238467"])
            ax.bar_label(bars, fmt="%.5f" if metric == "brier" else "%.2f", fontsize=10)
            ax.set(title=f"{resolution:g}° evaluation grid\n" + textwrap.fill(label, 29), ylim=(0, max(float(values.max()) * 1.22, .01)))
            ax.tick_params(axis="x", labelsize=9)
    fig.suptitle("Seven-day prediction using exact starting positions", fontsize=16)
    save(fig, "figure06_exact_starting_position")


if __name__ == "__main__":
    before = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in SOURCES.items()}
    diagnostic_figure()
    spatial_figure()
    exact_figure()
    after = {key: hashlib.sha256(path.read_bytes()).hexdigest() for key, path in SOURCES.items()}
    assert before == after
    receipt = {"purpose": "Report labels and layout; existing plot values and aggregation retained",
               "sources": {key: {"path": str(path.relative_to(ROOT)), "sha256": before[key]} for key, path in SOURCES.items()},
               "new_fitting_or_scoring": False}
    (HERE / "provenance.json").write_text(json.dumps(receipt, indent=2) + "\n")
    print("Rendered three figures; all source summary hashes unchanged.")
