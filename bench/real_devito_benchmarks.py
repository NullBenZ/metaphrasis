#!/usr/bin/env python3
"""Measure graph, retrieval, and Leiden sweeps on indexed Devito documents."""
import argparse
import csv
import json
import math
import os
import platform
import re
import subprocess
import tempfile
import time
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
from metagraph.retrieval import retrieve


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(dict.fromkeys(key for row in rows for key in row)) if rows else ['status']
    with path.open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=fields);writer.writeheader();writer.writerows(rows)


def fitted_slope(x,y):
    if len(x)<2 or len(y)!=len(x) or any(v<=0 for v in x) or any(v<=0 for v in y): return None
    return float(np.polyfit(np.log(x),np.log(y),1)[0])


def community_statistics(memberships):
    counts={}
    for community in memberships: counts[community]=counts.get(community,0)+1
    distribution={}
    for size in counts.values(): distribution[size]=distribution.get(size,0)+1
    n=len(memberships);large=sum(size for size in counts.values() if size>=2)
    return {'nodes':n,'communities':len(counts),'smallest':min(counts.values(),default=0),
            'largest':max(counts.values(),default=0),'mean_size':n/len(counts) if counts else 0.0,
            'fraction_nodes_non_singleton':large/n if n else 0.0,
            'size_distribution':';'.join(f'{size}:{distribution[size]}' for size in sorted(distribution))}


def physical_cores():
    try:
        pairs=set()
        for line in Path('/proc/cpuinfo').read_text().splitlines():
            if line.startswith(('physical id','core id')): pairs.add(line.split(':',1)[1].strip())
        # Linux exposes core/socket pairs through lscpu; prefer its stable CSV output.
        raw=subprocess.run(['lscpu','-p=SOCKET,CORE'],capture_output=True,text=True,check=True).stdout
        cores={tuple(row.split(',')) for row in raw.splitlines() if row and not row.startswith('#')}
        if cores:return len(cores)
    except (OSError,subprocess.SubprocessError): pass
    return os.cpu_count() or 1


def machine_info():
    memory=0
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'): memory=int(line.split()[1])*1024;break
    except OSError: pass
    processor=platform.processor()
    if not processor:
        try:
            processor=next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines()
                            if line.startswith('model name')),'unknown')
        except OSError: processor='unknown'
    return {'platform':platform.platform(),'machine':platform.machine(),'processor':processor,
            'logical_cpus':os.cpu_count(),'physical_cores':physical_cores(),'memory_bytes':memory,
            'python':platform.python_version()}


def measure(command, output, *, count_edges=False):
    start=time.perf_counter();process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    peak=0
    while process.poll() is None:
        try:
            status=Path(f'/proc/{process.pid}/status').read_text()
            match=re.search(r'^VmRSS:\s+(\d+) kB$',status,re.M)
            if match: peak=max(peak,int(match.group(1)))
        except OSError: pass
        time.sleep(.002)
    stdout,stderr=process.communicate();elapsed=time.perf_counter()-start
    if process.returncode: raise RuntimeError(f"command failed ({process.returncode}): {stderr.strip()}")
    edge_count=sum(1 for line in output.open() if line.strip() and not line.startswith('#')) if count_edges else None
    return {'seconds':elapsed,'sampled_peak_rss_kb':peak,'stdout':stdout.strip(),'edges':edge_count,
            'output_bytes':output.stat().st_size if output.exists() else 0}


def graph_command(tool,vector,output,*,k=8,threads=1,dense=False,mode='topk',nodes=None,resolution=1.,seed=1):
    command=[str(tool),'--input',str(vector),'--output',str(output)]
    if mode=='topk':
        command.extend(['--k',str(k),'--threads',str(threads)])
        if dense: command.append('--dense')
    else: command.extend(['--mode','leiden','--nodes',str(nodes),'--resolution',str(resolution),'--seed',str(seed)])
    return measure(command,output,count_edges=mode=='topk')


def plot(path,series,xlabel,ylabel,title,log=False):
    fig,ax=plt.subplots(figsize=(7,4.5))
    for name,points in series.items():
        if points: ax.plot([x for x,_ in points],[y for _,y in points],marker='o',label=name)
    ax.set_xlabel(xlabel);ax.set_ylabel(ylabel);ax.set_title(title);ax.grid(True,alpha=.3);ax.legend()
    if log: ax.set_xscale('log');ax.set_yscale('log')
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)


def read_queries(path):
    return [json.loads(line) for line in Path(path).read_text(encoding='utf-8').splitlines()
            if line.strip() and json.loads(line).get('status','DRAFT')=='DRAFT']


def read_labels(path):
    if not path or not Path(path).exists(): return {}
    return {row['query']:set(row.get('relevant',[])) for line in Path(path).read_text().splitlines()
            if line.strip() for row in [json.loads(line)] if row.get('status')=='REVIEWED' and row.get('relevant')}


