from pathlib import Path
import tempfile
import unittest
from metagraph.fortran_analysis import analyze_fortran

ROOT=Path(__file__).parents[1]/'fortran_samples'
class FortranPatternCases(unittest.TestCase):
    def test_five_supported_stencil_families(self):
        expected={'heat1d.f90':'heat_1d','heat2d.f90':'heat_2d','wave1d.f90':'wave_1d',
                  'advection1d.f90':'upwind_advection','poisson2d.f90':'jacobi_poisson'}
        for filename,pattern in expected.items():
            with self.subTest(filename=filename):
                result=analyze_fortran(ROOT/filename)
                self.assertEqual(result['status'],'supported',result)
                self.assertEqual(result['pattern'],pattern)
                self.assertTrue(result['stencil_offsets'])
                self.assertTrue(result['scalar_values'])
                self.assertTrue(result['array_bounds'])
                self.assertTrue(result['array_initializers'])
                self.assertTrue(result['boundary_assignments'])
    def test_unsupported_and_parse_errors_are_explained(self):
        result=analyze_fortran(ROOT/'unsupported.f90')
        self.assertEqual(result['status'],'unsupported')
        self.assertTrue(result['line'])
        self.assertIn('reason',result)
        nonlinear=analyze_fortran(ROOT/'unsupported_function.f90')
        self.assertEqual(nonlinear['status'],'unsupported')
        self.assertIn('expression tree',nonlinear['reason'])
        altered=ROOT/'heat1d.f90'
        altered_source=altered.read_text().replace('2.0*u(i)','3.0*u(i)')
        with tempfile.TemporaryDirectory() as td:
            changed=Path(td)/'wrong_center.f90';changed.write_text(altered_source)
            coefficient=analyze_fortran(changed)
            self.assertEqual(coefficient['status'],'unsupported')
            self.assertIn('expression tree',coefficient['reason'])
if __name__=='__main__':unittest.main()
