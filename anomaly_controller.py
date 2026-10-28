"""TODO3: teacher-inspired EMA/source blocking on the validated mesh baseline.

Keeps static routing for this stage. Dynamic costs and rerouting follow later.
Reference: teacher ceg_code/anomaly_detection.py, kept read-only.
"""
import json
import time

import baseline_controller as baseline
from traffic_stats import FlowRates, SourceEMA
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub

DROP_COOKIE = 0xCA230002


class AnomalyController(baseline.BaselineController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.flow_rates = FlowRates()
        self.detector = SourceEMA(self.hosts)
        self.replies = {}
        self.requests = {}
        self.rates = {}
        self.announced = False
        self.stats_worker = hub.spawn(self.stats_monitor)
        self.record('detection_parameters', sample_interval_seconds=1,
            theta=.3, multiplier=3, floor_pps=2000, warmup_samples=5,
            excluded_traffic='ICMP echo replies', block_scope='IPv4 source; all switches',
            recovery='Restart isolated experiment; no automatic unblock in TODO3')

    def drop(self, dp, ip):
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, cookie=DROP_COOKIE, priority=5000,
            match=p.OFPMatch(eth_type=0x0800, ipv4_src=ip),
            instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, [])]))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        super().features(ev)
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE,
            cookie=DROP_COOKIE, cookie_mask=0xffffffffffffffff,
            out_port=o.OFPP_ANY, out_group=o.OFPG_ANY, match=p.OFPMatch()))
        for ip, state in self.detector.sources.items():
            if state['blocked']:
                self.drop(dp, ip)

    def install(self):
        super().install()
        self.flow_rates.previous.clear()
        self.requests.clear()
        self.replies.clear()
        # Disjoint ICMP overrides: request counts contribute to detection;
        # echo replies from a victim are not classified as a separate attack.
        for key, route in self.routes.items():
            src, dst = key.split('>')
            for entry in reversed(route['outputs']):
                for priority, kind in ((110, 8), (109, 0)):
                    self.add_flow(self.dp[entry['dpid']], priority,
                        dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst,
                             ip_proto=1, icmpv4_type=kind), entry['output_port'])
        for dp in self.dp.values():
            request = dp.ofproto_parser.OFPBarrierRequest(dp)
            dp.set_xid(request)
            self.pending.add((dp.id, request.xid))
            dp.send_msg(request)
        self.deadline = time.monotonic() + 10

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats(self, ev):
        msg, now = ev.msg, time.monotonic()
        dpid = msg.datapath.id
        expected = self.requests.get(dpid)
        if expected is None or expected[0] != msg.xid:
            return
        key = (dpid, msg.xid)
        body = self.replies.setdefault(key, [])
        body.extend(msg.body)
        if msg.flags & msg.datapath.ofproto.OFPMPF_REPLY_MORE:
            return
        self.requests.pop(dpid, None)
        self.replies.pop(key, None)
        if not self.ready:
            return
        sources = {ip for ip, host in self.hosts.items() if host['switch'] == dpid}
        totals = {ip: dict(forward_pps=0., drop_pps=0., forward_bps=0., drop_bps=0.) for ip in sources}
        valid, present, destinations = set(sources), set(), {}
        for stat in body:
            src = stat.match.get('ipv4_src')
            if src not in sources:
                continue
            is_drop = stat.cookie == DROP_COOKIE and stat.priority == 5000
            is_route = stat.cookie == baseline.ROUTE_COOKIE and stat.priority in (100, 110)
            if not (is_drop or is_route):
                continue
            present.add(self.flow_rates.key(dpid, stat))
            rate = self.flow_rates.sample(dpid, stat, now)
            if rate is None:
                valid.discard(src)
                continue
            label = 'drop' if is_drop else 'forward'
            totals[src][label+'_pps'] += rate['pps']
            totals[src][label+'_bps'] += rate['bps']
            if is_route and rate['pps'] > destinations.get(src, (0, None))[0]:
                destinations[src] = (rate['pps'], stat.match.get('ipv4_dst'))
        self.flow_rates.prune(dpid, present)
        for ip in sorted(valid):
            rates = totals[ip]
            decision = self.detector.observe(ip, rates['forward_pps']+rates['drop_pps'])
            dst = destinations.get(ip, (0, None))[1]
            record = dict(decision, dpid=dpid, destination=dst, **rates)
            self.rates[ip] = record
            with (self.out / 'source-rates.jsonl').open('a') as f:
                f.write(json.dumps(dict(time=time.time(), **record))+'\n')
            if decision['newly_blocked']:
                for dp in self.dp.values():
                    self.drop(dp, ip)
                route = self.routes.get(ip+'>'+str(dst), {})
                self.record('block', **record, attack_path=route.get('path'))
                self.logger.warning('BLOCK source=%s pps=%.1f old_ema=%.1f threshold=%.1f path=%s',
                    ip, decision['pps'], decision['old_ema_pps'], decision['threshold_pps'], route.get('path'))
            self.sample_observed(record)
            if decision['pps'] > 0 or decision['samples'] <= 5:
                self.logger.info('STATS source=%s pps=%.1f old_ema=%.1f new_ema=%.1f threshold=%.1f warmup=%s blocked=%s drop_pps=%.1f',
                    ip, decision['pps'], decision['old_ema_pps'], decision['new_ema_pps'],
                    decision['threshold_pps'], 'done' if decision['warmed'] else str(decision['samples'])+'/5',
                    decision['blocked'], rates['drop_pps'])

    def sample_observed(self, record):
        """Extension point for link penalties; TODO3 itself keeps static costs."""
        pass

    def stats_monitor(self):
        while True:
            if self.ready and not self.failed:
                if not self.announced:
                    self.logger.info('DETECTION STARTED: poll=1s theta=0.3 multiplier=3 floor=2000pps warmup=5 samples; ICMP replies excluded')
                    self.announced = True
                now = time.monotonic()
                for dp in list(self.dp.values()):
                    old = self.requests.get(dp.id)
                    if old and now-old[1] <= 3:
                        continue
                    if old:
                        self.replies.pop((dp.id, old[0]), None)
                        self.record('stats_timeout', dpid=dp.id)
                    request = dp.ofproto_parser.OFPFlowStatsRequest(dp)
                    dp.set_xid(request)
                    self.requests[dp.id] = (request.xid, now)
                    dp.send_msg(request)
                snapshot = dict(time=time.time(), ready=True,
                    blocked=sorted(ip for ip, s in self.detector.sources.items() if s['blocked']),
                    sources=self.detector.sources, rates=self.rates,
                    parameters=dict(theta=.3, multiplier=3, floor_pps=2000, warmup_samples=5, sample_seconds=1),
                    dynamic_link_costs=False)
                temporary = self.out / 'anomaly-state.tmp'
                temporary.write_text(json.dumps(snapshot, indent=2))
                temporary.replace(self.out / 'anomaly-state.json')
            hub.sleep(1)
