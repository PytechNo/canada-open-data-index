"""Download a portal's full catalogue (every dataset with its files or columns) to <out_dir>/packages.json.gz.

CKAN portals: package_search records. Socrata portals: Discovery API records (one per dataset).

usage: fetch_catalogue.py <province code> <out_dir>
"""
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

from portals import PORTALS

code, out_dir = sys.argv[1], sys.argv[2]
portal = PORTALS[code]
ROWS = 500
out_path = os.path.join(out_dir, "packages.json.gz")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dataset-index-builder (personal research)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def page(start):
    """One page of the catalogue, sorted by name so pages don't shift if a dataset changes mid-download."""
    if portal["platform"] == "socrata":
        data = get(f"{portal['api']}&order=name&limit={ROWS}&offset={start}")
        return data["results"], data["resultSetSize"]
    fq = urllib.parse.quote(portal.get("fq", ""))
    res = get(f"{portal['api']}/package_search?rows={ROWS}&start={start}&include_private=false"
              f"&sort=name%20asc&fq={fq}")["result"]
    return res["results"], res["count"]


packages = []
start = 0
while True:
    results, total = page(start)
    packages.extend(results)
    print(f"start={start} got={len(results)} total={total}", flush=True)
    start += ROWS
    if start >= total or not results:
        break
    time.sleep(3)
# Socrata names aren't unique, so a page boundary between two equal names could repeat or skip one
ids = {(p.get("resource") or p)["id"] for p in packages}
if len(ids) != total:
    raise SystemExit(f"got {len(ids)} distinct datasets, catalogue says {total}: run again")

os.makedirs(out_dir, exist_ok=True)
with gzip.open(out_path, "wt", encoding="utf-8") as f:
    json.dump(packages, f, ensure_ascii=False)
print("saved", len(packages), "datasets to", out_path)
