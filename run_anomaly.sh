#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
mkdir -p "$task_root/todo03"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$task_root${PYTHONPATH:+:$PYTHONPATH}"
export CEG_BASELINE_OUTPUT="$(mktemp -d "$task_root/todo03/run-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
echo "TODO3 output: $CEG_BASELINE_OUTPUT"
echo "Open ca2-mesh-my.mn, Run, wait for BASELINE READY and at least 8 seconds of stats."
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
exec "$ryu_bin" \
    --observe-links --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 \
    "$task_root/anomaly_controller.py"
