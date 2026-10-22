# Quebec Open Data Index

An index of **every dataset published on [donneesquebec.ca](https://www.donneesquebec.ca)**, Québec's open data portal. For each dataset it lists what it contains, how often the publisher promised to update it, when it last changed, and a quality score to help you decide whether you can rely on it.

Snapshot: **2026-10-22** · **1,614 datasets** · **120 publishers** · **11,763 files** · column lists for **1,149 datasets**

> Unofficial. Built from the portal's public catalogue API. Not affiliated with Données Québec or the Gouvernement du Québec.

## Browse it

- **Interactive index:** [`docs/index.html`](docs/index.html). Search by title, topic or column name. Filter by publisher, theme, update frequency, format, grade, freshness, API access, licence and more. Click a dataset for its score breakdown, warnings, columns, portal checks and every file with download links.
- **Spreadsheets** (UTF-8 CSV, open in Excel):
  - [`data/datasets.csv`](data/datasets.csv): one row per dataset, 42 columns, including the score and every warning
  - [`data/files.csv`](data/files.csv): one row per file (11,763), with format, last change, size, download link and the portal's file checks
  - [`data/columns.csv`](data/columns.csv): one row per column of each dataset's main table (17,638 rows)

To open the interactive index locally, serve the folder (browsers block `data.json` when the page is opened as a plain file):

```bash
python -m http.server 8000 --directory docs
```

Then go to http://localhost:8000.

## What the index tells you about each dataset

| Field | Where it comes from |
|---|---|
| Contents | Description, methodology notes, keywords, themes, the list of files, and the column names, types and row count of the main table |
| Promised update frequency | The publisher's own setting (daily, weekly, monthly, yearly, as needed, …) |
| Last data change | The newest "last modified" date among the dataset's data files (or the date a file was added when no change date exists) |
| Freshness | Last data change compared with the promised frequency: on schedule, running late, overdue, or for unscheduled datasets, how long since the last change |
| Quality score and grade | Six checks out of 100 points, see below |
| Warnings | Plain-language reasons the score lost points: overdue updates, missing column descriptions, non-commercial licence, PDF-only data, failed portal checks, no contact |
| Licence, coverage, contact, popularity | Licence and whether commercial reuse is allowed, area and time covered, publisher contact, and the portal's view counters |

### Current picture (2026-10-22)

| Grade | Datasets | Share |
|---|---|---|
| A (85+) | 505 | 31% |
| B (70–84) | 558 | 35% |
| C (55–69) | 389 | 24% |
| D (under 55) | 162 | 10% |

| Freshness | Datasets |
|---|---|
| On schedule (promised frequency met) | 478 |
| Running late (up to 3× the promised interval) | 72 |
| Overdue (more than 3× the promised interval) | 190 |
| No fixed schedule, changed in the last year | 236 |
| No fixed schedule, 1–3 years without a change | 206 |
| No fixed schedule, 3+ years without a change | 383 |
| Archive (kept for history) | 48 |
| No dates | 1 |

11 datasets list a file as queryable through the API, but the API returns "not found" for its table. The index flags them.

## How the score works

| Check | Points | How points are given |
|---|---|---|
| Freshness | 25 | Newest data file date vs. the promised frequency. On schedule (within 1.5× the interval plus a week): 25. Late (within 3×): 12. Overdue: 0. No fixed schedule: changed in the last year 18, in 1–3 years 10, older 4. Archives 15. No dates 10. |
| Open format | 15 | 15 for an open machine-readable format (CSV, JSON, GeoJSON, XML, GeoPackage, Shapefile, KML…). 9 for Excel, file geodatabases, ZIP or map services only. 0 for PDF, web pages or images only. |
| API access | 10 | 10 when at least one file is in the portal's DataStore and can be queried row by row. 7 for a web map or feature service. |
| Documentation | 25 | Description length (up to 7), column descriptions as a document or in the metadata (8), methodology notes (5), time coverage stated (3), contact email (2). |
| Portal checks | 15 | Share of the portal's own file checks the publisher marked as met: UTF-8, comma separator, not compressed, standard projection (EPSG 4326/32198), empty unknown values, ISO dates, `.` decimals, simple booleans. 8 when none were filled in. |
| Licence | 10 | 10 when commercial reuse is allowed (CC BY, CC BY-SA, CC0, OGL). 6 for no-derivatives. 3 for non-commercial. |

Grades: **A** from 85, **B** from 70, **C** from 55, **D** below 55.

**Limits.** The score only uses what the catalogue says about each dataset. It shows how well a dataset is maintained and documented, not whether its values are correct, so look at the files before you depend on one. The portal checks are answers the publisher filled in, not tests run on the files. Column lists cover only the main queryable table of each dataset (the most recently changed data file loaded in the DataStore); the DataStore stores many columns as `text` even when they hold numbers or dates. Datasets served only as map services or external links have no column list.

## Sitemaps

The project started by crawling the site's sitemaps. They list 240 WordPress pages (news, guides, data standards, publishers) and **no datasets at all**, because the catalogue is a separate CKAN site with no sitemap. Details in [`sitemaps/README.md`](sitemaps/README.md).

## How it was built

Everything uses Python 3 with the standard library only.

| Step | Script | Output |
|---|---|---|
| 1. Crawl the WordPress sitemaps | [`scripts/crawl_sitemaps.py`](scripts/crawl_sitemaps.py) | `sitemaps/sitemap_urls.csv` |
| 2. Download the full catalogue (4 calls to `package_search`, 500 datasets each) | [`scripts/fetch_catalogue.py`](scripts/fetch_catalogue.py) | `raw/packages.json` |
| 3. Download the portal's field definitions | `curl` of `scheming_dataset_schema_show` | `raw/schema.json` |
| 4. Fetch the column list and row count of each dataset's main table (one `datastore_search?limit=0` call per dataset, 1.2 s apart) | [`scripts/fetch_columns.py`](scripts/fetch_columns.py) | `raw/columns.jsonl` |
| 5. Score every dataset and write the CSVs and page data | [`scripts/build_index.py`](scripts/build_index.py) | `data/*.csv`, `site/data.json` |
| 6. Package the page for static hosting | [`scripts/make_site.py`](scripts/make_site.py) | `docs/index.html`, `docs/data.json` |

[`run_all.sh`](run_all.sh) runs all six steps for a fresh snapshot (about an hour, mostly the polite column fetch):

```bash
./run_all.sh 2026-11-01
```

The repository itself was created and pushed with the GitHub CLI by [`publish.sh`](publish.sh).

## Data licence

Contains information from [Données Québec](https://www.donneesquebec.ca), used under the [Creative Commons Attribution 4.0](https://www.donneesquebec.ca/licence/) licence. Some datasets use other licences, including non-commercial ones. Each dataset's licence is listed in `data/datasets.csv` and in the index.
