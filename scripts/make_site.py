"""Turn site/page.html into a standalone docs/index.html (GitHub Pages ready) next to its index.json and detail/.

The page fragment has no <!doctype>/<head>/<body> of its own, so it can also be published as a
Claude artifact; this script adds that skeleton for regular hosting.

usage: make_site.py <page_html> <data_dir with index.json and detail/> <docs_dir>
"""
import os
import shutil
import sys

page_path, data_dir, docs_dir = sys.argv[1], sys.argv[2], sys.argv[3]
os.makedirs(docs_dir, exist_ok=True)
fragment = open(page_path, encoding="utf-8").read()
skeleton = (
    "<!doctype html>\n<html lang=\"en\">\n<head>\n<meta charset=\"utf-8\">\n"
    "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">\n"
    "<style>:root{color-scheme:light;padding-top:env(safe-area-inset-top,0px);"
    "padding-bottom:env(safe-area-inset-bottom,0px)}body{margin:0}img{max-width:100%}"
    "[hidden]{display:none!important}</style>\n"
)
head_end = fragment.index("</style>") + len("</style>")
html = skeleton + fragment[:head_end] + "\n</head>\n<body>\n" + fragment[head_end:] + "\n</body>\n</html>\n"
with open(os.path.join(docs_dir, "index.html"), "w", encoding="utf-8") as f:
    f.write(html)
shutil.copyfile(os.path.join(data_dir, "index.json"), os.path.join(docs_dir, "index.json"))
# replace detail/ whole, so a province that left the index doesn't keep a stale file
shutil.rmtree(os.path.join(docs_dir, "detail"), ignore_errors=True)
shutil.copytree(os.path.join(data_dir, "detail"), os.path.join(docs_dir, "detail"))
if os.path.exists(os.path.join(docs_dir, "data.json")):  # the single file the page loaded before the split
    os.remove(os.path.join(docs_dir, "data.json"))
open(os.path.join(docs_dir, ".nojekyll"), "w").close()
print("wrote", os.path.join(docs_dir, "index.html"))
