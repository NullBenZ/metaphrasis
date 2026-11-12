# Local graph-based Fortran-to-Devito converter

A deterministic, local DAA project. It indexes a pinned Devito checkout, builds TF-IDF vectors and a hand-written exact top-K CSR graph, detects communities with hand-written Louvain/Leiden, retrieves Devito idioms, converts five recognized Fortran finite-difference patterns, and numerically validates the generated script against gfortran output. It uses no LLM or runtime service.

## Install and run

Python 3.11+, a C++17 compiler, CMake, gfortran, and Git are required. These three commands install dependencies, fetch the recorded Devito revision, build the graph tool, index Devito, run retrieval inputs, and validate all five Fortran fixtures:

```sh
.venv/bin/python -m venv .venv && .venv/bin/python -m pip install -e '.[test]'
./scripts/clone_devito.sh --destination data/devito && cmake -S cpp -B build && cmake --build build
PYTHONPATH=python:data/devito .venv/bin/python -m metagraph.ingest --root data/devito --database data/devito.sqlite --allowed-names data/devito.allowed_names && PYTHONPATH=python .venv/bin/python -m metagraph.vectors --database data/devito.sqlite --output data/devito.sv && build/graph_tool --input data/devito.sv --output data/devito.edges --k 8 --threads 4 && build/graph_tool --mode leiden --input data/devito.edges --output data/devito.communities.tsv --nodes "$(wc -l < data/devito.sv)" --resolution 1.0 --seed 1 && PYTHONPATH=python:data/devito .venv/bin/python -m metagraph.validate_samples --database data/devito.sqlite --allowed-names data/devito.allowed_names --samples fortran_samples --csv bench/results/conversion_validation.csv
```

The clone script checks out `DEVITO_COMMIT`. If Devito is already cloned elsewhere, skip the clone command and point `PYTHONPATH` to that checkout; `scripts/clone_devito.sh` accepts `--destination`. Run `PYTHONPATH=python:/path/to/devito` for validation so the generated child process can import Devito.

To create communities after graph generation, use the graph node count (the number of rows in `.sv`):

```sh
build/graph_tool --mode leiden --input data/devito.edges --output data/devito.communities.tsv --nodes "$(wc -l < data/devito.sv)" --resolution 1.0 --seed 1
```

Emit and validate one sample with:

```sh
PYTHONPATH=python .venv/bin/python -m metagraph.emitter fortran_samples/heat1d.f90 --database data/devito.sqlite --allowed-names data/devito.allowed_names --output /tmp/heat1d.py
```

## Retrieval and evaluation

The four retrieval modes are BM25, exact text, `MENTIONS` expansion, and top-K similarity. Weighted scores are configurable; community pre-screening is optional. Twenty draft queries from the indexed Devito documentation are in `data/queries.jsonl`. They are marked `DRAFT` and contain empty relevance lists: review and fill those labels before interpreting metrics.

```sh
PYTHONPATH=python .venv/bin/python -m metagraph.retrieval --database data/devito.sqlite --query 'time stepping wavefield arrays' --communities data/devito.communities.tsv --graph data/devito.edges
PYTHONPATH=python .venv/bin/python -m metagraph.eval_retrieval --database data/devito.sqlite --queries data/queries.jsonl --communities data/devito.communities.tsv --graph data/devito.edges
```

## Tests and experiments

```sh
GRAPH_TOOL=build/graph_tool PYTHONPATH=python:/path/to/devito .venv/bin/python -m pytest -q
ctest --test-dir build --output-on-failure
PYTHONPATH=python .venv/bin/python bench/run_benchmarks.py --graph-tool build/graph_tool --output bench/results --seed 1 --devito-database data/devito.sqlite --allowed-names data/devito.allowed_names
```

Benchmarks write measured CSV/PNG outputs, machine specs, and fitted log-log slopes. Graph size studies use documented deterministic synthetic vectors; retrieval corpus results are synthetic and conversion measurements use the five supplied Fortran samples. No speedup claim is assumed.

See [docs/formats.md](docs/formats.md) for TSV/JSON/sparse formats and [docs/EXPLAIN.md](docs/EXPLAIN.md) for a plain-English module walkthrough. Current phase status and limitations are in [PLAN.md](PLAN.md).

For a clean-machine copy-paste walkthrough, see [docs/HOW_TO_RUN.md](docs/HOW_TO_RUN.md). Unsupported inputs and unverified cases are listed in [docs/LIMITATIONS.md](docs/LIMITATIONS.md). Review draft query relevance interactively with `python -m metagraph.label_queries`; compute reviewed metrics with `python -m metagraph.eval_labels`.
