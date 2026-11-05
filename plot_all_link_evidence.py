"""Offline all-link figures for Task 2, Task 3 and each Task 4 scenario."""
import argparse
import csv
import gzip
import hashlib
import io
import json
import math
from pathlib import Path
import re
import statistics

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D

ROOT=Path(__file__).resolve().parent
POLICY='todo06/policy-evidence-20261105'
CAPTURE='todo03/task2-link-capture-20261105'
BLUE,ORANGE,RED,GREEN,PURPLE='#2457A7','#C97921','#BF3B43','#087F73','#7652A5'
PROVENANCE={}


def read(rel):
    p=ROOT/rel
    if not p.exists():p=Path(str(p)+'.gz')
    raw=p.read_bytes();data=gzip.decompress(raw) if p.suffix=='.gz' else raw
    PROVENANCE[str(p.relative_to(ROOT))]={'file_sha256':hashlib.sha256(raw).hexdigest(),
        'uncompressed_sha256':hashlib.sha256(data).hexdigest()}
    return data


def records(rel):return [json.loads(x) for x in read(rel).decode().splitlines() if x.strip()]
def load(rel):return json.loads(read(rel))
def csv_read(rel):return list(csv.DictReader(io.StringIO(read(rel).decode('utf-8-sig'))))
def csv_write(out,name,rows):
    with (out/name).open('w',newline='',encoding='utf-8-sig') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)


def historical(name):
    rows=csv_read(POLICY+'/'+name+'-all-directed-links.csv')
    for row in rows:
        for field in ['seconds','rx_mbps','cost']:row[field]=float(row[field])
    assert len({r['edge'] for r in rows})==22
    for t in {r['seconds'] for r in rows}:
        assert sum(r['seconds']==t for r in rows)==22
    return rows


def capture(out):
    result=load(CAPTURE+'/capture-results.json');assert result['status']=='PASS'
    for name,digest in result['code_sha256'].items():
        assert hashlib.sha256(read(name)).hexdigest()==digest,name
    origin=result['origin'];block=result['block_event']['time']-origin
    mapping={(e['src'],e['dst']):e['port'] for e in result['initial_state']['links']}
    snapshots=records(CAPTURE+'/port-snapshots.jsonl')
    previous={};rates=[];hosts=[];intervals=[]
    for snapshot in snapshots:
        assert len(snapshot['switches'])==6
        for s in snapshot['switches']:
            switch=s['switch'];t=s['time'];ports=s['ports']
            needed={mapping[(switch,j)] for i,j in mapping if i==switch}|{1}
            assert needed<={int(p) for p in ports}
            if switch in previous:
                old_t,old=previous[switch];dt=t-old_t;intervals.append(dt)
                assert 0<dt<1,dt
                def rate(port,direction):
                    delta=ports[str(port)][direction+'_bytes']-old[str(port)][direction+'_bytes']
                    assert delta>=0,'Counter reset'
                    return delta*8/dt/1e6
                for (a,b),port in mapping.items():
                    if b!=switch:continue
                    peer_port=mapping[(b,a)]
                    rates.append(dict(seconds=t-origin,interval_start=old_t-origin,interval_seconds=dt,
                        edge=f'{a}>{b}',peer_ingress_port=peer_port,rx_mbps=rate(peer_port,'rx'),
                        measurement='destination switch RX bytes'))
                for direction,edge in [('rx',f'h{switch}>s{switch}'),('tx',f's{switch}>h{switch}')]:
                    hosts.append(dict(seconds=t-origin,interval_start=old_t-origin,interval_seconds=dt,
                        edge=edge,mbps=rate(1,direction),measurement='switch port '+direction.upper()+' bytes'))
            previous[switch]=(t,ports)
    assert len(rates)==(len(snapshots)-1)*22
    csv_write(out,'task2-all-directed-links.csv',rates);csv_write(out,'task2-host-attachments.csv',hosts)
    flows=records(CAPTURE+'/flow-snapshots.jsonl')
    for snapshot in flows:
        for s in snapshot['switches']:
            assert s['sources']['10.0.0.1']['drop_packets']==0
            assert not s['sources']['10.0.0.1']['drop_present']
    for sw in [2,6]:
        late=[next(s for s in row['switches'] if s['switch']==sw)['sources']['10.0.0.2']['forward_packets']
              for row in flows if row['time']-origin>block+1]
        assert len(set(late))==1, 'h2 forwarding must stop'
    assert all(s['sources']['10.0.0.2']['drop_present'] for s in flows[-1]['switches'])
    sender=read(CAPTURE+'/h1-udp-sender.log').decode()
    summary=re.findall(r'([\d.]+) Mbits/sec\s+[\d.]+ ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)',sender)
    assert summary,sender
    mbps,lost,total,percent=summary[-1]
    assert float(mbps)>9
    ping=read(CAPTURE+'/h1-continuous-ping.log').decode()
    sent,received=map(int,re.search(r'(\d+) packets transmitted, (\d+) received',ping).groups())
    for file in ['h6-udp-receiver.log','source-rates.jsonl','events.jsonl','h2-flood.log','mesh.mn']:
        read(CAPTURE+'/'+file)
    info=dict(run=CAPTURE,origin=origin,block_seconds=block,
        flood=[result['flood_start']-origin,result['flood_observed_stop']-origin],
        snapshots=len(snapshots),max_interval_seconds=max(intervals),directed_switch_links=22,
        host_attachment_directions=12,detected_pps=result['block_event']['pps'],
        udp_receiver_mbps=float(mbps),udp_lost=int(lost),udp_total=int(total),
        udp_loss_percent=100*int(lost)/int(total),ping_sent=sent,ping_received=received,
        h1_post_ping=result['h1_post_ping'],h2_post_ping=result['h2_post_ping'],
        all_switch_source_blocks=True,h1_not_blocked=True,
        original_bridges_preserved=result['original_bridges_preserved'])
    return rates,hosts,info


