"""Download a portal's full CKAN catalogue (every dataset with its resources) to <out_dir>/packages.json.gz.

usage: fetch_catalogue.py <province code> <out_dir>
"""
import gzip
import json
import os
import sys
import time
import urllib.request

from portals import PORTALS

code, out_dir = sys.argv[1], sys.argv[2]
API = PORTALS[code]["api"] + "/package_search"
ROWS = 500
out_path = os.path.join(out_dir, "packages.json.gz")


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dataset-index-builder (personal research)"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


packages = []
start = 0
while True:
    data = get(f"{API}?rows={ROWS}&start={start}&include_private=false")
    res = data["result"]
    packages.extend(res["results"])
    print(f"start={start} got={len(res['results'])} total={res['count']}", flush=True)
    start += ROWS
    if start >= res["count"] or not res["results"]:
        break
    time.sleep(3)

os.makedirs(out_dir, exist_ok=True)
with gzip.open(out_path, "wt", encoding="utf-8") as f:
    json.dump(packages, f, ensure_ascii=False)
print("saved", len(packages), "datasets to", out_path)
