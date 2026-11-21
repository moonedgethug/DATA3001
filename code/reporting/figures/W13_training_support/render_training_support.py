"""Reproduce Figure 9 from saved training origins; no model execution."""
from pathlib import Path
import hashlib
import json

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib import font_manager
import pandas as pd

OUT = Path(__file__).resolve().parent
ROOT = OUT.parents[2]
SOURCE = ROOT / "work_place/results/runs/exact_origin_s4_e7_primary_20261105T074326_829211Z/training_coordinates.parquet"
EXPECTED_SHA256 = "8638434fb651d10737a2827350d5ff98a3a76a5f3427778748c17a3ddb68715d"


def main():
    source_hash = hashlib.sha256(SOURCE.read_bytes()).hexdigest()
    if source_hash != EXPECTED_SHA256:
        raise ValueError("Training source differs from the reviewed input")
    origins = pd.read_parquet(SOURCE, columns=["id", "origin_time_UTC"])
    origins["year"] = origins.origin_time_UTC.dt.year
    annual = origins.groupby("year").agg(
        pairs=("id", "size"), independent_drifters=("id", "nunique")
    )
    annual["share_of_training_pairs"] = annual.pairs / len(origins)
    assert len(origins) == 265393 and origins.id.nunique() == 338
    assert annual.index.tolist() == list(range(2001, 2020))
    assert annual.pairs.sum() == len(origins)
    annual.to_csv(OUT / "annual_training_support.csv")

    available = {f.name for f in font_manager.fontManager.ttflist}
    font = next(n for n in ["Arial Unicode MS", "Noto Sans CJK SC", "PingFang HK"] if n in available)
    plt.rcParams.update({"font.family": font, "font.size": 10,
                         "axes.unicode_minus": False, "pdf.fonttype": 42,
                         "text.color": "#21333f", "axes.labelcolor": "#21333f"})
    fig, axes = plt.subplots(2, 1, figsize=(8, 4.8), sharex=True)
    fig.subplots_adjust(left=.105, right=.98, top=.78, bottom=.17, hspace=.38)
    fig.text(.105, .95, "最终七天模型：训练资料的年度分布", fontsize=14, weight="bold", va="top")
    fig.text(.105, .88, "2001–2019年 · 265,393组配对 · 338条独立漂流器", fontsize=10.5, va="top")
    for ax in axes:
        ax.set_axisbelow(True)
        ax.grid(axis="y", color="#e3e7e9", lw=.7)
        ax.spines[["top", "right"]].set_visible(False)
        ax.spines[["left", "bottom"]].set_color("#9aa7af")
        ax.tick_params(axis="both", length=3, color="#9aa7af", labelsize=9)
        ax.set_xlim(2000.35, 2019.65)
    axes[0].bar(annual.index, annual.pairs / 1000, width=.68, color="#345b73", zorder=3)
    axes[0].set_ylim(0, 64)
    axes[0].set_yticks([0, 20, 40, 60])
    axes[0].set_ylabel("配对数量（千组）", fontsize=10)
    axes[0].text(.01, .96, "(a)", transform=axes[0].transAxes, va="top", weight="bold")
    axes[0].text(2011, 53.5, "50,338组（18.97%）", ha="center", fontsize=10)
    axes[1].bar(annual.index, annual.independent_drifters, width=.68, color="#345b73", zorder=3)
    axes[1].set_ylim(0, 64)
    axes[1].set_yticks([0, 20, 40, 60])
    axes[1].set_ylabel("独立漂流器数量", fontsize=10)
    axes[1].set_xlabel("出发年份（UTC）", labelpad=8, fontsize=10)
    axes[1].set_xticks(list(range(2001, 2020, 2)))
    axes[1].text(.01, .96, "(b)", transform=axes[1].transAxes, va="top", weight="bold")
    axes[1].text(2011, 54, "51条", ha="center", fontsize=10)
    fig.text(.105, .035, "同一漂流器可在多个年份出现；逐年数量不可相加为独立总数。", fontsize=9)
    for suffix in ["png", "pdf"]:
        fig.savefig(OUT / f"figure09_annual_training_support_zh.{suffix}", dpi=240,
                    facecolor="white", metadata={"Creator": "DATA3001 W13 training-support renderer"})
    plt.close(fig)
    provenance = {
        "source": str(SOURCE.relative_to(ROOT)), "source_sha256": source_hash,
        "source_columns": ["id", "origin_time_UTC"], "grouping": "UTC origin year",
        "pairs": len(origins), "unique_drifters": int(origins.id.nunique()),
        "year_id_counts_overlap": True, "pair_counts_sum_to_total": True,
        "new_training": False, "final_test_access": False,
        "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    }
    (OUT / "provenance.json").write_text(json.dumps(provenance, indent=2) + "\n")
    print(f"Saved annual table and Figure 9: {len(origins):,} pairs, {origins.id.nunique()} drifters.")


if __name__ == "__main__":
    main()
