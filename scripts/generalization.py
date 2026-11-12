#!/usr/bin/env python3
"""Generate deterministic Fortran variants and measure analyzer/emitter/numeric pass rates."""
import argparse
import csv
import re
import tempfile
from pathlib import Path

from metagraph.fortran_analysis import analyze_fortran
from metagraph.emitter import emit_fortran
from metagraph.validate_numeric import validate

PATTERNS={
    'heat_1d':'heat1d.f90','heat_2d':'heat2d.f90','wave_1d':'wave1d.f90',
    'upwind_advection':'advection1d.f90','jacobi_poisson':'poisson2d.f90',
}


def variants(source):
    out=[('baseline',source)]
    dims=re.sub(r'\bnx\s*=\s*(\d+)',lambda m:f'nx={int(m.group(1))+2}',source,flags=re.I)
    dims=re.sub(r'\bny\s*=\s*(\d+)',lambda m:f'ny={int(m.group(1))+1}',dims,flags=re.I)
    dims=re.sub(r'\b(nt|niter)\s*=\s*(\d+)',lambda m:f'{m.group(1)}={int(m.group(2))+1}',dims,flags=re.I)
    out.append(('grid_and_steps',dims))
    changed=source
    for old,new in [('alpha=0.1','alpha=0.07'),('dt=0.1','dt=0.05'),('c2=0.25','c2=0.16'),
                    ('velocity=0.5','velocity=0.25'),('h2=1.0','h2=0.5')]:
        changed=re.sub(re.escape(old),new,changed,flags=re.I)
    out.append(('coefficients',changed))
    renamed=source
    for old,new in [('unew','next'),('uprev','prev'),('u','v'),('iter','istep'),('n','istep'),('i','ix'),('j','iy')]:
        renamed=re.sub(r'\b'+old+r'\b',new,renamed,flags=re.I)
    out.append(('renamed_arrays',renamed))
    styled='\n'.join('    '+line.upper()+' ! GENERATED VARIANT' for line in source.splitlines())+'\n'
    styled=styled.replace('RESULT.TXT','result.txt')
    styled=styled.replace('PROGRAM','program').replace('END PROGRAM','end program')
    styled=re.sub(r'(?im)^\s*REAL\s*::([^\n(]+)$',r'    real, parameter ::\1',styled)
    out.append(('case_comments_indentation_declarations',styled))
    return out


def write_rows(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    columns=list(dict.fromkeys(key for row in rows for key in row)) if rows else ['pattern','variant','status']
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=columns);writer.writeheader();writer.writerows(rows)


def run(database,allowed_file,samples,output,atol,rtol):
    allowed=Path(allowed_file).read_text(encoding='utf-8').splitlines()
    rows=[];mutation_rows=[]
    with tempfile.TemporaryDirectory(prefix='fortran-generalization-') as scratch:
        scratch=Path(scratch)
        for pattern,filename in PATTERNS.items():
            base=(Path(samples)/filename).read_text(encoding='utf-8')
            for label,source in variants(base):
                variant=scratch/f'{pattern}-{label}.f90';variant.write_text(source,encoding='utf-8')
                analysis=analyze_fortran(variant)
                row={'pattern':pattern,'variant':label,'analysis':analysis['status'],'emission':'not_run','validation':'not_run','max_abs_error':''}
                if analysis['status']=='supported':
                    try:
                        emitted=emit_fortran(variant,database,allowed)
                        script=scratch/f'{pattern}-{label}.py';script.write_text(emitted['code'],encoding='utf-8')
                        row['emission']='pass'
                        compared=validate(variant,script,atol=atol,rtol=rtol)
                        row['validation']='pass' if compared['passed'] else 'fail'
                        row['max_abs_error']=compared.get('max_abs_error','')
                    except Exception as exc:
                        row['emission']='fail' if row['emission']=='not_run' else row['emission']
                        row['reason']=str(exc)
                else: row['reason']=analysis['reason']
                rows.append(row)
            # Mutate generated output only in scratch, run it against the unmodified source,
            # and require numeric comparison to reject the sign change.
            base_path=Path(samples)/filename
            if pattern=='heat_1d':
                emitted=emit_fortran(base_path,database,allowed)
                mutation=emitted['code'].replace('alpha = 0.1','alpha = -0.1',1)
                script=scratch/'mutated_heat1d.py';script.write_text(mutation,encoding='utf-8')
                try:
                    result=validate(base_path,script,atol=atol,rtol=rtol)
                    caught=not result['passed']
                    detail=f"max_abs_error={result.get('max_abs_error')}"
                except Exception as exc:
                    caught=True;detail=f'generated program failed: {exc}'
                mutation_rows.append({'mutation':'flip_heat_diffusion_coefficient_sign','caught':caught,'detail':detail})
    summary=[]
    for pattern in PATTERNS:
        group=[r for r in rows if r['pattern']==pattern]
        passed=sum(r['analysis']=='supported' and r['emission']=='pass' and r['validation']=='pass' for r in group)
        summary.append({'pattern':pattern,'passed':passed,'total':len(group),'pass_rate':passed/len(group) if group else 0.0})
    write_rows(Path(output)/'generalization_variants.csv',rows)
    write_rows(Path(output)/'generalization_pass_rate.csv',summary)
    write_rows(Path(output)/'generalization_mutation.csv',mutation_rows)
    return summary,mutation_rows


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--database',required=True);parser.add_argument('--allowed-names',required=True)
    parser.add_argument('--samples',default='fortran_samples');parser.add_argument('--output',default='bench/results')
    parser.add_argument('--atol',type=float,default=2e-6);parser.add_argument('--rtol',type=float,default=2e-6)
    parser.add_argument('--seed',type=int,default=1,help='accepted for reproducible experiment interfaces; variants are enumerated deterministically')
    args=parser.parse_args();summary,mutations=run(args.database,args.allowed_names,args.samples,args.output,args.atol,args.rtol)
    print('pattern,passed,total,pass_rate')
    for row in summary: print(f"{row['pattern']},{row['passed']},{row['total']},{row['pass_rate']:.6f}")
    print(f"mutation_caught={all(row['caught'] for row in mutations)}")
    return 0 if all(row['pass_rate']==1 for row in summary) and all(row['caught'] for row in mutations) else 1
if __name__=='__main__':raise SystemExit(main())
