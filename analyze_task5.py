"""Task5: source-traceable offline plots of the student's three measured trials.

No network operations. Receiver Mbps is iperf's rounded delivered-rate report;
loss is calculated from its receiver-side lost/total datagram counters.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics
import time

from task4_evidence import performance

ROOT = Path(__file__).resolve().parent
TRIALS = {
    'A': ('run-A-20261016-145805-CPT5A8', '2>3', 10, 'h2 -> h3'),
    'B': ('run-B-20261016-144402-YuFNPf', '2>6', 14, 'h2 -> h6'),
    'C': ('run-C-20261016-153103-Ho9Y7P', '5>6', 20, 'h5 -> h6; direct link pinned'),
}


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def loss_percent(lost, total):
    if total <= 0:
        raise ValueError('No datagrams in measurement window')
    return 100 * lost / total


def path_cost(links, path):
    return sum(links[str(a)+'>'+str(b)]['cost'] for a, b in zip(path, path[1:]))


def load_trial(case, root=ROOT, folder_override=None):
    folder, edge, base, label = TRIALS[case]
    if folder_override is not None:
        folder = folder_override
    run = root / 'todo05' / folder
    original = read_json(run / 'results.json')
    review = read_json(run / 'evidence' / ('student-'+case+'-reviewed-results.json'))
    assert review['status'] == 'PASS'
    samples_file = run / 'dataplane-samples.jsonl'
    samples = [json.loads(line) for line in samples_file.read_text().splitlines()]
    exact_origin = original.get('legitimate_started')
    # Capture completion follows sample-loop elapsed measurement; this is an
    # estimate with unknown positive capture latency, never an exact timestamp.
    origin = exact_origin if exact_origin is not None else min(s['time']-s['elapsed'] for s in samples)
    clock_quality = 'sender-launch timestamp' if exact_origin is not None else 'estimated from sample timestamps; sub-second bias unknown'
    metrics = performance(run)
    receiver = []
    for row in metrics['receiver_intervals']:
        receiver.append(dict(row, midpoint=(row['start']+row['end'])/2,
                             loss_percent=loss_percent(row['lost'], row['total'])))
    assert len(receiver) == 60
    assert abs(sum(r['lost'] for r in receiver)-metrics['lost']) == 0
    frozen = run / 'evidence' / ('events-at-offline-review.jsonl' if case == 'B' else 'events-at-final-review.jsonl')
    raw_events = [json.loads(line) for line in frozen.read_text().splitlines()]
    events = []
    for e in raw_events:
        t = e['time']-origin
        if 0 <= t <= 60 and (e['event'] in ('block', 'penalty_added', 'penalty_restored')
            or (e['event'] == 'route_committed' and e['flow'] == '10.0.0.1>10.0.0.6')):
            events.append(dict(e, seconds=t))
    cost_file = run / 'link-costs.jsonl'
    costs = []
    for line in cost_file.read_text().splitlines():
        row = json.loads(line)
        t = row['time']-origin
        if -.5 <= t <= 60 and row['ready'] and edge in row['links']:
            link = row['links'][edge]
            assert link['base'] == base
            assert abs(link['cost']-(link['base']+link['load_term']+link['penalty'])) < 1e-8
            costs.append(dict(seconds=t, normalized=link['cost']/base, **link))
    assert len(costs) >= 55
    path_rows = []
    for s in samples:
        links, path = s['costs']['links'], s['actual_path']
        path_rows.append(dict(seconds=s['elapsed'], cost_seconds=s['costs']['time']-origin,
            path=path, tag=s['active_vlan'],
            active_cost=path_cost(links, path), original_cost=path_cost(links, [1, 2, 6]),
            alternative_cost=path_cost(links, [1, 2, 3, 6])))
    restored = [e for e in events if e['event'] == 'penalty_restored']
    blocks = [e for e in events if e['event'] == 'block']
    assert len(restored) == len(blocks) == 1
    interval_total = sum(r['total'] for r in receiver)
    stats = dict(receiver_mbps_reported=metrics['receiver_mbps'], lost=metrics['lost'], total=metrics['total'],
        whole_loss_percent=loss_percent(metrics['lost'], metrics['total']),
        printed_whole_loss_percent=metrics['loss_percent'], interval_total=interval_total,
        interval_loss_percent=loss_percent(sum(r['lost'] for r in receiver), interval_total),
        min_one_second_mbps=min(r['mbps'] for r in receiver),
        max_one_second_loss_percent=max(r['loss_percent'] for r in receiver),
        receiver_mean_one_second_mbps=statistics.mean(r['mbps'] for r in receiver),
        min_normalized_cost=min(r['normalized'] for r in costs), max_normalized_cost=max(r['normalized'] for r in costs),
        block_seconds=blocks[0]['seconds'], penalty_restored_seconds=restored[0]['seconds'],
        initial_path=review['initial_path'], during_path=review['during_path'], recovered_path=review['recovered_path'],
        source_drop_packets=review['dropped_packets'], windows=metrics['windows'],
        ping_sent=metrics['ping_sent'], ping_received=metrics['ping_received'], ping_loss_percent=metrics['ping_loss_percent'])
    # Parse only the main 60-second receiver session, already selected by the
    # established performance parser. Tiny final-ACK sessions are not data bins.
    sources = [run / 'results.json', run / 'sender.log', run / 'receiver.log',
               run / 'continuous-ping.log', samples_file, cost_file, frozen,
               run / 'evidence' / ('student-'+case+'-reviewed-results.json')]
    return dict(case=case, label=label, run=str(run), target_edge=edge, base_cost=base,
        origin=origin, clock_quality=clock_quality,
        scheduled_attack_on=original.get('attack_started', origin+12)-origin,
        scheduled_attack_off=original.get('attack_started', origin+12)-origin+14,
        timeout_note='Off marker is the planned 14-second timeout; actual process exit was not timestamped',
        receiver_alignment='Receiver bins start at first UDP datagram; overlaid against sender-launch clock at about one-second resolution. No sub-second synchronization claim.',
        costs=costs, receiver=receiver, events=events, paths=path_rows, metrics=stats,
        provenance={str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources})


def write_csv(path, fields, rows):
    with Path(path).open('w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(rows)


def plot_trials(trials, output):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False,
                         'savefig.facecolor': 'white'})
    colors = {'cost': '#315AA7', 'loss': '#C43A42', 'rate': '#087E70'}

    def markings(ax, trial):
        ax.axvspan(trial['scheduled_attack_on'], trial['scheduled_attack_off'], color='#D88A20', alpha=.12)
        ax.axvline(trial['metrics']['block_seconds'], color='#B83B42', lw=1, ls=':')
        ax.axvline(trial['metrics']['penalty_restored_seconds'], color='#248658', lw=1, ls='--')
        for e in trial['events']:
            if e['event'] == 'route_committed':
                ax.axvline(e['seconds'], color='#76539B', lw=.9, ls='-.', alpha=.8)
        ax.set_xlim(0, 60)
        ax.grid(alpha=.18)

    def panels(axes, trial):
        x = [r['seconds'] for r in trial['costs']]
        axes[0].step(x, [r['normalized'] for r in trial['costs']], where='post', color=colors['cost'], lw=1.8)
        axes[0].set_ylim(.8, 7.7)
        axes[0].axhline(1, color='#88919E', lw=.7, ls='--')
        receiver = trial['receiver']
        axes[1].bar([r['midpoint'] for r in receiver], [r['loss_percent'] for r in receiver],
                    width=.85, color=colors['loss'])
        axes[1].set_ylim(0, 5.8)
        axes[2].stairs([r['mbps'] for r in receiver], [receiver[0]['start']]+[r['end'] for r in receiver],
                       baseline=None, color=colors['rate'], lw=1.6)
        axes[2].axhline(10, color='#88919E', ls='--', lw=.8)
        axes[2].set_ylim(9.2, 10.25)
        for ax in axes:
            markings(ax, trial)

    fig, axs = plt.subplots(3, 3, figsize=(14, 8.4), sharex=True)
    for col, (case, trial) in enumerate(trials.items()):
        panels(axs[:, col], trial)
        axs[0, col].set_title('Case '+case+': '+trial['label'], fontsize=11, pad=12)
        axs[2, col].set_xlabel('Time (s)')
    axs[0, 0].set_ylabel('Link cost / original base cost')
    axs[1, 0].set_ylabel('Receiver UDP loss (%)')
    axs[2, 0].set_ylabel('Receiver throughput (Mbps)')
    fig.suptitle('Student trials: legitimate h1 -> h6, offered UDP rate 10 Mbps', fontsize=14, y=.985)
    fig.text(.5, .035, 'Shading: scheduled flood | red: detection/block | green: penalty recovery | purple: route commit (B)', ha='center', fontsize=9)
    fig.text(.5, .012, '1-second receiver bins; no sub-second clock alignment. Case B origin estimated. Case C workload pinned to s5 -> s6. Throughput axis cropped.', ha='center', fontsize=8)
    fig.tight_layout(rect=(.02, .07, .995, .95))
    fig.savefig(output / 'task5-three-cases.png', dpi=180)
    fig.savefig(output / 'task5-three-cases.svg')
    plt.close(fig)
    for case, trial in trials.items():
        fig, axes = plt.subplots(3, 1, figsize=(10, 7.3), sharex=True)
        panels(axes, trial)
        axes[0].set_title('Case '+case+': '+trial['label']+' | h1 -> h6 performance')
        for ax, label in zip(axes, ['Cost / base cost', 'Receiver UDP loss (%)', 'Receiver throughput (Mbps)']):
            ax.set_ylabel(label)
        axes[-1].set_xlabel('Seconds from sender launch (receiver bins approximately aligned)')
        fig.text(.5, .015, 'Flood shaded; detection red; penalty recovery green; route commit purple (B). 1-second bins; throughput axis cropped.', ha='center', fontsize=8)
        fig.tight_layout(rect=(0, .04, 1, 1))
        fig.savefig(output / ('case-'+case+'-timeseries.png'), dpi=180)
        fig.savefig(output / ('case-'+case+'-timeseries.svg'))
        plt.close(fig)
    trial = trials['B']
    fig, axes = plt.subplots(4, 1, figsize=(11, 9.2), sharex=True, gridspec_kw={'height_ratios': [2, .9, 1.5, 1.5]})
    x = [r['seconds'] for r in trial['paths']]
    for field, label, color in [('original_cost', 'Original s1-s2-s6', '#315AA7'),
                                ('alternative_cost', 'Alternative s1-s2-s3-s6', '#C47B16')]:
        axes[0].plot([r['cost_seconds'] for r in trial['paths']], [r[field] for r in trial['paths']],
                     label=label+' (sampled)', color=color, marker='.', markersize=3)
    axes[0].set_ylabel('Sum of link costs')
    axes[0].legend(loc='upper right', fontsize=9)
    axes[0].set_title('Case B: cost changes, actual forwarding path and receiver performance')
    axes[1].step(x, [int(r['path'] == [1, 2, 3, 6]) for r in trial['paths']], where='post', color='#65479A')
    axes[1].set_yticks([0, 1], ['s1-s2-s6', 's1-s2-s3-s6'])
    axes[1].set_ylim(-.3, 1.3)
    axes[1].set_ylabel('Actual path')
    receiver = trial['receiver']
    axes[2].bar([r['midpoint'] for r in receiver], [r['loss_percent'] for r in receiver], color=colors['loss'], width=.85)
    axes[2].set_ylabel('UDP loss (%)')
    axes[2].set_ylim(0, 5.8)
    axes[2].annotate('12-13 s: 43/848 lost\n5.07%; receiver 9.47 Mbps', xy=(12.5, 5.07), xytext=(17, 4.2),
                     fontsize=9, arrowprops={'arrowstyle': '->', 'color': colors['loss']})
    axes[3].stairs([r['mbps'] for r in receiver], [receiver[0]['start']]+[r['end'] for r in receiver],
                   baseline=None, color=colors['rate'])
    axes[3].axhline(10, color='#88919E', ls='--', lw=.8)
    axes[3].set_ylabel('Receiver Mbps')
    axes[3].set_ylim(9.2, 10.25)
    axes[3].set_xlabel('Time (s); sender origin estimated, receiver bins approximately aligned')
    for ax in axes:
        markings(ax, trial)
    fig.text(.5, .012, 'Cost snapshots and path probes are asynchronous (about 1 s); purple marks controller route commits. No sub-second ordering claim.', ha='center', fontsize=8)
    fig.tight_layout(rect=(.015, .035, 1, 1))
    fig.savefig(output / 'case-B-routing-and-loss.png', dpi=180)
    fig.savefig(output / 'case-B-routing-and-loss.svg')
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / 'todo06' / ('analysis-'+time.strftime('%Y%m%d-%H%M%S'))
    output.mkdir(parents=True, exist_ok=False)
    trials = {case: load_trial(case) for case in TRIALS}
    for case, trial in trials.items():
        write_csv(output / ('case-'+case+'-link-cost.csv'),
            ['seconds', 'base', 'normalized', 'cost', 'received_bps', 'utilization', 'load_term', 'penalty'], trial['costs'])
        write_csv(output / ('case-'+case+'-receiver.csv'),
            ['start', 'end', 'midpoint', 'mbps', 'lost', 'total', 'loss_percent', 'jitter_ms'], trial['receiver'])
        write_csv(output / ('case-'+case+'-paths.csv'),
            ['seconds', 'cost_seconds', 'path', 'tag', 'active_cost', 'original_cost', 'alternative_cost'], trial['paths'])
        write_csv(output / ('case-'+case+'-events.csv'),
            ['seconds', 'event', 'source', 'old_path', 'new_path'], trial['events'])
    plot_trials(trials, output)
    summary = {'scope': 'One student trial per scenario; source observations, no synthetic measurements or repeated-trial confidence intervals',
        'normalization': 'Directed link cost divided by its original fixed base cost: A/10, B/14, C/20',
        'measurement': 'UDP receiver loss=100*lost/total; Mbps from receiver iperf report, rounded at source; per-second data not smoothed',
        'cases': {case: {k:v for k,v in trial.items() if k not in ('receiver', 'costs', 'paths')} for case, trial in trials.items()},
        'analysis_source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    (output / 'analysis-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    for case, trial in trials.items():
        m = trial['metrics']
        print(case, 'mean report', m['receiver_mbps_reported'], 'whole loss', m['whole_loss_percent'],
              'peak 1s loss', m['max_one_second_loss_percent'], 'min 1s Mbps', m['min_one_second_mbps'])
    print(output)


if __name__ == '__main__':
    main()
