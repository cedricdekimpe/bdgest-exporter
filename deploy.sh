#!/bin/bash
# Publishes ./public over SFTP. The target (BD_SFTP_TARGET=user@host:/dir) and BD_KUMA_PUSH_URL
# live in ~/.config/bd-lists.env, the SFTP password in .sftpass.
set -euo pipefail
cd "$(dirname "$0")"
set -a; . "$HOME/.config/bd-lists.env"; set +a

# /up goes last: it is only published once everything else is online
files=()
for file in public/*; do
  [[ "$file" == public/up ]] || files+=("$file")
done
sshpass -f .sftpass scp "${files[@]}" "$BD_SFTP_TARGET"
sshpass -f .sftpass scp public/up "$BD_SFTP_TARGET"
[[ -z "${BD_KUMA_PUSH_URL:-}" ]] || curl -fsS -m 20 -G "$BD_KUMA_PUSH_URL" --data-urlencode "status=up" --data-urlencode "msg=publie $(cat public/up)" -o /dev/null
