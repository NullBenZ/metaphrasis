#!/usr/bin/env bash
set -euo pipefail
usage() { echo "usage: $0 --destination DIR [--commit-file FILE] [--repository URL]" >&2; exit 2; }
destination=""; commit_file="DEVITO_COMMIT"; repository="https://github.com/devitocodes/devito.git"
while (($#)); do
  case "$1" in
    --destination) (($# >= 2)) || usage; destination="$2"; shift 2 ;;
    --commit-file) (($# >= 2)) || usage; commit_file="$2"; shift 2 ;;
    --repository) (($# >= 2)) || usage; repository="$2"; shift 2 ;;
    *) usage ;;
  esac
done
[[ -n "$destination" ]] || usage
[[ -f "$commit_file" ]] || { echo "commit file not found: $commit_file" >&2; exit 2; }
commit="$(tr -d '[:space:]' < "$commit_file")"
[[ "$commit" =~ ^[0-9a-f]{40}$ ]] || { echo "invalid 40-character commit in $commit_file" >&2; exit 2; }
git clone --filter=blob:none --no-checkout --branch main "$repository" "$destination"
git -C "$destination" checkout --detach "$commit"
[[ "$(git -C "$destination" rev-parse HEAD)" == "$commit" ]]
echo "Devito pinned at $commit"
