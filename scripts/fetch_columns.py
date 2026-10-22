"""For each dataset with a DataStore table on a CKAN portal, fetch the column list and row count of its main table.

Picks the most recently modified DataStore resource marked as data (QC "donnees", BC "data", ON type "data",
CA "dataset"; falls back to any DataStore resource). Appends one JSON line per dataset (the last line per dataset
counts), so a rerun resumes where it stopped, and a table already in the file is only fetched again when its
resource has changed since (run_all.sh starts a fresh file once a week). A call that times out is tried once more;
the portal's column_workers calls run at once (default 1), each followed by the 1.2 s pause.

usage: fetch_columns.py <province code> <packages.json.gz> <out.jsonl>
"""
import gzip
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from portals import PORTALS, USER_AGENT

DELAY = 1.2
TIMEOUT = 20
code, packages_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]
API = f"{PORTALS[code]['api']}/datastore_search"
WORKERS = PORTALS[code].get("column_workers", 1)
DATA_TYPES = {"donnees", "data", "dataset"}


def main_resource(p):
    ds = [r for r in p["resources"] if r.get("datastore_active") is True]
    if not ds:
        return None
    data = [r for r in ds if r.get("resource_type") in DATA_TYPES or r.get("type") == "data"] or ds
    return max(data, key=lambda r: r.get("last_modified") or r.get("metadata_modified") or "")


def changed(r):
    """When the resource last changed: a new upload moves last_modified, an edit of its metadata metadata_modified."""
    return max(filter(None, [r.get("last_modified"), r.get("metadata_modified")]), default="")


def fetch(p, r):
    url = f"{API}?{urllib.parse.urlencode({'resource_id': r['id'], 'limit': 0})}"
    rec = {"dataset_id": p["id"], "resource_id": r["id"], "resource_name": r.get("name"), "changed": changed(r)}
    for attempt in (1, 2):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
            with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
                res = json.load(resp)["result"]
            rec.pop("error", None)
            rec["total"] = res.get("total")
            rec["fields"] = [
                {"id": f["id"], "type": f.get("type"), "label": (f.get("info") or {}).get("label"),
                 "notes": (f.get("info") or {}).get("notes")}
                for f in res.get("fields", []) if f["id"] != "_id"
            ]
            break
        except Exception as e:  # keep going; record the failure
            rec["error"] = f"{type(e).__name__}: {e}"[:300]
            # an HTTP error is the server's answer; a timeout is mostly a table the server hadn't touched yet,
            # and the first try warms it, so the retry is usually quick
            if isinstance(e, urllib.error.HTTPError):
                break
        time.sleep(DELAY)
    time.sleep(DELAY)
    return rec


def up_to_date(old, r):
    """A table is kept while it's the same resource, unchanged since it was fetched, and the fetch got an answer:
    a network error (timeout, reset) is fetched again, an HTTP error is kept as the server's answer."""
    return (old is not None and old["resource_id"] == r["id"] and old.get("changed") == changed(r)
            and (not old.get("error") or old["error"].startswith("HTTPError")))


last = {}
if os.path.exists(out_path):
    with open(out_path, encoding="utf-8") as f:
        last = {rec["dataset_id"]: rec for rec in map(json.loads, filter(str.strip, f))}

packages = json.load(gzip.open(packages_path, "rt", encoding="utf-8"))
tables = [(p, main_resource(p)) for p in packages]
tables = [(p, r) for p, r in tables if r]
todo = [(p, r) for p, r in tables if not up_to_date(last.get(p["id"]), r)]
print(f"{len(tables) - len(todo)} up to date, {len(todo)} to fetch, {WORKERS} at a time", flush=True)

# workers only overlap the calls; lines are written here, in order, so a rerun still resumes cleanly
with open(out_path, "a", encoding="utf-8") as out, ThreadPoolExecutor(WORKERS) as pool:
    for i, rec in enumerate(pool.map(lambda pr: fetch(*pr), todo), 1):
        out.write(json.dumps(rec, ensure_ascii=False) + "\n")
        out.flush()
        if i % 100 == 0:
            print(f"{i}/{len(todo)}", flush=True)
print("finished", flush=True)
