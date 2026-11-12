import unittest
import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from metagraph.eval_labels import evaluate_rows


class LabelMetricsCases(unittest.TestCase):
    def test_metrics_use_reviewed_relevance_and_first_relevant_rank(self):
        rows=[{'query':'q','status':'REVIEWED','results':[{'id':str(i)} for i in range(8)],'relevant':['1','6']}]
        result=evaluate_rows(rows)
        self.assertEqual(result['labeled_queries'],1)
        self.assertEqual(result['precision_at_5'],0.2)
        self.assertEqual(result['recall_at_5'],0.5)
        self.assertEqual(result['mrr'],0.5)

    def test_draft_and_empty_relevance_are_not_scored(self):
        self.assertEqual(evaluate_rows([{'query':'q','status':'DRAFT','results':[],'relevant':[]}])['labeled_queries'],0)

    def test_label_cli_persists_human_decisions(self):
        from metagraph.label_queries import label
        with tempfile.TemporaryDirectory() as td:
            root=Path(td);queries=root/'queries.jsonl';labels=root/'labels.jsonl'
            queries.write_text(json.dumps({'query':'q','status':'DRAFT'})+'\n')
            results=[{'id':'a','path':'a.py','name':'a','text':'first','score':1.0},
                     {'id':'b','path':'b.py','name':'b','text':'second','score':0.5}]
            with patch('metagraph.label_queries.retrieve',return_value=results), patch('builtins.input',side_effect=['y','n']):
                self.assertTrue(label(queries,labels,root/'unused.sqlite'))
            row=json.loads(labels.read_text())
            self.assertEqual(row['status'],'REVIEWED')
            self.assertEqual(row['relevant'],['a'])
            self.assertEqual([item['id'] for item in row['results']],['a','b'])


if __name__=='__main__':unittest.main()
