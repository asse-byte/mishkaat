"""
نظام إدارة مراكز تحفيظ القرآن الكريم
Quran Memorization Center Management System

English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).

──────────────────────────────────────────────────────────────────────────────
هذا الملف كان 5367 سطراً تضمّ كل شيء: الإعدادات والنماذج والأمن والتدقيق
و89 مساراً. صار غلافاً رفيعاً، والشيفرة انتقلت إلى حزمة `app/`:

    app/config.py      الإعدادات والأسرار والثوابت
    app/db.py          اتصال قاعدة البيانات
    app/models.py      نماذج Pydantic
    app/security.py    المصادقة والتوكنات وحدود المحاولات
    app/pii.py         تعمية الحقول الشخصية
    app/audit.py       سلسلة سجل التدقيق
    app/common.py      المساعدات المشتركة وفحص الملكية (BOLA)
    app/scoring.py     معادلة التقييم الذكي
    app/sse.py         الإشعارات: الحفظ والبثّ الحيّ
    app/startup.py     الفهارس والحسابات الأولى
    app/main.py        تركيب التطبيق وضمّ الموجّهات
    app/routers/*.py   17 موجّهاً حسب المجال

يبقى `server:app` نقطةَ الدخول كما هي، فلا يتغيّر أمر uvicorn ولا Dockerfile.
والأسماء المُعاد تصديرها أدناه يعتمد عليها ملف الاختبارات مباشرةً
(server.db، server.client، server.startup_event، server.ObjectId …).
──────────────────────────────────────────────────────────────────────────────
"""

from datetime import datetime, timedelta

from bson import ObjectId

from app.config import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    ACCOUNT_LOCKOUT_MINUTES,
    ALGORITHM,
    ALLOWED_ORIGINS,
    APP_ENV,
    AUDIT_PERMANENT_ACTIONS,
    BCRYPT_ROUNDS,
    DB_NAME,
    IS_PRODUCTION,
    LOCKOUT_MINUTES,
    MAX_ACCOUNT_ATTEMPTS,
    MAX_LOGIN_ATTEMPTS,
    MONGO_URL,
    REFRESH_TOKEN_EXPIRE_DAYS,
    REGISTER_MAX_PER_WINDOW,
    REGISTER_WINDOW_MINUTES,
    RESET_CODE_TTL_MINUTES,
    RESET_MAX_REQUESTS_PER_HOUR,
    RESET_MAX_VERIFY_ATTEMPTS,
    SECRET_KEY,
    TRUST_PROXY,
    logger,
)
from app.db import client, db
from app.pii import decrypt_pii, decrypt_student_doc, encrypt_pii, encrypt_student_doc
from app.security import (
    authenticate_user,
    create_access_token,
    create_refresh_token,
    get_current_user,
    get_password_hash,
    get_user_by_username,
    hash_reset_code,
    revoke_jti,
    validate_password_complexity,
    verify_password,
)
from app.audit import audit_hash_input, write_audit_log
from app.common import (
    NOT_DELETED,
    check_student_access,
    client_ip,
    parse_date_boundary,
    redact_teacher,
    safe_object_id,
    serialize_doc,
)
from app.scoring import compute_student_scores
from app.sse import push_notification, push_sse_notification
from app.startup import startup_event
from app.main import app

__all__ = [
    "datetime", "timedelta", "ObjectId", "ACCESS_TOKEN_EXPIRE_MINUTES",
    "ACCOUNT_LOCKOUT_MINUTES", "ALGORITHM", "ALLOWED_ORIGINS", "APP_ENV",
    "AUDIT_PERMANENT_ACTIONS", "BCRYPT_ROUNDS", "DB_NAME", "IS_PRODUCTION",
    "LOCKOUT_MINUTES", "MAX_ACCOUNT_ATTEMPTS", "MAX_LOGIN_ATTEMPTS", "MONGO_URL",
    "REFRESH_TOKEN_EXPIRE_DAYS", "REGISTER_MAX_PER_WINDOW", "REGISTER_WINDOW_MINUTES", "RESET_CODE_TTL_MINUTES",
    "RESET_MAX_REQUESTS_PER_HOUR", "RESET_MAX_VERIFY_ATTEMPTS", "SECRET_KEY", "TRUST_PROXY",
    "logger", "client", "db", "decrypt_pii",
    "decrypt_student_doc", "encrypt_pii", "encrypt_student_doc", "authenticate_user",
    "create_access_token", "create_refresh_token", "get_current_user", "get_password_hash",
    "get_user_by_username", "hash_reset_code", "revoke_jti", "validate_password_complexity",
    "verify_password", "audit_hash_input", "write_audit_log", "NOT_DELETED",
    "check_student_access", "client_ip", "parse_date_boundary", "redact_teacher",
    "safe_object_id", "serialize_doc", "compute_student_scores", "push_notification",
    "push_sse_notification", "startup_event", "app",
]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