def plot_grid(out,name,title,rows,target,limit,block,flood=None,recovery=None,hosts=None,foot=''):
    edges=sorted({tuple(sorted(map(int,r['edge'].split('>')))) for r in rows})
    assert len(edges)==11
    top=max(12,math.ceil(max(r['rx_mbps'] for r in rows)/5)*5)
    fig,axes=plt.subplots(4,3,figsize=(11.6,9),sharex=True)
    fig.suptitle(title,fontsize=15,y=.995)
    handles=[Line2D([0],[0],color=BLUE,lw=2,label='Lower ID -> higher ID'),
             Line2D([0],[0],color=ORANGE,ls='--',lw=2,label='Higher ID -> lower ID'),
             Line2D([0],[0],color=RED,ls=':',label='Source blocked')]
    if recovery is not None:handles.append(Line2D([0],[0],color=GREEN,ls='--',label='Penalty cleared'))
    fig.legend(handles=handles,loc='upper center',bbox_to_anchor=(.5,.963),ncol=len(handles),fontsize=10)
    for ax,(a,b) in zip(axes.flat,edges):
        for edge,color,ls in [(f'{a}>{b}',BLUE,'-'),(f'{b}>{a}',ORANGE,'--')]:
            values=[r for r in rows if r['edge']==edge]
            x=[r['seconds'] for r in values];y=[r['rx_mbps'] for r in values]
            if 'interval_start' in values[0]:ax.step(x,y,where='pre',color=color,ls=ls,lw=1.5)
            else:ax.plot(x,y,color=color,ls=ls,lw=1.5)
        suffix=' [affected]' if (a,b)==target else ' [h1 base path]' if (a,b) in [(1,2),(2,6)] else ''
        ax.set_title(f's{a} -- s{b}'+suffix,fontsize=10.5,loc='left')
        ax.set_ylim(-top*.035,top*1.05);ax.set_ylabel('RX Mbps',fontsize=9)
        if (a,b)==target:ax.set_facecolor('#FFF4F3')
        elif (a,b) in [(1,2),(2,6)]:ax.set_facecolor('#F0F7F5')
    last=axes.flat[-1]
    if hosts is not None:
        for edge,label,color in [('h2>s2','h2 -> s2 ingress',RED),('h1>s1','h1 -> s1 ingress',GREEN)]:
            values=[r for r in hosts if r['edge']==edge]
            last.step([r['seconds'] for r in values],[r['mbps'] for r in values],where='pre',label=label,color=color,lw=1.5)
        last.set_title('Host ingress before source filtering',fontsize=10.5,loc='left')
        last.set_ylabel('RX Mbps',fontsize=9);last.legend(fontsize=8,loc='upper right')
    else:
        values=[r for r in rows if r['edge']==f'{target[0]}>{target[1]}']
        last.plot([r['seconds'] for r in values],[r['cost'] for r in values],color=PURPLE,lw=1.6)
        last.set_title(f'Affected direction s{target[0]} -> s{target[1]} cost',fontsize=10.5,loc='left')
        last.set_ylabel('Routing cost',fontsize=9)
    for ax in axes.flat:
        ax.set_xlim(*limit);ax.tick_params(labelsize=9);ax.grid(alpha=.2);ax.set_axisbelow(True)
        ax.axvline(block,color=RED,ls=':',lw=.9)
        if flood:ax.axvspan(*flood,color=ORANGE,alpha=.09)
        if recovery is not None:ax.axvline(recovery,color=GREEN,ls='--',lw=.9)
    for ax in axes[-1]:ax.set_xlabel('Seconds from capture start' if hosts else 'Seconds relative to BLOCK' if name.startswith('task3') else 'Seconds from experiment start',fontsize=9)
    fig.text(.5,.012,foot,ha='center',va='bottom',fontsize=9)
    fig.tight_layout(rect=(0,.065,1,.93),h_pad=1.2,w_pad=1.4)
    fig.savefig(out/(name+'.png'),dpi=220);fig.savefig(out/(name+'.svg'));plt.close(fig)


