#!/usr/bin/env bash
# Refresh the index: catalogue snapshots, column lists, index, CSVs, site. Needs Python 3.9+ and curl, no extra packages.
# Column lists are only fetched again for tables that changed since the last run (about 30 minutes in all), except on
# Sundays or with FULL=1, when every table is fetched again (2 to 3 hours; the federal DataStore alone is 25-75 min).
# A download that fails keeps its last copy; the run carries on, lists it at the end, and fails when a portal has had
# no new snapshot for 3 days.
# RAW_DIR (snapshots and history, default raw) and SITE_DIR (the published site, default docs) let the nightly
# container keep both on its volume.
set -euo pipefail
cd "$(dirname "$0")"
SNAPSHOT="${1:-$(date +%F)}"
RAW="${RAW_DIR:-raw}"
SITE="${SITE_DIR:-docs}"
failed=""

for code in $(cd scripts && python -c "from portals import PORTALS; print(*PORTALS)"); do
  python scripts/fetch_catalogue.py "$code" "$RAW/$code" || failed="$failed $code"
done
# the Quebec extras download to .new first, so a failure never replaces the last good copy
if curl -fsSL -A "canada-open-data-index/1.0 (+https://github.com/PytechNo/canada-open-data-index)" -o "$RAW/QC/schema.json.new" \
     "https://www.donneesquebec.ca/recherche/api/3/action/scheming_dataset_schema_show?type=dataset"; then
  mv "$RAW/QC/schema.json.new" "$RAW/QC/schema.json"
else
  rm -f "$RAW/QC/schema.json.new"; failed="$failed QC-schema"
fi
# DataStore columns for every CKAN portal; a portal that is down would answer every column call with an error,
# so skip it when its catalogue failed
for code in $(cd scripts && python -c "from portals import PORTALS; print(*(c for c, p in PORTALS.items() if p['platform'] == 'ckan'))"); do
  [[ " $failed " == *" $code "* ]] && continue
  cols="$RAW/$code/columns.jsonl"
  # once a week start afresh, which also catches row counts and column notes that change without a new upload;
  # other nights start from the last lists, so only changed tables are fetched
  if [ "${FULL:-}" = 1 ] || [ "$(date +%u)" = 7 ] || [ ! -f "$cols" ]; then rm -f "$cols.new"; else cp "$cols" "$cols.new"; fi
  # the second pass only fetches the tables that timed out in the first (the federal DataStore drops a few percent)
  if python scripts/fetch_columns.py "$code" "$RAW/$code/packages.json.gz" "$cols.new" &&
     python scripts/fetch_columns.py "$code" "$RAW/$code/packages.json.gz" "$cols.new"; then
    mv "$cols.new" "$cols"
  else
    rm -f "$cols.new"; failed="$failed $code-columns"
  fi
done
python scripts/build_index.py "$RAW" data "$SNAPSHOT"
rm -rf site/index.json site/detail
mv data/index.json data/detail site/
# one row per portal per run, so freshness can be followed over time; a second run on the same day replaces that day's rows
hist="$RAW/history.csv"
[ -f "$hist" ] || head -n 1 data/portals.csv > "$hist"
{ grep -v "^$SNAPSHOT," "$hist"; tail -n +2 data/portals.csv; } > "$hist.new"
mv "$hist.new" "$hist"
# the new site is built next to the live one and swapped in, so visitors never load half of each
rm -rf "$SITE.new" "$SITE.old"
python scripts/make_site.py site/page.html site "$SITE.new"
mkdir -p "$SITE.new/data"
cp data/datasets.csv data/files.csv data/columns.csv "$hist" "$SITE.new/data/"
if [ -d "$SITE" ]; then mv "$SITE" "$SITE.old"; fi
mv "$SITE.new" "$SITE"
rm -rf "$SITE.old"

if [ -n "$failed" ]; then
  echo "WARNING: these downloads failed and kept their last snapshot:$failed" >&2
fi
# one bad night is normal (a portal restarting); three in a row needs a person
stale=$(find "$RAW" -name packages.json.gz -mtime +2 | sed -E 's|.*[/\\]([A-Z]+)[/\\]packages\.json\.gz|\1|' | tr '\n' ' ')
if [ -n "$stale" ]; then
  echo "ERROR: no new snapshot for 3 days or more: $stale" >&2
  exit 1
fi
