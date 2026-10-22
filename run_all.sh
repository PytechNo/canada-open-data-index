#!/usr/bin/env bash
# Rebuild everything from scratch: sitemap list, catalogue snapshot, column lists, index, site.
# Needs Python 3.9+ and no extra packages. Takes about an hour, mostly the polite column fetch.
# A download that fails keeps its last copy in raw/ (or sitemaps/); the run carries on and lists it at the end.
set -euo pipefail
cd "$(dirname "$0")"
SNAPSHOT="${1:-$(date +%F)}"
failed=""

python scripts/crawl_sitemaps.py sitemaps/sitemap_urls.csv || failed="$failed sitemaps"
for code in QC ON BC AB YT NT NL NS NB MB SK PE CA; do
  python scripts/fetch_catalogue.py "$code" "raw/$code" || failed="$failed $code"
done
# the Quebec extras download to .new first, so a failure never replaces the last good copy
if curl -fsSL -o raw/QC/schema.json.new "https://www.donneesquebec.ca/recherche/api/3/action/scheming_dataset_schema_show?type=dataset"; then
  mv raw/QC/schema.json.new raw/QC/schema.json
else
  rm -f raw/QC/schema.json.new; failed="$failed QC-schema"
fi
# a portal that is down would answer every column call with an error, so skip it when the QC catalogue failed
if [[ " $failed " != *" QC "* ]]; then
  rm -f raw/QC/columns.jsonl.new
  if python scripts/fetch_columns.py raw/QC/packages.json.gz raw/QC/columns.jsonl.new; then
    mv raw/QC/columns.jsonl.new raw/QC/columns.jsonl
  else
    rm -f raw/QC/columns.jsonl.new; failed="$failed QC-columns"
  fi
fi
python scripts/build_index.py raw data "$SNAPSHOT"
rm -rf site/index.json site/detail
mv data/index.json data/detail site/
python scripts/make_site.py site/page.html site docs
if [ -n "$failed" ]; then
  echo "WARNING: these downloads failed and kept their last snapshot:$failed" >&2
fi
