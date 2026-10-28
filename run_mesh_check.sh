#!/bin/bash
# Connectivity check for TODO1. Uses the acceptance prototype, not the final CA2 controller.
set -euo pipefail
task_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
task_out="$(mktemp -d "$task_root/todo01/mesh-check-XXXXXXXX")"
/usr/bin/python3 - "$task_root/todo01/mesh-check-template.json" "$task_out" <<'PY'
import json, sys
from pathlib import Path
config = json.loads(Path(sys.argv[1]).read_text())
config['output'] = sys.argv[2]
Path(sys.argv[2], 'config.json').write_text(json.dumps(config, indent=2))
PY
export CEG_VALIDATION_CONFIG="$task_out/config.json"
export PYTHONDONTWRITEBYTECODE=1
export PYTHONPATH="$task_root${PYTHONPATH:+:$PYTHONPATH}"
echo "Topology connectivity check; output: $task_out"
echo "Open ca2-mesh.mn in MiniEdit, Run, wait 15 seconds, then pingall."
ryu_bin="$(/usr/bin/python3 "$task_root/runtime_paths.py")"
exec "$ryu_bin" \
    --observe-links --ofp-listen-host 127.0.0.1 --ofp-tcp-listen-port 6653 \
    "$task_root/validation_controller.py"
