"""Compare saved student B repeats; never starts or modifies a network."""
import argparse
import hashlib
import json
from pathlib import Path

from analyze_task5 import ROOT, load_trial, write_csv


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--run', action='append', required=True, help='B run directory name under todo05; repeat in chronological order')
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    # Controllers may still append costs after the measured minute. Freeze all
    # inputs so source hashes refer to the exact bytes used for this analysis.
    frozen_root = output / 'inputs'
    copied = {}
    for folder in args.run:
        source = ROOT / 'todo05' / folder
        target = frozen_root / 'todo05' / folder
        for name in ['results.json', 'sender.log', 'receiver.log', 'continuous-ping.log',
                     'dataplane-samples.jsonl', 'link-costs.jsonl',
                     'evidence/events-at-offline-review.jsonl', 'evidence/student-B-reviewed-results.json']:
            data = (source / name).read_bytes()
            destination = target / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(data)
            copied[str(destination.relative_to(frozen_root))] = hashlib.sha256(data).hexdigest()
    trials = [load_trial('B', root=frozen_root, folder_override=folder) for folder in args.run]
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    plt.rcParams.update({'font.size': 10, 'axes.spines.top': False, 'axes.spines.right': False})
    colors = ['#315AA7', '#C47B16', '#16806D', '#76539B']
    fig, axes = plt.subplots(3, 1, figsize=(11, 8.6), sharex=True)
    maximum_loss = max(t['metrics']['max_one_second_loss_percent'] for t in trials)
    minimum_rate = min(t['metrics']['min_one_second_mbps'] for t in trials)
    maximum_rate = max(r['mbps'] for t in trials for r in t['receiver'])
    for index, trial in enumerate(trials):
        color = colors[index % len(colors)]
        label = 'Trial '+str(index+1)
        axes[0].step([r['seconds'] for r in trial['costs']], [r['normalized'] for r in trial['costs']],
                     where='post', color=color, label=label, lw=1.5)
        receiver = trial['receiver']
        bins = [receiver[0]['start']]+[r['end'] for r in receiver]
        axes[1].stairs([r['loss_percent'] for r in receiver], bins, baseline=None, color=color, label=label)
        axes[2].stairs([r['mbps'] for r in receiver], bins, baseline=None, color=color, label=label)
        write_csv(output / ('trial-'+str(index+1)+'-receiver.csv'),
                  ['start', 'end', 'mbps', 'lost', 'total', 'loss_percent'], receiver)
    for ax in axes:
        ax.axvspan(12, 26, color='#D88A20', alpha=.1)
        ax.set_xlim(0, 60)
        ax.grid(alpha=.18)
    axes[0].set_ylabel('s2 -> s6 cost / 14')
    axes[0].legend(loc='upper right', ncol=len(trials))
    axes[0].set_ylim(.8, 6.2)
    axes[0].set_title('Case B repeated student trials | legitimate UDP offered at 10 Mbps')
    axes[1].set_ylabel('Receiver UDP loss (%)')
    axes[1].set_ylim(0, maximum_loss*1.15+.1)
    axes[2].set_ylabel('Receiver throughput (Mbps)')
    axes[2].set_ylim(minimum_rate-.2, max(10.25, maximum_rate+.1))
    axes[2].axhline(10, color='#88919E', ls='--', lw=.8)
    axes[2].set_xlabel('Time (s); one-second receiver bins, approximately aligned across trials')
    fig.text(.5, .018, 'Shading: planned flood 12-26 s. Trial 1 origin estimated. Individual observations; no confidence intervals. Throughput axis cropped.',
             ha='center', fontsize=8)
    fig.tight_layout(rect=(0, .045, 1, 1))
    fig.savefig(output / 'case-B-repeat-comparison.png', dpi=180)
    fig.savefig(output / 'case-B-repeat-comparison.svg')
    plt.close(fig)
    summary = {'scope': 'Repeated student B measurements; all included, no best-run selection', 'trial_count': len(trials),
        'frozen_input_root': str(frozen_root), 'frozen_input_sha256': copied,
        'trials': [{'index': i+1, 'run': str(ROOT / 'todo05' / args.run[i]),
                    'frozen_run': t['run'], 'clock_quality': t['clock_quality'],
                    'metrics': t['metrics'], 'provenance': t['provenance']} for i,t in enumerate(trials)],
        'code_sha256': {p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [Path(__file__), ROOT / 'analyze_task5.py']}}
    (output / 'repeat-summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    rows = [dict(trial=i+1, receiver_mbps=t['metrics']['receiver_mbps_reported'],
                 lost=t['metrics']['lost'], total=t['metrics']['total'],
                 whole_loss_percent=t['metrics']['whole_loss_percent'],
                 peak_one_second_loss_percent=t['metrics']['max_one_second_loss_percent'],
                 min_one_second_receiver_mbps=t['metrics']['min_one_second_mbps']) for i,t in enumerate(trials)]
    write_csv(output / 'repeat-metrics.csv', list(rows[0]), rows)
    print(json.dumps(rows, indent=2))
    print(output)


if __name__ == '__main__':
    main()
