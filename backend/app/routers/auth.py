"""المصادقة وكلمات المرور."""

from app.clock import utc_from_timestamp, utcnow

from datetime import timedelta
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from fastapi.security import OAuth2PasswordRequestForm
from typing import Optional
import hmac
import jwt
import secrets

from app.audit import write_audit_log
from app.common import _PHONE_SCOPED_ROLES, client_ip
from app.config import ACCESS_TOKEN_EXPIRE_MINUTES, ALGORITHM, MAX_LOGIN_ATTEMPTS, REFRESH_TOKEN_EXPIRE_DAYS, RESET_CODE_TTL_MINUTES, RESET_MAX_VERIFY_ATTEMPTS, SECRET_KEY, logger
from app.db import db
from app.models import AdminResetPasswordRequest, ChangePasswordRequest, ForgotPasswordRequest, LogoutBody, RefreshRequest, ResetPasswordRequest, Token, UpdateProfileRequest, UserResponse
from app.security import _check_rate_limit, _check_reset_request_rate, _clear_attempts, _clear_attempts_for_account, _decode_and_verify, _record_failed_attempt, authenticate_user, create_access_token, create_refresh_token, get_current_user, get_password_hash, get_user_by_username, hash_reset_code, oauth2_scheme, revoke_jti, validate_password_complexity, verify_password

router = APIRouter()


