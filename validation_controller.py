"""CA2 environment acceptance prototype; not a finished coursework submission.

Uses known host addresses from the test fixture, LLDP-discovered switch links,
proxy ARP, per-source ingress statistics, EMA, source blocking and path updates.
ICMP echo replies are separated so a victim's replies are not classified as an
independent flood. Test-only commands explicitly label forced attack paths.
"""
import json
import os
import time
from pathlib import Path

import networkx as nx
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, arp, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event

ROUTE_COOKIE = 0xCA2001
DROP_COOKIE = 0xCA2002


class ValidationController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.config = json.loads(Path(os.environ['CEG_VALIDATION_CONFIG']).read_text())
        self.out = Path(self.config['output'])
        self.hosts = self.config['hosts']
        self.base = {tuple(sorted(edge['nodes'])): edge['cost'] for edge in self.config['edges']}
        self.dp = {}
        self.graph = nx.DiGraph()
        self.routes = {}
        self.last_flow = {}
        self.last_port = {}
        self.rates = {}
        self.ema = {}
        self.samples = {}
        self.blocked = set()
        self.penalties = {}
        self.forced = {}
        self.sequence = 0
        self.stage = 'startup'
        self.started = time.monotonic()
        self.worker = hub.spawn(self.monitor)

    def log(self, kind, **fields):
        record = dict(time=time.time(), elapsed=time.monotonic()-self.started,
                      stage=self.stage, event=kind)
        record.update(fields)
        with (self.out / 'controller-events.jsonl').open('a') as f:
            f.write(json.dumps(record, sort_keys=True)+'\n')

    def flow(self, dp, priority, fields, actions, cookie=ROUTE_COOKIE, delete=False):
        p, o = dp.ofproto_parser, dp.ofproto
        args = dict(datapath=dp, match=p.OFPMatch(**fields), cookie=cookie)
        if delete:
            args.update(command=o.OFPFC_DELETE, cookie_mask=0xffffffffffffffff,
                        out_port=o.OFPP_ANY, out_group=o.OFPG_ANY)
        else:
            args.update(priority=priority, instructions=[p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)])
        dp.send_msg(p.OFPFlowMod(**args))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        self.dp[dp.id] = dp
        self.graph.add_node(dp.id)
        self.flow(dp, 0, {}, [dp.ofproto_parser.OFPActionOutput(
            dp.ofproto.OFPP_CONTROLLER, dp.ofproto.OFPCML_NO_BUFFER)], cookie=0)
        self.log('switch_connected', dpid=dp.id)

    @set_ev_cls(event.EventLinkAdd)
    def link_add(self, ev):
        link = ev.link
        a, b = link.src.dpid, link.dst.dpid
        cost = self.base[tuple(sorted((a, b)))]
        self.graph.add_edge(a, b, port=link.src.port_no, base=cost, cost=cost)
        self.log('link_discovered', src=a, dst=b, port=link.src.port_no)

    @set_ev_cls(ofp_event.EventOFPErrorMsg, MAIN_DISPATCHER)
    def error(self, ev):
        self.log('openflow_error', dpid=ev.msg.datapath.id,
                 error_type=ev.msg.type, error_code=ev.msg.code)

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        msg, dp = ev.msg, ev.msg.datapath
        pkt = packet.Packet(msg.data)
        request = pkt.get_protocol(arp.arp)
        if request is None or request.opcode != arp.ARP_REQUEST:
            return
        target = self.hosts.get(request.dst_ip)
        if target is None:
            return
        response = packet.Packet()
        response.add_protocol(ethernet.ethernet(
            dst=request.src_mac, src=target['mac'], ethertype=ether_types.ETH_TYPE_ARP))
        response.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
            src_mac=target['mac'], src_ip=request.dst_ip,
            dst_mac=request.src_mac, dst_ip=request.src_ip))
        response.serialize()
        dp.send_msg(dp.ofproto_parser.OFPPacketOut(datapath=dp,
            buffer_id=dp.ofproto.OFP_NO_BUFFER, in_port=dp.ofproto.OFPP_CONTROLLER,
            actions=[dp.ofproto_parser.OFPActionOutput(msg.match['in_port'])],
            data=response.data))

    def paths(self):
        if len(self.graph.edges) != 22 or len(self.dp) != 6:
            return
        now = time.monotonic()
        for a, b, data in self.graph.edges(data=True):
            rate = max(self.rates.get((a, data['port']), 0),
                       self.rates.get((b, self.graph[b][a]['port']), 0))
            penalty = 60 if self.penalties.get(tuple(sorted((a, b))), 0) > now else 0
            data['cost'] = data['base'] + 5*min(rate/40e6, 1) + penalty
        for src, source in self.hosts.items():
            for dst, dest in self.hosts.items():
                if src == dst:
                    continue
                key = (src, dst)
                path = self.forced.get(key) or nx.shortest_path(
                    self.graph, source['switch'], dest['switch'], weight='cost')
                old = self.routes.get(key)
                if old == path:
                    continue
                # Install downstream first; delete only obsolete routing entries.
                # A final submission should additionally use barrier acknowledgements.
                for index in reversed(range(len(path))):
                    dpid = path[index]
                    port = dest['port'] if index == len(path)-1 else self.graph[dpid][path[index+1]]['port']
                    dp = self.dp[dpid]
                    fields = dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst)
                    actions = [dp.ofproto_parser.OFPActionOutput(port)]
                    self.flow(dp, 100, fields, actions)
                    for priority, icmp_type in ((110, 8), (109, 0)):
                        self.flow(dp, priority, dict(fields, ip_proto=1, icmpv4_type=icmp_type), actions)
                for dpid in set(old or [])-set(path):
                    self.flow(self.dp[dpid], 0, dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst), [], delete=True)
                self.routes[key] = list(path)
                self.log('route', src=src, dst=dst, before=old, after=path,
                         forced=key in self.forced)

    @set_ev_cls(ofp_event.EventOFPPortStatsReply, MAIN_DISPATCHER)
    def port_stats(self, ev):
        now = time.monotonic()
        for stat in ev.msg.body:
            key = (ev.msg.datapath.id, stat.port_no)
            old = self.last_port.get(key)
            if old and stat.tx_bytes >= old[0]:
                self.rates[key] = 8*(stat.tx_bytes-old[0])/(now-old[1])
            self.last_port[key] = (stat.tx_bytes, now)

    @set_ev_cls(ofp_event.EventOFPFlowStatsReply, MAIN_DISPATCHER)
    def flow_stats(self, ev):
        dpid, now = ev.msg.datapath.id, time.monotonic()
        totals = {}
        destinations = {}
        for stat in ev.msg.body:
            src, dst = stat.match.get('ipv4_src'), stat.match.get('ipv4_dst')
            if stat.cookie != ROUTE_COOKIE or stat.priority not in (100, 110):
                continue
            if src not in self.hosts or self.hosts[src]['switch'] != dpid:
                continue
            key = (dpid, stat.priority, src, dst)
            old = self.last_flow.get(key)
            self.last_flow[key] = (stat.packet_count, now)
            if old and stat.packet_count >= old[0]:
                rate = (stat.packet_count-old[0])/(now-old[1])
                totals[src] = totals.get(src, 0)+rate
                if rate > destinations.get(src, (0, None))[0]:
                    destinations[src] = (rate, dst)
        for src, rate in totals.items():
            baseline = self.ema.get(src, rate)
            n = self.samples.get(src, 0)
            if n >= 4 and rate > max(50, 3*baseline) and src not in self.blocked:
                dst = destinations[src][1]
                path = self.routes[(src, dst)]
                self.blocked.add(src)
                for a, b in zip(path, path[1:]):
                    self.penalties[tuple(sorted((a, b)))] = now+8
                for dp in self.dp.values():
                    self.flow(dp, 5000, dict(eth_type=0x0800, ipv4_src=src), [], cookie=DROP_COOKIE)
                self.log('block', src=src, dst=dst, pps=rate, baseline_pps=baseline,
                         attack_path=path)
            elif src not in self.blocked:
                self.ema[src] = 0.3*rate+0.7*baseline
            self.samples[src] = n+1
            self.log('source_rate', src=src, pps=rate, baseline_pps=baseline)

    def commands(self):
        path = self.out/'command.json'
        if not path.exists():
            return
        cmd = json.loads(path.read_text())
        if cmd['sequence'] <= self.sequence:
            return
        self.sequence = cmd['sequence']
        self.stage = cmd['stage']
        if cmd.get('reset'):
            for dp in self.dp.values():
                self.flow(dp, 0, {}, [], cookie=DROP_COOKIE, delete=True)
            self.blocked.clear()
            self.penalties.clear()
            self.ema.clear()
            self.samples.clear()
            self.last_flow.clear()
            self.forced = {}
        if cmd.get('clear_forced_path'):
            self.forced = {}
        if cmd.get('force_attack_path'):
            self.forced[(cmd['src'], cmd['dst'])] = cmd['force_attack_path']
        self.log('command', **cmd)

    def snapshot(self):
        state = dict(time=time.time(), stage=self.stage, sequence=self.sequence,
                     switches=sorted(self.dp), directed_links=len(self.graph.edges),
                     blocked=sorted(self.blocked),
                     routes={a+'>'+b:p for (a,b),p in self.routes.items()},
                     costs={str(a)+'-'+str(b):d['cost'] for a,b,d in self.graph.edges(data=True)},
                     baselines=self.ema, samples=self.samples)
        temporary = self.out/'state.tmp'
        temporary.write_text(json.dumps(state, indent=2))
        temporary.replace(self.out/'state.json')
        self.log('snapshot', **state)

    def monitor(self):
        while True:
            try:
                self.commands()
                self.paths()
                for dp in list(self.dp.values()):
                    p, o = dp.ofproto_parser, dp.ofproto
                    dp.send_msg(p.OFPFlowStatsRequest(dp))
                    dp.send_msg(p.OFPPortStatsRequest(dp, 0, o.OFPP_ANY))
                self.snapshot()
            except Exception:
                self.logger.exception('Validation monitor failed')
                self.log('monitor_exception')
            hub.sleep(1)
