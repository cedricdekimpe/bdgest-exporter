#!/bin/bash
# Exports the BDGest collections listed in collections.conf and builds the pages. deploy.sh publishes them.
# Credentials (BDGEST_LOGIN, BDGEST_PASSWORD) and BD_KUMA_PUSH_URL live in ~/.config/bd-lists.env
# Set FORCE=1 to run again within the hour.
set -uo pipefail
cd "$(dirname "$0")"
set -a; . "$HOME/.config/bd-lists.env"; set +a

MIN_INTERVAL=3600  # seconds between two exports: Cloudflare rate limits the IP when BDGest is hit too often

# Tells Uptime Kuma (push monitor) how the run went
push() {
  [[ -n "${BD_KUMA_PUSH_URL:-}" ]] || return 0
  curl -fsS -m 20 -G "$BD_KUMA_PUSH_URL" --data-urlencode "status=$1" --data-urlencode "msg=$2" -o /dev/null
}

# Keep cron.log small
if [[ -f cron.log && $(stat -c %s cron.log) -gt 1000000 ]]; then
  tail -c 200000 cron.log > cron.log.1
  : > cron.log
fi

# One run at a time, and not too often
exec 9> tmp/.run.lock
if ! flock -n 9; then
  echo "[skip] another run is in progress" >&2
  exit 75
fi
last_attempt=tmp/.last-attempt
if [[ -z "${FORCE:-}" && -f "$last_attempt" ]] && (( $(date +%s) - $(stat -c %Y "$last_attempt") < MIN_INTERVAL )); then
  echo "[skip] last run was less than ${MIN_INTERVAL}s ago (FORCE=1 to override)" >&2
  exit 75
fi
touch "$last_attempt"

exports=$(awk -F: '!/^#/ && NF >= 3 { printf "%s.csv:%s ", $1, $2 }' collections.conf)
# shellcheck disable=SC2086 # one argument per collection
if ! .venv/bin/python get_collection.py $exports; then
  push down "echec de l'export BDGest"
  exit 1
fi

if ! build_output=$(.venv/bin/python build_pages.py 2>&1); then
  echo "$build_output" >&2
  push down "echec de la generation : ${build_output##*$'\n'}"
  exit 1
fi
echo "$build_output"
