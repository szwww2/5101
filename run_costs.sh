#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$task_root/todo04"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$task_root${PYTHONPATH:+:$PYTHONPATH}"
export CEG_BASELINE_OUTPUT="$(mktemp -d "$task_root/todo04/run-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
echo "TODO4 output: $CEG_BASELINE_OUTPUT"
echo "Open ca2-mesh-my.mn, Run, wait for COST MONITOR READY and 8 seconds warmup."
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
exec "$ryu_bin" \
    --observe-links --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 \
    "$task_root/dynamic_cost_controller.py"
