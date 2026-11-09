# Project plan

## Understanding of the specification

Build a local, deterministic pipeline for indexing Devito source and documentation, creating TF-IDF vectors, sparsifying them with a hand-written exact top-K algorithm, finding connected Leiden communities with hand-written Louvain/Leiden steps, and retrieving source idioms. A rule-based Fortran analyzer recognizes only the five specified finite-difference patterns. A template emitter uses API names extracted from the indexed repository and validates emitted Python with `ast`; numerical validation compares outputs from compiled Fortran and Devito. Experiments report only measurements produced by actual runs.

## Assumptions

- The input vector file is documented sparse text: one row per document, `document_id<TAB>feature_index:weight ...`; IDs are unique and features are L2-normalized by the vector stage.
- Similarities are exact sparse cosine/dot products. Zero-vector similarities are zero. Ties are resolved by ascending document ID for repeatability.
- The top-K graph uses undirected union by default; `--mutual` keeps an edge only when both endpoints select each other. `--dense` ignores K and retains all positive similarities.
- Graph files use a documented edge-list text format. The C++ implementation owns CSR storage and graph algorithms.
- Unsupported or ambiguous Fortran is reported with a source location; no fallback translation is attempted.
- Any repository commit pin, indexed API allow-list, benchmark value, or validation result must come from an actual local checkout/run. None will be fabricated.

## Environment and current blockers (2026-11-09)

Available: GCC/G++ 16.2.1, CMake 4.4.5, Git 2.56.0, SQLite FTS5.
Available Python is 3.14.9 (meets the 3.11+ requirement). Missing: gfortran, Devito, scikit-learn, pytest, matplotlib, fparser, NumPy, leidenalg, igraph.
The workspace has no Git repository metadata (`.git` is an empty, read-only directory), so commits cannot be created here. Network DNS is unavailable, so the requested pinned Devito clone cannot be fetched or pinned. Those limitations prevent a completed environment setup, actual Devito API inventory, Python pipeline installation, reference Leiden checks, and numeric Fortran/Devito validation.

## Phases

Follow the user-provided phase order and tests-first requirement. Preserve hand-written top-K and Leiden as the DAA core. If dependencies or source inputs are unavailable, keep interfaces and plain-file formats runnable where possible, and report the exact unmet validation. Do not claim project completion until all stated DONE conditions have actually been met.

## Implemented work and validation

- Phase 0: environment inspected and blockers recorded above. Devito clone/hash and commits are unavailable because of DNS and the read-only empty `.git` directory.
- Phase 1: generic AST/document chunking, SQLite FTS5, chunk edges, and symbol entities implemented. Ingestion smoke test passes. It has not been run over Devito because that source is not present.
- Phase 2: scikit-learn TF-IDF exporter and `.sv` writer implemented. Its test is skipped because scikit-learn is not installed.
- Phase 3: exact top-K, deterministic tie handling, threaded per-node work, union/mutual/dense output, plus hand tests implemented. CMake/CTest passes.
- Phase 4: CSR, modularity, seeded local moving, connectivity refinement, and community aggregation implemented. Hand modularity/planted graph tests pass. Comparison to `leidenalg` remains unverified because the reference packages are not installed; full algorithmic equivalence is not claimed.
- Phase 5: BM25, exact, MENTIONS, and graph-neighbor retrieval with community pre-screening and an evaluation harness implemented. Retrieval and metric tests pass. Draft queries were not generated because the Devito docs were not available, and relevance labels were not invented.
- Phases 6–10 are not implemented. Numeric conversion and benchmarks cannot be reported without the indexed Devito checkout, gfortran, and runtime dependencies.

No phase commits could be created: `.git` exists as an empty read-only directory, and `git status` reports that the workspace is not a Git repository.
