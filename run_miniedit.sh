#!/bin/bash
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
if [[ "$EUID" -ne 0 ]]; then
    echo 'Run: sudo bash ./run_miniedit.sh (Mininet needs Linux root privileges).'
    exit 2
fi
exec /usr/bin/python3 "$task_root/miniedit_compat.py" "$@"
