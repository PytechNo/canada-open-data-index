#!/usr/bin/env bash
# The updater container: seed an empty volume from the snapshot in the image, then refresh the index every night
# at 07:17 UTC (about 3 a.m. in eastern Canada), and once at start when the last run is more than a day old
# (first start, or the machine was off or redeployed mid-run).
# NOTIFY_URL, if set, gets a plain-text POST when a run fails (an ntfy.sh topic URL works).
set -uo pipefail
cd /app
export RAW_DIR=/data/raw SITE_DIR=/data/site
[ -d "$RAW_DIR" ] || cp -r raw "$RAW_DIR"
[ -d "$SITE_DIR" ] || cp -r docs "$SITE_DIR"

run() {
  echo "$(date -u '+%F %T') run started"
  if ! ./run_all.sh; then
    msg="Canada Open Data Index: the $(date -u +%F) run failed, see the updater's logs"
    echo "$msg" >&2
    [ -z "${NOTIFY_URL:-}" ] || curl -fsS -m 30 -d "$msg" "$NOTIFY_URL" >/dev/null || echo "could not send the alert" >&2
  fi
  # marks the attempt, not success, so a failing run waits for the next night instead of starting over at once
  touch /data/last-run
  echo "$(date -u '+%F %T') run finished"
}

[ -n "$(find /data/last-run -mmin -1440 2>/dev/null)" ] || run
while true; do
  now=$(date +%s)
  next=$(date -d "07:17" +%s)
  [ "$next" -gt "$now" ] || next=$(date -d "tomorrow 07:17" +%s)
  sleep $((next - now))
  run
done
