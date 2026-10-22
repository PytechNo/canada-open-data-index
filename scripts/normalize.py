"""Turn each portal's raw catalogue into common dataset records, so one scorer handles every province.

A field the portal has no equivalent for is None; a field the publisher left empty is "".
Every portal's update-frequency values are mapped onto the FREQ codes below; the build stops on any
value it hasn't seen before, so a portal changing its vocabulary can't slip through as "not stated".
"""
import functools
import gzip
import html
import json
import os
import re
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone

from portals import PORTALS

FREQ = {  # code: (English label, expected days between updates or None)
    "continuous": ("Real time", 1), "hourly": ("Hourly", 1), "daily": ("Daily", 1),
    "weekly": ("Weekly", 7), "biweekly": ("Every 2 weeks", 14), "monthly": ("Monthly", 31),
    "bimonthly": ("Every 2 months", 61), "quarterly": ("Quarterly", 92), "semiannual": ("Twice a year", 183),
    "annual": ("Yearly", 366), "biennial": ("Every 2 years", 731), "triennial": ("Every 3 years", 1096),
    "quinquennial": ("Every 5 years", 1827), "asNeeded": ("As needed", None),
    "irregular": ("Irregular", None), "notPlanned": ("No updates planned", None),
    "archives": ("Archive", None), "notStated": ("Not stated", None),
}
FREQ_MAPS = {  # portal value -> FREQ code
    "QC": {k: k for k in FREQ},
    "ON": {"daily": "daily", "weekly": "weekly", "monthly": "monthly", "quarterly": "quarterly",
           "biannually": "semiannual", "yearly": "annual", "quinquennial": "quinquennial", "current": "continuous",
           "as_required": "asNeeded", "on_demand": "asNeeded", "periodically": "asNeeded", "other": "irregular",
           "historical": "archives", "never": "notPlanned", "": "notStated"},
    "BC": {"daily": "daily", "nightly": "daily", "weekly": "weekly", "fortnightly": "biweekly",
           "monthly": "monthly", "quarterly": "quarterly", "biannually": "semiannual", "annually": "annual",
           "continual": "continuous", "asNeeded": "asNeeded", "irregular": "irregular",
           "notPlanned": "notPlanned", "unknown": "notStated"},
    "AB": {"Daily": "daily", "Weekly": "weekly", "Every 2 weeks": "biweekly", "Monthly": "monthly",
           "Every 2 months": "bimonthly", "Quarterly": "quarterly", "Semi-annual": "semiannual",
           "Annual": "annual", "Biennial": "biennial", "Every 5 years": "quinquennial", "As needed": "asNeeded",
           "Irregular": "irregular", "Other": "irregular", "Once": "notPlanned", "notPlanned": "notPlanned"},
    "YT": {"real_time": "continuous", "daily": "daily", "monthly": "monthly", "quarterly": "quarterly",
           "ad_hoc": "asNeeded", "none": "notPlanned", "": "notStated"},
    "NT": {"monthly": "monthly", "quarterly": "quarterly", "yearly": "annual", "every5years": "quinquennial",
           "as_needed": "asNeeded", "infrequently": "irregular", "never": "notPlanned"},
    "NL": {"unknown": "notStated"},
    # shortcut: "Bi-Annually" read as twice a year, like Ontario's "biannually"; NS doesn't define it
    "NS": {"Daily": "daily", "Monthly": "monthly", "Bi-Monthly": "bimonthly", "Quarterly": "quarterly",
           "Bi-Annually": "semiannual", "Annually": "annual", "As needed": "asNeeded", "One-time": "notPlanned",
           "": "notStated"},
    "NB": {"": "notStated"},
}
# ArcGIS Hub: the ISO 19115 maintenance frequency code (MaintFreqCd) in an item's formal metadata, if any
FREQ_MAPS["MB"] = FREQ_MAPS["SK"] = FREQ_MAPS["PE"] = {
    "001": "continuous", "002": "daily", "003": "weekly", "004": "biweekly", "005": "monthly", "006": "quarterly",
    "007": "semiannual", "008": "annual", "009": "asNeeded", "010": "irregular", "011": "notPlanned",
    "012": "notStated", "": "notStated"}
