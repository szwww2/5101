"""Reconstruct policy evidence from saved logs; never runs a network.

All port rates are peer-ingress RX rates, not application payload rates.
Task 2 uses the explicitly requested 5 November capture; Task 3 is historical.
Integrated trials retain analyze_task5's documented time origins.
"""
from pathlib import Path
import argparse
import csv
import gzip
import hashlib
import json
import re
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
from analyze_task5 import load_trial

ROOT = Path(__file__).resolve().parent
BLUE, RED, GREEN, PURPLE, GOLD = '#2457A7', '#BF3B43', '#087F73', '#7652A5', '#BF811C'
SOURCES = {}


def read_bytes(rel):
    p = ROOT / rel
    if not p.exists():
        p = Path(str(p) + '.gz')
    raw = p.read_bytes()
    data = gzip.decompress(raw) if p.suffix == '.gz' else raw
    SOURCES[str(p.relative_to(ROOT))] = {
        'file_sha256': hashlib.sha256(raw).hexdigest(),
        'uncompressed_sha256': hashlib.sha256(data).hexdigest()}
    return data


def records(rel):
    return [json.loads(s) for s in read_bytes(rel).decode('utf-8').splitlines() if s.strip()]


def write_csv(out, name, rows):
    with (out / name).open('w', newline='', encoding='utf-8-sig') as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


def selected_links(rel, origin, lower, upper):
    raw = records(rel)
    rows = []
    for s in raw:
        t = s['time'] - origin
        if not (lower <= t <= upper and s['ready']):
            continue
        assert len(s['links']) == 22
        for edge, v in s['links'].items():
            assert v['measured'], (rel, t, edge)
            assert abs(v['cost'] - v['base'] - v['load_term'] - v['penalty']) < 1e-8
            assert abs(v['load_term'] - 5 * min(max(v['received_bps'] / 40000000, 0), 1)) < 1e-8
        rows.append(dict(s, seconds=t))
    assert len(rows) > 20
    assert all(b['seconds'] > a['seconds'] for a, b in zip(rows, rows[1:]))
    return rows


def save_links(out, name, rows):
    flat = []
    for s in rows:
        for edge in sorted(s['links']):
            v = s['links'][edge]
            flat.append(dict(seconds=s['seconds'], unix_time=s['time'], edge=edge,
                rx_mbps=v['received_bps']/1e6, base=v['base'], utilization=v['utilization'],
                load_term=v['load_term'], penalty=v['penalty'], cost=v['cost'],
                normalized_cost=v['cost']/v['base'], measured=v['measured']))
    write_csv(out, name, flat)


def style_axes(axes, limits):
    for ax in np.array(axes).ravel():
        ax.set_xlim(*limits)
        ax.grid(alpha=.18)
        ax.set_axisbelow(True)


def save_figure(fig, out, name, foot):
    fig.text(.5, .012, foot, ha='center', va='bottom', fontsize=8.5)
    fig.tight_layout(rect=(0, .06, 1, 1), h_pad=1.3)
    fig.savefig(out / (name+'.png'), dpi=200)
    fig.savefig(out / (name+'.svg'))
    plt.close(fig)


def gap_plot(ax, rows, field, origin, **kw):
    """Do not interpolate a missing first drop-counter sample after installation."""
    xs, ys = [], []
    for r in rows:
        t = r['time']-origin
        if xs and t-xs[-1] > 1.7:
            xs.append((t+xs[-1])/2)
            ys.append(float('nan'))
        xs.append(t)
        ys.append(r[field])
    ax.plot(xs, ys, marker='.', markersize=4, lw=1.4, **kw)


def rate_line(ax, rows, edge, label, color, marker=None, ls='-'):
    ax.plot([s['seconds'] for s in rows], [s['links'][edge]['received_bps']/1e6 for s in rows],
            label=label, color=color, lw=1.5, marker=marker, markersize=3, markevery=3, ls=ls)


