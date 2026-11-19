#!/usr/bin/env bash
set -euo pipefail

backup_dir="${BACKUP_DIR:-/backups}"
database="${APP_DATABASE:-lab14}"
retention_days="${BACKUP_RETENTION_DAYS:-7}"
timestamp="$(date -u +%Y%m%dT%H%M%SZ)"
archive="${backup_dir}/${database}_${timestamp}.archive.gz"

mkdir -p "$backup_dir"
mongodump \
  --host mongo1:27017 \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --db "$database" \
  --archive="$archive" \
  --gzip

test -s "$archive"
echo "BACKUP_CREATED=$archive"
bash /scripts/verify-backup.sh "$archive"
find "$backup_dir" -type f -name "${database}_*.archive.gz" \
  -mmin "+$((retention_days * 1440))" -print -delete
