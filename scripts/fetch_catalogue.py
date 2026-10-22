"""Download a portal's full catalogue (every dataset with its files or columns) to <out_dir>/packages.json.gz.

CKAN portals: package_search records. Socrata portals: Discovery API records (one per dataset).
ArcGIS Hub portals: search API items, each with its service layers ("layers": fields and last edit date)
and its formal metadata ("metadata_xml"), one polite call each.

usage: fetch_catalogue.py <province code> <out_dir>
"""
import gzip
import json
import os
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from portals import PORTALS, USER_AGENT

code, out_dir = sys.argv[1], sys.argv[2]
portal = PORTALS[code]
ROWS = 100 if portal["platform"] == "hub" else 500
DELAY = 1.2
out_path = os.path.join(out_dir, "packages.json.gz")
before = len(json.load(gzip.open(out_path, "rt", encoding="utf-8"))) if os.path.exists(out_path) else 0


def get(url, read=json.load, pause=10):
    # a 5xx or a call that hangs is usually the server catching its breath (open.canada.ca answered one catalogue
    # page with 504, the Hub search hung twice in 20 calls), so try twice more; any other HTTP error is an answer
    for attempt in (1, 2, 3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=120) as r:
                return read(r)
        except Exception as e:
            if attempt == 3 or (isinstance(e, urllib.error.HTTPError) and e.code < 500):
                raise
            print(f"retrying in {pause} s after {type(e).__name__}: {e}"[:200], flush=True)
            time.sleep(pause)


def page(start):
    """One page of the catalogue, sorted by name so pages don't shift if a dataset changes mid-download."""
    if portal["platform"] == "socrata":
        data = get(f"{portal['api']}&order=name&limit={ROWS}&offset={start}")
        return data["results"], data["resultSetSize"]
    if portal["platform"] == "hub":  # startindex counts from 1
        data = get(f"{portal['api']}?sortBy=properties.title&limit={ROWS}&startindex={start + 1}")
        return data["features"], data["numberMatched"]
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

# Hub's search index can lag weeks behind the items themselves (dates, licence text), so take each item's
# live record from ArcGIS Online, 50 ids per search
for k in range(0, len(packages) if portal["platform"] == "hub" else 0, 50):
    batch = packages[k:k + 50]
    q = urllib.parse.quote("id:(" + " OR ".join(p["id"] for p in batch) + ")")
    live = {r["id"]: r for r in get(f"https://www.arcgis.com/sharing/rest/search?f=json&num=100&q={q}")["results"]}
    for p in batch:
        p["properties"].update(live.get(p["id"], {}))
    time.sleep(DELAY)

for i, p in enumerate(packages if portal["platform"] == "hub" else [], 1):
    item = p["properties"]
    # a service item's url is the whole service, or one layer of it (…/FeatureServer/3)
    m = re.match(r"(.+/(?:Feature|Map)Server)(?:/(\d+))?/?$", item.get("url") or "")
    if m:
        try:
            res = get(urllib.parse.quote(m.group(1), safe=":/%") + "/layers?f=json")  # some urls have spaces or accents
            if "error" in res:  # ArcGIS reports errors with HTTP 200
                raise RuntimeError(res["error"])
            p["layers"] = [{k: l.get(k) for k in ("id", "name", "type", "geometryType", "editingInfo", "fields")}
                           for l in res["layers"] + res.get("tables", []) if m.group(2) in (None, str(l["id"]))]
        except Exception as e:  # keep going; record the failure
            p["layers_error"] = f"{type(e).__name__}: {e}"[:300]
        time.sleep(DELAY)
    if "Metadata" in item["typeKeywords"]:
        try:
            xml = get(f"https://www.arcgis.com/sharing/rest/content/items/{item['id']}/info/metadata/metadata.xml",
                      lambda r: r.read().decode("utf-8"))
            p["metadata_xml"] = re.sub(r"<Binary>.*?</Binary>", "", xml, flags=re.S)  # drop the embedded thumbnail
        except Exception as e:
            p["metadata_error"] = f"{type(e).__name__}: {e}"[:300]
        time.sleep(DELAY)
    if i % 25 == 0:
        print(f"{i}/{len(packages)} items", flush=True)

# a portal that suddenly lists far fewer datasets is more likely broken than cleaned up, so keep the last snapshot;
# to accept a real drop, delete <out_dir>/packages.json.gz and run again
if len(packages) < 0.9 * before:
    raise SystemExit(f"got {len(packages)} datasets, {before} last time: kept the last snapshot")
os.makedirs(out_dir, exist_ok=True)
# written next to the old one and swapped in, so a run stopped mid-write never leaves a broken snapshot
with gzip.open(out_path + ".new", "wt", encoding="utf-8") as f:
    json.dump(packages, f, ensure_ascii=False)
os.replace(out_path + ".new", out_path)
print("saved", len(packages), "datasets to", out_path)
