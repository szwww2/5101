"""Capture real OpenFlow outputs and trace VLAN-tagged h1->h6 forwarding."""
import json
from pathlib import Path
import re
import subprocess
import time


def read_json(path):
    # WSL DrvFS rename can briefly make a concurrently replaced file invisible.
    for attempt in range(20):
        try:
            return json.loads(Path(path).read_text())
        except (FileNotFoundError, json.JSONDecodeError):
            if attempt == 19:
                raise
            time.sleep(.01)


def capture(out, prefix='', label=None):
    out = Path(out)
    state = read_json(out / 'state.json')
    costs = read_json(out / 'cost-state.json')
    flows = {n: subprocess.check_output(['ovs-ofctl', '-O', 'OpenFlow13',
        '--no-names', 'dump-flows', prefix+'s'+str(n)], text=True) for n in range(1, 7)}
    links = json.loads(subprocess.check_output(['ovs-vsctl', '--format=json',
        '--columns=name,ofport', 'list', 'Interface'], text=True))
    # Use the saved mesh's verified endpoint map, not the controller route string.
    ports = {1: {2: 2, 3: 4, 4: 5}, 2: {2: 1, 3: 3, 4: 5, 5: 4, 6: 6},
             3: {2: 2, 3: 6, 4: 5}, 4: {2: 5, 3: 1, 4: 2},
             5: {2: 4, 3: 6, 4: 2, 5: 1, 6: 3}, 6: {2: 5, 3: 3, 4: 2}}
    def rows(n, priority):
        return [r for r in flows[n].splitlines() if 'priority='+str(priority)+',' in r
                and 'nw_src=10.0.0.1,' in r and 'nw_dst=10.0.0.6 ' in r]
    ingress = rows(1, 100)
    assert len(ingress) == 1, ingress
    tag = int(re.search(r'set_field:(\d+)->vlan_vid', ingress[0]).group(1)) & 0xfff
    path, counts, n = [], {}, 1
    while n not in path:
        path.append(n)
        matching = ingress if n == 1 else [r for r in rows(n, 200) if 'dl_vlan='+str(tag)+',' in r or 'dl_vlan='+str(tag)+' ' in r]
        assert len(matching) == 1, (n, tag, matching, flows[n])
        row = matching[0]
        counts[n] = int(re.search(r'n_packets=(\d+)', row).group(1))
        port = int(re.search(r'output:(\d+)', row).group(1))
        if n == 6:
            assert port == 1 and 'pop_vlan' in row
            break
        assert port in ports[n], (n, port)
        # Linux veth's peer ifindex must correspond to the expected next switch.
        peer = ports[n][port]
        local = prefix+'s'+str(n)+'-eth'+str(port)
        peer_index = int(Path('/sys/class/net', local, 'iflink').read_text())
        peer_names = [p.name for p in Path('/sys/class/net').iterdir()
                      if int((p / 'ifindex').read_text()) == peer_index]
        assert len(peer_names) == 1 and peer_names[0].startswith(prefix+'s'+str(peer)+'-eth'), (local, peer_names)
        n = peer
    else:
        raise AssertionError('Loop in actual flow outputs')
    drop = {n: [r for r in text.splitlines() if 'priority=5000,' in r] for n, text in flows.items()}
    result = dict(time=time.time(), actual_path=path, active_vlan=tag,
                  path_packet_counts=counts, installed=state, costs=costs, drops=drop,
                  interface_inventory=links, flows=flows)
    if label:
        dest = out / 'evidence'
        dest.mkdir(exist_ok=True)
        (dest / (label+'.json')).write_text(json.dumps(result, indent=2))
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('label', help='before, during, after, or another evidence label')
    parser.add_argument('--output')
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    out = Path(args.output) if args.output else max((root / 'todo05').glob('run-*'), key=lambda p: p.stat().st_mtime)
    result = capture(out, label=args.label)
    edge = {'A': '2>3', 'B': '2>6', 'C': '5>6'}[result['installed']['scenario']]
    item = result['costs']['links'][edge]
    print('Actual h1->h6 path:', result['actual_path'], 'VLAN:', result['active_vlan'])
    print('Current path counters:', result['path_packet_counts'])
    print('Link', edge, 'Mbps=%.3f cost=%.3f penalty=%.1f' % (item['received_bps']/1e6, item['cost'], item['penalty']))
    print('Blocked:', result['costs']['blocked'])
    print('Saved:', out / 'evidence' / (args.label+'.json'))
