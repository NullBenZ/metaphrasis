#include "topk.hpp"
#include <cassert>
#include <cmath>
#include <iostream>

using namespace localgraph;
int main() {
    // Hand check: A=(1,0), B=(.8,.6), C=(0,1), D=0. For K=1,
    // A-B=.8 and B-C=.6; A and B select each other, C selects B.
    // Union gives {A-B,B-C}, while mutual gives only {A-B}.
    SparseVectors x{{"A", {{0,1.0}}}, {"B", {{0,.8},{1,.6}}},
                    {"C", {{1,1.0}}}, {"D", {}}};
    auto u = make_topk(x, 1, false, false, 2);
    assert(u.size() == 2);
    assert(u[0].a == 0 && u[0].b == 1 && std::abs(u[0].weight-.8)<1e-12);
    assert(u[1].a == 1 && u[1].b == 2 && std::abs(u[1].weight-.6)<1e-12);
    auto m = make_topk(x, 1, true, false, 1);
    assert(m.size() == 1 && m[0].a == 0 && m[0].b == 1);
    auto dense = make_topk(x, 1, false, true, 1);
    assert(dense.size() == 2);
    // Equal scores resolve by stable ascending row index; duplicate vectors remain distinct.
    SparseVectors dup{{"x",{{0,1}}},{"y",{{0,1}}},{"z",{{0,1}}}};
    auto tie = make_topk(dup, 1, false, false, 1);
    assert(tie.size() == 2 && tie[0].a == 0 && tie[0].b == 1 && tie[1].a == 0 && tie[1].b == 2);
    assert(make_topk({}, 4, false, false, 2).empty());
    std::cout << "topk hand cases passed\n";
}
