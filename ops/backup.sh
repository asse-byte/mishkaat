#!/usr/bin/env bash
# =============================================================================
# Mishkaat — encrypted MongoDB backup
# - Dumps the production DB
# - Encrypts to a single file with GPG (public key, AES256)
# - Stores in $BACKUP_DIR with timestamp
# - Rotates: keeps last $RETENTION_DAYS days
# - Optional: ships to off-host storage via rclone (if RCLONE_REMOTE is set)
#
# Required env (typically loaded from /etc/mishkaat/backup.env):
#   MONGO_URI           mongodb://user:pass@host:27017/quran_center?authSource=quran_center
#   BACKUP_DIR          local backup directory (e.g. /var/backups/mishkaat)
#   GPG_RECIPIENT       fingerprint or email of the GPG key to encrypt FOR
#   RETENTION_DAYS      default 30
#   RCLONE_REMOTE       optional, e.g. "off-site:mishkaat-backups"
#
# Safety:
#   - No plaintext dump ever touches the disk (mongodump → gpg via pipe).
#   - Script fails closed on any error (set -euo pipefail).
#   - Backup file is mode 600 and owned by root only.
# =============================================================================
set -euo pipefail

: "${MONGO_URI:?MONGO_URI must be set}"
: "${BACKUP_DIR:?BACKUP_DIR must be set}"
: "${GPG_RECIPIENT:?GPG_RECIPIENT must be set}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"

STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT="${BACKUP_DIR}/mishkaat-${STAMP}.archive.gpg"

mkdir -p "${BACKUP_DIR}"
chmod 700 "${BACKUP_DIR}"

echo "[$(date -u)] starting backup → ${OUT}"

# Pipe mongodump → gpg so plaintext never lives on disk
mongodump \
    --uri="${MONGO_URI}" \
    --archive \
    --gzip \
  | gpg --batch --yes --trust-model always --encrypt \
        --cipher-algo AES256 \
        --recipient "${GPG_RECIPIENT}" \
        --output "${OUT}"

chmod 600 "${OUT}"

# Verify size
SIZE=$(stat -c%s "${OUT}")
if [ "${SIZE}" -lt 1024 ]; then
    echo "[$(date -u)] FATAL: backup is suspiciously small (${SIZE} bytes)" >&2
    rm -f "${OUT}"
    exit 1
fi
echo "[$(date -u)] OK ${SIZE} bytes"

# Rotation — keep last RETENTION_DAYS days
find "${BACKUP_DIR}" -maxdepth 1 -type f -name 'mishkaat-*.archive.gpg' \
     -mtime "+${RETENTION_DAYS}" -delete

# Optional: ship off-host (rclone must be configured separately)
if [ -n "${RCLONE_REMOTE:-}" ]; then
    echo "[$(date -u)] uploading to ${RCLONE_REMOTE}"
    rclone copy "${OUT}" "${RCLONE_REMOTE}/" --quiet
    echo "[$(date -u)] off-host copy complete"
fi

echo "[$(date -u)] done"
