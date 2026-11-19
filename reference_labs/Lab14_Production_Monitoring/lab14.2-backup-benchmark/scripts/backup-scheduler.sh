#!/usr/bin/env bash
set -euo pipefail

interval="${BACKUP_INTERVAL_SECONDS:-3600}"
echo "Backup scheduler started; interval=${interval}s"
while true; do
  started_at="$(date +%s)"
  bash /scripts/backup.sh
  elapsed="$(( $(date +%s) - started_at ))"
  delay="$((interval - elapsed))"
  if (( delay > 0 )); then
    sleep "$delay"
  else
    echo "Backup run exceeded ${interval}s; starting the next run immediately"
  fi
done
