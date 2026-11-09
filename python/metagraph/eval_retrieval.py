"""Evaluate retrieval against reviewed JSONL relevance labels."""
import argparse
import json
from pathlib import Path
from .retrieval import retrieve


def metrics(returned, relevant):
    relevant=set(relevant); first=next((i+1 for i,key in enumerate(returned) if key in relevant),None)
    hits=sum(key in relevant for key in returned[:5])
    return {'precision_at_5':hits/5.0,
            'recall_at_5':hits/len(relevant) if relevant else 0.0,
            'mrr':1/first if first else 0.0}


def evaluate(database,queries,communities=None,graph=None,no_prescreen=False):
    totals={'precision_at_5':0.0,'recall_at_5':0.0,'mrr':0.0};count=0
    for line_no,line in enumerate(Path(queries).read_text(encoding='utf-8').splitlines(),1):
        if not line.strip():continue
        row=json.loads(line)
        if row.get('status','DRAFT')=='DRAFT' or 'relevant' not in row:continue
        result=retrieve(database,row['query'],communities,graph,no_prescreen=no_prescreen)
        score=metrics([r['id'] for r in result],row['relevant'])
        for key,value in score.items():totals[key]+=value
        count+=1
    return {'labeled_queries':count,**{k:(v/count if count else 0.0) for k,v in totals.items()}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',required=True);p.add_argument('--queries',required=True);p.add_argument('--communities');p.add_argument('--graph');p.add_argument('--no-prescreen',action='store_true')
    a=p.parse_args();print(json.dumps(evaluate(a.database,a.queries,a.communities,a.graph,a.no_prescreen),indent=2))
if __name__=='__main__':main()
