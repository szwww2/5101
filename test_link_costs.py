from types import SimpleNamespace
import unittest

from link_costs import LinkCosts, PortRates


class LinkCostTests(unittest.TestCase):
    def test_actual_time_and_bit_units(self):
        tracker = PortRates()
        a = SimpleNamespace(port_no=4, duration_sec=10, duration_nsec=0,
                            rx_bytes=0, tx_bytes=100)
        b = SimpleNamespace(port_no=4, duration_sec=12, duration_nsec=0,
                            rx_bytes=2500000, tx_bytes=1000100)
        self.assertIsNone(tracker.sample(6, a, 5))
        value = tracker.sample(6, b, 7)
        self.assertEqual(value['rx_bps'], 10000000)
        self.assertEqual(value['tx_bps'], 4000000)

    def test_port_reinstallation_resets(self):
        tracker = PortRates()
        old = SimpleNamespace(port_no=1, duration_sec=20, duration_nsec=0,
                              rx_bytes=10, tx_bytes=20)
        new = SimpleNamespace(port_no=1, duration_sec=1, duration_nsec=0,
                              rx_bytes=100, tx_bytes=200)
        tracker.sample(1, old, 1)
        self.assertIsNone(tracker.sample(1, new, 2))

    def test_load_and_directional_penalty(self):
        model = LinkCosts()
        self.assertEqual(model.cost(2, 6, 14, 10000000, 0)['cost'], 15.25)
        model.detected('h2', [2, 6], 0)
        self.assertEqual(model.cost(2, 6, 14, 10000000, 1)['cost'], 75.25)
        self.assertEqual(model.cost(6, 2, 14, 0, 1)['penalty'], 0)

    def test_forward_load_zero_does_not_mean_attack_stopped(self):
        model = LinkCosts()
        model.detected('h2', [2, 6], 0)
        model.dropped_activity('h2', 20)
        self.assertEqual(model.expire(24), [])
        self.assertEqual(model.cost(2, 6, 14, 0, 24)['penalty'], 60)
        self.assertEqual(model.expire(25), ['h2'])
        self.assertEqual(model.cost(2, 6, 14, 0, 25)['penalty'], 0)

    def test_minimum_hold_and_reactivation(self):
        model = LinkCosts()
        model.detected('h2', [2, 6], 0)
        self.assertEqual(model.expire(7), [])
        self.assertEqual(model.expire(8), ['h2'])
        self.assertTrue(model.dropped_activity('h2', 10))
        self.assertEqual(model.expire(17), [])
        self.assertEqual(model.expire(18), ['h2'])


if __name__ == '__main__':
    unittest.main()
