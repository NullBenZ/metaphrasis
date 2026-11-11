# Module walkthrough

## Ingestion (`python/metagraph/ingest.py`)

The built-in Python `ast` module divides Python source into module, class, and function chunks. Documentation is divided at Markdown headings. SQLite stores chunk text, graph edges, and an FTS5 index. `CALLS` records syntactic call targets, `INHERITS` records class bases, `PART_OF` connects chunks to their file-level chunk, and `MENTIONS` links documentation to indexed class/function names. This stage does not import or execute indexed code.

## TF-IDF (`python/metagraph/vectors.py`)

Scikit-learn assigns a stable feature vocabulary and builds L2-normalized sparse TF-IDF rows. Rows are written in chunk-ID order using the `.sv` format in `formats.md`, so the C++ graph can use row positions as node indices.

## Top-K (`cpp/src/topk.cpp`)

For each row, an independent worker compares its sparse vector against every other row, computes exact cosine similarity, and retains the best K positive scores in a bounded min-heap. A fixed tie rule orders equal scores by row index. The default output is the undirected union of directed choices; `--mutual` requires both endpoints to choose each other. `--dense` keeps every positive-similarity edge. Top-K work takes O(n²·s + n² log K) in the worst case, where s bounds sparse row length; dense output uses O(n²) edge memory, while top-K output uses O(nK) graph memory in addition to the input vectors.

## CSR and communities (`cpp/src/leiden.cpp`)

The graph is stored in compressed sparse row form: offsets, neighbor indices, and weights use O(V+E) space. The implementation performs seeded local moving, a connected Leiden refinement pass, and recursive aggregation. Refinement starts from singleton subsets inside the locally moved parent communities, and moves nodes only to adjacent refined groups within the same parent. A move is allowed only when its destination remains connected and its source remainder stays connected. The refinement groups are contracted, initialized with the parent membership, and optimized recursively. The modularity function supports the resolution parameter. Each local/refinement pass scans nodes and their adjacency lists, with additional connectivity checks when considering a refinement move; worst-case pass count is not bounded tightly.

Reference verification uses `leidenalg.RBConfigurationVertexPartition`, whose quality divided by `2m` matches the project's generalized modularity. On 100 fixed graph-resolution runs on 10 random graphs and 10 planted graphs across resolutions 0.3, 0.5, 0.8, 1.0, and 1.2, the maximum absolute modularity difference was 0.0262827 and all returned communities were connected. The reproducible check is in `tests/test_leiden_reference.py`; set `GRAPH_TOOL` to the built executable when running it.

## Retrieval and evaluation (`python/metagraph/retrieval.py`, `eval_retrieval.py`)

Retrieval combines FTS5 BM25, exact text matches, `MENTIONS` expansion, and top-K neighbors, then deduplicates by chunk ID and ranks by configurable weighted scores. The optional community pre-screen selects communities from BM25 hits. The evaluation harness consumes labeled JSONL and reports Precision@5, Recall@5, and MRR. Synthetic benchmark queries are deliberately labeled only for the synthetic corpus.

## Fortran analysis (`python/metagraph/fortran_analysis.py`)

Fparser parses the source into a Fortran AST. The analyzer reports the update expression tree, index offsets, loop bounds, fields, parameters, and source line, and accepts only the five configured stencil families. Unsupported programs return a location and reason. The fixtures exercise each family. Since this recognizer is conservative and template-oriented, it should reject a variation it cannot prove instead of treating a similar-looking expression as equivalent.

## Numeric validation (`python/metagraph/validate_numeric.py`, `validate_samples.py`)

The harness compiles a Fortran source with gfortran, runs it and the generated script in separate working directories, reads each `result.txt`, and compares array shape and values with NumPy `allclose`. `validate_samples.py` emits and tests every supported fixture and prints a pass/fail table (also optionally writing CSV). All five current fixtures passed with absolute errors below `6e-8`; run with `PYTHONPATH=python:/path/to/devito` so the generated child process can import the checkout.

## Benchmarks (`bench/run_benchmarks.py`)

The script creates deterministic synthetic sparse vectors and a synthetic four-topic corpus, measures C++ and retrieval runs, records machine details, writes CSV/PNG files, and fits log-log slopes. Synthetic graph/retrieval results are identified as such. Pass `--devito-database` and `--allowed-names` to also measure the local Fortran conversion fixtures; the CSV reports the measured number passing and elapsed time.
