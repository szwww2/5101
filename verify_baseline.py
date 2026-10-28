"""Exercise TODO2 with a real MiniEdit network, isolated names and port 16656."""
import importlib.util
import json
import os
from pathlib import Path
import re
import signal
import socket
import subprocess
import time

from mininet.log import setLogLevel

ROOT = Path(__file__).resolve().parent
PORT = 16656
from runtime_paths import ryu_manager
RYU = ryu_manager()


def run(anomaly=False, costs=False):
    assert os.geteuid() == 0
    setLogLevel('warning')
    anomaly = anomaly or costs
    port = PORT + 2 if costs else PORT + 1 if anomaly else PORT
    controller_file = 'dynamic_cost_controller.py' if costs else 'anomaly_controller.py' if anomaly else 'baseline_controller.py'
    out = ROOT / ('todo04' if costs else 'todo03' if anomaly else 'todo02') / ('verification-' + time.strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True)
    before = subprocess.check_output(['ovs-vsctl', 'list-br'], text=True).splitlines()
    assert not any(name in before for name in ['b2s'+str(i) for i in range(1, 7)])
    with socket.socket() as probe:
        probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        probe.bind(('127.0.0.1', port))
    app = controller = server = net = attack = legitimate = None
    result = dict(status='RUNNING', output=str(out), controller=controller_file,
                  scope='Assistant isolated verification; student observation pending')
    log = (out / 'ryu.log').open('w')
    server_log = (out / 'iperf-receiver.log').open('w')
    try:
        document = json.loads((ROOT / 'todo01/ca2-mesh-my.mn').read_text())
        document['application']['startCLI'] = '0'
        for kind in ('hosts', 'switches', 'controllers'):
            for node in document[kind]:
                opts = node['opts']
                opts['hostname'] = 'b2' + opts['hostname']
                if 'controllers' in opts:
                    opts['controllers'] = ['b2c0']
                if 'startCommand' in opts:
                    opts['startCommand'] = opts['startCommand'].replace('dev h', 'dev b2h')
                if kind == 'controllers':
                    opts['remotePort'] = port
        for link in document['links']:
            link['src'] = 'b2' + link['src']
            link['dest'] = 'b2' + link['dest']
        shadow = out / 'mesh.mn'
        shadow.write_text(json.dumps(document))
        env = dict(os.environ, CEG_BASELINE_OUTPUT=str(out), PYTHONDONTWRITEBYTECODE='1',
                   PYTHONPATH=str(ROOT)+os.pathsep+os.environ.get('PYTHONPATH', ''))
        controller = subprocess.Popen([RYU, '--observe-links', '--ofp-listen-host',
            '127.0.0.1', '--ofp-tcp-listen-port', str(port), str(ROOT / controller_file)],
            env=env, stdout=log, stderr=subprocess.STDOUT)
        for _ in range(100):
            assert controller.poll() is None, 'Ryu exited; see ryu.log'
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1', port)) == 0:
                    break
            time.sleep(.1)
        else:
            raise AssertionError('Ryu did not listen')
        spec = importlib.util.spec_from_file_location('baseline_gui', ROOT / 'miniedit_compat.py')
        gui = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(gui)
        errors = []
        gui.showerror = lambda *a, **kw: errors.append(str(a))
        app = gui.MiniEdit()
        app.winfo_toplevel().withdraw()
        gui.tkFileDialog.askopenfile = lambda **kw: shadow.open('rb')
        app.loadTopology()
        assert not errors, errors
        app.start()
        net = app.net
        for _ in range(160):
            state_path = out / 'state.json'
            state = json.loads(state_path.read_text()) if state_path.exists() else {}
            assert not state.get('failed'), state
            if state.get('ready'):
                break
            time.sleep(.25)
        else:
            raise AssertionError('LLDP discovery/barriers did not become ready')
        assert state['directed_links'] == 22 and len(state['routes']) == 30
        (out / 'ready-state.json').write_text(json.dumps(state, indent=2))
        assert net.pingAll(timeout='1') == 0
        ping = net['b2h1'].cmd('ping -c 5 -W 1 10.0.0.6')
        (out / 'h1-h6-ping.txt').write_text(ping)
        assert ', 0% packet loss' in ping, ping

        def capture(label):
            dumps = {i: subprocess.check_output(['ovs-ofctl', '-O', 'OpenFlow13',
                '--no-names', 'dump-flows', 'b2s'+str(i)], text=True) for i in range(1, 7)}
            (out / (label + '-flows.json')).write_text(json.dumps(dumps, indent=2))
            return dumps

        def rule(dumps, n):
            rows = [r for r in dumps[n].splitlines() if 'priority=100,' in r
                    and 'nw_src=10.0.0.1,' in r and 'nw_dst=10.0.0.6 ' in r]
            assert len(rows) <= 1, rows
            return rows[0] if rows else None

        initial = capture('before-udp')
        path, n = [], 1
        while n not in path:
            path.append(n)
            row = rule(initial, n)
            assert row, (n, initial[n])
            port = int(re.search(r'actions=output:(\d+)', row).group(1))
            if n == 6:
                assert port == 1
                break
            intf = next(i for i in net['b2s'+str(n)].intfList() if net['b2s'+str(n)].ports[i] == port)
            peer = intf.link.intf2 if intf.link.intf1 == intf else intf.link.intf1
            n = int(peer.node.name.replace('b2s', ''))
        assert path == [1, 2, 6], path
        server = net['b2h6'].popen(['iperf', '-s', '-u', '-p', '5001', '-i', '1'],
                                 stdout=server_log, stderr=subprocess.STDOUT)
        time.sleep(.5)
        client = net['b2h1'].popen(['iperf', '-c', '10.0.0.6', '-u', '-b', '10000000',
                                   '-t', '12', '-i', '1', '-p', '5001'],
                                  stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        try:
            udp, _ = client.communicate(timeout=22)
        finally:
            if client.poll() is None:
                client.terminate()
                client.wait(timeout=3)
        (out / 'iperf-client.txt').write_text(udp)
        assert client.returncode == 0, udp
        summary = re.findall(r'([\d.]+) Mbits/sec\s+[\d.]+ ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)', udp)
        assert summary, udp
        mbps, lost, total, loss = summary[-1]
        assert float(mbps) > 8 and float(loss) < 5, summary[-1]
        final = capture('after-udp')
        deltas = {}
        for n in path:
            count = lambda row: int(re.search(r'n_packets=(\d+)', row).group(1))
            deltas[n] = count(rule(final, n)) - count(rule(initial, n))
            assert deltas[n] > 1000, deltas
        for n in set(range(1, 7)) - set(path):
            assert rule(final, n) is None
        result.update(status='PASS', pingall_received=30, pingall_total=30,
            ping_h1_h6_received=5, actual_path=path, switch_path_cost=19,
            route_packet_deltas=deltas, receiver_mbps=float(mbps),
            receiver_loss_percent=float(loss), receiver_lost=int(lost),
            receiver_total=int(total), offered_udp_mbps=10, duration_seconds=12)
        if anomaly:
            anomaly_path = out / 'anomaly-state.json'
            observed = json.loads(anomaly_path.read_text())
            assert observed['blocked'] == [], observed
            assert all(s['samples'] >= 5 for s in observed['sources'].values()), observed
            (out / 'normal-anomaly-state.json').write_text(json.dumps(observed, indent=2))
            if costs:
                history = [json.loads(line) for line in (out / 'link-costs.jsonl').read_text().splitlines()]
                normal_links = [s['links']['2>6'] for s in history if s['ready']
                                and s['links']['2>6']['received_bps'] > 8000000
                                and s['links']['2>6']['penalty'] == 0]
                assert normal_links, 'No measured normal link load'
                normal_link = normal_links[-1]
                assert 15 < normal_link['cost'] < 16, normal_link
                (out / 'cost-normal.json').write_text(json.dumps(normal_link, indent=2))
            legitimate = net['b2h1'].popen(['iperf', '-c', '10.0.0.6', '-u', '-b',
                '10000000', '-t', '32' if costs else '18', '-i', '1', '-p', '5001'],
                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            time.sleep(1)
            with (out / 'h2-flood.log').open('w') as attack_log:
                attack = net['b2h2'].popen(['timeout', '14s' if costs else '6s', 'hping3', '-1', '--flood', '10.0.0.6'],
                    stdout=attack_log, stderr=subprocess.STDOUT)
                for _ in range(40):
                    observed = json.loads(anomaly_path.read_text())
                    if observed['blocked']:
                        break
                    time.sleep(.25)
                assert observed['blocked'] == ['10.0.0.2'], observed
                if costs:
                    block_record = next(json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()
                                        if json.loads(line)['event'] == 'block')
                    until = block_record['time']+9
                    while time.time() < until:
                        time.sleep(.1)
                    assert attack.poll() is None, 'Flood must still be active beyond minimum hold'
                    cost_during = json.loads((out / 'cost-state.json').read_text())
                    active_link = cost_during['links']['2>6']
                    assert active_link['penalty'] == 60 and active_link['cost'] >= 74, active_link
                    assert cost_during['links']['6>2']['penalty'] == 0
                    (out / 'cost-active-after-minimum-hold.json').write_text(json.dumps(cost_during, indent=2))
                attack.wait(timeout=17 if costs else 9)
            after_attack = capture('after-attack')
            ingress_drop = [r for r in after_attack[2].splitlines()
                            if 'priority=5000,' in r and 'nw_src=10.0.0.2 ' in r]
            assert len(ingress_drop) == 1 and 'actions=drop' in ingress_drop[0], ingress_drop
            drop_count = int(re.search(r'n_packets=(\d+)', ingress_drop[0]).group(1))
            assert drop_count > 0, ingress_drop
            for n in range(1, 7):
                assert 'priority=5000,ip,nw_src=10.0.0.2 actions=drop' in after_attack[n]
            post_ping = net['b2h1'].cmd('ping -c 3 -W 1 10.0.0.6')
            (out / 'legitimate-post-block-ping.txt').write_text(post_ping)
            assert ', 0% packet loss' in post_ping, post_ping
            blocked_ping = net['b2h2'].cmd('ping -c 2 -W 1 10.0.0.6')
            (out / 'blocked-source-ping.txt').write_text(blocked_ping)
            assert '100% packet loss' in blocked_ping, blocked_ping
            during, _ = legitimate.communicate(timeout=20)
            (out / 'legitimate-during-attack-iperf.txt').write_text(during)
            assert legitimate.returncode == 0, during
            summaries = re.findall(r'([\d.]+) Mbits/sec\s+[\d.]+ ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)', during)
            assert summaries, during
            observed = json.loads(anomaly_path.read_text())
            assert observed['blocked'] == ['10.0.0.2'], observed
            (out / 'final-anomaly-state.json').write_text(json.dumps(observed, indent=2))
            events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
            blocks = [e for e in events if e['event'] == 'block']
            assert len(blocks) == 1 and blocks[0]['source'] == '10.0.0.2', blocks
            assert blocks[0]['pps'] > blocks[0]['threshold_pps']
            assert blocks[0]['old_ema_pps'] == blocks[0]['new_ema_pps']
            assert not [e for e in events if e['event'] in ('openflow_error', 'barrier_timeout', 'stats_timeout', 'port_stats_timeout')]
            result['anomaly'] = dict(blocked=observed['blocked'], block_event=blocks[0],
                ingress_drop_packets=drop_count, legitimate_post_block_ping_received=3,
                blocked_source_ping_loss_percent=100, victim_echo_replies_not_blocked=True,
                legitimate_during_attack_mbps=float(summaries[-1][0]),
                legitimate_during_attack_loss_percent=float(summaries[-1][3]),
                dynamic_link_costs=costs)
            if costs:
                recovered = json.loads((out / 'cost-state.json').read_text())
                assert recovered['links']['2>6']['penalty'] == 0, recovered
                assert recovered['links']['2>6']['cost'] < 16, recovered
                assert recovered['blocked'] == ['10.0.0.2'], recovered
                assert any(e['event'] == 'penalty_restored' for e in events), events
                for n, expected_port in ((1, 2), (2, 6), (6, 1)):
                    assert 'actions=output:'+str(expected_port) in rule(after_attack, n)
                (out / 'cost-recovered.json').write_text(json.dumps(recovered, indent=2))
                result['costs'] = dict(normal_link=normal_link,
                    active_link_after_minimum_hold=active_link,
                    recovered_link=recovered['links']['2>6'],
                    recovered_penalty_while_source_remains_blocked=True,
                    directed_reverse_link_not_penalized=True,
                    route_rules_remain_static=True, flood_duration_seconds=14,
                    minimum_hold_seconds=8, quiet_seconds=5)
            assert 'Traceback (most recent call last)' not in (out / 'ryu.log').read_text()
    except Exception as exc:
        result.update(status='FAIL', error=repr(exc))
        raise
    finally:
        for process in (attack, legitimate, server, controller):
            if process is not None and process.poll() is None:
                if process is controller:
                    process.terminate()
                else:
                    process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        if net is None and app is not None:
            net = app.net
        if net is not None:
            net.stop()
        if app is not None:
            app.winfo_toplevel().destroy()
        log.close()
        server_log.close()
        after = subprocess.check_output(['ovs-vsctl', 'list-br'], text=True).splitlines()
        result['original_bridges_preserved'] = before == after
        (out / 'results.json').write_text(json.dumps(result, indent=2))
        assert before == after, (before, after)
        print(json.dumps(result, indent=2), flush=True)


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--anomaly', action='store_true')
    parser.add_argument('--costs', action='store_true')
    args = parser.parse_args()
    run(anomaly=args.anomaly, costs=args.costs)
