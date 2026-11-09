#include "topk.hpp"
#include <algorithm>
#include <cmath>
#include <fstream>
#include <functional>
#include <limits>
#include <queue>
#include <set>
#include <sstream>
#include <stdexcept>
#include <thread>

namespace localgraph {
namespace {
using Candidate = std::pair<double,std::size_t>;
double cosine(const SparseVector& x, const SparseVector& y) {
    std::size_t i=0,j=0; double dot=0, nx=0, ny=0;
    for (auto [f,v] : x.values) nx += v*v;
    for (auto [f,v] : y.values) ny += v*v;
    while(i<x.values.size() && j<y.values.size()) {
        if(x.values[i].first<y.values[j].first) ++i;
        else if(y.values[j].first<x.values[i].first) ++j;
        else { dot += x.values[i].second*y.values[j].second; ++i; ++j; }
    }
    if(nx==0 || ny==0) return 0;
    return dot/std::sqrt(nx*ny);
}
bool better(const Candidate& x,const Candidate& y) {
    return x.first>y.first || (x.first==y.first && x.second<y.second);
}
}
SparseVectors read_vectors(const std::string& path) {
    std::ifstream in(path); if(!in) throw std::runtime_error("cannot open vector file: "+path);
    SparseVectors rows; std::set<std::string> ids; std::string line; std::size_t lineno=0;
    while(std::getline(in,line)) {
        ++lineno; if(line.empty() || line[0]=='#') continue;
        auto tab=line.find('\t'); if(tab==std::string::npos) throw std::runtime_error("expected tab at line "+std::to_string(lineno));
        SparseVector row; row.id=line.substr(0,tab);
        if(row.id.empty() || !ids.insert(row.id).second) throw std::runtime_error("empty or duplicate ID at line "+std::to_string(lineno));
        std::istringstream ss(line.substr(tab+1)); std::string tok; std::size_t previous=0; bool first=true;
        while(ss>>tok) {
            auto colon=tok.find(':'); if(colon==std::string::npos) throw std::runtime_error("bad feature at line "+std::to_string(lineno));
            std::size_t used=0; auto f=std::stoull(tok.substr(0,colon),&used);
            if(used!=colon || (!first && f<=previous)) throw std::runtime_error("features must be increasing at line "+std::to_string(lineno));
            double v=std::stod(tok.substr(colon+1));
            if(!std::isfinite(v) || v<0) throw std::runtime_error("feature weights must be finite and nonnegative");
            row.values.emplace_back(f,v); previous=f; first=false;
        }
        rows.push_back(std::move(row));
    }
    return rows;
}
std::vector<Edge> make_topk(const SparseVectors& rows,std::size_t k,bool mutual,bool dense,std::size_t threads) {
    const std::size_t n=rows.size(); if(n<2) return {};
    if(!dense && k==0) throw std::runtime_error("--k must be positive unless --dense is selected");
    if(threads==0) throw std::runtime_error("--threads must be positive");
    using Heap=std::priority_queue<Candidate,std::vector<Candidate>,decltype(&better)>;
    std::vector<std::vector<Candidate>> chosen(n);
    std::vector<Heap> heaps; heaps.reserve(n); for(std::size_t i=0;i<n;++i) heaps.emplace_back(&better);
    const std::size_t workers=std::min(threads,n);
    std::vector<std::thread> pool;
    for(std::size_t t=0;t<workers;++t) pool.emplace_back([&,t]{
        for(std::size_t i=t;i<n;i+=workers) for(std::size_t j=0;j<n;++j) {
            if(i==j) continue;
            const double s=cosine(rows[i],rows[j]); if(!(s>0)) continue;
            auto& h=heaps[i]; Candidate c{s,j};
            if(dense) { h.push(c); continue; }
            if(h.size()<k) h.push(c);
            else if(better(c,h.top())) { h.pop(); h.push(c); }
        }
    });
    for(auto& th:pool) th.join();
    std::vector<std::set<std::size_t>> selected(n);
    for(std::size_t i=0;i<n;++i) while(!heaps[i].empty()) { selected[i].insert(heaps[i].top().second); heaps[i].pop(); }
    std::vector<Edge> out;
    for(std::size_t i=0;i<n;++i) for(std::size_t j=i+1;j<n;++j) {
        const bool ij=selected[i].count(j), ji=selected[j].count(i);
        if((mutual && ij && ji) || (!mutual && (ij || ji)))
            out.push_back({i,j,cosine(rows[i],rows[j])});
    }
    std::sort(out.begin(),out.end(),[](const Edge& a,const Edge& b){return a.a<b.a || (a.a==b.a && a.b<b.b);});
    return out;
}
void write_edges(const std::string& path,const std::vector<Edge>& edges) {
    std::ofstream out(path); if(!out) throw std::runtime_error("cannot write edge file: "+path);
    out.precision(17); for(const auto& e:edges) out<<e.a<<'\t'<<e.b<<'\t'<<e.weight<<'\n';
}
}
