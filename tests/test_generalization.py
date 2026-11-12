import tempfile
import unittest
import re
from pathlib import Path

from metagraph.fortran_analysis import analyze_fortran

ROOT=Path(__file__).parents[1]
SAMPLES={"heat1d.f90":"heat_1d","heat2d.f90":"heat_2d","wave1d.f90":"wave_1d",
         "advection1d.f90":"upwind_advection","poisson2d.f90":"jacobi_poisson"}


class GeneralizationCases(unittest.TestCase):
    def test_variants_keep_pattern_under_casing_comments_and_layout(self):
        for filename,pattern in SAMPLES.items():
            source=(ROOT/'fortran_samples'/filename).read_text()
            variants=[source,source.upper().replace('PROGRAM','program').replace('END PROGRAM','end program'),
                      '\n'.join('    '+line+' ! variant comment' for line in source.splitlines())]
            for index,variant in enumerate(variants):
                with self.subTest(pattern=pattern,variant=index),tempfile.TemporaryDirectory() as td:
                    path=Path(td)/filename;path.write_text(variant)
                    result=analyze_fortran(path)
                    self.assertEqual(result['status'],'supported',result)
                    self.assertEqual(result['pattern'],pattern)

    def test_negative_stencils_return_location_and_reason(self):
        original=(ROOT/'fortran_samples'/'heat1d.f90').read_text()
        mutations={
            'nonlinear':original.replace('u(i+1)-2.0*u(i)+u(i-1)', 'u(i+1)*u(i)-2.0*u(i)+u(i-1)'),
            'boundary':original.replace('unew(0)=u(0)', 'unew(0)=1.0'),
            'loop':original.replace('do n=1,nt', 'do n=1,nt,2'),
        }
        for label,source in mutations.items():
            with self.subTest(kind=label),tempfile.TemporaryDirectory() as td:
                path=Path(td)/'negative.f90';path.write_text(source)
                result=analyze_fortran(path)
                self.assertEqual(result['status'],'unsupported',result)
                self.assertEqual(result['file'],str(path))
                self.assertGreaterEqual(result['line'],1)
                self.assertTrue(result['reason'])

    @unittest.skipUnless((ROOT/'data/devito.sqlite').is_file(),'index Devito before emitter tests')
    def test_renamed_fields_remain_emittable(self):
        from metagraph.emitter import emit_fortran
        allow=(ROOT/'data/devito.allowed_names').read_text().splitlines()
        for filename,pattern in SAMPLES.items():
            source=(ROOT/'fortran_samples'/filename).read_text()
            for old,new in [('unew','next'),('uprev','prev'),('u','v'),('iter','istep'),('n','istep'),('i','ix'),('j','iy')]:
                source=re.sub(r'\b'+old+r'\b',new,source,flags=re.IGNORECASE)
            with self.subTest(pattern=pattern),tempfile.TemporaryDirectory() as td:
                path=Path(td)/filename;path.write_text(source)
                emitted=emit_fortran(path,ROOT/'data/devito.sqlite',allow)
                self.assertEqual(emitted['status'],'supported',emitted)
                self.assertIsNotNone(emitted['code'])


if __name__=='__main__':unittest.main()
