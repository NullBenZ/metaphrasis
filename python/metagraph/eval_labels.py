"""Compute retrieval metrics from reviewed query/result JSONL labels."""
import argparse
import json
from pathlib import Path


def evaluate_rows(rows):
    totals={'precision_at_5':0.0,'recall_at_5':0.0,'mrr':0.0};count=0
    for row in rows:
        relevant=set(row.get('relevant',[]))
        if row.get('status')!='REVIEWED' or not relevant: continue
        results=row.get('results',[]);ids=[item['id'] if isinstance(item,dict) else item for item in results]
        hits=sum(item in relevant for item in ids[:5])
        first=next((i+1 for i,item in enumerate(ids) if item in relevant),None)
        totals['precision_at_5']+=hits/5.0
        totals['recall_at_5']+=hits/len(relevant)
        totals['mrr']+=1/first if first else 0.0
        count+=1
    return {'labeled_queries':count,**{k:(v/count if count else 0.0) for k,v in totals.items()}}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--labels',required=True)
    a=p.parse_args();rows=[json.loads(line) for line in Path(a.labels).read_text(encoding='utf-8').splitlines() if line.strip()]
    print(json.dumps(evaluate_rows(rows),indent=2));return 0
if __name__=='__main__':raise SystemExit(main())
