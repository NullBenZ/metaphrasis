#pragma once
#include <cstddef>
#include <vector>
namespace localgraph {
struct WeightedEdge { std::size_t a,b; double weight; };
using WeightedEdges=std::vector<WeightedEdge>;
class CSRGraph {
public:
    CSRGraph(std::size_t nodes, const WeightedEdges& edges);
    std::size_t nodes() const { return n_; }
    const std::vector<std::size_t>& offsets() const { return offsets_; }
    const std::vector<std::size_t>& neighbors() const { return neighbors_; }
    const std::vector<double>& weights() const { return weights_; }
    double degree(std::size_t node) const;
private:
    std::size_t n_; std::vector<std::size_t> offsets_,neighbors_; std::vector<double> weights_,degree_;
};
double modularity(const CSRGraph&, const std::vector<std::size_t>& communities, double resolution);
std::vector<std::size_t> refine_partition(const CSRGraph&, const std::vector<std::size_t>& parent, double resolution, unsigned seed);
std::vector<std::size_t> leiden(const CSRGraph&, double resolution, unsigned seed);
bool connected_communities(const CSRGraph&, const std::vector<std::size_t>& communities);
}
