"""Repeat Task 2 with continuous, independently sampled OVS counters.

Only creates q2* nodes and a controller on 127.0.0.1:16661. The existing
anomaly controller is unmodified. Every complete flow-table snapshot records
zero for an absent drop rule, allowing aggregate counter differencing across
rule creation without inventing a missing per-rule rate sample.
"""
import argparse
import hashlib
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
PORT = 16661
PREFIX = 'q2'


def command(args):
    return subprocess.check_output(args, text=True, timeout=4)


def dump(switch):
    start = time.time()
    raw = command(['ovs-ofctl', '-O', 'OpenFlow13', '--no-names',
                   'dump-flows', PREFIX+'s'+str(switch)])
    end = time.time()
    sources = {}
    for source in ('10.0.0.1', '10.0.0.2'):
        totals = dict(forward_packets=0, drop_packets=0, drop_present=False,
                      forward_rules=0)
        for row in raw.splitlines():
            if not re.search(r'nw_src='+re.escape(source)+r'(?:,|\s)', row):
                continue
            priority = int(re.search(r'priority=(\d+)', row).group(1))
            packets = int(re.search(r'n_packets=(\d+)', row).group(1))
            if priority in (100, 110) and 'actions=output:' in row:
                totals['forward_packets'] += packets
                totals['forward_rules'] += 1
            elif priority == 5000 and 'actions=drop' in row:
                totals['drop_packets'] += packets
                totals['drop_present'] = True
        sources[source] = totals
    return dict(switch=switch, start=start, end=end, time=(start+end)/2,
                raw=raw, sources=sources)


def stop(process):
    if process is not None and process.poll() is None:
        process.send_signal(signal.SIGINT)
        try:
            process.wait(timeout=4)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=3)


