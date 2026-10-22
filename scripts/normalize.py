"""Turn each portal's raw catalogue into common dataset records, so one scorer handles every province.

A field the portal has no equivalent for is None; a field the publisher left empty is "".
"""
import gzip
import json
import os

from portals import PORTALS

PARENT_LABELS = {
    "gouvernement-du-quebec": "Gouvernement du Québec", "organismes": "Organismes",
    "cm-quebec": "Communauté métropolitaine de Québec",
    "assemblee-nationale-du-quebec": "Assemblée nationale du Québec",
}
DATA_TYPES = {"donnees", "indefini", "archives", None, ""}
CHECKS = [  # Données Québec resource field, English label
    ("relidi_confic_utf8", "UTF-8 encoding"),
    ("relidi_confic_separateur_virgule", "Comma separator (CSV)"),
    ("relidi_confic_pascom", "File not compressed"),
    ("relidi_confic_epsg", "Standard projection (EPSG 4326 / 32198)"),
    ("relidi_condon_valinc", "Unknown values left empty"),
    ("relidi_condon_datheu", "ISO dates and times (YYYY-MM-DD)"),
    ("relidi_condon_nombre", "Numbers use '.' decimals and SI units"),
    ("relidi_condon_boolee", "Simple true/false values"),
]


def fmt_of(r):
    f = (r.get("format") or "").upper().strip().lstrip(".")
    return {"GEO JSON": "GEOJSON", "SHAPEFILE": "SHP", "ESRI REST": "ESRIREST", "GEOPACKAGE": "GPKG"}.get(f, f)


def load_columns(raw_dir):
    path = os.path.join(raw_dir, "columns.jsonl")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {rec["dataset_id"]: rec for rec in map(json.loads, filter(str.strip, f))}


def choices(schema, field_name):
    for f in schema["dataset_fields"] + schema["resource_fields"]:
        if f["field_name"] == field_name:
            out = {}
            for c in f.get("choices") or []:
                lab = c.get("label")
                out[c["value"]] = lab.get("fr") if isinstance(lab, dict) else lab
            return out
    return {}


def ckan(code, raw_dir):
    site = PORTALS[code]["site"]
    packages = json.load(gzip.open(os.path.join(raw_dir, "packages.json.gz"), "rt", encoding="utf-8"))
    schema = json.load(open(os.path.join(raw_dir, "schema.json"), encoding="utf-8"))["result"]
    spatial, standards = choices(schema, "ext_spatial"), choices(schema, "extras_flag_donnees_normalise")
    columns = load_columns(raw_dir)
    out = []
    for p in packages:
        url = f"{site}/dataset/{p['name']}"
        files = []
        for r in sorted(p.get("resources") or [], key=lambda r: r.get("position", 0)):
            size = r.get("size") if isinstance(r.get("size"), int) and r.get("size") > 0 else None
            if size is None and isinstance(r.get("taille_entier"), (int, float)) and r["taille_entier"] > 0:
                size = int(r["taille_entier"] * 1_000_000)
            files.append({
                "name": r.get("name"), "format": fmt_of(r), "type": r.get("resource_type") or "",
                "data": r.get("resource_type") in DATA_TYPES, "doc": r.get("resource_type") == "support",
                "service": r.get("resource_type") == "web", "modified": r.get("last_modified"),
                "added": r.get("created"), "size": size, "url": r.get("url") or "",
                "queryable": r.get("datastore_active") is True, "page": f"{url}/resource/{r['id']}",
                "col_desc": r.get("relidi_description_champs") or "",
                "checks": {label: r.get(key) or "" for key, label in CHECKS},
            })
        org = p["organization"]["title"]
        std = p.get("extras_flag_donnees_normalise") or ""
        views = p.get("tracking_summary") or {}
        out.append({
            "province": code, "id": p["id"], "slug": p["name"], "title": p["title"], "url": url,
            "publisher": org, "parent": PARENT_LABELS.get(p.get("extras_organisation_principale") or "") or org,
            "themes": [g["title"] for g in p.get("groups") or []],
            "tags": [t["display_name"] for t in p.get("tags") or []],
            "description": p.get("notes"), "methodology": p.get("methodologie"),
            "frequency": p["update_frequency"], "time_coverage": (p.get("temporal") or "").strip(),
            "contact": (p.get("author") or "").strip(), "email": (p.get("author_email") or "").strip(),
            "licence_id": p.get("license_id"), "licence_title": p.get("license_title"),
            "web": (p.get("url") or "").strip(), "created": (p.get("metadata_created") or "")[:10],
            "spatial": spatial.get(p.get("ext_spatial"), p.get("ext_spatial") or ""),
            "geo": p.get("spatial_data") == "Oui", "standard": standards.get(std, "") or std,
            "reference": bool(p.get("extras_donnees_reference")), "language": p.get("language"),
            "views": views.get("total", 0), "views_recent": views.get("recent", 0),
            "files": files, "columns": columns.get(p["id"]),
        })
    return out


PLATFORMS = {"ckan": ckan}


def records(raw_root):
    out = []
    for code, portal in PORTALS.items():
        out.extend(PLATFORMS[portal["platform"]](code, os.path.join(raw_root, code)))
    return out
