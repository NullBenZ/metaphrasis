"""Conservative, AST-based recognizer for five fixed finite-difference families."""
from pathlib import Path
import argparse
import json
from decimal import Decimal,InvalidOperation
import re
from fparser.common.readfortran import FortranStringReader
from fparser.two.parser import ParserFactory
from fparser.two.utils import walk


def _id(node):
    return str(node).strip().lower()


def _items_subscripts(part_ref):
    try:
        sub=part_ref.items[1]
        values=sub.items
        if isinstance(values,tuple) and len(values)==2 and values[0]==",":values=values[1]
        return list(values)
    except (AttributeError,IndexError,TypeError):
        return []


def _affine_offset(node, variable):
    """Return integer offset in `variable + offset`, or None if not affine-simple."""
    s=re.sub(r"\s+","",str(node).lower())
    s=s.strip("()")
    if s==variable:return 0
    if s in {"+"+variable,variable+"+0"}:return 0
    m=re.fullmatch(re.escape(variable)+r"([+-])(\d+)",s)
    if m:return int(m.group(2))*(1 if m.group(1)=="+" else -1)
    m=re.fullmatch(r"(\d+)\+"+re.escape(variable),s)
    if m:return int(m.group(1))
    return None


def _tree(node):
    if node is None:return None
    if isinstance(node,(str,int,float)):return str(node).lower()
    name=type(node).__name__
    if name=="Part_Ref":
        base=_id(node.items[0]); subs=[_tree(x) for x in _items_subscripts(node)]
        return {"ref":base,"indices":subs}
    if hasattr(node,"items"):
        return {name:[_tree(x) for x in node.items]}
    return str(node).lower()


def _expr_has_ref(node,Part_Ref):
    if isinstance(node,Part_Ref):return True
    if isinstance(node,(tuple,list)):return any(_expr_has_ref(x,Part_Ref) for x in node)
    return any(_expr_has_ref(x,Part_Ref) for x in getattr(node,"items",()) if not isinstance(x,str))


def _expression_shape(node,variables,by_array,Part_Ref):
    """Normalize variable coefficients but retain stencil constants and tree structure."""
    if type(node).__name__ in {"Function_Reference","Intrinsic_Function_Reference"}:return None
    if type(node).__name__ in {"Int_Literal_Constant","Real_Literal_Constant"}:
        raw=str(node.items[0]).replace("d","e").replace("D","e")
        try:
            value=Decimal(raw)
            rendered=format(value.normalize(),"f")
            return "C"+rendered
        except (InvalidOperation,AttributeError):return None
    if isinstance(node,Part_Ref):
        name=_id(node.items[0]);indices=_items_subscripts(node);offset=[]
        for dim,var in enumerate(variables):
            if dim>=len(indices):return None
            value=_affine_offset(indices[dim],var)
            if value is None:return None
            offset.append(value)
        offset=tuple(offset);field_offsets=by_array.get(name,set())
        if len(variables)==1:
            if offset==(0,):return "A0" if (-1,) in field_offsets or (1,) in field_offsets else "P0"
            if offset==(-1,):return "AXM"
            if offset==(1,):return "AXP"
        else:
            if offset==(0,0):return "A0" if any(v!=(0,0) for v in field_offsets) else "F0"
            if offset==(-1,0):return "AXM"
            if offset==(1,0):return "AXP"
            if offset==(0,-1):return "AYM"
            if offset==(0,1):return "AYP"
        return None
    if not _expr_has_ref(node,Part_Ref):
        allowed={"Name","Int_Literal_Constant","Real_Literal_Constant","Parenthesis","Level_1_Expr","Level_2_Expr","Add_Operand","Mult_Operand","Power_Operand"}
        for item in walk(node):
            if isinstance(item,str) or item is None:continue
            if type(item).__name__ not in allowed:return None
        return "S"
    if type(node).__name__=="Parenthesis":return _expression_shape(node.items[1],variables,by_array,Part_Ref)
    items=getattr(node,"items",None)
    if isinstance(items,tuple) and len(items)==3 and isinstance(items[1],str) and items[1] in {"+","-","*","/","**"}:
        left=_expression_shape(items[0],variables,by_array,Part_Ref);right=_expression_shape(items[2],variables,by_array,Part_Ref)
        if left is None or right is None:return None
        return (items[1],left,right)
    return None


