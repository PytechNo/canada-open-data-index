#!/usr/bin/env bash
# Create the public GitHub repository for this folder and push it, using the GitHub CLI.
# Requires: git, gh (logged in with `gh auth login`, "repo" scope).
set -euo pipefail
cd "$(dirname "$0")"
REPO="${1:-quebec-open-data-index}"

git init -b main
git add -A
git update-index --chmod=+x run_all.sh publish.sh
git commit -m "Quebec Open Data Index: every donneesquebec.ca dataset with freshness and quality scores"

gh repo create "$REPO" --public --source . --remote origin --push \
  --description "Searchable index of every dataset on donneesquebec.ca: contents, update frequency, freshness and a quality score."
