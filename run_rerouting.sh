#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
export CEG_SCENARIO="${1:-B}"
case "$CEG_SCENARIO" in A|B|C) ;; *) echo 'Choose A, B or C'; exit 2;; esac
mkdir -p "$task_root/todo05"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$task_root${PYTHONPATH:+:$PYTHONPATH}"
export CEG_BASELINE_OUTPUT="$(mktemp -d "$task_root/todo05/run-$CEG_SCENARIO-$(date +%Y%m%d-%H%M%S)-XXXXXX")"
echo "Teacher Task4 / internal TODO5, scenario $CEG_SCENARIO output: $CEG_BASELINE_OUTPUT"
echo 'Open ca2-mesh-my.mn, Run, wait for REROUTING READY then >=8s warmup.'
if [[ "$CEG_SCENARIO" == C ]]; then
    echo 'DISCLOSED CONDITION: only h5->h6 IPv4 pair pinned to direct s5->s6; original base costs unchanged.'
fi
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
exec "$ryu_bin" \
    --observe-links --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 \
    "$task_root/rerouting_controller.py"
