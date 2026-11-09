import unittest
from metagraph.eval_retrieval import metrics
class MetricCases(unittest.TestCase):
    def test_hand_computed_rankings(self):
        # Relevant IDs a,c; returned b,a,c gives P@5=2/5, R@5=1, MRR=1/2.
        got=metrics(['b','a','c'],{'a','c'})
        self.assertAlmostEqual(got['precision_at_5'],2/5)
        self.assertEqual(got['recall_at_5'],1.0)
        self.assertEqual(got['mrr'],.5)
if __name__=='__main__':unittest.main()
