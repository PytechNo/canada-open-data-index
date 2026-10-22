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
  fetch_columns.py    # CKAN DataStore (QC, ON, NT) and Hub layer JSON; skipped where the catalogue already has columns
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
| Catalogue call | `package_search?rows=500&start=N&fq=<filter>` (existing loop) | `/api/catalog/v1?domains=D&search_context=D&only=dataset&limit=100&offset=N` | `/api/search/v1/collections/dataset/items?limit=100&startindex=N` |
| Promised frequency | QC `update_frequency`; ON `update_frequency`; AB `updatefrequency`; YT, NT `update_frequency`; BC per-file `resource_update_cycle` (use the most frequent promise among data files) | NS `domain_metadata` "Detailed-Metadata_Frequency"; NB none | none |
| Last data change | newest file `last_modified` (existing rule); ON also has `data_last_updated` | `data_updated_at` (true data date) | layer `editingInfo.lastEditDate` from the FeatureServer call, else item `modified` (with a warning that it's a metadata date) |
| Columns | DataStore `datastore_search?limit=0` (QC, ON, NT); BC per-file `details` (column name, type, comment), no extra call | in catalogue: `columns_name`, `columns_datatype`, `columns_description` | one FeatureServer layer call per item gives `fields` |
| Methodology | QC `methodologie`; BC `lineage_statement` | none | none |
| Time coverage | QC `temporal`; AB `time_coverage_from/to`; YT `temporal_coverage_*`; NT `starting/ending_time_range`; ON file `data_range_start/end` | none | none |
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
| no field (NB, MB, SK, PE) | new code `notStated`: scored like "no fixed schedule", plus the warning "No update frequency promised" |

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
| 2 | CKAN provinces: ON, BC, AB, YT, NT (and NL if the portal is back); field maps; filters; frequency and licence tables | ~7,400 more datasets build; every frequency and licence value seen is mapped (the build stops and lists any that aren't) |
| 3 | Socrata fetcher and normaliser: NS, NB | 1,032 more; columns come from the catalogue |
| 4 | Hub fetcher and normaliser: MB, SK, PE, plus one FeatureServer call per item for fields and last edit date | 342 more |
| 5 | Columns: DataStore for ON and NT through the existing `fetch_columns.py` (it already resumes and waits 1.2 s per call) | column lists for every platform that has them |
| 6 | Split JSON, province filter, comparison table, README, `run_all.sh` loop | the site serves locally and on Pages |
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

- **Federal portal** (36,119 federal-only records with `jurisdiction:federal`). It's the biggest single source, and its ISO 8601 frequencies (`P1Y`, `P3M`, `P2W`) convert to days directly. Its size alone (about 160 MB of detail JSON) means it needs the split from section 5 first.
- **Municipal portals** (Montréal, Toronto, Calgary, Vancouver, Ottawa, …). Same three platforms, so mostly config once v1 exists.
- **Snapshot history**: keep each run's slim index, to chart freshness over time per province.
