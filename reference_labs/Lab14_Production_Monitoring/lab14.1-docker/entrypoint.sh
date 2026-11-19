#!/usr/bin/env bash
set -euo pipefail

mode="${1:-dashboard}"
if [[ $# -gt 0 ]]; then
  shift
fi

case "$mode" in
  dashboard)
    exec python3 /app/app.py dashboard "$@"
    ;;
  benchmark)
    exec python3 /app/app.py benchmark "$@"
    ;;
  smoke-test)
    exec python3 /app/app.py smoke-test "$@"
    ;;
  backup)
    exec bash /scripts/backup.sh "$@"
    ;;
  scheduler)
    exec bash /scripts/backup-scheduler.sh "$@"
    ;;
  verify-backup)
    exec bash /scripts/verify-backup.sh "$@"
    ;;
  webhook)
    exec python3 /app/webhook_sink.py "$@"
    ;;
  test)
    exec python3 -m unittest -v test_app "$@"
    ;;
  python|python3)
    if [[ "${1:-}" == "app.py" ]]; then
      shift
      exec python3 /app/app.py "$@"
    fi
    exec python3 "$@"
    ;;
  mongosh|mongodump|mongorestore)
    exec "$mode" "$@"
    ;;
  *)
    exec "$mode" "$@"
    ;;
esac
