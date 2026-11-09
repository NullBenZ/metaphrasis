# File formats

## Sparse vectors (`.sv`)

UTF-8 text, one document per line. The first tab-separated field is a unique document ID. Remaining whitespace-separated tokens are `nonnegative_integer_feature_index:finite_weight`. An empty feature list represents a zero vector. Feature indices are strictly increasing; vector rows should be L2-normalized. Lines beginning with `#` are comments.

## Weighted edge list (`.edges`)

UTF-8 text with one undirected weighted edge per line: `node_id<TAB>node_id<TAB>weight`. Node IDs are nonnegative integers. Self-edges are omitted; weights are finite and nonnegative. Isolated vertices can be declared by `# node <id>` comment records. Output ordering is deterministic by endpoint ID.

For the C++ graph tool, edge-list endpoint IDs are zero-based vertex indices in the sparse-vector file order. Isolated vertices are represented by the explicit `--nodes N` argument when running community detection. The community output is `vertex_index<TAB>community_index`, one row per vertex, with community IDs assigned deterministically for a given seed.

## Commands

- `graph_tool --input vectors.sv --output graph.edges --k K --threads N [--mutual] [--dense]`
- `graph_tool --mode leiden --input graph.edges --output communities.tsv --nodes N --resolution R --seed S`
