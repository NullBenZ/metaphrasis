"""Generate and numerically validate each supported Fortran fixture."""
import argparse
import csv
import json
import sqlite3
import tempfile
from pathlib import Path

from .emitter import emit_fortran
from .validate_numeric import validate


def run(database, allow_file, sample_dir, atol=1e-8, rtol=1e-7):
    allowed=Path(allow_file).read_text(encoding='utf-8').splitlines()
    rows=[]
    for source in sorted(Path(sample_dir).glob('*.f90')):
        emitted=emit_fortran(source,database,allowed)
        if emitted['status']!='supported': continue
        with tempfile.TemporaryDirectory(prefix='devito-generated-') as td:
            script=Path(td)/'generated.py';script.write_text(emitted['code'],encoding='utf-8')
            result=validate(source,script,atol=atol,rtol=rtol)
        rows.append({'pattern':emitted['pattern'],'file':source.name,'status':'PASS' if result['passed'] else 'FAIL',
                     'max_abs_error':result.get('max_abs_error')})
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',required=True);p.add_argument('--allowed-names',required=True);p.add_argument('--samples',default='fortran_samples');p.add_argument('--atol',type=float,default=1e-8);p.add_argument('--rtol',type=float,default=1e-7);p.add_argument('--csv')
    a=p.parse_args();rows=run(a.database,a.allowed_names,a.samples,a.atol,a.rtol)
    print('| Pattern | Fortran sample | Result | Max abs error |\n|---|---|---:|---:|')
    for r in rows: print(f"| {r['pattern']} | {r['file']} | {r['status']} | {r['max_abs_error']:.6g} |")
    if a.csv:
        target=Path(a.csv);target.parent.mkdir(parents=True,exist_ok=True)
        with target.open('w',newline='',encoding='utf-8') as f:
            w=csv.DictWriter(f,fieldnames=['pattern','file','status','max_abs_error']);w.writeheader();w.writerows(rows)
    return 0 if rows and all(r['status']=='PASS' for r in rows) else 1
if __name__=='__main__':raise SystemExit(main())
