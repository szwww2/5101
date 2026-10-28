import tempfile
from pathlib import Path
import unittest
from task4_evidence import controller_log_check


class ControllerLogTests(unittest.TestCase):
    def test_external_terminal_does_not_require_redirected_file(self):
        with tempfile.TemporaryDirectory() as directory:
            self.assertIn('External controller', controller_log_check(directory))

    def test_owned_controller_missing_log_is_an_error(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(FileNotFoundError):
                controller_log_check(directory, required=True)

    def test_existing_log_is_checked_in_both_modes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ryu.log'
            path.write_text('REROUTING READY\n')
            for required in (False, True):
                self.assertIn('checked', controller_log_check(directory, required))
                path.write_text('Traceback (most recent call last):\n')
                with self.assertRaises(AssertionError):
                    controller_log_check(directory, required)
                path.write_text('REROUTING READY\n')


if __name__ == '__main__':
    unittest.main()
