"""Resolve the Ryu executable on the current machine without a fixed username."""
import os
from pathlib import Path
import shutil

def ryu_manager():
    override = os.environ.get('CEG_RYU_MANAGER')
    if override:
        path = Path(override).expanduser()
        if path.is_file() and os.access(str(path), os.X_OK):
            return str(path.resolve())
        raise RuntimeError('CEG_RYU_MANAGER must name an executable ryu-manager file')
    candidates = [shutil.which('ryu-manager')]
    root = Path(__file__).resolve().parent
    candidates.append(root / '.venv/bin/ryu-manager')
    for install in ('miniforge3', 'miniconda3', 'anaconda3'):
        candidates.append(Path.home() / install / 'envs/ceg5101-ryu38/bin/ryu-manager')
    for candidate in candidates:
        if candidate and Path(candidate).is_file() and os.access(str(candidate), os.X_OK):
            return str(Path(candidate).resolve())
    raise RuntimeError('Activate ceg5101-ryu38 or set CEG_RYU_MANAGER to its absolute ryu-manager path')

if __name__ == '__main__':
    print(ryu_manager())
