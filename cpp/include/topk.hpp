#pragma once
#include <cstddef>
#include <string>
#include <utility>
#include <vector>
namespace localgraph {
using Feature = std::pair<std::size_t,double>;
struct SparseVector { std::string id; std::vector<Feature> values; };
using SparseVectors = std::vector<SparseVector>;
struct Edge { std::size_t a, b; double weight; };
SparseVectors read_vectors(const std::string& path);
std::vector<Edge> make_topk(const SparseVectors&, std::size_t k, bool mutual,
                            bool dense, std::size_t threads);
void write_edges(const std::string& path, const std::vector<Edge>& edges);
}
