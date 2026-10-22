"""Download the full Données Québec CKAN catalogue (every dataset with its resources)."""
import json
import sys
import time
import urllib.request

API = "https://www.donneesquebec.ca/recherche/api/3/action/package_search"
ROWS = 500
out_path = sys.argv[1]


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

with open(out_path, "w", encoding="utf-8") as f:
    json.dump(packages, f, ensure_ascii=False)
print("saved", len(packages), "datasets to", out_path)
