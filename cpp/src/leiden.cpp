#include "leiden.hpp"
#include <algorithm>
#include <cmath>
#include <map>
#include <numeric>
#include <queue>
#include <random>
#include <set>
#include <stdexcept>
namespace localgraph {
CSRGraph::CSRGraph(std::size_t n,const WeightedEdges& edges):n_(n),offsets_(n+1,0),degree_(n,0) {
    WeightedEdges sorted=edges;
    for(const auto& e:sorted) {
        if(e.a>=n||e.b>=n||!std::isfinite(e.weight)||e.weight<0) throw std::invalid_argument("invalid weighted edge");
        if(e.weight==0) continue;
        ++offsets_[e.a+1]; ++offsets_[e.b+1]; degree_[e.a]+=e.weight; degree_[e.b]+=e.weight;
    }
    std::partial_sum(offsets_.begin(),offsets_.end(),offsets_.begin());
    neighbors_.resize(offsets_.back()); weights_.resize(offsets_.back()); auto cursor=offsets_;
    for(const auto& e:sorted) if(e.weight>0) {
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
}
std::vector<std::size_t> leiden(const CSRGraph& g,double gamma,unsigned seed) {
    if(!std::isfinite(gamma)||gamma<0) throw std::invalid_argument("resolution must be finite and nonnegative");
    const auto n=g.nodes(); if(!n)return {};
    std::vector<std::size_t> c(n);std::iota(c.begin(),c.end(),0);
    double m=0;for(std::size_t i=0;i<n;++i)m+=g.degree(i);m*=.5;
    if(m==0)return c;
    std::vector<double> totals(n);for(std::size_t i=0;i<n;++i)totals[i]=g.degree(i);
    std::vector<std::size_t> order(n);std::iota(order.begin(),order.end(),0);std::mt19937 rng(seed);
    // Louvain local moving: visit nodes in seeded order and move to the best neighboring community.
    for(std::size_t pass=0;pass<100;++pass) {
        std::shuffle(order.begin(),order.end(),rng); bool changed=false;
        for(auto u:order) {
            const auto old=c[u]; const double ku=g.degree(u); totals[old]-=ku;
            std::map<std::size_t,double> weights;
            for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p) weights[c[g.neighbors()[p]]]+=g.weights()[p];
            weights.try_emplace(old,0);
            auto best=old; double best_gain=weights[old]-gamma*ku*totals[old]/(2*m);
            for(auto [candidate,kin]:weights) {
                const double gain=kin-gamma*ku*totals[candidate]/(2*m);
                if(gain>best_gain+1e-14 || (std::abs(gain-best_gain)<=1e-14 && candidate<best)){best=candidate;best_gain=gain;}
            }
            c[u]=best;totals[best]+=ku;if(best!=old)changed=true;
        }
        if(!changed)break;
    }
    // Leiden refinement: enforce connectivity before aggregating communities.
    c=split_components(g,c);
    const auto groups=*std::max_element(c.begin(),c.end())+1;
    if(groups==n) return c;
    // Louvain aggregation contracts each refined community into a supernode.
    std::map<std::pair<std::size_t,std::size_t>,double> directed;
    for(std::size_t u=0;u<n;++u) for(auto p=g.offsets()[u];p<g.offsets()[u+1];++p) {
        auto a=c[u],b=c[g.neighbors()[p]]; if(a>b)std::swap(a,b);
        directed[{a,b}]+=g.weights()[p];
    }
    WeightedEdges coarse_edges; coarse_edges.reserve(directed.size());
    for(auto [ab,w]:directed) coarse_edges.push_back({ab.first,ab.second,w*.5});
    CSRGraph coarse(groups,coarse_edges);
    auto coarse_c=leiden(coarse,gamma,seed+0x9e3779b9u);
    for(auto& community:c) community=coarse_c[community];
    return normalize(c);
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
