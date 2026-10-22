# What the donneesquebec.ca sitemaps contain

Crawled on 2026-10-22 with `scripts/crawl_sitemaps.py`. The full URL list is in [`sitemap_urls.csv`](sitemap_urls.csv).

`https://www.donneesquebec.ca/wp-sitemap.xml` (also reached through `/sitemap.xml`) is a WordPress sitemap index with **5 child sitemaps and 240 URLs**. It only covers the WordPress part of the site.

| Sitemap | URLs | Content |
|---|---|---|
| `wp-sitemap-posts-post-1.xml` | 97 | News articles, 2016 to 2026 |
| `wp-sitemap-posts-page-1.xml` | 70 | Static pages: guides, policies, data standards |
| `wp-sitemap-posts-organisation-1.xml` | 35 | Publisher profile pages |
| `wp-sitemap-taxonomies-category-1.xml` | 30 | News categories, one per publisher (no dates) |
| `wp-sitemap-users-1.xml` | 8 | WordPress author pages |

## News articles (97)
Portal news (launches, yearly recaps, new partners, HackQC 2017 to 2024, the Canadian Open Data Summit) and dataset announcements. About 16 posts are Montréal dataset descriptions brought in as articles in 2021, and two look like leftover test posts (`/article-deux-4/`, `/lignes/`).

## Pages (70)
- 28 data standard pages under `/normalisation-des-donnees/` (27 standards plus an index)
- 8 publisher guide pages (`/diffusion/`) and 6 user guide pages (`/explorer/`, `/exploiter/`)
- 7 policy pages (publishing guidelines with 3 subpages, adopted standards, framework policy, reference data)
- 10 core pages, 4 contact pages, 4 legal and security pages
- 3 leftovers that probably should not be listed: `foire-aux-questions-old`, `403-2`, `captchaprotected`

## Organisations (35)
Gouvernement du Québec, Assemblée nationale, Communauté métropolitaine de Québec, a general "organismes" page, 19 cities and 12 MRCs.

## Categories (30)
They repeat the organisation list but stop around 2022. Near-duplicates (`organisme` / `organismes` / `organismes-fr`), a typo (`villes-de-trois-rivieres`) and a trailing dash (`ville-de-rouyn-noranda-`).

## Authors (8)
WordPress author archives, which expose the editors' login names.

## What is missing
**None of the datasets are in a sitemap.** The catalogue is a CKAN site under `/recherche/`, and robots.txt declares no sitemap for it. That is why this project reads the catalogue through its API instead.
