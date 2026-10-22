# Handoff: nightly updates (2026-10-22)

Where the Canada Open Data Index stands after phase 5 (column lists) and the move to nightly updates on a Coolify workstation. Details and reasoning are in [`CANADA-PLAN.md`](CANADA-PLAN.md), sections 14 and 15.

## Done

| Commit | What |
|---|---|
| `671a50a` | Phase 5: column lists from every CKAN DataStore. 5,592 datasets have one (was 3,531): Ontario 38%, BC 62%, federal 8%, Northwest Territories 3% |
| `deb3c39` | Corrected the full-run time: 2 to 3 hours |
| `1f070c2` | Nightly updates on a Coolify workstation |

### What runs each night

[`docker-compose.yml`](docker-compose.yml) runs two containers on one volume:

- **updater** ([`Dockerfile`](Dockerfile), [`deploy/updater.sh`](deploy/updater.sh)) runs [`run_all.sh`](run_all.sh) every night at 07:17 UTC (about 3 a.m. in eastern Canada). It also runs once at start when the last run was more than a day ago (first start, or the machine was off). On first start it fills the volume from the snapshot in the repository.
- **web** ([`deploy/web.Dockerfile`](deploy/web.Dockerfile), [`deploy/Caddyfile`](deploy/Caddyfile)) is Caddy serving the site from the volume, gzipped. Coolify's proxy adds the domain and HTTPS.

### What `run_all.sh` does now

- **Column lists only for tables that changed** since the last run. On Sundays, or with `FULL=1`, it fetches all of them again.
- **Count check:** if a portal returns more than 10% fewer datasets than last time, its last snapshot is kept. To accept a real drop, delete that portal's `packages.json.gz` on the volume.
- **No half-written files:** snapshots and the site are written next to the old ones and swapped in.
- **Retries:** a catalogue call that hits a server error (5xx) or hangs is tried twice more. Any other HTTP error is taken as the answer.
- **History:** each run adds one row per portal to `raw/history.csv` (datasets, grades, median score, column lists, freshness counts).
- **Downloads:** the CSVs and the history are published under `/data/` on the site.
- **Alerts:** a portal with no new snapshot for 3 days makes the run fail. If `NOTIFY_URL` is set, a failed run sends a message there.
- **User-Agent:** `canada-open-data-index/1.0 (+https://github.com/PytechNo/canada-open-data-index)`. data.ontario.ca answers 429 to the same string without `/1.0`, so keep the `name/version` form.

### Tested

- Unit checks: the column fetch skips unchanged tables and refetches a changed one; the count check refuses a shrunken catalogue and keeps the old file; the retry recovers from a 504, gives up after three, and fails at once on a 404.
- Docker: both images build. The updater fills an empty volume and sleeps until 07:17 UTC. Caddy serves the page and gzipped JSON (`index.json`: 19 MB, 4.0 MB on the wire). A column fetch works inside the container.
- One real end-to-end run with only changed tables fetched: **19 minutes**, exit 0. The federal catalogue failed during it (see below), so a normal night will be a few minutes longer.

## Expected run times

| Night | Time |
|---|---|
| Normal night | about 20–30 minutes, mostly the ~610 ArcGIS Hub calls |
| Sunday (full column refresh) | 2–3 hours (the federal DataStore alone takes 25–75 minutes). Estimated from timings, not measured |
| First run after deploying | 2–3 hours: the committed column records have no change dates, so every table is fetched |

## To deploy in Coolify

1. Add a resource from this Git repository with the **Docker Compose** build pack.
2. Give the **web** service a domain. It listens on port 80.
3. Optional: set `NOTIFY_URL` (for example an [ntfy](https://ntfy.sh) topic URL) to get a message when a run fails.
4. Each push redeploys. A redeploy in the middle of a run stops it. The next start makes up the missed night if the last run was more than a day ago.

## Open items

1. **The federal portal was down this evening.** open.canada.ca answered 504 after 60 s on every catalogue call from about 16:40 Eastern on 2026-10-22, including with the old User-Agent and with 0 rows. So it's the portal, not this project. On nights like that the run keeps the federal portal's last snapshot and warns. If it lasts 3 nights, the run fails and alerts. Check it again tomorrow. The note in commit `1f070c2` that lists this as open is out of date.
2. **The README has no live-site URL yet,** because the domain isn't known. Add it to the README once the web service has its domain.
3. **Back up the volume's `raw/history.csv`.** It's the only thing a fresh run can't rebuild.
4. **Alberta scoring:** Alberta's DataStore answers HTTP 500 for all 306 tables, yet those datasets still get 10 API points. Changing that is a scoring decision.
5. **Optional:** filling in change dates on the committed column records would make the first run on the workstation about 25 minutes instead of 2–3 hours. A one-off script for it is in the session scratchpad, not in the repository.
6. **Not committed:** `ideas/` and `reports/` (product-idea notes), and `backup/` (column-file backups, ignored by git).
7. **On the development PC:** Docker Desktop was started for the container tests and is still running.
