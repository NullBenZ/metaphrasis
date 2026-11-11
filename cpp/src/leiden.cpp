#include "leiden.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <limits>
#include <numeric>
#include <queue>
#include <random>
#include <stdexcept>
namespace localgraph {
CSRGraph::CSRGraph(std::size_t n,const WeightedEdges& edges):n_(n),offsets_(n+1,0),degree_(n,0) {
    for(const auto& e:edges) {
        if(e.a>=n||e.b>=n||!std::isfinite(e.weight)||e.weight<0) throw std::invalid_argument("invalid weighted edge");
        if(e.weight==0) continue;
        ++offsets_[e.a+1]; ++offsets_[e.b+1]; degree_[e.a]+=e.weight; degree_[e.b]+=e.weight;
    }
    std::partial_sum(offsets_.begin(),offsets_.end(),offsets_.begin());
    neighbors_.resize(offsets_.back()); weights_.resize(offsets_.back()); auto cursor=offsets_;
    for(const auto& e:edges) if(e.weight>0) {
        auto x=cursor[e.a]++; neighbors_[x]=e.b; weights_[x]=e.weight;
        auto y=cursor[e.b]++; neighbors_[y]=e.a; weights_[y]=e.weight;
    }
    for(std::size_t i=0;i<n_;++i) {
        std::vector<std::pair<std::size_t,double>> row;
        for(auto p=offsets_[i];p<offsets_[i+1];++p) row.emplace_back(neighbors_[p],weights_[p]);
        std::sort(row.begin(),row.end());
        for(std::size_t j=0;j<row.size();++j) {neighbors_[offsets_[i]+j]=row[j].first;weights_[offsets_[i]+j]=row[j].second;}
    }
}
double CSRGraph::degree(std::size_t n) const {return degree_.at(n);}
double modularity(const CSRGraph& g,const std::vector<std::size_t>& c,double gamma) {
    if(c.size()!=g.nodes()||!std::isfinite(gamma)||gamma<0) throw std::invalid_argument("invalid modularity arguments");
    double m=0; for(std::size_t i=0;i<g.nodes();++i)m+=g.degree(i); m*=.5;
    if(m==0)return 0;
    std::map<std::size_t,double> total,inside;
    for(std::size_t i=0;i<g.nodes();++i) {
        total[c[i]]+=g.degree(i);
        for(auto p=g.offsets()[i];p<g.offsets()[i+1];++p) if(c[i]==c[g.neighbors()[p]]) inside[c[i]]+=g.weights()[p];
    }
    double q=0; for(auto [id,d]:total) q+=inside[id]/(2*m)-gamma*(d/(2*m))*(d/(2*m));
    return q;
}
namespace {
std::vector<std::size_t> normalize(const std::vector<std::size_t>& x) {
    std::map<std::size_t,std::size_t> ids; std::vector<std::size_t> y; y.reserve(x.size());
    for(auto v:x){auto [it,ins]=ids.emplace(v,ids.size()); y.push_back(it->second);} return y;
}
std::vector<std::size_t> split_components(const CSRGraph& g,const std::vector<std::size_t>& c) {
    std::vector<std::size_t> out(g.nodes(),static_cast<std::size_t>(-1)); std::size_t next=0;
    for(std::size_t root=0;root<g.nodes();++root) if(out[root]==static_cast<std::size_t>(-1)) {
        std::queue<std::size_t> q; q.push(root); out[root]=next;
        while(!q.empty()){auto u=q.front();q.pop();for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p){auto v=g.neighbors()[p];if(out[v]==static_cast<std::size_t>(-1)&&c[v]==c[root]){out[v]=next;q.push(v);}}} ++next;
    }
    return normalize(out);
}
double total_weight(const CSRGraph& g) {double d=0;for(std::size_t i=0;i<g.nodes();++i)d+=g.degree(i);return d*.5;}
std::vector<std::size_t> local_move(const CSRGraph& g,double gamma,unsigned seed,std::vector<std::size_t> c) {
    const auto n=g.nodes(); if(!n)return c;
    c=normalize(c); const double m=total_weight(g); if(m==0)return c;
    auto groups=*std::max_element(c.begin(),c.end())+1;
    std::vector<double> totals(groups);for(std::size_t i=0;i<n;++i)totals[c[i]]+=g.degree(i);
    std::vector<std::size_t> order(n);std::iota(order.begin(),order.end(),0);std::mt19937 rng(seed);
    for(std::size_t pass=0;pass<100;++pass) {
        std::shuffle(order.begin(),order.end(),rng); bool changed=false;
        for(auto u:order) {
            const auto old=c[u]; const double ku=g.degree(u); totals[old]-=ku;
            std::map<std::size_t,double> weights;
            for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p) {
                auto v=g.neighbors()[p]; if(v!=u) weights[c[v]]+=g.weights()[p];
            }
            weights.try_emplace(old,0);
            auto best=old; double best_gain=weights[old]-gamma*ku*totals[old]/(2*m);
            for(auto [candidate,kin]:weights) {
                const double gain=kin-gamma*ku*totals[candidate]/(2*m);
                if(gain>best_gain+1e-14){best=candidate;best_gain=gain;}
            }
            c[u]=best;totals[best]+=ku;if(best!=old)changed=true;
        }
        if(!changed)break;
    }
    return split_components(g,c);
}
bool source_connected_after_removal(const CSRGraph& g,const std::vector<std::size_t>& r,std::size_t u,std::size_t size) {
    if(size<=1)return true;
    std::size_t root=g.nodes();for(std::size_t i=0;i<g.nodes();++i)if(i!=u&&r[i]==r[u]){root=i;break;}
    if(root==g.nodes())return true;
    std::vector<bool> seen(g.nodes());std::queue<std::size_t> q;q.push(root);seen[root]=true;std::size_t count=0;
    while(!q.empty()){auto x=q.front();q.pop();++count;for(auto p=g.offsets()[x];p<g.offsets()[x+1];++p){auto v=g.neighbors()[p];if(v!=u&&!seen[v]&&r[v]==r[u]){seen[v]=true;q.push(v);}}}
    return count==size-1;
}
std::vector<std::size_t> refine(const CSRGraph& g,const std::vector<std::size_t>& parent,double gamma,unsigned seed) {
    const auto n=g.nodes();std::vector<std::size_t> r(n);std::iota(r.begin(),r.end(),0);
    const double m=total_weight(g);if(!n||m==0)return r;
    std::vector<double> totals(n);std::vector<std::size_t> sizes(n,1),order(n);std::iota(order.begin(),order.end(),0);
    for(std::size_t i=0;i<n;++i)totals[i]=g.degree(i);
    std::mt19937 rng(seed);
    // Leiden refinement starts from singleton subsets and moves only within each
    // parent community. Moves keep both the source remainder and destination connected.
    for(std::size_t pass=0;pass<100;++pass) {
        std::shuffle(order.begin(),order.end(),rng);bool changed=false;
        for(auto u:order) {
            const auto old=r[u];const double ku=g.degree(u);totals[old]-=ku;--sizes[old];
            std::map<std::size_t,double> weights;
            for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p){auto v=g.neighbors()[p];if(v!=u&&parent[v]==parent[u])weights[r[v]]+=g.weights()[p];}
            weights.try_emplace(old,0);
            auto best=old;double best_gain=weights[old]-gamma*ku*totals[old]/(2*m);
            for(auto [candidate,kin]:weights) {
                if(candidate!=old&&sizes[candidate]>0&&kin<=0)continue;
                const double gain=kin-gamma*ku*totals[candidate]/(2*m);
                if(gain>best_gain+1e-14&&source_connected_after_removal(g,r,u,sizes[old]+1)){best=candidate;best_gain=gain;}
            }
            r[u]=best;totals[best]+=ku;++sizes[best];if(best!=old)changed=true;
        }
        if(!changed)break;
    }
    return normalize(r);
}
CSRGraph aggregate(const CSRGraph& g,const std::vector<std::size_t>& r) {
    std::map<std::pair<std::size_t,std::size_t>,double> directed;
    for(std::size_t u=0;u<g.nodes();++u)for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p){auto a=r[u],b=r[g.neighbors()[p]];if(a>b)std::swap(a,b);directed[{a,b}]+=g.weights()[p];}
    WeightedEdges edges;edges.reserve(directed.size());for(auto [ab,w]:directed)edges.push_back({ab.first,ab.second,w*.5});
    return CSRGraph(r.empty()?0:*std::max_element(r.begin(),r.end())+1,edges);
}
std::vector<std::size_t> run_leiden(const CSRGraph& g,double gamma,unsigned seed,std::vector<std::size_t> initial) {
    const auto n=g.nodes();if(!n)return {};
    auto parent=local_move(g,gamma,seed,std::move(initial));
    auto refined=refine(g,parent,gamma,seed^0x85ebca6bu);
    auto groups=*std::max_element(refined.begin(),refined.end())+1;
    if(groups==n)return parent;
    CSRGraph coarse=aggregate(g,refined);
    std::vector<std::size_t> coarse_parent(groups,std::numeric_limits<std::size_t>::max());
    for(std::size_t i=0;i<n;++i)coarse_parent[refined[i]]=parent[i];
    auto upper=run_leiden(coarse,gamma,seed+0x9e3779b9u,std::move(coarse_parent));
    for(auto& x:refined)x=upper[x];
    return normalize(refined);
}
}
std::vector<std::size_t> refine_partition(const CSRGraph& g,const std::vector<std::size_t>& parent,double gamma,unsigned seed) {
    if(parent.size()!=g.nodes()||!std::isfinite(gamma)||gamma<0)throw std::invalid_argument("invalid refinement arguments");
    return refine(g,parent,gamma,seed);
}
std::vector<std::size_t> leiden(const CSRGraph& g,double gamma,unsigned seed) {
    if(!std::isfinite(gamma)||gamma<0)throw std::invalid_argument("resolution must be finite and nonnegative");
    std::vector<std::size_t> initial(g.nodes());std::iota(initial.begin(),initial.end(),0);
    return run_leiden(g,gamma,seed,std::move(initial));
}
bool connected_communities(const CSRGraph& g,const std::vector<std::size_t>& c) {
    if(c.size()!=g.nodes())return false;
    std::vector<bool> seen(g.nodes());
    for(std::size_t root=0;root<g.nodes();++root) if(!seen[root]) {
        std::queue<std::size_t> q;q.push(root);seen[root]=true;
        while(!q.empty()){auto u=q.front();q.pop();for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p){auto v=g.neighbors()[p];if(!seen[v]&&c[v]==c[root]){seen[v]=true;q.push(v);}}}
        for(std::size_t v=0;v<g.nodes();++v)if(c[v]==c[root]&&!seen[v])return false;
    } return true;
}
}
