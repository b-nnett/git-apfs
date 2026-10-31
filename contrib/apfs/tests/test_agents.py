from pathlib import Path
import argparse
import os
import sys
import tempfile
import unittest
sys.path.insert(0,str(Path(__file__).parents[1]/'benchmarks'))
import bench
import agents
ROOT=Path(__file__).parents[1]
BASE=Path(os.environ.get('GIT_APFS_BASELINE',ROOT/'benchmark-results/git-baseline/bin/git')).resolve()
FORK=Path(os.environ.get('GIT_APFS_BINARY',ROOT/'benchmark-results/git-apfs/bin/git')).resolve()

class AgentBenchmarkTests(unittest.TestCase):
    def test_percentiles_include_endpoints_and_interpolation(self):
        self.assertEqual(1,agents.percentile([3,1,2],0))
        self.assertEqual(3,agents.percentile([3,1,2],1))
        self.assertEqual(2.9,agents.percentile([1,2,3],.95))
        self.assertIsNone(agents.percentile([],.5))

    @unittest.skipUnless(BASE.is_file() and FORK.is_file(),'build matched Git binaries')
    def test_real_repository_concurrent_loop_preserves_source_and_records_resources(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);seed=root/'seed';seed.mkdir();env=bench.environment(seed)
            env['PATH']=str(BASE.parent)+os.pathsep+env['PATH']
            source,base,_=bench.fixture(seed,env,20,file_bytes=128)
            before=bench.snapshot(source)
            scratch=root/'trial';scratch.mkdir()
            args=argparse.Namespace(source=source,ref=base,baseline=BASE,candidate=FORK,timeout=30,
                edits=2,cycles=1,cache_bytes=16384,assert_clones=True,profile=False)
            result=agents.trial(scratch,args,'apfs',2,0)
            self.assertEqual('pass',result['outcome'],result['errors'])
            self.assertEqual(before,bench.snapshot(source))
            self.assertEqual(2,len(result['agents_results']))
            self.assertGreater(result['total_workflow_wall_seconds'],result['wall_seconds'])
            for row in result['agents_results']:
                self.assertFalse(row['errors'])
                self.assertTrue(all(c['max_rss_bytes'] is not None for c in row['commands']))
            self.assertFalse((scratch/'agent-0').exists())
            self.assertEqual(0,result['lease_balance'])

    @unittest.skipUnless(BASE.is_file() and FORK.is_file(),'build matched Git binaries')
    def test_cache_with_fsmonitor_configuration_preserves_concurrent_edits(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);seed=root/'seed';seed.mkdir();env=bench.environment(seed)
            env['PATH']=str(BASE.parent)+os.pathsep+env['PATH']
            source,base,_=bench.fixture(seed,env,64,file_bytes=128)
            scratch=root/'trial';scratch.mkdir()
            args=argparse.Namespace(source=source,ref=base,baseline=BASE,candidate=FORK,timeout=90,
                edits=16,cycles=2,cache_bytes=1024*1024,assert_clones=True,profile=False)
            result=agents.trial(scratch,args,'apfs-cache-tuned',8,0)
            self.assertEqual('pass',result['outcome'],result['errors'])
            self.assertEqual(0,result['lease_balance'])
