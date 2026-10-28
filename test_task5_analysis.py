import unittest
from analyze_task5 import load_trial, loss_percent, path_cost


class MetricTests(unittest.TestCase):
    def test_transient_loss_is_not_whole_run_loss(self):
        self.assertAlmostEqual(loss_percent(43, 848), 5.070754716981132)
        self.assertAlmostEqual(loss_percent(43, 51024), .08427406710567575)

    def test_zero_datagrams_is_missing_not_zero_loss(self):
        with self.assertRaises(ValueError):
            loss_percent(0, 0)

    def test_route_cost_uses_each_directed_edge(self):
        links = {'1>2': {'cost': 6}, '2>6': {'cost': 74}, '2>3': {'cost': 11}, '3>6': {'cost': 8}}
        self.assertEqual(path_cost(links, [1, 2, 6]), 80)
        self.assertEqual(path_cost(links, [1, 2, 3, 6]), 25)

    def test_original_failed_b_is_usable_only_with_verified_saved_evidence(self):
        trial = load_trial('B')
        self.assertIn('estimated', trial['clock_quality'])
        self.assertEqual(len(trial['receiver']), 60)
        peak = max(trial['receiver'], key=lambda row: row['loss_percent'])
        self.assertEqual((peak['start'], peak['end'], peak['lost'], peak['total']), (12, 13, 43, 848))

    def test_tiny_ack_sessions_do_not_pollute_a_or_c(self):
        for case in ('A', 'C'):
            trial = load_trial(case)
            self.assertEqual(len(trial['receiver']), 60)
            self.assertEqual(trial['metrics']['lost'], 0)
            self.assertEqual(trial['clock_quality'], 'sender-launch timestamp')

    def test_repeat_override_uses_new_measured_run(self):
        trial = load_trial('B', folder_override='run-B-20261017-105957-DfB6RZ')
        self.assertEqual(trial['clock_quality'], 'sender-launch timestamp')
        self.assertEqual(trial['metrics']['lost'], 78)
        self.assertEqual([r['lost'] for r in trial['receiver'] if r['lost']], [51, 27])


if __name__ == '__main__':
    unittest.main()
