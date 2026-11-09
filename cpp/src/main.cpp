#include "topk.hpp"
#include "leiden.hpp"
#include <algorithm>
#include <fstream>
#include <iostream>
#include <sstream>
#include <stdexcept>
#include <string>
namespace {
localgraph::WeightedEdges read_edges(const std::string& path) {
    std::ifstream in(path); if(!in)throw std::runtime_error("cannot open edge file: "+path);
    localgraph::WeightedEdges e; std::string line;std::size_t ln=0;
    while(std::getline(in,line)){++ln;if(line.empty()||line[0]=='#')continue;std::istringstream ss(line);localgraph::WeightedEdge x{};if(!(ss>>x.a>>x.b>>x.weight))throw std::runtime_error("bad edge at line "+std::to_string(ln));std::string extra;if(ss>>extra)throw std::runtime_error("extra edge fields at line "+std::to_string(ln));e.push_back(x);}return e;
}
}
int main(int argc,char** argv) {
    try {
        std::string mode="topk",input,output; std::size_t k=8,threads=1,nodes=0; unsigned seed=1; double resolution=1.; bool mutual=false,dense=false;
        for(int i=1;i<argc;++i) {
            std::string a=argv[i]; auto value=[&](){if(++i>=argc) throw std::runtime_error("missing value for "+a); return std::string(argv[i]);};
            if(a=="--mode") mode=value(); else if(a=="--input") input=value(); else if(a=="--output") output=value();
            else if(a=="--k") k=std::stoull(value()); else if(a=="--threads") threads=std::stoull(value());
            else if(a=="--nodes") nodes=std::stoull(value()); else if(a=="--resolution") resolution=std::stod(value()); else if(a=="--seed") seed=static_cast<unsigned>(std::stoul(value()));
            else if(a=="--mutual") mutual=true; else if(a=="--dense") dense=true;
            else if(a=="--help") {std::cout<<"top-K: graph_tool --input vectors.sv --output graph.edges [--k K] [--threads N] [--mutual] [--dense]\nLeiden: graph_tool --mode leiden --input graph.edges --output communities.tsv --nodes N [--resolution R] [--seed S]\n";return 0;}
            else throw std::runtime_error("unknown option: "+a);
        }
        if(input.empty()||output.empty()) throw std::runtime_error("--input and --output are required");
        if(mode=="topk") {auto rows=localgraph::read_vectors(input);auto edges=localgraph::make_topk(rows,k,mutual,dense,threads);localgraph::write_edges(output,edges);std::cout<<"nodes="<<rows.size()<<" edges="<<edges.size()<<"\n";}
        else if(mode=="leiden") {auto edges=read_edges(input);localgraph::CSRGraph g(nodes,edges);auto c=localgraph::leiden(g,resolution,seed);std::ofstream out(output);if(!out)throw std::runtime_error("cannot write community file: "+output);for(std::size_t i=0;i<c.size();++i)out<<i<<'\t'<<c[i]<<'\n';std::cout<<"nodes="<<nodes<<" communities="<<(c.empty()?0:*std::max_element(c.begin(),c.end())+1)<<" modularity="<<localgraph::modularity(g,c,resolution)<<"\n";}
        else throw std::runtime_error("--mode must be topk or leiden");
    } catch(const std::exception& e) { std::cerr<<"error: "<<e.what()<<'\n'; return 2; }
}
