import unittest

from bench.real_devito_benchmarks import community_statistics, fitted_slope, machine_info


class RealBenchmarkHelpers(unittest.TestCase):
    def test_community_distribution_and_non_singleton_fraction(self):
        result=community_statistics([0,0,1,2,2,2,3])
        self.assertEqual(result['communities'],4)
        self.assertEqual(result['size_distribution'],'1:2;2:1;3:1')
        self.assertAlmostEqual(result['fraction_nodes_non_singleton'],5/7)

    def test_log_log_slope_hand_check(self):
        self.assertAlmostEqual(fitted_slope([1,2,4],[3,12,48]),2.0)
        self.assertAlmostEqual(fitted_slope([1,2],[4,4]),0.0)
        self.assertIsNone(fitted_slope([1],[2]))

    def test_machine_report_has_cpu_and_memory_fields(self):
        info=machine_info()
        self.assertGreater(info['logical_cpus'],0)
        self.assertGreater(info['physical_cores'],0)
        self.assertGreater(info['memory_bytes'],0)
        self.assertTrue(info['processor'])


if __name__=='__main__':unittest.main()
