import sqlite3
import tempfile
import unittest
from pathlib import Path
from metagraph.retrieval import retrieve

class RetrievalCases(unittest.TestCase):
    def test_modes_merge_and_deduplicate(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); db=root/'db.sqlite'
            c=sqlite3.connect(db)
            c.executescript('CREATE TABLE chunks(id text,path text,kind text,name text,text text); CREATE VIRTUAL TABLE chunks_fts USING fts5(id UNINDEXED,path UNINDEXED,kind UNINDEXED,name,text); CREATE TABLE edges(source text,target text,kind text); CREATE TABLE entities(id text,name text,kind text,source_chunk text);')
            rows=[('a','a.py','function','heat_step','heat update'),('b','guide.md','docchunk','heat','heat uses TimeFunction'),('c','other.md','docchunk','wave','wave equation')]
            c.executemany('INSERT INTO chunks VALUES(?,?,?,?,?)',rows);c.executemany('INSERT INTO chunks_fts VALUES(?,?,?,?,?)',rows)
            c.execute("INSERT INTO edges VALUES('b','a','MENTIONS')");c.execute("INSERT INTO entities VALUES('symbol:heat_step','heat_step','function','a')");c.commit();c.close()
            (root/'communities.tsv').write_text('0\t0\n1\t0\n2\t1\n')
            (root/'graph.edges').write_text('0\t1\t0.8\n1\t2\t0.2\n')
            result=retrieve(db,'heat',root/'communities.tsv',root/'graph.edges',top=15)
            ids=[x['id'] for x in result]
            self.assertEqual(len(ids),len(set(ids)));self.assertIn('a',ids);self.assertIn('b',ids)

if __name__=='__main__':unittest.main()