UNMAPPED = set()

QC_PARENTS = {
    "gouvernement-du-quebec": "Gouvernement du Québec", "organismes": "Organismes",
    "cm-quebec": "Communauté métropolitaine de Québec",
    "assemblee-nationale-du-quebec": "Assemblée nationale du Québec",
}
QC_DATA_TYPES = {"donnees", "indefini", "archives", None, ""}
QC_COL_DESC = {"relidi.descha.foudoc": "Separate document", "relidi.descha.foumet": "In the description",
               "relidi.descha.absent": "Missing"}
QC_CHECKS = [  # Données Québec resource field, English label
    ("relidi_confic_utf8", "UTF-8 encoding"),
    ("relidi_confic_separateur_virgule", "Comma separator (CSV)"),
    ("relidi_confic_pascom", "File not compressed"),
    ("relidi_confic_epsg", "Standard projection (EPSG 4326 / 32198)"),
    ("relidi_condon_valinc", "Unknown values left empty"),
    ("relidi_condon_datheu", "ISO dates and times (YYYY-MM-DD)"),
    ("relidi_condon_nombre", "Numbers use '.' decimals and SI units"),
    ("relidi_condon_boolee", "Simple true/false values"),
]
GEO_FORMATS = {"SHP", "KML", "KMZ", "GEOJSON", "GPKG", "GML", "WMS", "WFS", "WMTS", "ESRIREST", "FGDB", "GDB",
               "GEOTIFF", "MULTIPLE"}
GEOMETRY_TYPES = {"Point", "MultiPoint", "Line", "MultiLine", "Polygon", "MultiPolygon", "Location"}  # Socrata
HUB_FILE_FORMATS = {"File Geodatabase": "FGDB", "Shapefile": "SHP", "CSV": "CSV"}  # Hub items that are one file
ARCGIS_SYSTEM_FIELDS = {"esriFieldTypeOID", "esriFieldTypeGeometry"}  # Hub's own table leaves these out
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")


def fmt_of(r):
    f = (r.get("format") or "").upper().strip().lstrip(".")
    return {"GEO JSON": "GEOJSON", "SHAPEFILE": "SHP", "ESRI REST": "ESRIREST", "GEOPACKAGE": "GPKG",
            "ARCGIS_REST": "ESRIREST", "FGDB/GDB": "FGDB", "XSLX": "XLSX", "TIF": "TIFF",
            "APPLICATION/VND.MS-EXCEL (XLSX)": "XLSX", "OPENAPI-JSON": "API"}.get(f, f)


LINK_EXT = re.compile(r"\.(csv|xlsx|xls|zip|pdf|json|geojson|kml|kmz|shp|gpkg|txt|docx|doc)(?:\?|$)", re.I)


def fix_links(files):
    """Correct files the portal labels as a web page or leaves unlabelled."""
    for f in files:
        url = f["url"].lower()
        if "/metadata/" in url and (f["format"] == "XML" or url.split("?")[0].endswith(".xml")):
            f.update(format="METADATA", data=False, doc=True)  # a metadata record, not the data
        elif f["format"] in ("", "HTML", "URI", "LINK", "WEB"):
            m = LINK_EXT.search(url)
            if m:
                f["format"] = m.group(1).upper()
            elif "maps.arcgis.com/home/item.html" in url:
                f.update(format="ARCGIS", service=True)  # ArcGIS Online item: a hosted map layer


def freq(code, value):
    value = value or ""
    if value not in FREQ_MAPS[code]:
        UNMAPPED.add((code, value))
        return "notStated"
    return FREQ_MAPS[code][value]


def en(v):
    return (v.get("en") if isinstance(v, dict) else v) or ""


def span(start, end):
    start, end = [(d or "")[:10] for d in (start, end)]
    start = "" if start.startswith("0001") else start  # federal portal placeholder for "no date"
    return f"{start} to {end}" if start and end else f"from {start}" if start else f"until {end}" if end else ""


def load_columns(raw_dir):
    path = os.path.join(raw_dir, "columns.jsonl")
    if not os.path.exists(path):
        return {}
    with open(path, encoding="utf-8") as f:
        return {rec["dataset_id"]: rec for rec in map(json.loads, filter(str.strip, f))}


