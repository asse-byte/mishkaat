"""إعدادات التشغيل والأسرار والثوابت."""

import logging
import os

from cryptography.fernet import Fernet
from dotenv import load_dotenv

# يجب أن يسبق أي os.getenv أدناه، وإلا قُرئت الإعدادات قبل تحميل ملف .env
load_dotenv()

logger = logging.getLogger("uvicorn.error")

# Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")

DB_NAME = os.getenv("DB_NAME", "quran_center")

# [AUDIT-2026-05-22 fix: production fail-fast on default SECRET_KEY]
APP_ENV = os.getenv("APP_ENV", "development").lower()

IS_PRODUCTION = APP_ENV in ("production", "prod")

_DEFAULT_SECRET = "9f4a2e8b1d6c3f7a0e5b2d9c4f1a8e3b6d0c7f2a5e8b1d4c9f3a6e0b7d2c5f8a1e"

SECRET_KEY = os.getenv("SECRET_KEY", _DEFAULT_SECRET)
if IS_PRODUCTION and SECRET_KEY == _DEFAULT_SECRET:
    raise RuntimeError(
        "SECURITY: SECRET_KEY must be set in production. "
        "Generate via: python -c \"import secrets; print(secrets.token_hex(64))\""
    )

ALGORITHM = "HS256"

# [AUDIT-2026-05-22 fix: short-lived access token + long-lived refresh token]
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))   # 1 hour

REFRESH_TOKEN_EXPIRE_DAYS = int(os.getenv("REFRESH_TOKEN_EXPIRE_DAYS", "7"))        # 7 days

MAX_LOGIN_ATTEMPTS = 5

LOCKOUT_MINUTES = 15

# [AUDIT-2026-09-03 fix: the rate limiter keyed on request.client.host, which behind nginx/Docker is
#  ALWAYS the proxy's IP — five bad passwords from anyone locked out every user of the deployment,
#  and a real attacker was never isolated. Honour X-Forwarded-For only when we are actually behind a
#  proxy we control (TRUST_PROXY=true), never by default: trusting it blindly lets a client forge it.]
TRUST_PROXY = os.getenv("TRUST_PROXY", "false").lower() in ("true", "1", "yes")

# [AUDIT-2026-09-03 fix: password-reset hardening — codes are hashed at rest and brute-force capped]
RESET_CODE_TTL_MINUTES = int(os.getenv("RESET_CODE_TTL_MINUTES", "10"))

RESET_MAX_VERIFY_ATTEMPTS = 5

RESET_MAX_REQUESTS_PER_HOUR = 5

# Per-account lockout, on top of the per-IP one (an attacker rotating IPs used to be unlimited)
MAX_ACCOUNT_ATTEMPTS = int(os.getenv("MAX_ACCOUNT_ATTEMPTS", "10"))

ACCOUNT_LOCKOUT_MINUTES = int(os.getenv("ACCOUNT_LOCKOUT_MINUTES", "15"))

# سجلات التدقيق التي لا تُحذف أبداً (المال والصلاحيات)؛ ما عداها يُنظَّف بعد سنتين
AUDIT_PERMANENT_ACTIONS = {
    "collect_fee", "pay_salary", "create_expense", "delete_expense",
    "PASSWORD_CHANGED", "PASSWORD_RESET_VIA_CODE", "ADMIN_RESET_PASSWORD",
    "SUPER_REGISTER_CENTER", "SUPER_CENTER_STATUS_CHANGE",
    "CENTER_APPROVED", "CENTER_REJECTED",
}

# [AUDIT-2026-05-22 fix: bcrypt cost raised to OWASP-recommended 12; tunable via env]
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))

# pwd_context removed in favor of direct native bcrypt calls

# [AUDIT-2026-05-22 fix: field-level PII encryption key (Fernet AES-128-CBC + HMAC)]
_PII_KEY_ENV = os.getenv("PII_ENCRYPTION_KEY")
if not _PII_KEY_ENV:
    if IS_PRODUCTION:
        raise RuntimeError(
            "SECURITY: PII_ENCRYPTION_KEY must be set in production. "
            "Generate via: python -c \"from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())\""
        )
    # Development: generate an ephemeral key; warn that data won't survive a restart
    _PII_KEY_ENV = Fernet.generate_key().decode()
    logger.warning("PII_ENCRYPTION_KEY not set — using ephemeral dev key; encrypted fields will not survive a restart")

try:
    _fernet = Fernet(_PII_KEY_ENV.encode() if isinstance(_PII_KEY_ENV, str) else _PII_KEY_ENV)
except Exception as exc:
    raise RuntimeError(f"Invalid PII_ENCRYPTION_KEY format: {exc}")

# قائمة النطاقات المسموح بها (CORS)
# [AUDIT-2026-09-03 fix: ".split(',')" left the space in "a, b" attached to the origin, so a perfectly
#  correct ALLOWED_ORIGINS line silently blocked the real front-end. Strip and drop empties.]
ALLOWED_ORIGINS = [
    o.strip() for o in os.getenv(
        "ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
    ).split(",") if o.strip()
]
if IS_PRODUCTION and "*" in ALLOWED_ORIGINS:
    raise RuntimeError("SECURITY: ALLOWED_ORIGINS must not be '*' in production (allow_credentials is on)")

# [AUDIT-2026-05-22 fix: per-IP throttle for unauthenticated center registration — MongoDB-backed, multi-worker safe]
REGISTER_WINDOW_MINUTES = 60

REGISTER_MAX_PER_WINDOW = 3

# إصدار التطبيق. كان مكتوباً داخل كائن FastAPI وحده، فاضطر فحصُ الجاهزية
# إلى استيراد app نفسه — وهي دورة استيراد. المصدر هنا الآن.
APP_VERSION = "2.1.0"