def plot_hosts(out,hosts,info):
    fig,axes=plt.subplots(3,2,figsize=(10.5,7),sharex=True)
    fig.suptitle('Task 2 | all six host attachments, measured at switch ports',fontsize=14,y=.995)
    for i,ax in enumerate(axes.flat,1):
        for edge,label,color,ls in [(f'h{i}>s{i}','Host -> switch (RX)',BLUE,'-'),(f's{i}>h{i}','Switch -> host (TX)',ORANGE,'--')]:
            values=[r for r in hosts if r['edge']==edge]
            ax.step([r['seconds'] for r in values],[r['mbps'] for r in values],where='pre',label=label,color=color,ls=ls,lw=1.4)
        ax.set_title(f'h{i} -- s{i}',loc='left');ax.set_ylabel('Mbps');ax.set_ylim(-1,40)
        ax.set_xlim(0,32);ax.axvspan(*info['flood'],color=ORANGE,alpha=.1)
        ax.axvline(info['block_seconds'],color=RED,ls=':',lw=1);ax.grid(alpha=.2)
    axes[0,0].legend(fontsize=9,loc='upper left')
    for ax in axes[-1]:ax.set_xlabel('Seconds from capture start')
    fig.text(.5,.012,'h2 ingress continues while its source is blocked; h1 -> s1 and s6 -> h6 keep carrying legitimate traffic.\n'
        'RX/TX are switch-port byte counters, not application payload; TX is not a host-reception guarantee.',ha='center',fontsize=9)
    fig.tight_layout(rect=(0,.075,1,.97),h_pad=1.1)
    fig.savefig(out/'task2-host-attachments.png',dpi=220);fig.savefig(out/'task2-host-attachments.svg');plt.close(fig)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('--output',type=Path,default=ROOT/'todo06/all-link-evidence-20261105')
    out=parser.parse_args().output;out.mkdir(parents=True,exist_ok=True)
    plt.rcParams.update({'font.size':10,'axes.spines.top':False,'axes.spines.right':False})
    policy=load(POLICY+'/POLICY_EVIDENCE.json')
    # Verify the source chain behind existing derived CSVs without changing them.
    for rel,expected in policy['source_provenance'].items():
        payload=read(rel)
        assert hashlib.sha256(payload).hexdigest()==expected['uncompressed_sha256'],rel
    t2,hosts,info=capture(out)
    plot_grid(out,'task2-all-links','Task 2 | all 11 switch links, both directions',t2,(2,6),(0,32),info['block_seconds'],
        flood=info['flood'],hosts=hosts,foot='New 5 Nov capture: unchanged Task 2 controller; h1 UDP 10 Mbps + ping, h2 ICMP flood for 8 s.\n'
        'All switch panels use the same linear scale. Interval-average peer RX; zero-scale lines may contain small control traffic.')
    plot_hosts(out,hosts,info)
    t3=historical('task3');s3=policy['standalone']['task3']
    plot_grid(out,'task3-all-links','Task 3 | all 11 switch links; cost update with static forwarding',t3,(2,6),(-12,35),0,
        recovery=s3['restored_seconds'],foot='Original October experiment. Red: source blocked; green: penalty cleared.\n'
        's1 -> s2 -> s6 retains the legitimate load; changing costs alone does not change installed routes.')
    phase=[];case_info={}
    for case,key,target in [('A','A',(2,3)),('B','B1',(2,6)),('C','C',(5,6))]:
        rows=historical(key);trial=policy['trials'][key]
        if case=='C':
            initial=load('todo05/'+trial['run']+'/evidence/initial.json')
            assert initial['installed']['routes']['10.0.0.5>10.0.0.6']['path']==[5,6]
            assert initial['installed']['routes']['10.0.0.6>10.0.0.5']['path']==[6,3,5]
        bt=next(e['seconds'] for e in trial['events'] if e['event']=='block')
        recovery=next(e['seconds'] for e in trial['events'] if e['event']=='penalty_restored')
        path='h1 route stays s1 -> s2 -> s6' if case!='B' else 'h1 changes s1 -> s2 -> s6 to s1 -> s2 -> s3 -> s6, then returns'
        plot_grid(out,f'task4-{case}-all-links',f'Task 4 case {case} | all 11 switch links, both directions',rows,target,(0,60),bt,
            flood=(12,26),recovery=recovery,foot=path+'. Shading: planned flood; peer RX includes all traffic.\n'+
            ('C condition: only the h5 -> h6 test pair is pinned to s5 -> s6; h1 is not pinned.' if case=='C' else 'Original student measurement; all 22 directions are shown, including idle and reverse directions.'))
        case_info[case]=dict(run=trial['run'],path_before=trial['initial_path'],path_during=trial['during_path'],path_after=trial['recovered_path'],
            block_seconds=bt,penalty_restored_seconds=recovery,source='Original October student run',rows=len(rows))
        for name,lo,hi in [('before',4,10),('during',15,24),('after',40,55)]:
            for edge in sorted({r['edge'] for r in rows}):
                v=[r for r in rows if r['edge']==edge and lo<=r['seconds']<hi]
                phase.append(dict(task='Task4-'+case,phase=name,edge=edge,start=lo,end=hi,samples=len(v),
                    mean_rx_mbps=statistics.mean(r['rx_mbps'] for r in v),peak_rx_mbps=max(r['rx_mbps'] for r in v)))
    for task,rows,windows in [('Task2',t2,[('before',4,10),('during',14,19),('after',24,30)]),
                              ('Task3',t3,[('before',-10,-2),('during',3,8),('after',20,30)])]:
        for name,lo,hi in windows:
            for edge in sorted({r['edge'] for r in rows}):
                v=[r for r in rows if r['edge']==edge and lo<=r['seconds']<hi]
                phase.append(dict(task=task,phase=name,edge=edge,start=lo,end=hi,samples=len(v),
                    mean_rx_mbps=statistics.mean(r['rx_mbps'] for r in v),peak_rx_mbps=max(r['rx_mbps'] for r in v)))
    assert len(phase)==330
    for r in phase:
        if r['task'] in ('Task2','Task3','Task4-A','Task4-C') and r['edge'] in ('1>2','2>6'):
            assert 9<r['mean_rx_mbps']<12,r
    csv_write(out,'all-tasks-phase-means.csv',phase)
    result=dict(status='PASS',task2=info,task4=case_info,task3_source='Original October static-cost-stage run',
        figure_count=6,all_11_switch_links_both_directions=True,task2_all_6_host_attachments=True,
        phase_rows=len(phase),historical_source_chain_verified=len(policy['source_provenance']),source_provenance=PROVENANCE,
        script_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest())
    (out/'ALL_LINK_EVIDENCE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:result[k] for k in ['status','figure_count','task2','task4','phase_rows']},indent=2))


if __name__=='__main__':main()
