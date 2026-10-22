# Plan: from Quebec Open Data Index to Canada Open Data Index

Goal: the same index we built for donneesquebec.ca (every dataset, promised update frequency, last data change, freshness, 100-point quality score, warnings, columns, files) for every province and territory, on one site, scored by the same rules so provinces can be compared.

Portal facts below come from live API calls made on 2026-10-22.

## 1. The portals

| Code | Portal | Platform | Records in catalogue | In scope | Filter |
|---|---|---|---|---|---|
| QC | donneesquebec.ca | CKAN | 1,614 | 1,614 | none (already done) |
| ON | data.ontario.ca | CKAN | 2,964 | **1,137** | `access_level:open` (1,007 are "under review", 820 "restricted": listed but no data) |
| BC | catalogue.data.gov.bc.ca | CKAN | 3,364 | **2,445** | `download_audience:Public` (the rest are government-only, named users or not downloadable) |
| AB | open.alberta.ca | CKAN | 37,537 | **3,018** | `type:opendata` (34,500 are publications: reports, fact sheets) |
| YT | open.yukon.ca | CKAN (since Aug. 2025) | 3,856 | **493** | `type:data` (the rest are publications, access-to-information requests, privacy impact assessment summaries) |
| NT | opendata.gov.nt.ca | CKAN | 341 | 341 | none |
| NL | opendata.gov.nl.ca | CKAN (not confirmed) | ? | ? | **Every URL returned HTTP 500 on 2026-10-22, gov.nl.ca too.** Fallback: the 76 NL records copied to open.canada.ca (`organization:nl-tnl`) |
| NS | data.novascotia.ca | Socrata | 713 | 713 | `only=dataset` |
| NB | gnb.socrata.com | Socrata | 319 | 319 | `only=dataset` |
| MB | geoportal.gov.mb.ca (DataMB) | ArcGIS Hub | 123 | 123 | Hub `dataset` collection |
| SK | geohub.saskatchewan.ca | ArcGIS Hub | 129 | 129 | Hub `dataset` collection (map data only; Saskatchewan has no general portal) |
| PE | data.princeedwardisland.ca | ArcGIS Hub (moved off Socrata) | 90 | 90 | Hub `dataset` collection |
| NU | none | none | 0 | 0 | No portal. Shown on the site as "no portal" and not filled from federal data |

**About 10,400 datasets in scope**, 6.5 times Quebec alone. Three platforms, so three fetchers, not twelve.

The federal portal (open.canada.ca, CKAN, 48,151 records) also holds 11,746 records copied from the provinces, so most provinces would appear there twice. It stays out of v1 (see section 9).

## 2. What has to change

`build_index.py` reads the Données Québec CKAN schema directly: `update_frequency` codes, `methodologie`, `resource_type == "donnees"`, the `relidi_*` checklist and `extras_*` fields. No other portal has those fields. So the work is:

1. **Fetch** each portal's catalogue into `raw/<code>/`.
2. **Normalize** each portal's records into one common shape (new `scripts/normalize.py`, one function per platform plus small per-portal field maps).
3. **Score** the common shape with today's rules, unchanged (`build_index.py`, loop body rewritten to read the common shape).
4. **Publish** one site with a province filter and a province comparison table.

### Files after the change

```
scripts/
  portals.py          # one dict: code -> name, platform, API base, filter, field map
  fetch_catalogue.py  # python scripts/fetch_catalogue.py ON raw/ON   (ckan | socrata | hub)
  fetch_columns.py    # CKAN DataStore (QC, ON, NT); skipped where the catalogue already has columns (Hub layers come with the catalogue)
  normalize.py        # raw/<code>/ -> common records
  build_index.py      # scoring, warnings, CSV and JSON, all provinces
  make_site.py        # unchanged except copying several JSON files
site/page.html        # province filter, province column, comparison table, lazy-loaded details
run_all.sh            # loops over portals.py codes
```

`crawl_sitemaps.py` stays as Quebec history. It isn't run for other provinces, because sitemaps had no datasets in them for Quebec either.

### Common record (what `normalize.py` returns per dataset)

`province, id, slug, title, url, publisher, parent, themes, tags, description, methodology, frequency (one of the FREQ codes or "notStated"), time_coverage, contact, email, licence_id, licence_title, files[], checks, columns, views, spatial_coverage, geospatial, standard, reference, language`

Each file in `files[]`: `name, format, kind (data | doc | service), last_modified, added, size, url, queryable`.

