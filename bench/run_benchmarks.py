"""Run deterministic graph/retrieval benchmarks and save only measured results."""
import argparse,csv,json,math,os,platform,random,re,subprocess,tempfile,time
from pathlib import Path
import numpy as np
import matplotlib.pyplot as plt
from metagraph.ingest import build_index
from metagraph.vectors import export_vectors
from metagraph.retrieval import retrieve


def write_csv(path,rows):
    path.parent.mkdir(parents=True,exist_ok=True)
    fields=list(rows[0]) if rows else ['status']
    with path.open('w',newline='',encoding='utf-8') as f:
        w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)

def machine_info():
    mem=0
    try:
        for line in Path('/proc/meminfo').read_text().splitlines():
            if line.startswith('MemTotal:'):mem=int(line.split()[1])*1024;break
    except OSError:pass
    return {'platform':platform.platform(),'machine':platform.machine(),'processor':platform.processor() or next((line.split(':',1)[1].strip() for line in Path('/proc/cpuinfo').read_text().splitlines() if line.startswith('model name')),'unknown'),'logical_cpus':os.cpu_count(),'memory_bytes':mem,'python':platform.python_version()}

def make_vectors(path,n,seed,dims=48,nnz=12):
    rng=random.Random(seed)
    with path.open('w') as f:
        for i in range(n):
            features=sorted(rng.sample(range(dims),nnz))
            f.write(f'd{i:06d}\t'+' '.join(f'{j}:1' for j in features)+'\n')

def run_graph(tool,vec,graph,*,k=8,threads=1,dense=False,mutual=False,mode='topk',nodes=None,resolution=1.,seed=1):
    command=[str(tool),'--input',str(vec),'--output',str(graph)]
    if mode=='topk':
        command += ['--k',str(k),'--threads',str(threads)]
        if dense:command.append('--dense')
        if mutual:command.append('--mutual')
    else:
        command += ['--mode','leiden','--nodes',str(nodes),'--resolution',str(resolution),'--seed',str(seed)]
    t0=time.perf_counter(); proc=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    peak_kb=0
    while proc.poll() is None:
        try:
            status=Path(f'/proc/{proc.pid}/status').read_text()
            match=re.search(r'^VmRSS:\s+(\d+) kB$',status,re.MULTILINE)
            if match:peak_kb=max(peak_kb,int(match.group(1)))
        except OSError:pass
        time.sleep(.002)
    stdout,stderr=proc.communicate();elapsed=time.perf_counter()-t0
    if proc.returncode:raise RuntimeError(f'graph command failed: {stderr.strip()}')
    count=sum(1 for line in graph.read_text().splitlines() if line.strip() and not line.startswith('#'))
    return {'seconds':elapsed,'peak_rss_kb':peak_kb,'edges':count,'stdout':stdout.strip()}

def plot_lines(path,series,xlabel,ylabel,title,logx=False,logy=False):
    fig,ax=plt.subplots(figsize=(7,4.5))
    for name,points in series.items():
        if points:ax.plot([p[0] for p in points],[p[1] for p in points],marker='o',label=name)
    ax.set_xlabel(xlabel);ax.set_ylabel(ylabel);ax.set_title(title);ax.grid(True,alpha=.3);ax.legend();
    if logx:ax.set_xscale('log')
    if logy:ax.set_yscale('log')
    fig.tight_layout();fig.savefig(path,dpi=140);plt.close(fig)

