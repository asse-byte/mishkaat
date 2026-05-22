#!/usr/bin/env bash
# =============================================================================
# Mishkaat — restore from encrypted backup
# Usage:  ./restore.sh /var/backups/mishkaat/mishkaat-YYYYMMDDTHHMMSSZ.archive.gpg
# Requires the GPG private key for $GPG_RECIPIENT to be present in the keyring.
# =============================================================================
set -euo pipefail

: "${MONGO_URI:?MONGO_URI must be set}"

BACKUP_FILE="${1:?usage: restore.sh <backup.archive.gpg>}"

if [ ! -f "${BACKUP_FILE}" ]; then
    echo "Backup file not found: ${BACKUP_FILE}" >&2
    exit 1
fi

echo "[$(date -u)] decrypting + restoring ${BACKUP_FILE}"
echo "WARNING: this OVERWRITES the target database."
read -r -p "Type the word RESTORE to continue: " confirm
[ "${confirm}" = "RESTORE" ] || { echo "aborted"; exit 1; }

gpg --batch --quiet --decrypt "${BACKUP_FILE}" \
  | mongorestore --uri="${MONGO_URI}" --archive --gzip --drop

echo "[$(date -u)] restore complete"
