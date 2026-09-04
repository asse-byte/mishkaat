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

echo "[$(date -u)] preparing to restore ${BACKUP_FILE}"
echo
echo "WARNING: this OVERWRITES the target database (mongorestore --drop)."
echo
# [إصلاح 2026-09-03] تحذير مفتاح تعمية البيانات الشخصية.
# حقول (تاريخ الميلاد، عنوان ولي الأمر، اسم ولي الأمر) مُعمّاة بـ PII_ENCRYPTION_KEY.
# استرجاع نسخة على خادم يحمل مفتاحاً مختلفاً يُعيد البيانات "سليمة" ظاهرياً وغير قابلة للقراءة
# إلى الأبد — و decrypt_pii يتسامح مع الفشل فيُعيد النص المعمّى كما هو بلا خطأ ظاهر.
echo "IMPORTANT: the PII_ENCRYPTION_KEY on THIS host must be the same key that was"
echo "           in use when this backup was taken. A different key silently yields"
echo "           unreadable dates of birth / guardian names and addresses."
echo
read -r -p "Type the word RESTORE to continue: " confirm
[ "${confirm}" = "RESTORE" ] || { echo "aborted"; exit 1; }

# [إصلاح 2026-09-03] شبكة أمان: نسخة من الحالة الراهنة قبل إتلافها.
# --drop يمحو قاعدة البيانات الحالية أولاً؛ فإذا تبيّن أن النسخة تالفة في منتصف الاسترجاع
# لم يكن هناك ما يُرجَع إليه. هذه النسخة غير معمّاة عمداً وتُحذف يدوياً بعد التأكد.
SAFETY_DIR="${SAFETY_DIR:-/var/backups/mishkaat/pre-restore}"
SAFETY="${SAFETY_DIR}/pre-restore-$(date -u +%Y%m%dT%H%M%SZ).archive.gz"
mkdir -p "${SAFETY_DIR}"
chmod 700 "${SAFETY_DIR}"
echo "[$(date -u)] snapshotting current database → ${SAFETY}"
if mongodump --uri="${MONGO_URI}" --archive="${SAFETY}" --gzip; then
    chmod 600 "${SAFETY}"
    echo "[$(date -u)] safety snapshot OK ($(stat -c%s "${SAFETY}") bytes)"
else
    echo "[$(date -u)] could not snapshot the current database (empty or unreachable)." >&2
    read -r -p "Continue WITHOUT a safety snapshot? Type YES: " force
    [ "${force}" = "YES" ] || { echo "aborted"; exit 1; }
fi

echo "[$(date -u)] decrypting + restoring ${BACKUP_FILE}"
gpg --batch --quiet --decrypt "${BACKUP_FILE}" \
  | mongorestore --uri="${MONGO_URI}" --archive --gzip --drop

echo "[$(date -u)] restore complete"
echo "[$(date -u)] pre-restore snapshot kept at ${SAFETY} — delete it once you have verified the data."
