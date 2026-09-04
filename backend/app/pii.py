"""تعمية الحقول الشخصية."""

from app.config import _fernet

from cryptography.fernet import InvalidToken


def encrypt_pii(value):
    """تشفير حقل PII (مثل تاريخ الميلاد وعنوان ولي الأمر)"""
    if value is None or value == "":
        return value
    try:
        return _fernet.encrypt(str(value).encode()).decode()
    except Exception:
        return value

def decrypt_pii(value):
    """فك تشفير PII مع تسامح مع البيانات القديمة (non-encrypted)"""
    if value is None or value == "":
        return value
    if not isinstance(value, str):
        return value
    try:
        return _fernet.decrypt(value.encode()).decode()
    except (InvalidToken, ValueError, Exception):
        return value  # legacy plaintext or non-token; pass through

# [AUDIT-2026-05-22 fix: PII field whitelist — encrypted at rest.
# Phones are NOT encrypted because check_student_access needs them for ownership matching.
# parent_name added because it identifies the minor's guardian.]
_STUDENT_PII_FIELDS = ("date_of_birth", "guardian_address", "parent_name")

def encrypt_student_doc(d: dict) -> dict:
    """تشفير حقول PII قبل الكتابة في قاعدة البيانات"""
    if not d:
        return d
    out = dict(d)
    for f in _STUDENT_PII_FIELDS:
        if out.get(f):
            out[f] = encrypt_pii(out[f])
    return out

def decrypt_student_doc(d: dict) -> dict:
    """فك تشفير حقول PII قبل إرجاع البيانات للمستخدم"""
    if not d:
        return d
    out = dict(d)
    for f in _STUDENT_PII_FIELDS:
        if out.get(f):
            out[f] = decrypt_pii(out[f])
    return out