@router.post("/api/auth/login", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """تسجيل الدخول مع حماية Rate Limiting"""
    ip = client_ip(request)
    await _check_rate_limit(ip, form_data.username)

    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        # [AUDIT-2026-05-22 fix: await DB-backed rate-limit calls]
        current_count = await _record_failed_attempt(ip, form_data.username)
        await write_audit_log(
            actor_id="anonymous",
            center_id="system",
            action="LOGIN_FAILED",
            payload={"username": form_data.username},
            client_ip=ip,
        )
        attempts_left = max(0, MAX_LOGIN_ATTEMPTS - current_count)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"اسم المستخدم أو كلمة المرور غير صحيحة ({attempts_left} محاولات متبقية)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # [AUDIT-2026-05-22 fix: refuse to issue tokens for disabled accounts even on correct password]
    if not user.get("is_active", True):
        await write_audit_log(
            actor_id=str(user["_id"]),
            center_id=user.get("center_id", "system"),
            action="LOGIN_DENIED_DISABLED",
            payload={"username": user["username"]},
            client_ip=ip,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="الحساب معطّل - Account is disabled")

    await _clear_attempts(ip, form_data.username)
    # تسجيل الدخول الناجح
    # [AUDIT-2026-09-03 fix: كانت أحداث الدخول تُكتب مباشرة بلا center_id ولا بصمة، فلا تظهر
    #  إطلاقاً في /api/audit-logs لمدير مركز (يُصفّى بـ center_id) وتبقى خارج سلسلة التحقق.]
    await write_audit_log(
        actor_id=str(user["_id"]),
        center_id=user.get("center_id", "system"),
        action="LOGIN_SUCCESS",
        payload={"username": user["username"], "role": user["role"]},
        client_ip=ip,
    )

    # [AUDIT-2026-05-22 fix: issue short-lived access + long-lived refresh]
    access_token, _ = create_access_token(user)
    refresh_token, _ = create_refresh_token(user)

    user_response = UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        name=user["name"],
        email=user.get("email"),
        phone=user.get("phone"),
        role=user["role"],
        center_id=user.get("center_id"),
        is_active=user["is_active"],
        created_at=user["created_at"]
    )

    return Token(
        access_token=access_token,
        token_type="bearer",
        user=user_response,
        refresh_token=refresh_token,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.post("/api/auth/refresh", response_model=Token)
async def refresh_access_token(body: RefreshRequest):
    """تجديد التوكن باستخدام refresh token (مع تدوير وإلغاء القديم)"""
    payload, user = await _decode_and_verify(body.refresh_token, expected_type="refresh")
    # Rotate: revoke the old refresh token jti
    old_jti = payload.get("jti")
    old_exp = utc_from_timestamp(payload["exp"]) if "exp" in payload else (utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
    if old_jti:
        await revoke_jti(old_jti, old_exp)

    new_access, _ = create_access_token(user)
    new_refresh, _ = create_refresh_token(user)

    user_response = UserResponse(
        id=str(user["_id"]),
        username=user["username"],
        name=user["name"],
        email=user.get("email"),
        phone=user.get("phone"),
        role=user["role"],
        center_id=user.get("center_id"),
        is_active=user["is_active"],
        created_at=user["created_at"],
    )
    return Token(
        access_token=new_access,
        token_type="bearer",
        user=user_response,
        refresh_token=new_refresh,
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )

@router.get("/api/auth/me", response_model=UserResponse)
async def get_me(current_user: dict = Depends(get_current_user)):
    """الحصول على بيانات المستخدم الحالي"""
    return UserResponse(
        id=str(current_user["_id"]),
        username=current_user["username"],
        name=current_user["name"],
        email=current_user.get("email"),
        phone=current_user.get("phone"),
        role=current_user["role"],
        center_id=current_user.get("center_id"),
        is_active=current_user["is_active"],
        created_at=current_user["created_at"]
    )

@router.post("/api/auth/logout")
async def logout(
    request: Request,
    body: Optional[LogoutBody] = None,
    token: str = Depends(oauth2_scheme),
    current_user: dict = Depends(get_current_user),
):
    """تسجيل الخروج مع إلغاء التوكن في القائمة السوداء"""
    # [AUDIT-2026-05-22 fix: revoke the access token's jti so the token cannot be reused]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        jti = payload.get("jti")
        exp = utc_from_timestamp(payload["exp"]) if "exp" in payload else (utcnow() + timedelta(hours=1))
        if jti:
            await revoke_jti(jti, exp)
    except jwt.PyJWTError:
        pass

    # [AUDIT-2026-05-22 fix: also revoke the refresh token if the client supplied it]
    if body and body.refresh_token:
        try:
            r_payload = jwt.decode(body.refresh_token, SECRET_KEY, algorithms=[ALGORITHM])
            if r_payload.get("type") == "refresh" and r_payload.get("sub") == current_user["username"]:
                r_jti = r_payload.get("jti")
                r_exp = utc_from_timestamp(r_payload["exp"]) if "exp" in r_payload else (utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
                if r_jti:
                    await revoke_jti(r_jti, r_exp)
        except jwt.PyJWTError:
            pass

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="LOGOUT",
        payload={"username": current_user["username"]},
        client_ip=client_ip(request),
    )
    return {"message": "تم تسجيل الخروج بنجاح"}

@router.post("/api/auth/change-password")
async def change_password(
    request: Request,
    data: ChangePasswordRequest,
    current_user: dict = Depends(get_current_user)
):
    """تغيير كلمة المرور"""
    if not verify_password(data.current_password, current_user["hashed_password"]):
        raise HTTPException(status_code=400, detail="كلمة المرور الحالية غير صحيحة")
    # [AUDIT-2026-05-22 fix: enforce complexity + invalidate all existing sessions via user_version bump]
    validate_password_complexity(data.new_password)
    if data.new_password == data.current_password:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تختلف عن الحالية")
    new_hash = get_password_hash(data.new_password)
    next_version = int(current_user.get("user_version", 0)) + 1
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {
            "hashed_password": new_hash,
            "user_version": next_version,
            "password_changed_at": utcnow(),
            "must_change_password": False,
        }}
    )
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="PASSWORD_CHANGED",
        payload={"username": current_user["username"]},
        client_ip=client_ip(request),
    )

    # [AUDIT-2026-05-22 fix: hand the caller a fresh access+refresh pair so they don't get logged out
    #  of THIS device — other devices are invalidated automatically via user_version bump]
    refreshed_user = dict(current_user)
    refreshed_user["user_version"] = next_version
    new_access, _ = create_access_token(refreshed_user)
    new_refresh, _ = create_refresh_token(refreshed_user)
    return {
        "message": "تم تغيير كلمة المرور بنجاح. تم تسجيل الخروج تلقائياً من الأجهزة الأخرى.",
        "access_token": new_access,
        "refresh_token": new_refresh,
        "expires_in": ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    }

