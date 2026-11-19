#!/usr/bin/env bash
set -euo pipefail

archive="${1:?Usage: verify-backup.sh <archive>}"
database="${APP_DATABASE:-lab14}"
verification_database="${database}_restore_check"

if [[ ! -s "$archive" ]]; then
  echo "Backup archive is missing or empty: $archive" >&2
  exit 1
fi

mongosh \
  --host mongo1:27017 \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --quiet "$database" \
  --eval "db.getSiblingDB('$verification_database').dropDatabase()"

mongorestore \
  --host mongo1:27017 \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --archive="$archive" \
  --gzip \
  --nsFrom="${database}.*" \
  --nsTo="${verification_database}.*"

mongosh \
  --host mongo1:27017 \
  --username "$MONGO_INITDB_ROOT_USERNAME" \
  --password "$MONGO_INITDB_ROOT_PASSWORD" \
  --authenticationDatabase admin \
  --quiet "$database" \
  --eval "
    const source = db.getSiblingDB('$database');
    const restored = db.getSiblingDB('$verification_database');
    const names = source.getCollectionNames().filter((name) => !name.startsWith('system.'));
    if (names.length === 0) {
      throw new Error('Source database has no user collections to verify');
    }
    for (const name of names) {
      const sourceCount = source.getCollection(name).countDocuments({});
      const restoredCount = restored.getCollection(name).countDocuments({});
      if (sourceCount !== restoredCount) {
        throw new Error(name + ': source=' + sourceCount + ' restored=' + restoredCount);
      }
      print('RESTORE_VERIFIED ' + name + ' documents=' + sourceCount);
    }
    restored.dropDatabase();
  "

echo "RESTORE_VERIFICATION_OK=$archive"
