# Project plan and verified status

## Understanding and assumptions

Build a deterministic local pipeline: index Python and docs from a pinned Devito checkout into SQLite/FTS5; export normalized TF-IDF; build an exact, hand-written C++ top-K CSR graph; run hand-written Louvain plus Leiden refinement; retrieve with four configured modes; conservatively parse five Fortran stencil patterns; emit templates whose Devito identifiers are checked against the indexed source; and compare generated output with compiled Fortran. Benchmarks report measurements from the current machine and clearly identify synthetic inputs.

- The `.sv` format is one row per chunk ID with sorted `feature:weight` pairs. Empty rows represent zero vectors.
- Cosine weights are exact sparse dot products; nonpositive scores are omitted. Stable ID ordering resolves ties. Union symmetrization is default; `--mutual` and `--dense` are explicit modes.
- Unsupported Fortran returns a path, line, and reason. The emitter rejects non-zero-based arrays and unsupported metadata rather than guessing.
- Devito API allow-list names and idiom source paths are read from the indexed checkout.
- The numeric comparison uses `numpy.allclose`; the five fixture runs use `atol=rtol=2e-6` to allow for the Fortran fixtures' single precision.
- All generated/test outputs stay local. The user asked to be consulted before any GitHub update; none has been made.

## Environment and inputs

The current environment has GCC/G++, CMake, Git, Python 3.14 in `.venv`, gfortran, and required Python packages. Devito is cloned at `/home/shakti/devito`, commit `00e78a59c640deb8ecbf1af5125d99abb40f5a20`. The checkout is indexed in `data/devito.sqlite`; the allowed-name file is `data/devito.allowed_names`. Python commands below use `.venv/bin/python` and `PYTHONPATH=python:/home/shakti/devito` for generated scripts.

The workspace `.git` metadata is available to read. The workspace contains uncommitted project files; remote GitHub has not been updated. The latest tests pass (see final recorded run below).

## Phase status

0. **Setup:** verified compiler/tool availability, recorded the Devito commit, and documented assumptions here.
1. **Ingest:** Python AST and Markdown/RST/text chunking, entity/edge extraction, SQLite tables, and FTS5. Indexed Devito: 7,958 chunks and 48,851 edges.
2. **Vectors:** scikit-learn TF-IDF, L2 normalization, deterministic row order, sparse `.sv` export. 7,958 rows exported.
3. **Top-K:** hand-written exact sparse cosine with bounded min-heaps and worker parallelism, CSR, union/mutual/dense output. Devito top-K graph has 7,958 nodes and 47,965 edges.
4. **Leiden:** hand-written local moving, aggregation, constrained connected refinement, resolution and seed controls, modularity. Reference comparison: 100 graph-resolution cases across 20 fixed random/planted graphs, maximum absolute normalized quality difference 0.0262827; every resulting community connected. C++ hand tests pass.
5. **Retrieval:** BM25, exact text, MENTIONS expansion, and graph neighbors; community pre-screen toggle; weighted merge and top-15. Eval supports Precision@5, Recall@5 and MRR. `data/queries.jsonl` has 20 Devito-doc-derived DRAFT queries with empty relevance labels for review.
6. **Fortran analysis:** fparser recognizes the five requested stencil families using expression structure, offsets, loop bounds, coefficients and boundaries. Unsupported samples produce reasons. Unit tests pass.
7. **Emitter:** implemented templates for all five patterns. Each cites a Python file from the indexed Devito checkout. Generated Python passes AST allow-list validation.
8. **Numeric validation:** gfortran compiles and runs each fixture; generated Devito scripts run locally; arrays compare successfully. Current table is reproducible with `metagraph.validate_samples` and appears in `bench/results/conversion_validation.csv`.
9. **Benchmarks:** synthetic dense-vs-top-K, K, resolution, pre-screen, thread-scaling and retrieval measurements are saved as CSV/PNG with machine specs and fitted slopes. The benchmark CLI can also measure the five real conversion fixtures when passed the indexed DB and allow-list. No interpretation or unsupported speedup claim is made.
10. **Docs:** README, sparse formats, and module walkthrough are maintained in `README.md`, `docs/formats.md`, and `docs/EXPLAIN.md`.

