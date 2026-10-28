"""Regression checks for reference-code pitfalls: identities, units, EMA order."""
from types import SimpleNamespace
import unittest

from traffic_stats import FlowRates, SourceEMA


def entry(dst, packets, duration=10, priority=100):
    return SimpleNamespace(table_id=0, priority=priority, cookie=1,
        match=dict(eth_type=0x0800, ipv4_src='10.0.0.1', ipv4_dst=dst),
        packet_count=packets, byte_count=packets*100,
        duration_sec=duration, duration_nsec=0)


class TrafficTests(unittest.TestCase):
    def test_same_source_two_flows_and_actual_elapsed_time(self):
        rates = FlowRates()
        self.assertIsNone(rates.sample(1, entry('10.0.0.2', 100), 10))
        self.assertIsNone(rates.sample(1, entry('10.0.0.3', 900), 10))
        a = rates.sample(1, entry('10.0.0.2', 130, 12), 12)
        b = rates.sample(1, entry('10.0.0.3', 910, 12), 12)
        self.assertEqual(a['pps']+b['pps'], 20)
        self.assertEqual(a['bps']+b['bps'], 16000)

    def test_rule_reinstallation_resets_even_when_count_grows(self):
        rates = FlowRates()
        rates.sample(1, entry('10.0.0.2', 100, 50), 10)
        self.assertIsNone(rates.sample(1, entry('10.0.0.2', 1000, 1), 11))
        self.assertIsNone(rates.sample(1, entry('10.0.0.2', 5, 2), 12))

    def test_full_identity_separates_priority_table_cookie_and_switch(self):
        rates = FlowRates()
        one = entry('10.0.0.2', 100)
        other_cookie, other_table = entry('10.0.0.2', 100), entry('10.0.0.2', 100)
        other_cookie.cookie = 2
        other_table.table_id = 1
        variants = [(1, one), (2, one), (1, entry('10.0.0.2', 900, priority=110)),
                    (1, other_cookie), (1, other_table)]
        for dpid, stat in variants:
            self.assertIsNone(rates.sample(dpid, stat, 10))
        self.assertEqual(len(rates.previous), 5)

    def test_compare_with_old_ema_and_freeze_attack_sample(self):
        detector = SourceEMA(['x'], floor_pps=0)
        for _ in range(15):
            detector.observe('x', 100)
        old = detector.sources['x']['ema_pps']
        decision = detector.observe('x', 400)
        self.assertTrue(decision['newly_blocked'])
        self.assertEqual(decision['new_ema_pps'], old)
        self.assertFalse(detector.observe('x', 1000)['newly_blocked'])
        self.assertEqual(detector.sources['x']['ema_pps'], old)

    def test_zero_baseline_and_legitimate_10mbps_load(self):
        detector = SourceEMA(['x'])
        for _ in range(8):
            self.assertFalse(detector.observe('x', 0)['blocked'])
        for _ in range(10):
            self.assertFalse(detector.observe('x', 850)['blocked'])
        self.assertTrue(detector.observe('x', 10000)['newly_blocked'])


if __name__ == '__main__':
    unittest.main()
