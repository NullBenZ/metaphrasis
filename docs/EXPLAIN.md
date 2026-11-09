# Module walkthrough

## Ingestion (`python/metagraph/ingest.py`)

The built-in Python `ast` module divides Python source into module, class, and function chunks. Documentation is divided at Markdown headings. SQLite stores chunk text, graph edges, and an FTS5 index. `CALLS` records syntactic call targets, `INHERITS` records class bases, `PART_OF` connects chunks to their file-level chunk, and `MENTIONS` links documentation to indexed class/function names. This stage does not import or execute indexed code.

## TF-IDF (`python/metagraph/vectors.py`)

Scikit-learn assigns a stable feature vocabulary and builds L2-normalized sparse TF-IDF rows. Rows are written in chunk-ID order using the `.sv` format in `formats.md`, so the C++ graph can use row positions as node indices.

## Top-K (`cpp/src/topk.cpp`)

For each row, an independent worker compares its sparse vector against every other row, computes exact cosine similarity, and retains the best K positive scores in a bounded min-heap. A fixed tie rule orders equal scores by row index. The default output is the undirected union of directed choices; `--mutual` requires both endpoints to choose each other. `--dense` keeps every positive-similarity edge. Top-K work takes O(n²·s + n² log K) in the worst case, where s bounds sparse row length; dense output uses O(n²) edge memory, while top-K output uses O(nK) graph memory in addition to the input vectors.

## CSR and communities (`cpp/src/leiden.cpp`)

The graph is stored in compressed sparse row form: offsets, neighbor indices, and weights use O(V+E) space. The implementation performs seeded Louvain-style local moving, refines each moved community by splitting disconnected components, then contracts communities and repeats. Community labels are normalized to stable consecutive IDs. The modularity function accepts the resolution parameter. Each local pass scans nodes and their adjacency lists; practical work is near O(V+E) per pass, with map and sorting overhead. There is no tight worst-case bound on the number of passes.

The Leiden reference comparison against `leidenalg` is pending because that package is unavailable in the current environment. The implemented connectivity check and small hand-computed modularity case are covered by CTest.

## Remaining stages

Retrieval will combine FTS5 BM25, exact text matches, `MENTIONS` expansion, and top-K neighbors; it must deduplicate and rank results. The Fortran stage will parse only the five named finite-difference patterns, produce review reasons for unsupported input, and use repository-derived API names to validate generated Python. The validation stage will compare actual Fortran and Devito arrays. Benchmarks must write actual CSV/PNG measurements and must not substitute assumed results.
