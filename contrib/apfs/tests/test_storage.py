from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[1]/'benchmarks'))
import storage


def containers(free):
    return {'Containers':[{'ContainerReference':'private-disk','CapacityCeiling':10000,'CapacityFree':free},
                          {'ContainerReference':'unrelated-disk','CapacityCeiling':90000,'CapacityFree':0}]}


class StorageMeasurementTests(unittest.TestCase):
    def test_counts_only_the_private_container_and_waits_for_stability(self):
        with patch.object(storage,'plist',side_effect=[containers(8000),containers(7000),containers(7000),containers(7000)]), patch.object(storage.os,'sync'), patch.object(storage.time,'sleep'):
            result=storage.allocation('private-disk')
        self.assertEqual(3000,result['allocated_bytes'])
        self.assertTrue(result['stable'])
        self.assertEqual([2000,3000,3000,3000],result['samples'])

    def test_unstable_readings_are_reported_instead_of_claiming_precision(self):
        with patch.object(storage,'plist',side_effect=[containers(i) for i in range(15)]), patch.object(storage.os,'sync'), patch.object(storage.time,'sleep'):
            result=storage.allocation('private-disk')
        self.assertFalse(result['stable'])
        self.assertEqual(15,len(result['samples']))

    def test_missing_container_is_an_error(self):
        with patch.object(storage,'plist',return_value=containers(8000)), patch.object(storage.os,'sync'):
            with self.assertRaisesRegex(RuntimeError,'disappeared'):
                storage.allocation('missing-disk')

if __name__=='__main__':
    unittest.main()
