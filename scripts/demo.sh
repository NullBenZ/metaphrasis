#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
source_file="${1:-$root/fortran_samples/heat1d.f90}"
database="${DEVITO_DATABASE:-$root/data/devito.sqlite}"
allowed="${DEVITO_ALLOWED_NAMES:-$root/data/devito.allowed_names}"
devito_root="${DEVITO_ROOT:-$root/data/devito}"
python="${PYTHON:-$root/.venv/bin/python}"
[[ -f "$database" && -f "$allowed" ]] || { echo "Devito index/allow-list missing; follow docs/HOW_TO_RUN.md first" >&2; exit 2; }
[[ -x "$python" ]] || { echo "Python not found: $python" >&2; exit 2; }
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
export PYTHONPATH="$root/python:$devito_root${PYTHONPATH:+:$PYTHONPATH}"
export DEVITO_JIT_DIR="${DEVITO_JIT_DIR:-$tmp/jit}"
"$python" -m metagraph.emitter "$source_file" --database "$database" --allowed-names "$allowed" --output "$tmp/generated.py"
"$python" -m metagraph.validate_numeric --fortran "$source_file" --devito-script "$tmp/generated.py" --atol "${ATOL:-2e-6}" --rtol "${RTOL:-2e-6}"
