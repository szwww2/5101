"""Plot the user-requested Task 2 repeat; no network operations."""
import csv
import json
import re
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

RUN='todo03/task2-recapture-20261105'
BLUE,RED,GREEN,PURPLE,GOLD='#2457A7','#BF3B43','#087F73','#7652A5','#BF811C'


def plot(root,out,read_bytes):
    def load(name):return json.loads(read_bytes(RUN+'/'+name))
    def lines(name):return [json.loads(x) for x in read_bytes(RUN+'/'+name).decode().splitlines()]
    def csvfile(name,rows):
        with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
            w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
    result=load('capture-results.json');assert result['status']=='PASS'
    origin=result['origin'];block=result['block_event'];bt=block['time']-origin
    start=result['flood_start']-origin;end=result['flood_observed_stop']-origin
    snapshots=lines('flow-snapshots.jsonl');controller=lines('source-rates.jsonl')
    read_bytes(RUN+'/events.jsonl')
    for name in ['anomaly_controller.py','traffic_stats.py','baseline_controller.py',
                 'capture_task2.py','todo01/ca2-mesh-my.mn']:
        import hashlib
        assert hashlib.sha256(read_bytes(name)).hexdigest()==result['code_sha256'][name]
    allrates=[];previous={};max_interval=0
    for record in snapshots:
        assert len(record['switches'])==6
        for s in record['switches']:
            assert s['end']>=s['start']
            for source,t in s['sources'].items():
                key=(s['switch'],source)
                if key in previous:
                    oldtime,old=previous[key];dt=s['time']-oldtime
                    assert dt>0
                    max_interval=max(max_interval,dt)
                    forward=t['forward_packets']-old['forward_packets']
                    dropped=t['drop_packets']-old['drop_packets']
                    assert forward>=0 and dropped>=0, 'Counter reset: do not interpolate'
                    allrates.append(dict(switch=s['switch'],source=source,
                        seconds=s['time']-origin,interval_start=oldtime-origin,interval_seconds=dt,
                        forward_pps=forward/dt,drop_pps=dropped/dt,**t))
                previous[key]=(s['time'],t)
    assert max_interval<1, max_interval
    csvfile('task2-recapture-all-switch-counters.csv',allrates)
    rates=lambda switch,source:[r for r in allrates if r['switch']==switch and r['source']==source]
    h2=rates(2,'10.0.0.2');h1=rates(1,'10.0.0.1')
    assert all(r['drop_packets']==0 for r in allrates if r['source']=='10.0.0.1')
    assert max(r['drop_pps'] for r in h2)>2000
    assert all(r['forward_pps']==0 for r in h2 if r['interval_start']>bt+1)
    assert all(r['forward_pps']==0 for r in rates(6,'10.0.0.2') if r['interval_start']>bt+1)
    normal=[r for r in controller if r['source']=='10.0.0.2' and origin<=r['time']<result['flood_start']]
    detected=[r for r in controller if r['source']=='10.0.0.2' and origin<=r['time']<=block['time']]
    for r in normal:assert abs(r['new_ema_pps']-(.3*r['pps']+.7*r['old_ema_pps']))<1e-8
    ping=read_bytes(RUN+'/h1-continuous-ping.log').decode()
    replies=[dict(seconds=float(ts)-origin,sequence=int(seq),rtt_ms=float(rtt))
        for ts,seq,rtt in re.findall(r'\[([\d.]+)\].*icmp_seq=(\d+).*time=([\d.]+) ms',ping)]
    sent,received=map(int,re.search(r'(\d+) packets transmitted, (\d+) received',ping).groups())
    assert len(replies)==received
    csvfile('task2-recapture-h1-replies.csv',replies)
    csvfile('task2-recapture-normal-ema.csv',[dict(seconds=r['time']-origin,**r) for r in normal])
    for name in ['h1-post-ping.log','h2-post-ping.log','h2-continuous-ping.log','h2-flood.log','mesh.mn']:
        read_bytes(RUN+'/'+name)
    fig=plt.figure(figsize=(11,8.5));grid=fig.add_gridspec(3,2,height_ratios=[1,1.1,1])
    a=fig.add_subplot(grid[0,0]);b=fig.add_subplot(grid[0,1]);c=fig.add_subplot(grid[1,:])
    d=fig.add_subplot(grid[2,0]);e=fig.add_subplot(grid[2,1])
    fig.suptitle('Task 2 | continuous capture of detection and selective blocking',fontsize=14,y=.994)
    x=[r['time']-origin for r in normal]
    a.plot(x,[r['pps'] for r in normal],'.-',color=BLUE,label='h2 normal ping rate')
    a.plot(x,[r['new_ema_pps'] for r in normal],'.-',color=GREEN,label='Updated EMA')
    a.set_title('A  Normal traffic learns the EMA',loc='left');a.set_ylim(-.1,3.4)
    a.set_ylabel('Packets/s');a.set_xlim(0,12);a.legend(fontsize=9,loc='upper left',ncol=2)
    dx=[r['time']-origin for r in detected]
    b.plot(dx,[r['pps'] for r in detected],'o',markersize=4,color=RED,label='Controller source samples')
    b.axhline(block['threshold_pps'],color=GOLD,ls='--',label='Threshold: 2,000 pps')
    b.text(.03,.58,f"Detected: {block['pps']:,.1f} pps",transform=b.transAxes,color=RED,fontsize=9)
    b.set_xlim(start-1.5,bt+.5);b.set_ylim(-500,block['pps']*1.5)
    b.axvline(bt,color=RED,ls=':',lw=1);b.set_title('B  Detection at the controller',loc='left')
    b.set_ylabel('Packets/s');b.legend(fontsize=9,loc='upper left')
    def curve(ax,rows,field,label,color,ls='-'):
        # Each step value is the measured delta over [previous, current].
        ax.step([r['seconds'] for r in rows],[r[field] for r in rows],where='pre' if field.endswith('pps') else 'post',
                label=label,color=color,ls=ls,lw=1.5)
    curve(c,h2,'drop_pps','h2 dropped at s2',BLUE)
    curve(c,h2,'forward_pps','h2 forwarded at s2',RED)
    curve(c,rates(6,'10.0.0.2'),'forward_pps','h2 forwarded to h6 at s6',PURPLE,'--')
    c.set_title('C  Continuous counters: h2 forwarding stops; ingress drops continue',loc='left')
    c.set_ylabel('Packets/s');c.legend(fontsize=9,loc='upper right',ncol=3)
    c.set_ylim(-max(r['drop_pps'] for r in h2)*.04,max(r['drop_pps'] for r in h2)*1.3)
    for switch,color,ls in [(1,GREEN,'-'),(2,BLUE,'--'),(6,PURPLE,':')]:
        curve(d,rates(switch,'10.0.0.1'),'forward_packets',f'h1 forwarded: s{switch}',color,ls)
    curve(d,h1,'drop_packets','h1 source-rule drops',RED,'--')
    d.set_title('D  h1 continues across s1, s2 and s6',loc='left');d.set_ylabel('Cumulative packets')
    d.set_ylim(-3,sent*1.35);d.legend(fontsize=8.5,loc='upper left',ncol=2)
    e.scatter([r['seconds'] for r in replies],[r['rtt_ms'] for r in replies],color=GREEN,s=12)
    e.set_title(f'E  h1 received {received}/{sent} ping replies',loc='left');e.set_ylabel('Ping RTT (ms)')
    e.set_ylim(0,200)
    for axis in (c,d,e):
        axis.set_xlim(0,32);axis.axvspan(start,end,color=GOLD,alpha=.12)
        axis.axvline(bt,color=RED,ls=':',lw=1)
    for axis in (a,b,c,d,e):
        axis.set_xlabel('Seconds from capture start');axis.grid(alpha=.18);axis.set_axisbelow(True)
    fig.text(.5,.012,
        'New experiment: 5 Nov 2026; unchanged controller. Shading = measured flood process window; dotted red = BLOCK.\n'
        'C/D: complete OVS tables sampled every ~0.5 s; absent drop rule has zero count. No interpolated or spliced samples.',
        fontsize=8.5,ha='center',va='bottom')
    fig.tight_layout(rect=(0,.065,1,.975),h_pad=1.55,w_pad=2)
    fig.savefig(out/'task2-selective-blocking.png',dpi=220)
    fig.savefig(out/'task2-selective-blocking.svg');plt.close(fig)
    info=dict(scope='New assistant-run experiment requested by user, 2026-11-05',run=RUN,
        origin=origin,block_seconds=bt,flood_start_seconds=start,flood_observed_stop_seconds=end,
        detected_pps=block['pps'],threshold_pps=block['threshold_pps'],snapshots=len(snapshots),
        max_sample_interval_seconds=max_interval,all_switch_rate_rows=len(allrates),
        h1_ping_sent=sent,h1_ping_received=received,h1_drop_packets=0,
        h1_post_ping=result['h1_post_ping'],h2_post_ping=result['h2_post_ping'],
        normal_end_ema=normal[-1]['new_ema_pps'],
        h2_forwarding_zero_after_block_plus_one_second=True,
        all_switch_drop_rules=True,original_bridges_preserved=result['original_bridges_preserved'],
        rate_method='Aggregate monotonic counter deltas per complete OVS table; zero when no matching drop rule exists; no interpolation')
    (out/'TASK2_RECAPTURE_VALIDATION.json').write_text(json.dumps(info,indent=2))
    return info
