"""For each dataset with a DataStore table, fetch the column list and row count of its main table.

Picks the most recently modified DataStore resource of type "donnees" (falls back to any
DataStore resource). Appends one JSON line per dataset, so a rerun resumes where it stopped.
"""
import gzip
import json
import os
import sys
import time
import urllib.parse
import urllib.request

API = "https://www.donneesquebec.ca/recherche/api/3/action/datastore_search"
DELAY = 1.2
packages_path, out_path = sys.argv[1], sys.argv[2]


def main_resource(p):
    ds = [r for r in p["resources"] if r.get("datastore_active") is True]
    if not ds:
        return None
    data = [r for r in ds if r.get("resource_type") == "donnees"] or ds
    return max(data, key=lambda r: r.get("last_modified") or r.get("metadata_modified") or "")


done = set()
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8") as f:
        done = {json.loads(line)["dataset_id"] for line in f if line.strip()}

packages = json.load(gzip.open(packages_path, "rt", encoding="utf-8"))
todo = [(p, main_resource(p)) for p in packages if p["id"] not in done]
todo = [(p, r) for p, r in todo if r]
print(f"{len(done)} already done, {len(todo)} to fetch", flush=True)

with open(out_path, "a", encoding="utf-8") as out:
    for i, (p, r) in enumerate(todo, 1):
        url = f"{API}?{urllib.parse.urlencode({'resource_id': r['id'], 'limit': 0})}"
        rec = {"dataset_id": p["id"], "resource_id": r["id"], "resource_name": r.get("name")}
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "dataset-index-builder (personal research)"})
            with urllib.request.urlopen(req, timeout=60) as resp:
                res = json.load(resp)["result"]
            rec["total"] = res.get("total")
            rec["fields"] = [
                {"id": f["id"], "type": f.get("type"), "label": (f.get("info") or {}).get("label"),
                 "notes": (f.get("info") or {}).get("notes")}
                for f in res.get("fields", []) if f["id"] != "_id"
            ]
        except Exception as e:  # keep going; record the failure
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        if i % 100 == 0:
            print(f"{i}/{len(todo)}", flush=True)
        time.sleep(DELAY)
print("finished", flush=True)
