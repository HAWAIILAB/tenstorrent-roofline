#!/usr/bin/env python3
"""
Roofline figure for the paper

Usage:
    python3 plots/plot_paper_roofline.py [results_dir] [out_dir] [dram_add_dir]
    defaults: results/  paper/figures/  (none)

Reads peak_bandwidth.csv, peak_flops_block_matrix.csv and (optional) ttnn_ops.csv.
The compute roofs use the best matmul_block shape per format and fidelity.
If dram_add_dir is given, the DRAM slope uses the best copy variant from its dram_add_*.csv
(mean over runs), if that is higher than peak_bandwidth.csv.
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as ticker
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "results"
OUT = Path(sys.argv[2]) if len(sys.argv) > 2 else ROOT / "paper" / "figures"
DRAM_ADD = Path(sys.argv[3]) if len(sys.argv) > 3 else None
OUT.mkdir(parents=True, exist_ok=True)

THEO_BW_GBS = 288.0
TEXT_WIDTH_IN = 7.16

# 2*32^3 FLOP per tile product, 16/32/64 cycles, 56 cores, 1 GHz
CYCLES = {"LoFi": 16, "HiFi2": 32, "HiFi4": 64}
PEAK = {f: 56 * 2 * 32**3 / c / 1e3 for f, c in CYCLES.items()}  # TFLOPS

# BF16 drawn widest so BF8 stays visible on top of it where overlap
STYLE = {
    "BF16": ("#9467bd", 2.6),
    "BF8": ("#1f77b4", 1.4),
    "BF4": ("#2ca02c", 1.4),
}


def read_csv(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


# my DRAM kernel: best point of the core count sweep
bw_rows = read_csv(RESULTS / "peak_bandwidth.csv")
dram_gbs = max(float(r["bw_gbs"]) for r in bw_rows)

# best copy variant of dram_add (1 read + 1 write, same workload as peak_bandwidth)
if DRAM_ADD:
    runs = {}
    for path in DRAM_ADD.glob("dram_add_*.csv"):
        for r in read_csv(path):
            if r["variant"].startswith("copy"):
                runs.setdefault(r["variant"], []).append(float(r["bw_gbs"]))
    if runs:
        dram_gbs = max(dram_gbs, max(sum(v) / len(v) for v in runs.values()))

# best matmul_block shape per (format, fidelity)
best = {}
for r in read_csv(RESULTS / "peak_flops_block_matrix.csv"):
    if r["kernel"].startswith("block"):
        key = (r["data_format"], r["math_fidelity"])
        best[key] = max(best.get(key, 0.0), float(r["tflops"]))

ttnn_path = RESULTS / "ttnn_ops.csv"
ttnn = read_csv(ttnn_path) if ttnn_path.exists() else []

plt.rcParams.update(
    {
        "font.size": 7,
        "axes.labelsize": 7,
        "axes.titlesize": 7,
        "legend.fontsize": 5.5,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "pdf.fonttype": 42,
    }
)

fig, axes = plt.subplots(1, 3, figsize=(TEXT_WIDTH_IN, 2.3), sharey=True)
ai = np.logspace(-2, 5, 1000)  # FLOP/byte

# bandwidth slopes (TFLOPS = GB/s * FLOP/byte / 1000)
theo_slope = THEO_BW_GBS * ai / 1e3
meas_slope = dram_gbs * ai / 1e3

families = {
    "matmul": ("TTNN matmul (LoFi)", "o", "#17becf"),
    "add": ("TTNN add", "^", "#d62728"),
    "exp": ("TTNN exp", "s", "#ff7f0e"),
}

for ax, fid in zip(axes, CYCLES):
    peak = PEAK[fid]
    # theoretical roof
    ax.plot(ai, np.minimum(theo_slope, peak), color="black", lw=0.8, ls="--", alpha=0.6)

    # measured roofs one per format
    for fmt, (color, lw) in STYLE.items():
        if (fmt, fid) not in best:
            continue
        t = best[(fmt, fid)]
        ax.plot(
            ai, np.minimum(meas_slope, t), color=color, lw=lw, label=f"{fmt} ({t:.1f})"
        )

    # TTNN operators, matmuls run at LoFi
    for r in ttnn:
        fam = r["op"].split("_")[0]
        if fam not in families or (fam == "matmul" and fid != "LoFi"):
            continue
        _, marker, color = families[fam]
        ax.scatter(
            float(r["arithmetic_intensity"]),
            float(r["tflops"]),
            marker=marker,
            s=12,
            color=color,
            edgecolors="black",
            linewidths=0.3,
            zorder=5,
        )

    ax.set_title(f"{fid} (peak {peak:.1f} TFLOPS)")
    ax.set_xscale("log")
    ax.set_yscale("log")
    ax.set_xlim(0.05, 5e4)
    ax.set_ylim(1e-2, 500)
    ax.set_xlabel("Arithmetic intensity (FLOP/byte)")

    # plain numbers instead of 10^x
    plain = ticker.FuncFormatter(lambda v, _: f"{v:g}")
    ax.yaxis.set_major_locator(ticker.LogLocator(base=10))
    ax.yaxis.set_major_formatter(plain)
    ax.yaxis.set_minor_formatter(ticker.NullFormatter())
    ax.xaxis.set_major_locator(ticker.LogLocator(base=10, numticks=10))
    ax.xaxis.set_minor_formatter(ticker.NullFormatter())

    ax.grid(True, which="major", alpha=0.25, lw=0.5)
    ax.legend(
        loc="lower right",
        framealpha=0.9,
        handlelength=1.8,
        title="measured TFLOPS",
        title_fontsize=5.5,
    )

axes[0].set_ylabel("Throughput (TFLOPS)")

# shared legend
handles = [
    plt.Line2D(
        [],
        [],
        color="black",
        lw=0.8,
        ls="--",
        alpha=0.6,
        label=f"theoretical ({THEO_BW_GBS:.0f} GB/s, peak)",
    ),
    plt.Line2D(
        [], [], color="black", lw=1.4, label=f"measured DRAM ({dram_gbs:.1f} GB/s)"
    ),
]
for name, marker, color in families.values():
    handles.append(
        plt.Line2D(
            [],
            [],
            ls="none",
            marker=marker,
            markersize=4,
            color=color,
            markeredgecolor="black",
            markeredgewidth=0.3,
            label=name,
        )
    )
fig.legend(
    handles=handles,
    loc="upper center",
    ncol=len(handles),
    frameon=False,
    bbox_to_anchor=(0.5, 1.0),
)

fig.tight_layout(pad=0.3, rect=(0, 0, 1, 0.93))
for ext in ("pdf", "png"):
    fig.savefig(OUT / f"roofline.{ext}", dpi=300)
print(
    f"Saved {OUT / 'roofline.pdf'}  (DRAM {dram_gbs:.1f} GB/s, results from {RESULTS})"
)
