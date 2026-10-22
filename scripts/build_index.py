"""Build the dataset index (page data + CSV exports) from the downloaded catalogue.

usage: build.py <raw_dir> <out_dir> <snapshot YYYY-MM-DD>
"""
import csv
import html
import json
import os
import re
import sys
from collections import Counter
from datetime import date, datetime

raw_dir, out_dir, snapshot = sys.argv[1], sys.argv[2], sys.argv[3]
TODAY = date.fromisoformat(snapshot)
SITE = "https://www.donneesquebec.ca/recherche"

packages = json.load(open(os.path.join(raw_dir, "packages.json"), encoding="utf-8"))
schema = json.load(open(os.path.join(raw_dir, "schema.json"), encoding="utf-8"))["result"]
fields_by_ds = {}
fields_path = os.path.join(raw_dir, "columns.jsonl")
if os.path.exists(fields_path):
    with open(fields_path, encoding="utf-8") as f:
        for line in f:
            if line.strip():
                rec = json.loads(line)
                fields_by_ds[rec["dataset_id"]] = rec


def choices(field_name):
    for f in schema["dataset_fields"] + schema["resource_fields"]:
        if f["field_name"] == field_name:
            out = {}
            for c in f.get("choices") or []:
                lab = c.get("label")
                out[c["value"]] = lab.get("fr") if isinstance(lab, dict) else lab
            return out
    return {}


SPATIAL = choices("ext_spatial")
STANDARDS = choices("extras_flag_donnees_normalise")

FREQ = {  # code: (English label, expected days between updates or None)
    "continuous": ("Real time", 1), "hourly": ("Hourly", 1), "daily": ("Daily", 1),
    "weekly": ("Weekly", 7), "monthly": ("Monthly", 31), "bimonthly": ("Every 2 months", 61),
    "quarterly": ("Quarterly", 92), "semiannual": ("Twice a year", 183), "annual": ("Yearly", 366),
    "biennial": ("Every 2 years", 731), "triennial": ("Every 3 years", 1096),
    "quinquennial": ("Every 5 years", 1827), "asNeeded": ("As needed", None),
    "irregular": ("Irregular", None), "notPlanned": ("No updates planned", None),
    "archives": ("Archive", None),
}

PARENT_LABELS = {
    "gouvernement-du-quebec": "Gouvernement du Québec", "organismes": "Organismes",
    "cm-quebec": "Communauté métropolitaine de Québec",
    "assemblee-nationale-du-quebec": "Assemblée nationale du Québec",
}

OPEN_FORMATS = {"CSV", "TSV", "JSON", "GEOJSON", "XML", "GPKG", "GML", "KML", "KMZ", "SHP", "GTFS",
                "SQLITE", "ODS", "RINEX", "GEOTIFF", "TIFF", "TXT", "JSONL", "PARQUET", "LAS", "LAZ",
                "NETCDF", "GEOPACKAGE", "ATOM", "RSS", "IVT", "3DM", "JPEG2000"}
STRUCTURED_FORMATS = {"XLSX", "XLS", "FGDB", "GDB", "ZIP", "DWG", "DGN", "DXF", "ECW", "LYR", "QML",
                      "MDB", "ACCDB", "SAV", "DTA"}
SERVICE_FORMATS = {"WMS", "WFS", "WMTS", "ESRIREST", "API", "REST", "OGC", "WCS", "ARCGIS"}
DATA_TYPES = {"donnees", "indefini", "archives", None, ""}

CHECKS = [  # resource field, English label
    ("relidi_confic_utf8", "UTF-8 encoding"),
    ("relidi_confic_separateur_virgule", "Comma separator (CSV)"),
    ("relidi_confic_pascom", "File not compressed"),
    ("relidi_confic_epsg", "Standard projection (EPSG 4326 / 32198)"),
    ("relidi_condon_valinc", "Unknown values left empty"),
    ("relidi_condon_datheu", "ISO dates and times (YYYY-MM-DD)"),
    ("relidi_condon_nombre", "Numbers use '.' decimals and SI units"),
    ("relidi_condon_boolee", "Simple true/false values"),
]
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


def fmt_of(r):
    f = (r.get("format") or "").upper().strip().lstrip(".")
    return {"GEO JSON": "GEOJSON", "SHAPEFILE": "SHP", "ESRI REST": "ESRIREST", "GEOPACKAGE": "GPKG"}.get(f, f)


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


def licence_info(lid):
    l = (lid or "").lower()
    if "nc" in l.split("-"):
        return False, 3
    if "nd" in l.split("-"):
        return True, 6
    return True, 10


