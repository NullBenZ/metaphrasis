"""Compile a Fortran sample, run a Devito script, and compare result.txt arrays."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import numpy as np


def compare_arrays(reference,converted,atol,rtol):
    reference=np.asarray(reference);converted=np.asarray(converted)
    if reference.shape!=converted.shape:
        return {'passed':False,'shape':{'fortran':list(reference.shape),'devito':list(converted.shape)},'elements':int(reference.size)}
    delta=np.abs(reference-converted)
    return {'passed':bool(np.allclose(reference,converted,atol=atol,rtol=rtol)),
            'elements':int(reference.size),'max_abs_error':float(delta.max(initial=0.0)),
            'atol':float(atol),'rtol':float(rtol)}


def validate(fortran_source,devito_script,atol=1e-8,rtol=1e-7):
    compiler=shutil.which('gfortran')
    if not compiler:raise RuntimeError('gfortran is required for numeric validation')
    fortran_source=Path(fortran_source).resolve();devito_script=Path(devito_script).resolve()
    with tempfile.TemporaryDirectory(prefix='fortran-devito-validate-') as td:
        root=Path(td);fdir=root/'fortran';pdir=root/'devito';fdir.mkdir();pdir.mkdir();exe=root/'sample'
        subprocess.run([compiler,'-std=f2008','-O0',str(fortran_source),'-o',str(exe)],check=True,capture_output=True,text=True)
        subprocess.run([str(exe)],cwd=fdir,check=True,capture_output=True,text=True)
        subprocess.run([sys.executable,str(devito_script)],cwd=pdir,check=True,capture_output=True,text=True)
        fpath=fdir/'result.txt';dpath=pdir/'result.txt'
        if not fpath.is_file() or not dpath.is_file():raise RuntimeError('both programs must write result.txt in their working directory')
        result=compare_arrays(np.loadtxt(fpath),np.loadtxt(dpath),atol,rtol)
        result.update({'status':'pass' if result['passed'] else 'fail','fortran':str(fortran_source),'devito_script':str(devito_script)})
        return result


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--fortran',required=True);p.add_argument('--devito-script',required=True);p.add_argument('--atol',type=float,default=1e-8);p.add_argument('--rtol',type=float,default=1e-7)
    a=p.parse_args()
    try:result=validate(a.fortran,a.devito_script,a.atol,a.rtol)
    except (RuntimeError,subprocess.CalledProcessError) as exc:
        print(json.dumps({'status':'blocked','reason':str(exc)},indent=2));return 2
    print(json.dumps(result,indent=2));return 0 if result['passed'] else 1
if __name__=='__main__':raise SystemExit(main())