@functools.lru_cache
def qc_choices(raw_dir):
    schema = json.load(open(os.path.join(raw_dir, "schema.json"), encoding="utf-8"))["result"]

    def choices(field_name):
        for f in schema["dataset_fields"] + schema["resource_fields"]:
            if f["field_name"] == field_name:
                out = {}
                for c in f.get("choices") or []:
                    lab = c.get("label")
                    out[c["value"]] = lab.get("fr") if isinstance(lab, dict) else lab
                return out
        return {}
    return choices("ext_spatial"), choices("extras_flag_donnees_normalise")


# Per-portal field maps: fill in what the generic CKAN record can't know. `res` lines up with rec["files"].

def qc(p, rec, res, raw_dir):
    spatial, standards = qc_choices(raw_dir)
    std = p.get("extras_flag_donnees_normalise") or ""
    views = p.get("tracking_summary") or {}
    rec.update(
        parent=QC_PARENTS.get(p.get("extras_organisation_principale") or "") or rec["publisher"],
        methodology=p.get("methodologie") or "", frequency=freq("QC", p["update_frequency"]),
        time_coverage=(p.get("temporal") or "").strip(),
        contact=(p.get("author") or "").strip(), email=(p.get("author_email") or "").strip(),
        spatial=spatial.get(p.get("ext_spatial"), p.get("ext_spatial") or ""), geo=p.get("spatial_data") == "Oui",
        standard=standards.get(std, "") or std, reference=bool(p.get("extras_donnees_reference")),
        views=views.get("total", 0), views_recent=views.get("recent", 0),
    )
    for f, r in zip(rec["files"], res):
        if f["size"] is None and isinstance(r.get("taille_entier"), (int, float)) and r["taille_entier"] > 0:
            f["size"] = int(r["taille_entier"] * 1_000_000)
        f.update(type=r.get("resource_type") or "", data=r.get("resource_type") in QC_DATA_TYPES,
                 doc=r.get("resource_type") == "support", service=r.get("resource_type") == "web",
                 col_desc=QC_COL_DESC.get(r.get("relidi_description_champs") or "", r.get("relidi_description_champs") or ""),
                 checks={label: {"oui": "yes", "non": "no"}.get((r.get(key) or "").lower(), r.get(key) or "")
                         for key, label in QC_CHECKS})


def on(p, rec, res, raw_dir):
    rec.update(
        frequency=freq("ON", p.get("update_frequency")),
        time_coverage=span(min((r["data_range_start"] for r in res if r.get("data_range_start")), default=""),
                           max((r["data_range_end"] for r in res if r.get("data_range_end")), default="")),
        contact=(p.get("author") or en(p.get("maintainer_translated")) or p.get("maintainer") or "").strip(),
        spatial=en(p.get("geographic_coverage_translated")), data_date=p.get("current_as_of"),
    )
    for f, r in zip(rec["files"], res):
        kind = r.get("type") or ""
        f.update(type=kind, data=kind in ("data", ""), dictionary=kind == "data_dictionary",
                 doc=kind in ("data_dictionary", "technical_document", "information"),
                 modified=max(filter(None, [r.get("data_last_updated"), r.get("last_modified")]), default=None))
        if r.get("validation_status") in ("success", "failure"):
            f["checks"] = {"Passes automatic file validation": "yes" if r["validation_status"] == "success" else "no"}


def bc(p, rec, res, raw_dir):
    cycles = Counter(r.get("resource_update_cycle") for r in res if r.get("resource_type") == "data")
    contact = next((c for c in p.get("contacts") or [] if c.get("email")), {})
    extents = [t for r in res for t in r.get("temporal_extent") or [] if t.get("beginning_date") or t.get("end_date")]
    rec.update(
        frequency=freq("BC", cycles.most_common(1)[0][0] if cycles else "unknown"),
        contact=contact.get("name", ""), email=contact.get("email", ""),
        methodology=p.get("lineage_statement") or "",
        time_coverage=span(extents[0].get("beginning_date"), extents[0].get("end_date")) if extents else "",
        data_date=max((d["date"] for d in p.get("dates") or [] if d.get("type") in ("Modified", "Revised")),
                      default=None),
    )
    for f, r in zip(rec["files"], res):
        f.update(type=r.get("bcdc_type") or "",
                 data=r.get("resource_type") == "data" and r.get("bcdc_type") in ("document", "geographic"),
                 doc=r.get("resource_type") in ("reports", "abstraction"), service=r.get("bcdc_type") == "webservice")
    # BC Geographic Warehouse objects list their columns in the catalogue itself
    main = next((r for f, r in zip(rec["files"], res) if f["data"] and r.get("details")), None)
    if main:
        rec["columns"] = {"dataset_id": p["id"], "resource_id": main["id"], "resource_name": main.get("name"),
                          "total": None, "fields": [{"id": c["column_name"], "type": c.get("data_type"), "label": None,
                                                     "notes": c.get("column_comments")} for c in main["details"]]}


