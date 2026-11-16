# TT Wormhole n300: Empirical Roofline Model

Empirical roofline model for the Tenstorrent Wormhole n300 accelerator. 
Handwritten TT-Metal kernels measure peak DRAM
bandwidth, L1/NoC bandwidth, and matmul compute throughput (TFLOPS) across
numerical formats and fidelities, and a Python benchmark that measures the same
things through TTNN's own operators for comparison.

## Repository layout

```
tenstorrent-roofline/
├── CMakeLists.txt       - builds 5 C++ benchmarks against a local tt-metal build
├── run_benchmarks.sh    - builds and runs everything, writes results/ (+ optional device profiler data)
├── run_batch1.sh        - profiler-off rerun of everything + peak_flops_block, out-of-box inputs, repeats
├── run_batch2.sh        - dram_add + TTNN add/exp in the same session, matmul repeats
├── run_repeats.sh       - repeats of the headline benchmarks (called by run_batch1.sh)
├── run_smi.sh           - matmul while logging tt-smi telemetry
├── run_repeats_random.sh - random input matmul matrix 10 times with telemetry
├── paper/figures/       - paper figures
├── benchmarks/          - benchmarks source
├── plots/               - plots
└── results/             - benchmark output (not in repo, generated when running)
```

## Requirements

- TT-Metal SDK v0.72.0 (commit `ba9340e3a45a`), built locally (`CMakeLists.txt`'s
  `TT_METAL_HOME` cache variable points at the build, edit it for your machine if you need to!!)
- `clang++-20`, CMake ≥3.20, Ninja
- Apptainer to run inside the container image referenced by
  `run_benchmarks.sh` (adjust the `CONTAINER` path at the top of that script
  for your own image, or run the built binaries directly on a host that
  already has the SDK available)
- Python 3 + `ttnn` (only needed for `benchmarks/ttnn_ops/bench_ttnn_ops.py`)
- `tt-smi` on the host (only needed for `run_smi.sh` and `run_repeats_random.sh`,
  set path with `TT_SMI=...`)

## Running

The run scripts are not marked executable here. Run them with `bash` as
below, or `chmod +x file.sh` first.

On the cluster, everything is launched with a single

```
srun -w csg-torrent -p torrent --gres=tt:n300s:4 --pty bash -lc 'cd /csghome/sc323/tt-analysis && bash run_benchmarks.sh'
```

With kernel profiler enabled:

```
srun -w csg-torrent -p torrent --gres=tt:n300s:4 --pty bash -lc 'cd /csghome/sc323/tt-analysis && ENABLE_DEVICE_PROFILER=1 bash run_benchmarks.sh'
```

For the new runs (profiler off, results go to results_<date>/):

```
srun -w csg-torrent -p torrent --gres=tt:n300s:4 --time=02:00:00 --pty bash -lc 'cd /csghome/sc323/tt-analysis && bash run_batch1.sh'
```
run_batch2.sh works the same way. Without --time, Slurm rejects the job on this cluster. That limit probably applies to your original srun lines too.

The telemetry runs poll `tt-smi -s` in the background and write `telemetry.csv`
next to the benchmark output (results_<date>_smi/ and results_<date>_random10/):

```
srun -w csg-torrent -p torrent --gres=tt:n300s:4 --time=01:00:00 --pty bash -lc 'cd /csghome/sc323/tt-analysis && bash run_smi.sh'
srun -w csg-torrent -p torrent --gres=tt:n300s:4 --time=03:00:00 --pty bash -lc 'cd /csghome/sc323/tt-analysis && bash run_repeats_random.sh'
```


## Plotting

```
uv run --no-project --with matplotlib --with numpy python plots/plot_paper_roofline.py results_2026-11-11_rep2 paper/figures results_2026-10-31_batch3 results_2026-11-14_random10
uv run --no-project --with matplotlib --with numpy python plots/plot_paper_figures.py results_2026-11-14_random10 results_2026-10-31_batch3
uv run --no-project --with matplotlib python plots/plot_clock.py results_2026-11-14_random10 2
pdflatex -output-directory=paper/figures plots/noc_routing.tex
```

The matmul plots use the median over all `peak_flops_block_matrix*.csv` in the
given folder. `plot_clock.py` plots clock and power during one run.

Running this on another machine, you will have to edit `THESIS`/`TT_METAL`/`CONTAINER`
in `run_benchmarks.sh` to point at your own paths, or skip the
script entirely and run the built binaries (plus
`python3 benchmarks/ttnn_ops/bench_ttnn_ops.py`) directly on a host that
already has the SDK set up.
