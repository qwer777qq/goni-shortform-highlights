from pathlib import Path
import sys
import tempfile
import threading
import time
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import core
from reel_direct import Engine


class DirectJobs(unittest.TestCase):
    def setUp(self):
        self.old_data = core.DATA
        self.temp = tempfile.TemporaryDirectory()
        self.engine = Engine(self.temp.name)

    def tearDown(self):
        self.engine.close()
        core.DATA = self.old_data
        self.temp.cleanup()

    def wait(self, job):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            state = self.engine.job_status(job['id'])
            if state['status'] in ('done', 'error'):
                return state
            time.sleep(.01)
        self.fail('job did not complete')

    def test_running_project_is_guarded_and_status_is_copy(self):
        release = threading.Event()
        try:
            job = self.engine.start('render', lambda progress: release.wait(5), 'a' * 32)
            with self.assertRaises(ValueError):
                self.engine.start('render', lambda progress: None, 'a' * 32)
            with self.assertRaises(ValueError):
                self.engine.save('a' * 32, {})
            state = self.engine.job_status(job['id'])
            state['status'] = 'done'
            self.assertNotEqual(self.engine.job_status(job['id'])['status'], 'done')
        finally:
            release.set()
        self.assertEqual(self.wait(job)['status'], 'done')

    def test_failure_does_not_report_success_or_block_later_job(self):
        def fail(progress):
            raise ValueError('test media failure')
        failed = self.wait(self.engine.start('render', fail, 'b' * 32))
        self.assertEqual(failed['status'], 'error')
        self.assertNotIn('result', failed)
        self.assertEqual(self.wait(self.engine.start('render', lambda p: 42, 'b' * 32))['result'], 42)
        with self.assertRaises(ValueError):
            self.engine.job_status('c' * 32)


if __name__ == '__main__':
    unittest.main()