def ab(p, rec, res, raw_dir):
    rec.update(
        frequency=freq("AB", p.get("updatefrequency")),
        contact=(p.get("contact") or p.get("author") or "").strip(),
        email=(p.get("contact_email") or p.get("author_email") or "").strip(),
        time_coverage=span(p.get("time_coverage_from"), p.get("time_coverage_to")),
        spatial=p.get("spatialcoverage1") or "", data_date=p.get("date_modified"),
    )
    for f in rec["files"]:
        if "/geoportal/rest/metadata/" in f["url"]:  # GeoDiscover metadata record, not the data itself
            f.update(format="METADATA" if f["format"] == "XML" else f["format"], data=False, doc=True)


def yt(p, rec, res, raw_dir):
    rec.update(
        frequency=freq("YT", p.get("update_frequency")), methodology=p.get("methodology") or "",
        time_coverage=span(p.get("temporal_coverage_start_date"), p.get("temporal_coverage_end_date")),
        contact=(p.get("custodian") or p.get("maintainer") or p.get("author") or "").strip(),
        email=(p.get("custodian_email") or p.get("maintainer_email") or p.get("author_email") or "").strip(),
        standard=p.get("data_standard") or "",
        views=int(p.get("visits") or 0), views_recent=int(p.get("visit_90_days") or 0),
    )


def nt(p, rec, res, raw_dir):
    rec.update(
        frequency=freq("NT", p.get("update_frequency")),
        time_coverage=span(p.get("starting_time_range"), p.get("ending_time_range")),
        contact=(p.get("maintainer") or p.get("author") or p.get("Creator") or "").strip(),
        spatial=p.get("geographic_range") or "", data_date=p.get("modified_date"),
    )


def nl(p, rec, res, raw_dir):
    rec.update(
        title=en(p.get("title_translated")) or p["title"], description=en(p.get("notes_translated")) or p.get("notes"),
        publisher=rec["publisher"].split(" | ")[0], parent=rec["publisher"].split(" | ")[0],
        frequency=freq("NL", p.get("frequency")),
        time_coverage=span(p.get("time_period_coverage_start"), p.get("time_period_coverage_end")),
    )
    # the federal copy's file and "modified" dates are its own sync dates, so fall back on first publication
    for f, r in zip(rec["files"], res):
        f.update(type=r.get("resource_type") or "", data=r.get("resource_type") == "dataset",
                 doc=r.get("resource_type") == "guide", added=p.get("date_published"))


# Socrata maps get the portal's custom metadata fields (domain_metadata) as a dict instead of resources.

def ns(p, rec, meta, raw_dir):
    dept = meta.get("Detailed-Metadata_Department") or rec["publisher"]
    # retired datasets say "ARCHIVED on <date>" here and promise "One-time" updates
    archived = re.match(r"\s*archived\b", meta.get("Detailed-Metadata_Usage-Considerations", ""), re.I)
    rec.update(
        publisher=dept, parent=dept,
        frequency="archives" if archived else freq("NS", meta.get("Detailed-Metadata_Frequency")),
        time_coverage=meta.get("Detailed-Metadata_Time-Period-Coverage", "").strip(),
        spatial=meta.get("Detailed-Metadata_Geographic-Region-Name", "").strip(),
        language=meta.get("Detailed-Metadata_Language"),
    )


