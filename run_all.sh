#!/usr/bin/env bash
# Rebuild everything from scratch: sitemap list, catalogue snapshot, column lists, index, site.
# Needs Python 3.9+ and no extra packages. Takes 2 to 3 hours, mostly the polite column fetch (the federal DataStore alone is 25-75 min).
# A download that fails keeps its last copy in raw/ (or sitemaps/); the run carries on and lists it at the end.
set -euo pipefail
cd "$(dirname "$0")"
SNAPSHOT="${1:-$(date +%F)}"
failed=""

python scripts/crawl_sitemaps.py sitemaps/sitemap_urls.csv || failed="$failed sitemaps"
for code in $(cd scripts && python -c "from portals import PORTALS; print(*PORTALS)"); do
  python scripts/fetch_catalogue.py "$code" "raw/$code" || failed="$failed $code"
done
# the Quebec extras download to .new first, so a failure never replaces the last good copy
if curl -fsSL -o raw/QC/schema.json.new "https://www.donneesquebec.ca/recherche/api/3/action/scheming_dataset_schema_show?type=dataset"; then
  mv raw/QC/schema.json.new raw/QC/schema.json
else
  rm -f raw/QC/schema.json.new; failed="$failed QC-schema"
fi
# DataStore columns for every CKAN portal; a portal that is down would answer every column call with an error,
# so skip it when its catalogue failed
for code in $(cd scripts && python -c "from portals import PORTALS; print(*(c for c, p in PORTALS.items() if p['platform'] == 'ckan'))"); do
  [[ " $failed " == *" $code "* ]] && continue
  rm -f "raw/$code/columns.jsonl.new"
  # the second pass only fetches the tables that timed out in the first (the federal DataStore drops a few percent)
  if python scripts/fetch_columns.py "$code" "raw/$code/packages.json.gz" "raw/$code/columns.jsonl.new" &&
     python scripts/fetch_columns.py "$code" "raw/$code/packages.json.gz" "raw/$code/columns.jsonl.new"; then
    mv "raw/$code/columns.jsonl.new" "raw/$code/columns.jsonl"
  else
    rm -f "raw/$code/columns.jsonl.new"; failed="$failed $code-columns"
  fi
done
python scripts/build_index.py raw data "$SNAPSHOT"
rm -rf site/index.json site/detail
mv data/index.json data/detail site/
python scripts/make_site.py site/page.html site docs
if [ -n "$failed" ]; then
  echo "WARNING: these downloads failed and kept their last snapshot:$failed" >&2
fi
