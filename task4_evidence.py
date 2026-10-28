"""Review saved Task4 evidence without starting traffic or changing a network."""
import json
from pathlib import Path
import re


def controller_log_check(out, required=False):
    path = Path(out) / 'ryu.log'
    if not path.exists():
        if required:
            raise FileNotFoundError('Harness-owned controller log missing: '+str(path))
        return 'External controller terminal not captured; controller events checked separately'
    assert 'Traceback' not in path.read_text(), 'Controller traceback in '+str(path)
    return 'Controller text log checked'


def performance(out):
    out = Path(out)
    summary = re.findall(r'([\d.]+) Mbits/sec\s+[\d.]+ ms\s+(\d+)/\s*(\d+)\s+\(([\d.]+)%\)',
                         (out / 'sender.log').read_text())
    assert summary, 'UDP Server Report missing'
    mbps, lost, total, loss = summary[-1]
    assert float(mbps) > 8 and float(loss) < 5, summary[-1]
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
    assert len(reply_times) >= 100, 'Too few continuous ping replies'
    max_reply_gap = max(b-a for a, b in zip(reply_times, reply_times[1:]))
    assert max_reply_gap < 3, max_reply_gap
    ping_summary = re.search(r'(\d+) packets transmitted, (\d+) received, ([\d.]+)% packet loss', ping_text)
    assert ping_summary, 'Continuous ping summary missing'
    windows = {}
    for name, lo, hi in [('before', 4, 10), ('during', 15, 24), ('after', 40, 55)]:
        selected = [r for r in intervals if r['start'] >= lo and r['end'] <= hi]
        assert len(selected) >= hi-lo-2, (name, intervals)
        total_i, lost_i = sum(r['total'] for r in selected), sum(r['lost'] for r in selected)
        duration = sum(r['end']-r['start'] for r in selected)
        windows[name] = dict(start_seconds=lo, end_seconds=hi, intervals=len(selected),
            receiver_mbps=sum(r['mbps']*(r['end']-r['start']) for r in selected)/duration,
            loss_percent=100*lost_i/total_i, lost=lost_i, total=total_i)
    return dict(receiver_mbps=float(mbps), loss_percent=float(loss), lost=int(lost), total=int(total),
        windows=windows, receiver_intervals=intervals, receiver_positive_every_one_second_interval=True,
        continuous_ping_replies=len(reply_times), maximum_ping_reply_gap_seconds=max_reply_gap,
        ping_sent=int(ping_summary[1]), ping_received=int(ping_summary[2]),
        ping_loss_percent=float(ping_summary[3]))


def review_saved(out):
    out = Path(out)
    read = lambda name: json.loads((out / name).read_text())
    first, last = read('evidence/initial.json'), read('evidence/recovered.json')
    samples = [json.loads(line) for line in (out / 'dataplane-samples.jsonl').read_text().splitlines()]
    events = [json.loads(line) for line in (out / 'events.jsonl').read_text().splitlines()]
    case = first['installed']['scenario']
    source, target, edge = {'A': ('10.0.0.2', '10.0.0.3', '2>3'),
                           'B': ('10.0.0.2', '10.0.0.6', '2>6'),
                           'C': ('10.0.0.5', '10.0.0.6', '5>6')}[case]
    expected = [1, 2, 3, 6] if case == 'B' else [1, 2, 6]
    assert first['actual_path'] == last['actual_path'] == [1, 2, 6]
    assert len(samples) == 60
    assert first['installed']['routes'][source+'>'+target]['path'] == [int(source[-1]), int(target[-1])]
    active = [s for s in samples if s['costs']['links'][edge]['penalty'] == 60]
    assert active and any(s['actual_path'] == expected for s in active)
    if case != 'B':
        assert all(s['actual_path'] == expected for s in samples)
    for s in samples:
        if 18 < s['elapsed'] < 23:
            assert all(n > 0 for n in s['path_packet_counts'].values())
        if source in s['costs']['blocked']:
            assert all(any('nw_src='+source+' ' in row for row in rows) for rows in s['drops'].values())
    assert max(s['costs']['links'][edge]['received_bps'] for s in samples) > 1e6
    assert last['costs']['links'][edge]['penalty'] == 0 and last['costs']['blocked'] == [source]
    drop = last['drops'][str(int(source[-1]))][0]
    dropped = int(re.search(r'n_packets=(\d+)', drop)[1])
    assert dropped > 1000
    pings = (out / 'post-pings.txt').read_text()
    assert '3 packets transmitted, 3 received, 0% packet loss' in pings
    assert '2 packets transmitted, 0 received, 100% packet loss' in pings
    assert not any(e['event'] in ('openflow_error', 'routing_failure', 'barrier_timeout',
                                  'stats_timeout', 'port_stats_timeout') for e in events)
    assert any(e['event'] == 'penalty_restored' and e['source'] == source for e in events)
    if case == 'B':
        assert any(e['event'] == 'old_version_removed' for e in events)
    result = dict(status='PASS', scenario=case, scope='Offline review of original saved experiment; no replay',
        output=str(out), original_result=read('results.json'), initial_path=first['actual_path'],
        during_path=expected, recovered_path=last['actual_path'], dropped_packets=dropped,
        drops_preserved_all_samples=True, source_remains_blocked_after_cost_and_route_recovery=True,
        controller_log_check=controller_log_check(out), **performance(out))
    return result
