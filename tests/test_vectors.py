import importlib.util
import tempfile
import unittest
from pathlib import Path
from metagraph.vectors import export_vectors

@unittest.skipUnless(importlib.util.find_spec('sklearn'), 'scikit-learn is unavailable')
class VectorCases(unittest.TestCase):
    def test_normalized_sparse_export_is_deterministic(self):
        with tempfile.TemporaryDirectory() as td:
            db=Path(td)/'x.sqlite'; out=Path(td)/'x.sv'
            import sqlite3
            c=sqlite3.connect(db);c.execute('create table chunks(id text,text text)')
            c.executemany('insert into chunks values(?,?)',[('b','heat flow'),('a','heat flow'),('z','')]);c.commit();c.close()
            export_vectors(db,out); first=out.read_text();export_vectors(db,out)
            self.assertEqual(first,out.read_text());self.assertEqual(len(first.splitlines()),3)
            self.assertIn('a\t',first)
            for line in first.splitlines():
                indices=[int(token.split(':')[0]) for token in line.split('\t')[1].split()]
                self.assertEqual(indices,sorted(set(indices)))

if __name__=='__main__':unittest.main()
