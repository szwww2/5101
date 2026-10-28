"""Teacher Task 4: versioned forwarding, measured costs, source blocks.

Internal VLAN labels distinguish old/new packets during a route transition.
Labels never reach hosts. Teacher files and previous stage controllers unchanged.
"""
import json
import os
import time

import networkx as nx
import dynamic_cost_controller as costs
import baseline_controller as baseline
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub

VERSION_PREFIX = 0xCA25000000000000
VERSION_MASK = 0xFFFFFFFFFFFF0000


class ReroutingController(costs.DynamicCostController):
    def record(self, kind, **values):
        if kind == 'cost_parameters':
            values['routing'] = 'Measured costs applied by versioned ReroutingController'
        if kind == 'detection_parameters':
            values['recovery'] = 'Cost/legitimate-route recovery preserves source block; restart each scenario'
        super().record(kind, **values)

    def __init__(self, *args, **kwargs):
        self.case = os.environ.get('CEG_SCENARIO', 'B').upper()
        if self.case not in ('A', 'B', 'C'):
            raise ValueError('CEG_SCENARIO must be A, B or C')
        self.used_tags = set()
        self.retired = []
        self.changed_at = {}
        self.initialized = False
        self.route_generation = 0
        super().__init__(*args, **kwargs)
        self.record('routing_parameters', scenario=self.case, improvement_margin=1,
            minimum_route_hold_seconds=3, old_version_retention_seconds=5,
            transition='Prepare tagged downstream rules; barrier; switch untagged ingress; barrier; drain old version',
            case_c_condition='Only h5->h6 IPv4 test pair pinned to direct s5->s6' if self.case == 'C' else None)

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        super().features(ev)
        dp = ev.msg.datapath
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE,
            cookie=VERSION_PREFIX, cookie_mask=VERSION_MASK,
            out_port=o.OFPP_ANY, out_group=o.OFPG_ANY, match=p.OFPMatch()))

    def label(self):
        tag = next((n for n in range(1, 4095) if n not in self.used_tags), None)
        if tag is None:
            raise RuntimeError('No free route version labels')
        self.used_tags.add(tag)
        return tag

    def route(self, src, dst):
        if self.case == 'C' and (src, dst) == ('10.0.0.5', '10.0.0.6'):
            path = [5, 6]
        else:
            path = nx.shortest_path(self.graph, self.hosts[src]['switch'],
                self.hosts[dst]['switch'], weight='cost')
        return dict(path=path, cost=self.path_cost(path), outputs=[
            dict(dpid=n, output_port=self.hosts[dst]['port'] if i == len(path)-1
                 else self.graph[n][path[i+1]]['port']) for i, n in enumerate(path)])

    def path_cost(self, path):
        return sum(self.graph[a][b]['cost'] for a, b in zip(path, path[1:]))

    def send_rule(self, dp, priority, fields, actions, cookie, modify=False):
        p, o = dp.ofproto_parser, dp.ofproto
        dp.send_msg(p.OFPFlowMod(datapath=dp, cookie=cookie, priority=priority,
            command=o.OFPFC_MODIFY_STRICT if modify else o.OFPFC_ADD,
            match=p.OFPMatch(**fields), instructions=[
                p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)]))

    def prepare(self, key, route):
        src, dst = key.split('>')
        tag = route['tag'] = self.label()
        for entry in reversed(route['outputs'][1:]):
            dp = self.dp[entry['dpid']]
            p, o = dp.ofproto_parser, dp.ofproto
            actions = []
            if entry['dpid'] == route['path'][-1]:
                actions.append(p.OFPActionPopVlan())
            actions.append(p.OFPActionOutput(entry['output_port']))
            self.send_rule(dp, 200, dict(eth_type=0x0800, ipv4_src=src,
                ipv4_dst=dst, vlan_vid=o.OFPVID_PRESENT | tag), actions,
                VERSION_PREFIX | tag)

    def activate(self, key, route, initial):
        src, dst = key.split('>')
        entry = route['outputs'][0]
        dp = self.dp[entry['dpid']]
        p, o = dp.ofproto_parser, dp.ofproto
        actions = [p.OFPActionPushVlan(0x8100),
                   p.OFPActionSetField(vlan_vid=o.OFPVID_PRESENT | route['tag']),
                   p.OFPActionOutput(entry['output_port'])]
        for priority, kind in ((100, None), (110, 8), (109, 0)):
            fields = dict(in_port=self.hosts[src]['port'], vlan_vid=o.OFPVID_NONE,
                          eth_type=0x0800, ipv4_src=src, ipv4_dst=dst)
            if kind is not None:
                fields.update(ip_proto=1, icmpv4_type=kind)
            self.send_rule(dp, priority, fields, actions, baseline.ROUTE_COOKIE,
                           modify=not initial)

    def barriers(self):
        self.pending.clear()
        for dp in list(self.dp.values()):
            request = dp.ofproto_parser.OFPBarrierRequest(dp)
            dp.set_xid(request)
            self.pending.add((dp.id, request.xid))
            dp.send_msg(request)
        deadline = time.monotonic() + 5
        while self.pending and not self.failed and time.monotonic() < deadline:
            hub.sleep(.01)
        if self.pending or self.failed:
            raise RuntimeError('Route transaction barrier failed: '+str(sorted(self.pending)))

    def commit(self, changes, initial=False):
        for key, route in changes.items():
            self.prepare(key, route)
        self.barriers()
        self.record('route_prepare_confirmed', keys=sorted(changes))
        for key, route in changes.items():
            self.activate(key, route, initial)
        self.barriers()
        now = time.monotonic()
        self.route_generation += 1
        for key, route in changes.items():
            old = self.routes.get(key)
            if old:
                self.retired.append((now+5, old['tag']))
            self.routes[key] = route
            self.changed_at[key] = now
            self.record('route_committed', flow=key, old_path=old['path'] if old else None,
                new_path=route['path'], old_cost=self.path_cost(old['path']) if old else None,
                new_cost=route['cost'], tag=route['tag'], generation=self.route_generation)
            if key == '10.0.0.1>10.0.0.6':
                self.logger.warning('ROUTE h1->h6 %s -> %s cost=%.3f VLAN=%s (barriers confirmed)',
                    old['path'] if old else None, route['path'], route['cost'], route['tag'])

    def collect_old(self):
        now = time.monotonic()
        for deadline, tag in list(self.retired):
            if now < deadline:
                continue
            for dp in self.dp.values():
                p, o = dp.ofproto_parser, dp.ofproto
                dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE,
                    cookie=VERSION_PREFIX | tag, cookie_mask=0xffffffffffffffff,
                    out_port=o.OFPP_ANY, out_group=o.OFPG_ANY, match=p.OFPMatch()))
            self.barriers()
            self.used_tags.remove(tag)
            self.retired.remove((deadline, tag))
            self.record('old_version_removed', tag=tag)

    def cost_snapshot(self):
        snapshot = super().cost_snapshot()
        snapshot.update(rerouting=True, routing='Versioned downstream preparation and ingress switch',
                        scenario=self.case)
        return snapshot

    def monitor(self):
        while True:
            try:
                complete = set(self.dp) == set(range(1, 7)) and self.graph.number_of_edges() == 22
                signature = tuple(sorted((a, b, d['port']) for a, b, d in self.graph.edges(data=True)))
                if not self.failed and complete:
                    if not self.initialized:
                        self.signature = signature
                        changes = {src+'>'+dst: self.route(src, dst)
                                   for src in self.hosts for dst in self.hosts if src != dst}
                        self.commit(changes, initial=True)
                        self.initialized = self.ready = True
                        self.logger.warning('REROUTING READY: scenario=%s; 30 versioned routes; warmup >=8s', self.case)
                    elif signature != self.signature:
                        raise RuntimeError('Topology changed; stop traffic and restart this fixed-topology experiment')
                    snapshot = self.cost_snapshot()
                    if snapshot['ready']:
                        for a, b in self.graph.edges():
                            self.graph[a][b]['cost'] = snapshot['links'][str(a)+'>'+str(b)]['cost']
                        changes = {}
                        for key, old in self.routes.items():
                            old['cost'] = self.path_cost(old['path'])
                            src, dst = key.split('>')
                            if self.detector.sources[src]['blocked']:
                                continue
                            candidate = self.route(src, dst)
                            if (candidate['path'] != old['path'] and old['cost']-candidate['cost'] >= 1
                                    and time.monotonic()-self.changed_at[key] >= 3):
                                changes[key] = candidate
                        if changes:
                            self.commit(changes)
                    self.collect_old()
                elif self.initialized and not complete and not self.failed:
                    raise RuntimeError('Switch/link disappeared; restart experiment')
            except Exception as exc:
                self.failed, self.ready = True, False
                self.record('routing_failure', error=repr(exc))
                self.logger.exception('Routing transaction failed; inspect output and restart')
            snapshot = dict(time=time.time(), ready=self.ready, failed=self.failed,
                switches=sorted(self.dp), directed_links=self.graph.number_of_edges(),
                routes=self.routes, scenario=self.case, generation=self.route_generation,
                pending_retired_tags=[tag for _, tag in self.retired])
            temporary = self.out / 'state.tmp'
            temporary.write_text(json.dumps(snapshot, indent=2))
            temporary.replace(self.out / 'state.json')
            hub.sleep(.25)

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
                edge = {'A': '2>3', 'B': '2>6', 'C': '5>6'}[self.case]
                item = snapshot['links'][edge]
                self.logger.info('LINK %s rx_mbps=%.3f base=%.1f load=%.3f penalty=%.1f cost=%.3f',
                    edge, item['received_bps']/1e6, item['base'], item['load_term'], item['penalty'], item['cost'])
            hub.sleep(1)
