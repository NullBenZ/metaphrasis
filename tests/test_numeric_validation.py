import unittest
import numpy as np
from metagraph.validate_numeric import compare_arrays
class NumericValidationCases(unittest.TestCase):
    def test_allclose_and_shape_mismatch(self):
        good=compare_arrays(np.array([1.,2.]),np.array([1.,2.00000001]),1e-6,1e-6)
        self.assertTrue(good['passed']);self.assertEqual(good['elements'],2)
        bad=compare_arrays(np.array([1.,2.]),np.array([[1.,2.]]),1e-6,1e-6)
        self.assertFalse(bad['passed']);self.assertIn('shape',bad)
if __name__=='__main__':unittest.main()

class NumericIntegrationCases(unittest.TestCase):
    def test_all_five_samples_against_generated_devito(self):
        import importlib.util, os, shutil, tempfile
        from pathlib import Path
        from metagraph.emitter import emit_fortran
        from metagraph.validate_numeric import validate
        from metagraph.api_validation import validate_source
        root=Path(__file__).parents[1];db=root/'data/devito.sqlite';allow=root/'data/devito.allowed_names'
        if not db.is_file() or not allow.is_file() or not shutil.which('gfortran') or not importlib.util.find_spec('devito'):
            self.skipTest('requires indexed Devito, gfortran, and Devito import path')
        names=set(allow.read_text().splitlines())
        for filename in ['heat1d.f90','heat2d.f90','wave1d.f90','advection1d.f90','poisson2d.f90']:
            with self.subTest(filename=filename),tempfile.TemporaryDirectory() as td:
                script=Path(td)/'generated.py'
                emitted=emit_fortran(root/'fortran_samples'/filename,db,names)
                script.write_text(emitted['code'])
                self.assertEqual(validate_source(emitted['code'],names),[])
                result=validate(root/'fortran_samples'/filename,script,atol=2e-6,rtol=2e-6)
                self.assertTrue(result['passed'],result)
