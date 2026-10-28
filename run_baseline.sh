#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export PYTHONDONTWRITEBYTECODE=1
export CEG_BASELINE_OUTPUT="$(mktemp -d "$task_root/todo02/run-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
echo "TODO2 baseline output: $CEG_BASELINE_OUTPUT"
echo "Open ca2-mesh-my.mn and Run; wait for BASELINE READY before ping."
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
exec "$ryu_bin" \
    --observe-links --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 \
    "$task_root/baseline_controller.py"
