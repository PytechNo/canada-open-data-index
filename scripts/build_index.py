"""Build the dataset index (page data + CSV exports) from every portal's downloaded catalogue.

usage: build_index.py <raw_root> <out_dir> <snapshot YYYY-MM-DD>
"""
import csv
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime

from normalize import FREQ, records

raw_root, out_dir, snapshot = sys.argv[1], sys.argv[2], sys.argv[3]
TODAY = date.fromisoformat(snapshot)

# MULTIPLE: BC Geographic Warehouse objects, downloaded as shapefile, CSV, file geodatabase or KML on request
OPEN_FORMATS = {"CSV", "TSV", "JSON", "GEOJSON", "XML", "GPKG", "GML", "KML", "KMZ", "SHP", "GTFS",
                "SQLITE", "ODS", "RINEX", "GEOTIFF", "TIFF", "TXT", "JSONL", "PARQUET", "LAS", "LAZ",
                "NETCDF", "GEOPACKAGE", "ATOM", "RSS", "IVT", "3DM", "JPEG2000", "ASCII GRID", "MULTIPLE"}
STRUCTURED_FORMATS = {"XLSX", "XLS", "FGDB", "GDB", "ZIP", "DWG", "DGN", "DXF", "ECW", "LYR", "QML",
                      "MDB", "ACCDB", "SAV", "DTA"}
SERVICE_FORMATS = {"WMS", "WFS", "WMTS", "ESRIREST", "API", "REST", "OGC", "WCS", "ARCGIS"}
# Licences other than Creative Commons, by title in lowercase words: 10 commercial reuse allowed,
# 3 non-commercial only, 0 no open licence. The build stops on a title that isn't listed here.
LICENCES = {
    "ogl canada 2 0": 10, "open government licence canada": 10, "statistics canada open licence": 10,
    "open government licence ontario": 10, "open government licence british columbia": 10,
    "open government licence alberta": 10, "open government licence yukon": 10,
    "open government licence northwest territories": 10, "open government licence newfoundland and labrador": 10,
    "nova scotia open government licence": 10, "new brunswick open government licence": 10,
    "canada open government licence": 10,
    "open government licence bc assessment": 10, "open government licence destination bc": 10,
    "open government licence skilledtradesbc": 10, "open government licence translink": 10,
    "open government licence municipality of north cowichan": 10, "elections bc open data licence": 10,
    "bc energy regulator open data license": 10, "open data licence for icbc information": 10,
    "open data licence office of the registrar of lobbyists for british columbia": 10,
    "open licence university of northern british columbia": 10,
    "open data commons public domain dedication and licence": 10, "apache license 2 0": 10, "other open": 10,
    # Crown copyright terms: reproduction for non-commercial purposes without asking
    "king s printer for ontario": 3, "ontario ca terms of use": 3,
    # shortcut: BC King's Printer and the old Ontario terms of use aren't checked against their full text
    "king s printer licence british columbia": 3, "ontario open data terms of use": 0,
    "public sector salary disclosure act": 0, "ministry terms of use": 0, "access only": 0, "no licence": 0,
    "licence not specified": 0, "license not specified": 0,
}
UNKNOWN_LICENCES = set()
DICT_NAME = re.compile(r"dictionnaire|description des (champs|donn|attributs|colonnes)|m[ée]tadonn[ée]es|"
                       r"structure|sch[ée]ma|data dictionary|guide|documentation|lisez", re.I)


