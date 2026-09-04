"""المصادقة والتوكنات وحدود المحاولات."""

from app.clock import utcnow

from datetime import datetime
from datetime import timedelta
from fastapi import Depends
from fastapi import HTTPException
from fastapi import status
from fastapi.security import OAuth2PasswordBearer
from pymongo import ReturnDocument
from typing import Optional
import bcrypt
import hashlib
import hmac
import jwt
import secrets

from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ACCOUNT_LOCKOUT_MINUTES, ALGORITHM, BCRYPT_ROUNDS, LOCKOUT_MINUTES, MAX_ACCOUNT_ATTEMPTS, MAX_LOGIN_ATTEMPTS, REFRESH_TOKEN_EXPIRE_DAYS, REGISTER_MAX_PER_WINDOW, REGISTER_WINDOW_MINUTES, RESET_MAX_REQUESTS_PER_HOUR, SECRET_KEY, logger
from app.db import db


def validate_password_complexity(password: str) -> None:
    """[AUDIT-2026-05-22 fix: enforce password complexity uniformly]"""
    if not password or len(password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تكون 8 أحرف على الأقل")
    if not any(c.isdigit() for c in password):
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تحتوي على رقم")
    if not any(c.isalpha() for c in password):
        raise HTTPException(status_code=400, detail="كلمة المرور يجب أن تحتوي على حرف")

# OAuth2
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

# ==================== Helper Functions ====================

def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))
    except Exception:
        return False

def get_password_hash(password: str) -> str:
    salt = bcrypt.gensalt(rounds=BCRYPT_ROUNDS)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')

def _encode_jwt(payload: dict, expires_delta: timedelta, token_type: str) -> tuple[str, str, datetime]:
    """[AUDIT-2026-05-22 fix: tokens now carry jti + type + user_version for revocation/rotation]"""
    now = utcnow()
    expire = now + expires_delta
    jti = secrets.token_hex(16)
    body = {**payload, "exp": expire, "iat": int(now.timestamp()), "jti": jti, "type": token_type}
    encoded = jwt.encode(body, SECRET_KEY, algorithm=ALGORITHM)
    return encoded, jti, expire

def create_access_token(user: dict) -> tuple[str, datetime]:
    encoded, _jti, expire = _encode_jwt(
        {"sub": user["username"], "uv": user.get("user_version", 0)},
        timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES),
        "access",
    )
    return encoded, expire

def create_refresh_token(user: dict) -> tuple[str, datetime]:
    encoded, _jti, expire = _encode_jwt(
        {"sub": user["username"], "uv": user.get("user_version", 0)},
        timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS),
        "refresh",
    )
    return encoded, expire

async def get_user_by_username(username: str) -> Optional[dict]:
    user = await db.users.find_one({"username": username})
    return user

async def authenticate_user(username: str, password: str) -> Optional[dict]:
    user = await get_user_by_username(username)
    if not user:
        return None
    if not verify_password(password, user["hashed_password"]):
        return None
    return user

async def revoke_jti(jti: str, expires_at: datetime):
    """تسجيل توكن مُلغى في القائمة السوداء (TTL ينظّف تلقائياً)"""
    if not jti:
        return
    await db.revoked_tokens.update_one(
        {"jti": jti},
        {"$set": {"jti": jti, "expires_at": expires_at}},
        upsert=True,
    )

async def _decode_and_verify(token: str, expected_type: str = "access") -> tuple[dict, dict]:
    """يفك ويتحقق من التوكن. يعيد (payload, user_doc)"""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
    except jwt.PyJWTError:
        raise credentials_exception

    # [AUDIT-2026-05-22 fix: enforce token type — refresh cannot be used as access]
    token_type = payload.get("type", "access")
    if token_type != expected_type:
        raise credentials_exception

    username = payload.get("sub")
    jti = payload.get("jti")
    token_uv = payload.get("uv", 0)
    token_iat = payload.get("iat")
    if not username:
        raise credentials_exception

    # [AUDIT-2026-05-22 fix: revocation blacklist check]
    if jti and await db.revoked_tokens.find_one({"jti": jti}):
        raise credentials_exception

    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception

    # [AUDIT-2026-05-22 fix: reject tokens for disabled accounts]
    if not user.get("is_active", True):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="الحساب معطّل - Account is disabled",
        )

    # [AUDIT-2026-05-22 fix: user_version mismatch (e.g., password changed) invalidates token]
    if user.get("user_version", 0) != token_uv:
        raise credentials_exception

    # [PHASE-1 fix: check password_changed_at against token iat]
    password_changed_at = user.get("password_changed_at")
    if password_changed_at and token_iat:
        if isinstance(password_changed_at, str):
            try:
                password_changed_at = datetime.fromisoformat(password_changed_at)
            except ValueError:
                password_changed_at = None
        if password_changed_at:
            if password_changed_at.timestamp() > token_iat:
                raise credentials_exception

    return payload, user

