"""AST validator that permits only Devito identifiers in an indexed allow-list."""
import argparse
import ast
from pathlib import Path


def validate_source(source,allowed_names):
    allowed=set(allowed_names);errors=[]
    try:tree=ast.parse(source)
    except SyntaxError as exc:return [f"Python syntax error at line {exc.lineno}: {exc.msg}"]
    imported={};modules=set();devito_objects=set()
    for node in ast.walk(tree):
        if isinstance(node,ast.ImportFrom) and node.module and (node.module=='devito' or node.module.startswith('devito.')):
            for alias in node.names:
                if alias.name not in allowed:errors.append(f"Devito API name not in indexed allow-list: {alias.name}")
                imported[alias.asname or alias.name]=alias.name
        elif isinstance(node,ast.Import):
            for alias in node.names:
                if alias.name=='devito':modules.add(alias.asname or 'devito')
    for node in ast.walk(tree):
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Name) and node.value.func.id in imported:
            devito_objects.update(t.id for t in node.targets if isinstance(t,ast.Name))
        if isinstance(node,ast.Assign) and isinstance(node.value,ast.Call) and isinstance(node.value.func,ast.Attribute) and isinstance(node.value.func.value,ast.Name) and node.value.func.value.id in modules:
            devito_objects.update(t.id for t in node.targets if isinstance(t,ast.Name))
    for node in ast.walk(tree):
        if isinstance(node,ast.Attribute):
            if isinstance(node.value,ast.Name) and node.value.id in modules and node.attr not in allowed:
                errors.append(f"Devito API name not in indexed allow-list: {node.attr}")
            elif isinstance(node.value,ast.Name) and node.value.id in devito_objects and node.attr not in allowed:
                errors.append(f"Devito object attribute not in indexed allow-list: {node.attr}")
    return sorted(set(errors))


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--source',required=True);p.add_argument('--allowed-names',required=True)
    a=p.parse_args();errors=validate_source(Path(a.source).read_text(encoding='utf-8'),Path(a.allowed_names).read_text(encoding='utf-8').splitlines())
    if errors:
        for error in errors:print(error)
        return 1
    print('API names validated against indexed allow-list');return 0
if __name__=='__main__':raise SystemExit(main())
