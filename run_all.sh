#!/usr/bin/env bash
# Rebuild everything from scratch: sitemap list, catalogue snapshot, column lists, index, site.
# Needs Python 3.9+ and no extra packages. Takes about 30 minutes, mostly the polite column fetch.
set -euo pipefail
cd "$(dirname "$0")"
SNAPSHOT="${1:-$(date +%F)}"

python scripts/crawl_sitemaps.py sitemaps/sitemap_urls.csv
for code in QC ON BC AB YT NT NL NS NB MB SK PE; do
  python scripts/fetch_catalogue.py "$code" "raw/$code"
done
curl -sSL -o raw/QC/schema.json "https://www.donneesquebec.ca/recherche/api/3/action/scheming_dataset_schema_show?type=dataset"
rm -f raw/QC/columns.jsonl
python scripts/fetch_columns.py raw/QC/packages.json.gz raw/QC/columns.jsonl
python scripts/build_index.py raw data "$SNAPSHOT"
mv data/data.json site/data.json
python scripts/make_site.py site/page.html site/data.json docs
