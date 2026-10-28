"""Isolated saved-MiniEdit integration tests for all three Teacher Task4 cases."""
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
from inspect_rerouting import capture, read_json
from task4_evidence import controller_log_check

ROOT = Path(__file__).resolve().parent
from runtime_paths import ryu_manager
RYU = ryu_manager()


def run(case, existing_net=None, existing_output=None, existing_prefix='', use_student_entry=False):
    assert os.geteuid() == 0
    setLogLevel('warning')
    prefix, port = (existing_prefix if existing_net is not None else 't4'), 16659
    out = Path(existing_output) if existing_output else ROOT / 'todo05' / ('verification-'+case+'-'+time.strftime('%Y%m%d-%H%M%S'))
    out.mkdir(parents=True, exist_ok=existing_net is not None)
    if existing_net is not None:
        # Preflight outside the result-writing try/finally preserves previous evidence.
        assert not (out / 'results.json').exists(), 'Start a fresh controller round; previous results preserved'
        assert read_json(out / 'state.json')['scenario'] == case
        assert read_json(out / 'anomaly-state.json')['blocked'] == [], 'Restart controller/network before each case'
    before = subprocess.check_output(['ovs-vsctl', 'list-br'], text=True).splitlines()
    if existing_net is None:
        assert not any(n.startswith(prefix) for n in before), before
        with socket.socket() as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            probe.bind(('127.0.0.1', port))
    app = net = controller = server = client = attack = ping = None
    files = []
    result = dict(status='RUNNING', scenario=case, output=str(out),
                  scope='Student current MiniEdit network' if existing_net is not None and not prefix else 'Assistant isolated validation, not student experiment')
    def logfile(name):
        f = (out / name).open('w')
        files.append(f)
        return f
    def read(name):
        return read_json(out / name)
    def wait_for(fn, seconds=40):
        deadline = time.monotonic()+seconds
        while time.monotonic() < deadline:
            assert controller is None or controller.poll() is None, 'Controller exited'
            state = read('state.json') if (out / 'state.json').exists() else {}
            assert not state.get('failed'), state
            value = fn()
            if value:
                return value
            time.sleep(.2)
        raise AssertionError('Condition timed out')
    try:
        if existing_net is None:
            document = json.loads((ROOT / 'todo01/ca2-mesh-my.mn').read_text())
            document['application']['startCLI'] = '0'
            for kind in ('hosts', 'switches', 'controllers'):
                for node in document[kind]:
                    opts = node['opts']
                    opts['hostname'] = prefix+opts['hostname']
                    if 'controllers' in opts:
                        opts['controllers'] = [prefix+'c0']
                    if 'startCommand' in opts:
                        opts['startCommand'] = opts['startCommand'].replace('dev h', 'dev '+prefix+'h')
                    if kind == 'controllers':
                        opts['remotePort'] = port
            for link in document['links']:
                link['src'], link['dest'] = prefix+link['src'], prefix+link['dest']
            shadow = out / 'mesh.mn'
            shadow.write_text(json.dumps(document))
            env = dict(os.environ, CEG_BASELINE_OUTPUT=str(out), CEG_SCENARIO=case,
                       PYTHONDONTWRITEBYTECODE='1', PYTHONPATH=str(ROOT))
            controller = subprocess.Popen([RYU, '--observe-links', '--ofp-listen-host',
                '127.0.0.1', '--ofp-tcp-listen-port', str(port), str(ROOT / 'rerouting_controller.py')],
                env=env, stdout=logfile('ryu.log'), stderr=subprocess.STDOUT)
            def listening():
                with socket.socket() as s:
                    return s.connect_ex(('127.0.0.1', port)) == 0
            wait_for(listening, 15)
            spec = importlib.util.spec_from_file_location('task4_gui', ROOT / 'miniedit_compat.py')
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
        else:
            net = existing_net
        if use_student_entry:
            import student_task4_experiment
            student_task4_experiment.run(net, output=out, prefix=prefix)
            result = read('results.json')
            result['student_entry_verified'] = True
            return result
        wait_for(lambda: (out / 'anomaly-state.json').exists()
                 and read('cost-state.json')['ready']
                 and all(s['samples'] >= 5 for s in read('anomaly-state.json')['sources'].values()))
        assert net.pingAll(timeout='1') == 0
        first = capture(out, prefix, 'initial')
        assert first['actual_path'] == [1, 2, 6], first['actual_path']
        attack_src, attack_dst, edge = {'A': (2, 3, '2>3'), 'B': (2, 6, '2>6'), 'C': (5, 6, '5>6')}[case]
        attack_route = first['installed']['routes']['10.0.0.'+str(attack_src)+'>10.0.0.'+str(attack_dst)]['path']
        assert attack_route == [attack_src, attack_dst], attack_route
        server = net[prefix+'h6'].popen(['iperf', '-s', '-u', '-p', '5001', '-i', '1', '-f', 'm'],
            stdout=logfile('receiver.log'), stderr=subprocess.STDOUT)
        time.sleep(.5)
        started = time.time()
        client = net[prefix+'h1'].popen(['iperf', '-c', '10.0.0.6', '-u', '-b', '10000000',
            '-t', '60', '-i', '1', '-p', '5001', '-f', 'm'], stdout=logfile('sender.log'), stderr=subprocess.STDOUT)
        ping = net[prefix+'h1'].popen(['ping', '-D', '-i', '0.5', '-W', '1', '10.0.0.6'],
            stdout=logfile('continuous-ping.log'), stderr=subprocess.STDOUT)
        samples = []
        attack_started = None
        for second in range(60):
            elapsed = time.time()-started
            if elapsed >= 12 and attack is None:
                attack_started = time.time()
                attack = net[prefix+'h'+str(attack_src)].popen(['timeout', '14s', 'hping3', '-1',
                    '--flood', '10.0.0.'+str(attack_dst)], stdout=logfile('flood.log'), stderr=subprocess.STDOUT)
            sample = capture(out, prefix)
            sample['elapsed'] = elapsed
            samples.append(sample)
            with (out / 'dataplane-samples.jsonl').open('a') as f:
                f.write(json.dumps(sample)+'\n')
            source = '10.0.0.'+str(attack_src)
            if source in sample['costs']['blocked']:
                assert all(any('nw_src='+source+' ' in row for row in rows)
                           for rows in sample['drops'].values()), 'Drop disappeared during rerouting/GC'
            if second % 10 == 0:
                print(case, 'elapsed=%.1f' % elapsed, 'path='+str(sample['actual_path']),
                      'penalty='+str(sample['costs']['links'][edge]['penalty']), flush=True)
            time.sleep(max(0, started+second+1-time.time()))
        client.wait(timeout=10)
        attack.wait(timeout=3)
        ping.send_signal(signal.SIGINT)
        ping.wait(timeout=3)
        last = capture(out, prefix, 'recovered')
        assert last['actual_path'] == [1, 2, 6]
        assert last['costs']['links'][edge]['penalty'] == 0
        assert last['costs']['blocked'] == [source]
        active = [s for s in samples if s['costs']['links'][edge]['penalty'] == 60]
        assert active and max(s['costs']['links'][edge]['received_bps'] for s in samples) > 1e6
        expected = [1, 2, 3, 6] if case == 'B' else [1, 2, 6]
        assert any(s['actual_path'] == expected for s in active), [s['actual_path'] for s in active]
        if case != 'B':
            assert all(s['actual_path'] == expected for s in samples)
        # The installed active-version downstream rules must carry real traffic.
        for s in samples:
            if 18 < s['elapsed'] < 23:
                assert all(count > 0 for count in s['path_packet_counts'].values()), s['path_packet_counts']
        rows = last['drops'][attack_src]
        dropped = int(re.search(r'n_packets=(\d+)', rows[0]).group(1))
        assert dropped > 1000
        normal_ping = net[prefix+'h1'].cmd('ping -c 3 -W 1 10.0.0.6')
        blocked_ping = net[prefix+'h'+str(attack_src)].cmd('ping -c 2 -W 1 10.0.0.'+str(attack_dst))
        (out / 'post-pings.txt').write_text(normal_ping+'\n'+blocked_ping)
        assert ', 0% packet loss' in normal_ping
        assert ', 100% packet loss' in blocked_ping
        text = (out / 'sender.log').read_text()
        summary = re.findall(r'([\d.]+) Mbits/sec\s+[\d.]+ ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)', text)
        assert summary, text
        mbps, lost, total, loss = summary[-1]
        assert float(mbps) > 8 and float(loss) < 5, summary[-1]
        # Receiver intervals report delivered bytes and lost datagrams, not offered traffic.
        intervals = []
        for line in (out / 'receiver.log').read_text().splitlines():
            m = re.search(r'([\d.]+)-\s*([\d.]+) sec\s+[\d.]+ MBytes\s+([\d.]+) Mbits/sec\s+([\d.]+) ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)', line)
            if m and .5 < float(m[2])-float(m[1]) < 1.5:
                a, b, rate, jitter, lost_i, total_i, percent = m.groups()
                intervals.append(dict(start=float(a), end=float(b), mbps=float(rate),
                    jitter_ms=float(jitter), lost=int(lost_i), total=int(total_i)))
        assert len(intervals) >= 58 and all(r['mbps'] > 0 for r in intervals), 'One-second receiver outage'
        ping_text = (out / 'continuous-ping.log').read_text()
        reply_times = [float(t) for t in re.findall(r'^\[([\d.]+)\].*bytes from', ping_text, re.M)]
        assert len(reply_times) >= 100, ping_text
        max_reply_gap = max(b-a for a, b in zip(reply_times, reply_times[1:]))
        assert max_reply_gap < 3, max_reply_gap
        windows = {}
        for name, lo, hi in [('before', 4, 10), ('during', 15, 24), ('after', 40, 55)]:
            selected = [r for r in intervals if r['start'] >= lo and r['end'] <= hi]
            assert len(selected) >= hi-lo-2, (name, intervals)
            total_i, lost_i = sum(r['total'] for r in selected), sum(r['lost'] for r in selected)
            duration = sum(r['end']-r['start'] for r in selected)
            windows[name] = dict(start_seconds=lo, end_seconds=hi, intervals=len(selected),
                receiver_mbps=sum(r['mbps']*(r['end']-r['start']) for r in selected)/duration,
                loss_percent=100*lost_i/total_i, lost=lost_i, total=total_i)
        events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
        assert not any(e['event'] in ('openflow_error', 'routing_failure', 'barrier_timeout',
            'stats_timeout', 'port_stats_timeout') for e in events)
        log_check = controller_log_check(out, required=controller is not None)
        assert any(e['event'] == 'old_version_removed' for e in events) if case == 'B' else True
        result.update(status='PASS', initial_path=first['actual_path'], during_path=expected,
            recovered_path=last['actual_path'], receiver_mbps=float(mbps), loss_percent=float(loss),
            lost=int(lost), total=int(total), windows=windows, receiver_intervals=intervals,
            dropped_packets=dropped, drops_preserved_all_samples=True,
            source_remains_blocked_after_cost_and_route_recovery=True,
            source=source, attack_path=attack_route, attack_started=attack_started,
            legitimate_started=started, scenario_c_pin_disclosed=case == 'C')
        result.update(receiver_positive_every_one_second_interval=True,
                      continuous_ping_replies=len(reply_times), maximum_ping_reply_gap_seconds=max_reply_gap,
                      controller_log_check=log_check)
    except Exception as exc:
        import traceback
        result.update(status='FAIL', error=repr(exc), traceback=traceback.format_exc())
        print('Experiment error:', repr(exc), flush=True)
        raise
    finally:
        for process in (attack, client, ping, server, controller):
            if process is not None and process.poll() is None:
                process.terminate() if process is controller else process.send_signal(signal.SIGINT)
                try:
                    process.wait(timeout=4)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)
        if net is None and app is not None:
            net = app.net
        if net is not None and existing_net is None:
            net.stop()
        if app is not None:
            app.winfo_toplevel().destroy()
        for f in files:
            f.close()
        after = subprocess.check_output(['ovs-vsctl', 'list-br'], text=True).splitlines()
        result['original_bridges_preserved'] = before == after
        (out / 'results.json').write_text(json.dumps(result, indent=2))
        assert before == after, (before, after)
        print(case, result['status'], str(out), flush=True)
    return result


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--case', choices=['A', 'B', 'C', 'all'], default='all')
    parser.add_argument('--student-entry', action='store_true')
    args = parser.parse_args()
    for case in ('A', 'B', 'C') if args.case == 'all' else [args.case]:
        run(case, use_student_entry=args.student_entry)