def _expected_shape(pattern,advection_side="left"):
    add=lambda a,b:("+",a,b);sub=lambda a,b:("-",a,b);mul=lambda a,b:("*",a,b);div=lambda a,b:("/",a,b)
    lap1=add(sub("AXP",mul("C2","A0")),"AXM")
    if pattern=="heat_1d":return add("A0",mul("S",lap1))
    if pattern=="wave_1d":return add(sub(mul("C2","A0"),"P0"),mul("S",lap1))
    if pattern=="upwind_advection":return sub("A0",mul("S",sub("A0","AXM" if advection_side=="left" else "AXP")))
    lapx=add(sub("AXP",mul("C2","A0")),"AXM")
    lapy=add(sub("AYP",mul("C2","A0")),"AYM")
    if pattern=="heat_2d":return add("A0",mul("S",add(div(lapx,"S"),div(lapy,"S"))))
    if pattern=="jacobi_poisson":return mul("C0.25",sub(add(add(add("AXP","AXM"),"AYP"),"AYM"),mul("S","F0")))
    return None

def _eval_numeric(node,values):
    name=type(node).__name__
    if name in {"Int_Literal_Constant","Real_Literal_Constant"}:
        raw=str(node.items[0]).replace("d","e").replace("D","e")
        try:
            number=float(raw)
            return int(number) if number.is_integer() else number
        except ValueError:return None
    if name=="Name":return values.get(_id(node))
    if name=="Parenthesis":return _eval_numeric(node.items[1],values)
    items=getattr(node,"items",None)
    if isinstance(items,tuple) and len(items)==3 and isinstance(items[1],str):
        left=_eval_numeric(items[0],values);right=_eval_numeric(items[2],values)
        if left is None or right is None:return None
        try:
            return {"+":lambda:left+right,"-":lambda:left-right,"*":lambda:left*right,
                    "/":lambda:left/right,"**":lambda:left**right}.get(items[1],lambda:None)()
        except (ZeroDivisionError,OverflowError):return None
    return None


def _list_items(node):
    items=getattr(node,"items",())
    if isinstance(items,tuple) and len(items)==2 and items[0]==",":return list(items[1])
    return list(items) if isinstance(items,(tuple,list)) else []


def _fortran_metadata(tree,assignments):
    from fparser.two.Fortran2003 import Entity_Decl,Type_Declaration_Stmt,Part_Ref
    declarations=list(walk(tree,Type_Declaration_Stmt));scalar_values={};array_bounds={}
    for declaration in declarations:
        try:entities=walk(declaration.items[2],Entity_Decl)
        except (IndexError,TypeError):continue
        for entity in entities:
            name=_id(entity.items[0]);shape=entity.items[1];init=entity.items[3]
            if shape is not None:
                bounds=[]
                for spec in _list_items(shape):
                    try:lower,upper=spec.items
                    except (AttributeError,ValueError):continue
                    bounds.append((lower,upper))
                array_bounds[name]=bounds
            elif init is not None:
                val=_eval_numeric(init.items[-1],scalar_values)
                if val is not None:scalar_values[name]=val
    array_initializers={};array_points=[]
    for assignment in assignments:
        if _active_loops(assignment):continue
        try:lhs,rhs=assignment.items[0],assignment.items[2]
        except (AttributeError,IndexError):continue
        value=_eval_numeric(rhs,scalar_values)
        if value is None:continue
        if type(lhs).__name__=="Name":
            name=_id(lhs)
            if name in array_bounds:array_initializers[name]=value
        elif isinstance(lhs,Part_Ref):
            name=_id(lhs.items[0])
            if name in array_bounds:
                indices=[]
                for index in _items_subscripts(lhs):
                    idx=_eval_numeric(index,scalar_values)
                    if idx is None:break
                    indices.append(idx)
                if len(indices)==len(array_bounds[name]):array_points.append({"array":name,"indices":indices,"value":value})
    shape_data={}
    for name,bounds in array_bounds.items():
        dims=[]
        for lower_node,upper_node in bounds:
            lower=_eval_numeric(lower_node,scalar_values);upper=_eval_numeric(upper_node,scalar_values)
            if lower is None or upper is None:break
            dims.append({"lower":lower,"upper":upper,"size":upper-lower+1})
        if len(dims)==len(bounds):shape_data[name]=dims
    return scalar_values,shape_data,array_initializers,array_points

