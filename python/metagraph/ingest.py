"""Deterministic AST/document chunking and SQLite FTS5 graph indexing."""
import argparse
import ast
import hashlib
import re
import sqlite3
from pathlib import Path


def _id(path: str, kind: str, name: str) -> str:
    return hashlib.sha256(f"{path}\0{kind}\0{name}".encode()).hexdigest()[:24]


def _name(node):
    if isinstance(node, ast.Name): return node.id
    if isinstance(node, ast.Attribute): return _name(node.value) + "." + node.attr
    if isinstance(node, ast.Call): return _name(node.func)
    return ""


def _read_python(path, rel):
    source = path.read_text(encoding="utf-8", errors="replace")
    try: tree = ast.parse(source, filename=rel)
    except SyntaxError: return [], [], []
    rows=[]; edges=[]; entities=[]
    module_id=_id(rel,"module",rel)
    rows.append((module_id,rel,"module",rel,source))
    for node in ast.walk(tree):
        if not isinstance(node,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)): continue
        kind="class" if isinstance(node,ast.ClassDef) else "function"
        name=node.name; cid=_id(rel,kind,name+":"+str(node.lineno))
        text=ast.get_source_segment(source,node) or ast.dump(node,include_attributes=False)
        rows.append((cid,rel,kind,name,text))
        entities.append(("symbol:"+name,name,kind,cid))
        edges.append((cid,module_id,"PART_OF"))
        for call in ast.walk(node):
            if isinstance(call,ast.Call):
                called=_name(call.func)
                if called:
                    edges.append((cid,"symbol:"+called,"CALLS"))
                    entities.append(("symbol:"+called,called,"call_target",cid))
        if kind=="class":
            for base in node.bases:
                base_name=_name(base)
                if base_name:
                    edges.append((cid,"symbol:"+base_name,"INHERITS"))
                    entities.append(("symbol:"+base_name,base_name,"base",cid))
    return rows,edges,entities


def _read_doc(path, rel):
    source=path.read_text(encoding="utf-8",errors="replace")
    file_id=_id(rel,"doc",rel); rows=[(file_id,rel,"document",rel,source)]; edges=[]
    matches=list(re.finditer(r"(?m)^#{1,6}\s+.+$",source))
    if not matches:
        parts=[(rel,source)] if source.strip() else []
    else:
        parts=[]
        for i,m in enumerate(matches):
            end=matches[i+1].start() if i+1<len(matches) else len(source)
            title=m.group(0).lstrip("# ").strip()
            body=source[m.start():end]
            parts.append((title,body))
    for i,(title,body) in enumerate(parts):
        cid=_id(rel,"docchunk",f"{i}:{title}")
        rows.append((cid,rel,"docchunk",title,body));edges.append((cid,file_id,"PART_OF"))
    return rows,edges,[]


def build_index(root, database):
    root=Path(root).resolve(); database=Path(database)
    candidates=sorted(p for p in root.rglob("*") if p.is_file() and not any(x in {".git",".venv","venv","__pycache__"} for x in p.parts))
    records=[]; relations=[]; entity_records=[]
    for path in candidates:
        rel=path.relative_to(root).as_posix()
        if path.suffix==".py": rows,edges,entities=_read_python(path,rel)
        elif path.suffix.lower() in {".md",".rst",".txt"}: rows,edges,entities=_read_doc(path,rel)
        else: continue
        records.extend(rows);relations.extend(edges);entity_records.extend(entities)
    symbols={}
    for cid,rel,kind,name,text in records:
        if kind in {"class","function"}: symbols.setdefault(name,cid)
    for cid,rel,kind,name,text in records:
        if kind in {"document","docchunk"}:
            for symbol,target in sorted(symbols.items()):
                if re.search(r"(?<![\w])"+re.escape(symbol)+r"(?![\w])",text): relations.append((cid,target,"MENTIONS"))
    database.parent.mkdir(parents=True,exist_ok=True)
    con=sqlite3.connect(database)
    try:
        con.executescript("DROP TABLE IF EXISTS chunks_fts; DROP TABLE IF EXISTS edges; DROP TABLE IF EXISTS entities; DROP TABLE IF EXISTS chunks; CREATE TABLE chunks(id TEXT PRIMARY KEY,path TEXT NOT NULL,kind TEXT NOT NULL,name TEXT NOT NULL,text TEXT NOT NULL); CREATE TABLE edges(source TEXT NOT NULL,target TEXT NOT NULL,kind TEXT NOT NULL,UNIQUE(source,target,kind)); CREATE TABLE entities(id TEXT PRIMARY KEY,name TEXT NOT NULL,kind TEXT NOT NULL,source_chunk TEXT NOT NULL); CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED,path UNINDEXED,kind UNINDEXED,name,text,tokenize='unicode61');")
        con.executemany("INSERT INTO chunks VALUES(?,?,?,?,?)",records)
        con.executemany("INSERT OR IGNORE INTO edges VALUES(?,?,?)",relations)
        con.executemany("INSERT OR IGNORE INTO entities VALUES(?,?,?,?)",entity_records)
        con.executemany("INSERT INTO chunks_fts(id,path,kind,name,text) VALUES(?,?,?,?,?)",records)
        con.commit()
    finally: con.close()
    return len(records)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root",required=True);parser.add_argument("--database",required=True)
    args=parser.parse_args(); print(f"indexed_chunks={build_index(args.root,args.database)}")
if __name__=="__main__":main()
