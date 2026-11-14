#!/bin/bash
# Random input matmul matrix (peak_flops_block, both APIs) repeated REPEATS times,
# each run a separate process, with tt-smi telemetry logged during all runs
#
#   srun -w csg-torrent -p torrent --gres=tt:n300s:4 --time=03:00:00 --pty bash -lc \
#     'cd /csghome/sc323/tt-analysis && bash run_repeats_random.sh'
set -uo pipefail

THESIS=/csghome/sc323/tt-analysis
TT_METAL=/csghome/sc323/tt-metal
CONTAINER=/csghome/sc323/tt-metalium-ubuntu-22.04-release-amd64_latest-rc.sif
BUILD=$THESIS/build
REPEATS=${REPEATS:-10}
OUT=${OUT:-$THESIS/results_$(date +%Y-%m-%d)_random10}
LIBS="$TT_METAL/build_Release/tt_metal:$TT_METAL/build_Release/tt_stl:$TT_METAL/build_Release/tt_metal/third_party/umd/lib"

TT_SMI=${TT_SMI:-/csghome/sc323/.conda/envs/jon/bin/tt-smi}
"$TT_SMI" -v > /dev/null 2>&1 || { echo "$TT_SMI does not start on $(hostname)"; exit 1; }
command -v python3 > /dev/null || { echo "python3 not found on the host"; exit 1; }
mkdir -p "$OUT"
echo "Repeats: $REPEATS, output: $OUT"

run() {
    local name="$1"
    shift
    echo "=== $name ==="
    apptainer exec --bind /csghome/sc323:/csghome/sc323 "$CONTAINER" bash -lc "
        cd $THESIS
        export TT_METAL_HOME=$TT_METAL TT_METAL_RUNTIME_ROOT=$TT_METAL
        export LD_LIBRARY_PATH=$LIBS:\${LD_LIBRARY_PATH:-}
        unset TT_METAL_DEVICE_PROFILER
        $*" 2>&1 | while IFS= read -r line; do echo "$(date +%s.%N) $line"; done | tee "$OUT/$name.txt"
}

poll() {
    echo "time,bus_id,board_type,aiclk_mhz,power_w,current_a,voltage_v,temp_c,throttler" > "$OUT/telemetry.csv"
    while true; do
        "$TT_SMI" -s --snapshot_no_tty < /dev/null 2>> "$OUT/tt-smi_stderr.txt" | python3 -c '
import json, sys, time
s = sys.stdin.read()
t = "%.2f" % time.time()
if "{" not in s:
    sys.stderr.write(t + " no snapshot\n")
    sys.exit()
d = json.loads(s[s.index("{"):])
for x in d["device_info"]:
    b, m = x["board_info"], x["telemetry"]
    row = [t, b["bus_id"], b["board_type"], m["aiclk"], m["power"], m["current"],
           m["voltage"], m["asic_temperature"], x["smbus_telem"]["THROTTLER"]]
    print(",".join(str(v).strip() for v in row))
' >> "$OUT/telemetry.csv" 2>> "$OUT/tt-smi_stderr.txt"
        sleep 1
    done
}

run build cmake --build "$BUILD" --target peak_flops_block

poll &
POLL_PID=$!
trap 'kill $POLL_PID 2> /dev/null' EXIT

sleep 15
for rep in $(seq 1 "$REPEATS"); do
    run "peak_flops_block_$rep" "$BUILD/peak_flops_block" \
        "$OUT/peak_flops_block_matrix_$rep.csv" - -
done
sleep 15

kill $POLL_PID 2> /dev/null
echo "Done. Telemetry rows: $(($(wc -l < "$OUT/telemetry.csv") - 1))"
