"""Read-only prerequisite check; does not start traffic or change services."""
import importlib.util
from pathlib import Path
import shutil
import subprocess
import sys
from runtime_paths import ryu_manager

def main():
    failed = []
    for name in ('ip', 'tc', 'ovs-vsctl', 'ovs-ofctl', 'iperf', 'hping3'):
        found = shutil.which(name)
        print(('OK' if found else 'MISSING'), name, found or '')
        if not found: failed.append(name)
    for module in ('mininet', 'tkinter'):
        found = importlib.util.find_spec(module) is not None
        print(('OK' if found else 'MISSING'), module)
        if not found: failed.append(module)
    bitmap = Path('/usr/include/X11/bitmaps/left_ptr')
    print(('OK' if bitmap.exists() else 'MISSING'), str(bitmap))
    if not bitmap.exists(): failed.append('xbitmaps')
    try:
        binary = ryu_manager()
        print('OK Ryu executable', binary)
        python = str(Path(binary).parent / 'python')
        result = subprocess.run([python, '-c',
            'import sys,ryu,eventlet,networkx; print("Ryu Python:",sys.version.split()[0],"NetworkX:",networkx.__version__)'],
            check=False)
        if result.returncode: failed.append('Ryu imports')
    except (RuntimeError, OSError) as error:
        print('MISSING', error); failed.append('Ryu')
    print('Missing prerequisites:', ', '.join(failed) if failed else 'none')
    return bool(failed)

if __name__ == '__main__':
    sys.exit(main())