def _loop_info(node):
    try:
        control=node.items[1]
        spec=control.items[1]
        variable=_id(spec[0]); bounds=[_id(x) for x in spec[1]]
        step=_id(control.items[2]) if control.items[2] is not None else "1"
        return {"variable":variable,"bounds":bounds,"step":step}
    except (AttributeError,IndexError,TypeError):return None


def _active_loops(node):
    from fparser.two.Fortran2003 import Block_Nonlabel_Do_Construct
    ancestors=[];parent=getattr(node,"parent",None)
    while parent is not None:
        if isinstance(parent,Block_Nonlabel_Do_Construct) and parent.content:
            info=_loop_info(parent.content[0])
            if info:ancestors.append(info)
        parent=getattr(parent,"parent",None)
    return list(reversed(ancestors))


def _line(node):
    try:return int(node.item.span[0])
    except (AttributeError,TypeError,IndexError):return 1


def _failure(path,line,reason):
    return {"status":"unsupported","file":str(path),"line":int(line or 1),"reason":reason}


def analyze_fortran(path):
    path=Path(path)
    try:
        source=path.read_text(encoding="utf-8",errors="replace")
        tree=ParserFactory().create(std="f2008")(FortranStringReader(source))
    except Exception as exc:
        return _failure(path,1,f"Fortran parse failed: {exc}")
    from fparser.two.Fortran2003 import Assignment_Stmt, Part_Ref
    assignments=list(walk(tree,Assignment_Stmt))
    scalar_values,array_bounds,array_initializers,array_points=_fortran_metadata(tree,assignments)
    candidates=[]
    for stmt in assignments:
        try:lhs,rhs=stmt.items[0],stmt.items[2]
        except (AttributeError,IndexError):continue
        if not isinstance(lhs,Part_Ref):continue
        active_loops=_active_loops(stmt);loop_vars=[x["variable"] for x in active_loops]
        subs=_items_subscripts(lhs)
        vars_=[_id(x) for x in subs]
        if not vars_ or not all(v in loop_vars for v in vars_):continue
        refs=[]
        for ref in walk(rhs,Part_Ref):
            base=_id(ref.items[0]);idx=_items_subscripts(ref)
            offsets=[]
            for dim,var in enumerate(vars_):
                if dim>=len(idx):break
                offsets.append(_affine_offset(idx[dim],var))
            if len(offsets)==len(vars_) and all(x is not None for x in offsets):refs.append((base,tuple(offsets)))
        by_array={}
        for name,offset in refs:by_array.setdefault(name,set()).add(offset)
        candidates.append((stmt,lhs,rhs,vars_,by_array,refs,active_loops))
    if not candidates:
        return _failure(path,1,"no array-element assignment under an index loop")
    cross1={(-1,),(1,)};cross2={(-1,0),(1,0),(0,-1),(0,1)}
    chosen=None;pattern=None;stencil=[];advection_side="left"
    # Try update statements from the deepest spatial loops first.
    for candidate in reversed(candidates):
        stmt,lhs,rhs,vars_,by_array,refs,active_loops=candidate
        spatial_vars=set(vars_)
        outer=[loop for loop in active_loops if loop["variable"] not in spatial_vars]
        has_outer_step_loop=bool(outer)
        if len(vars_)==1:
            arrays=[(a,ofs) for a,ofs in by_array.items() if cross1.issubset(ofs)]
            if arrays and has_outer_step_loop:
                pattern="wave_1d" if len(by_array)>=2 else "heat_1d"
                chosen=candidate;stencil=sorted(cross1|{(0,)});break
            upwind=[(a,ofs) for a,ofs in by_array.items() if (0,) in ofs and (set(ofs)&{(-1,),(1)})]
            if upwind and has_outer_step_loop:
                pattern="upwind_advection";chosen=candidate
                advection_side="left" if any((-1,) in ofs for _,ofs in upwind) else "right"
                stencil=sorted({o for _,ofs in upwind for o in ofs});break
        if len(vars_)==2 and cross2.issubset(set().union(*by_array.values()) if by_array else set()):
            arrays=[(a,ofs) for a,ofs in by_array.items() if cross2.issubset(ofs)]
            if arrays and has_outer_step_loop and len(by_array)==1:
                pattern="heat_2d";chosen=candidate;stencil=sorted(cross2|{(0,0)});break
            if arrays and has_outer_step_loop and len(by_array)==2:
                pattern="jacobi_poisson";chosen=candidate;stencil=sorted(cross2|{(0,0)});break
    if chosen is None:
        stmt=candidates[0][0]
        return _failure(path,_line(stmt),"array updates do not match the supported 1D/2D heat, 1D wave, upwind, or Jacobi stencils")
    stmt,lhs,rhs,vars_,by_array,refs,active_loops=chosen
    actual_shape=_expression_shape(rhs,vars_,by_array,Part_Ref)
    expected_shape=_expected_shape(pattern,advection_side)
    if actual_shape!=expected_shape:
        return _failure(path,_line(stmt),"expression tree or coefficient structure does not match the supported stencil template")
    target_name=_id(lhs.items[0]);boundary=[]
    stencil_fields={name for name,offsets in by_array.items() if any(any(component!=0 for component in offset) for offset in offsets)}
    for assignment in assignments:
        if assignment is stmt:continue
        try:blhs,brhs=assignment.items[0],assignment.items[2]
        except (AttributeError,IndexError):continue
        if not isinstance(blhs,Part_Ref) or _id(blhs.items[0])!=target_name:continue
        active_names=[x["variable"] for x in _active_loops(assignment)]
        if all(v in active_names for v in vars_):continue
        if not isinstance(brhs,Part_Ref) or _id(brhs.items[0]) not in stencil_fields or str(blhs.items[1])!=str(brhs.items[1]):
            return _failure(path,_line(assignment),"boundary assignment is not a direct same-index copy from the evolving stencil field")
        boundary.append({"line":_line(assignment),"target":str(blhs),"source":_id(brhs.items[0]),
                         "indices":[":" if type(x).__name__=="Subscript_Triplet" else str(x) for x in _items_subscripts(blhs)]})
    if len({x["target"] for x in boundary})<2*len(vars_):
        return _failure(path,_line(stmt),"required explicit boundary assignments were not found for every spatial dimension")
    if any(len(loop["bounds"]) != 2 for loop in active_loops):
        return _failure(path,_line(stmt),"explicit loop strides are unsupported; only the default unit stride is recognized")
    loop_bounds={x["variable"]:x["bounds"] for x in active_loops}
    outer=[loop for loop in active_loops if loop["variable"] not in set(vars_)]
    step_parameters=sorted({b for x in outer for b in x["bounds"] if not b.isdigit()})
    grid_parameters=sorted({b for x in active_loops if x["variable"] in vars_ for b in x["bounds"] if not b.isdigit()})
    return {"status":"supported","file":str(path),"line":_line(stmt),"pattern":pattern,
            "dimensions":len(vars_),"grid_parameters":grid_parameters,
            "step_parameters":step_parameters,"spatial_variables":vars_,
            "loop_variables":[x["variable"] for x in active_loops],"loop_bounds":loop_bounds,
            "loop_steps":{x["variable"]:x["step"] for x in active_loops},
            "boundary_assignments":boundary,
            "target_array":target_name,"source_arrays":sorted(by_array),
            "array_offsets":{k:[list(x) for x in sorted(v)] for k,v in sorted(by_array.items())},
            "array_bounds":array_bounds,"scalar_values":scalar_values,
            "array_initializers":array_initializers,"array_points":array_points,
            "advection_side":advection_side if pattern=="upwind_advection" else None,
            "stencil_offsets":[list(x) for x in stencil],"expression_tree":_tree(rhs),
            "expression_symbols":sorted(set(re.findall(r"[a-z][a-z0-9_]*",str(rhs).lower())))}


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument("source");parser.add_argument("--output")
    args=parser.parse_args();result=analyze_fortran(args.source);rendered=json.dumps(result,indent=2)
    if args.output:Path(args.output).write_text(rendered+"\n",encoding="utf-8")
    else:print(rendered)
if __name__=="__main__":main()
