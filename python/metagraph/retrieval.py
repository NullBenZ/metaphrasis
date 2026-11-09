"""Four-mode deterministic retrieval over the local SQLite/graph files."""
import argparse
import json
import re
import sqlite3
from pathlib import Path


def _terms(query): return re.findall(r"[\w.]+", query, flags=re.UNICODE)
def _ranked(ids, weight): return {key:weight/(rank+1) for rank,key in enumerate(ids)}

def retrieve(database, query, communities=None, graph=None, *, top=15, no_prescreen=False,
             community_count=5, weights=(1.0,.9,.8,.7)):
    if len(weights)!=4 or top<0 or community_count<1: raise ValueError('invalid retrieval settings')
    con=sqlite3.connect(database);con.row_factory=sqlite3.Row
    try:
        docs={r['id']:dict(r) for r in con.execute('SELECT id,path,kind,name,text FROM chunks')}
        terms=_terms(query)
        if not terms or not docs or top==0:return []
        fts_query=' OR '.join('"'+t.replace('"','""')+'"' for t in terms)
        bm25_rows=con.execute('SELECT id,bm25(chunks_fts) AS score FROM chunks_fts WHERE chunks_fts MATCH ? ORDER BY score,id',(fts_query,)).fetchall()
        bm25_ids=[r['id'] for r in bm25_rows if r['id'] in docs]
        selected_communities=None
        row_ids=sorted(docs);index_by_id={key:i for i,key in enumerate(row_ids)}
        if communities is not None:
            by_index={}
            for line in Path(communities).read_text().splitlines():
                if not line.strip() or line.startswith('#'):continue
                i,c=line.split()[:2];by_index[int(i)]=int(c)
            community_scores={}
            for key in bm25_ids:
                i=index_by_id.get(key,-1)
                if i in by_index:community_scores[by_index[i]]=community_scores.get(by_index[i],0)+1
            if community_scores:selected_communities={c for c,_ in sorted(community_scores.items(),key=lambda p:(-p[1],p[0]))[:community_count]}
        def allowed(key):
            if no_prescreen or selected_communities is None or communities is None:return True
            i=index_by_id.get(key)
            if i is None:return False
            return by_index.get(i) in selected_communities
        modes=[{}, {}, {}, {}]
        modes[0]=_ranked([x for x in bm25_ids if allowed(x)],weights[0])
        needle=query.casefold()
        exact=con.execute("SELECT id FROM chunks WHERE instr(lower(name||' '||text),?)>0 ORDER BY id",(needle,)).fetchall() if needle else []
        modes[1]=_ranked([r['id'] for r in exact if allowed(r['id'])],weights[1])
        entity_rows=con.execute("SELECT DISTINCT source_chunk FROM entities WHERE instr(lower(name),?)>0 ORDER BY source_chunk",(needle,)).fetchall() if needle else []
        entity_ids=[r[0] for r in entity_rows]
        target_ids=[]
        if entity_ids:
            marks=','.join('?' for _ in entity_ids)
            target_ids=[r[0] for r in con.execute(f"SELECT DISTINCT source FROM edges WHERE kind='MENTIONS' AND target IN ({marks}) ORDER BY source",entity_ids)]
        modes[2]=_ranked([x for x in target_ids if x in docs and allowed(x)],weights[2])
        if graph is not None:
            # Vector rows use chunk IDs sorted lexicographically, exactly as vectors.py exports.
            index_to_id={i:key for i,key in enumerate(row_ids)}
            seeds=set(bm25_ids)|{r['id'] for r in exact}|set(target_ids)
            candidate_scores={}
            for line in Path(graph).read_text().splitlines():
                if not line.strip() or line.startswith('#'):continue
                a,b,w=line.split()[:3];a=int(a);b=int(b);w=float(w)
                if a>=len(row_ids) or b>=len(row_ids):continue
                if index_to_id.get(a) in seeds:candidate_scores[index_to_id[b]]=max(candidate_scores.get(index_to_id[b],0),w)
                if index_to_id.get(b) in seeds:candidate_scores[index_to_id[a]]=max(candidate_scores.get(index_to_id[a],0),w)
            ordered=sorted((x for x in candidate_scores if allowed(x)),key=lambda x:(-candidate_scores[x],x))
            modes[3]={key:weights[3]*candidate_scores[key] for key in ordered}
        combined={}
        for mode in modes:
            for key,score in mode.items():combined[key]=combined.get(key,0)+score
        return [dict(docs[key],score=score) for key,score in sorted(combined.items(),key=lambda p:(-p[1],p[0]))[:top]]
    finally: con.close()


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--database',required=True);p.add_argument('--query',required=True)
    p.add_argument('--communities');p.add_argument('--graph');p.add_argument('--top',type=int,default=15);p.add_argument('--community-count',type=int,default=5)
    p.add_argument('--no-prescreen',action='store_true');p.add_argument('--bm25-weight',type=float,default=1.0);p.add_argument('--exact-weight',type=float,default=.9);p.add_argument('--concept-weight',type=float,default=.8);p.add_argument('--similarity-weight',type=float,default=.7)
    a=p.parse_args();results=retrieve(a.database,a.query,a.communities,a.graph,top=a.top,no_prescreen=a.no_prescreen,community_count=a.community_count,weights=(a.bm25_weight,a.exact_weight,a.concept_weight,a.similarity_weight))
    print(json.dumps(results,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