## Latest verification

Run from the project root:

```sh
GRAPH_TOOL=/tmp/metaphrasis-build/graph_tool PYTHONPATH=python:/home/shakti/devito DEVITO_JIT_DIR=/tmp/metaphrasis-devito-jit .venv/bin/python -m pytest -q
ctest --test-dir /tmp/metaphrasis-build --output-on-failure
```

Observed result: 12 pytest tests passed with 15 subtests; CTest passed 2/2. Five numeric conversions passed (max absolute errors: advection 0, heat 1D 1.86265e-09, heat 2D 5.96046e-08, Jacobi Poisson 0, wave 3.72529e-09). Do not treat this as verification of arbitrary legacy Fortran; only the recognized subset is supported.

## Continuation verification (2026-11-12)

- Generalization runner: 5 deterministic variants per pattern (25 total), covering grid/time sizes, coefficients, array and loop variable names, upper case, comments, indentation, and scalar declaration style. Numeric results: 5/5 for each of the five patterns. The temporary heat-coefficient sign mutation was caught (`max_abs_error=0.12003988027572632`). CSVs: `bench/results/generalization_variants.csv`, `generalization_pass_rate.csv`, and `generalization_mutation.csv`.
- Negative analyzer cases: nonlinear stencil, unsupported boundary assignment, and explicit non-unit loop stride all return `unsupported` with file, line, and reason. Tests assert these fields.
- Real Devito benchmark: indexed vector count 7,958. Top-K graph construction completed at sizes 994, 1,989, 3,979, and 7,958. Dense completed at 994, 1,989, and 3,979; the 7,958-row dense size is recorded as skipped under the configured limit after a separate full-size attempt did not complete. At 3,979 rows: dense 56.7680 s, sampled peak RSS 1,111,888 KiB, 7,136,370 edges; top-K 11.4449 s, sampled peak RSS 12,444 KiB, 24,355 edges. Dense/top-K retrieval over 20 draft queries at the same 3,979-row comparison size measured mean 7.6361/0.1419 s, ratio 53.8035. This is a subset result, not a full-index ratio.
- K, resolution, prescreen timing, thread scaling, log-log slopes, CSV, PNG, and machine metadata are in `bench/results/devito_*.csv`, `devito_*.png`, and `devito_benchmark_metadata.json`. Resolution counts at 0.3/0.5/0.8/1.0/1.2 were 25/35/47/55/60; the measured fraction of nodes in communities of size at least two was 0.998743 at each setting. Threads 1/2/4/8/14 measured 160.138/83.589/45.092/33.152/24.026 s; corresponding speedup and efficiency are in the thread CSV. Prescreen recall is blank because no relevance labels have been reviewed.
- Query labeling and direct label metrics CLIs were added and unit-tested. The 20 draft queries remain unreviewed; real retrieval metrics and prescreen recall remain unverified.
- Clean-copy run: copied to `/tmp/metaphrasis-final-clean`; CMake/CTest, pytest (21 passed, 38 subtests), Devito index/vectors, graph, Leiden, demo, five-sample numeric table, and the all-benchmarks wrapper completed there. Fresh-environment pip installation failed because DNS could not resolve `pypi.org`; after documenting that blocker, commands used the existing workspace virtualenv via a temp symlink. The Devito clone was skipped because the pinned checkout already existed at `/home/shakti/devito` and the system had no network resolution.
- Final workspace verification: pytest 21 passed/38 subtests; CTest 2/2; `git diff --check` and shell syntax checks passed. No GitHub updates or commits were performed. `scripts/first_commit.sh` only prints local Git commands for the user to run.
