from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).parents[1]/'benchmarks'))
import bench

class ProcessRunnerTests(unittest.TestCase):
    def test_collects_success_and_failure_without_timeout(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env=bench.environment(root)
            ok=bench.run([sys.executable,'-c','print("complete")'],root,env,2)
            self.assertEqual(0,ok['exit'])
            self.assertEqual('complete\n',ok['stdout'])
            self.assertFalse(ok['timeout'])
            fail=bench.run([sys.executable,'-c','import sys;sys.stderr.write("failed");sys.exit(7)'],root,env,2)
            self.assertEqual(7,fail['exit'])
            self.assertEqual('failed',fail['stderr'])
            self.assertFalse(fail['timeout'])

    def test_watchdog_kills_a_hung_process(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);env=bench.environment(root)
            result=bench.run([sys.executable,'-c','import time;time.sleep(10)'],root,env,.2)
            self.assertTrue(result['timeout'])
            self.assertLess(result['exit'],0)
            self.assertLess(result['seconds'],3)