datasets, file_rows, column_rows = [], [], []
for p in packages:
    res = p.get("resources") or []
    data_res = [r for r in res if r.get("resource_type") in DATA_TYPES]
    formats = sorted({fmt_of(r) for r in res if fmt_of(r)})
    data_formats = {fmt_of(r) for r in data_res if fmt_of(r)} or set(formats)

    # last data update: newest last_modified among data files, else their creation date
    dated = [as_date(r.get("last_modified")) for r in (data_res or res)]
    dated = [d for d in dated if d]
    last_src = "file modified"
    if not dated:
        dated = [d for d in (as_date(r.get("created")) for r in (data_res or res)) if d]
        last_src = "file added"
    last = max(dated) if dated else None
    status, s_fresh, age = freshness(p["update_frequency"], last)

    # format openness
    if data_formats & OPEN_FORMATS:
        s_fmt = 15
    elif data_formats & (STRUCTURED_FORMATS | SERVICE_FORMATS):
        s_fmt = 9
    else:
        s_fmt = 0

    # API access
    datastore = any(r.get("datastore_active") is True for r in res)
    service = any(fmt_of(r) in SERVICE_FORMATS or r.get("resource_type") == "web" for r in res)
    s_api = 10 if datastore else 7 if service else 0

    # documentation
    desc = clean_text(p.get("notes"))
    method = clean_text(p.get("methodologie"))
    temporal = (p.get("temporal") or "").strip()
    email = (p.get("author_email") or "").strip()
    fd_vals = Counter(r.get("relidi_description_champs") for r in data_res)
    support_docs = [r for r in res if r.get("resource_type") == "support"]
    dict_doc = any(DICT_NAME.search(r.get("name") or "") for r in support_docs)
    fields_rec = fields_by_ds.get(p["id"]) or {}
    labelled_cols = any((c.get("label") or c.get("notes")) for c in fields_rec.get("fields") or [])
    if fd_vals.get("relidi.descha.foudoc") or dict_doc:
        field_desc = "Separate document"
    elif fd_vals.get("relidi.descha.foumet") or labelled_cols:
        field_desc = "In the description"
    elif fd_vals.get("relidi.descha.absent"):
        field_desc = "Missing"
    else:
        field_desc = "Not stated"
    s_doc = (7 if len(desc) >= 400 else 4 if len(desc) >= 150 else 1 if desc else 0)
    s_doc += 8 if field_desc in ("Separate document", "In the description") else 0
    s_doc += 5 if len(method) >= 40 else 0
    s_doc += 3 if temporal else 0
    s_doc += 2 if email else 0

    # portal conformity checks on data files
    check_summary = []
    yes = no = 0
    for key, label in CHECKS:
        vals = Counter((r.get(key) or "").lower() for r in data_res)
        y, n = vals.get("oui", 0), vals.get("non", 0)
        yes += y
        no += n
        if y or n:
            check_summary.append([label, y, n])
    s_conf = round(15 * yes / (yes + no)) if (yes + no) else 8

    commercial, s_lic = licence_info(p.get("license_id"))
    score = s_fresh + s_fmt + s_api + s_doc + s_conf + s_lic
    grade = "A" if score >= 85 else "B" if score >= 70 else "C" if score >= 55 else "D"

    # flags
    flags = []
    label, every = FREQ.get(p["update_frequency"], (p["update_frequency"], None))
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
    if not data_res:
        flags.append("No data files (documents or links only)")
    elif s_fmt == 0:
        flags.append("Data only as PDF, web pages or images")
    if field_desc == "Missing":
        flags.append("Publisher says column descriptions are missing")
    elif field_desc == "Not stated":
        flags.append("No column descriptions found")
    if not commercial:
        flags.append(f"Non-commercial licence ({p.get('license_title')})")
    elif s_lic < 10:
        flags.append(f"No-derivatives licence ({p.get('license_title')})")
    failing = [c[0] for c in check_summary if c[2]]
    if failing:
        flags.append("Portal checks not met: " + ", ".join(failing))
    if "404" in (fields_rec.get("error") or ""):
        flags.append(f"API table missing: '{clean_text(fields_rec.get('resource_name'), 80)}' is marked queryable but the API returns not found")
    if not email:
        flags.append("No contact email")
    if len(desc) < 150:
        flags.append("Very short description")

    std = STANDARDS.get(p.get("extras_flag_donnees_normalise") or "", "") or (p.get("extras_flag_donnees_normalise") or "")
    reference = bool(p.get("extras_donnees_reference"))
    org = p["organization"]["title"]
    parent_slug = p.get("extras_organisation_principale") or ""
    groups = [g["title"] for g in p.get("groups") or []]
    tags = [t["display_name"] for t in p.get("tags") or []]
    views = p.get("tracking_summary") or {}
    url = f"{SITE}/dataset/{p['name']}"

    files = []
    for r in sorted(res, key=lambda r: r.get("position", 0)):
        size = r.get("size") if isinstance(r.get("size"), int) and r.get("size") > 0 else None
        if size is None and isinstance(r.get("taille_entier"), (int, float)) and r["taille_entier"] > 0:
            size = int(r["taille_entier"] * 1_000_000)
        lm = as_date(r.get("last_modified"))
        cr = as_date(r.get("created"))
        files.append({
            "n": clean_text(r.get("name"), 160) or "(untitled)", "f": fmt_of(r),
            "ty": r.get("resource_type") or "", "lm": lm.isoformat() if lm else "",
            "sz": size, "u": r.get("url") or "", "ds": r.get("datastore_active") is True,
        })
        file_rows.append({
            "dataset": p["name"], "dataset_title": p["title"], "file_name": files[-1]["n"],
            "format": files[-1]["f"], "type": files[-1]["ty"], "last_modified": files[-1]["lm"],
            "added": cr.isoformat() if cr else "", "size_bytes": size or "",
            "queryable_api": "yes" if files[-1]["ds"] else "no",
            "column_descriptions": r.get("relidi_description_champs") or "",
            **{label: (r.get(key) or "") for key, label in CHECKS},
            "download_url": files[-1]["u"], "file_page": f"{url}/resource/{r['id']}",
        })

    cols = None
    if fields_rec.get("fields") is not None:
        cols = {"rows": fields_rec.get("total"), "file": clean_text(fields_rec.get("resource_name"), 160),
                "rid": fields_rec["resource_id"],
                "c": [[c["id"], c.get("type") or "", clean_text(c.get("label") or "", 120),
                       clean_text(c.get("notes") or "", 300)] for c in fields_rec["fields"]]}
        for c in cols["c"]:
            column_rows.append({"dataset": p["name"], "dataset_title": p["title"], "table": cols["file"],
                                "table_rows": cols["rows"], "column": c[0], "type": c[1],
                                "label": c[2], "notes": c[3]})

    datasets.append({
        "s": p["name"], "t": p["title"].strip(), "o": org,
        "po": PARENT_LABELS.get(parent_slug) or org, "g": groups, "tg": tags[:15],
        "d": clean_text(p.get("notes"), 1500), "m": clean_text(p.get("methodologie"), 900),
        "fq": p["update_frequency"], "lu": last.isoformat() if last else "", "lus": last_src,
        "age": age, "st": status, "cr": (p.get("metadata_created") or "")[:10],
        "sc": score, "gr": grade, "sub": [s_fresh, s_fmt, s_api, s_doc, s_conf, s_lic],
        "lic": p.get("license_title") or p.get("license_id"), "com": commercial,
        "fm": formats, "sp": SPATIAL.get(p.get("ext_spatial"), p.get("ext_spatial") or ""),
        "geo": p.get("spatial_data") == "Oui", "tc": temporal, "au": (p.get("author") or "").strip(),
        "em": email, "web": (p.get("url") or "").strip(), "fd": field_desc, "chk": check_summary,
        "std": std, "ref": reference, "api": datastore, "svc": service,
        "v": views.get("total", 0), "vr": views.get("recent", 0), "nf": len(res), "nd": len(data_res),
        "fl": flags, "files": files, "cols": cols, "lang": p.get("language"),
    })

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
        "dataset": d["s"], "title": d["t"], "publisher": d["o"], "parent_organisation": d["po"],
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
        "warnings": " | ".join(d["fl"]), "description": d["d"][:1000], "dataset_page": f"{SITE}/dataset/{d['s']}",
    })
write_csv("datasets.csv", ds_rows, list(ds_rows[0].keys()))
write_csv("files.csv", file_rows, list(file_rows[0].keys()))
if column_rows:
    write_csv("columns.csv", column_rows, list(column_rows[0].keys()))

print(json.dumps(summary, ensure_ascii=False))
print("data.json bytes:", os.path.getsize(os.path.join(out_dir, "data.json")))
print("rows: datasets", len(ds_rows), "files", len(file_rows), "columns", len(column_rows))
