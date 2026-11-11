"""Emit conservative Devito templates for five recognized Fortran stencils."""
import argparse
import json
import sqlite3
from pathlib import Path

from .fortran_analysis import analyze_fortran
from .api_validation import validate_source


def _idiom(database, pattern):
    terms = {
        "heat_1d": ("TimeFunction", "Eq(", "u.dt"),
        "heat_2d": ("TimeFunction", "Eq(", "u.dt"),
        "wave_1d": ("TimeFunction", "Eq(", "u.dt2"),
        "upwind_advection": ("TimeFunction", "Operator(", "forward"),
        "jacobi_poisson": ("Function(", "Operator(", "Eq("),
    }[pattern]
    with sqlite3.connect(database) as con:
        rows=con.execute("SELECT path,text FROM chunks WHERE path LIKE '%.py' ORDER BY path,name,id").fetchall()
    for path,text in rows:
        if all(term in text for term in terms): return path
    raise ValueError(f"no indexed Devito Python idiom found for {pattern}")


def _render(info, source):
    if info["status"] != "supported":
        raise ValueError(f"unsupported Fortran at {info['file']}:{info['line']}: {info['reason']}")
    pattern=info["pattern"]; values=info["scalar_values"]; dims=info["array_bounds"]["u"]
    if any(d["lower"] != 0 for d in dims): raise ValueError("only zero-based Fortran array bounds are supported")
    shape=tuple(d["size"] for d in dims)
    if any(d["size"] < 3 for d in dims): raise ValueError("grid needs at least one interior point")
    shape_arg=shape[0] if len(shape)==1 else shape
    spacing=[float(values.get(x,1.0)) for x in (["dx"] if len(shape)==1 else ["dx","dy"])]
    extent=tuple(spacing[i]*(shape[i]-1) for i in range(len(shape)))
    init=float(info["array_initializers"].get("u",0)); points=info["array_points"]
    nt=int(values[info["step_parameters"][0]]); dt=float(values.get("dt",1.0))
    code=f'''# Generated from {info['file']}:{info['line']}
# Devito idiom source: {source}
import numpy as np
from devito import Grid, TimeFunction, Function, Eq, Operator, solve

shape = {shape_arg!r}
extent = {extent!r}
grid = Grid(shape=shape, extent=extent)
'''
    def initialization(field, frame=0):
        return f"{field}.data[:] = {init!r}\n"+''.join(f"{field}.data[{frame}, {', '.join(map(str,p['indices']))}] = {float(p['value'])!r}\n" for p in points if p['array']=='u')
    if pattern in {"heat_1d","heat_2d"}:
        alpha=float(values.get("alpha",1.0)); derivative="u.dx2" if len(shape)==1 else "u.dx2 + u.dy2"
        code+=f'''nt = {nt}
dt = {dt!r}
alpha = {alpha!r}
u = TimeFunction(name="u", grid=grid, time_order=1, space_order=2, save=nt+1)
{initialization('u')}x = grid.dimensions[0]
''' + ("y = grid.dimensions[1]\n" if len(shape)==2 else "")
        code+=f"eqn = Eq(u.dt, alpha*({derivative}))\nstencil = solve(eqn, u.forward)\nop = Operator(Eq(u.forward, stencil))\n"
        code+='''for step in range(nt):
    op.apply(time_m=step, time_M=step, dt=dt)
    u.data[step+1, 0, ...] = u.data[step, 0, ...]
    u.data[step+1, -1, ...] = u.data[step, -1, ...]
'''
        if len(shape)==2: code+='    u.data[step+1, :, 0] = u.data[step, :, 0]\n    u.data[step+1, :, -1] = u.data[step, :, -1]\n'
        code+="np.savetxt('result.txt', u.data[nt, ...].ravel(order='F'))\n"
    elif pattern=="upwind_advection":
        vel=float(values["velocity"]); offset="x-1" if info["advection_side"]=="left" else "x+1"
        code+=f'''nt = {nt}
dt = {dt!r}
velocity = {vel!r}
u = TimeFunction(name="u", grid=grid, time_order=1, space_order=1, save=nt+1)
{initialization('u')}x = grid.dimensions[0]
eq = Eq(u.forward, u-velocity*dt*u.dxl)
op = Operator(eq)
for step in range(nt):
    op.apply(time_m=step, time_M=step, dt=dt)
    u.data[step+1, 0] = u.data[step, 0]
    u.data[step+1, -1] = u.data[step, -1]
np.savetxt('result.txt', u.data[nt, ...].ravel(order='F'))
'''
    elif pattern=="wave_1d":
        c2=float(values["c2"])
        code+=f'''nt = {nt}
dt = {dt!r}
c2 = {c2!r}
u = TimeFunction(name="u", grid=grid, time_order=2, space_order=2, save=nt+2)
u.data[:] = {init!r}
{initialization('u',1)}
eqn = Eq(u.dt2, c2*u.dx2)
stencil = solve(eqn, u.forward)
op = Operator(Eq(u.forward, stencil))
for step in range(1, nt+1):
    op.apply(time_m=step, time_M=step, dt=dt)
    u.data[step+1, 0] = u.data[step, 0]
    u.data[step+1, -1] = u.data[step, -1]
np.savetxt('result.txt', u.data[nt+1, ...].ravel(order='F'))
'''
    else:
        h2=float(values["h2"]); finit=float(info["array_initializers"].get("f",0))
        code+=f'''niter = {nt}
h2 = {h2!r}
u = Function(name="u", grid=grid, space_order=2)
unew = Function(name="unew", grid=grid, space_order=2)
f = Function(name="f", grid=grid, space_order=2)
u.data[:] = {init!r}
f.data[:] = {finit!r}
x, y = grid.dimensions
eq = Eq(unew, 0.25*(u[x+1, y]+u[x-1, y]+u[x, y+1]+u[x, y-1]-h2*f))
op = Operator(eq)
for _ in range(niter):
    op.apply()
    unew.data[0, :] = u.data[0, :]
    unew.data[-1, :] = u.data[-1, :]
    unew.data[:, 0] = u.data[:, 0]
    unew.data[:, -1] = u.data[:, -1]
    u.data[:] = unew.data
np.savetxt('result.txt', u.data.ravel(order='F'))
'''
    return code


def emit_fortran(source, database, allowed_names):
    info=analyze_fortran(source)
    idiom=_idiom(database,info["pattern"]) if info["status"]=="supported" else None
    code=_render(info,idiom) if idiom else None
    if code is not None:
        errors=validate_source(code,allowed_names)
        if errors: raise ValueError("generated API validation failed: "+"; ".join(errors))
    return {**info,"idiom_source":idiom,"code":code}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('source');p.add_argument('--database',required=True);p.add_argument('--allowed-names',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();result=emit_fortran(a.source,a.database,Path(a.allowed_names).read_text().splitlines())
    if result['status']!='supported': print(json.dumps(result,indent=2));return 2
    Path(a.output).write_text(result['code'],encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='code'},indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
