"""Interactively review ranked results for draft retrieval queries."""
import argparse
import json
from pathlib import Path

from .retrieval import retrieve


def label(queries_path,labels_path,database,communities=None,graph=None,top=15):
    queries=[json.loads(line) for line in Path(queries_path).read_text(encoding='utf-8').splitlines() if line.strip()]
    target=Path(labels_path);target.parent.mkdir(parents=True,exist_ok=True)
    reviewed={}
    if target.exists():
        for line in target.read_text(encoding='utf-8').splitlines():
            if line.strip():
                row=json.loads(line);reviewed[row['query']]=row
    for index,query_row in enumerate(queries,1):
        query=query_row['query']
        if query in reviewed and reviewed[query].get('status')=='REVIEWED': continue
        found=retrieve(database,query,communities,graph,top=top)
        print(f"\n[{index}/{len(queries)}] {query}")
        relevant=[];ranked=[]
        for rank,result in enumerate(found,1):
            excerpt=' '.join(result['text'].split())[:400]
            print(f"\n{rank}. {result['path']} :: {result['name']}\n   {excerpt}")
            while True:
                answer=input('Relevant? [y/n/q] ').strip().lower()
                if answer in {'y','n','q'}: break
                print('Enter y, n, or q.')
            if answer=='q':
                reviewed[query]={'query':query,'status':'DRAFT','results':ranked,'relevant':relevant,'source':query_row.get('source','')}
                target.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in reviewed.values()),encoding='utf-8')
                return False
            ranked.append({'id':result['id'],'path':result['path'],'name':result['name'],'score':result['score']})
            if answer=='y': relevant.append(result['id'])
        reviewed[query]={'query':query,'status':'REVIEWED','results':ranked,'relevant':relevant,'source':query_row.get('source','')}
        target.write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in reviewed.values()),encoding='utf-8')
    return True


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--queries',required=True);p.add_argument('--labels',required=True);p.add_argument('--database',required=True);p.add_argument('--communities');p.add_argument('--graph');p.add_argument('--top',type=int,default=15)
    a=p.parse_args();return 0 if label(a.queries,a.labels,a.database,a.communities,a.graph,a.top) else 1
if __name__=='__main__':raise SystemExit(main())
