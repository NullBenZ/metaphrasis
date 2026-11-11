#include "leiden.hpp"
#include <cassert>
#include <cmath>
#include <iostream>
using namespace localgraph;
int main(){
    // Two triangles joined by one low-weight bridge. Total edge weight m=6.1;
    // each triangle has internal weight 3 and degree sum 6.1. Thus Q at gamma=1
    // is 2*(3/6.1 - (6.1/12.2)^2) = 0.483606557..., by hand.
    WeightedEdges e{{0,1,1},{1,2,1},{0,2,1},{3,4,1},{4,5,1},{3,5,1},{2,3,.1}};
    CSRGraph g(6,e);
    assert(std::abs(modularity(g,{0,0,0,1,1,1},1.0)-0.4836065573770492)<1e-12);
    auto refined=refine_partition(g,{0,0,0,1,1,1},1.0,7);
    assert(connected_communities(g,refined));
    assert(refined[0]==refined[1] && refined[1]==refined[2]);
    assert(refined[3]==refined[4] && refined[4]==refined[5] && refined[0]!=refined[3]);
    for(std::size_t i=0;i<refined.size();++i) for(std::size_t j=0;j<refined.size();++j)
        if(refined[i]==refined[j]) assert((i<3)==(j<3));
    auto c=leiden(g,1.0,7);
    assert(connected_communities(g,c));
    assert(c[0]==c[1] && c[1]==c[2]);
    assert(c[3]==c[4] && c[4]==c[5] && c[0]!=c[3]);
    CSRGraph empty(0,{}); assert(leiden(empty,1.0,1).empty());
    CSRGraph one(1,{}); auto solo=leiden(one,1.0,1); assert(solo.size()==1 && solo[0]==0);
    CSRGraph isolated(3,{}); auto iso=leiden(isolated,.5,2); assert(connected_communities(isolated,iso));
    std::cout<<"leiden hand cases passed\n";
}
