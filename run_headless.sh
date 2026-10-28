#!/bin/bash
# Uses only its own t4 nodes and port 16659; existing bridges must be preserved.
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
scenario="${1:-B}"
case "$scenario" in A|B|C|all) ;; *) echo 'Choose A, B, C or all'; exit 2;; esac
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
if [[ "$EUID" -ne 0 ]]; then
    exec sudo env CEG_RYU_MANAGER="$ryu_bin" PYTHONDONTWRITEBYTECODE=1 \
      DISPLAY="${DISPLAY:-}" XAUTHORITY="${XAUTHORITY:-}" \
      CEG_USE_XVFB="${CEG_USE_XVFB:-0}" /bin/bash "$task_root/run_headless.sh" "$scenario"
fi
export CEG_RYU_MANAGER="$ryu_bin"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$task_root${PYTHONPATH:+:$PYTHONPATH}"
if [[ "${CEG_USE_XVFB:-0}" == 1 || -z "${DISPLAY:-}" ]]; then
    command -v xvfb-run >/dev/null || { echo 'Install xvfb and xauth, or supply a working DISPLAY.'; exit 2; }
    exec xvfb-run -a /usr/bin/python3 "$task_root/verify_rerouting.py" --case "$scenario"
fi
exec /usr/bin/python3 "$task_root/verify_rerouting.py" --case "$scenario"