def integrated_marks(axes, t):
    for ax in np.array(axes).ravel():
        ax.axvspan(t['scheduled_attack_on'], t['scheduled_attack_off'], color=GOLD, alpha=.10)
        ax.axvline(t['metrics']['block_seconds'], color=RED, ls=':', lw=1)
        ax.axvline(t['metrics']['penalty_restored_seconds'], color=GREEN, ls='--', lw=1)
        for e in t['events']:
            if e['event'] == 'route_committed':
                ax.axvline(e['seconds'], color=PURPLE, ls='-.', lw=.9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--output', type=Path, default=ROOT/'todo06/policy-evidence-20261105')
    out = ap.parse_args().output
    out.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({'font.size': 11, 'axes.spines.top': False, 'axes.spines.right': False,
                         'axes.titlesize': 12, 'savefig.facecolor': 'white'})
    summary = {'scope': 'Offline analysis: Task 2 uses the requested 2026-11-05 repeat; other trials remain historical', 'standalone': {}}

    # Task 2: separate forwarding and dropping for h2, and independently inspect h1.
    ev = records('todo03/evidence/controller-events-after-block-20261016.jsonl')
    block = next(e for e in ev if e['event'] == 'block')
    origin = block['time']
    source_history = records('todo03/evidence/source-rates-after-block-20261016.jsonl')
    src = [r for r in source_history
           if -6 <= r['time']-origin <= 18 and r['source'] in ('10.0.0.1','10.0.0.2')]
    write_csv(out, 'task2-sources.csv', [dict(seconds=r['time']-origin, **r) for r in src])
    ping = read_bytes('todo03/evidence/legitimate-h1-ping-during-anomaly-20261016.log').decode()
    replies = [dict(seconds=float(ts)-origin, sequence=int(seq), rtt_ms=float(rtt))
               for ts, seq, rtt in re.findall(r'\[([0-9.]+)\].*icmp_seq=(\d+).*time=([0-9.]+) ms', ping)
               if -6 <= float(ts)-origin <= 18]
    write_csv(out, 'task2-h1-replies.csv', replies)
    h2 = [r for r in src if r['source'] == '10.0.0.2']
    h1 = [r for r in src if r['source'] == '10.0.0.1']
    assert all(r['drop_pps'] == 0 and not r['blocked'] for r in h1)
    assert all(r['forward_pps'] == 0 for r in h2 if 2 <= r['time']-origin <= 8)
    normal_active = [r for r in source_history if r['source']=='10.0.0.2'
                     and not r['blocked'] and .1<r['pps']<20]
    normal_origin = normal_active[0]['time']
    normal_end = normal_active[-1]['time']
    normal = [r for r in source_history if r['source']=='10.0.0.2'
              and normal_origin-2<=r['time']<=normal_end]
    assert len(normal_active)==10 and all(not r['blocked'] for r in normal)
    for r in normal:
        assert abs(r['new_ema_pps']-(.3*r['pps']+.7*r['old_ema_pps']))<1e-8
    write_csv(out,'task2-normal-baseline.csv',[dict(seconds=r['time']-normal_origin,**r) for r in normal])
    fig = plt.figure(figsize=(11,8.5))
    grid = fig.add_gridspec(3,2,height_ratios=[1,1.05,1])
    a=fig.add_subplot(grid[0,0]);b=fig.add_subplot(grid[0,1])
    c=fig.add_subplot(grid[1,:]);d=fig.add_subplot(grid[2,0]);e=fig.add_subplot(grid[2,1])
    fig.suptitle('Task 2 | learn the baseline, detect h2, block h2, preserve h1',fontsize=14,y=.994)
    gap_plot(a,normal,'pps',normal_origin,label='h2 normal ping rate',color=BLUE)
    gap_plot(a,normal,'new_ema_pps',normal_origin,label='Updated EMA',color=GREEN)
    a.set_title('A  Normal baseline (earlier window)',loc='left')
    a.set_ylabel('Packets/s');a.set_xlabel('Seconds from first active normal sample')
    a.set_ylim(-.1,2.8);a.set_xlim(-2,10.5);a.legend(loc='upper left',fontsize=9,ncol=2)
    gap_plot(b,h2,'forward_pps',origin,label='h2 forwarded',color=RED)
    gap_plot(b,h2,'threshold_pps',origin,label='Threshold: 2,000 pps',color=GOLD,ls='--')
    b.set_title('B  Detection detail',loc='left');b.set_ylabel('Packets/s')
    b.set_xlim(-2,3.5);b.set_ylim(-500,17500)
    b.set_xlabel('Seconds relative to block event')
    b.legend(loc='upper right',fontsize=9)
    b.text(-1.85,14000,'13,339.8 pps\n> 2,000 pps',fontsize=9,color=RED)
    # Peak label is text only; do not imply an unrecorded packet timestamp.
    for field,label,color in [('forward_pps','h2 forwarded by s2',RED),
                              ('drop_pps','h2 discarded by s2',BLUE)]:
        gap_plot(c,h2,field,origin,label=label,color=color)
    c.set_title('C  Enforcement: forwarding stops; ingress drops continue',loc='left')
    c.set_ylabel('Packets/s');c.set_xlim(-6,18);c.set_ylim(-3000,112000)
    c.set_xlabel('Seconds relative to block event');c.legend(loc='upper right',fontsize=9,ncol=2)
    first_drop=next(r['time']-origin for r in h2 if r['drop_pps']>0)
    c.text(8.6,53000,'After counter sampling resumes:\nh2 forwarding = 0',fontsize=10,color=RED)
    for axis in [b,c]:
        axis.axvspan(0,first_drop,color='#777777',alpha=.10)
    c.text(.2,106000,'New drop-counter\nsampling gap',fontsize=9,color='#555555',ha='left',va='top')
    for field, label, color in [('forward_pps','h1 forwarded',GREEN),('drop_pps','h1 dropped',RED)]:
        gap_plot(d,h1,field,origin,label=label,color=color)
    d.set_title('D  Legitimate h1 remains unblocked',loc='left')
    d.set_ylabel('Packets/s');d.set_xlim(-6,18);d.set_ylim(-.15,3.9)
    d.legend(loc='upper right',fontsize=9,ncol=2);d.set_xlabel('Seconds relative to block event')
    e.scatter([r['seconds'] for r in replies],[r['rtt_ms'] for r in replies],s=14,color=GREEN)
    e.set_title('E  h1 still receives replies from h6',loc='left')
    e.set_ylabel('Received ping RTT (ms)');e.set_xlim(-6,18);e.set_ylim(0,200)
    e.set_xlabel('Seconds relative to block event')
    for axis in [b,c,d,e]:axis.axvline(0,color=RED,ls=':',lw=1)
    for axis in [a,b,c,d,e]:axis.grid(alpha=.18);axis.set_axisbelow(True)
    fig.text(.5,.013,
        'A is a separate earlier window (~6 min before block); B is a close-up. B-E: red dotted line = recorded block event.\n'
        'Gray band: no valid h2 rate after the new counter is installed; not a measured blocking delay. Full h1 ping log: 292/293 replies.',
        ha='center',va='bottom',fontsize=8.5)
    fig.tight_layout(rect=(0,.065,1,.975),h_pad=1.55,w_pad=2)
    fig.savefig(out/'task2-selective-blocking.png',dpi=220)
    fig.savefig(out/'task2-selective-blocking.svg')
    plt.close(fig)
    summary['standalone']['task2'] = dict(origin=origin, origin_kind='recorded block event',
        displayed_seconds=[-6,18], h2_detected_pps=block['pps'], h1_drop_pps_max=max(r['drop_pps'] for r in h1),
        normal_window_origin=normal_origin,normal_window_end=normal_end,
        normal_window_offset_from_block=normal_origin-origin,
        baseline_end_ema=normal_active[-1]['new_ema_pps'],first_valid_drop_rate_seconds=first_drop,
        figure_revision='Five panels: earlier normal EMA, detection detail, source filtering, h1 forwarding and replies')

    # Keep the old export for audit, but replace the report figure with a complete
    # independently sampled repeat. Never splice old and new measurements.
    from plot_task2_recapture import plot as plot_task2
    read_bytes('plot_task2_recapture.py')
    summary['standalone']['task2_historical']=summary['standalone']['task2']
    summary['standalone']['task2']=plot_task2(ROOT,out,read_bytes)

    # Task 3: no rerouting in this standalone controller; establish that explicitly.
    ev3 = records('todo04/evidence/controller-events-after-anomaly-20261016.jsonl')
    origin3 = next(e['time'] for e in ev3 if e['event']=='block')
    restored3 = next(e['time']-origin3 for e in ev3 if e['event']=='penalty_restored')
    l3 = selected_links('todo04/evidence/link-cost-history-after-anomaly-20261016.jsonl',origin3,-12,35)
    save_links(out, 'task3-all-directed-links.csv', l3)
    fig, ax = plt.subplots(3,1,figsize=(10,7.2),sharex=True)
    rate_line(ax[0],l3,'1>2','s1 -> s2 (shared approach)',BLUE)
    rate_line(ax[0],l3,'2>6','s2 -> s6 (original branch)',RED,marker='o',ls='--')
    ax[0].set_title('Task 3 alone | costs change; installed routes remain static')
    ax[0].set_ylabel('RX rate (Mbps)'); ax[0].legend(fontsize=9,loc='upper right')
    rate_line(ax[1],l3,'2>3','s2 -> s3 (alternative)',GREEN)
    rate_line(ax[1],l3,'3>6','s3 -> s6 (alternative)',PURPLE,marker='o',ls='--')
    ax[1].set_ylim(-.2,12);ax[1].set_ylabel('RX rate (Mbps)');ax[1].legend(fontsize=9,loc='upper right')
    x=[s['seconds'] for s in l3]; target=[s['links']['2>6'] for s in l3]
    ax[2].stackplot(x, [v['base'] for v in target],[v['load_term'] for v in target],
        [v['penalty'] for v in target], labels=['Base 14','Load term 5U','Anomaly term 60A'],
        colors=['#BBCBDD',GREEN,'#E8AFB3'],step='post',alpha=.9)
    ax[2].set_ylabel('s2 -> s6 cost');ax[2].legend(fontsize=9,loc='upper right',ncol=3)
    ax[2].set_xlabel('Seconds relative to the recorded h2 block event')
    for a in ax:
        a.axvline(0,color=RED,ls=':',lw=1);a.axvline(restored3,color=GREEN,ls='--',lw=1)
    style_axes(ax,(-12,35))
    save_figure(fig,out,'task3-cost-without-rerouting',
        'Red dotted: block; green dashed: penalty cleared. Alternative links stay near zero.\n'
        'Port RX includes non-payload bytes and control traffic; it is not iperf payload throughput.')
    summary['standalone']['task3'] = dict(origin=origin3, origin_kind='recorded block event',
        displayed_seconds=[-12,35], restored_seconds=restored3, rerouting=False)

    # Integrated trials: all 22 directed links, all five measured runs.
    trials={}
    configs=[('A','A',None),('B1','B',None),('B2','B','run-B-20261017-105957-DfB6RZ'),
             ('B3','B','run-B-20261017-111734-b9lfbt'),('C','C',None)]
    phase_rows=[]
    for name,case,folder in configs:
        t=load_trial(case,root=ROOT,folder_override=folder)
        run=Path(t['run']);rel=str(run.relative_to(ROOT)).replace('\\','/')
        for srcpath,digest in t['provenance'].items():
            read_bytes(srcpath)
            assert SOURCES[srcpath]['uncompressed_sha256']==digest
        links=selected_links(rel+'/link-costs.jsonl',t['origin'],0,60)
        save_links(out,name+'-all-directed-links.csv',links)
        write_csv(out,name+'-actual-path.csv',[dict(seconds=p['seconds'],path='>'.join(map(str,p['path'])),
                  original_cost=p['original_cost'],alternative_cost=p['alternative_cost']) for p in t['paths']])
        srcs=[r for r in records(rel+'/source-rates.jsonl') if 0<=r['time']-t['origin']<=60
              and r['source'] in ('10.0.0.1','10.0.0.2','10.0.0.5')]
        write_csv(out,name+'-sources.csv',[dict(seconds=r['time']-t['origin'],**r) for r in srcs])
        assert all(not r['blocked'] and r['drop_pps']==0 for r in srcs if r['source']=='10.0.0.1')
        trials[name]=dict(trial=t,links=links)
        for phase,lo,hi in [('before',4,10),('during',15,24),('after',40,55)]:
            w=[s for s in links if lo<=s['seconds']<hi]
            for edge in sorted(links[0]['links']):
                phase_rows.append(dict(trial=name,phase=phase,start=lo,end=hi,edge=edge,samples=len(w),
                    mean_rx_mbps=statistics.mean(s['links'][edge]['received_bps']/1e6 for s in w),
                    mean_cost=statistics.mean(s['links'][edge]['cost'] for s in w)))
    write_csv(out,'all-trials-phase-means.csv',phase_rows)
    summary['trials']={name:dict(run=Path(d['trial']['run']).name, origin=d['trial']['origin'],
        clock_quality=d['trial']['clock_quality'], snapshots=len(d['links']), events=d['trial']['events'],
        initial_path=d['trial']['metrics']['initial_path'], during_path=d['trial']['metrics']['during_path'],
        recovered_path=d['trial']['metrics']['recovered_path']) for name,d in trials.items()}
    # Keep the original 15-24 s window, including B2's nonzero transition sample.
    # Validate sustained transfer separately at 18-24 s, without replacing those data.
    for row in phase_rows:
        if row['edge'] in ('1>2','2>6','2>3','3>6'):
            rerouted=row['trial'].startswith('B') and row['phase']=='during'
            active=row['edge']=='1>2' or (row['edge']=='2>6' and not rerouted) or (row['edge'] in ('2>3','3>6') and rerouted)
            if active:
                assert 9<row['mean_rx_mbps']<12, row
            elif row['trial']=='B2' and row['phase']=='during' and row['edge']=='2>6':
                pass
            else:
                assert row['mean_rx_mbps']<.01, row
    for name in ['B1','B2','B3']:
        late=[s for s in trials[name]['links'] if 18<=s['seconds']<24]
        assert all(s['links']['2>6']['received_bps']/1e6<.01 for s in late)
        assert all(9<s['links'][e]['received_bps']/1e6<12 for s in late for e in ['2>3','3>6'])

    b=trials['B1'];t=b['trial'];links=b['links']
    fig,ax=plt.subplots(4,1,figsize=(10,8.6),sharex=True)
    rate_line(ax[0],links,'1>2','s1 -> s2 (shared approach)',BLUE)
    ax[0].plot([r['midpoint'] for r in t['receiver']],[r['mbps'] for r in t['receiver']],
               color='black',ls='--',lw=1,label='h6 received h1 UDP payload')
    ax[0].set_title('Integrated case B, trial 1 | measured transfer to the alternative branch')
    rate_line(ax[1],links,'2>6','s2 -> s6 (original branch)',RED)
    rate_line(ax[2],links,'2>3','s2 -> s3 (alternative, first hop)',GREEN)
    rate_line(ax[2],links,'3>6','s3 -> s6 (alternative, second hop)',PURPLE,marker='o',ls='--')
    for a in ax[:3]:a.set_ylabel('Rate (Mbps)');a.set_ylim(-.5, max(12, a.get_ylim()[1]));a.legend(fontsize=9,loc='upper right')
    for route,label,color in [([1,2,6],'Cost of s1 -> s2 -> s6',RED),([1,2,3,6],'Cost of s1 -> s2 -> s3 -> s6',GREEN)]:
        ax[3].step([s['seconds'] for s in links],
            [sum(s['links'][str(a)+'>'+str(c)]['cost'] for a,c in zip(route,route[1:])) for s in links],
            where='post',label=label,color=color,lw=1.5)
    ax[3].set_ylabel('Whole-path cost');ax[3].legend(fontsize=9,loc='upper right')
    ax[3].set_xlabel('Seconds from legitimate-flow start (B1 origin estimated)')
    style_axes(ax,(0,60));integrated_marks(ax,t)
    save_figure(fig,out,'B1-branch-transfer-and-cost',
        'Shading: planned flood; red dotted: block; green dashed: penalty cleared; purple: route commit.\n'
        'About 1-second alignment; port RX and receiver payload measure different byte scopes.')

    # All directions prevent a selected-link-only view; linear scale preserves relative loads.
    edges=sorted(links[0]['links'],key=lambda s:tuple(map(int,s.split('>'))))
    x=np.array([s['seconds'] for s in links]);xb=np.r_[0,(x[1:]+x[:-1])/2,60]
    data=np.array([[s['links'][e]['received_bps']/1e6 for s in links] for e in edges])
    fig,ax=plt.subplots(figsize=(10,7.2))
    mesh=ax.pcolormesh(xb,np.arange(len(edges)+1),data,cmap='YlGnBu',vmin=0,
                       vmax=np.ceil(data.max()/5)*5,shading='flat',rasterized=True)
    ax.set_yticks(np.arange(len(edges))+.5,[e.replace('>',' -> s').join(['s','']) for e in edges])
    ax.invert_yaxis();ax.set_ylim(22,0);ax.set_xlim(0,60)
    ax.set_title('Integrated case B, trial 1 | every directed switch-to-switch link')
    ax.set_xlabel('Seconds from legitimate-flow start (B1 origin estimated)')
    ax.set_ylabel('Directed link; reverse directions are separate rows')
    for e in t['events']:
        if e['event']=='route_committed':ax.axvline(e['seconds'],color=PURPLE,lw=1.2,ls='-.')
    fig.colorbar(mesh,ax=ax,pad=.025,label='Port RX rate (Mbps)')
    save_figure(fig,out,'B1-all-links-heatmap',
        'Snapshot cells, no smoothing. Purple lines mark route commits.\n'
        'Aggregated port traffic includes control packets and replies; it is not source-specific.')

    fig,ax=plt.subplots(2,2,figsize=(10.5,7),sharex=True)
    for col,name in enumerate(['A','C']):
        t=trials[name]['trial'];links=trials[name]['links'];target=t['target_edge']
        rate_line(ax[0,col],links,'1>2','s1 -> s2',BLUE)
        rate_line(ax[0,col],links,'2>6','s2 -> s6',RED,marker='o',ls='--')
        ax[0,col].plot([r['midpoint'] for r in t['receiver']],[r['mbps'] for r in t['receiver']],
                       color='black',ls=':',lw=1,label='h6 received h1 UDP')
        ax[0,col].set_title('Case '+name+' | original legitimate branch remains active')
        ax[0,col].set_ylim(-.4,12);ax[0,col].legend(fontsize=8.5,loc='lower right')
        rate_line(ax[1,col],links,target,'Affected '+target.replace('>',' -> s').join(['s','']),GREEN)
        rate_line(ax[1,col],links,'3>6','s3 -> s6 (other branch)',PURPLE,marker='o',ls='--')
        ax[1,col].set_ylim(-.4,12);ax[1,col].legend(fontsize=8.5,loc='upper right')
        ax[1,col].set_xlabel('Time from legitimate-flow start (s)')
        for a in ax[:,col]:a.set_ylabel('Rate (Mbps)')
        integrated_marks(ax[:,col],t)
    style_axes(ax,(0,60))
    save_figure(fig,out,'AC-unaffected-legitimate-path',
        'Shading: planned flood; red dotted: block; green dashed: penalty cleared.\n'
        'C pins only the h5 -> h6 test pair to s5 -> s6. No legitimate reroute occurs in A or C.')

    fig,ax=plt.subplots(3,2,figsize=(10.5,8),sharex=True,sharey=True)
    for row,name in enumerate(['B1','B2','B3']):
        t=trials[name]['trial'];links=trials[name]['links']
        rate_line(ax[row,0],links,'2>6','s2 -> s6',RED)
        rate_line(ax[row,1],links,'2>3','s2 -> s3',GREEN)
        rate_line(ax[row,1],links,'3>6','s3 -> s6',PURPLE,marker='o',ls='--')
        ax[row,0].set_title(name+' | original branch')
        ax[row,1].set_title(name+' | alternative branch')
        for a in ax[row]:
            a.set_ylabel('Port RX (Mbps)');a.set_ylim(-1,34);a.legend(fontsize=9,loc='upper right')
        integrated_marks(ax[row],t)
    for a in ax[-1]:a.set_xlabel('Time from legitimate-flow start (s)')
    style_axes(ax,(0,60))
    save_figure(fig,out,'B-all-repeats-branch-transfer',
        'All three B trials, including onset transitions. B1 time origin estimated.\n'
        'B2 still records 4.726 Mbps on s2 -> s6 at 15.60 s; this sample is retained.')

    summary['limitations']=[
        'Historical Task2 lacks port statistics. Its replacement figure uses a separate 5 November repeat with complete source flow counters at every switch, not per-port Mbps.',
        'Port RX contains multiple sources/protocols and Ethernet/VLAN overhead; do not call it UDP payload throughput.',
        'Step/event times reflect about one-second sampling; B1 origin is estimated. No sub-second causality claim.',
        'B2 retains 4.726 Mbps on the original branch at 15.60 s; its 15-24 s original-branch mean is 0.525 Mbps, not zero.',
        'Low link RX after blocking does not clear the anomaly flag while ingress drops continue.',
        'Task3 alone retains static routes; only the integrated Task4 controller moves legitimate traffic.',
        'No controlled comparison estimates the independent throughput gain of rerouting or proves optimal parameters.']
    summary['source_provenance']=SOURCES
    summary['analysis_script_sha256']=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    summary['checks']={'all_22_directions_present':True,'cost_formula_matches_logged_values':True,
        'h1_not_blocked':True,'all_B_repeats_transfer_and_recover':True,'A_C_retain_original_branch':True}
    (out/'POLICY_EVIDENCE.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'output':str(out),'figures':6,'source_files':len(SOURCES),'checks':summary['checks']},indent=2))


if __name__=='__main__':
    main()