def run(output):
    assert os.geteuid() == 0
    setLogLevel('warning')
    output.mkdir(parents=True, exist_ok=False)
    before = command(['ovs-vsctl', 'list-br']).splitlines()
    assert not any(x.startswith(PREFIX) for x in before), before
    with socket.socket() as probe:
        probe.bind(('127.0.0.1', PORT))
    result = dict(status='RUNNING', scope='Assistant rerun explicitly requested by user',
                  sample_period_seconds=.5, flood_duration_seconds=8,
                  duration_seconds=32, controller_unchanged=True)
    app = net = controller = attack = None
    processes, handles = [], []
    def log(name):
        f=(output/name).open('w');handles.append(f);return f
    try:
        document=json.loads((ROOT/'todo01/ca2-mesh-my.mn').read_text())
        document['application']['startCLI']='0'
        for kind in ('hosts','switches','controllers'):
            for node in document[kind]:
                opts=node['opts'];opts['hostname']=PREFIX+opts['hostname']
                if 'controllers' in opts:opts['controllers']=[PREFIX+'c0']
                if 'startCommand' in opts:
                    opts['startCommand']=opts['startCommand'].replace('dev h','dev '+PREFIX+'h')
                if kind=='controllers':opts['remotePort']=PORT
        for link in document['links']:
            link['src']=PREFIX+link['src'];link['dest']=PREFIX+link['dest']
        shadow=output/'mesh.mn';shadow.write_text(json.dumps(document))
        env=dict(os.environ,CEG_BASELINE_OUTPUT=str(output),PYTHONDONTWRITEBYTECODE='1',
                 PYTHONPATH=str(ROOT)+os.pathsep+os.environ.get('PYTHONPATH',''))
        ryu=os.environ.get('CEG_RYU_MANAGER','/home/robot/miniforge3/envs/ceg5101-ryu38/bin/ryu-manager')
        controller=subprocess.Popen([ryu,'--observe-links','--ofp-listen-host','127.0.0.1',
            '--ofp-tcp-listen-port',str(PORT),str(ROOT/'anomaly_controller.py')],
            env=env,stdout=log('ryu.log'),stderr=subprocess.STDOUT)
        for _ in range(100):
            assert controller.poll() is None, 'Controller exited'
            with socket.socket() as probe:
                if probe.connect_ex(('127.0.0.1',PORT))==0:break
            time.sleep(.1)
        else:raise RuntimeError('Controller listen timeout')
        spec=importlib.util.spec_from_file_location('task2_gui',ROOT/'miniedit_compat.py')
        gui=importlib.util.module_from_spec(spec);spec.loader.exec_module(gui)
        errors=[];gui.showerror=lambda *args,**kw:errors.append(str(args))
        app=gui.MiniEdit();app.winfo_toplevel().withdraw()
        gui.tkFileDialog.askopenfile=lambda **kw:shadow.open('rb')
        app.loadTopology();assert not errors,errors
        app.start();net=app.net
        for _ in range(160):
            p=output/'state.json';state=json.loads(p.read_text()) if p.exists() else {}
            assert not state.get('failed'),state
            if state.get('ready'):break
            time.sleep(.25)
        else:raise RuntimeError('Topology ready timeout')
        assert state['directed_links']==22 and len(state['routes'])==30
        result['initial_state']=state
        origin=time.time();result['origin']=origin
        print('CAPTURE READY: normal ping 0-12 s; h2 flood 12-20 s; observe to 32 s',flush=True)
        samples=log('flow-snapshots.jsonl')
        def sample():
            row=dict(time=time.time(),switches=[dump(i) for i in range(1,7)])
            samples.write(json.dumps(row)+'\n');samples.flush()
            return row
        sample()
        for host in ('h1','h2'):
            processes.append(net[PREFIX+host].popen(['ping','-D','-i','0.5','-W','1','10.0.0.6'],
                stdout=log(host+'-continuous-ping.log'),stderr=subprocess.STDOUT))
        deadline=time.monotonic()+32;next_sample=time.monotonic()+.5
        while time.monotonic()<deadline:
            if attack is None and time.time()-origin>=12:
                observed=json.loads((output/'anomaly-state.json').read_text())
                assert not observed['blocked'] and observed['sources']['10.0.0.2']['samples']>=5,observed
                result['flood_start']=time.time()
                attack=net[PREFIX+'h2'].popen(['timeout','8s','hping3','-1','--flood','10.0.0.6'],
                    stdout=log('h2-flood.log'),stderr=subprocess.STDOUT)
                print('FLOOD STARTED',flush=True)
            if attack is not None and attack.poll() is not None and 'flood_observed_stop' not in result:
                result['flood_observed_stop']=time.time()
                print('FLOOD STOPPED; normal-source monitoring continues',flush=True)
            sample()
            time.sleep(max(0,next_sample-time.monotonic()));next_sample+=.5
        result['end']=time.time()
        for process in processes:stop(process)
        final=sample();result['final_counters']=final
        for host in ('h1','h2'):
            text=net[PREFIX+host].cmd('ping -c 3 -W 1 10.0.0.6')
            (output/(host+'-post-ping.log')).write_text(text)
            match=re.search(r'(\d+) packets transmitted, (\d+) received',text)
            assert match,text
            result[host+'_post_ping']=dict(sent=int(match[1]),received=int(match[2]))
        events=[json.loads(x) for x in (output/'events.jsonl').read_text().splitlines()]
        blocks=[e for e in events if e['event']=='block']
        assert len(blocks)==1 and blocks[0]['source']=='10.0.0.2',blocks
        assert not [e for e in events if e['event'] in ('openflow_error','barrier_timeout','stats_timeout')]
        result['block_event']=blocks[0]
        for s in final['switches']:
            assert s['sources']['10.0.0.2']['drop_present']
            assert not s['sources']['10.0.0.1']['drop_present']
        assert result['h1_post_ping']['received']==3 and result['h2_post_ping']['received']==0
        result['status']='PASS'
    except Exception as exc:
        result.update(status='FAIL',error=repr(exc))
        raise
    finally:
        stop(attack)
        for process in processes:stop(process)
        stop(controller)
        if net is None and app is not None:net=app.net
        if net is not None:net.stop()
        if app is not None:app.winfo_toplevel().destroy()
        for f in handles:f.close()
        after=command(['ovs-vsctl','list-br']).splitlines()
        result['original_bridges_preserved']=before==after
        result['code_sha256']={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest()
            for name in ['anomaly_controller.py','traffic_stats.py','baseline_controller.py',
                         'capture_task2.py','todo01/ca2-mesh-my.mn']}
        (output/'capture-results.json').write_text(json.dumps(result,indent=2))
        assert before==after,(before,after)
        print(json.dumps({k:result[k] for k in ['status','original_bridges_preserved']})+' '+str(output),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,required=True)
    run(parser.parse_args().output.resolve())