def run(args):
    out=Path(args.output).resolve();out.mkdir(parents=True,exist_ok=True);tool=Path(args.graph_tool).resolve()
    (out/'machine.json').write_text(json.dumps(machine_info(),indent=2)+'\n')
    with tempfile.TemporaryDirectory(prefix='metagraph-bench-') as tmp:
        work=Path(tmp);measure=[];size_edges={};size_vectors={}
        for n in args.sizes:
            vec=work/f'v{n}.sv';make_vectors(vec,n,args.seed);size_vectors[n]=vec
            for label,dense in [('dense',True),('topk',False)]:
                graph=work/f'{label}-{n}.edges';m=run_graph(tool,vec,graph,k=args.k,threads=args.threads,dense=dense,seed=args.seed)
                size_edges[(label,n)]=m['edges'];measure.append({'experiment':'dense_vs_topk','method':label,'n':n,'k':args.k,'threads':args.threads,'seconds':m['seconds'],'peak_rss_kb':m['peak_rss_kb'],'edges':m['edges']})
        write_csv(out/'dense_vs_topk.csv',[r for r in measure if r['experiment']=='dense_vs_topk'])
        slope_rows=[]
        for method in ('dense','topk'):
            vals=[r for r in measure if r['experiment']=='dense_vs_topk' and r['method']==method]
            for metric in ('seconds','peak_rss_kb'):
                usable=[r for r in vals if r[metric]>0]
                slope=float(np.polyfit(np.log([r['n'] for r in usable]),np.log([r[metric] for r in usable]),1)[0]) if len(usable)>=2 else float('nan')
                slope_rows.append({'experiment':'dense_vs_topk','measure':metric,'method':method,'log_log_slope':slope})
        write_csv(out/'log_log_slopes.csv',slope_rows)
        plot_lines(out/'dense_vs_topk.png',{'dense':[(r['n'],r['seconds']) for r in measure if r['method']=='dense'],'top-K':[(r['n'],r['seconds']) for r in measure if r['method']=='topk']},'documents n','seconds','Dense versus top-K time',True,True)
        plot_lines(out/'dense_vs_topk_memory.png',{'dense':[(r['n'],max(1,r['peak_rss_kb'])) for r in measure if r['method']=='dense'],'top-K':[(r['n'],max(1,r['peak_rss_kb'])) for r in measure if r['method']=='topk']},'documents n','peak RSS (KiB)','Dense versus top-K memory',True,True)
        n=args.sizes[-1];vec=size_vectors[n];dense_file=work/'all.edges';dense_info=run_graph(tool,vec,dense_file,dense=True,threads=args.threads,seed=args.seed);dense_count=max(1,dense_info['edges'])
        k_rows=[]
        for k in (3,5,8,16,32):
            g=work/f'k{k}.edges';m=run_graph(tool,vec,g,k=k,threads=args.threads,seed=args.seed)
            k_rows.append({'k':k,'seconds':m['seconds'],'peak_rss_kb':m['peak_rss_kb'],'edges':m['edges'],'dense_edge_retention':m['edges']/dense_count})
        kd=run_graph(tool,vec,work/'klimit.edges',dense=True,threads=args.threads,seed=args.seed)
        k_rows.append({'k':'no_limit','seconds':kd['seconds'],'peak_rss_kb':kd['peak_rss_kb'],'edges':kd['edges'],'dense_edge_retention':1.0})
        write_csv(out/'k_sweep.csv',k_rows)
        plot_lines(out/'k_sweep.png',{'time':[(i+1,r['seconds']) for i,r in enumerate(k_rows)],'edge retention':[(i+1,r['dense_edge_retention']) for i,r in enumerate(k_rows)]},'K index (1..6; 6=no limit)','measured value','K sweep')
        base_graph=work/'resolution.edges';run_graph(tool,vec,base_graph,k=args.k,threads=args.threads,seed=args.seed)
        resolution_rows=[]
        for resolution in (.3,.5,.8,1.,1.2):
            comm=work/f'c{resolution}.tsv';m=run_graph(tool,base_graph,comm,mode='leiden',nodes=n,resolution=resolution,seed=args.seed)
            memberships=[int(line.split()[1]) for line in comm.read_text().splitlines() if line.strip()]
            sizes={c:memberships.count(c) for c in set(memberships)}
            resolution_rows.append({'resolution':resolution,'communities':len(sizes),'smallest':min(sizes.values(),default=0),'largest':max(sizes.values(),default=0),'seconds':m['seconds'],'modularity':re.search(r'modularity=([-+0-9.eE]+)',m['stdout']).group(1)})
        write_csv(out/'resolution_sweep.csv',resolution_rows)
        plot_lines(out/'resolution_sweep.png',{'community count':[(r['resolution'],r['communities']) for r in resolution_rows]},'resolution','communities','Resolution sweep')
        thread_rows=[]
        for threads in sorted(set([1,2,4,8,args.threads])):
            g=work/f't{threads}.edges';m=run_graph(tool,vec,g,k=args.k,threads=threads,seed=args.seed)
            thread_rows.append({'threads':threads,'seconds':m['seconds'],'speedup':0.0,'parallel_efficiency':0.0,'peak_rss_kb':m['peak_rss_kb'],'edges':m['edges']})
        baseline=next(r['seconds'] for r in thread_rows if r['threads']==1)
        for row in thread_rows:row['speedup']=baseline/row['seconds'];row['parallel_efficiency']=row['speedup']/row['threads']
        write_csv(out/'thread_scaling.csv',thread_rows)
        plot_lines(out/'thread_scaling.png',{'top-K':[(r['threads'],r['seconds']) for r in thread_rows]},'threads','seconds','Thread scaling')
        retrieval_rows=[]
        with tempfile.TemporaryDirectory(prefix='metagraph-corpus-') as corpus_tmp:
            corpus=Path(corpus_tmp);topics={'heat':'Heat diffusion finite difference stencil','wave':'Wave propagation finite difference stencil','advect':'Upwind advection transport stencil','poisson':'Poisson Jacobi elliptic solver'}
            gold={}
            for topic,body in topics.items():
                gold[topic]=set()
                for i in range(24):
                    p=corpus/f'{topic}_{i:02d}.md';p.write_text(f'# {topic.title()} method\n{body}. Example number {i}. Grid update and boundary condition.\n')
            db=work/'synthetic.sqlite';build_index(corpus,db);sv=work/'synthetic.sv';export_vectors(db,sv);cg=work/'synthetic.edges';run_graph(tool,sv,cg,k=8,threads=args.threads,seed=args.seed)
            comm=work/'synthetic.comms';run_graph(tool,cg,comm,mode='leiden',nodes=sum(1 for _ in sv.open()),resolution=1.,seed=args.seed)
            with __import__('sqlite3').connect(db) as con:
                for topic in topics:
                    gold[topic]={row[0] for row in con.execute('select id from chunks where path like ?',(topic+'_%',))}
            pre_rows=[];metric_rows=[]
            for topic,body in topics.items():
                query={'heat':'heat diffusion','wave':'wave propagation','advect':'advection transport','poisson':'poisson jacobi'}[topic]
                for mode,off in [('prescreen',False),('no_prescreen',True)]:
                    t0=time.perf_counter();results=retrieve(db,query,comm,cg,no_prescreen=off,top=15);elapsed=time.perf_counter()-t0
                    ids=[r['id'] for r in results];hits=len(set(ids[:5])&gold[topic]);recall=hits/len(gold[topic]) if gold[topic] else 0
                    pre_rows.append({'query':query,'mode':mode,'seconds':elapsed,'recall_at_5':recall,'returned':len(ids)})
                    if mode=='no_prescreen':metric_rows.append({'query':query,'precision_at_5':hits/5,'recall_at_5':recall,'mrr':next((1/(i+1) for i,x in enumerate(ids[:5]) if x in gold[topic]),0.)})
            write_csv(out/'prescreen_speed_recall.csv',pre_rows);write_csv(out/'retrieval_metrics.csv',metric_rows)
            metric_means=[{'metric':key,'mean':sum(r[key] for r in metric_rows)/len(metric_rows)} for key in ('precision_at_5','recall_at_5','mrr')]
            write_csv(out/'retrieval_metric_means.csv',metric_means)
            fig,ax=plt.subplots(figsize=(6,4));ax.bar([x['metric'] for x in metric_means],[x['mean'] for x in metric_means]);ax.set_ylim(0,1);ax.set_ylabel('mean score');ax.set_title('Synthetic retrieval metrics');fig.tight_layout();fig.savefig(out/'retrieval_metrics.png',dpi=140);plt.close(fig)
            plot_lines(out/'prescreen_speed_recall.png',{'pre-screen':[(r['seconds'],r['recall_at_5']) for r in pre_rows if r['mode']=='prescreen'],'no pre-screen':[(r['seconds'],r['recall_at_5']) for r in pre_rows if r['mode']=='no_prescreen']},'seconds','Recall@5','Pre-screen speed versus recall')
        if args.devito_database and args.allowed_names:
            from metagraph.validate_samples import run as validate_samples
            started=time.perf_counter()
            conversion=validate_samples(args.devito_database,args.allowed_names,args.fortran_samples,args.atol,args.rtol)
            elapsed=time.perf_counter()-started
            passed=sum(row['status']=='PASS' for row in conversion)
            conversion.extend([{'pattern':'ALL','file':'','status':f'{passed}/{len(conversion)} passed','max_abs_error':None}])
            write_csv(out/'conversion_validation_status.csv',conversion)
            write_csv(out/'conversion_benchmark.csv',[{'samples':passed,'total':len(conversion)-1,'pass_rate':passed/(len(conversion)-1) if len(conversion)>1 else 0.0,'seconds':elapsed}])
        else:
            write_csv(out/'conversion_validation_status.csv',[{'status':'blocked','reason':'pass --devito-database and --allowed-names to measure local conversion fixtures'}])
    return out

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--graph-tool',required=True);p.add_argument('--output',default='bench/results');p.add_argument('--sizes',type=int,nargs='+',default=[50,100,200,400]);p.add_argument('--k',type=int,default=8);p.add_argument('--threads',type=int,default=4);p.add_argument('--seed',type=int,default=1);p.add_argument('--devito-database');p.add_argument('--allowed-names');p.add_argument('--fortran-samples',default='fortran_samples');p.add_argument('--atol',type=float,default=1e-8);p.add_argument('--rtol',type=float,default=1e-7)
    args=p.parse_args();print(run(args))
if __name__=='__main__':main()