def clean_text(s, limit=None):
    if not s:
        return ""
    s = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = re.sub(r"<br\s*/?>|</p>|</div>|</li>|</h\d>", "\n", s, flags=re.I)
    s = re.sub(r"<li[^>]*>", "\n- ", s, flags=re.I)
    s = re.sub(r"<[^>]+>", " ", s)
    s = html.unescape(s).replace("﻿", "").replace("\r", "")
    s = re.sub(r"\*\*|__", "", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", s)
    s = re.sub(r"[ \t\xa0]+", " ", s)
    s = re.sub(r" *\n *", "\n", s)
    s = re.sub(r"\n{3,}", "\n\n", s).strip()
    if limit and len(s) > limit:
        s = s[:limit].rsplit(" ", 1)[0] + " …"
    return s


def as_date(s):
    if not s:
        return None
    try:
        return datetime.fromisoformat(s[:19]).date()
    except ValueError:
        return None


def freshness(freq, last):
    label, every = FREQ.get(freq, (freq, None))
    if freq == "archives":
        return "archive", 15, None
    if last is None:
        return "unknown", 10, None
    age = (TODAY - last).days
    if every:
        if age <= every * 1.5 + 7:
            return "on_time", 25, age
        if age <= every * 3 + 14:
            return "late", 12, age
        return "overdue", 0, age
    if age <= 365:
        return "recent", 18, age
    if age <= 3 * 365:
        return "stale", 10, age
    return "old", 4, age


def licence_info(lid, title):
    l = (lid or "").lower()
    if l.startswith("cc"):
        parts = l.split("-")
        return "nc" not in parts, 3 if "nc" in parts else 6 if "nd" in parts else 10
    key = re.sub(r"[\W_]+", " ", (title or l).lower()).strip()
    if key not in LICENCES:
        UNKNOWN_LICENCES.add(title or lid)
    pts = LICENCES.get(key, 0)
    return pts >= 6, pts


recs = records(raw_root)
CHECK_LABELS = list(dict.fromkeys(label for p in recs for f in p["files"] for label in f["checks"]))

datasets, file_rows, column_rows = [], [], []
for p in recs:
    res = p["files"]
    data_res = [r for r in res if r["data"]]
    formats = sorted({r["format"] for r in res if r["format"]})
    data_formats = {r["format"] for r in data_res if r["format"]} or set(formats)

    # last data update: newest last_modified among data files, else the publisher's own data date,
    # else the files' creation date
    dated = [as_date(r["modified"]) for r in (data_res or res)]
    dated = [d for d in dated if d]
    last_src = "file modified"
    if not dated and as_date(p["data_date"]):
        dated, last_src = [as_date(p["data_date"])], "publisher's date"
    if not dated:
        dated = [d for d in (as_date(r["added"]) for r in (data_res or res)) if d]
        last_src = "file added"
    last = max(dated) if dated else None
    status, s_fresh, age = freshness(p["frequency"], last)

    # format openness
    if data_formats & OPEN_FORMATS:
        s_fmt = 15
    elif data_formats & (STRUCTURED_FORMATS | SERVICE_FORMATS):
        s_fmt = 9
    else:
        s_fmt = 0

    # API access
    datastore = any(r["queryable"] for r in res)
    service = any(r["format"] in SERVICE_FORMATS or r["service"] for r in res)
    s_api = 10 if datastore else 7 if service else 0

    # documentation
    desc = clean_text(p["description"])
    method = clean_text(p["methodology"])
    temporal = p["time_coverage"]
    email = p["email"]
    fd_vals = Counter(r["col_desc"] for r in data_res)
    dict_doc = any(r["dictionary"] or (r["doc"] and DICT_NAME.search(r["name"] or "")) for r in res)
    fields_rec = p["columns"] or {}
    labelled_cols = any((c.get("label") or c.get("notes")) for c in fields_rec.get("fields") or [])
    if fd_vals.get("Separate document") or dict_doc:
        field_desc = "Separate document"
    elif fd_vals.get("In the description") or labelled_cols:
        field_desc = "In the description"
    elif fd_vals.get("Missing"):
        field_desc = "Missing"
    else:
        field_desc = "Not stated"
    # a field the portal doesn't have gets half points (rounded up), not zero
    s_doc = (7 if len(desc) >= 400 else 4 if len(desc) >= 150 else 1 if desc else 0)
    s_doc += 8 if field_desc in ("Separate document", "In the description") else 0
    s_doc += 3 if p["methodology"] is None else 5 if len(method) >= 40 else 0
    s_doc += 2 if temporal is None else 3 if temporal else 0
    s_doc += 2 if email else 0

    # portal conformity checks on data files
    check_summary = []
    yes = no = 0
    for label in CHECK_LABELS:
        vals = [r["checks"].get(label) for r in data_res]
        y, n = vals.count("yes"), vals.count("no")
        yes += y
        no += n
        if y or n:
            check_summary.append([label, y, n])
    s_conf = round(15 * yes / (yes + no)) if (yes + no) else 8

    commercial, s_lic = licence_info(p["licence_id"], p["licence_title"])
    score = s_fresh + s_fmt + s_api + s_doc + s_conf + s_lic
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"

    # flags
    flags = []
    label, every = FREQ.get(p["frequency"], (p["frequency"], None))
    if status == "overdue":
        flags.append(f"Overdue: promised {label.lower()} updates, last change {age} days ago")
    elif status == "late":
        flags.append(f"Running late: promised {label.lower()} updates, last change {age} days ago")
    elif status == "old":
        flags.append(f"No change in {age // 365} years")
    elif status == "archive":
        flags.append("Archive: kept for history, not updated")
    elif status == "unknown":
        flags.append("No file dates, so freshness can't be checked")
    if p["frequency"] == "notStated":
        flags.append("No update frequency promised")
    if not data_res:
        flags.append("No data files (documents or links only)")
    elif s_fmt == 0:
        flags.append("Data only as PDF, web pages or images")
    if field_desc == "Missing":
        flags.append("Publisher says column descriptions are missing")
    elif field_desc == "Not stated":
        flags.append("No column descriptions found")
    if s_lic == 0:
        flags.append(f"No open licence ({p['licence_title']})")
    elif not commercial:
        flags.append(f"Non-commercial licence ({p['licence_title']})")
    elif s_lic < 10:
        flags.append(f"No-derivatives licence ({p['licence_title']})")
    failing = [c[0] for c in check_summary if c[2]]
    if failing:
        flags.append("Portal checks not met: " + ", ".join(failing))
    if "404" in (fields_rec.get("error") or ""):
        flags.append(f"API table missing: '{clean_text(fields_rec.get('resource_name'), 80)}' is marked queryable but the API returns not found")
    if not email:
        flags.append("No contact email")
    if len(desc) < 150:
        flags.append("Very short description")

    files = []
    for r in res:
        lm = as_date(r["modified"])
        cr = as_date(r["added"])
        files.append({
            "n": clean_text(r["name"], 160) or "(untitled)", "f": r["format"],
            "ty": r["type"], "lm": lm.isoformat() if lm else "",
            "sz": r["size"], "u": r["url"], "ds": r["queryable"],
        })
        file_rows.append({
            "province": p["province"], "dataset": p["slug"], "dataset_title": p["title"], "file_name": files[-1]["n"],
            "format": files[-1]["f"], "type": files[-1]["ty"], "last_modified": files[-1]["lm"],
            "added": cr.isoformat() if cr else "", "size_bytes": r["size"] or "",
            "queryable_api": "yes" if files[-1]["ds"] else "no",
            "column_descriptions": r["col_desc"],
            **{label: r["checks"].get(label, "") for label in CHECK_LABELS},
            "download_url": files[-1]["u"], "file_page": r["page"],
        })

    cols = None
    if fields_rec.get("fields") is not None:
        cols = {"rows": fields_rec.get("total"), "file": clean_text(fields_rec.get("resource_name"), 160),
                "rid": fields_rec["resource_id"],
                "c": [[c["id"], c.get("type") or "", clean_text(c.get("label") or "", 120),
                       clean_text(c.get("notes") or "", 300)] for c in fields_rec["fields"]]}
        for c in cols["c"]:
            column_rows.append({"province": p["province"], "dataset": p["slug"], "dataset_title": p["title"],
                                "table": cols["file"], "table_rows": cols["rows"], "column": c[0], "type": c[1],
                                "label": c[2], "notes": c[3]})

    datasets.append({
        "pr": p["province"], "s": p["slug"], "u": p["url"], "t": p["title"].strip(), "o": p["publisher"],
        "po": p["parent"], "g": p["themes"], "tg": p["tags"][:15],
        "d": clean_text(p["description"], 1500), "m": clean_text(p["methodology"], 900),
        "fq": p["frequency"], "lu": last.isoformat() if last else "", "lus": last_src,
        "age": age, "st": status, "cr": p["created"],
        "sc": score, "gr": grade, "sub": [s_fresh, s_fmt, s_api, s_doc, s_conf, s_lic],
        "lic": p["licence_title"] or p["licence_id"], "com": commercial,
        "fm": formats, "sp": p["spatial"],
        "geo": p["geo"], "tc": temporal, "au": p["contact"],
        "em": email, "web": p["web"], "fd": field_desc, "chk": check_summary,
        "std": p["standard"], "ref": p["reference"], "api": datastore, "svc": service,
        "v": p["views"], "vr": p["views_recent"], "nf": len(res), "nd": len(data_res),
        "fl": flags, "files": files, "cols": cols, "lang": p["language"],
    })

if UNKNOWN_LICENCES:
    raise SystemExit(f"Unlisted licences, add them to LICENCES: {sorted(UNKNOWN_LICENCES)}")

os.makedirs(out_dir, exist_ok=True)
summary = {
    "snapshot": snapshot, "datasets": len(datasets), "files": sum(d["nf"] for d in datasets),
    "publishers": len({d["o"] for d in datasets}),
    "with_columns": sum(1 for d in datasets if d["cols"]),
    "grades": Counter(d["gr"] for d in datasets), "status": Counter(d["st"] for d in datasets),
}
with open(os.path.join(out_dir, "data.json"), "w", encoding="utf-8") as f:
    json.dump({"summary": summary, "freq": {k: v[0] for k, v in FREQ.items()}, "datasets": datasets},
              f, ensure_ascii=False, separators=(",", ":"))

STATUS_EN = {"on_time": "On schedule", "late": "Running late", "overdue": "Overdue", "recent": "Changed in last year",
             "stale": "No change in 1-3 years", "old": "No change in 3+ years", "archive": "Archive", "unknown": "Unknown"}


def write_csv(name, rows, cols):
    with open(os.path.join(out_dir, name), "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


ds_rows = []
for d in datasets:
    ds_rows.append({
        "province": d["pr"], "dataset": d["s"], "title": d["t"], "publisher": d["o"], "parent_organisation": d["po"],
        "themes": "; ".join(d["g"]), "tags": "; ".join(d["tg"]),
        "update_frequency": FREQ.get(d["fq"], (d["fq"],))[0], "freshness": STATUS_EN[d["st"]],
        "last_data_update": d["lu"], "days_since_update": d["age"] if d["age"] is not None else "",
        "on_portal_since": d["cr"], "quality_score": d["sc"], "grade": d["gr"],
        "pts_freshness_25": d["sub"][0], "pts_format_15": d["sub"][1], "pts_api_10": d["sub"][2],
        "pts_documentation_25": d["sub"][3], "pts_portal_checks_15": d["sub"][4], "pts_licence_10": d["sub"][5],
        "licence": d["lic"], "commercial_use": "yes" if d["com"] else "no", "formats": ", ".join(d["fm"]),
        "files": d["nf"], "data_files": d["nd"], "queryable_api": "yes" if d["api"] else "no",
        "map_or_web_service": "yes" if d["svc"] else "no", "spatial_coverage": d["sp"],
        "geospatial": "yes" if d["geo"] else "no", "time_coverage": d["tc"], "column_descriptions": d["fd"],
        "methodology": "yes" if len(d["m"]) >= 40 else "no", "contact": d["au"], "contact_email": d["em"],
        "data_standard": d["std"], "reference_data": "yes" if d["ref"] else "no",
        "views_total": d["v"], "views_recent": d["vr"],
        "main_table_rows": (d["cols"] or {}).get("rows", ""), "main_table_columns": len((d["cols"] or {}).get("c", [])) or "",
        "warnings": " | ".join(d["fl"]), "description": d["d"][:1000], "dataset_page": d["u"],
    })
write_csv("datasets.csv", ds_rows, list(ds_rows[0].keys()))
write_csv("files.csv", file_rows, list(file_rows[0].keys()))
if column_rows:
    write_csv("columns.csv", column_rows, list(column_rows[0].keys()))

print(json.dumps(summary, ensure_ascii=False))
print("data.json bytes:", os.path.getsize(os.path.join(out_dir, "data.json")))
print("rows: datasets", len(ds_rows), "files", len(file_rows), "columns", len(column_rows))
