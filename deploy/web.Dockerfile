# The web server: serves the site the updater keeps on the shared volume, compressed (index.json is 19 MB, 3.6 MB gzipped).
FROM caddy:2.8.4-alpine
COPY deploy/Caddyfile /etc/caddy/Caddyfile