def run(args):
    out=Path(args.output);out.mkdir(parents=True,exist_ok=True);tool=Path(args.graph_tool).resolve()
    vectors=Path(args.vectors);database=Path(args.database);n=sum(1 for line in vectors.open() if line.strip())
    rows=[line for line in vectors.read_text(encoding='utf-8').splitlines() if line.strip()]
    query_rows=read_queries(args.queries);labels=read_labels(args.labels)
    (out/'devito_machine.json').write_text(json.dumps(machine_info(),indent=2)+'\n')
    graph_rows=[];graph_paths={};slope_rows=[];resolution_rows=[];k_rows=[];thread_rows=[];retrieval_rows=[];prescreen_rows=[]
    with tempfile.TemporaryDirectory(prefix='real-devito-bench-') as temp:
        work=Path(temp)
        sizes=args.sizes if args.sizes else sorted(set([max(2,n//8),max(2,n//4),max(2,n//2),n]))
        dense_limit=min(n,args.dense_limit if args.dense_limit is not None else max(2,n//2))
        for size in sizes:
            if size<2 or size>n: raise ValueError(f'size {size} must be within [2,{n}]')
            vector=work/f'devito-{size}.sv';vector.write_text('\n'.join(rows[:size])+'\n')
            for mode,dense in [('topk',False),('dense',True)]:
                if dense and size>dense_limit:
                    graph_rows.append({'dataset':'Devito indexed documents','n':size,'method':mode,'k':'no_limit',
                                       'status':'skipped','reason':f'dense size exceeds configured limit {dense_limit}'})
                    continue
                target=work/f'{mode}-{size}.edges'
                measured=graph_command(tool,vector,target,k=args.k,threads=args.threads,dense=dense)
                graph_paths[(mode,size)]=target
                graph_rows.append({'dataset':'Devito indexed documents','n':size,'method':mode,'k':args.k,'threads':args.threads,
                                   **measured})
        write_csv(out/'devito_dense_vs_topk.csv',graph_rows)
        for method in ('dense','topk'):
            group=[row for row in graph_rows if row['method']==method and row.get('status')!='skipped']
            for metric in ('seconds','sampled_peak_rss_kb','output_bytes','edges'):
                slope=fitted_slope([r['n'] for r in group],[r[metric] for r in group])
                slope_rows.append({'dataset':'Devito indexed documents','method':method,'measure':metric,'log_log_slope':slope or ''})
        plot(out/'devito_dense_vs_topk_time.png',{'dense':[(r['n'],r['seconds']) for r in graph_rows if r['method']=='dense' and r.get('status')!='skipped'],
             'top-K':[(r['n'],r['seconds']) for r in graph_rows if r['method']=='topk']},'Devito chunks','seconds','Devito dense vs top-K runtime',True)
        plot(out/'devito_dense_vs_topk_memory.png',{'dense':[(r['n'],max(r['sampled_peak_rss_kb'],1)) for r in graph_rows if r['method']=='dense' and r.get('status')!='skipped'],
             'top-K':[(r['n'],max(r['sampled_peak_rss_kb'],1)) for r in graph_rows if r['method']=='topk']},'Devito chunks','sampled peak RSS KiB','Devito dense vs top-K memory',True)
        full_topk=graph_paths[('topk',n)]
        dense_size=max(size for mode,size in graph_paths if mode=='dense')
        full_dense=graph_paths[('dense',dense_size)]
        dense_measure=next(row for row in graph_rows if row['n']==dense_size and row['method']=='dense')
        topk_measure=next(r for r in graph_rows if r['n']==dense_size and r['method']=='topk')
        query_comparison=[]
        for row in query_rows:
            for mode,graph in [('dense',full_dense),('topk',full_topk)]:
                start=time.perf_counter();found=retrieve(database,row['query'],graph=graph,top=15,no_prescreen=True);seconds=time.perf_counter()-start
                query_comparison.append({'query':row['query'],'graph':mode,'n':dense_size,'seconds':seconds,'results':len(found)})
        write_csv(out/'devito_graph_retrieval_time.csv',query_comparison)
        avg_dense=np.mean([r['seconds'] for r in query_comparison if r['graph']=='dense']) if query_rows else 0
        avg_topk=np.mean([r['seconds'] for r in query_comparison if r['graph']=='topk']) if query_rows else 0
        ratio=avg_dense/avg_topk if avg_topk else ''
        write_csv(out/'devito_retrieval_ratio.csv',[{'queries':len(query_rows),'n':dense_size,'full_index_n':n,'dense_mean_seconds':avg_dense,'topk_mean_seconds':avg_topk,
                   'dense_over_topk_ratio':ratio,'topk_graph_edges':topk_measure['edges'],'dense_graph_edges':dense_measure['edges']}])
        plot(out/'devito_retrieval_time.png',{'dense':[(i+1,r['seconds']) for i,r in enumerate([x for x in query_comparison if x['graph']=='dense'])],
             'top-K':[(i+1,r['seconds']) for i,r in enumerate([x for x in query_comparison if x['graph']=='topk'])]},'draft query index','seconds','Devito graph retrieval')
        full_measure=next(r for r in graph_rows if r['n']==n and r['method']=='topk')
        k_rows.append({'k':args.k,'n':n,'seconds':full_measure['seconds'],'sampled_peak_rss_kb':full_measure['sampled_peak_rss_kb'],'edges':full_measure['edges']})
        for k in (3,5,8,16,32):
            if k==args.k: continue
            target=work/f'k{k}.edges';measured=graph_command(tool,vectors,target,k=k,threads=args.threads)
            k_rows.append({'k':k,'n':n,**measured})
        k_rows.append({'k':'no_limit','n':dense_size,'seconds':dense_measure['seconds'],'sampled_peak_rss_kb':dense_measure['sampled_peak_rss_kb'],'edges':dense_measure['edges']})
        k_rows.sort(key=lambda row: (6 if row['k']=='no_limit' else [3,5,8,16,32].index(row['k'])))
        write_csv(out/'devito_k_sweep.csv',k_rows)
        plot(out/'devito_k_sweep.png',{'runtime':[(i+1,row['seconds']) for i,row in enumerate(k_rows)],
             'edges':[(i+1,row['edges']) for i,row in enumerate(k_rows)]},'K setting index (last=no limit)','measured value','Devito K sweep')
        base=full_topk
        for resolution in (.3,.5,.8,1.,1.2):
            comm=work/f'community-{resolution}.tsv'
            measured=graph_command(tool,base,comm,mode='leiden',nodes=n,resolution=resolution,seed=args.seed)
            assignments=[int(line.split()[1]) for line in comm.read_text().splitlines() if line.strip()]
            resolution_rows.append({'resolution':resolution,'seconds':measured['seconds'],**community_statistics(assignments)})
        write_csv(out/'devito_resolution_sweep.csv',resolution_rows)
        plot(out/'devito_resolution_sweep.png',{'community count':[(r['resolution'],r['communities']) for r in resolution_rows],
             'fraction nodes in size>=2':[(r['resolution'],r['fraction_nodes_non_singleton']) for r in resolution_rows]},'resolution','count / fraction','Devito Leiden resolution sweep')
        community_file=work/'communities.tsv';graph_command(tool,base,community_file,mode='leiden',nodes=n,resolution=1.0,seed=args.seed)
        core=physical_cores();thread_counts=sorted(set([1,2,4,8,core]))
        for threads in thread_counts:
            target=work/f'threads-{threads}.edges';measured=graph_command(tool,vectors,target,k=args.k,threads=threads)
            thread_rows.append({'threads':threads,**measured})
        baseline=next(row['seconds'] for row in thread_rows if row['threads']==1)
        for row in thread_rows:
            row['speedup']=baseline/row['seconds'] if row['seconds'] else ''
            row['efficiency']=row['speedup']/row['threads'] if row['seconds'] else ''
        write_csv(out/'devito_thread_scaling.csv',thread_rows)
        plot(out/'devito_thread_scaling.png',{'top-K':[(r['threads'],r['seconds']) for r in thread_rows]},'threads','seconds','Devito top-K thread scaling')
        for query in query_rows:
            relevant=labels.get(query['query']); per_mode={}
            for mode,no_prescreen in [('prescreen',False),('no_prescreen',True)]:
                start=time.perf_counter();found=retrieve(database,query['query'],community_file,full_topk,top=15,no_prescreen=no_prescreen);elapsed=time.perf_counter()-start
                ids=[result['id'] for result in found]
                recall=(sum(item in relevant for item in ids[:5])/len(relevant)) if relevant else ''
                per_mode[mode]={'seconds':elapsed,'recall_at_5':recall}
            prescreen_rows.append({'query':query['query'],'prescreen_seconds':per_mode['prescreen']['seconds'],
                'no_prescreen_seconds':per_mode['no_prescreen']['seconds'],'prescreen_recall_at_5':per_mode['prescreen']['recall_at_5'],
                'no_prescreen_recall_at_5':per_mode['no_prescreen']['recall_at_5'],
                'recall_status':'reviewed labels' if relevant else 'not scored: no reviewed labels'})
    write_csv(out/'devito_log_log_slopes.csv',slope_rows)
    write_csv(out/'devito_prescreen_speed_recall.csv',prescreen_rows)
    plot(out/'devito_prescreen_speed.png',{'pre-screen':[(i+1,r['prescreen_seconds']) for i,r in enumerate(prescreen_rows)],
         'no pre-screen':[(i+1,r['no_prescreen_seconds']) for i,r in enumerate(prescreen_rows)]},'draft query index','seconds','Devito pre-screen timing')
    (out/'devito_benchmark_metadata.json').write_text(json.dumps({'dataset':'indexed Devito chunks','vector_file':str(vectors),
        'n':n,'seed':args.seed,'machine':machine_info(),'synthetic_sizes_used':False},indent=2)+'\n')
    return out


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--graph-tool',required=True);p.add_argument('--vectors',required=True);p.add_argument('--database',required=True)
    p.add_argument('--queries',default='data/queries.jsonl');p.add_argument('--labels');p.add_argument('--output',default='bench/results')
    p.add_argument('--sizes',type=int,nargs='*');p.add_argument('--dense-limit',type=int);p.add_argument('--k',type=int,default=8);p.add_argument('--threads',type=int,default=4);p.add_argument('--seed',type=int,default=1)
    args=p.parse_args();print(run(args))
if __name__=='__main__':main()
