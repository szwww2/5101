"""TODO4: measured directed link costs and source-activity-based recovery.

Cost observation only: current forwarding remains the validated static baseline.
Rerouting existing flows is the next stage. Source-IP blocks stay installed.
"""
import json
import time

import anomaly_controller as anomaly
from link_costs import LinkCosts, PortRates
from ryu.controller import ofp_event
from ryu.controller.handler import MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub


class DynamicCostController(anomaly.AnomalyController):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.port_rates = PortRates()
        self.link_model = LinkCosts()
        self.port_samples = {}
        self.port_requests = {}
        self.port_replies = {}
        self.cost_ready = False
        self.cost_worker = hub.spawn(self.cost_monitor)
        self.record('cost_parameters', capacity_bps=40000000, alpha=5, beta=60,
            minimum_hold_seconds=8, quiet_seconds=5,
            measurement='Directed link rate from peer ingress rx_bytes; source tx_bytes also recorded',
            routing='Static route rules retained in TODO4; no rerouting yet')

    def sample_observed(self, record):
        now, source = time.monotonic(), record['source']
        if record['newly_blocked']:
            route = self.routes.get(source+'>'+str(record['destination']))
            if route:
                self.link_model.detected(source, route['path'], now)
                self.record('penalty_added', source=source, path=route['path'], beta=60)
        elif record['blocked'] and record['drop_pps'] > 0:
            if self.link_model.dropped_activity(source, now):
                self.record('penalty_reactivated', source=source,
                    reason='New packets at blocked source ingress; retain previously observed attack path')

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats(self, ev):
        msg, now = ev.msg, time.monotonic()
        dpid = msg.datapath.id
        expected = self.port_requests.get(dpid)
        if expected is None or expected[0] != msg.xid:
            return
        key = (dpid, msg.xid)
        body = self.port_replies.setdefault(key, [])
        body.extend(msg.body)
        if msg.flags & msg.datapath.ofproto.OFPMPF_REPLY_MORE:
            return
        self.port_requests.pop(dpid, None)
        self.port_replies.pop(key, None)
        for stat in body:
            rate = self.port_rates.sample(dpid, stat, now)
            if rate is not None:
                self.port_samples[(dpid, stat.port_no)] = rate
            else:
                self.port_samples.pop((dpid, stat.port_no), None)

    def cost_snapshot(self):
        now, links = time.monotonic(), {}
        # If flow statistics are missing, do not declare a blocked source quiet.
        stale = []
        for source, info in self.link_model.anomalies.items():
            dpid = self.hosts[source]['switch']
            samples = [v[3] for k, v in self.flow_rates.previous.items() if k[0] == dpid]
            if info['active'] and (not samples or now-max(samples) > 3):
                stale.append(source)
                info['last_activity'] = now
        for source in self.link_model.expire(now):
            self.record('penalty_restored', source=source,
                        reason='Minimum hold passed and ingress drop counter quiet for 5 seconds')
        for a, b, data in self.graph.edges(data=True):
            if not self.graph.has_edge(b, a):
                continue
            out_port, in_port = data['port'], self.graph[b][a]['port']
            received = self.port_samples.get((b, in_port))
            sent = self.port_samples.get((a, out_port))
            valid = received is not None and now-received['sampled_monotonic'] <= 3
            base = self.costs[tuple(sorted((a, b)))]
            item = self.link_model.cost(a, b, base, received['rx_bps'] if valid else 0, now)
            item.update(egress_port=out_port, peer_ingress_port=in_port,
                        measured=valid, source_tx_bps=sent['tx_bps'] if sent else None)
            links[str(a)+'>'+str(b)] = item
        ready = self.ready and len(links) == 22 and all(v['measured'] for v in links.values())
        return dict(time=time.time(), ready=ready, links=links,
            stale_source_stats=stale,
            blocked=sorted(ip for ip, state in self.detector.sources.items() if state['blocked']),
            alpha=5, beta=60, capacity_bps=40000000, minimum_hold_seconds=8,
            quiet_seconds=5, rerouting=False,
            measurement='Destination ingress rx_bytes for each directed link',
            routing='Installed routes remain static during TODO4')

    def cost_monitor(self):
        while True:
            if self.ready and not self.failed:
                now = time.monotonic()
                for dp in list(self.dp.values()):
                    old = self.port_requests.get(dp.id)
                    if old and now-old[1] <= 3:
                        continue
                    if old:
                        self.port_replies.pop((dp.id, old[0]), None)
                        self.record('port_stats_timeout', dpid=dp.id)
                    request = dp.ofproto_parser.OFPPortStatsRequest(dp, 0, dp.ofproto.OFPP_ANY)
                    dp.set_xid(request)
                    self.port_requests[dp.id] = (request.xid, now)
                    dp.send_msg(request)
            snapshot = self.cost_snapshot()
            temporary = self.out / 'cost-state.tmp'
            temporary.write_text(json.dumps(snapshot, indent=2))
            temporary.replace(self.out / 'cost-state.json')
            with (self.out / 'link-costs.jsonl').open('a') as f:
                f.write(json.dumps(snapshot)+'\n')
            if snapshot['ready']:
                if not self.cost_ready:
                    self.logger.info('COST MONITOR READY: 22 directed link rates; alpha=5 beta=60 hold>=8s quiet>=5s; static route rules retained')
                    self.cost_ready = True
                link = snapshot['links']['2>6']
                self.logger.info('LINK s2->s6 rx_mbps=%.3f utilization=%.3f base=%.1f load=%.3f penalty=%.1f cost=%.3f',
                    link['received_bps']/1e6, link['utilization'], link['base'],
                    link['load_term'], link['penalty'], link['cost'])
            hub.sleep(1)
