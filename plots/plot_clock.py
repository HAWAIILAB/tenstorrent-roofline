#!/usr/bin/env python3
"""
Clock and power of the chip during one random input matmul run

Usage:
    python3 plots/plot_clock.py <results_dir> [run] [out_dir]
    e.g. results_2026-11-14_random10 2 (run default: 2, out_dir default: paper/figures/)

Reads telemetry.csv and peak_flops_block_<run>.txt from run_repeats_random.sh
"""

import csv
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

ROOT = Path(__file__).resolve().parent.parent
RESULTS = Path(sys.argv[1])
RUN = int(sys.argv[2]) if len(sys.argv) > 2 else 2
OUT = Path(sys.argv[3]) if len(sys.argv) > 3 else ROOT / "paper" / "figures"
OUT.mkdir(parents=True, exist_ok=True)

CHIP = "0000:31:00.0"
COLUMN_WIDTH_IN = 3.5
NOMINAL_MHZ = 1000
POWER_LIMIT_W = 85

LINE = "#2a78d6"
INK = "#333333"
MUTED = "#777777"

plt.rcParams.update(
    {
        "font.size": 7,
        "axes.labelsize": 7,
        "xtick.labelsize": 6.5,
        "ytick.labelsize": 6.5,
        "axes.edgecolor": MUTED,
        "axes.linewidth": 0.6,
        "xtick.color": INK,
        "ytick.color": INK,
        "pdf.fonttype": 42,
    }
)

# end time of every config from the log, its start is the end of the one before
configs = []
start = None
with open(RESULTS / f"peak_flops_block_{RUN}.txt") as f:
    for line in f:
        p = line.split()
        if len(p) == 2 and p[1].startswith("-----"):
            start = float(p[0])
        elif len(p) >= 7 and p[2] in ("BF4", "BF8", "BF16") and start is not None:
            end = float(p[0])
            configs.append((p[2], p[3], start, end))
            start = end
t0, t1 = configs[0][2], configs[-1][3]

# format x fidelity groups
groups = []
for fmt, fid, s, e in configs:
    if groups and groups[-1][:2] == [fmt, fid]:
        groups[-1][3] = e
    else:
        groups.append([fmt, fid, s, e])

t, clk, pwr = [], [], []
with open(RESULTS / "telemetry.csv", newline="") as f:
    for r in csv.DictReader(f):
        x = float(r["time"])
        if r["bus_id"] == CHIP and t0 - 10 <= x <= t1 + 10:
            t.append(x - t0)
            clk.append(float(r["aiclk_mhz"]))
            pwr.append(float(r["power_w"]))

fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(COLUMN_WIDTH_IN, 2.6), sharex=True)

for ax in (ax1, ax2):
    for i, (fmt, fid, s, e) in enumerate(groups):
        if i % 2 == 0:
            ax.axvspan(s - t0, e - t0, color="#000000", alpha=0.05, lw=0)
    ax.spines["top"].set_visible(False)
    ax.spines["right"].set_visible(False)

ax1.step(t, clk, where="post", color=LINE, lw=1.0)
ax1.axhline(NOMINAL_MHZ, color=INK, ls="--", lw=0.8)
ax1.text(
    (t1 - t0) * 0.99,
    NOMINAL_MHZ + 15,
    "nominal 1 GHz",
    ha="right",
    va="bottom",
    fontsize=6,
    color=INK,
)
ax1.set_ylabel("Clock (MHz)")
ax1.set_ylim(0, 1150)

ax2.step(t, pwr, where="post", color=LINE, lw=1.0)
ax2.axhline(POWER_LIMIT_W, color=INK, ls="--", lw=0.8)
ax2.text(
    (t1 - t0) * 0.99,
    POWER_LIMIT_W + 2,
    "85 W limit",
    ha="right",
    va="bottom",
    fontsize=6,
    color=INK,
)
ax2.set_ylabel("Power (W)")
ax2.set_ylim(0, 100)
ax2.set_xlabel("Time (s)")
ax2.set_xlim(-5, t1 - t0 + 5)

# group labels above the top panel
for fmt, fid, s, e in groups:
    ax1.text(
        (s + e) / 2 - t0,
        1160,
        f"{fmt}\n{fid}",
        ha="center",
        va="bottom",
        fontsize=5,
        color=INK,
    )

fig.tight_layout(pad=0.3, h_pad=0.4)
fig.subplots_adjust(top=0.86)
for ext in ("pdf", "png"):
    fig.savefig(OUT / f"clock.{ext}", dpi=300)
print(
    f"Saved {OUT / 'clock.pdf'} (run {RUN}, {len(t)} samples, {len(configs)} configs)"
)
