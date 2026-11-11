"""Fit deterministic L2-normalized TF-IDF vectors and export the .sv format."""
import argparse
import sqlite3
import numpy as np
from pathlib import Path


def export_vectors(database, output):
    try:
        from sklearn.feature_extraction.text import TfidfVectorizer
    except ImportError as exc:
        raise RuntimeError("scikit-learn is required for the TF-IDF stage") from exc
    with sqlite3.connect(database) as con:
        rows=con.execute("SELECT id,text FROM chunks ORDER BY id").fetchall()
    ids=[r[0] for r in rows]; docs=[r[1] for r in rows]
    target=Path(output);target.parent.mkdir(parents=True,exist_ok=True)
    if not docs:
        target.write_text("",encoding="utf-8");return 0
    vec=TfidfVectorizer(norm="l2",dtype=np.float64,token_pattern=r"(?u)\b\w+\b")
    try: matrix=vec.fit_transform(docs).tocsr();matrix.sort_indices()
    except ValueError as exc:
        if "empty vocabulary" not in str(exc): raise
        target.write_text("".join(f"{doc_id}\t\n" for doc_id in ids),encoding="utf-8");return len(ids)
    with target.open("w",encoding="utf-8",newline="\n") as out:
        for row,doc_id in enumerate(ids):
            fields=[]
            for p in range(matrix.indptr[row],matrix.indptr[row+1]):
                fields.append(f"{matrix.indices[p]}:{matrix.data[p]:.17g}")
            out.write(doc_id+"\t"+" ".join(fields)+"\n")
    return len(ids)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',required=True);p.add_argument('--output',required=True)
    a=p.parse_args();print(f"vector_rows={export_vectors(a.database,a.output)}")
if __name__=='__main__':main()
