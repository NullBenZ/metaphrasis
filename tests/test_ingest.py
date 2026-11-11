import tempfile
import unittest
from pathlib import Path
from metagraph.ingest import build_index

class IngestCases(unittest.TestCase):
    def test_python_symbols_edges_and_search(self):
        with tempfile.TemporaryDirectory() as td:
            root=Path(td); (root/'a.py').write_text('from devito import Grid\nclass Base: pass\nclass Child(Base):\n    def solve(self):\n        helper()\ndef helper():\n    return Grid(shape=(8,))\n')
            (root/'guide.md').write_text('# Heat\nThe Function is used for heat equations.\n')
            db=root/'index.sqlite'
            allowed=root/'allowed.txt'
            chunks=build_index(root,db,allowed)
            self.assertGreaterEqual(chunks,4)
            import sqlite3
            con=sqlite3.connect(db)
            self.assertEqual(con.execute("select count(*) from edges where kind='INHERITS'").fetchone()[0],1)
            self.assertGreaterEqual(con.execute("select count(*) from chunks_fts where chunks_fts match 'heat'").fetchone()[0],1)
            self.assertIn('Grid',allowed.read_text().splitlines())
            con.close()

if __name__=='__main__': unittest.main()
