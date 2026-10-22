"""Crawl the donneesquebec.ca WordPress sitemaps and list every URL they contain.

usage: crawl_sitemaps.py <out_csv>
"""
import csv
import re
import sys
import time
import urllib.request
from collections import Counter

INDEX = "https://www.donneesquebec.ca/wp-sitemap.xml"
out_path = sys.argv[1]


def get(url):
    req = urllib.request.Request(url, headers={"User-Agent": "dataset-index-builder (personal research)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read().decode("utf-8")


children = re.findall(r"<sitemap><loc>([^<]+)</loc>", get(INDEX))
rows = []
for sm in children:
    time.sleep(2)
    for block in re.findall(r"<url>(.*?)</url>", get(sm), flags=re.S):
        loc = re.search(r"<loc>([^<]+)</loc>", block).group(1)
        lastmod = re.search(r"<lastmod>([^<]+)</lastmod>", block)
        rows.append({"sitemap": sm.rsplit("/", 1)[-1], "url": loc, "lastmod": lastmod.group(1) if lastmod else ""})

with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=["sitemap", "url", "lastmod"])
    w.writeheader()
    w.writerows(rows)

for sm, c in Counter(r["sitemap"] for r in rows).items():
    print(f"{sm}: {c} URLs")
print(f"total: {len(rows)} URLs -> {out_path}")
