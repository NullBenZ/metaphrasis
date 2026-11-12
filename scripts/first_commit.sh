#!/usr/bin/env bash
# Review and run these local Git commands yourself after checking `git status`.
# This script does not run git, commit, push, or contact GitHub.
cat <<'COMMANDS'
git status --short
git add PLAN.md README.md docs python cpp tests bench data fortran_samples scripts DEVITO_COMMIT pyproject.toml requirements.txt
git diff --cached --check
git diff --cached --stat
git commit -m "Complete graph-based Fortran Devito project"
COMMANDS
