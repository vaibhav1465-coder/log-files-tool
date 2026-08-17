#!/bin/sh
set -eu
while true; do
  stamp="$(date -u +%Y%m%dT%H%M%SZ)"
  target="/backups/express-${stamp}.dump.tmp"
  pg_dump --format=custom --compress=6 --file="$target"
  mv "$target" "${target%.tmp}"
  find /backups -type f -name 'express-*.dump' -mtime "+${BACKUP_RETENTION_DAYS:-14}" -delete
  sleep 86400
done