def nb(p, rec, meta, raw_dir):
    # the department field is filled on half the records; the rest name the source (122 are Statistics Canada)
    org = meta.get("Department-/-Ministère_Department-/-Ministère") or p["resource"].get("attribution") or rec["publisher"]
    rec.update(publisher=org, parent=org, frequency=freq("NB", ""))
    svc = meta.get("Map-Service-/-Service-de-carte_Map-Service-/-Service-de-carte")
    if svc:
        rec["files"].append({**rec["files"][0], "name": "Map service", "format": "ESRIREST", "data": False,
                             "service": True, "queryable": False, "modified": None, "url": svc.strip()})


# Hub maps get the item's formal metadata values (hub_metadata) instead of resources. Hub only has free licence
# text, so each portal lists (pattern, licence title) rules for it.

def hub_licence(item, rules):
    """The first rule the licence text matches names the licence; text no rule matches is passed on as the
    title, so the build stops on it."""
    text = " ".join(html.unescape(re.sub(r"<[^>]+>", " ", item.get("licenseInfo") or "")).split())
    if not text:
        return "Licence not specified"
    return next((title for pattern, title in rules if re.search(pattern, text, re.I)), text[:100])


def mb(p, rec, meta, raw_dir):
    # every licence link goes to manitoba.ca/legal/copyright.html, which is the OpenMB licence
    rec["licence_title"] = hub_licence(p["properties"], [
        (r"open ?data|openmb|ouvert|legal/copyright", "OpenMB Information and Data Use Licence"),
        (r"^(disclaimer|this boundary is not|manitoba agriculture makes)", "Licence not specified")])


def sk(p, rec, meta, raw_dir):
    rec["licence_title"] = hub_licence(p["properties"], [
        (r"open government licen[cs]e\W+canada", "Open Government Licence - Canada"),
        (r"unrestricted", "Government of Saskatchewan Standard Unrestricted Use Data Licence"),
        (r"^(although|monitoring station)", "Licence not specified")])


def pe(p, rec, meta, raw_dir):
    # credits read "Contact Information: <name>, <phone> Contact Email: <email>"
    contact = re.match(r"\s*Contact Information:\s*([^,\n\d–]+?)\s*(?:[,\n\d–]|Contact Email|$)",
                       p["properties"].get("accessInformation") or "")
    rec["contact"] = contact.group(1) if contact else ""
    rec["licence_title"] = hub_licence(p["properties"], [
        (r"open government licen[cs]e\W+prince edward island", "Open Government Licence - Prince Edward Island"),
        (r"^care has been taken", "Licence not specified")])


FIELD_MAPS = {"QC": qc, "ON": on, "BC": bc, "AB": ab, "YT": yt, "NT": nt, "NL": nl, "NS": ns, "NB": nb,
              "MB": mb, "SK": sk, "PE": pe}


def ckan(code, raw_dir):
    page = PORTALS[code]["page"]
    packages = json.load(gzip.open(os.path.join(raw_dir, "packages.json.gz"), "rt", encoding="utf-8"))
    columns = load_columns(raw_dir)
    out = []
    for p in packages:
        url = page.format(name=p["name"], id=p["id"])
        res = sorted(p.get("resources") or [], key=lambda r: r.get("position", 0))
        files = [{
            "name": r.get("name"), "format": fmt_of(r), "type": "", "data": True, "doc": False,
            "dictionary": False, "service": False, "modified": r.get("last_modified"), "added": r.get("created"),
            "size": r["size"] if isinstance(r.get("size"), int) and r["size"] > 0 else None,
            "url": r.get("url") or "", "queryable": r.get("datastore_active") is True,
            "page": f"{url}/resource/{r['id']}", "col_desc": "", "checks": {},
        } for r in res]
        org = p["organization"]["title"]
        rec = {
            "province": code, "id": p["id"], "slug": p["name"], "title": p["title"], "url": url,
            "publisher": org, "parent": org,
            "themes": [g["title"] for g in p.get("groups") or []],
            "tags": [t["display_name"] for t in p.get("tags") or []],
            "description": p.get("notes"), "methodology": None, "frequency": None, "time_coverage": None,
            "contact": (p.get("author") or p.get("maintainer") or "").strip(),
            "email": (p.get("author_email") or p.get("maintainer_email") or "").strip(),
            "licence_id": p.get("license_id"), "licence_title": p.get("license_title"),
            "web": (p.get("url") or "").strip(), "created": (p.get("metadata_created") or "")[:10],
            "spatial": "", "geo": any(f["format"] in GEO_FORMATS for f in files), "standard": "", "reference": False,
            "language": p.get("language"), "views": 0, "views_recent": 0, "data_date": None,
            "files": files, "columns": columns.get(p["id"]),
        }
        FIELD_MAPS[code](p, rec, res, raw_dir)
        fix_links(files)
        out.append(rec)
    return out


