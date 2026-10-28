"""Run the validated timed measurement inside the student's current MiniEdit CLI."""
from pathlib import Path
from inspect_rerouting import read_json
import verify_rerouting


def run(net, output=None, prefix=''):
    root = Path(__file__).resolve().parent
    out = Path(output) if output else max((root / 'todo05').glob('run-*'), key=lambda p: p.stat().st_mtime)
    state = read_json(out / 'state.json')
    if not state['ready']:
        # Independent integration harness may invoke this immediately after Run.
        import time
        deadline = time.monotonic()+40
        while not state['ready'] and not state['failed'] and time.monotonic() < deadline:
            time.sleep(.2)
            state = read_json(out / 'state.json')
    assert state['ready'] and not state['failed'], 'Wait for REROUTING READY'
    assert set(prefix+'h'+str(i) for i in range(1, 7)).issubset(set(net.keys())), 'Open the six-host mesh'
    print('Output:', out, flush=True)
    print('60 seconds: baseline 0-12s, flood 12-26s, recovery afterwards.', flush=True)
    print('Watch controller BLOCK/ROUTE lines. Capture screenshots of these and the final summary.', flush=True)
    result = verify_rerouting.run(state['scenario'], existing_net=net, existing_output=out, existing_prefix=prefix)
    print('Actual paths:', result['initial_path'], '->', result['during_path'], '->', result['recovered_path'])
    for phase, metrics in result['windows'].items():
        print(phase, 'receiver %.3f Mbps, loss %.4f%% (%s/%s)' % (
            metrics['receiver_mbps'], metrics['loss_percent'], metrics['lost'], metrics['total']))
    print('All-switch source blocks preserved; cost/route recovered; source still blocked.')
    print('Saved results.json, receiver.log, continuous-ping.log, events.jsonl and dataplane-samples.jsonl.')
    return str(out)
