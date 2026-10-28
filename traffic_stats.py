"""Counter differencing and EMA decisions independent of Ryu/Mininet."""
import json


class FlowRates:
    def __init__(self):
        self.previous = {}

    def key(self, dpid, stat):
        return (dpid, stat.table_id, stat.priority, stat.cookie,
                json.dumps(dict(stat.match.items()), sort_keys=True))

    def sample(self, dpid, stat, now):
        key = self.key(dpid, stat)
        duration = stat.duration_sec + stat.duration_nsec / 1e9
        current = (stat.packet_count, stat.byte_count, duration, now)
        old = self.previous.get(key)
        self.previous[key] = current
        if old is None or now <= old[3] or duration < old[2]:
            return None
        if current[0] < old[0] or current[1] < old[1]:
            return None
        elapsed = now - old[3]
        return dict(pps=(current[0]-old[0])/elapsed,
                    bps=8*(current[1]-old[1])/elapsed, elapsed=elapsed)

    def prune(self, dpid, present):
        self.previous = {key: value for key, value in self.previous.items()
                         if key[0] != dpid or key in present}


class SourceEMA:
    def __init__(self, sources, theta=.3, multiplier=3, floor_pps=2000, warmup=5):
        self.theta, self.multiplier = theta, multiplier
        self.floor_pps, self.warmup = floor_pps, warmup
        self.sources = {ip: dict(ema_pps=0., samples=0, blocked=False) for ip in sources}

    def observe(self, ip, pps):
        state = self.sources[ip]
        old = state['ema_pps']
        threshold = max(self.floor_pps, self.multiplier*old)
        warmed = state['samples'] >= self.warmup
        newly_blocked = warmed and not state['blocked'] and pps > threshold
        if newly_blocked:
            state['blocked'] = True
        if not state['blocked']:
            state['ema_pps'] = self.theta*pps + (1-self.theta)*old
        state['samples'] += 1
        state['pps'] = pps
        return dict(source=ip, pps=pps, old_ema_pps=old,
                    new_ema_pps=state['ema_pps'], threshold_pps=threshold,
                    samples=state['samples'], warmed=warmed,
                    blocked=state['blocked'], newly_blocked=newly_blocked)