def socrata(code, raw_dir):
    """One record per Socrata dataset: a single table, exported as CSV and queryable through the SODA API."""
    page = PORTALS[code]["page"]
    out = []
    for p in json.load(gzip.open(os.path.join(raw_dir, "packages.json.gz"), "rt", encoding="utf-8")):
        r, c = p["resource"], p["classification"]
        meta = {m["key"]: m["value"] for m in c.get("domain_metadata") or []}
        url = page.format(id=r["id"])
        added = r.get("publication_date") or r["createdAt"]
        files = [{
            "name": r["name"], "format": "CSV", "type": "", "data": True, "doc": False, "dictionary": False,
            "service": False, "modified": r.get("data_updated_at"), "added": added, "size": None,
            "url": f"https://{p['metadata']['domain']}/api/views/{r['id']}/rows.csv?accessType=DOWNLOAD",
            "queryable": True, "page": url, "col_desc": "", "checks": {},
        }]
        views = r.get("page_views") or {}
        rec = {
            "province": code, "id": r["id"], "slug": r["id"], "title": r["name"], "url": url,
            "publisher": p["owner"]["display_name"], "parent": p["owner"]["display_name"],
            "themes": [t.strip() for t in [c.get("domain_category")] + (c.get("categories") or []) if t and t.strip()],
            "tags": (c.get("domain_tags") or []) + (c.get("tags") or []),
            "description": r.get("description"), "methodology": None, "frequency": None, "time_coverage": None,
            "contact": "", "email": (r.get("contact_email") or "").strip(),
            "licence_id": None, "licence_title": p["metadata"].get("license") or "Licence not specified",
            "web": (r.get("attribution_link") or "").strip(), "created": added[:10],
            "spatial": "", "geo": bool(GEOMETRY_TYPES & set(r.get("columns_datatype") or [])), "standard": "",
            "reference": False, "language": None,
            "views": views.get("page_views_total", 0), "views_recent": views.get("page_views_last_month", 0),
            "data_date": None, "files": files,
            # the column names are the CSV headers, so only a description counts as documenting a column
            "columns": {"dataset_id": r["id"], "resource_id": r["id"], "resource_name": r["name"], "total": None,
                        "fields": [{"id": n, "type": t, "label": None, "notes": d} for n, t, d in
                                   zip(r["columns_name"], r["columns_datatype"], r["columns_description"])]},
        }
        FIELD_MAPS[code](p, rec, meta, raw_dir)
        out.append(rec)
    return out


def ms_date(t):
    return datetime.fromtimestamp(t / 1000, timezone.utc).isoformat() if t else None


def hub_metadata(xml_text):
    """The values read from an item's formal (ISO 19115) metadata; {} when it has none. Formal metadata is
    optional and not on Hub's dataset form, so a value left empty there is read as missing, not as 0."""
    if not xml_text:
        return {}
    root = ET.fromstring(xml_text)
    code = root.find("dataIdInfo/resMaint/maintFreq/MaintFreqCd")
    return {"frequency": code.get("value") if code is not None else "",
            "revised": root.findtext("dataIdInfo/idCitation/date/reviseDate"),
            "lineage": (root.findtext("dqInfo/dataLineage/statement") or "").strip() or None,
            "email": (root.findtext("dataIdInfo/idPoC/rpCntInfo/cntAddress/eMailAdd") or "").strip()}


