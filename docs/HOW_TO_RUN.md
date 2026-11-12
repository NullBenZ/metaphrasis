# How to run the project from a clean checkout

This guide assumes Python 3.11+, C++17, CMake, Git, and gfortran are installed. On Arch Linux, the compiler package is `gcc-fortran` (it supplies `gfortran`); `libgfortran` alone is only the runtime library. The workflow is local and deterministic. It uses no hosted API or model.

Run all commands from the repository root.

Install the system toolchain for your distribution. Example commands:

```sh
# Arch Linux
sudo pacman -S --needed base-devel cmake git python python-pip gcc-fortran
# Debian/Ubuntu (choose Python 3.11 or newer on the target release)
sudo apt-get update && sudo apt-get install -y build-essential cmake git python3 python3-venv python3-dev gfortran
```

Expected: `g++ --version`, `cmake --version`, `git --version`, `python --version`, and `gfortran --version` each print an installed tool version. Python must be 3.11 or newer.

## Install Python dependencies and build the C++ tool

```sh
python -m venv .venv
.venv/bin/python -m pip install -e '.[test]'
cmake -S cpp -B build
cmake --build build
ctest --test-dir build --output-on-failure
```

Expected: editable package installation completes, CMake reports a successful build of `graph_tool`, and CTest reports both hand-case executables passing. Python tests can then run with:

```sh
GRAPH_TOOL="$PWD/build/graph_tool" PYTHONPATH=python .venv/bin/python -m pytest -q
```

Expected: pytest prints the pass count and returns exit status zero. The Leiden reference test uses the installed `leidenalg` package.

## Fetch and index the pinned Devito checkout

```sh
./scripts/clone_devito.sh --destination data/devito
```

Expected: the last line says `Devito pinned at` followed by the SHA in `DEVITO_COMMIT`. If the checkout already exists elsewhere, set `DEVITO_ROOT` to that path and skip this clone step. The shell/network must be able to reach GitHub for a new clone.

```sh
export DEVITO_ROOT="$PWD/data/devito"
export PYTHONPATH="$PWD/python:$DEVITO_ROOT"
export DEVITO_JIT_DIR="/tmp/metagraph-devito-jit"
.venv/bin/python -m metagraph.ingest --root "$DEVITO_ROOT" --database data/devito.sqlite --allowed-names data/devito.allowed_names
.venv/bin/python -m metagraph.vectors --database data/devito.sqlite --output data/devito.sv
```

Expected: ingestion prints `indexed_chunks=<count>`; vector export prints `vector_rows=<count>` with the same count. The exact number depends on the pinned checkout, but the command output is the measured value.

## Build the graph and retrieve a result

```sh
node_count="$(wc -l < data/devito.sv)"
build/graph_tool --input data/devito.sv --output data/devito.edges --k 8 --threads "$(nproc)"
build/graph_tool --mode leiden --input data/devito.edges --output data/devito.communities.tsv --nodes "$node_count" --resolution 1.0 --seed 1
.venv/bin/python -m metagraph.retrieval --database data/devito.sqlite --query 'time stepping wavefield arrays' --communities data/devito.communities.tsv --graph data/devito.edges
```

Expected: graph generation prints node and edge counts; Leiden prints node count, community count, and modularity; retrieval prints a JSON array of ranked chunks (up to 15). These values are produced by your actual run.

## Convert and numerically validate one Fortran program

```sh
DEVITO_ROOT="$DEVITO_ROOT" scripts/demo.sh fortran_samples/heat1d.f90
```

Expected: the emitter prints recognized-pattern metadata and the numeric validator prints JSON with `"status": "pass"`. If gfortran or Devito cannot run, the validator exits nonzero and prints the error; it does not create a pass result.

To run all included supported samples and print a table:

```sh
.venv/bin/python -m metagraph.validate_samples --database data/devito.sqlite --allowed-names data/devito.allowed_names --samples fortran_samples --atol 2e-6 --rtol 2e-6 --csv bench/results/conversion_validation.csv
```

Expected: one row per supported pattern with `PASS` or `FAIL`; the CSV contains measured maximum absolute errors.

## Draft-query labeling and reviewed evaluation

```sh
.venv/bin/python -m metagraph.label_queries --queries data/queries.jsonl --labels data/queries.labeled.jsonl --database data/devito.sqlite --communities data/devito.communities.tsv --graph data/devito.edges
.venv/bin/python -m metagraph.eval_labels --labels data/queries.labeled.jsonl
```

The first command presents each draft query and ranked chunk. Enter `y` or `n` for each result; enter `q` to stop and save progress. The second command reports labeled-query count, Precision@5, Recall@5, and MRR. Until you review labels, the metrics command reports zero labeled queries and zero aggregate values; those are empty-set defaults, not retrieval measurements.

## Run the generalization and benchmark suite

```sh
DEVITO_ROOT="$DEVITO_ROOT" GRAPH_TOOL="$PWD/build/graph_tool" scripts/run_all_benchmarks.sh
```

Expected: per-pattern variant pass rates and mutation-check status print first. The real-data benchmark writes CSV and PNG files beneath `bench/results`, plus machine details. It measures Devito graph subsets and the full indexed graph for top-K. To bound dense all-pairs runtime, the default dense limit is half the indexed rows (and every skip is recorded); set `DENSE_LIMIT` to the full row count to request the full dense run. Dense all-pairs work can take substantially longer and use much more disk/memory than top-K. Pre-screen recall remains blank and explicitly unscored until reviewed relevance labels are passed by setting `QUERY_LABELS=data/queries.labeled.jsonl`.

To run the generalization runner or real-graph benchmark separately, use:

```sh
.venv/bin/python scripts/generalization.py --database data/devito.sqlite --allowed-names data/devito.allowed_names --samples fortran_samples --output bench/results --seed 1
.venv/bin/python bench/real_devito_benchmarks.py --graph-tool build/graph_tool --vectors data/devito.sv --database data/devito.sqlite --queries data/queries.jsonl --output bench/results --seed 1
```

## View outputs

```sh
column -s, -t < bench/results/generalization_pass_rate.csv
column -s, -t < bench/results/devito_dense_vs_topk.csv
column -s, -t < bench/results/devito_resolution_sweep.csv
column -s, -t < bench/results/devito_thread_scaling.csv
ls bench/results/*.png
```

CSV files contain measured values; the log-log slope CSV is populated only when at least two positive observations exist. PNGs visualize those recorded measurements. The benchmark scripts do not write interpretations or assert a speedup claim.
