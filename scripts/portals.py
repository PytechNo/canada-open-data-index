"""The open data portals in the index, by province code. Raw downloads live in raw/<code>/.

page: dataset page URL template ({name} or {id}); fq: CKAN filter that keeps only open datasets.
Each platform has a reader in normalize.py (PLATFORMS).
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
    # Socrata: api is the Discovery API search, already limited to the portal's own datasets
    "NS": {"name": "Nova Scotia", "platform": "socrata",
           "api": "https://data.novascotia.ca/api/catalog/v1?domains=data.novascotia.ca"
                  "&search_context=data.novascotia.ca&only=dataset",
           "page": "https://data.novascotia.ca/d/{id}"},
    "NB": {"name": "New Brunswick", "platform": "socrata",
           "api": "https://gnb.socrata.com/api/catalog/v1?domains=gnb.socrata.com&search_context=gnb.socrata.com&only=dataset",
           "page": "https://gnb.socrata.com/d/{id}"},
    # ArcGIS Hub: api is the site's search API for its "dataset" collection
    "MB": {"name": "Manitoba", "platform": "hub",
           "api": "https://geoportal.gov.mb.ca/api/search/v1/collections/dataset/items",
           "page": "https://geoportal.gov.mb.ca/datasets/{id}"},
    "SK": {"name": "Saskatchewan", "platform": "hub",
           "api": "https://geohub.saskatchewan.ca/api/search/v1/collections/dataset/items",
           "page": "https://geohub.saskatchewan.ca/datasets/{id}"},
    "PE": {"name": "Prince Edward Island", "platform": "hub",
           "api": "https://data.princeedwardisland.ca/api/search/v1/collections/dataset/items",
           "page": "https://data.princeedwardisland.ca/datasets/{id}"},
}
