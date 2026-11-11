import unittest
from pathlib import Path
from metagraph.emitter import emit_fortran
from metagraph.api_validation import validate_source

ROOT=Path(__file__).parents[1]
DB=ROOT/'data/devito.sqlite'
ALLOWED=ROOT/'data/devito.allowed_names'
class EmitterCases(unittest.TestCase):
    @unittest.skipUnless(DB.is_file() and ALLOWED.is_file(),'index Devito before emitter integration test')
    def test_templates_are_index_checked_and_cite_repository_idiom(self):
        samples={'heat1d.f90':'heat_1d','heat2d.f90':'heat_2d','wave1d.f90':'wave_1d',
                 'advection1d.f90':'upwind_advection','poisson2d.f90':'jacobi_poisson'}
        names=set(ALLOWED.read_text().splitlines())
        for filename,pattern in samples.items():
            with self.subTest(filename=filename):
                result=emit_fortran(ROOT/'fortran_samples'/filename,DB,names)
                self.assertEqual(result['pattern'],pattern)
                self.assertTrue(result['idiom_source'].endswith('.py'))
                self.assertIn(result['idiom_source'],result['code'])
                self.assertEqual(validate_source(result['code'],names),[])
                compile(result['code'],filename,'exec')
if __name__=='__main__':unittest.main()
