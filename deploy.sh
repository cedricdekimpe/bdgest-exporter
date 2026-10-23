#!/bin/bash
set -euo pipefail
cd "$(dirname "$0")"
set -a; . "$HOME/.config/bd-lists.env"; set +a
sshpass -f .sftpass scp -r ./public/*.html ./public/up my_webapp__2@cedric.dkmp.be:/www
[[ -z "${BD_KUMA_PUSH_URL:-}" ]] || curl -fsS -m 20 -G "$BD_KUMA_PUSH_URL" --data-urlencode "status=up" --data-urlencode "msg=publie $(cat public/up)" -o /dev/null
