#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
python="${PYTHON:-$root/.venv/bin/python}"
graph_tool="${GRAPH_TOOL:-$root/build/graph_tool}"
database="${DEVITO_DATABASE:-$root/data/devito.sqlite}"
allowed="${DEVITO_ALLOWED_NAMES:-$root/data/devito.allowed_names}"
vectors="${DEVITO_VECTORS:-$root/data/devito.sv}"
devito_root="${DEVITO_ROOT:-$root/data/devito}"
output="${BENCH_OUTPUT:-$root/bench/results}"
for file in "$database" "$allowed" "$vectors"; do [[ -f "$file" ]] || { echo "Missing indexed input: $file" >&2; exit 2; }; done
[[ -x "$graph_tool" ]] || { echo "Build graph tool first: $graph_tool" >&2; exit 2; }
export PYTHONPATH="$root/python:$devito_root${PYTHONPATH:+:$PYTHONPATH}"
export DEVITO_JIT_DIR="${DEVITO_JIT_DIR:-/tmp/metagraph-devito-jit}"
export MPLCONFIGDIR="${MPLCONFIGDIR:-${TMPDIR:-/tmp}/metagraph-matplotlib}"
dense_args=()
if [[ -n "${DENSE_LIMIT:-}" ]]; then dense_args+=(--dense-limit "$DENSE_LIMIT"); fi
"$python" "$root/scripts/generalization.py" --database "$database" --allowed-names "$allowed" --samples "$root/fortran_samples" --output "$output" --seed "${SEED:-1}"
"$python" "$root/bench/real_devito_benchmarks.py" --graph-tool "$graph_tool" --vectors "$vectors" --database "$database" --queries "$root/data/queries.jsonl" --labels "${QUERY_LABELS:-$root/data/queries.labeled.jsonl}" --output "$output" --seed "${SEED:-1}" "${dense_args[@]}"