@router.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, request: Request):
    """طلب إعادة تعيين كلمة المرور (لا يسرب الرمز في الاستجابة)"""
    ip = client_ip(request)
    await _check_reset_request_rate(ip, data.username)

    user = await get_user_by_username(data.username)
    if not user:
        # Don't leak whether user exists to avoid user enumeration
        return {"message": "إذا كان المستخدم موجوداً، فقد تم إرسال رمز التحقق"}

    # Generate 6-digit code
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES)

    # [AUDIT-2026-09-03 fix: يُخزَّن الرمز مبصوماً فقط — من يقرأ قاعدة البيانات أو نسخة احتياطية
    #  لم يعد يملك رموز إعادة تعيين صالحة لكل الحسابات.]
    await db.password_resets.update_one(
        {"username": data.username},
        {"$set": {
            "username": data.username,
            "code_hash": hash_reset_code(data.username, code),
            "expires_at": expires_at,
            "attempts": 0,
            "requested_from_ip": ip,
            "created_at": utcnow(),
        },
         "$unset": {"code": ""}},   # تنظيف أي رمز صريح قديم من قبل هذا الإصلاح
        upsert=True
    )

    # In production, this would send an SMS/Email. Here we log it server-side only.
    logger.info(f"[reset] code issued for {data.username}: {code} (expires in {RESET_CODE_TTL_MINUTES} min)")

    return {"message": "إذا كان المستخدم موجوداً، فقد تم إرسال رمز التحقق"}

@router.get("/api/auth/reset-codes")
async def get_reset_codes(current_user: dict = Depends(get_current_user)):
    """
    طلبات إعادة التعيين النشطة — بيانات وصفية فقط، بلا أي رمز.

    [AUDIT-2026-09-03 fix — ثغرة استيلاء كامل على النظام] كانت هذه النقطة تعيد الرمز الصريح
    لكل الحسابات لأي admin أو center_manager. فيكفي لمدير مركز واحد أن ينفّذ:
    forgot-password{"username":"superadmin"} ← reset-codes ← reset-password ليصبح المدير العام
    ويرى ويعدّل كل المراكز. صارت للمدير العام ومدير النظام فقط، وبلا رمز إطلاقاً.
    من يحتاج فعلاً إعادة تعيين لمستخدم يستعمل POST /api/auth/admin-reset-password المُدقَّق.
    """
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    now = utcnow()
    entries = await db.password_resets.find({"expires_at": {"$gt": now}}).to_list(100)
    return [
        {
            "username": c["username"],
            "expires_at": c["expires_at"].isoformat(),
            "attempts_used": c.get("attempts", 0),
            "requested_from_ip": c.get("requested_from_ip"),
        }
        for c in entries
    ]

@router.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, request: Request):
    """إعادة تعيين كلمة المرور باستخدام الرمز المكون من 6 أرقام"""
    ip = client_ip(request)
    reset_entry = await db.password_resets.find_one({"username": data.username})
    user = await get_user_by_username(data.username)

    generic = HTTPException(status_code=400, detail="المستخدم أو الرمز غير صالح")
    if not user or not reset_entry:
        raise generic

    if utcnow() > reset_entry["expires_at"]:
        await db.password_resets.delete_one({"username": data.username})
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز")

    # [AUDIT-2026-09-03 fix: رمز من 6 أرقام بلا سقف محاولات = مليون تخمينة بلا مقاومة]
    attempts = int(reset_entry.get("attempts", 0))
    if attempts >= RESET_MAX_VERIFY_ATTEMPTS:
        await db.password_resets.delete_one({"username": data.username})
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="تم تجاوز عدد المحاولات. اطلب رمزاً جديداً.",
        )

    stored_hash = reset_entry.get("code_hash")
    if not stored_hash:
        # سجل قديم بنص صريح من قبل الإصلاح — يُبطل بدل قبوله
        await db.password_resets.delete_one({"username": data.username})
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز، اطلب رمزاً جديداً")

    if not hmac.compare_digest(stored_hash, hash_reset_code(data.username, data.code)):
        await db.password_resets.update_one(
            {"username": data.username}, {"$inc": {"attempts": 1}}
        )
        raise generic

    validate_password_complexity(data.new_password)

    new_hash = get_password_hash(data.new_password)
    next_version = int(user.get("user_version", 0)) + 1

    await db.users.update_one(
        {"_id": user["_id"]},
        {"$set": {
            "hashed_password": new_hash,
            "user_version": next_version,
            "password_changed_at": utcnow()
        }}
    )

    await db.password_resets.delete_one({"username": data.username})
    await _clear_attempts_for_account(data.username)

    await write_audit_log(
        actor_id=str(user["_id"]),
        center_id=user.get("center_id", "system"),
        action="PASSWORD_RESET_VIA_CODE",
        payload={"username": data.username},
        client_ip=ip
    )

    return {"message": "تمت إعادة تعيين كلمة المرور بنجاح"}