The fields a portal has no equivalent for are `None`, not `""`, so scoring can tell "portal doesn't have this field" apart from "publisher left it empty" (see section 4).

## 3. Field map per platform

| Need | CKAN (QC, ON, BC, AB, YT, NT, NL) | Socrata (NS, NB) | ArcGIS Hub (MB, SK, PE) |
|---|---|---|---|
| Catalogue call | `package_search?rows=500&start=N&fq=<filter>` (existing loop) | `/api/catalog/v1?domains=D&search_context=D&only=dataset&order=name&limit=500&offset=N` | `/api/search/v1/collections/dataset/items?sortBy=properties.title&limit=100&startindex=N`, then each item's live record from ArcGIS Online |
| Promised frequency | QC `update_frequency`; ON `update_frequency`; AB `updatefrequency`; YT, NT `update_frequency`; BC per-file `resource_update_cycle` (use the most frequent promise among data files) | NS `domain_metadata` "Detailed-Metadata_Frequency"; NB none | ISO `MaintFreqCd` in the item's formal metadata, where filled |
| Last data change | newest file `last_modified` (existing rule); ON also has `data_last_updated` | `data_updated_at` (true data date) | newest layer `editingInfo.dataLastEditDate` (else `lastEditDate`) from the FeatureServer call, else the metadata `reviseDate`, else item `modified` (with a warning that it's a metadata date) |
| Columns | DataStore `datastore_search?limit=0` (QC, ON, NT); BC per-file `details` (column name, type, comment), no extra call | in catalogue: `columns_name`, `columns_datatype`, `columns_description` | one FeatureServer layer call per item gives `fields` |
| Methodology | QC `methodologie`; BC `lineage_statement` | none | formal metadata lineage statement, where filled |
| Time coverage | QC `temporal`; AB `time_coverage_from/to`; YT `temporal_coverage_*`; NT `starting/ending_time_range`; ON file `data_range_start/end` | NS `domain_metadata` "Detailed-Metadata_Time-Period-Coverage"; NB none | none |
| Portal checks | QC publisher checklist (`relidi_*`); ON Frictionless `validation_status` per file (a real test of the file) | none | none |
| Views | QC `tracking_summary`; YT `visits`, `visit_90_days` | `page_views` | `numViews` |
| Dataset page | `{site}/dataset/{name}` | `https://{domain}/d/{id}` | `{site}/datasets/{id}` |

### Frequency vocabularies to map onto the existing `FREQ` codes

| Portal value | Code |
|---|---|
| ON `daily`, `weekly`, `monthly`, `quarterly`, `yearly`, `quinquennial` | same meaning |
| ON `biannually` | `semiannual` |
| ON `current` | `continuous` |
| ON `as_required`, `on_demand`, `periodically` | `asNeeded` |
| ON `other` | `irregular` |
| ON `historical` | `archives` |
| ON `never` | `notPlanned` |
| AB, YT, NT, NS, BC values | lowercase, then the same table; the full list comes from a facet call at build time |
| MB, SK, PE ISO codes `001` continual … `011` notPlanned | same meaning (`004` fortnightly is `biweekly`, `007` biannually is `semiannual`) |
| no field (NB; MB, SK, PE items whose metadata has none) | new code `notStated`: scored like "no fixed schedule", plus the warning "No update frequency promised" |

## 4. Scoring across provinces

The six checks and their weights stay exactly as in the README. Two rules keep the comparison fair:

- **Portal has no such field → neutral points; field exists but is empty → 0.** Quebec already does this for portal checks (8 of 15 when none are filled in). The same half-points-rounded-up rule applies to methodology (3 of 5) and time coverage (2 of 3) on portals that don't have those fields. Without this rule, most non-Quebec datasets would lose up to 8 points (methodology 5, time coverage 3) for fields their portal never offered.
- **Platform defaults follow the existing rules, not new ones.**
  - Format: Socrata tabular datasets and Hub feature layers always offer CSV/GeoJSON downloads, so 15.
  - API: Socrata's SODA API is row-level querying, like the DataStore, so 10. Hub FeatureServers count as "map or feature service", so 7, same as Quebec.

Licences: map each portal's `license_id`/title. The Open Government Licence variants (OGL-Ontario, OGL-BC, OGL-Alberta, OGL-NWT, OGL-Yukon, OGL-NS, OGL-NB, OGL-Manitoba) all allow commercial reuse, so 10. `licence_info()` already handles CC variants.

## 5. Site and outputs

- **Size.** Today's `data.json` is 7.1 MB for 1,614 datasets, about 4.4 KB each. 6.5 times that (around 46 MB) is too much for one load. Split it:
  - `docs/index.json`: one slim row per dataset (title, province, publisher, grade, score, freshness, frequency, formats, licence, flags count), about 4 MB for everyone, loaded at start.
  - `docs/detail/<code>.json`: full records for one province, fetched the first time a dataset from that province is opened.
- **Page.** Add a province filter (first filter), a province column, and a comparison table at the top: datasets, grade spread, freshness spread, median score, share with columns, per province. That table is the new headline.
- **CSVs.** Same three files with a `province` column first. `files.csv` grows from 6 MB to roughly 40 MB, still under GitHub's 100 MB limit.
- **raw/.** Quebec's `raw/packages.json` is already 27 MB. Store `raw/<code>/packages.json.gz` (stdlib `gzip`) so snapshots stay committed and the repo stays small.
- **README.** Becomes Canada-wide: portal table, comparison table, scoring rules with the neutral-points rule. Quebec-specific notes (the `relidi_*` checklist, the sitemap finding) move to a Quebec section.

## 6. Order of work

Each phase ends with something that runs.

| Phase | Work | Done when |
|---|---|---|
| 0 | Decide the open questions in section 8 | answers written here |
| 1 | `portals.py` with QC only; `normalize.py` with the CKAN normaliser and QC field map; rewrite the `build_index.py` loop to read common records; move raw to `raw/QC/` | **Rerun on today's Quebec raw data gives the same `datasets.csv`, `files.csv` and `columns.csv` as now, apart from the new `province` column** (diff is the test). **Done 2026-10-22:** all three CSVs match row for row, and `data.json` matches apart from the new `pr` and `u` keys |
| 2 | CKAN provinces: ON, BC, AB, YT, NT (and NL if the portal is back); field maps; filters; frequency and licence tables | ~7,400 more datasets build; every frequency and licence value seen is mapped (the build stops and lists any that aren't). **Done 2026-10-22:** 7,510 more datasets (9,124 in all); decisions in section 10 |
| 3 | Socrata fetcher and normaliser: NS, NB | 1,032 more; columns come from the catalogue. **Done 2026-10-22:** 1,032 more datasets (10,156 in all); the 9,124 earlier rows are unchanged; decisions in section 11 |
| 4 | Hub fetcher and normaliser: MB, SK, PE, plus one FeatureServer call per item for fields and last edit date | 342 more. **Done 2026-10-22:** 342 more datasets (10,498 in all); the 10,156 earlier rows are unchanged; decisions in section 12 |
| 5 | Columns: DataStore for ON and NT through the existing `fetch_columns.py` (it already resumes and waits 1.2 s per call) | column lists for every platform that has them. **Done 2026-10-22** for ON, NT, BC and the federal portal too: 2,061 more datasets with a column list (5,592 in all); AB's DataStore is broken; decisions in section 14 |
| 6 | Split JSON, province filter, comparison table, README, `run_all.sh` loop | the site serves locally and on Pages. **Split done 2026-10-22** (section 13). **Rest done 2026-10-22:** portal filter, portal name on each row and in the dataset panel, "Portals compared" table at the top (sorted by median score, Nunavut as "no open data portal"; clicking a portal filters the list), Canada-wide page header, method notes and README, `run_all.sh` reads its portal list from `portals.py`, and `data/` and `docs/` rebuilt for all 24,343 datasets. Checked locally; Pages updates on the next push |
| 7 | Rename the repo (if chosen) and publish | live link works |

Phase 2 covers 84% of the new datasets with one fetcher, so it goes first after the refactor.

## 7. Checks

- Phase 1 regression diff on Quebec (above). It's the guard for the whole refactor.
- `normalize.py` asserts every frequency and licence value it meets is in the map, and prints the unmapped ones. Twelve vocabularies drift; this catches it at build time instead of silently scoring `None`.
- After each phase, spot-check five datasets per province against the live portal page: title, last change, frequency, file count.

## 8. Open decisions

| Question | Recommendation |
|---|---|
| Rename the repo to `canada-open-data-index`? | Yes, with `gh repo rename`. GitHub redirects the repo URL, but the old GitHub Pages URL stops working, so update any links shared so far. |
| Include Ontario's "under review" and "restricted" entries? | No. They have no data. Report their counts in the README, since 1,827 promised-but-unpublished datasets is a finding in itself. |
| Newfoundland if its portal stays down? | Retry first. If it's still down at build time, use the 76 records on open.canada.ca, and say on the site that the source is the federal copy. |
| Nunavut? | Show it in the comparison table as "no portal". Don't fill it with federal department data about Nunavut. |
| Run portals in parallel? | No. Sequential runs take about an hour, mostly column fetches, and staying polite to small portals matters more. |

## 9. Later, not in v1

- ~~**Federal portal**~~ Added 2026-10-22 with the core collection only (13,845 records), see section 13. Still out: its geospatial collections (`geogratis` 9,799, mostly one Natural Resources Canada record per survey site; `fgp` 2,253), publications (8,158) and parliamentary records.
- **Municipal portals** (Montréal, Toronto, Calgary, Vancouver, Ottawa, …). Same three platforms, so mostly config once v1 exists.
- **Snapshot history**: keep each run's slim index, to chart freshness over time per province.

## 10. Phase 2 decisions and findings (2026-10-22)

**Result** (snapshot 2026-10-22; columns for BC come from its catalogue, DataStore columns for ON and NT wait for phase 5):

| Province | Datasets | A | B | C | D | Median score |
|---|---|---|---|---|---|---|
| QC | 1,614 | 505 | 558 | 389 | 162 | 76 |
| ON | 1,137 | 80 | 124 | 373 | 560 | 55 |
| BC | 2,445 | 42 | 427 | 622 | 1,354 | 52 |
| AB | 3,018 | 0 | 93 | 219 | 2,706 | 39 |
| YT | 493 | 0 | 0 | 44 | 449 | 45 |
| NT | 341 | 0 | 1 | 5 | 335 | 29 |
| NL | 76 | 0 | 0 | 0 | 76 | 43 |

**Scoring changes, applied to every province:**
- **Publisher's data date as a fallback.** When no data file has a modified date, use the portal's own dataset-level data date (ON `current_as_of`, BC `dates` Modified/Revised, AB `date_modified`, NT `modified_date`) before falling back on when the file was added. Without it, Alberta's records, re-imported on 2026-09-06, all looked fresh. Quebec has no such field, so it's unaffected.
- **Neutral half points** for methodology (3 of 5) and time coverage (2 of 3) where the portal has no such field (section 4).
- **"Not stated" frequency** (new code `notStated`) scores like "no fixed schedule" and adds the warning "No update frequency promised". There's also a new code `biweekly` (14 days).
- **Licences.** Creative Commons is scored as before. Every other licence is listed by title in `LICENCES` in `build_index.py`: 10 for open licences, 3 for Crown copyright terms that allow non-commercial reproduction (King's Printer, Ontario.ca terms), and 0 for no open licence ("Access Only", "No licence", "Not specified", ministry terms of use), with the new warning "No open licence". BC's King's Printer licence and the old Ontario Open Data Terms of Use (4 datasets) aren't checked against their full text.
- **Mislabelled links are corrected** (`fix_links` in `normalize.py`). A web-page link whose URL ends in `.csv`, `.zip` and so on takes that format. `…/metadata/….xml` becomes a `METADATA` document, not data, and an ArcGIS Online item page counts as a map service. For Quebec this only changed the format list of 23 datasets; no score moved.
- **Quebec's `files.csv`** now shows the checklist answers as `yes`/`no`/`n/a` (was `oui`/`non`/`n/a`), and column descriptions as "Separate document" / "In the description" / "Missing" (was the `relidi.descha.*` codes).

**Per-portal findings:**
- **AB:** 1,339 of the 3,018 records are Alberta Energy Regulator map layers imported from GeoDiscover. Their only links are metadata pages (no data files), they promise updates "every 2 months", and they were last dated 2016, so they're overdue.
- **BC:** 543 public records are "Access Only" (no open licence). Geographic Warehouse layers are scored as open formats (`MULTIPLE`: shapefile, CSV, file geodatabase or KML on request).
- **YT:** most records link to ArcGIS Online items and GeoYukon pages, not files. 428 of 493 promise "ad hoc" updates. Dataset pages are `open.yukon.ca/data/{name}`.
- **NT:** descriptions are title-length (median 54 characters), no record gives a contact email, and 286 of 341 records only link to a StatsNWT web page.
- **NL:** the portal still returned HTTP 500, so the index uses the 76 federal copies. Their file and modified dates are federal sync dates (64 records share 2026-02-06), so freshness uses the original publication date (2013–2016) and the frequency is "unknown".

## 11. Phase 3 decisions and findings (2026-10-22)

**Result** (snapshot 2026-10-22; columns come from the catalogue, row counts aren't in it):

| Province | Datasets | A | B | C | D | Median score |
|---|---|---|---|---|---|---|
| NS | 713 | 5 | 451 | 156 | 101 | 71 |
| NB | 319 | 0 | 115 | 147 | 57 | 59 |

**How a Socrata dataset is read:**
- One dataset is one table, so it gets one data file: the CSV export (`/api/views/{id}/rows.csv`), marked queryable because the SODA API serves the same rows. That gives the platform defaults from section 4: format 15, API 10. There are no portal checks, so 8 of 15.
- Last data change is `data_updated_at`; "on portal since" is `publication_date`.
- Column names are the CSV headers, so a column only counts as documented when it has a description (78 NS datasets, 7 NB).
- Methodology gets the neutral half points on both portals. NS has a time coverage field (`Time-Period-Coverage`, filled on 555 of 713), so an empty one scores 0 there; NB has none, so neutral.
- A record with no licence (NS 4, NB 2) is read as "Licence not specified": 0 points and the "No open licence" warning. The NS and NB Open Government Licences and the Canada one (4 NB records) score 10.
- The fetcher checks that the number of distinct ids matches the catalogue count, because Socrata names aren't unique and a page boundary between two equal names could repeat or skip one.

**Per-portal findings:**
- **NS:** 141 datasets are retired: "[ARCHIVED]" in the title and "ARCHIVED on <date>" in Usage Considerations, with a "One-time" frequency. They're scored as archives (15 freshness points, "Archive" warning), as Quebec's are. The other 74 "One-time" records are "no updates planned". "Bi-Annually" (28) is read as twice a year, like Ontario's `biannually`; NS doesn't define it. Publisher is the `Department` field (28 departments). No record gives a contact email. 52 records name a data dictionary or guide in the free-text Related Documents field, but it isn't a linked file, so it isn't counted (46 of them already have column descriptions).
- **NB:** no update frequency field at all, so all 319 are "Not stated". 122 records are Statistics Canada tables republished by the province; publisher is the `Department` field where filled (162), else the attribution. 31 GeoNB records give an ArcGIS map service URL, added as a service file. 152 of 319 haven't changed in 3+ years. No record gives a contact email.

## 12. Phase 4 decisions and findings (2026-10-22)

**Result** (snapshot 2026-10-22; columns come from the FeatureServer layer call, row counts aren't fetched):

| Province | Datasets | A | B | C | D | Median score |
|---|---|---|---|---|---|---|
| MB | 123 | 0 | 50 | 64 | 9 | 63 |
| SK | 129 | 0 | 35 | 73 | 21 | 62 |
| PE | 90 | 0 | 1 | 78 | 11 | 58 |

**How a Hub item is read:**
- The fetcher pages the site's search API by title (same distinct-id check as Socrata), then makes three kinds of extra call, 1.2 s apart: one ArcGIS Online search per 50 items for the live item records, one `/layers` call per service, and one formal metadata call per item that has metadata. The live record wins because Hub's search index lags: 49 SK items had a `modified` date days behind the item (47 by 76 days) and 14 had older licence text. Thumbnails embedded in the metadata are dropped (5.3 MB of MB's 7.9 MB of metadata).
- A feature service gives one CSV data file per layer (Hub's download API, `{site}/api/download/v1/items/{id}/csv?layers=N`) plus the service itself, so format 15 and API 7. An item that is one file (MB 2 file geodatabases; SK 9 shapefiles, 3 file geodatabases, 1 CSV) is that file, with no API. No portal checks, so 8 of 15.
- Last change is the newest layer's `editingInfo.dataLastEditDate`, else `lastEditDate`. `lastEditDate` also moves on schema and service changes (40 of 130 MB layers differ; one moved in 2025 with data unchanged since 2022), and Hub's own "Data updated" uses the data date. With no layer date, the metadata revision date (`reviseDate`) counts as the publisher's date, else the item's `modified` date with the new warning "No data date: last change is when the catalogue entry was last edited" (MB 2, SK 65, PE 18).
- Hub's page shows the metadata revision date ahead of the layer date; the index doesn't, because the layer date is recorded by the server, as file dates are elsewhere. On 24 of the 27 MB items that have both, the layer date is later (e.g. "AW Case Outcomes V03": revised 2022-01-24 in the metadata, data edited 2026-07-22), so the index shows a later date than the page for those (SK 10, PE 3).
- Frequency is the ISO maintenance frequency (`MaintFreqCd`) in the item's formal metadata (filled on MB 43, SK 22, PE 1); the rest are "Not stated". Hub also shows a frequency for updating the metadata itself, which isn't used.
- Formal metadata is optional and not on Hub's dataset form, so an empty value there is read as missing, not as 0: methodology is the lineage statement where filled (MB 31, SK 18), else neutral. No item fills a time extent, so time coverage is neutral everywhere. Contact email is the metadata point of contact, else an email in the item's credits text.
- Columns are the first layer's fields without the object id and geometry, as Hub's table shows them. Field aliases are display names, so only a field description counts as documenting a column (MB 1, SK 3, PE 0 datasets). Hub's table also leaves out `DateOnly` fields, so one MB dataset has 11 columns here and 10 on the page.
- Licences are free text (`licenseInfo`) on all three, so each field map lists patterns that name a licence; text no pattern matches goes to the build as the title, so the build stops on it. The OpenMB Information and Data Use Licence (manitoba.ca/legal/copyright.html), the Government of Saskatchewan Standard Unrestricted Use Data Licence v2.0 (commercial use allowed, checked in the PDF), OGL-Canada and OGL-PEI score 10. Disclaimers that name no licence, and empty text, are "Licence not specified" (0).
- Publisher is the item's `source` where filled, else "Government of <province>".

**Per-portal findings:**
- **MB:** 121 feature services and 2 file geodatabases. Titles and descriptions are bilingual in one field (median description 1,377 characters). The licence text is written 18 ways; all name or link to the OpenMB licence except 5 disclaimers. 74 items give "Manitoba Maps" as the source, so the publisher is coarse. 34 of the 43 stated frequencies are "as needed". 57 had a data edit in 2026, 36 haven't changed in 3+ years.
- **SK:** a map portal, not a general one: 116 feature services (3 backed by map service layers), 9 shapefiles, 3 file geodatabases, 1 CSV. 60 services run on the province's ArcGIS Server without edit tracking, so 65 records fall back on the item date. 10 items bundle 2 to 92 layers (the geology and petroleum services); each layer is a CSV file in `files.csv` and the columns are the first layer's. 5 services are broken: 2 need a sign-in ("Token Required") and 3 point to layers the service no longer publishes, so they have no data files. The 9 road network layers are each listed twice, as a feature service and as a shapefile; the 8 that promise continual updates were edited 2026-10-18 as services but last revised 2025-05-09 as shapefiles, so each pair is on time once and overdue once.
- **PE:** 90 feature services, 72 on ArcGIS Online and 18 on the province's server. 24 have no licence (Hub shows "No licence provided"). There's no source field, so the publisher is "Government of Prince Edward Island"; the contact name and email come from the credits text ("Contact Information: … Contact Email: …", 57 and 55 filled). Descriptions are short (median 106 characters, 16 items have only the summary), so 54 get "Very short description". One item states a frequency (daily). 51 of the 64 numbered "OD" tables last changed in March 2024.
- **All three:** the Hub search API hung on a page twice in about 20 calls and the fetch stopped after its 120 s timeout; running it again worked.

## 13. Site split and federal portal (2026-10-22)

**Split.** `build_index.py` writes `index.json` (one slim row per dataset: what the list, filters, sort and search use) and `detail/<code>.json` (everything the dataset panel shows, keyed by slug). The page fetches a province's detail file the first time one of its datasets is opened, and asks again if that fetch failed.

| File | Size | Gzipped |
|---|---|---|
| `index.json` (24,343 datasets) | 19.2 MB | 3.6 MB |
| `detail/CA.json` (largest) | 31.8 MB | 4.9 MB |
| `detail/QC.json` | 7.2 MB | 1.4 MB |
| `files.csv` (largest CSV) | 49.6 MB | |

- The index row keeps a 260-character description (what the list shows) and a search string `k`: parent organisation, keywords, column names and labels. Search therefore no longer covers the rest of a long description.
- Links come from each record (`u`, and `mu` for the portal's machine-readable record: CKAN `package_show`, Socrata `/api/views/{id}.json`, ArcGIS Online item JSON) instead of being built for donneesquebec.ca. "First 5 rows as JSON" shows only where the columns came from a CKAN DataStore.
- Checked: on the 10,498 datasets before the federal portal, index plus detail merge back to the previous `data.json` records exactly (apart from the new `mu`, `k` and `cols.api`), and all three CSVs are byte for byte the same.

**Federal portal** (`CA`, open.canada.ca, `jurisdiction:federal AND collection:primary`): 13,845 records, 60 departments, 28 catalogue calls, 17 MB gzipped. The full build takes 16 s and about 700 MB of memory.

| Province | Datasets | A | B | C | D | Median score |
|---|---|---|---|---|---|---|
| CA | 13,845 | 65 | 896 | 5,160 | 7,724 | 52 |

- **Field map** `ca()`, which NL now shares: English title and description, the English half of "English \| French" department names, subjects as themes, English keywords as tags (NL's 76 records gain themes and keywords; nothing else in the earlier rows changed), file types `dataset` (data), `guide` / `data_dictionary` / `specification` (documentation), `api` / `web_service` (service).
- **Frequencies** are ISO 8601 durations plus words. New codes `fourmonthly` (P4M, 2 datasets) and `quadrennial` (P4Y, 1). P0.5M (twice a month, 2 datasets) is read as every 2 weeks.
- **Licences:** OGL-Canada on all but 2; the Commissioner of Lobbying's Open Data Licence Agreement allows commercial use, so it scores 10.
- **Bulk-load dates.** Federal files have no change date (StatCan: 2 of 10,010 records have one), only a creation date, and StatCan re-creates a table's files when it releases it. But the catalogue was also reloaded in bulk: 3,738 records were created on 2023-01-17 (437 of their titles end in "inactive"), 1,413 on 2016-12-01 (the migration), 326 on 2023-11-08. A creation date shared by 300+ records is treated as no date, so those 5,451 records are "No dates" (10 of 25 freshness points) instead of "overdue" on a load date. The next largest group is 135 records (2025-05-26), treated as a real release day. 2023-11-08 is the least certain, but 93% of those records promise "as needed" updates, where a 3-year-old date and no date both score 10. StatCan's own site and API were down on 2026-10-22, so release dates couldn't be checked against it.
- **Findings:** Statistics Canada is 10,010 of the 13,845 (median 52; the other departments 55). Average points: freshness 11.3/25, format 14.3/15, API 1.0/10 (only a few files are in the DataStore), documentation 10.2/25, portal checks 8/15 (none, so neutral), licence 10/10. 13,209 have no column descriptions in the catalogue, 2,387 very short descriptions, 1,259 no frequency.
- Checked: 5 random federal records match the live `package_show` on title, frequency, file count and newest file date (the one on a bulk date shows "No dates").
- Not done at the time: column lists (`fetch_columns.py` only knew the Quebec DataStore). Done in phase 5, section 14.

## 14. Phase 5: DataStore columns on every CKAN portal (2026-10-22)

**Result** (one `datastore_search?limit=0` call per dataset that has a DataStore table):

| Portal | Tables called | Column lists | Errors | Datasets with a column list (before → after) |
|---|---|---|---|---|
| ON | 436 | 436 | 0 | 0% → 38% (436) |
| BC | 507 | 507 | 0 | 42% → 62% (1,034 → 1,522; the catalogue's own column list wins on the 19 that have both) |
| NT | 11 | 11 | 0 | 0% → 3% (11) |
| CA | 1,134 | 1,126 | 7 not found, 1 server error | 0% → 8% (1,126) |
| AB | 306 | 0 | 306 server errors | 0% |

`columns.csv` grows from 60,227 to 94,422 rows. Every other portal's rows in all three CSVs are unchanged.

**How the fetcher works now:**
- `fetch_columns.py <code> <packages> <out>` reads the API from `portals.py`. The main table is the newest DataStore resource marked as data (QC `donnees`, BC `data`, ON type `data`, CA `dataset`), else any DataStore resource. It picks the same table as before for all 1,160 Quebec datasets.
- The timeout is 20 s, and a call that times out is tried once more straight away. An HTTP error is the server's answer and is kept. A rerun fetches again only the datasets whose last line is a network error (the build reads the last line per dataset), and `run_all.sh` makes that second pass for every portal.
- **Federal speed.** open.canada.ca takes 2–10 s to answer for a table it hasn't touched yet, and well under a second after that, whether or not the row count is asked for (timed on 8 tables, alternating the order). So skipping the count (`include_total=false`) wouldn't help. One call at a time ran at 7–8.5 s per table, and the 60 s timeouts took 27% of the time. With `column_workers: 3` in `portals.py` (3 calls at once, each followed by the 1.2 s pause), it ran at about 1.2 s per table. 83 tables timed out twice in the first pass; 73 came back on the second and the last 10 on the third.

**Scoring:**
- **Column descriptions.** ON is the only new portal whose DataStore columns carry descriptions (`info.notes`, often in both languages): 133 datasets. 92 of them gain 8 documentation points ("No column descriptions found" goes away); the others already had a data dictionary file. A label or note that only repeats the column name doesn't count (2 ON tables, e.g. "Adoption Practitioners"; no Quebec table does this). ON grades move from 80/124/373/560 to 107/106/365/559 (A/B/C/D); its median stays 55.
- BC, NT and federal DataStore columns have names and types only, so their scores don't move.
- The 7 federal tables that answer "not found" get the existing "API table missing" warning.

**Findings:**
- **AB:** `datastore_search` and `datastore_info` both answer HTTP 500 for every one of the 306 tables (sampled first, then all 306). Those datasets still get 10 API points, because the catalogue marks their files as DataStore tables; the build only flags a missing table on a 404. Whether a portal-wide 500 should cost the API points is left open.
- **CA:** 1,134 of the 13,845 records have a DataStore table, and the tables hold 23.9 million rows in all. None of the columns has a description.
- **ON:** the 436 tables hold 9.9 million rows. 8 of the 133 described tables describe only some of their columns.

## 15. Nightly updates on a Coolify workstation (2026-10-22)

**Why not commit each night.** The repository was already about 80 MB after nine commits, and every run rewrites all of `raw/` (34 MB; gzip stores the time, so even an unchanged catalogue gives a new file) plus `data/` (91 MB) and `docs/` (80 MB). That's about 1 GB of history a month. So the nightly run keeps its snapshots and publishes its site on the machine that runs it, and the repository keeps the code and a seed snapshot.

**Where.** A workstation running Coolify, not GitHub Actions and Pages: no dependency on GitHub's schedule (which turns itself off after 60 days without commits), no US cloud runners for portals to block, and the files stay on a volume between runs.

**How** (`docker-compose.yml`, `Dockerfile`, `deploy/`):
- `updater` runs `run_all.sh` at 07:17 UTC (about 3 a.m. eastern), and once at start when the last run is more than a day old, so a night the machine was off is made up when it comes back. `/data/last-run` marks the attempt, not success, so a failing run waits for the next night. On first start it copies `raw/` and `docs/` from the image to the volume.
- `web` is Caddy serving `/srv/index/site` read-only, with gzip/zstd (index.json: 19 MB, 4.0 MB on the wire). Coolify's proxy adds the domain and HTTPS. The volume isn't mounted at `/data` there because the Caddy image keeps its own state in `/data`.
- `NOTIFY_URL` (optional) gets a plain-text POST when a run fails, for example an ntfy topic.

**Changes to the pipeline:**
- **Column lists only for changed tables.** Each column record stores its resource's last change (newest of `last_modified` and `metadata_modified`). A table is fetched again only when that date or the main resource changes, or the last try was a network error. On Sundays (or `FULL=1`) `run_all.sh` starts the file afresh, which also catches row counts and column notes that change without a new upload. Records from before this change have no date, so the first run after deploying fetches every table.
- **Count check.** `fetch_catalogue.py` keeps the last snapshot when a portal returns more than 10% fewer datasets than last time. A real drop is accepted by deleting that portal's snapshot.
- **No half-written files.** Catalogue snapshots are written next to the old one and swapped in (`os.replace`); the site is built in `<site>.new` and swapped with two renames.
- **Stale portals fail the run.** A portal whose snapshot is 3+ days old makes `run_all.sh` exit 1 (one bad night only warns).
- **History.** `build_index.py` writes `data/portals.csv` (per portal: datasets, grades, median score, column lists, freshness counts) and `run_all.sh` adds it to `raw/history.csv`, replacing that day's rows on a second run. The site serves the CSVs and the history under `/data/`.
- **User-Agent** names the project and links the repository (`portals.USER_AGENT`): `canada-open-data-index/1.0 (+https://github.com/PytechNo/canada-open-data-index)`. data.ontario.ca answers 429 to the same string without `/1.0` (and to the bare repo URL in brackets), every time; the `name/version` form passes there and on every other endpoint the run calls (checked 2026-10-22).
- The Québec sitemap crawl is no longer part of the run.

**Checked:** the column fetch skips unchanged tables and fetches a changed one again (NT, 11 tables); the count check refuses a 341-dataset catalogue against a 1,000-dataset snapshot and leaves the old file; both images build; the updater seeds an empty volume, skips the start-up run when `/data/last-run` is recent and sleeps until 07:17 UTC; web serves the page and gzipped JSON; a column fetch works inside the container.
