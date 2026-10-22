"""The open data portals in the index, by province code. Raw downloads live in raw/<code>/.

page: dataset page URL template ({name} or {id}); fq: CKAN filter that keeps only open datasets.
"""
PORTALS = {
    "QC": {"name": "Québec", "platform": "ckan", "api": "https://www.donneesquebec.ca/recherche/api/3/action",
           "page": "https://www.donneesquebec.ca/recherche/dataset/{name}"},
    "ON": {"name": "Ontario", "platform": "ckan", "api": "https://data.ontario.ca/api/3/action",
           "page": "https://data.ontario.ca/dataset/{name}", "fq": "access_level:open"},
    "BC": {"name": "British Columbia", "platform": "ckan", "api": "https://catalogue.data.gov.bc.ca/api/3/action",
           "page": "https://catalogue.data.gov.bc.ca/dataset/{name}", "fq": "download_audience:Public"},
    "AB": {"name": "Alberta", "platform": "ckan", "api": "https://open.alberta.ca/api/3/action",
           "page": "https://open.alberta.ca/opendata/{name}", "fq": "type:opendata"},
    "YT": {"name": "Yukon", "platform": "ckan", "api": "https://open.yukon.ca/api/3/action",
           "page": "https://open.yukon.ca/data/{name}", "fq": "type:data"},
    "NT": {"name": "Northwest Territories", "platform": "ckan", "api": "https://opendata.gov.nt.ca/api/3/action",
           "page": "https://opendata.gov.nt.ca/dataset/{name}"},
    # opendata.gov.nl.ca returned HTTP 500 on 2026-10-22; these are the NL records copied to the federal portal
    "NL": {"name": "Newfoundland and Labrador", "platform": "ckan", "api": "https://open.canada.ca/data/api/3/action",
           "page": "https://open.canada.ca/data/en/dataset/{id}", "fq": "organization:nl-tnl"},
}