@router.post("/api/auth/admin-reset-password")
async def admin_reset_password(
    data: AdminResetPasswordRequest,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    [AUDIT-2026-09-03 addition] المسار المشروع الذي كانت /auth/reset-codes تُستعمل لأجله:
    إعادة تعيين كلمة مرور مستخدم من قبل الإدارة — لكن ضمن نطاق محدود ومسجّل.

    القواعد: مدير المركز لا يطال إلا مستخدمي مركزه، ولا أحد دون المدير العام يطال حساب
    admin أو super_admin، ولا أحد يعيد تعيين كلمة مروره بهذه النقطة (لذلك change-password).
    """
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    target = await get_user_by_username(data.username)
    if not target:
        raise HTTPException(status_code=404, detail="المستخدم غير موجود")

    if str(target["_id"]) == str(current_user["_id"]):
        raise HTTPException(status_code=400, detail="استخدم تغيير كلمة المرور من ملفك الشخصي")

    actor_role = current_user["role"]
    target_role = target.get("role")

    if target_role in ("admin", "super_admin") and actor_role != "super_admin":
        raise HTTPException(status_code=403, detail="غير مصرح لك بإعادة تعيين كلمة مرور حساب إداري")

    if actor_role == "center_manager":
        if target_role in ("admin", "super_admin", "center_manager"):
            raise HTTPException(status_code=403, detail="غير مصرح")
        if not current_user.get("center_id") or target.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="هذا المستخدم لا ينتمي لمركزك")

    validate_password_complexity(data.new_password)

    await db.users.update_one(
        {"_id": target["_id"]},
        {"$set": {
            "hashed_password": get_password_hash(data.new_password),
            "user_version": int(target.get("user_version", 0)) + 1,
            "password_changed_at": utcnow(),
            "must_change_password": True,
        }}
    )
    await db.password_resets.delete_one({"username": data.username})
    await _clear_attempts_for_account(data.username)

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="ADMIN_RESET_PASSWORD",
        payload={"target_username": data.username, "target_role": target_role, "by": current_user["username"]},
        client_ip=client_ip(request),
    )
    return {"message": "تمت إعادة تعيين كلمة المرور. أُنهيت جلسات المستخدم على كل الأجهزة."}

@router.put("/api/auth/profile")
async def update_profile(
    request: Request,
    data: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """
    تحديث الملف الشخصي.

    [AUDIT-2026-09-03 fix — ثغرة تصعيد صلاحيات] كان بالإمكان تعديل الهاتف والاسم ذاتياً، وهما
    نفسهما مفتاحا الملكية في check_student_access و /api/students و /api/fees. فيكفي أن يضع
    وليّ أمر رقم هاتف أسرة أخرى ليقرأ ملفات أبنائها ودرجاتهم ورسومهم. الاسم لم يعد مفتاح ملكية،
    ورقم الهاتف لم يعد قابلاً للتعديل الذاتي لأدوار (ولي الأمر / الطالب) — يغيّره مدير المركز.
    """
    update_data = {k: v for k, v in data.model_dump().items() if v is not None}

    if "phone" in update_data:
        new_phone = str(update_data["phone"]).strip()
        current_phone = (current_user.get("phone") or "").strip()
        if new_phone != current_phone:
            if current_user.get("role") in _PHONE_SCOPED_ROLES:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="لا يمكن تغيير رقم الهاتف من هنا — تواصل مع إدارة المركز لتعديله",
                )
            # لبقية الأدوار: الهاتف فريد حتى لا ينتحل أحدهم مطابقة ملكية قائمة
            clash = await db.users.find_one({"phone": new_phone, "_id": {"$ne": current_user["_id"]}})
            if clash:
                raise HTTPException(status_code=400, detail="رقم الهاتف مستخدم في حساب آخر")
            update_data["phone"] = new_phone

    if "email" in update_data:
        email = str(update_data["email"]).strip()
        if email and ("@" not in email or "." not in email.split("@")[-1] or len(email) > 254):
            raise HTTPException(status_code=400, detail="البريد الإلكتروني غير صالح")
        update_data["email"] = email

    if "name" in update_data:
        name = str(update_data["name"]).strip()
        if not name or len(name) > 120:
            raise HTTPException(status_code=400, detail="الاسم غير صالح")
        update_data["name"] = name

    if update_data:
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": update_data}
        )
        await write_audit_log(
            actor_id=str(current_user["_id"]),
            center_id=current_user.get("center_id", "system"),
            action="PROFILE_UPDATED",
            payload={"username": current_user["username"], "fields": sorted(update_data.keys())},
            client_ip=client_ip(request),
        )
    return {"message": "تم تحديث الملف بنجاح"}