async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    _payload, user = await _decode_and_verify(token, expected_type="access")
    return user

# ==================== Auth Routes ====================

# [AUDIT-2026-05-22 fix: rate-limit state moved to MongoDB so it is correct across workers/processes]
# [AUDIT-2026-09-03 fix: القفل صار على مفتاحين — العنوان والحساب. القفل على العنوان وحده كان
#  يُتجاوَز بتدوير العناوين، وخلف وكيل واحد كان يقفل كل مستخدمي المركز دفعة واحدة.]
async def _check_attempt_key(key: str, label: str):
    now = utcnow()
    entry = await db.login_attempts.find_one({"_id": key})
    if not entry:
        return
    locked = entry.get("locked_until")
    if locked and now < locked:
        remaining = int((locked - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تم تجاوز عدد المحاولات ({label}). حاول مرة أخرى بعد {remaining} دقيقة"
        )

async def _check_rate_limit(ip: str, username: Optional[str] = None):
    """فحص حد معدل محاولات تسجيل الدخول (MongoDB-backed)"""
    await _check_attempt_key(f"ip:{ip}", "من هذا الجهاز")
    if username:
        await _check_attempt_key(f"user:{username}", "لهذا الحساب")

async def _bump_attempt_key(key: str, maximum: int, lock_minutes: int) -> int:
    now = utcnow()
    entry = await db.login_attempts.find_one_and_update(
        {"_id": key},
        {"$inc": {"count": 1}, "$set": {"last_seen": now}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    count = int(entry.get("count", 1))
    if count >= maximum:
        await db.login_attempts.update_one(
            {"_id": key},
            {"$set": {"locked_until": now + timedelta(minutes=lock_minutes)}},
        )
        logger.warning(f"تم قفل {key} بعد {count} محاولات فاشلة")
    return count

async def _record_failed_attempt(ip: str, username: Optional[str] = None) -> int:
    """تسجيل محاولة فاشلة، يرجع عدد محاولات هذا العنوان"""
    ip_count = await _bump_attempt_key(f"ip:{ip}", MAX_LOGIN_ATTEMPTS, LOCKOUT_MINUTES)
    if username:
        await _bump_attempt_key(f"user:{username}", MAX_ACCOUNT_ATTEMPTS, ACCOUNT_LOCKOUT_MINUTES)
    return ip_count

async def _clear_attempts(ip: str, username: Optional[str] = None):
    """مسح المحاولات بعد نجاح الدخول"""
    await db.login_attempts.delete_one({"_id": f"ip:{ip}"})
    if username:
        await db.login_attempts.delete_one({"_id": f"user:{username}"})

async def _clear_attempts_for_account(username: str):
    """رفع القفل عن حساب بعد إعادة تعيين كلمة مروره بنجاح"""
    await db.login_attempts.delete_one({"_id": f"user:{username}"})

def hash_reset_code(username: str, code: str) -> str:
    """
    [AUDIT-2026-09-03 fix] بصمة الرمز بدل تخزينه كنص صريح.
    مربوطة باسم المستخدم حتى لا يصلح رمز حساب لحساب آخر.
    """
    return hmac.new(SECRET_KEY.encode(), f"{username}:{code}".encode(), hashlib.sha256).hexdigest()

async def _check_reset_request_rate(ip: str, username: str):
    """حدّ لطلبات إعادة التعيين — بالعنوان وبالحساب معاً"""
    now = utcnow()
    window_start = now - timedelta(hours=1)
    for key in (f"ip:{ip}", f"user:{username}"):
        await db.reset_requests.update_one(
            {"_id": key}, {"$pull": {"timestamps": {"$lt": window_start}}}
        )
        entry = await db.reset_requests.find_one({"_id": key})
        fresh = entry.get("timestamps", []) if entry else []
        if len(fresh) >= RESET_MAX_REQUESTS_PER_HOUR:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="تجاوزت عدد طلبات إعادة التعيين المسموح بها. حاول بعد ساعة.",
            )
        await db.reset_requests.update_one(
            {"_id": key},
            {"$push": {"timestamps": now}, "$set": {"last_seen": now}},
            upsert=True,
        )

async def _check_register_rate(ip: str):
    now = utcnow()
    window_start = now - timedelta(minutes=REGISTER_WINDOW_MINUTES)
    # Trim old timestamps, then check count
    await db.register_attempts.update_one(
        {"_id": ip},
        {"$pull": {"timestamps": {"$lt": window_start}}},
    )
    entry = await db.register_attempts.find_one({"_id": ip})
    fresh = entry.get("timestamps", []) if entry else []
    if len(fresh) >= REGISTER_MAX_PER_WINDOW:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تجاوزت الحد المسموح. حاول بعد {REGISTER_WINDOW_MINUTES} دقيقة."
        )
    await db.register_attempts.update_one(
        {"_id": ip},
        {"$push": {"timestamps": now}, "$set": {"last_seen": now}},
        upsert=True,
    )
