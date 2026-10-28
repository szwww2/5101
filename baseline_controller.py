"""TODO2: six-switch shortest-path baseline, before anomaly handling.

Uses the fixed host IP/MAC/attachment inventory from the saved lab topology.
LLDP discovers switch links and ports. Proxy ARP avoids flooding mesh loops.
Teacher resilient_controller.py supplies the routing design reference; this
separate implementation leaves teacher originals and acceptance code unchanged.
"""
import json
import os
import time
from pathlib import Path

import networkx as nx
from ryu.base import app_manager
from ryu.controller import ofp_event
from ryu.controller.handler import CONFIG_DISPATCHER, MAIN_DISPATCHER, DEAD_DISPATCHER, set_ev_cls
from ryu.lib import hub
from ryu.lib.packet import packet, ethernet, arp, ether_types
from ryu.ofproto import ofproto_v1_3
from ryu.topology import event

ROUTE_COOKIE = 0xCA220001


class BaselineController(app_manager.RyuApp):
    OFP_VERSIONS = [ofproto_v1_3.OFP_VERSION]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        root = Path(__file__).resolve().parent
        config = json.loads((root / 'todo01/mesh-check-template.json').read_text())
        self.hosts = config['hosts']
        self.costs = {tuple(sorted(e['nodes'])): e['cost'] for e in config['edges']}
        self.out = Path(os.environ['CEG_BASELINE_OUTPUT'])
        self.out.mkdir(parents=True, exist_ok=True)
        self.dp = {}
        self.graph = nx.DiGraph()
        self.routes = {}
        self.signature = None
        self.pending = set()
        self.ready = False
        self.failed = False
        self.deadline = 0
        self.worker = hub.spawn(self.monitor)

    def record(self, kind, **values):
        with (self.out / 'events.jsonl').open('a') as f:
            f.write(json.dumps(dict(time=time.time(), event=kind, **values)) + '\n')

    def delete_routes(self, dp):
        o, p = dp.ofproto, dp.ofproto_parser
        dp.send_msg(p.OFPFlowMod(datapath=dp, command=o.OFPFC_DELETE,
            cookie=ROUTE_COOKIE, cookie_mask=0xffffffffffffffff,
            out_port=o.OFPP_ANY, out_group=o.OFPG_ANY, match=p.OFPMatch()))

    def add_flow(self, dp, priority, fields, port, cookie=ROUTE_COOKIE):
        o, p = dp.ofproto, dp.ofproto_parser
        actions = [p.OFPActionOutput(port, o.OFPCML_NO_BUFFER)]
        dp.send_msg(p.OFPFlowMod(datapath=dp, cookie=cookie, priority=priority,
            match=p.OFPMatch(**fields), instructions=[
                p.OFPInstructionActions(o.OFPIT_APPLY_ACTIONS, actions)]))

    @set_ev_cls(ofp_event.EventOFPSwitchFeatures, CONFIG_DISPATCHER)
    def features(self, ev):
        dp = ev.msg.datapath
        self.dp[dp.id] = dp
        self.graph.add_node(dp.id)
        self.signature = None
        self.ready = False
        self.delete_routes(dp)
        self.add_flow(dp, 0, {}, dp.ofproto.OFPP_CONTROLLER, cookie=0)
        self.record('switch_connected', dpid=dp.id)

    @set_ev_cls(ofp_event.EventOFPStateChange, DEAD_DISPATCHER)
    def disconnected(self, ev):
        if self.dp.get(ev.datapath.id) is not ev.datapath:
            return
        self.dp.pop(ev.datapath.id, None)
        if ev.datapath.id in self.graph:
            self.graph.remove_node(ev.datapath.id)
        self.signature = None
        self.ready = False

    @set_ev_cls(event.EventLinkAdd)
    def link_add(self, ev):
        link = ev.link
        a, b = link.src.dpid, link.dst.dpid
        cost = self.costs.get(tuple(sorted((a, b))))
        if cost is None:
            self.record('unexpected_link', src=a, dst=b)
            return
        self.graph.add_edge(a, b, port=link.src.port_no, cost=cost)

    @set_ev_cls(event.EventLinkDelete)
    def link_delete(self, ev):
        a, b = ev.link.src.dpid, ev.link.dst.dpid
        if self.graph.has_edge(a, b):
            self.graph.remove_edge(a, b)
        self.ready = False

    @set_ev_cls(ofp_event.EventOFPBarrierReply, MAIN_DISPATCHER)
    def barrier_reply(self, ev):
        self.pending.discard((ev.msg.datapath.id, ev.msg.xid))

    @set_ev_cls(ofp_event.EventOFPErrorMsg, [CONFIG_DISPATCHER, MAIN_DISPATCHER])
    def error(self, ev):
        self.failed = True
        self.ready = False
        self.record('openflow_error', dpid=ev.msg.datapath.id,
                    error_type=ev.msg.type, error_code=ev.msg.code)
        self.logger.error('OpenFlow error; inspect events.jsonl and restart baseline')

    @set_ev_cls(ofp_event.EventOFPPacketIn, MAIN_DISPATCHER)
    def packet_in(self, ev):
        if not self.ready:
            return
        dp, msg = ev.msg.datapath, ev.msg
        request = packet.Packet(msg.data).get_protocol(arp.arp)
        if request is None or request.opcode != arp.ARP_REQUEST:
            return
        source, target = self.hosts.get(request.src_ip), self.hosts.get(request.dst_ip)
        if source is None or target is None:
            return
        if (dp.id, msg.match['in_port'], request.src_mac) != (
                source['switch'], source['port'], source['mac']):
            return
        response = packet.Packet()
        response.add_protocol(ethernet.ethernet(dst=request.src_mac,
            src=target['mac'], ethertype=ether_types.ETH_TYPE_ARP))
        response.add_protocol(arp.arp(opcode=arp.ARP_REPLY,
            src_mac=target['mac'], src_ip=request.dst_ip,
            dst_mac=request.src_mac, dst_ip=request.src_ip))
        response.serialize()
        dp.send_msg(dp.ofproto_parser.OFPPacketOut(datapath=dp,
            buffer_id=dp.ofproto.OFP_NO_BUFFER, in_port=dp.ofproto.OFPP_CONTROLLER,
            actions=[dp.ofproto_parser.OFPActionOutput(msg.match['in_port'])],
            data=response.data))

    def install(self):
        self.ready = False
        self.pending.clear()
        self.routes = {}
        for dp in self.dp.values():
            self.delete_routes(dp)
        for src, source in self.hosts.items():
            for dst, target in self.hosts.items():
                if src == dst:
                    continue
                path = nx.shortest_path(self.graph, source['switch'],
                                        target['switch'], weight='cost', method='dijkstra')
                outputs = []
                for index, dpid in enumerate(path):
                    port = target['port'] if index == len(path)-1 else self.graph[dpid][path[index+1]]['port']
                    outputs.append(dict(dpid=dpid, output_port=port))
                for entry in reversed(outputs):
                    self.add_flow(self.dp[entry['dpid']], 100,
                        dict(eth_type=0x0800, ipv4_src=src, ipv4_dst=dst), entry['output_port'])
                self.routes[src + '>' + dst] = dict(path=path, outputs=outputs,
                    cost=sum(self.graph[a][b]['cost'] for a, b in zip(path, path[1:])))
        for dp in self.dp.values():
            request = dp.ofproto_parser.OFPBarrierRequest(dp)
            dp.set_xid(request)
            self.pending.add((dp.id, request.xid))
            dp.send_msg(request)
        self.deadline = time.monotonic() + 10

    def monitor(self):
        while True:
            if not self.failed:
                complete = set(self.dp) == set(range(1, 7)) and self.graph.number_of_edges() == 22
                signature = tuple(sorted((a, b, d['port']) for a, b, d in self.graph.edges(data=True)))
                if complete and signature != self.signature:
                    self.signature = signature
                    self.install()
                elif not complete and self.routes:
                    for dp in self.dp.values():
                        self.delete_routes(dp)
                    self.routes.clear()
                    self.pending.clear()
                    self.signature = None
                    self.ready = False
                if complete and self.routes and not self.pending and not self.ready:
                    self.ready = True
                    route = self.routes['10.0.0.1>10.0.0.6']
                    self.record('ready', **route)
                    self.logger.info('BASELINE READY: 6 switches, 22 directed links, 30 routes; h1->h6 %s cost=%s', route['path'], route['cost'])
                if self.pending and time.monotonic() > self.deadline:
                    self.failed = True
                    self.ready = False
                    self.record('barrier_timeout')
            snapshot = dict(time=time.time(), ready=self.ready, failed=self.failed,
                switches=sorted(self.dp), directed_links=self.graph.number_of_edges(),
                links=[dict(src=a, dst=b, **d) for a, b, d in self.graph.edges(data=True)],
                routes=self.routes, host_assumption='Fixed IP/MAC and switch port inventory; proxy ARP')
            temporary = self.out / 'state.tmp'
            temporary.write_text(json.dumps(snapshot, indent=2))
            temporary.replace(self.out / 'state.json')
            hub.sleep(.25)