def hub(code, raw_dir):
    """One record per Hub item. A feature service gives one CSV download per layer (Hub exports any layer as
    CSV or GeoJSON) plus the service itself; an item that is a single file (file geodatabase, shapefile, CSV)
    is that file."""
    page = PORTALS[code]["page"]
    site = PORTALS[code]["api"].split("/api/")[0]
    out = []
    for p in json.load(gzip.open(os.path.join(raw_dir, "packages.json.gz"), "rt", encoding="utf-8")):
        it, layers = p["properties"], p.get("layers") or []
        meta = hub_metadata(p.get("metadata_xml"))
        url = page.format(id=it["id"])
        added = ms_date(it["created"])
        base = {"type": "", "data": True, "doc": False, "dictionary": False, "service": False, "added": added,
                "size": None, "queryable": False, "page": url, "col_desc": "", "checks": {}}
        if it.get("url"):
            # dataLastEditDate leaves out schema and service changes that lastEditDate also counts
            files = [{**base, "name": l["name"], "format": "CSV",
                      "modified": ms_date((l.get("editingInfo") or {}).get("dataLastEditDate")
                                          or (l.get("editingInfo") or {}).get("lastEditDate")),
                      "url": f"{site}/api/download/v1/items/{it['id']}/csv?layers={l['id']}"} for l in layers]
            files.append({**base, "name": "Feature service", "format": "ESRIREST", "data": False, "service": True,
                          "modified": None, "url": it["url"]})
        else:
            files = [{**base, "name": it.get("name") or it["title"], "modified": None, "size": it.get("size"),
                      "format": HUB_FILE_FORMATS.get(it["type"], it["type"].upper()),
                      "url": f"https://www.arcgis.com/sharing/rest/content/items/{it['id']}/data"}]
        main = next((l for l in layers if l.get("fields")), None)
        rec = {
            "province": code, "id": it["id"], "slug": it["id"], "title": it["title"], "url": url,
            "publisher": it.get("source") or f"Government of {PORTALS[code]['name']}",
            "parent": it.get("source") or f"Government of {PORTALS[code]['name']}",
            "themes": [c.rsplit("/", 1)[-1] for c in it.get("categories") or []], "tags": it.get("tags") or [],
            "description": it.get("description") or it.get("snippet"), "methodology": meta.get("lineage"),
            "frequency": freq(code, meta.get("frequency")), "time_coverage": None, "contact": "",
            "email": meta.get("email") or next(iter(EMAIL.findall(it.get("accessInformation") or "")), ""),
            # a Creative Commons licence picked from Hub's list; any other licence is only free text
            "licence_id": it["license"] if (it.get("license") or "").lower().startswith("cc") else None,
            "licence_title": None, "web": "", "created": added[:10], "spatial": "",
            "geo": any(l.get("geometryType") for l in layers) or HUB_FILE_FORMATS.get(it["type"]) in GEO_FORMATS,
            "standard": "", "reference": False, "language": None, "views": it.get("numViews") or 0,
            "views_recent": 0,
            # used only when no layer has an edit date: the publisher's revision date, else the item's own
            # modified date, which changes with any metadata edit
            "data_date": meta.get("revised") or ms_date(it["modified"]),
            "data_date_src": "publisher's date" if meta.get("revised") else "metadata date",
            "files": files,
            # field aliases are display names, so only a field description counts as documenting a column
            "columns": main and {
                "dataset_id": it["id"], "resource_id": f"{it['id']}/{main['id']}", "resource_name": main["name"],
                "total": None, "fields": [{"id": f["name"], "type": f["type"].removeprefix("esriFieldType"),
                                           "label": None,
                                           # a JSON string: {"value": "…", "fieldValueType": "…"}, or "null"
                                           "notes": (json.loads(f.get("description") or "{}") or {}).get("value")}
                                          for f in main["fields"] if f["type"] not in ARCGIS_SYSTEM_FIELDS]},
        }
        FIELD_MAPS[code](p, rec, meta, raw_dir)
        out.append(rec)
    return out


PLATFORMS = {"ckan": ckan, "socrata": socrata, "hub": hub}


def records(raw_root):
    out = []
    for code, portal in PORTALS.items():
        out.extend(PLATFORMS[portal["platform"]](code, os.path.join(raw_root, code)))
    if UNMAPPED:
        raise SystemExit(f"Unmapped update frequencies, add them to FREQ_MAPS: {sorted(UNMAPPED)}")
    return out
