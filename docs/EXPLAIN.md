# Module walkthrough and complexity

Symbols: `F` is source-file characters, `A` is AST nodes, `N` is document chunks, `T` is tokens, `Z` is nonzero TF-IDF values, `V` is graph vertices, `E` is graph edges, `s` is the maximum number of nonzeros in a compared vector, `K` is the requested neighbor count, `Q` is query count, and `R` is displayed/retrieved result count. Complexity describes the current implementation, not an asymptotic claim about wall-clock performance.

## Python indexing and search data

### `python/metagraph/ingest.py`

Python source is parsed with the standard `ast` module into file, class, and function chunks. Docs are split by headings. SQLite stores chunks, syntactic `CALLS` and `INHERITS`, `PART_OF`, entities, and a full-text FTS5 table; doc-to-symbol `MENTIONS` edges are found by name matching. Parsing is O(F+A) over source. The current MENTIONS builder scans every symbol against every documentation chunk, so that phase can be O(D·S·L) where D is the number of doc chunks, S the symbol count, and L the scanned text length. Database space is O(N+E+total indexed text).

### `python/metagraph/vectors.py`

Scikit-learn creates a deterministic vocabulary and L2-normalized sparse TF-IDF rows, sorted by chunk ID. Fitting is proportional to the tokenized corpus size plus sparse matrix work; storage is O(Z+N+vocabulary size). The `.sv` serialization is described in `docs/formats.md`.

### `python/metagraph/retrieval.py`

One query combines four lists: SQLite FTS5/BM25, literal text/name matches, `MENTIONS` expansion, and top-K graph neighbors. Results are deduplicated and combined with configurable weights. Community pre-screening ranks communities represented by BM25 hits. Reading all chunk metadata costs O(N) time and space per call in this implementation; graph-based similarity reads O(E) edge records and stores candidate scores up to O(V). FTS search cost depends on index size and matching terms. `--no-prescreen` skips the community filter.

### `python/metagraph/eval_retrieval.py`

Reads labeled query JSONL, reruns retrieval, and averages Precision@5, Recall@5, and MRR. For Q queries, cost is Q retrieval calls plus O(QR) metric work. DRAFT rows are skipped.

### `python/metagraph/label_queries.py`

Runs retrieval for draft queries, presents ranked chunks for human y/n decisions, and incrementally writes reviewed rows to JSONL. Its runtime is Q retrieval calls plus human review time. Stored data is O(QR).

### `python/metagraph/eval_labels.py`

Computes Precision@5, Recall@5, and MRR directly from reviewed ranked results and relevance IDs. Runtime and input storage are O(QR). DRAFT and empty-label rows do not contribute.

## C++ graph algorithms

### `cpp/src/topk.cpp` and `cpp/include/topk.hpp`

Sparse vector rows are compared exactly by a two-pointer feature merge. The implementation writes one bounded min-heap per vertex, parallelized over vertices using the requested thread count. For maximum row sparsity s, comparison work is O(V²s) and heap work is O(V² log K); output symmetrization currently also checks vertex pairs in O(V²). For top-K, candidate/selection memory is O(VK), plus vector storage and the output edges. In `--dense`, all positive neighbors are retained, so memory can reach O(V²); it is intentionally expensive and is measured separately.

### `cpp/src/leiden.cpp` and `cpp/include/leiden.hpp`

CSR stores row offsets, neighbor IDs, and weights in O(V+E) space. Seeded Louvain local moving is followed by a constrained Leiden refinement: singleton refined subsets are initialized within parent communities; node moves require adjacency and preserve connected source/destination subsets; refined groups are contracted and optimized recursively. Modularity supports a resolution parameter. A local-moving pass is approximately O(V+E) before connectivity checks; each connectivity check can cost O(V+E), so a pass with many candidate refinement moves can reach O(V(V+E)). Aggregation is O(V+E) per level. Passes and levels are data-dependent.

The reference test compares normalized quality with `leidenalg.RBConfigurationVertexPartition` and checks community connectivity. The current fixed suite ran 100 graph-resolution comparisons over 20 random/planted weighted graphs; maximum observed absolute quality difference was 0.0262827. These are test observations, not a universal equivalence guarantee.

### `cpp/src/main.cpp`

Parses command-line flags and selects top-K or Leiden mode. Parsing is O(argument count); graph work is in the modules above. It writes plain edge or membership files and prints actual run counts.

## Fortran analysis and emission

### `python/metagraph/fortran_analysis.py`

Fparser creates the Fortran AST. The recognizer checks exact expression-tree shape, offsets, loop structure, coefficients, array metadata, and boundaries for only 1D heat, 2D heat, 1D wave, upwind advection, and Jacobi Poisson. Parse and tree-walk work is O(A) for a normal input; current assignment-to-boundary checking can add O(C·A) for C candidate updates. Unsupported code returns file, line, and reason.

### `python/metagraph/emitter.py`

Looks up a matching indexed Python source idiom in SQLite, fills the fixed pattern template from analyzer metadata, and validates generated Devito identifiers against the repository-derived allow-list with Python `ast`. Idiom lookup scans indexed Python chunks, O(P+B) where P is chunk count and B is inspected text; AST validation is O(G) for G generated syntax nodes. Unsupported input is not emitted.

### `python/metagraph/api_validation.py`

Parses Python source and checks imported Devito names and known Devito-object attributes against the allow-list. Runtime and AST storage are O(G).

### `python/metagraph/validate_numeric.py`

Compiles a Fortran program, runs it and the generated Python in separate temporary directories, loads arrays, checks shape, and uses NumPy `allclose`. Time includes compiler/JIT time and the numerical runs; memory includes the two outputs and runtimes. It produces a measured pass/fail result or an explicit blocked/error result.

### `python/metagraph/validate_samples.py`

Applies emission and numeric validation to every supported `.f90` in a fixture directory and prints a table; for P samples its work is the sum of P compile/run/compare operations. Current five base fixtures passed. The separate generalization runner currently records 5 generated variants per pattern and a mutation check in `bench/results/generalization_*.csv`.

## Experiments and scripts

### `bench/run_benchmarks.py`

Measures synthetic graph and retrieval inputs and, when given the index/allow-list, actual fixture conversions. Synthetic outputs are explicitly identified. Cost is the sum of each experiment; dense cases are quadratic in vertices and may dominate.

### `bench/real_devito_benchmarks.py`

Uses actual indexed Devito vector rows for dense/top-K size scaling, graph retrieval timing, K, Leiden resolution, and thread sweeps. It writes CSV data, plots, machine specs, and log-log slopes. Dense output can consume O(V²) time, disk, and memory. Recall values require reviewed relevance labels; when none are supplied, the CSV leaves recall blank and records that it was not scored. Complexity is the sum of each measured C++ graph build, community run, and query's O(E) graph scan.

### `scripts/generalization.py`

Deterministically generates source variants and runs analyze → emit → Fortran/Devito numeric comparison. It writes per-variant and per-pattern CSVs and checks that a sign-flipped generated heat coefficient fails validation. Runtime is the sum of all compilation, JIT, and numeric runs; scratch files are removed at exit.

### `scripts/demo.sh`, `scripts/run_all_benchmarks.sh`, `scripts/clone_devito.sh`

Shell wrappers for one conversion, the experiment suite, and fetching the pinned repository. Their cost is that of the invoked commands. `scripts/first_commit.sh` only prints local Git commands for the user; it does not run a commit or contact GitHub.
