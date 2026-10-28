"""Port byte-rate differences and directed dynamic-cost/quiet-time policy."""


class PortRates:
    def __init__(self):
        self.previous = {}

    def sample(self, dpid, stat, now):
        key = (dpid, stat.port_no)
        duration = stat.duration_sec + stat.duration_nsec / 1e9
        current = (stat.rx_bytes, stat.tx_bytes, duration, now)
        old = self.previous.get(key)
        self.previous[key] = current
        if old is None or now <= old[3] or duration < old[2]:
            return None
        if current[0] < old[0] or current[1] < old[1]:
            return None
        elapsed = now-old[3]
        return dict(rx_bps=8*(current[0]-old[0])/elapsed,
                    tx_bps=8*(current[1]-old[1])/elapsed, elapsed=elapsed,
                    sampled_monotonic=now)


class LinkCosts:
    def __init__(self, capacity_bps=40000000, alpha=5, beta=60,
                 minimum_hold_seconds=8, quiet_seconds=5):
        self.capacity_bps, self.alpha, self.beta = capacity_bps, alpha, beta
        self.minimum_hold_seconds, self.quiet_seconds = minimum_hold_seconds, quiet_seconds
        self.anomalies = {}

    def detected(self, source, path, now):
        self.anomalies[source] = dict(edges=list(zip(path, path[1:])),
            detected=now, last_activity=now, active=True)

    def dropped_activity(self, source, now):
        info = self.anomalies.get(source)
        if info is None:
            return False
        reactivated = not info['active']
        if reactivated:
            info['detected'] = now
        info.update(last_activity=now, active=True)
        return reactivated

    def expire(self, now):
        restored = []
        for source, info in self.anomalies.items():
            if info['active'] and now-info['detected'] >= self.minimum_hold_seconds \
                    and now-info['last_activity'] >= self.quiet_seconds:
                info['active'] = False
                restored.append(source)
        return restored

    def cost(self, a, b, base, received_bps, now):
        sources = sorted(source for source, info in self.anomalies.items()
                         if info['active'] and (a, b) in info['edges'])
        utilization = min(max(received_bps/self.capacity_bps, 0), 1)
        load_term = self.alpha*utilization
        penalty = self.beta if sources else 0
        return dict(src=a, dst=b, base=base, received_bps=received_bps,
                    capacity_bps=self.capacity_bps, utilization=utilization,
                    load_term=load_term, penalty=penalty,
                    cost=base+load_term+penalty, anomalous_sources=sources)
