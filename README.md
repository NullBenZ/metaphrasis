# Local graph-based Fortran-to-Devito converter

A deterministic, local university DAA project. The intended pipeline indexes Devito Python source and documentation, exports TF-IDF vectors, builds an exact top-K similarity graph, detects connected communities, retrieves idioms, recognizes five fixed Fortran stencils, emits Devito templates, and compares generated results with compiled Fortran.

## Current implementation status

The C++ top-K and community stages are implemented with hand-written algorithms and hand-checkable tests. Python AST/document ingestion and the scikit-learn TF-IDF exporter are implemented. The repository ingestion, retrieval, Fortran analysis, Devito emitter, numeric harness, evaluation harness, and benchmark suite are not complete. The pinned Devito checkout could not be fetched in this environment, so no API allow-list or conversion result is claimed. See [PLAN.md](PLAN.md).

## Build and run the implemented graph stages

Requirements for the graph stages: C++17 compiler and CMake.

```sh
cmake -S cpp -B build && cmake --build build
./build/graph_tool --input tests/fixtures/tiny.sv --output /tmp/graph.edges --k 1 --threads 2
./build/graph_tool --mode leiden --input /tmp/graph.edges --output /tmp/communities.tsv --nodes 4 --resolution 1.0 --seed 1
```

Use the actual number of rows in `vectors.sv` for `--nodes`. The first command builds the C++ tool; the next two run top-K and community detection. See [docs/formats.md](docs/formats.md) for the plain-text formats.

## Python stages

Python must be 3.11 or newer. Install project dependencies with `python -m pip install -r requirements.txt`. Index a repository with:

```sh
PYTHONPATH=python python -m metagraph.ingest --root /path/to/repository --database data/index.sqlite
PYTHONPATH=python python -m metagraph.vectors --database data/index.sqlite --output data/vectors.sv
```

## Tests

Run C++ tests with `ctest --test-dir build --output-on-failure`. Run Python tests with `PYTHONPATH=python python -m pytest`. Tests do not download data or use a network service.
