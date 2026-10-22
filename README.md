# Canada Open Data Index

An index of **every dataset on the open data portals of Canada's provinces and territories**, plus the federal departments' core collection on [open.canada.ca](https://open.canada.ca). For each dataset it lists what it contains, how often the publisher promised to update it, when it last changed, and a quality score to help you decide whether you can rely on it. Every portal is scored by the same rules, so the portals can be compared.

Snapshot: **2026-10-22** · **13 portals** · **24,343 datasets** · **521 publishers** · **116,188 files** · column lists for **5,592 datasets**

> Unofficial. Built from each portal's public catalogue API. Not affiliated with any government.

## Browse it

- **Interactive index:** [`docs/index.html`](docs/index.html). Compare the portals, then search by title, topic or column name. Filter by portal, publisher, theme, update frequency, format, grade, freshness, API access, licence and more. Click a dataset for its score breakdown, warnings, columns, portal checks and every file with download links.
- **Spreadsheets** (UTF-8 CSV, open in Excel), each starting with a `province` column:
  - [`data/datasets.csv`](data/datasets.csv): one row per dataset, 43 columns, including the score and every warning
  - [`data/files.csv`](data/files.csv): one row per file (116,188), with format, last change, size, download link and the portal's file checks
  - [`data/columns.csv`](data/columns.csv): one row per column of each dataset's main table (94,422 rows)

To open the interactive index locally, serve the folder (browsers block the page's data files when it is opened as a plain file):

```bash
python -m http.server 8000 --directory docs
```

Then go to http://localhost:8000.

## The portals

| Code | Portal | Platform | Datasets | What is included |
|---|---|---|---|---|
| QC | [donneesquebec.ca](https://www.donneesquebec.ca) | CKAN | 1,614 | everything |
| ON | [data.ontario.ca](https://data.ontario.ca) | CKAN | 1,137 | open datasets only (`access_level:open`) |
| BC | [catalogue.data.gov.bc.ca](https://catalogue.data.gov.bc.ca) | CKAN | 2,445 | public downloads only |
| AB | [open.alberta.ca](https://open.alberta.ca) | CKAN | 3,018 | open data only, not the 34,500 publications |
| YT | [open.yukon.ca](https://open.yukon.ca) | CKAN | 493 | data only, not publications or access-to-information requests |
| NT | [opendata.gov.nt.ca](https://opendata.gov.nt.ca) | CKAN | 341 | everything |
| NL | [open.canada.ca](https://open.canada.ca) | CKAN | 76 | the province's records copied to the federal portal: opendata.gov.nl.ca answered every call with HTTP 500 |
| NS | [data.novascotia.ca](https://data.novascotia.ca) | Socrata | 713 | datasets, not charts, maps or stories |
| NB | [gnb.socrata.com](https://gnb.socrata.com) | Socrata | 319 | datasets, not charts, maps or stories |
| MB | [geoportal.gov.mb.ca](https://geoportal.gov.mb.ca) | ArcGIS Hub | 123 | the Hub `dataset` collection |
| SK | [geohub.saskatchewan.ca](https://geohub.saskatchewan.ca) | ArcGIS Hub | 129 | the Hub `dataset` collection (map data; Saskatchewan has no general portal) |
| PE | [data.princeedwardisland.ca](https://data.princeedwardisland.ca) | ArcGIS Hub | 90 | the Hub `dataset` collection |
| CA | [open.canada.ca](https://open.canada.ca) | CKAN | 13,845 | federal departments, core collection only (not the provincial copies, publications or the geospatial collections) |
| NU | none | | 0 | Nunavut has no open data portal |

Ontario also lists 1,007 datasets "under review" and 820 "restricted": promised, but with no data. They aren't in the index.

## How the portals compare (2026-10-22)

| Portal | Datasets | A | B | C | D | Median score | With a column list |
|---|---|---|---|---|---|---|---|
| Québec | 1,614 | 505 | 558 | 389 | 162 | 76 | 71% |
| Nova Scotia | 713 | 5 | 451 | 156 | 101 | 71 | 100% |
| Manitoba | 123 | 0 | 50 | 64 | 9 | 63 | 98% |
| Saskatchewan | 129 | 0 | 35 | 73 | 21 | 62 | 86% |
| New Brunswick | 319 | 0 | 115 | 147 | 57 | 59 | 100% |
| Prince Edward Island | 90 | 0 | 1 | 78 | 11 | 58 | 100% |
| Ontario | 1,137 | 107 | 106 | 365 | 559 | 55 | 38% |
| Federal | 13,845 | 65 | 896 | 5,160 | 7,724 | 52 | 8% |
| British Columbia | 2,445 | 42 | 427 | 622 | 1,354 | 52 | 62% |
| Yukon | 493 | 0 | 0 | 44 | 449 | 45 | 0% |
| Newfoundland and Labrador | 76 | 0 | 0 | 0 | 76 | 43 | 0% |
| Alberta | 3,018 | 0 | 93 | 219 | 2,706 | 39 | 0% |
| Northwest Territories | 341 | 0 | 1 | 5 | 335 | 29 | 3% |

Column lists come from the CKAN DataStore (Québec, Ontario, BC, Northwest Territories, federal), the catalogue (BC, Nova Scotia, New Brunswick) or the feature service (ArcGIS Hub). Alberta has 306 DataStore tables, but its DataStore answered every call with HTTP 500 on 2026-10-22, so it has no column lists. Yukon and the Newfoundland records have no DataStore tables.

| Freshness | Datasets |
|---|---|
| On schedule (promised frequency met) | 3,726 |
| Running late (up to 3× the promised interval) | 933 |
| Overdue (more than 3× the promised interval) | 4,374 |
| No fixed schedule, changed in the last year | 1,976 |
| No fixed schedule, 1–3 years without a change | 2,741 |
| No fixed schedule, 3+ years without a change | 4,875 |
| Archive (kept for history) | 258 |
| No dates | 5,460 |

Most "No dates" are federal: 5,451 records whose only date is a bulk catalogue load (see [`CANADA-PLAN.md`](CANADA-PLAN.md), section 13).

## What the index tells you about each dataset

| Field | Where it comes from |
|---|---|
| Contents | Description, methodology notes, keywords, themes, the list of files, and the column names, types and row count of the main table |
| Promised update frequency | The publisher's own setting (daily, weekly, monthly, yearly, as needed, …), mapped onto one list for every portal; "Not stated" where the portal has no such field |
| Last data change | The newest "last modified" date among the dataset's data files, else the portal's own data date for the dataset, else the date a file was added |
| Freshness | Last data change compared with the promised frequency: on schedule, running late, overdue, or for unscheduled datasets, how long since the last change |
| Quality score and grade | Six checks out of 100 points, see below |
| Warnings | Plain-language reasons the score lost points: overdue updates, missing column descriptions, no open licence, PDF-only data, failed portal checks, no contact |
| Licence, coverage, contact, popularity | Licence and whether commercial reuse is allowed, area and time covered, publisher contact, and the portal's view counters |

## How the score works

| Check | Points | How points are given |
|---|---|---|
| Freshness | 25 | Newest data date vs. the promised frequency. On schedule (within 1.5× the interval plus a week): 25. Late (within 3×): 12. Overdue: 0. No fixed schedule: changed in the last year 18, in 1–3 years 10, older 4. Archives 15. No dates 10. |
| Open format | 15 | 15 for an open machine-readable format (CSV, JSON, GeoJSON, XML, GeoPackage, Shapefile, KML…). 9 for Excel, file geodatabases, ZIP or map services only. 0 for PDF, web pages or images only. Socrata datasets and Hub feature layers always offer CSV, so 15. |
| API access | 10 | 10 when at least one file can be queried row by row through the portal's API (a CKAN DataStore table or a Socrata dataset). 7 for a web map or feature service. |
| Documentation | 25 | Description length (up to 7), column descriptions as a document or in the metadata (8), methodology notes (5), time coverage stated (3), contact email (2). |
| Portal checks | 15 | Share of the portal's own file checks that were met: Données Québec's publisher checklist (UTF-8, comma separator, not compressed, standard projection, empty unknown values, ISO dates, `.` decimals, simple booleans) and Ontario's automatic file validation. 8 when there are none. |
| Licence | 10 | 10 when commercial reuse is allowed (CC BY, CC BY-SA, CC0, the Open Government Licences). 6 for no-derivatives. 3 for non-commercial and Crown copyright terms. 0 with no open licence. |

Grades: **A** from 85, **B** from 70, **C** from 55, **D** below 55.

**Same rules everywhere.** A field the portal doesn't have gets neutral points, and a field the portal has but the publisher left empty gets 0. So methodology gets 3 of 5 and time coverage 2 of 3 on portals with no such field, and portal checks 8 of 15 where there are none. Without this, datasets would lose points for fields their portal never offered.

**Limits.** The score only uses what the catalogue says about each dataset. It shows how well a dataset is maintained and documented, not whether its values are correct, so look at the files before you depend on one. Portal checks are answers the publisher filled in (Québec) or the portal's own validation (Ontario), not tests run by this index. Column lists cover only the main table of each dataset; the DataStore stores many columns as `text` even when they hold numbers or dates. Datasets served only as external links have no column list. Decisions and findings for each portal are in [`CANADA-PLAN.md`](CANADA-PLAN.md), sections 10 to 14.

## Québec notes

The index started with Québec alone, so a few things exist only there:

- **Publisher checklist.** Données Québec asks publishers to answer eight yes/no checks per file (the `relidi_*` fields). They are the only portal checks besides Ontario's validation.
- **Broken API tables.** 11 datasets list a file as queryable through the API, but the API returns "not found" for its table. The index flags them.
- **Sitemaps.** The project started by crawling the site's sitemaps. They list 240 WordPress pages (news, guides, data standards, publishers) and **no datasets at all**, because the catalogue is a separate CKAN site with no sitemap. Details in [`sitemaps/README.md`](sitemaps/README.md).

## How it was built

Everything uses Python 3 with the standard library only. The portals are listed in [`scripts/portals.py`](scripts/portals.py).

| Step | Script | Output |
|---|---|---|
| 1. Crawl the Québec WordPress sitemaps | [`scripts/crawl_sitemaps.py`](scripts/crawl_sitemaps.py) | `sitemaps/sitemap_urls.csv` |
| 2. Download each portal's catalogue (CKAN `package_search` and the Socrata catalogue 500 datasets per call, the Hub search 100 per call plus each item's record and feature service) | [`scripts/fetch_catalogue.py`](scripts/fetch_catalogue.py) | `raw/<code>/packages.json.gz` |
| 3. Download Données Québec's field definitions | `curl` of `scheming_dataset_schema_show` | `raw/QC/schema.json` |
| 4. Fetch the column list and row count of each dataset's main DataStore table on the CKAN portals (one `datastore_search?limit=0` call per dataset, 1.2 s apart; 3 at a time on the federal portal, whose DataStore is slow) | [`scripts/fetch_columns.py`](scripts/fetch_columns.py) | `raw/<code>/columns.jsonl` |
| 5. Turn each portal's catalogue into common records, score every dataset and write the CSVs and page data | [`scripts/normalize.py`](scripts/normalize.py), [`scripts/build_index.py`](scripts/build_index.py) | `data/*.csv`, `site/index.json` (one slim row per dataset, loaded at start), `site/detail/<code>.json` (full records, loaded when a dataset from that portal is opened) |
| 6. Package the page for static hosting | [`scripts/make_site.py`](scripts/make_site.py) | `docs/index.html`, `docs/index.json`, `docs/detail/` |

[`run_all.sh`](run_all.sh) runs all six steps for a fresh snapshot (about an hour and a half, mostly the polite column fetch):

```bash
./run_all.sh 2026-11-01
```

If a portal is down, its download is skipped and the build reuses its last snapshot in `raw/`. The run ends with a warning listing what was skipped.

The repository itself was created and pushed with the GitHub CLI by [`publish.sh`](publish.sh).

## Data licence

Contains information from the open data portals listed above, used under their licences: [Creative Commons Attribution 4.0](https://www.donneesquebec.ca/licence/) for Données Québec, and the Open Government Licence of Canada or of each province or territory for the others. Some datasets use other licences, including non-commercial ones and none at all. Each dataset's licence is listed in `data/datasets.csv` and in the index.
