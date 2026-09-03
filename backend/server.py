"""
نظام إدارة مراكز تحفيظ القرآن الكريم
Quran Memorization Center Management System

English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
"""

from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse, StreamingResponse, PlainTextResponse
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel, ConfigDict
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from pymongo.errors import OperationFailure
from cryptography.fernet import Fernet, InvalidToken
import os
import io
import re
import csv
import sys
import uuid
import asyncio          # [AUDIT-2026-09-03 fix: was used by the SSE stream but never imported → NameError]
import secrets
import hmac
import hashlib
import json
from contextlib import asynccontextmanager
from dotenv import load_dotenv
import jwt
import bcrypt
import logging

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

# MongoDB Client
client = AsyncIOMotorClient(MONGO_URL)
db = client[DB_NAME]

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

# [AUDIT-2026-09-03 fix: @app.on_event("startup") مهجور وسيُحذف من FastAPI.
#  الدالة startup_event نفسها لم تتغير — غيّرنا طريقة استدعائها فقط، والاختبارات تناديها مباشرة.]
@asynccontextmanager
async def lifespan(_app: FastAPI):
    await startup_event()
    yield


# FastAPI App
app = FastAPI(
    lifespan=lifespan,
    title="نظام إدارة مراكز التحفيظ",
    description="API لإدارة مراكز تحفيظ القرآن الكريم",
    version="2.1.0",
    # الوثائق التفاعلية متاحة في التطوير فقط، ومعطّلة تماماً في الإنتاج
    docs_url=None if IS_PRODUCTION else "/api/docs",
    redoc_url=None,
    openapi_url=None if IS_PRODUCTION else "/api/openapi.json",
)

# GZip compression لتسريع الاستجابات
app.add_middleware(GZipMiddleware, minimum_size=1000)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Accept"],
    max_age=600,
)


def client_ip(request: Request) -> str:
    """
    [AUDIT-2026-09-03 fix] عنوان العميل الحقيقي.
    خلف nginx يكون request.client.host هو عنوان الوكيل نفسه لكل المستخدمين، فيقفل النظام الجميع
    بعد 5 محاولات خاطئة من شخص واحد. نقرأ X-Forwarded-For فقط عندما نكون فعلاً خلف وكيل نثق به.
    """
    if TRUST_PROXY:
        fwd = request.headers.get("x-forwarded-for")
        if fwd:
            # أول عنوان في السلسلة هو العميل الأصلي
            first = fwd.split(",")[0].strip()
            if first:
                return first
        real = request.headers.get("x-real-ip")
        if real:
            return real.strip()
    return request.client.host if request.client else "unknown"


# [AUDIT-2026-09-03 addition: رؤوس أمنية على كل استجابة + معرّف طلب للتتبّع]
@app.middleware("http")
async def security_and_tracing_middleware(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:16]
    request.state.request_id = request_id
    try:
        response = await call_next(request)
    except HTTPException:
        raise
    except Exception:
        # [AUDIT-2026-09-03 fix: لا تُسرّب أثر الاستثناء (stack trace) للعميل — يُسجَّل داخلياً فقط]
        logger.exception(f"[{request_id}] unhandled error on {request.method} {request.url.path}")
        return JSONResponse(
            status_code=500,
            content={"detail": "حدث خطأ داخلي في الخادم", "request_id": request_id},
        )

    response.headers["X-Request-ID"] = request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
    response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    # واجهة JSON فقط: لا سكربتات ولا إطارات (ما عدا صفحة الوثائق في التطوير)
    if not request.url.path.startswith("/api/docs"):
        response.headers.setdefault(
            "Content-Security-Policy",
            "default-src 'none'; frame-ancestors 'none'; base-uri 'none'",
        )
    if IS_PRODUCTION:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# ==================== Pydantic Models ====================

UserRole = Literal["admin", "center_manager", "teacher", "student", "parent", "super_admin"]
RecitationEvaluation = Literal["excellent", "good", "acceptable", "needs_improvement"]
AttendanceStatus = Literal["present", "absent", "late", "excused"]
FeeStatus = Literal["pending", "paid", "overdue"]
FeeType = Literal["monthly", "annual", "registration"]
MemorizationPlan = Literal["plan_2_years", "plan_3_years", "plan_4_years", "plan_5_years", "plan_review"]


class UserBase(BaseModel):
    username: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    role: UserRole
    center_id: Optional[str] = None
    is_active: bool = True


class UserCreate(UserBase):
    password: str


class UserResponse(UserBase):
    id: str
    created_at: datetime

    # [AUDIT-2026-09-03 fix: class-based Config محذوف في Pydantic v3 — سيتوقف التطبيق عن
    #  الإقلاع عند أول ترقية للمكتبة. صار ConfigDict.]
    model_config = ConfigDict(from_attributes=True)


class Token(BaseModel):
    access_token: str
    token_type: str
    user: UserResponse
    # [AUDIT-2026-05-22 fix: refresh token returned alongside access token]
    refresh_token: Optional[str] = None
    expires_in: Optional[int] = None  # access-token TTL in seconds


class TokenData(BaseModel):
    username: Optional[str] = None


class CenterBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    is_active: bool = True
    currency: Optional[str] = "FCFA"
    status: Optional[str] = "trial"


class CenterCreate(CenterBase):
    manager_name: Optional[str] = None
    manager_username: Optional[str] = None
    manager_password: Optional[str] = None
    manager_email: Optional[str] = None


class CenterResponse(CenterBase):
    id: str
    manager_id: Optional[str] = None
    manager_name: Optional[str] = None
    created_at: datetime
    students_count: int = 0
    teachers_count: int = 0
    halaqat_count: int = 0


class StudentBase(BaseModel):
    name: str
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    guardian_address: Optional[str] = None
    center_id: str
    halaqah_id: Optional[str] = None
    halaqah_name: Optional[str] = None
    memorization_plan: Optional[MemorizationPlan] = None
    student_type: Literal["memorizing", "reviewing"] = "memorizing"
    is_active: bool = True


class StudentCreate(StudentBase):
    pass


class StudentUpdate(BaseModel):
    name: Optional[str] = None
    date_of_birth: Optional[str] = None
    phone: Optional[str] = None
    parent_name: Optional[str] = None
    parent_phone: Optional[str] = None
    guardian_address: Optional[str] = None
    halaqah_id: Optional[str] = None
    halaqah_name: Optional[str] = None
    memorization_plan: Optional[MemorizationPlan] = None
    student_type: Optional[Literal["memorizing", "reviewing"]] = None
    is_active: Optional[bool] = None


class StudentResponse(StudentBase):
    id: str
    enrollment_date: datetime
    progress: float = 0
    current_surah: Optional[str] = None
    current_ayah: Optional[int] = None


class TeacherBase(BaseModel):
    name: str
    phone: Optional[str] = None
    center_id: str
    specialization: Optional[str] = None
    marital_status: Optional[Literal["single", "married", "divorced", "widowed"]] = None
    work_schedule: Optional[Literal["full_time", "part_time"]] = None
    salary: Optional[float] = None
    is_active: bool = True


class TeacherCreate(TeacherBase):
    username: Optional[str] = None
    password: Optional[str] = None


class TeacherUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    specialization: Optional[str] = None
    marital_status: Optional[Literal["single", "married", "divorced", "widowed"]] = None
    work_schedule: Optional[Literal["full_time", "part_time"]] = None
    salary: Optional[float] = None
    halaqah_id: Optional[str] = None
    is_active: Optional[bool] = None


class TeacherTransferRequest(BaseModel):
    from_halaqah_id: str
    to_halaqah_id: str


class TeacherEvaluationBase(BaseModel):
    teacher_id: str
    evaluation_date: str
    attendance_rate: float
    tajweed_proficiency: int
    student_retention: int
    average_memorization_speed: float
    discipline: int
    notes: Optional[str] = None


class TeacherEvaluationCreate(TeacherEvaluationBase):
    pass


class TeacherEvaluationResponse(TeacherEvaluationBase):
    id: str
    center_id: str
    tpi: float
    teacher_name: Optional[str] = None
    created_at: datetime


class SalaryCreate(BaseModel):
    teacher_id: str
    teacher_name: Optional[str] = None
    amount: float
    month: str  # YYYY-MM
    center_id: str
    notes: Optional[str] = None


class ExpenseCreate(BaseModel):
    title: str
    amount: float
    category: Optional[str] = None
    date: str
    center_id: str
    notes: Optional[str] = None


# [AUDIT-2026-05-22 fix: typed model replaces previous untyped `dict` (mass-assignment risk)]
class ReviewPlanCreate(BaseModel):
    center_id: str
    teacher_id: Optional[str] = None
    student_id: Optional[str] = None
    halaqah_id: Optional[str] = None
    title: Optional[str] = None
    description: Optional[str] = None
    surahs: Optional[List[str]] = None
    notes: Optional[str] = None
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class TeacherResponse(TeacherBase):
    id: str
    user_id: Optional[str] = None
    hire_date: datetime
    halaqat: List[str] = []
    students_count: int = 0


class HalaqahBase(BaseModel):
    name: str
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    center_id: str
    schedule: str
    time: Optional[str] = None
    location: Optional[str] = None
    max_students: int = 20
    is_active: bool = True


class HalaqahCreate(HalaqahBase):
    pass


class HalaqahUpdate(BaseModel):
    name: Optional[str] = None
    teacher_id: Optional[str] = None
    teacher_name: Optional[str] = None
    schedule: Optional[str] = None
    time: Optional[str] = None
    location: Optional[str] = None
    max_students: Optional[int] = None
    is_active: Optional[bool] = None


class AcademicScheduleBase(BaseModel):
    subject: str
    day: str
    time_slot: str
    halaqa_id: str
    teacher_id: str
    room_number: Optional[str] = None


class AcademicScheduleCreate(AcademicScheduleBase):
    # [AUDIT-2026-09-03 fix: كان المسار يقرأ schedule.center_id وهو حقل غير موجود في النموذج
    #  إطلاقاً — فأي مدير نظام غير مرتبط بمركز يحصل على AttributeError → 500 عند إنشاء أي
    #  موعد دراسي. الحقل صار معرّفاً واختيارياً.]
    center_id: Optional[str] = None


class AcademicScheduleResponse(AcademicScheduleBase):
    id: str
    center_id: str
    teacher_name: Optional[str] = None
    halaqa_name: Optional[str] = None


class CompetitionBase(BaseModel):
    title: str
    date: str
    categories: List[str] = ["القرآن كاملاً", "15 جزءاً", "5 أجزاء", "جزء عم"]


class CompetitionCreate(CompetitionBase):
    pass


class CompetitionResponse(CompetitionBase):
    id: str
    center_id: str
    created_at: datetime


class ContestantGrades(BaseModel):
    hifdh_score: float
    tajweed_score: float
    voice_score: float


class CompetitionContestantBase(BaseModel):
    student_id: str
    category: str
    notes: Optional[str] = None


class CompetitionContestantCreate(CompetitionContestantBase):
    pass


class CompetitionContestantResponse(CompetitionContestantBase):
    id: str
    competition_id: str
    center_id: str
    grades: Optional[ContestantGrades] = None
    total_score: float = 0.0
    student_name: Optional[str] = None
    created_at: datetime


class MessageReply(BaseModel):
    teacher_id: str
    teacher_name: str
    content: str
    timestamp: datetime


class BulkMessageBase(BaseModel):
    recipient_role: str
    subject: str
    content: str


class BulkMessageCreate(BulkMessageBase):
    pass


class BulkMessageResponse(BulkMessageBase):
    id: str
    center_id: str
    sender_id: str
    sender_name: Optional[str] = None
    sent_at: datetime
    replies: List[MessageReply] = []


class HalaqahResponse(HalaqahBase):
    id: str
    current_students: int = 0


class RecitationBase(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    teacher_id: str
    teacher_name: Optional[str] = None
    surah_number: Optional[int] = None
    surah_name: str
    start_ayah: int
    end_ayah: int
    evaluation: RecitationEvaluation
    mistakes_count: int = 0
    hesitations_count: int = 0
    tajweed_errors_count: int = 0
    notes: Optional[str] = None
    recitation_type: Literal["new", "review"] = "new"


class RecitationCreate(RecitationBase):
    pass


class RecitationResponse(RecitationBase):
    id: str
    date: datetime


class AttendanceBase(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    halaqah_id: str
    status: AttendanceStatus
    notes: Optional[str] = None


class AttendanceCreate(BaseModel):
    records: List[AttendanceBase]
    date: Optional[str] = None


class AttendanceResponse(AttendanceBase):
    id: str
    date: datetime


class FeeBase(BaseModel):
    student_id: str
    student_name: Optional[str] = None
    amount: float
    due_date: str
    fee_type: FeeType
    notes: Optional[str] = None


class FeeCreate(FeeBase):
    pass


class FeeResponse(FeeBase):
    id: str
    status: FeeStatus = "pending"
    paid_date: Optional[datetime] = None


class DashboardStats(BaseModel):
    total_students: int = 0
    total_teachers: int = 0
    total_centers: int = 0
    total_halaqat: int = 0
    attendance_rate: float = 0.0
    pending_fees: int = 0


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
    now = datetime.utcnow()
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


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


async def _next_audit_seq() -> int:
    """رقم تسلسلي ذرّي لسلسلة سجل التدقيق"""
    doc = await db.counters.find_one_and_update(
        {"_id": "audit_logs"},
        {"$inc": {"seq": 1}},
        upsert=True,
        return_document=ReturnDocument.AFTER,
    )
    return int(doc["seq"])


async def _previous_log_hash(seq: int) -> tuple[str, bool]:
    """
    بصمة السجل السابق حسب الترتيب الذرّي. يعيد (البصمة، هل هناك انقطاع في السلسلة).
    """
    if seq <= 1:
        return "0" * 64, False
    # قد يكون السجل السابق قيد الكتابة الآن من عامل آخر — ننتظره لحظات
    for _ in range(50):
        prev = await db.audit_logs.find_one({"seq": seq - 1}, {"log_hash": 1})
        if prev:
            return prev.get("log_hash", "0" * 64), False
        await asyncio.sleep(0.02)
    logger.error(f"audit chain: previous entry seq={seq - 1} never appeared; recording a marked gap")
    return "0" * 64, True


async def write_audit_log(actor_id: str, center_id: str, action: str, payload: dict, client_ip: str = None) -> dict:
    """
    إضافة سجل تدقيق مالي/إداري غير قابل للتلاعب (سلسلة تشفير SHA-256).

    [AUDIT-2026-09-03 fix] كان السجل السابق يُقرأ بـ sort على الوقت: عند كتابتين متزامنتين يحصل
    السجلّان على نفس previous_hash فتنشقّ السلسلة بصمت وتفشل أي مراجعة لاحقة دون سبب ظاهر.
    صار لكل سجل رقم تسلسلي ذرّي (counters) والسلسلة تُبنى عليه، ويُعلَّم أي انقطاع صراحةً
    بحقل chain_gap بدل التظاهر بأن السلسلة سليمة.
    """
    # MongoDB يخزّن التاريخ بدقة الملي ثانية فقط. لو بُصمت الطوابع بدقة الميكرو ثانية لاختلفت
    # البصمة المُعاد حسابها عن المخزَّنة في كل سجل، فيبلّغ التحقق عن "تلاعب" في سجل سليم.
    now_raw = datetime.utcnow()
    timestamp = now_raw.replace(microsecond=(now_raw.microsecond // 1000) * 1000)
    try:
        seq = await _next_audit_seq()
        previous_hash, gap = await _previous_log_hash(seq)
    except Exception as e:
        logger.error(f"audit chain sequencing failed: {e}")
        seq, previous_hash, gap = None, "0" * 64, True

    serialized_payload = json.dumps(payload, sort_keys=True, default=str)

    hash_input = f"{seq}:{actor_id}:{center_id}:{action}:{serialized_payload}:{timestamp.isoformat()}:{previous_hash}"
    log_hash = hashlib.sha256(hash_input.encode()).hexdigest()

    log_entry = {
        "seq": seq,
        "actor_id": actor_id,
        "center_id": center_id,
        "action": action,
        "payload": payload,
        "timestamp": timestamp,
        "client_ip": client_ip or "system",
        "previous_hash": previous_hash,
        "log_hash": log_hash,
    }
    if gap:
        log_entry["chain_gap"] = True

    if action not in AUDIT_PERMANENT_ACTIONS:
        log_entry["purge_at"] = timestamp + timedelta(days=730)

    try:
        await db.audit_logs.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")

    return log_entry


def audit_hash_input(entry: dict) -> str:
    """إعادة بناء نص البصمة كما كُتب — تستخدمه نقطة التحقق من سلامة السلسلة"""
    ts = entry.get("timestamp")
    ts_iso = ts.isoformat() if isinstance(ts, datetime) else str(ts)
    payload = json.dumps(entry.get("payload", {}), sort_keys=True, default=str)
    return (
        f"{entry.get('seq')}:{entry.get('actor_id')}:{entry.get('center_id')}:"
        f"{entry.get('action')}:{payload}:{ts_iso}:{entry.get('previous_hash')}"
    )


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


def parse_date_boundary(value: str, end: bool = False) -> Optional[datetime]:
    """
    [AUDIT-2026-09-03 addition] تحويل YYYY-MM-DD (أو ISO كامل) إلى حدّ زمني، وتجاهل الصيغ الخاطئة
    بدل تمريرها إلى قاعدة البيانات. تاريخ النهاية يشمل اليوم كله حتى 23:59:59.
    """
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is not None:
            parsed = parsed.replace(tzinfo=None)
    except (ValueError, TypeError):
        return None
    if end and len(str(value)) <= 10:
        parsed = parsed.replace(hour=23, minute=59, second=59, microsecond=999999)
    return parsed


# [AUDIT-2026-09-03 fix: كشف بيانات رواتب] كان GET /api/teachers يُرجع مستند المعلم كما هو —
# بما فيه salary والحالة الاجتماعية — لأي دور داخل المركز، فيرى الطالب وولي الأمر والمعلم
# الآخر راتب كل معلم. الرواتب لإدارة المركز فقط.
_TEACHER_PRIVATE_FIELDS = ("salary", "marital_status")
_TEACHER_PAYROLL_ROLES = {"admin", "super_admin", "center_manager"}


def redact_teacher(doc: dict, role: str) -> dict:
    if role in _TEACHER_PAYROLL_ROLES:
        return doc
    for field in _TEACHER_PRIVATE_FIELDS:
        doc.pop(field, None)
    return doc


def safe_object_id(id_str: str) -> ObjectId:
    """تحويل النص إلى ObjectId بشكل آمن لتجنب أخطاء 500"""
    try:
        return ObjectId(id_str)
    except InvalidId:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="معرف غير صالح - Invalid ID format"
        )


async def check_student_access(student_id: str, current_user: dict) -> dict:
    """التحقق الموحد من ملكية وصلاحية الوصول لبيانات الطالب (حماية BOLA/IDOR)"""
    student_obj_id = safe_object_id(student_id)
    student = await db.students.find_one({"_id": student_obj_id})
    if not student:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="الطالب غير موجود - Student not found"
        )
    
    role = current_user.get("role")
    
    # 1. Super Admin & Admin: الوصول الكامل
    if role in ["super_admin", "admin"]:
        return student
        
    # 2. Center Manager: تطابق مركز الطالب مع مركز المدير
    if role == "center_manager":
        if student.get("center_id") != current_user.get("center_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بالوصول لبيانات هذا الطالب في مركز آخر"
            )
        return student
        
    # 3. Teacher: تطابق مركز الطالب مع مركز المعلم
    if role == "teacher":
        if student.get("center_id") != current_user.get("center_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بالوصول لبيانات هذا الطالب في مركز آخر"
            )
        return student
        
    # 4. Student: تطابق مع حساب الطالب نفسه (عبر الربط المباشر أو رقم الهاتف)
    # [AUDIT-2026-09-03 fix: أُزيلت المطابقة بالاسم. كان الاسم قابلاً للتعديل ذاتياً من
    #  PUT /api/auth/profile، فيكفي أن يعيد طالبٌ تسمية نفسه باسم زميله ليقرأ ملفه ودرجاته
    #  ورسومه بالكامل. الاسم ليس مُعرِّف ملكية.]
    if role == "student":
        allowed = False
        if student.get("user_id") == str(current_user.get("_id")):
            allowed = True
        elif current_user.get("phone") and student.get("phone") == current_user.get("phone"):
            allowed = True

        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بالوصول لبيانات هذا الطالب"
            )
        return student
        
    # 5. Parent: تطابق رقم هاتف ولي الأمر مع حساب ولي الأمر الحالي
    if role == "parent":
        allowed = False
        user_phone = current_user.get("phone")
        if user_phone and (
            student.get("parent_phone") == user_phone or
            student.get("phone") == user_phone
        ):
            allowed = True
            
        if not allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بالوصول لبيانات هذا الطالب"
            )
        return student
        
    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="غير مصرح لك بالوصول لبيانات هذا الطالب"
    )


# ==================== Startup Events ====================

async def startup_event():
    """Initialize database with default data and create indexes"""
    
    async def _safe_create_index(coll, *args, **kwargs):
        try:
            await coll.create_index(*args, **kwargs)
        except OperationFailure as e:
            if e.code == 85:  # IndexOptionsConflict
                try:
                    info = await coll.index_information()
                    keys = args[0]
                    target_key = [(keys, 1)] if isinstance(keys, str) else list(keys)
                    for idx_name, idx_spec in info.items():
                        if idx_spec.get("key") == target_key:
                            await coll.drop_index(idx_name)
                            break
                    await coll.create_index(*args, **kwargs)
                except Exception as exc:
                    logger.warning(f"Could not recreate index on {coll.name}: {exc}")
            else:
                raise

    # Create Indexes for performance
    await _safe_create_index(db.users, "username", unique=True)
    await db.users.create_index("role")
    await db.users.create_index("center_id")
    await db.students.create_index("center_id")
    await db.students.create_index("halaqah_id")
    await db.teachers.create_index("center_id")
    await db.audit_logs.create_index("timestamp")
    
    # [AUDIT-2026-05-22 performance: add critical query optimization indexes]
    await db.recitations.create_index("student_id")
    await db.recitations.create_index([("student_id", 1), ("date", -1)])
    await db.recitations.create_index("teacher_id")
    await db.attendance.create_index("student_id")
    await db.attendance.create_index([("student_id", 1), ("date", -1)])
    await db.attendance.create_index("halaqah_id")
    await db.attendance.create_index([("halaqah_id", 1), ("date_str", 1)])

    # [إصلاح 2026-09-03] الفهرس الفريد هو ما يجعل منع الازدواج حقيقياً.
    # upsert وحده ليس ذرّياً بلا فهرس فريد: طلبان متزامنان (نقرة مزدوجة على «حفظ») لا يجد
    # أيّهما سجلاً فيُدرجان معاً — وهو الازدواج نفسه الذي جاء الإصلاح لمنعه.
    # لا نُفشل الإقلاع إن كانت هناك تكرارات قديمة: تنشيط الفهرس حينها يوقف الخدمة كلها،
    # فنُسجّل تحذيراً واضحاً ويبقى الاستبدال عاملاً، ويُنشَأ الفهرس بعد تنظيف التكرارات.
    try:
        await db.attendance.create_index(
            [("student_id", 1), ("date_str", 1)], unique=True, name="uniq_student_day"
        )
    except Exception as exc:
        logger.warning(
            "تعذّر إنشاء الفهرس الفريد للحضور (student_id + date_str): %s — "
            "الأرجح وجود سجلات مكرّرة قديمة. نظّفها ثم أعد التشغيل ليصبح منع الازدواج مضموناً.",
            exc,
        )
    await db.fees.create_index("student_id")
    await db.fees.create_index("status")
    await db.expenses.create_index([("center_id", 1), ("created_at", -1)])
    await db.halaqat.create_index("center_id")
    await db.halaqat.create_index("teacher_id")
    await db.salaries.create_index([("center_id", 1), ("created_at", -1)])
    await db.salaries.create_index("teacher_id")
    await db.review_plans.create_index([("center_id", 1), ("created_at", -1)])
    await db.review_plans.create_index("teacher_id")

    # [AUDIT-2026-05-22 fix: indexes that support parent/student ownership lookups in check_student_access]
    await db.students.create_index("parent_phone")
    await db.students.create_index("phone")
    await db.students.create_index("user_id")
    await db.teachers.create_index("user_id")
    await db.users.create_index("phone")
    await db.centers.create_index("manager_id")

    # [AUDIT-2026-05-22 fix: TTL indexes for token revocation list and rate-limit storage]
    await _safe_create_index(db.revoked_tokens, "jti", unique=True)
    await _safe_create_index(db.revoked_tokens, "expires_at", expireAfterSeconds=0)
    await _safe_create_index(
        db.login_attempts, "last_seen", expireAfterSeconds=max(LOCKOUT_MINUTES * 60 * 2, 3600)
    )
    await _safe_create_index(
        db.register_attempts, "last_seen", expireAfterSeconds=REGISTER_WINDOW_MINUTES * 60 * 2
    )

    # [AUDIT-2026-09-03 additions: فهارس الإصلاحات الجديدة]
    # نافذة طلبات إعادة التعيين تُنظَّف تلقائياً
    await _safe_create_index(db.reset_requests, "last_seen", expireAfterSeconds=7200)
    # رموز إعادة التعيين المنتهية تُحذف من نفسها بدل أن تتراكم
    await _safe_create_index(db.password_resets, "expires_at", expireAfterSeconds=0)
    await _safe_create_index(db.password_resets, "username", unique=True)
    # سلسلة سجل التدقيق: ترتيب ذرّي فريد (جزئي، لأن السجلات القديمة بلا seq)
    await _safe_create_index(
        db.audit_logs, "seq", unique=True, partialFilterExpression={"seq": {"$exists": True, "$type": "number"}}
    )
    await _safe_create_index(db.audit_logs, [("center_id", 1), ("timestamp", -1)])
    await _safe_create_index(db.audit_logs, "action")
    # النطاق الجديد لسجلات الحضور والرسوم (كانا بلا center_id — انظر /api/dashboard/stats)
    await _safe_create_index(db.attendance, [("student_id", 1), ("date_str", 1)])
    await _safe_create_index(db.attendance, [("center_id", 1), ("date", -1)])
    await _safe_create_index(db.fees, [("center_id", 1), ("status", 1)])
    await _safe_create_index(db.fees, [("student_id", 1), ("status", 1)])
    await _safe_create_index(db.students, [("center_id", 1), ("is_active", 1)])
    await _safe_create_index(db.salaries, [("center_id", 1), ("month", 1)])
    # الإشعارات المخزَّنة: قراءة سريعة للمستخدم، وتنظيف تلقائي بعد 180 يوماً
    await _safe_create_index(db.notifications, [("user_id", 1), ("created_at", -1)])
    await _safe_create_index(db.notifications, [("user_id", 1), ("read", 1)])
    await _safe_create_index(db.notifications, "created_at", expireAfterSeconds=180 * 24 * 3600)

    # Compound and performance indexes for new SaaS collections (v2.1 specification)
    await db.academic_schedules.create_index([("center_id", 1), ("day", 1), ("time_slot", 1)])
    await db.teacher_evaluations.create_index([("center_id", 1), ("teacher_id", 1)])
    await db.competitions.create_index("center_id")
    await db.competition_contestants.create_index([("competition_id", 1), ("student_id", 1)])
    await db.bulk_messages.create_index([("center_id", 1), ("sender_id", 1)])

    # [AUDIT-2026-05-22 fix: admin bootstrap — never ship default password to production]
    SEED_DEMO_DATA = os.getenv("SEED_DEMO_DATA", "false").lower() in ("true", "1", "yes")
    INITIAL_ADMIN_PASSWORD = os.getenv("INITIAL_ADMIN_PASSWORD")

    existing_admin = await db.users.find_one({"username": "admin"})
    if not existing_admin:
        if INITIAL_ADMIN_PASSWORD:
            admin_password = INITIAL_ADMIN_PASSWORD
            password_source = "INITIAL_ADMIN_PASSWORD env"
        elif IS_PRODUCTION:
            raise RuntimeError(
                "SECURITY: INITIAL_ADMIN_PASSWORD must be set when bootstrapping a production instance"
            )
        else:
            admin_password = secrets.token_urlsafe(16)
            password_source = "RANDOM (printed once below)"
            print("=" * 60)
            print(f"[KEY] GENERATED admin password (save now, will not be shown again):")
            print(f"   {admin_password}")
            print("=" * 60)
        await db.users.insert_one({
            "username": "admin",
            "name": "مدير النظام",
            "email": os.getenv("ADMIN_EMAIL", "admin@quran-center.com"),
            "role": "admin",
            "hashed_password": get_password_hash(admin_password),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow(),
        })
        print(f"[SUCCESS] Admin user provisioned (password source: {password_source})")

    # [AUDIT-2026-09-03 fix — كلمة مرور ثابتة لأقوى حساب في النظام]
    # كان الحساب الأعلى صلاحية (super_admin: يرى كل المراكز ويعطّلها) يُنشأ بكلمة المرور
    # "superadmin123" كلما لم يكن INITIAL_ADMIN_PASSWORD مضبوطاً — بما في ذلك الإنتاج، لأن
    # الحماية السابقة تفحص حساب admin فقط، فإذا كان admin موجوداً من قبل مرّ هذا السطر بلا اعتراض.
    # كذلك كان يشارك admin نفس كلمة المرور، فكسر أحدهما يكسر الآخر.
    existing_super_admin = await db.users.find_one({"username": "superadmin"})
    if not existing_super_admin:
        super_admin_pass = os.getenv("INITIAL_SUPER_ADMIN_PASSWORD")
        if not super_admin_pass:
            if IS_PRODUCTION:
                raise RuntimeError(
                    "SECURITY: INITIAL_SUPER_ADMIN_PASSWORD must be set when bootstrapping the super admin"
                )
            super_admin_pass = secrets.token_urlsafe(16)
            print("=" * 60)
            print("[KEY] GENERATED superadmin password (save now, will not be shown again):")
            print(f"   {super_admin_pass}")
            print("=" * 60)
        await db.users.insert_one({
            "username": "superadmin",
            "name": "المدير العام (الوزارة/الجمعية)",
            "email": "superadmin@quran-center.com",
            "role": "super_admin",
            "hashed_password": get_password_hash(super_admin_pass),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow(),
        })
        print("[SUCCESS] Super Admin user provisioned")

    if not SEED_DEMO_DATA:
        print("[INFO] SEED_DEMO_DATA is false — skipping demo users/centers/halaqat/students seeding")
        return

    # [AUDIT-2026-05-22 fix: demo accounts now opt-in only]
    default_users = [
        {
            "username": "manager1",
            "name": "أحمد محمد - مدير المركز",
            "email": "manager@quran-center.com",
            "role": "center_manager",
            "center_id": "center_1",
            "hashed_password": get_password_hash("manager123"),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        },
        {
            "username": "teacher1",
            "name": "الشيخ محمد علي",
            "email": "teacher@quran-center.com",
            "role": "teacher",
            "center_id": "center_1",
            "hashed_password": get_password_hash("teacher123"),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        },
        {
            "username": "student1",
            "name": "أحمد الطالب",
            "email": "student@quran-center.com",
            "role": "student",
            "center_id": "center_1",
            "hashed_password": get_password_hash("student123"),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        },
        {
            "username": "parent1",
            "name": "أبو أحمد",
            "email": "parent@quran-center.com",
            "role": "parent",
            "hashed_password": get_password_hash("parent123"),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        }
    ]
    for u in default_users:
        await db.users.update_one(
            {"username": u["username"]},
            {"$setOnInsert": u},
            upsert=True
        )
    print("[SUCCESS] Demo users ensured (SEED_DEMO_DATA=true)")

    # Seed centers if none exist
    centers_count = await db.centers.count_documents({})
    if centers_count == 0:
        # Get manager user id
        manager_user = await db.users.find_one({"username": "manager1"})
        manager_id = str(manager_user["_id"]) if manager_user else None
        
        default_centers = [
            {
                "name": "مركز النور للقرآن الكريم",
                "address": "باماكو - حي النيجر",
                "phone": "+223 70 00 00 01",
                "manager_id": manager_id,
                "manager_name": "أحمد محمد - مدير المركز",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "name": "مركز الفجر للتحفيظ",
                "address": "سيغو - وسط المدينة",
                "phone": "+223 70 00 00 02",
                "manager_id": None,
                "manager_name": "عمر خالد سعيد",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
            {
                "name": "مركز الهدى القرآني",
                "address": "موبتي - حي السوق",
                "phone": "+223 70 00 00 03",
                "manager_id": None,
                "manager_name": "محمد سعيد أحمد",
                "is_active": True,
                "created_at": datetime.utcnow()
            },
        ]
        result = await db.centers.insert_many(default_centers)
        center_ids = [str(id) for id in result.inserted_ids]
        
        # Update manager's center_id
        if manager_id and center_ids:
            await db.users.update_one(
                {"username": "manager1"},
                {"$set": {"center_id": center_ids[0]}}
            )
            await db.users.update_one(
                {"username": "teacher1"},
                {"$set": {"center_id": center_ids[0]}}
            )
            await db.users.update_one(
                {"username": "student1"},
                {"$set": {"center_id": center_ids[0]}}
            )
        
        print(f"[SUCCESS] Default centers created: {center_ids}")
        
        # Seed teachers
        default_teachers = [
            {
                "name": "الشيخ محمد علي أحمد",
                "phone": "+223 70 11 22 33",
                "center_id": center_ids[0],
                "specialization": "حفص عن عاصم",
                "is_active": True,
                "hire_date": datetime.utcnow()
            },
            {
                "name": "الشيخ عبدالله محمود",
                "phone": "+223 70 22 33 44",
                "center_id": center_ids[0],
                "specialization": "ورش عن نافع",
                "is_active": True,
                "hire_date": datetime.utcnow()
            },
            {
                "name": "الشيخ إبراهيم سعيد",
                "phone": "+223 70 33 44 55",
                "center_id": center_ids[0],
                "specialization": "حفص عن عاصم",
                "is_active": True,
                "hire_date": datetime.utcnow()
            },
        ]
        teacher_result = await db.teachers.insert_many(default_teachers)
        teacher_ids = [str(id) for id in teacher_result.inserted_ids]
        print(f"[SUCCESS] Default teachers created: {teacher_ids}")
        
        # Seed halaqat
        default_halaqat = [
            {
                "name": "حلقة الفجر",
                "teacher_id": teacher_ids[0],
                "teacher_name": "الشيخ محمد علي أحمد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة الفجر",
                "time": "06:00 - 07:30",
                "location": "القاعة الرئيسية",
                "max_students": 25,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة الضحى",
                "teacher_id": teacher_ids[1],
                "teacher_name": "الشيخ عبدالله محمود",
                "center_id": center_ids[0],
                "schedule": "يومياً ماعدا الجمعة",
                "time": "09:00 - 10:30",
                "location": "القاعة الثانية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة العصر",
                "teacher_id": teacher_ids[0],
                "teacher_name": "الشيخ محمد علي أحمد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة العصر",
                "time": "16:30 - 18:00",
                "location": "القاعة الرئيسية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة المغرب",
                "teacher_id": teacher_ids[2],
                "teacher_name": "الشيخ إبراهيم سعيد",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة المغرب",
                "time": "19:00 - 20:30",
                "location": "القاعة الثانية",
                "max_students": 20,
                "current_students": 0,
                "is_active": True,
            },
            {
                "name": "حلقة المراجعة",
                "teacher_id": teacher_ids[1],
                "teacher_name": "الشيخ عبدالله محمود",
                "center_id": center_ids[0],
                "schedule": "يومياً بعد صلاة الظهر",
                "time": "13:00 - 14:30",
                "location": "القاعة الثالثة",
                "max_students": 15,
                "current_students": 0,
                "is_active": True,
            },
        ]
        halaqah_result = await db.halaqat.insert_many(default_halaqat)
        halaqah_ids = [str(id) for id in halaqah_result.inserted_ids]
        print(f"[SUCCESS] Default halaqat created: {halaqah_ids}")
        
        # Seed students
        default_students = [
            {
                "name": "أحمد محمد علي",
                "phone": "+223 70 11 22 33",
                "parent_name": "محمد علي",
                "parent_phone": "+223 70 44 55 66",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[0],
                "halaqah_name": "حلقة الفجر",
                "memorization_plan": "plan_3_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": datetime.utcnow(),
                "progress": 17,
                "current_surah": "البقرة",
                "current_ayah": 150,
            },
            {
                "name": "عمر خالد سعيد",
                "phone": "+223 70 22 33 44",
                "parent_name": "خالد سعيد",
                "parent_phone": "+223 70 55 66 77",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[0],
                "halaqah_name": "حلقة الفجر",
                "memorization_plan": "plan_4_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": datetime.utcnow(),
                "progress": 12,
                "current_surah": "آل عمران",
                "current_ayah": 50,
            },
            {
                "name": "سعيد محمود أحمد",
                "phone": "+223 70 33 44 55",
                "parent_name": "محمود أحمد",
                "parent_phone": "+223 70 66 77 88",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[4],
                "halaqah_name": "حلقة المراجعة",
                "memorization_plan": "plan_review",
                "student_type": "reviewing",
                "is_active": True,
                "enrollment_date": datetime.utcnow(),
                "progress": 100,
                "current_surah": "الفاتحة",
                "current_ayah": 1,
            },
            {
                "name": "إبراهيم موسى عمر",
                "phone": "+223 70 44 55 66",
                "parent_name": "موسى عمر",
                "parent_phone": "+223 70 77 88 99",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[1],
                "halaqah_name": "حلقة الضحى",
                "memorization_plan": "plan_2_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": datetime.utcnow(),
                "progress": 25,
                "current_surah": "النساء",
                "current_ayah": 80,
            },
            {
                "name": "خالد أحمد علي",
                "phone": "+223 70 55 66 77",
                "parent_name": "أحمد علي",
                "parent_phone": "+223 70 88 99 00",
                "center_id": center_ids[0],
                "halaqah_id": halaqah_ids[2],
                "halaqah_name": "حلقة العصر",
                "memorization_plan": "plan_5_years",
                "student_type": "memorizing",
                "is_active": True,
                "enrollment_date": datetime.utcnow(),
                "progress": 8,
                "current_surah": "البقرة",
                "current_ayah": 50,
            },
        ]
        await db.students.insert_many(default_students)
        
        # Update halaqat student counts
        for i, halaqah_id in enumerate(halaqah_ids):
            count = await db.students.count_documents({"halaqah_id": halaqah_id, "is_active": True})
            await db.halaqat.update_one(
                {"_id": ObjectId(halaqah_id)},
                {"$set": {"current_students": count}}
            )
        
        print("[SUCCESS] Default students created")


# ==================== Auth Routes ====================

# [AUDIT-2026-05-22 fix: rate-limit state moved to MongoDB so it is correct across workers/processes]
# [AUDIT-2026-09-03 fix: القفل صار على مفتاحين — العنوان والحساب. القفل على العنوان وحده كان
#  يُتجاوَز بتدوير العناوين، وخلف وكيل واحد كان يقفل كل مستخدمي المركز دفعة واحدة.]
async def _check_attempt_key(key: str, label: str):
    now = datetime.utcnow()
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
    now = datetime.utcnow()
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


@app.post("/api/auth/login", response_model=Token)
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


# [AUDIT-2026-05-22 fix: refresh-token rotation endpoint]
class RefreshRequest(BaseModel):
    refresh_token: str


@app.post("/api/auth/refresh", response_model=Token)
async def refresh_access_token(body: RefreshRequest):
    """تجديد التوكن باستخدام refresh token (مع تدوير وإلغاء القديم)"""
    payload, user = await _decode_and_verify(body.refresh_token, expected_type="refresh")
    # Rotate: revoke the old refresh token jti
    old_jti = payload.get("jti")
    old_exp = datetime.utcfromtimestamp(payload["exp"]) if "exp" in payload else (datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
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


@app.get("/api/auth/me", response_model=UserResponse)
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


class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None


@app.post("/api/auth/logout")
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
        exp = datetime.utcfromtimestamp(payload["exp"]) if "exp" in payload else (datetime.utcnow() + timedelta(hours=1))
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
                r_exp = datetime.utcfromtimestamp(r_payload["exp"]) if "exp" in r_payload else (datetime.utcnow() + timedelta(days=REFRESH_TOKEN_EXPIRE_DAYS))
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


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/auth/change-password")
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
            "password_changed_at": datetime.utcnow(),
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


class ForgotPasswordRequest(BaseModel):
    username: str


class ResetPasswordRequest(BaseModel):
    username: str
    code: str
    new_password: str


def hash_reset_code(username: str, code: str) -> str:
    """
    [AUDIT-2026-09-03 fix] بصمة الرمز بدل تخزينه كنص صريح.
    مربوطة باسم المستخدم حتى لا يصلح رمز حساب لحساب آخر.
    """
    return hmac.new(SECRET_KEY.encode(), f"{username}:{code}".encode(), hashlib.sha256).hexdigest()


async def _check_reset_request_rate(ip: str, username: str):
    """حدّ لطلبات إعادة التعيين — بالعنوان وبالحساب معاً"""
    now = datetime.utcnow()
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


@app.post("/api/auth/forgot-password")
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
    expires_at = datetime.utcnow() + timedelta(minutes=RESET_CODE_TTL_MINUTES)

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
            "created_at": datetime.utcnow(),
        },
         "$unset": {"code": ""}},   # تنظيف أي رمز صريح قديم من قبل هذا الإصلاح
        upsert=True
    )

    # In production, this would send an SMS/Email. Here we log it server-side only.
    logger.info(f"[reset] code issued for {data.username}: {code} (expires in {RESET_CODE_TTL_MINUTES} min)")

    return {"message": "إذا كان المستخدم موجوداً، فقد تم إرسال رمز التحقق"}


@app.get("/api/auth/reset-codes")
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

    now = datetime.utcnow()
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


@app.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, request: Request):
    """إعادة تعيين كلمة المرور باستخدام الرمز المكون من 6 أرقام"""
    ip = client_ip(request)
    reset_entry = await db.password_resets.find_one({"username": data.username})
    user = await get_user_by_username(data.username)

    generic = HTTPException(status_code=400, detail="المستخدم أو الرمز غير صالح")
    if not user or not reset_entry:
        raise generic

    if datetime.utcnow() > reset_entry["expires_at"]:
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
            "password_changed_at": datetime.utcnow()
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


class AdminResetPasswordRequest(BaseModel):
    username: str
    new_password: str


@app.post("/api/auth/admin-reset-password")
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
            "password_changed_at": datetime.utcnow(),
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


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


# الأدوار التي يُحدَّد وصولها لبيانات الطلاب عبر رقم الهاتف
_PHONE_SCOPED_ROLES = {"parent", "student"}

# [إصلاح 2026-09-03] مرشِّح الحذف الناعم للتسميعات.
# "$ne": True وليس "is_deleted": False — فالسجلات القديمة لا تحمل الحقل إطلاقاً،
# وشرط المساواة بـ False كان سيُخفيها كلها.
NOT_DELETED = {"is_deleted": {"$ne": True}}


@app.put("/api/auth/profile")
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


@app.get("/api/audit-logs")
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    action: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
):
    """سجل النشاط - للمدير فقط"""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    query: dict = {}
    if current_user["role"] != "super_admin":
        user_cid = current_user.get("center_id")
        if not user_cid:
            # مدير نظام غير مرتبط بمركز: يرى الأحداث العامة (دخول/خروج/تعديل صلاحيات)
            query["center_id"] = "system"
        else:
            query["center_id"] = user_cid

    if action:
        query["action"] = action

    date_range = {}
    if from_date:
        parsed = parse_date_boundary(from_date, end=False)
        if parsed:
            date_range["$gte"] = parsed
    if to_date:
        parsed = parse_date_boundary(to_date, end=True)
        if parsed:
            date_range["$lte"] = parsed
    if date_range:
        query["timestamp"] = date_range

    total = await db.audit_logs.count_documents(query)
    logs = await db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    items = [serialize_doc(log) for log in logs]
    # [AUDIT-2026-09-03 addition: العدّاد الكلي حتى يعرف الترقيم في الواجهة أين يتوقف]
    return JSONResponse(
        content=jsonable_encoder(items),
        headers={"X-Total-Count": str(total), "Access-Control-Expose-Headers": "X-Total-Count"},
    )


@app.get("/api/audit-logs/verify")
async def verify_audit_chain(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(5000, ge=1, le=50000),
):
    """
    [AUDIT-2026-09-03 addition] التحقق الفعلي من سلامة سلسلة سجل التدقيق.

    كانت البصمات تُحسب وتُخزَّن ولا يقرؤها أحد قط — أي سلسلة بلا مدقِّق لا تحمي شيئاً.
    هذه النقطة تعيد بناء بصمة كل سجل وتقارنها بالمخزَّن وتتحقق من ترابط previous_hash،
    فتكشف أي تعديل أو حذف لسجل مالي بعد كتابته.
    """
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    entries = await db.audit_logs.find(
        {"seq": {"$ne": None}}
    ).sort("seq", 1).limit(limit).to_list(limit)

    broken_hash, broken_link, gaps = [], [], []
    previous = None
    checked = 0

    for e in entries:
        checked += 1
        expected = hashlib.sha256(audit_hash_input(e).encode()).hexdigest()
        if expected != e.get("log_hash"):
            broken_hash.append({"seq": e.get("seq"), "action": e.get("action")})
        if previous is not None:
            if e.get("seq") != previous.get("seq", 0) + 1:
                gaps.append({"after_seq": previous.get("seq"), "next_seq": e.get("seq")})
            elif e.get("previous_hash") != previous.get("log_hash"):
                broken_link.append({"seq": e.get("seq"), "action": e.get("action")})
        if e.get("chain_gap"):
            gaps.append({"marked_gap_at_seq": e.get("seq")})
        previous = e

    legacy = await db.audit_logs.count_documents({"seq": None})
    intact = not broken_hash and not broken_link and not gaps

    return {
        "intact": intact,
        "entries_checked": checked,
        "legacy_unchained_entries": legacy,
        "tampered_entries": broken_hash,
        "broken_links": broken_link,
        "sequence_gaps": gaps,
        "message": "السلسلة سليمة ولم يُعدَّل أي سجل" if intact else "تم رصد خلل في سلسلة سجل التدقيق — راجع التفاصيل",
    }


_sse_clients = {}


async def push_sse_notification(user_id: str, event_type: str, data: dict):
    """
    دفع إشعار SSE حي إلى مستخدم محدد.

    ملاحظة تشغيلية: _sse_clients ذاكرة داخل العملية الواحدة. عند تشغيل uvicorn بأكثر من worker
    لا يصل الإشعار الحي إلا لمن اتصل بنفس العامل — ولهذا يُخزَّن كل إشعار في قاعدة البيانات
    أيضاً (انظر push_notification) فلا يضيع شيء.
    """
    if user_id in _sse_clients:
        for q in _sse_clients[user_id]:
            try:
                await q.put({"event": event_type, "data": data})
            except Exception:
                pass


async def push_notification(user_id: str, event_type: str, title: str, body: str, data: dict = None) -> None:
    """
    [AUDIT-2026-09-03 addition] إشعار مُخزَّن + دفع حيّ.

    كان تنبيه غياب الطالب يُرسَل عبر SSE فقط، أي إلى وليّ أمر متصل بالتطبيق في تلك اللحظة
    بالضبط. ووليّ الأمر في الغالب ليس متصلاً وقت تسجيل الحضور صباحاً، فيضيع التنبيه إلى
    الأبد ولا أثر له في أي مكان. صار كل إشعار يُحفَظ ويمكن قراءته لاحقاً من /api/notifications.
    """
    doc = {
        "user_id": user_id,
        "type": event_type,
        "title": title,
        "body": body,
        "data": data or {},
        "read": False,
        "created_at": datetime.utcnow(),
    }
    try:
        await db.notifications.insert_one(doc)
    except Exception as e:
        logger.error(f"failed to store notification for {user_id}: {e}")
    await push_sse_notification(user_id, event_type, {"title": title, "message": body, **(data or {})})


@app.get("/api/notifications")
async def list_notifications(
    unread_only: bool = False,
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """إشعارات المستخدم الحالي فقط"""
    query: dict = {"user_id": str(current_user["_id"])}
    if unread_only:
        query["read"] = False

    rows = await db.notifications.find(query).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    unread = await db.notifications.count_documents({"user_id": str(current_user["_id"]), "read": False})
    items = []
    for n in rows:
        doc = serialize_doc(n)
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        items.append(doc)
    return {"items": items, "unread_count": unread}


@app.post("/api/notifications/{notification_id}/read")
async def mark_notification_read(notification_id: str, current_user: dict = Depends(get_current_user)):
    """تعليم إشعار كمقروء — لصاحبه وحده"""
    result = await db.notifications.update_one(
        {"_id": safe_object_id(notification_id), "user_id": str(current_user["_id"])},
        {"$set": {"read": True, "read_at": datetime.utcnow()}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="الإشعار غير موجود")
    return {"message": "تم"}


@app.post("/api/notifications/read-all")
async def mark_all_notifications_read(current_user: dict = Depends(get_current_user)):
    result = await db.notifications.update_many(
        {"user_id": str(current_user["_id"]), "read": False},
        {"$set": {"read": True, "read_at": datetime.utcnow()}},
    )
    return {"message": "تم", "updated": result.modified_count}


@app.get("/api/notifications/stream")
async def sse_notifications_stream(token: str, request: Request):
    """قناة SSE لاستلام الإشعارات الفورية"""
    try:
        payload, user = await _decode_and_verify(token, expected_type="access")
    except Exception:
        raise HTTPException(status_code=401, detail="Unauthorized")
        
    user_id = str(user["_id"])
    
    q = asyncio.Queue()
    if user_id not in _sse_clients:
        _sse_clients[user_id] = set()
    _sse_clients[user_id].add(q)
    
    async def generator():
        try:
            while True:
                if await request.is_disconnected():
                    break
                try:
                    event_data = await asyncio.wait_for(q.get(), timeout=15.0)
                    yield f"event: {event_data['event']}\ndata: {json.dumps(event_data['data'])}\n\n"
                except asyncio.TimeoutError:
                    yield ": keep-alive\n\n"
        finally:
            if user_id in _sse_clients:
                _sse_clients[user_id].discard(q)
                if not _sse_clients[user_id]:
                    del _sse_clients[user_id]
                    
    # [إصلاح 2026-09-03 — اكتُشف في مراجعة الإصلاحات نفسها]
    # استيراد asyncio أزال الانهيار، لكن القناة ظلت لا تُوصِّل شيئاً: العميل يتصل ويُسجَّل
    # ويعود 200، ولا يصل أي حدث. سببان يخنقان البثّ، كلاهما يجمّع الاستجابة قبل إرسالها:
    #   1) GZipMiddleware يضغط الجسم فيحتجزه — و Starlette يتخطّاه إن كان الرأس Content-Encoding
    #      مضبوطاً مسبقاً، فنضبطه إلى identity (أي بلا تحويل).
    #   2) nginx يضبط proxy_buffering on لكل مسارات /api، و X-Accel-Buffering: no يلغيه
    #      لهذه الاستجابة وحدها فتبقى بقية الواجهة مستفيدة من التخزين المؤقت.
    return StreamingResponse(
        generator(),
        media_type="text/event-stream",
        headers={
            "Content-Encoding": "identity",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


# ==================== Dashboard Routes ====================

async def scoped_student_ids(center_id: Optional[str], cap: int = 20000) -> List[str]:
    """معرّفات طلاب مركز واحد — تُستعمل لتحديد نطاق الجداول التي لا تحمل center_id"""
    if not center_id:
        return []
    rows = await db.students.find({"center_id": center_id}, {"_id": 1}).to_list(cap)
    return [str(r["_id"]) for r in rows]


@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """
    الحصول على إحصائيات لوحة التحكم.

    [AUDIT-2026-09-03 fix — رقمان خاطئان دائماً على الصفحة الرئيسية]
    كان نطاق المركز يُطبَّق على مجموعتَي attendance و fees عبر حقل center_id، وهما لا يحتويان
    هذا الحقل أصلاً (سجل الحضور فيه student_id و halaqah_id فقط، والرسوم فيها student_id فقط).
    فكانت النتيجة صفراً حتمياً: «نسبة الحضور 0%» و«الرسوم المعلّقة 0» لكل مدير مركز ومعلم،
    مهما بلغ عدد السجلات. النطاق الآن عبر طلاب المركز، والحقل يُكتب من الآن فصاعداً على
    السجلات الجديدة (انظر POST /api/attendance و POST /api/fees) فتصير الاستعلامات أسرع لاحقاً.
    كذلك كان التعليق يقول «آخر 30 يوماً» بينما الحساب يشمل كل التاريخ، فلا تتحرك النسبة أبداً.
    """
    role = current_user["role"]
    center_id = current_user.get("center_id")

    query_filter = {}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id

    total_students = await db.students.count_documents({**query_filter, "is_active": True})
    total_teachers = await db.teachers.count_documents({**query_filter, "is_active": True})

    # Non-super admins only count their own center
    if role == "super_admin":
        total_centers = await db.centers.count_documents({"is_active": True})
    else:
        total_centers = 1 if center_id else 0

    total_halaqat = await db.halaqat.count_documents({**query_filter, "is_active": True})

    # نطاق السجلات المرتبطة بالطلاب (حضور/رسوم)
    student_scope: dict = {}
    if role != "super_admin" and center_id:
        ids = await scoped_student_ids(center_id)
        if not ids:
            return {
                "total_students": total_students,
                "total_teachers": total_teachers,
                "total_centers": total_centers,
                "total_halaqat": total_halaqat,
                "attendance_rate": 0.0,
                "pending_fees": 0,
            }
        student_scope = {"student_id": {"$in": ids}}

    pending_fees = await db.fees.count_documents({**student_scope, "status": "pending"})

    # نسبة الحضور خلال آخر 30 يوماً فعلاً
    since = datetime.utcnow() - timedelta(days=30)
    window = {**student_scope, "date": {"$gte": since}}
    total_attendance = await db.attendance.count_documents(window)
    present_attendance = await db.attendance.count_documents({**window, "status": {"$in": ["present", "late"]}})
    attendance_rate = 0.0
    if total_attendance > 0:
        attendance_rate = round((present_attendance / total_attendance) * 100, 1)

    return {
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_centers": total_centers,
        "total_halaqat": total_halaqat,
        "attendance_rate": attendance_rate,
        "pending_fees": pending_fees,
    }


# [AUDIT-2026-09-03 refactor: كانت معادلة التقييم الذكي مكتوبة مرتين بحرفها في سجل الشرف
#  وفي الترتيب، وقد اختلفتا فعلاً في النافذة الزمنية (30 يوماً مقابل 90 يوماً باسم متغيّر
#  يقول thirty_days_ago). صارت دالة واحدة، فأي تعديل مستقبلي على المعادلة يسري على الشاشتين.]
_EVAL_SCORE_MAP = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}
_ATTENDANCE_SCORE_MAP = {"present": 100, "late": 80, "excused": 60, "absent": 0}


async def compute_student_scores(students: List[dict], days: int) -> List[dict]:
    """
    التقييم الذكي: (حفظ×0.4) + (مراجعة×0.3) + (حضور×0.2) − (أخطاء×0.1)، محصوراً بين 0 و100.

    [AUDIT-2026-09-03 perf: كان سجل الشرف يُطلق استعلامين لكل طالب — 2000 رحلة لقاعدة
     البيانات في مركز فيه ألف طالب على كل فتح للصفحة الرئيسية. صار استعلامين للكل.]
    """
    student_ids = [str(s["_id"]) for s in students]
    if not student_ids:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    rec_by_student: dict = {}
    att_by_student: dict = {}

    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": student_ids}, "date": {"$gte": since}}):
        rec_by_student.setdefault(r["student_id"], []).append(r)
    async for a in db.attendance.find({"student_id": {"$in": student_ids}, "date": {"$gte": since}}):
        att_by_student.setdefault(a["student_id"], []).append(a)

    scored = []
    for s in students:
        sid = str(s["_id"])
        h_sum = h_count = r_sum = r_count = e_sum = 0

        for rec in rec_by_student.get(sid, []):
            score = _EVAL_SCORE_MAP.get(rec.get("evaluation", "good"), 80)
            if rec.get("recitation_type") == "new":
                h_sum += score
                h_count += 1
            else:
                r_sum += score
                r_count += 1
            e_sum += rec.get("mistakes_count", 0)

        a_sum = a_count = 0
        for att in att_by_student.get(sid, []):
            a_sum += _ATTENDANCE_SCORE_MAP.get(att.get("status", "present"), 100)
            a_count += 1

        H = (h_sum / h_count) if h_count else 80    # 80 افتراضياً عند غياب البيانات
        R = (r_sum / r_count) if r_count else 80
        A = (a_sum / a_count) if a_count else 100
        final_score = max(0, min(100, (H * 0.4) + (R * 0.3) + (A * 0.2) - (e_sum * 0.1)))

        scored.append({
            "id": sid,
            "name": s.get("name"),
            "halaqah_name": s.get("halaqah_name", "غير محدد"),
            "score": round(final_score, 1),
            "progress": s.get("progress", 0),
            "has_data": bool(h_count or r_count or a_count),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored


@app.get("/api/dashboard/honor-roll")
async def get_honor_roll(current_user: dict = Depends(get_current_user)):
    """حساب التقييم الذكي وسجل الشرف (المعادلة الذكية)"""
    role = current_user["role"]
    center_id = current_user.get("center_id")

    query_filter = {"is_active": True}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id

    students = await db.students.find(query_filter).to_list(2000)
    scored = await compute_student_scores(students, days=30)
    return [{k: v for k, v in s.items() if k != "has_data"} for s in scored[:5]]


@app.get("/api/analytics/rankings")
async def get_analytics_rankings(current_user: dict = Depends(get_current_user)):
    """الحصول على الترتيب لجميع الطلاب (أفضل الطلاب والطلاب الضعفاء)"""
    role = current_user["role"]
    center_id = current_user.get("center_id")

    query_filter = {"is_active": True}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id

    students = await db.students.find(query_filter).to_list(2000)
    enrollment_by_id = {
        str(s["_id"]): (s.get("enrollment_date").isoformat() if isinstance(s.get("enrollment_date"), datetime) else None)
        for s in students
    }

    scored = await compute_student_scores(students, days=90)  # ثلاثة أشهر للترتيب
    rankings = []
    for s in scored:
        score = s["score"]
        rankings.append({
            **{k: v for k, v in s.items() if k != "has_data"},
            "category": "best" if score >= 85 else "weak" if score < 65 else "average",
            "enrollment_date": enrollment_by_id.get(s["id"]),
        })
    return rankings

@app.get("/api/analytics/student/{student_id}")
async def get_student_analytics(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على الأداء التاريخي للطالب المعين"""
    student = await check_student_access(student_id, current_user)
        
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    
    recitations = await db.recitations.find({
        **NOT_DELETED,
        "student_id": student_id,
        "date": {"$gte": six_months_ago}
    }).sort("date", 1).to_list(500)
    
    attendances = await db.attendance.find({
        "student_id": student_id,
        "date": {"$gte": six_months_ago}
    }).sort("date", 1).to_list(500)
    
    eval_map = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}
    att_map = {"present": 100, "late": 80, "excused": 60, "absent": 0}
    
    timeline = {}
    
    for r in recitations:
        d = r["date"].strftime("%Y-%m-%d") if isinstance(r["date"], datetime) else str(r["date"])[:10]
        if d not in timeline:
            timeline[d] = {"date": d, "recitation_score": None, "attendance_score": None, "mistakes": 0}
        
        score = eval_map.get(r.get("evaluation", "good"), 80)
        if timeline[d]["recitation_score"] is None:
            timeline[d]["recitation_score"] = score
        else:
            timeline[d]["recitation_score"] = (timeline[d]["recitation_score"] + score) / 2
        timeline[d]["mistakes"] += r.get("mistakes_count", 0)
        
    for a in attendances:
        d = a.get("date")
        if isinstance(d, datetime):
            d = d.strftime("%Y-%m-%d")
        elif isinstance(d, str):
            d = d[:10]
        else:
            continue
            
        if d not in timeline:
            timeline[d] = {"date": d, "recitation_score": None, "attendance_score": None, "mistakes": 0}
        
        timeline[d]["attendance_score"] = att_map.get(a.get("status", "present"), 100)
        
    timeline_list = [v for k, v in sorted(timeline.items())]
    
    return {
        # [AUDIT-2026-05-22 fix: decrypt PII before serialization]
        "student": serialize_doc(decrypt_student_doc(student)),
        "timeline": timeline_list
    }


# ==================== Centers Routes ====================

@app.get("/api/centers")
async def get_centers(current_user: dict = Depends(get_current_user)):
    """الحصول على قائمة المراكز مع إحصائيات"""
    role = current_user["role"]
    centers_query: dict = {"is_active": True}
    if role != "super_admin":
        user_center = current_user.get("center_id")
        if not user_center:
            return []
        try:
            centers_query["_id"] = safe_object_id(user_center)
        except HTTPException:
            return []
    centers = await db.centers.find(centers_query).to_list(100)
    result = []
    for c in centers:
        center_data = serialize_doc(c)
        center_id = center_data["id"]
        # Get counts
        center_data["students_count"] = await db.students.count_documents({"center_id": center_id, "is_active": True})
        center_data["teachers_count"] = await db.teachers.count_documents({"center_id": center_id, "is_active": True})
        center_data["halaqat_count"] = await db.halaqat.count_documents({"center_id": center_id, "is_active": True})
        if "created_at" not in center_data:
            center_data["created_at"] = datetime.utcnow().isoformat()
        else:
            center_data["created_at"] = center_data["created_at"].isoformat() if isinstance(center_data["created_at"], datetime) else center_data["created_at"]
        result.append(center_data)
    return result


# [AUDIT-2026-05-22 fix: per-IP throttle for unauthenticated center registration — MongoDB-backed, multi-worker safe]
REGISTER_WINDOW_MINUTES = 60
REGISTER_MAX_PER_WINDOW = 3


async def _check_register_rate(ip: str):
    now = datetime.utcnow()
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


@app.get("/api/public/best-centers")
async def get_public_best_centers():
    """عرض أفضل مراكز التحفيظ القرآنية بناءً على الأداء والجودة"""
    centers = await db.centers.find({"is_active": True}).to_list(100)
    out = []
    for c in centers:
        center_id = str(c["_id"])
        students_count = await db.students.count_documents({"center_id": center_id, "is_active": True})
        teachers_count = await db.teachers.count_documents({"center_id": center_id, "is_active": True})
        halaqat_count = await db.halaqat.count_documents({"center_id": center_id, "is_active": True})
        
        student_score = min(40, students_count * 2)
        teacher_score = min(30, teachers_count * 6)
        halaqah_score = min(30, halaqat_count * 5)
        score = int(student_score + teacher_score + halaqah_score)
        
        out.append({
            "id": center_id,
            "name": c["name"],
            "address": c["address"],
            "phone": c.get("phone") or "",
            "students_count": students_count,
            "teachers_count": teachers_count,
            "halaqat_count": halaqat_count,
            "score": score
        })
    out.sort(key=lambda x: x["score"], reverse=True)
    return out[:6]


@app.get("/api/admin/system/status")
async def get_system_status(current_user: dict = Depends(get_current_user)):
    """عرض الإحصائيات الشاملة وحالة النظام وقاعدة البيانات للمدير العام ومدير النظام"""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    db_connected = False
    try:
        await db.command("ping")
        db_connected = True
    except Exception:
        db_connected = False
        
    total_centers = await db.centers.count_documents({})
    total_students = await db.students.count_documents({})
    total_teachers = await db.teachers.count_documents({})
    total_halaqat = await db.halaqat.count_documents({})
    total_audit_logs = await db.audit_logs.count_documents({})
    
    total_logins_success = await db.audit_logs.count_documents({"action": "LOGIN_SUCCESS"})
    total_logins_failed = await db.audit_logs.count_documents({"action": "LOGIN_FAILED"})
    total_logins_disabled = await db.audit_logs.count_documents({"action": "LOGIN_DENIED_DISABLED"})
    total_login_attempts = total_logins_success + total_logins_failed + total_logins_disabled
    
    active_rate_locks = await db.login_attempts.count_documents({"locked_until": {"$gt": datetime.utcnow()}})
    total_public_registrations = await db.register_attempts.count_documents({})
    
    return {
        "db_connected": db_connected,
        "db_name": DB_NAME,
        "db_type": "MongoDB (Motor AsyncIO)",
        "total_centers": total_centers,
        "total_students": total_students,
        "total_teachers": total_teachers,
        "total_halaqat": total_halaqat,
        "total_audit_logs": total_audit_logs,
        "login_attempts": {
            "total": total_login_attempts,
            "success": total_logins_success,
            "failed": total_logins_failed + total_logins_disabled,
            "active_locks": active_rate_locks
        },
        "public_register_attempts": total_public_registrations,
        "python_version": sys.version,
        "os_platform": sys.platform
    }


@app.post("/api/public/register-center")
async def public_register_center(request: Request, center: CenterCreate):
    """تسجيل مركز جديد بشكل عام (يحتاج موافقة المدير قبل التفعيل)"""
    # [AUDIT-2026-05-22 fix: rate-limit unauthenticated registration to deter spam/DoS]
    ip = client_ip(request)
    await _check_register_rate(ip)

    if not center.manager_username or not center.manager_password:
        raise HTTPException(status_code=400, detail="يجب إدخال اسم المستخدم وكلمة المرور للمدير")
    # [AUDIT-2026-05-22 fix: enforce password complexity on the public path too]
    validate_password_complexity(center.manager_password)
    if not center.manager_email:
        raise HTTPException(status_code=400, detail="البريد الإلكتروني مطلوب للتحقق")

    existing = await db.users.find_one({"username": center.manager_username})
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")

    # [AUDIT-2026-05-22 fix: centers from the public endpoint start INACTIVE and require admin approval.
    # Manager account is also INACTIVE until approval — prevents drive-by account creation.]
    center_dict = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "manager_name": center.manager_name,
        "is_active": False,
        "approval_status": "pending",
        "status": "trial",
        "currency": center.currency or "FCFA",
        "registered_from_ip": ip,
        "created_at": datetime.utcnow(),
    }

    manager_user = {
        "username": center.manager_username,
        "name": center.manager_name or center.name + " - مدير",
        "email": center.manager_email,
        "role": "center_manager",
        "hashed_password": get_password_hash(center.manager_password),
        "is_active": False,
        "approval_status": "pending",
        "user_version": 0,
        "created_at": datetime.utcnow(),
    }
    manager_result = await db.users.insert_one(manager_user)
    center_dict["manager_id"] = str(manager_result.inserted_id)

    result = await db.centers.insert_one(center_dict)
    center_id = str(result.inserted_id)

    await db.users.update_one(
        {"_id": ObjectId(center_dict["manager_id"])},
        {"$set": {"center_id": center_id}}
    )

    await write_audit_log(
        actor_id="public",
        center_id=center_id,
        action="PUBLIC_REGISTER_CENTER",
        payload={"manager_username": center.manager_username, "center_name": center_dict["name"]},
        client_ip=ip,
    )

    return {
        "id": center_id,
        "name": center_dict["name"],
        "approval_status": "pending",
        "message": "تم استلام طلب التسجيل. سيتم التفعيل بعد مراجعة المدير."
    }


# [AUDIT-2026-05-22 fix: admin approval endpoint for pending centers]
@app.post("/api/centers/{center_id}/approve")
async def approve_center(center_id: str, current_user: dict = Depends(get_current_user)):
    """تفعيل مركز قيد المراجعة (للمدير فقط)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    center_obj_id = safe_object_id(center_id)
    center = await db.centers.find_one({"_id": center_obj_id})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    if center.get("approval_status") == "approved":
        return {"message": "المركز مُفعّل مسبقاً"}

    await db.centers.update_one(
        {"_id": center_obj_id},
        {"$set": {"is_active": True, "approval_status": "approved", "approved_at": datetime.utcnow()}}
    )
    if center.get("manager_id"):
        await db.users.update_one(
            {"_id": safe_object_id(center["manager_id"])},
            {"$set": {"is_active": True, "approval_status": "approved"}}
        )
    # [AUDIT-2026-09-03 fix: كانت قرارات اعتماد/رفض المراكز تُكتب خارج السلسلة المُبصَمة،
    #  أي قابلة للتعديل دون أن يكشفها التحقق. صارت داخلها.]
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=center_id,
        action="CENTER_APPROVED",
        payload={"approved_by": current_user["username"], "center_name": center.get("name")},
    )
    return {"message": "تم تفعيل المركز بنجاح", "center_id": center_id}


@app.post("/api/centers/{center_id}/reject")
async def reject_center(center_id: str, current_user: dict = Depends(get_current_user)):
    """رفض طلب تسجيل مركز قيد المراجعة (للمدير فقط)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    center_obj_id = safe_object_id(center_id)
    center = await db.centers.find_one({"_id": center_obj_id})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    await db.centers.update_one(
        {"_id": center_obj_id},
        {"$set": {"is_active": False, "approval_status": "rejected"}}
    )
    if center.get("manager_id"):
        await db.users.update_one(
            {"_id": safe_object_id(center["manager_id"])},
            {"$set": {"is_active": False, "approval_status": "rejected"}}
        )
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=center_id,
        action="CENTER_REJECTED",
        payload={"rejected_by": current_user["username"], "center_name": center.get("name")},
    )
    return {"message": "تم رفض الطلب", "center_id": center_id}


@app.get("/api/centers/pending")
async def list_pending_centers(current_user: dict = Depends(get_current_user)):
    """قائمة المراكز قيد الموافقة (للمدير فقط)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    pending = await db.centers.find({"approval_status": "pending"}).sort("created_at", -1).to_list(200)
    return [serialize_doc(c) for c in pending]


@app.post("/api/centers")
async def create_center(center: CenterCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء مركز جديد"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    center_dict = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "manager_name": center.manager_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    
    # Create manager account if provided
    if center.manager_username and center.manager_password:
        # [AUDIT-2026-05-22 fix: enforce password complexity even on admin-created manager accounts]
        validate_password_complexity(center.manager_password)
        existing = await db.users.find_one({"username": center.manager_username})
        if existing:
            raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")

        manager_user = {
            "username": center.manager_username,
            "name": center.manager_name or center.name + " - مدير",
            "email": center.manager_email,
            "role": "center_manager",
            "hashed_password": get_password_hash(center.manager_password),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        }
        manager_result = await db.users.insert_one(manager_user)
        center_dict["manager_id"] = str(manager_result.inserted_id)
    
    result = await db.centers.insert_one(center_dict)
    center_id = str(result.inserted_id)
    
    # Update manager's center_id
    if center_dict.get("manager_id"):
        await db.users.update_one(
            {"_id": ObjectId(center_dict["manager_id"])},
            {"$set": {"center_id": center_id}}
        )
    
    return {
        "id": center_id,
        "name": center_dict["name"],
        "address": center_dict["address"],
        "phone": center_dict["phone"],
        "manager_name": center_dict["manager_name"],
        "manager_id": center_dict.get("manager_id"),
        "is_active": center_dict["is_active"],
        "created_at": center_dict["created_at"].isoformat(),
        "students_count": 0,
        "teachers_count": 0,
        "halaqat_count": 0,
    }


@app.put("/api/centers/{center_id}")
async def update_center(center_id: str, center: CenterCreate, current_user: dict = Depends(get_current_user)):
    """تحديث مركز"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: safe object id parse + center_manager may only edit own center]
    center_obj_id = safe_object_id(center_id)
    existing = await db.centers.find_one({"_id": center_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    if current_user["role"] == "center_manager" and center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل مركز آخر")

    update_data = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "currency": center.currency or "FCFA",
    }
    if center.manager_name:
        update_data["manager_name"] = center.manager_name
    if current_user["role"] == "admin" and center.status:
        update_data["status"] = center.status

    # [AUDIT-2026-05-22 fix: use matched_count semantics — unchanged values must not 404]
    await db.centers.update_one({"_id": center_obj_id}, {"$set": update_data})

    updated = await db.centers.find_one({"_id": center_obj_id})
    return serialize_doc(updated)


@app.delete("/api/centers/{center_id}")
async def delete_center(center_id: str, current_user: dict = Depends(get_current_user)):
    """حذف مركز (تعطيل)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: safe_object_id prevents 500 on malformed ID]
    center_obj_id = safe_object_id(center_id)
    result = await db.centers.update_one(
        {"_id": center_obj_id},
        {"$set": {"is_active": False}}
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    return {"message": "تم حذف المركز بنجاح"}


@app.get("/api/centers/{center_id}/details")
async def get_center_details(center_id: str, current_user: dict = Depends(get_current_user)):
    """تفاصيل مركز واحد مع كامل البيانات"""
    # [AUDIT-2026-05-22 fix: allow center_manager to view OWN center only; safe id parse]
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    if current_user["role"] == "center_manager" and center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض مركز آخر")

    center_obj_id = safe_object_id(center_id)
    center = await db.centers.find_one({"_id": center_obj_id})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    
    center_data = serialize_doc(center)
    cid = center_data["id"]
    
    # Statistics
    students_count = await db.students.count_documents({"center_id": cid, "is_active": True})
    teachers_count = await db.teachers.count_documents({"center_id": cid, "is_active": True})
    halaqat_count = await db.halaqat.count_documents({"center_id": cid, "is_active": True})
    
    # Teachers list
    teachers = await db.teachers.find({"center_id": cid, "is_active": True}).to_list(100)
    teachers_list = []
    for t in teachers:
        doc = serialize_doc(t)
        halaqat = await db.halaqat.find({"teacher_id": doc["id"], "is_active": True}).to_list(10)
        doc["halaqat"] = [h["name"] for h in halaqat]
        doc["students_count"] = await db.students.count_documents({"halaqah_id": {"$in": [str(h["_id"]) for h in halaqat]}, "is_active": True})
        doc["hire_date"] = doc.get("hire_date", datetime.utcnow())
        if isinstance(doc["hire_date"], datetime):
            doc["hire_date"] = doc["hire_date"].isoformat()
        teachers_list.append(doc)
    
    # Registration info
    center_data["created_at"] = center_data.get("created_at", datetime.utcnow())
    if isinstance(center_data["created_at"], datetime):
        center_data["created_at"] = center_data["created_at"].isoformat()
    
    center_data["students_count"] = students_count
    center_data["teachers_count"] = teachers_count
    center_data["halaqat_count"] = halaqat_count
    center_data["teachers_list"] = teachers_list
    
    return center_data


class SuperCenterCreate(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    manager_name: str
    manager_username: str
    manager_password: str
    manager_email: str


class SuperCenterStatusUpdate(BaseModel):
    is_active: bool
    approval_status: str  # e.g., "approved", "suspended"


@app.post("/api/super/centers")
async def super_register_center(center: SuperCenterCreate, current_user: dict = Depends(get_current_user)):
    """تسجيل مركز جديد بالكامل عبر المدير العام (super_admin)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="غير مصرح - للمدير العام فقط")

    validate_password_complexity(center.manager_password)
    existing = await db.users.find_one({"username": center.manager_username})
    if existing:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")

    center_dict = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "manager_name": center.manager_name,
        "is_active": True,
        "approval_status": "approved",
        "created_at": datetime.utcnow(),
    }

    manager_user = {
        "username": center.manager_username,
        "name": center.manager_name,
        "email": center.manager_email,
        "role": "center_manager",
        "hashed_password": get_password_hash(center.manager_password),
        "is_active": True,
        "approval_status": "approved",
        "user_version": 0,
        "created_at": datetime.utcnow(),
    }
    
    manager_result = await db.users.insert_one(manager_user)
    center_dict["manager_id"] = str(manager_result.inserted_id)

    result = await db.centers.insert_one(center_dict)
    center_id = str(result.inserted_id)

    await db.users.update_one(
        {"_id": ObjectId(center_dict["manager_id"])},
        {"$set": {"center_id": center_id}}
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=center_id,
        action="SUPER_REGISTER_CENTER",
        payload={"center_name": center.name, "manager_username": center.manager_username}
    )

    return {
        "id": center_id,
        "name": center_dict["name"],
        "is_active": True,
        "approval_status": "approved"
    }


@app.post("/api/super/centers/{center_id}/status")
async def super_update_center_status(center_id: str, data: SuperCenterStatusUpdate, current_user: dict = Depends(get_current_user)):
    """تعديل حالة الاشتراك لمركز (تنشيط أو إيقاف) للمدير العام"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="غير مصرح - للمدير العام فقط")

    center_obj_id = safe_object_id(center_id)
    center = await db.centers.find_one({"_id": center_obj_id})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")

    await db.centers.update_one(
        {"_id": center_obj_id},
        {"$set": {"is_active": data.is_active, "approval_status": data.approval_status}}
    )

    user_status = data.is_active
    await db.users.update_many(
        {"center_id": center_id},
        {"$set": {"is_active": user_status}}
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=center_id,
        action="SUPER_CENTER_STATUS_CHANGE",
        payload={"is_active": data.is_active, "approval_status": data.approval_status}
    )

    return {"message": "تم تحديث حالة المركز وحسابات المستخدمين المرتبطة بنجاح"}


@app.get("/api/super/dashboard/stats")
async def super_get_global_stats(current_user: dict = Depends(get_current_user)):
    """إحصائيات إجمالية عالمية للجمعية أو الوزارة (super_admin)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="غير مصرح - للمدير العام فقط")

    total_active_centers = await db.centers.count_documents({"is_active": True})
    total_active_students = await db.students.count_documents({"is_active": True})
    
    # Financial aggregate in FCFA (الجمع داخل قاعدة البيانات — انظر _sum_amounts)
    total_fees_fcfa = await _sum_amounts(db.fees, {"status": "paid"})
    total_salaries_fcfa = await _sum_amounts(db.salaries, {})
    total_expenses_fcfa = await _sum_amounts(db.expenses, {})

    global_balance_fcfa = total_fees_fcfa - total_salaries_fcfa - total_expenses_fcfa

    return {
        "total_active_centers": total_active_centers,
        "total_active_students": total_active_students,
        "total_fees_collected_fcfa": total_fees_fcfa,
        "total_salaries_paid_fcfa": total_salaries_fcfa,
        "total_expenses_fcfa": total_expenses_fcfa,
        "global_balance_fcfa": global_balance_fcfa
    }


# ==================== Students Routes ====================

@app.get("/api/students")
async def get_students(
    center_id: Optional[str] = None,
    halaqah_id: Optional[str] = None,
    search: Optional[str] = None,
    limit: int = Query(500, ge=1, le=2000),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة الطلاب"""
    role = current_user.get("role", "student")
    if role not in ["admin", "center_manager", "teacher", "super_admin", "parent", "student"]:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    query: dict = {"is_active": True}

    # SaaS Multi-tenant & Role Isolation
    if role in ["super_admin", "admin"]:
        if center_id:
            query["center_id"] = center_id
    elif role == "parent":
        # [AUDIT-2026-09-03 fix: كانت المطابقة تشمل parent_name، وهو حقل مُشفَّر في قاعدة البيانات
        #  منذ تشفير بيانات PII — فلا يطابق النص الصريح أبداً، ووليّ أمر بلا رقم هاتف مسجَّل كان
        #  يرى قائمة فارغة دائماً بلا سبب ظاهر. المطابقة الآن برقم هاتف وليّ الأمر فقط،
        #  وهو حقل غير مشفَّر ولم يعد قابلاً للتعديل الذاتي (انظر PUT /api/auth/profile).]
        parent_phone = current_user.get("phone")
        if not parent_phone:
            return []
        query["parent_phone"] = parent_phone
    elif role == "student":
        # [AUDIT-2026-09-03 fix: كانت المطابقة بالاسم، والاسم يعدّله الطالب بنفسه]
        conditions = [{"user_id": str(current_user["_id"])}]
        if current_user.get("phone"):
            conditions.append({"phone": current_user["phone"]})
        query["$or"] = conditions
    else:
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]

    if halaqah_id:
        # فلترة الحلقة تُطبَّق فوق نطاق الدور، فلا تُوسِّعه
        query["halaqah_id"] = halaqah_id

    if search:
        # [AUDIT-2026-09-03 fix: يجب تهريب رموز الـ regex وإلا صار البحث تعبيراً نمطياً
        #  يتحكم به المستخدم (استنزاف للمعالج بـ ReDoS)]
        safe = re.escape(search.strip())
        if safe:
            query["name"] = {"$regex": safe, "$options": "i"}

    students = await db.students.find(query).skip(skip).limit(limit).to_list(limit)
    result = []
    for s in students:
        # [AUDIT-2026-05-22 fix: decrypt PII before serialization]
        doc = serialize_doc(decrypt_student_doc(s))
        doc["enrollment_date"] = doc.get("enrollment_date", datetime.utcnow())
        if isinstance(doc["enrollment_date"], datetime):
            doc["enrollment_date"] = doc["enrollment_date"].isoformat()
        result.append(doc)
    return result


@app.get("/api/students/{student_id}")
async def get_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """
    [AUDIT-2026-09-03 addition] جلب طالب واحد — كانت الواجهة تستدعيها (studentsApi.getById)
    ولا وجود لها في الخادم، فتُرجع 404 دائماً. تمرّ عبر نفس فحص الملكية.
    """
    student = await check_student_access(student_id, current_user)
    doc = serialize_doc(decrypt_student_doc(student))
    if isinstance(doc.get("enrollment_date"), datetime):
        doc["enrollment_date"] = doc["enrollment_date"].isoformat()
    return doc


@app.post("/api/students")
async def create_student(student: StudentCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء طالب جديد"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center isolation]
    if current_user["role"] != "admin" and student.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء طالب في مركز آخر")
    
    student_dict = student.model_dump()
    enrollment_date = datetime.utcnow()
    student_dict["enrollment_date"] = enrollment_date
    student_dict["progress"] = 0
    student_dict["current_surah"] = None
    student_dict["current_ayah"] = None

    # [AUDIT-2026-05-22 fix: encrypt PII fields before storing]
    persisted = encrypt_student_doc(student_dict)
    result = await db.students.insert_one(persisted)
    
    # Update halaqah student count
    if student.halaqah_id:
        try:
            # [AUDIT-2026-05-22 fix: safe object id parse]
            halaqah_obj_id = safe_object_id(student.halaqah_id)
            count = await db.students.count_documents({"halaqah_id": student.halaqah_id, "is_active": True})
            await db.halaqat.update_one(
                {"_id": halaqah_obj_id},
                {"$set": {"current_students": count}}
            )
        except Exception:
            pass
    
    return {
        "id": str(result.inserted_id),
        "name": student_dict["name"],
        "date_of_birth": student_dict.get("date_of_birth"),
        "phone": student_dict.get("phone"),
        "parent_name": student_dict.get("parent_name"),
        "parent_phone": student_dict.get("parent_phone"),
        "center_id": student_dict["center_id"],
        "halaqah_id": student_dict.get("halaqah_id"),
        "halaqah_name": student_dict.get("halaqah_name"),
        "memorization_plan": student_dict.get("memorization_plan"),
        "student_type": student_dict["student_type"],
        "is_active": student_dict["is_active"],
        "enrollment_date": enrollment_date.isoformat(),
        "progress": student_dict["progress"],
        "current_surah": student_dict["current_surah"],
        "current_ayah": student_dict["current_ayah"]
    }


@app.put("/api/students/{student_id}")
async def update_student(student_id: str, student: StudentUpdate, current_user: dict = Depends(get_current_user)):
    """تحديث طالب"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    student_obj_id = safe_object_id(student_id)
    existing_student = await db.students.find_one({"_id": student_obj_id})
    if not existing_student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
    if current_user["role"] != "admin" and existing_student.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل بيانات هذا الطالب")
        
    update_data = {k: v for k, v in student.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")

    # [AUDIT-2026-05-22 fix: encrypt PII fields on update]
    result = await db.students.update_one(
        {"_id": student_obj_id},
        {"$set": encrypt_student_doc(update_data)}
    )

    updated = await db.students.find_one({"_id": student_obj_id})
    # [AUDIT-2026-05-22 fix: decrypt PII for the response]
    doc = serialize_doc(decrypt_student_doc(updated))
    doc["enrollment_date"] = doc.get("enrollment_date", datetime.utcnow())
    if isinstance(doc["enrollment_date"], datetime):
        doc["enrollment_date"] = doc["enrollment_date"].isoformat()
    return doc


@app.delete("/api/students/{student_id}")
async def delete_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """حذف طالب (تعطيل)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    student_obj_id = safe_object_id(student_id)
    student = await db.students.find_one({"_id": student_obj_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
    if current_user["role"] != "admin" and student.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف هذا الطالب")
    
    await db.students.update_one(
        {"_id": student_obj_id},
        {"$set": {"is_active": False}}
    )
    
    # Update halaqah count
    if student.get("halaqah_id"):
        try:
            # [AUDIT-2026-05-22 fix: safe object id parse]
            halaqah_obj_id = safe_object_id(student["halaqah_id"])
            count = await db.students.count_documents({"halaqah_id": student["halaqah_id"], "is_active": True})
            await db.halaqat.update_one(
                {"_id": halaqah_obj_id},
                {"$set": {"current_students": count}}
            )
        except Exception:
            pass
    
    return {"message": "تم حذف الطالب بنجاح"}


# ==================== Teachers Routes ====================

@app.get("/api/teachers")
async def get_teachers(
    center_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=1000),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة المعلمين"""
    # [AUDIT-2026-05-22 fix: gate by role + close fallthrough that exposed all teachers]
    role = current_user.get("role")
    if role not in ["admin", "center_manager", "teacher", "super_admin", "parent", "student"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query = {"is_active": True}

    # SaaS Multi-tenant Isolation
    if role in ["super_admin", "admin"]:
        if center_id:
            query["center_id"] = center_id
    else:
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]

    teachers = await db.teachers.find(query).skip(skip).limit(limit).to_list(limit)

    # [AUDIT-2026-09-03 perf: كانت حلقتان لكل معلم (N+1). صارت استعلامين لكل الصفحة.]
    teacher_ids = [str(t["_id"]) for t in teachers]
    halaqat_by_teacher: dict = {tid: [] for tid in teacher_ids}
    all_halaqah_ids: List[str] = []
    if teacher_ids:
        async for h in db.halaqat.find({"teacher_id": {"$in": teacher_ids}, "is_active": True}):
            halaqat_by_teacher.setdefault(h["teacher_id"], []).append(h)
            all_halaqah_ids.append(str(h["_id"]))

    students_per_halaqah: dict = {}
    if all_halaqah_ids:
        pipeline = [
            {"$match": {"halaqah_id": {"$in": all_halaqah_ids}, "is_active": True}},
            {"$group": {"_id": "$halaqah_id", "n": {"$sum": 1}}},
        ]
        async for row in db.students.aggregate(pipeline):
            students_per_halaqah[row["_id"]] = row["n"]

    result = []
    for t in teachers:
        doc = redact_teacher(serialize_doc(t), role)
        mine = halaqat_by_teacher.get(doc["id"], [])
        doc["halaqat"] = [h["name"] for h in mine]
        doc["students_count"] = sum(students_per_halaqah.get(str(h["_id"]), 0) for h in mine)
        doc["hire_date"] = doc.get("hire_date", datetime.utcnow())
        if isinstance(doc["hire_date"], datetime):
            doc["hire_date"] = doc["hire_date"].isoformat()
        result.append(doc)
    return result


@app.post("/api/teachers")
async def create_teacher(teacher: TeacherCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء معلم جديد"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center-level isolation]
    if current_user["role"] != "admin" and teacher.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء معلم في مركز آخر")
    
    # [AUDIT-2026-09-03 fix: كان الراتب والحالة الاجتماعية ونظام الدوام تُرسل من الواجهة
    #  وتُهمَل بصمت عند الإنشاء — يُدخل مدير المركز راتب المعلم فيختفي دون رسالة خطأ،
    #  ولا يظهر إلا بعد تعديل لاحق. الآن تُحفظ عند الإنشاء.]
    teacher_dict = {
        "name": teacher.name,
        "phone": teacher.phone,
        "center_id": teacher.center_id,
        "specialization": teacher.specialization,
        "marital_status": teacher.marital_status,
        "work_schedule": teacher.work_schedule,
        "salary": teacher.salary,
        "is_active": True,
        "hire_date": datetime.utcnow(),
    }
    hire_date = teacher_dict["hire_date"]
    
    # Create user account if credentials provided
    user_id = None
    if teacher.username and teacher.password:
        # [AUDIT-2026-05-22 fix: enforce password complexity on teacher account creation]
        validate_password_complexity(teacher.password)
        existing = await db.users.find_one({"username": teacher.username})
        if existing:
            raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")

        user_data = {
            "username": teacher.username,
            "name": teacher.name,
            "role": "teacher",
            "center_id": teacher.center_id,
            "hashed_password": get_password_hash(teacher.password),
            "is_active": True,
            "user_version": 0,
            "created_at": datetime.utcnow()
        }
        user_result = await db.users.insert_one(user_data)
        user_id = str(user_result.inserted_id)
        teacher_dict["user_id"] = user_id
    
    result = await db.teachers.insert_one(teacher_dict)
    
    return {
        "id": str(result.inserted_id),
        "name": teacher_dict["name"],
        "phone": teacher_dict.get("phone"),
        "center_id": teacher_dict["center_id"],
        "specialization": teacher_dict.get("specialization"),
        "marital_status": teacher_dict.get("marital_status"),
        "work_schedule": teacher_dict.get("work_schedule"),
        "salary": teacher_dict.get("salary"),
        "is_active": teacher_dict["is_active"],
        "hire_date": hire_date.isoformat(),
        "user_id": teacher_dict.get("user_id"),
        "halaqat": [],
        "students_count": 0
    }


@app.put("/api/teachers/{teacher_id}")
async def update_teacher(teacher_id: str, teacher: TeacherUpdate, current_user: dict = Depends(get_current_user)):
    """تحديث معلم"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    teacher_obj_id = safe_object_id(teacher_id)
    existing = await db.teachers.find_one({"_id": teacher_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
    if current_user["role"] != "admin" and existing.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتحديث بيانات هذا المعلم")
    
    update_data = {k: v for k, v in teacher.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
    
    await db.teachers.update_one(
        {"_id": teacher_obj_id},
        {"$set": update_data}
    )
    
    updated = await db.teachers.find_one({"_id": teacher_obj_id})
    return serialize_doc(updated)


@app.post("/api/teachers/{teacher_id}/transfer")
async def transfer_teacher(teacher_id: str, data: TeacherTransferRequest, current_user: dict = Depends(get_current_user)):
    """نقل محفظ من حلقة إلى حلقة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    teacher_obj_id = safe_object_id(teacher_id)
    from_halaqah_obj_id = safe_object_id(data.from_halaqah_id)
    to_halaqah_obj_id = safe_object_id(data.to_halaqah_id)
    
    teacher = await db.teachers.find_one({"_id": teacher_obj_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
    if current_user["role"] != "admin" and teacher.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لمعلومات هذا المعلم")
        
    from_halaqah = await db.halaqat.find_one({"_id": from_halaqah_obj_id})
    to_halaqah = await db.halaqat.find_one({"_id": to_halaqah_obj_id})
    if not from_halaqah or not to_halaqah:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")
        
    if current_user["role"] != "admin" and (
        from_halaqah.get("center_id") != current_user.get("center_id") or 
        to_halaqah.get("center_id") != current_user.get("center_id")
    ):
        raise HTTPException(status_code=403, detail="غير مصرح لك بالتعامل مع حلقات في مركز آخر")
    
    # [AUDIT-2026-09-03 fix: كان الشرط غائباً فيُجرَّد المعلّم من الحلقة المصدر حتى لو لم يكن
    #  معلّمها أصلاً — يكفي خطأ في اختيار الحلقة ليصبح لدى المركز حلقة بلا محفّظ بلا إشعار.]
    if from_halaqah.get("teacher_id") != teacher_id:
        raise HTTPException(status_code=400, detail="هذا المحفظ ليس معلّم الحلقة المصدر")
    if data.from_halaqah_id == data.to_halaqah_id:
        raise HTTPException(status_code=400, detail="الحلقة المصدر والوجهة متطابقتان")

    await db.halaqat.update_one(
        {"_id": from_halaqah_obj_id},
        {"$unset": {"teacher_id": "", "teacher_name": ""}}
    )

    await db.halaqat.update_one(
        {"_id": to_halaqah_obj_id},
        {"$set": {"teacher_id": teacher_id, "teacher_name": teacher["name"]}}
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=teacher.get("center_id", "system"),
        action="TEACHER_TRANSFERRED",
        payload={
            "teacher_id": teacher_id,
            "teacher_name": teacher.get("name"),
            "from_halaqah": from_halaqah.get("name"),
            "to_halaqah": to_halaqah.get("name"),
        },
    )
    return {"message": f"تم نقل المحفظ {teacher['name']} إلى {to_halaqah['name']} بنجاح"}


@app.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: str, current_user: dict = Depends(get_current_user)):
    """حذف معلم (تعطيل)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    teacher_obj_id = safe_object_id(teacher_id)
    teacher = await db.teachers.find_one({"_id": teacher_obj_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
    if current_user["role"] != "admin" and teacher.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف محفظ في مركز آخر")
    
    await db.teachers.update_one(
        {"_id": teacher_obj_id},
        {"$set": {"is_active": False}}
    )
    return {"message": "تم حذف المعلم بنجاح"}


# ==================== Teacher Evaluations Routes ====================

@app.post("/api/teachers/{teacher_id}/evaluations", response_model=TeacherEvaluationResponse)
async def create_teacher_evaluation(
    teacher_id: str,
    evaluation: TeacherEvaluationCreate,
    current_user: dict = Depends(get_current_user)
):
    """إرسال تقييم دوري جديد للمعلم"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    teacher_obj_id = safe_object_id(teacher_id)
    teacher = await db.teachers.find_one({"_id": teacher_obj_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
    center_id = current_user.get("center_id")
    if current_user["role"] not in ["admin", "super_admin"] and teacher.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتقييم محفظ في مركز آخر")
    
    if not center_id:
        center_id = teacher.get("center_id") or "default"
        
    att_part = evaluation.attendance_rate * 0.2
    taj_part = evaluation.tajweed_proficiency * 10 * 0.3
    ret_part = evaluation.student_retention * 10 * 0.2
    speed_part = min(100.0, evaluation.average_memorization_speed * 15.0) * 0.15
    disc_part = evaluation.discipline * 10 * 0.15
    
    tpi = round(att_part + taj_part + ret_part + speed_part + disc_part, 2)
    
    eval_dict = evaluation.model_dump()
    eval_dict["center_id"] = center_id
    eval_dict["tpi"] = tpi
    eval_dict["created_at"] = datetime.utcnow()
    
    result = await db.teacher_evaluations.insert_one(eval_dict)
    
    return {
        **eval_dict,
        "id": str(result.inserted_id),
        "teacher_name": teacher.get("name"),
        "created_at": eval_dict["created_at"]
    }


@app.get("/api/teachers/{teacher_id}/evaluations", response_model=List[TeacherEvaluationResponse])
async def get_teacher_evaluations(
    teacher_id: str,
    current_user: dict = Depends(get_current_user)
):
    """عرض سجل التقييمات الخاص بالمعلم"""
    teacher_obj_id = safe_object_id(teacher_id)
    teacher = await db.teachers.find_one({"_id": teacher_obj_id})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
        
    role = current_user["role"]
    center_id = current_user.get("center_id")
    if role not in ["admin", "super_admin"] and teacher.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض تقييمات محفظ في مركز آخر")
        
    query = {"teacher_id": teacher_id}
    if role != "super_admin":
        query["center_id"] = center_id or teacher.get("center_id")
        
    evals = await db.teacher_evaluations.find(query).sort("created_at", -1).to_list(100)
    result = []
    for ev in evals:
        item = serialize_doc(ev)
        item["teacher_name"] = teacher.get("name")
        result.append(item)
        
    return result


# ==================== Halaqat Routes ====================

@app.get("/api/halaqat")
async def get_halaqat(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة الحلقات"""
    # [AUDIT-2026-05-22 fix: gate by role + close fallthrough that exposed all halaqat]
    role = current_user.get("role")
    if role not in ["admin", "center_manager", "teacher", "super_admin", "parent", "student"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query = {"is_active": True}

    # SaaS Multi-tenant Isolation
    if role in ["super_admin", "admin"]:
        if center_id:
            query["center_id"] = center_id
    else:
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]

    halaqat = await db.halaqat.find(query).to_list(100)
    result = []
    for h in halaqat:
        doc = serialize_doc(h)
        # Recalculate current students
        doc["current_students"] = await db.students.count_documents(
            {"halaqah_id": doc["id"], "is_active": True}
        )
        result.append(doc)
    return result


@app.post("/api/halaqat")
async def create_halaqah(halaqah: HalaqahCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء حلقة جديدة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center-level isolation]
    if current_user["role"] != "admin" and halaqah.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء حلقة في مركز آخر")
    
    halaqah_dict = halaqah.model_dump()
    halaqah_dict["current_students"] = 0
    result = await db.halaqat.insert_one(halaqah_dict)
    
    return {
        "id": str(result.inserted_id),
        "name": halaqah_dict["name"],
        "teacher_id": halaqah_dict.get("teacher_id"),
        "teacher_name": halaqah_dict.get("teacher_name"),
        "center_id": halaqah_dict["center_id"],
        "schedule": halaqah_dict["schedule"],
        "time": halaqah_dict.get("time"),
        "location": halaqah_dict.get("location"),
        "max_students": halaqah_dict["max_students"],
        "is_active": halaqah_dict["is_active"],
        "current_students": halaqah_dict["current_students"]
    }


@app.put("/api/halaqat/{halaqah_id}")
async def update_halaqah(halaqah_id: str, halaqah: HalaqahUpdate, current_user: dict = Depends(get_current_user)):
    """تحديث حلقة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    halaqah_obj_id = safe_object_id(halaqah_id)
    existing = await db.halaqat.find_one({"_id": halaqah_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")
        
    if current_user["role"] != "admin" and existing.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتحديث حلقة في مركز آخر")
    
    update_data = {k: v for k, v in halaqah.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
    
    await db.halaqat.update_one(
        {"_id": halaqah_obj_id},
        {"$set": update_data}
    )
    
    updated = await db.halaqat.find_one({"_id": halaqah_obj_id})
    return serialize_doc(updated)


@app.delete("/api/halaqat/{halaqah_id}")
async def delete_halaqah(halaqah_id: str, current_user: dict = Depends(get_current_user)):
    """حذف حلقة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    halaqah_obj_id = safe_object_id(halaqah_id)
    existing = await db.halaqat.find_one({"_id": halaqah_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")
        
    if current_user["role"] != "admin" and existing.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف حلقة في مركز آخر")
    
    await db.halaqat.update_one(
        {"_id": halaqah_obj_id},
        {"$set": {"is_active": False}}
    )
    return {"message": "تم حذف الحلقة بنجاح"}


# ==================== Academic Schedules Routes ====================

@app.post("/api/academic-schedules", response_model=AcademicScheduleResponse)
async def create_academic_schedule(schedule: AcademicScheduleCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء موعد دراسي أكاديمي جديد"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    center_id = current_user.get("center_id")
    if current_user["role"] in ["admin", "super_admin"] and not center_id:
        center_id = schedule.center_id or "default"
        
    if not center_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المركز")

    schedule_dict = schedule.model_dump()
    schedule_dict["center_id"] = center_id
    schedule_dict["created_at"] = datetime.utcnow()
    
    teacher_name = None
    teacher = await db.teachers.find_one({"_id": safe_object_id(schedule.teacher_id)})
    if teacher:
        teacher_name = teacher.get("name")
        
    halaqa_name = None
    halaqa = await db.halaqat.find_one({"_id": safe_object_id(schedule.halaqa_id)})
    if halaqa:
        halaqa_name = halaqa.get("name")
        
    result = await db.academic_schedules.insert_one(schedule_dict)
    
    return {
        **schedule_dict,
        "id": str(result.inserted_id),
        "center_id": center_id,
        "teacher_name": teacher_name,
        "halaqa_name": halaqa_name
    }


@app.get("/api/academic-schedules", response_model=List[AcademicScheduleResponse])
async def get_academic_schedules(current_user: dict = Depends(get_current_user)):
    """الحصول على الجدول الدراسي الأكاديمي للمركز"""
    role = current_user["role"]
    query = {}
    if role != "super_admin":
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query["center_id"] = center_id
        
    schedules = await db.academic_schedules.find(query).to_list(1000)
    result = []
    
    teacher_ids = list(set([s.get("teacher_id") for s in schedules if s.get("teacher_id")]))
    halaqa_ids = list(set([s.get("halaqa_id") for s in schedules if s.get("halaqa_id")]))
    
    teachers_map = {}
    if teacher_ids:
        teachers_cursor = db.teachers.find({"_id": {"$in": [safe_object_id(tid) for tid in teacher_ids]}})
        async for t in teachers_cursor:
            teachers_map[str(t["_id"])] = t.get("name")
            
    halaqat_map = {}
    if halaqa_ids:
        halaqat_cursor = db.halaqat.find({"_id": {"$in": [safe_object_id(hid) for hid in halaqa_ids]}})
        async for h in halaqat_cursor:
            halaqat_map[str(h["_id"])] = h.get("name")
            
    for s in schedules:
        item = serialize_doc(s)
        item["teacher_name"] = teachers_map.get(s.get("teacher_id"), "معلم غير معروف")
        item["halaqa_name"] = halaqat_map.get(s.get("halaqa_id"), "حلقة غير معروفة")
        result.append(item)
        
    return result


@app.put("/api/academic-schedules/{schedule_id}", response_model=AcademicScheduleResponse)
async def update_academic_schedule(schedule_id: str, schedule: AcademicScheduleCreate, current_user: dict = Depends(get_current_user)):
    """تحديث موعد دراسي أكاديمي"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    schedule_obj_id = safe_object_id(schedule_id)
    existing = await db.academic_schedules.find_one({"_id": schedule_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="الموعد الدراسي غير موجود")
        
    if current_user["role"] not in ["admin", "super_admin"] and existing.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل موعد دراسي لمركز آخر")
        
    # [AUDIT-2026-09-03 fix: لا يُسمح بنقل موعد إلى مركز آخر عبر التعديل — المركز يبقى كما هو]
    update_dict = schedule.model_dump(exclude={"center_id"})
    await db.academic_schedules.update_one({"_id": schedule_obj_id}, {"$set": update_dict})
    
    teacher_name = None
    teacher = await db.teachers.find_one({"_id": safe_object_id(schedule.teacher_id)})
    if teacher:
        teacher_name = teacher.get("name")
        
    halaqa_name = None
    halaqa = await db.halaqat.find_one({"_id": safe_object_id(schedule.halaqa_id)})
    if halaqa:
        halaqa_name = halaqa.get("name")
        
    return {
        **update_dict,
        "id": schedule_id,
        "center_id": existing["center_id"],
        "teacher_name": teacher_name,
        "halaqa_name": halaqa_name
    }


@app.delete("/api/academic-schedules/{schedule_id}")
async def delete_academic_schedule(schedule_id: str, current_user: dict = Depends(get_current_user)):
    """حذف موعد دراسي أكاديمي"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    schedule_obj_id = safe_object_id(schedule_id)
    existing = await db.academic_schedules.find_one({"_id": schedule_obj_id})
    if not existing:
        raise HTTPException(status_code=404, detail="الموعد الدراسي غير موجود")
        
    if current_user["role"] not in ["admin", "super_admin"] and existing.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف موعد دراسي لمركز آخر")
        
    await db.academic_schedules.delete_one({"_id": schedule_obj_id})
    return {"message": "تم حذف الموعد الدراسي بنجاح"}


# ==================== Quran Competitions Routes ====================

@app.post("/api/competitions", response_model=CompetitionResponse)
async def create_competition(comp: CompetitionCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء مسابقة قرآنية سنوية جديدة"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    center_id = current_user.get("center_id")
    if not center_id:
        raise HTTPException(status_code=400, detail="يجب ربط حسابك بمركز تحفيظ معتمد")
        
    comp_dict = comp.model_dump()
    comp_dict["center_id"] = center_id
    comp_dict["created_at"] = datetime.utcnow()
    
    result = await db.competitions.insert_one(comp_dict)
    
    return {
        **comp_dict,
        "id": str(result.inserted_id)
    }


@app.get("/api/competitions", response_model=List[CompetitionResponse])
async def get_competitions(current_user: dict = Depends(get_current_user)):
    """عرض قائمة المسابقات القرآنية في المركز"""
    role = current_user["role"]
    query = {}
    if role != "super_admin":
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query["center_id"] = center_id
        
    comps = await db.competitions.find(query).sort("created_at", -1).to_list(100)
    return [serialize_doc(c) for c in comps]


@app.post("/api/competitions/{comp_id}/register", response_model=CompetitionContestantResponse)
async def register_contestant(
    comp_id: str,
    contestant: CompetitionContestantCreate,
    current_user: dict = Depends(get_current_user)
):
    """تسجيل طالب كمتسابق في مسابقة قرآنية"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    comp_obj_id = safe_object_id(comp_id)
    comp = await db.competitions.find_one({"_id": comp_obj_id})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة القرآنية غير موجودة")
        
    student_obj_id = safe_object_id(contestant.student_id)
    student = await db.students.find_one({"_id": student_obj_id})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
    center_id = current_user.get("center_id")
    if current_user["role"] not in ["admin", "super_admin"] and student.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتسجيل طالب من مركز آخر")
        
    existing = await db.competition_contestants.find_one({
        "competition_id": comp_id,
        "student_id": contestant.student_id
    })
    if existing:
        raise HTTPException(status_code=400, detail="الطالب مسجل بالفعل في هذه المسابقة")
        
    con_dict = contestant.model_dump()
    con_dict["competition_id"] = comp_id
    con_dict["center_id"] = center_id or student.get("center_id")
    con_dict["grades"] = None
    con_dict["total_score"] = 0.0
    con_dict["created_at"] = datetime.utcnow()
    
    result = await db.competition_contestants.insert_one(con_dict)
    
    return {
        **con_dict,
        "id": str(result.inserted_id),
        "student_name": student.get("name")
    }


@app.get("/api/competitions/{comp_id}/contestants", response_model=List[CompetitionContestantResponse])
async def get_contestants(comp_id: str, current_user: dict = Depends(get_current_user)):
    """عرض المتسابقين المسجلين في المسابقة القرآنية مع درجاتهم"""
    comp_obj_id = safe_object_id(comp_id)
    comp = await db.competitions.find_one({"_id": comp_obj_id})
    if not comp:
        raise HTTPException(status_code=404, detail="المسابقة القرآنية غير موجودة")
        
    role = current_user["role"]
    center_id = current_user.get("center_id")
    if role not in ["admin", "super_admin"] and comp.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بعرض متسابقي مركز آخر")
        
    query = {"competition_id": comp_id}
    contestants = await db.competition_contestants.find(query).sort("total_score", -1).to_list(200)
    
    student_ids = list(set([c.get("student_id") for c in contestants]))
    students_map = {}
    if student_ids:
        students_cursor = db.students.find({"_id": {"$in": [safe_object_id(sid) for sid in student_ids]}})
        async for s in students_cursor:
            students_map[str(s["_id"])] = s.get("name")
            
    result = []
    for c in contestants:
        item = serialize_doc(c)
        item["student_name"] = students_map.get(c.get("student_id"), "طالب غير معروف")
        result.append(item)
        
    return result


@app.post("/api/competitions/contestants/{contestant_id}/grade", response_model=CompetitionContestantResponse)
async def grade_contestant(
    contestant_id: str,
    grades: ContestantGrades,
    current_user: dict = Depends(get_current_user)
):
    """رصد وتقييم درجات المتسابق في المسابقة القرآنية"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    con_obj_id = safe_object_id(contestant_id)
    contestant = await db.competition_contestants.find_one({"_id": con_obj_id})
    if not contestant:
        raise HTTPException(status_code=404, detail="المتسابق غير موجود")
        
    center_id = current_user.get("center_id")
    if current_user["role"] not in ["admin", "super_admin"] and contestant.get("center_id") != center_id:
        raise HTTPException(status_code=403, detail="غير مصرح لك بتقييم متسابق لمركز آخر")
        
    if grades.hifdh_score > 70 or grades.hifdh_score < 0:
        raise HTTPException(status_code=400, detail="درجة الحفظ يجب أن تكون بين 0 و 70")
    if grades.tajweed_score > 20 or grades.tajweed_score < 0:
        raise HTTPException(status_code=400, detail="درجة أحكام التجويد يجب أن تكون بين 0 و 20")
    if grades.voice_score > 10 or grades.voice_score < 0:
        raise HTTPException(status_code=400, detail="درجة حسن الصوت والأداء يجب أن تكون بين 0 و 10")
        
    total = round(grades.hifdh_score + grades.tajweed_score + grades.voice_score, 2)
    
    await db.competition_contestants.update_one(
        {"_id": con_obj_id},
        {"$set": {"grades": grades.model_dump(), "total_score": total}}
    )
    
    updated = await db.competition_contestants.find_one({"_id": con_obj_id})
    student = await db.students.find_one({"_id": safe_object_id(updated.get("student_id"))})
    
    return {
        **serialize_doc(updated),
        "student_name": student.get("name") if student else "طالب غير معروف"
    }


# ==================== Bulk Messaging Routes ====================

class ReplyPayload(BaseModel):
    content: str


@app.post("/api/messages/broadcast", response_model=BulkMessageResponse)
async def create_broadcast_message(msg: BulkMessageCreate, current_user: dict = Depends(get_current_user)):
    """إرسال رسالة جماعية (بث) جديدة للمعلمين أو مدراء المراكز"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    center_id = current_user.get("center_id")
    if not center_id:
        if current_user["role"] == "super_admin":
            center_id = "global"
        else:
            raise HTTPException(status_code=400, detail="يجب ربط حسابك بمركز معتمد")
        
    msg_dict = msg.model_dump()
    msg_dict["center_id"] = center_id
    msg_dict["sender_id"] = str(current_user["_id"])
    msg_dict["sender_name"] = current_user.get("name") or current_user.get("username")
    msg_dict["sent_at"] = datetime.utcnow()
    msg_dict["replies"] = []
    
    result = await db.bulk_messages.insert_one(msg_dict)
    
    return {
        **msg_dict,
        "id": str(result.inserted_id)
    }


@app.get("/api/messages/inbox", response_model=List[BulkMessageResponse])
async def get_received_broadcasts(current_user: dict = Depends(get_current_user)):
    """عرض الرسائل الجماعية الواردة للمعلم أو مدير المركز"""
    role = current_user["role"]
    center_id = current_user.get("center_id")
    
    if role == "center_manager":
        # مدير المركز يستقبل الرسائل المرسلة له من الإشراف العام (Super Admin)
        query = {
            "$or": [
                {"center_id": center_id, "recipient_role": "center_manager"},
                {"center_id": "global", "recipient_role": "center_manager"}
            ]
        }
    else:
        if not center_id:
            return []
        query = {"center_id": center_id}
        if role == "teacher":
            query["recipient_role"] = "all_teachers"
        else:
            query["recipient_role"] = role
        
    messages = await db.bulk_messages.find(query).sort("sent_at", -1).to_list(100)
    return [serialize_doc(m) for m in messages]


@app.post("/api/messages/{message_id}/reply", response_model=BulkMessageResponse)
async def reply_to_broadcast(
    message_id: str,
    payload: ReplyPayload,
    current_user: dict = Depends(get_current_user)
):
    """الرد على رسالة جماعية واردة"""
    if current_user["role"] not in ["teacher", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح - للرد يجب أن تكون معلماً أو مديراً")
        
    msg_obj_id = safe_object_id(message_id)
    message = await db.bulk_messages.find_one({"_id": msg_obj_id})
    if not message:
        raise HTTPException(status_code=404, detail="الرسالة غير موجودة")
        
    if message.get("center_id") != "global" and message.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    reply = {
        "teacher_id": str(current_user["_id"]),
        "teacher_name": current_user.get("name") or current_user.get("username") or "مدير مركز",
        "content": payload.content,
        "timestamp": datetime.utcnow()
    }
    
    await db.bulk_messages.update_one(
        {"_id": msg_obj_id},
        {"$push": {"replies": reply}}
    )
    
    updated = await db.bulk_messages.find_one({"_id": msg_obj_id})
    return serialize_doc(updated)


@app.get("/api/messages/broadcasts", response_model=List[BulkMessageResponse])
async def get_sent_broadcasts(current_user: dict = Depends(get_current_user)):
    """عرض رسائل البث المرسلة من قبل المدير مع الردود الواردة"""
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    if role == "super_admin":
        query = {"center_id": "global"}
    else:
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query = {"center_id": center_id}
        if role == "center_manager":
            query["sender_id"] = str(current_user["_id"])
        
    messages = await db.bulk_messages.find(query).sort("sent_at", -1).to_list(100)
    return [serialize_doc(m) for m in messages]


# ==================== Recitations Routes ====================

@app.get("/api/recitations")
async def get_recitations(
    center_id: Optional[str] = None,
    halaqah_id: Optional[str] = None,
    student_id: Optional[str] = None,
    limit: int = Query(200, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة التسميعات - مفلترة حسب الدور"""
    # [AUDIT-2026-05-22 fix: tight role gate + center isolation; closed dead-code BOLA for students/parents]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher", "student", "parent", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    allowed_student_ids: Optional[set] = None  # whitelist for non-admin scopes

    user_cid = current_user.get("center_id")
    if role not in ["super_admin", "admin"]:
        if not user_cid:
            return []

    # SaaS Multi-tenant Isolation
    if role in ["super_admin", "admin"]:
        if center_id:
            students = await db.students.find(
                {"center_id": center_id, "is_active": True}, {"_id": 1}
            ).to_list(2000)
            allowed_student_ids = {str(s["_id"]) for s in students}
    elif role == "center_manager":
        students = await db.students.find(
            {"center_id": user_cid, "is_active": True}, {"_id": 1}
        ).to_list(5000)
        allowed_student_ids = {str(s["_id"]) for s in students}
    elif role == "teacher":
        # [AUDIT-2026-05-22 fix: deny-by-default if no teacher row found]
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher:
            return []
        query["teacher_id"] = str(teacher["_id"])
    elif role == "student":
        # [AUDIT-2026-05-22 fix: replace dead `if False` branch with real ownership lookup]
        student_doc = await db.students.find_one({"user_id": str(current_user["_id"])})
        if not student_doc and current_user.get("phone"):
            student_doc = await db.students.find_one({"phone": current_user["phone"]})
        if not student_doc:
            return []
        allowed_student_ids = {str(student_doc["_id"])}
    elif role == "parent":
        phone = current_user.get("phone")
        if not phone:
            return []
        children = await db.students.find({"parent_phone": phone}, {"_id": 1}).to_list(100)
        allowed_student_ids = {str(s["_id"]) for s in children}
        if not allowed_student_ids:
            return []

    # [AUDIT-2026-05-22 fix: query-param student_id MUST stay within caller's whitelist]
    if student_id:
        if allowed_student_ids is not None and student_id not in allowed_student_ids:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لتسميعات هذا الطالب")
        query["student_id"] = student_id
    elif allowed_student_ids is not None:
        query["student_id"] = {"$in": list(allowed_student_ids)}

    if halaqah_id:
        # [AUDIT-2026-05-22 fix: verify halaqah belongs to caller's center before filtering by it]
        if role in ("center_manager", "teacher") and current_user.get("center_id"):
            try:
                h = await db.halaqat.find_one({"_id": safe_object_id(halaqah_id)})
            except HTTPException:
                h = None
            if not h or h.get("center_id") != current_user.get("center_id"):
                raise HTTPException(status_code=403, detail="حلقة لا تنتمي لمركزك")
        query["halaqah_id"] = halaqah_id

    recitations = await db.recitations.find({**query, **NOT_DELETED}).sort("date", -1).to_list(limit)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


@app.post("/api/recitations")
async def create_recitation(recitation: RecitationCreate, current_user: dict = Depends(get_current_user)):
    """تسجيل تسميع جديد"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: enforce student belongs to caller's center before logging recitation]
    await check_student_access(recitation.student_id, current_user)

    # [AUDIT-2026-05-22 fix: a teacher may only record recitations under their own teacher identity]
    if current_user["role"] == "teacher":
        teacher_row = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher_row or recitation.teacher_id != str(teacher_row["_id"]):
            raise HTTPException(status_code=403, detail="لا يمكن تسجيل تسميع باسم معلم آخر")

    recitation_dict = recitation.model_dump()
    recitation_dict["date"] = datetime.utcnow()
    result = await db.recitations.insert_one(recitation_dict)
    
    return {
        "id": str(result.inserted_id),
        "student_id": recitation_dict["student_id"],
        "student_name": recitation_dict.get("student_name"),
        "teacher_id": recitation_dict["teacher_id"],
        "teacher_name": recitation_dict.get("teacher_name"),
        "surah_number": recitation_dict.get("surah_number"),
        "surah_name": recitation_dict["surah_name"],
        "start_ayah": recitation_dict["start_ayah"],
        "end_ayah": recitation_dict["end_ayah"],
        "evaluation": recitation_dict["evaluation"],
        "mistakes_count": recitation_dict["mistakes_count"],
        "hesitations_count": recitation_dict.get("hesitations_count", 0),
        "tajweed_errors_count": recitation_dict.get("tajweed_errors_count", 0),
        "notes": recitation_dict.get("notes"),
        "recitation_type": recitation_dict["recitation_type"],
        "date": recitation_dict["date"].isoformat()
    }


@app.get("/api/recitations/student/{student_id}")
async def get_student_recitations(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على تسميعات طالب محدد"""
    await check_student_access(student_id, current_user)
    recitations = await db.recitations.find({**NOT_DELETED, "student_id": student_id}).sort("date", -1).to_list(100)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


@app.delete("/api/recitations/{recitation_id}")
async def delete_recitation(
    recitation_id: str,
    request: Request,
    current_user: dict = Depends(get_current_user),
):
    """
    حذف تسميع (حذف ناعم).

    [إصلاح 2026-09-03] صفحة التسميع فيها زر «حذف» منذ البداية يستدعي
    PUT /api/recitations/{id} — وهي نقطة لا وجود لها في الخادم. الاستجابة 404 كانت تُبتلع في
    catch صامت، فيؤكّد المعلّم الحذف ولا يحدث شيء ويبقى التسميع في الدرجات.

    الحذف ناعم لا نهائي: التسميع يقرّر جزءاً من تقييم الطالب، فإبقاؤه في قاعدة البيانات يسمح
    بمراجعة ما جرى. ويُستبعَد بعدها من كل حساب (القائمة، سجل الشرف، الترتيب، التحليلات، التنبؤ).
    """
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    rec_obj_id = safe_object_id(recitation_id)
    rec = await db.recitations.find_one({"_id": rec_obj_id})
    if not rec:
        raise HTTPException(status_code=404, detail="التسميع غير موجود")
    if rec.get("is_deleted"):
        raise HTTPException(status_code=409, detail="هذا التسميع محذوف مسبقاً")

    # الطالب يحدّد المركز — وهو الفحص نفسه الذي يحرس بقية مسارات التسميع
    await check_student_access(rec.get("student_id"), current_user)

    # المعلّم لا يحذف إلا تسميعاً سجّله بنفسه؛ حذف عمل زميله من صلاحية الإدارة
    if current_user["role"] == "teacher":
        teacher_row = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher_row or rec.get("teacher_id") != str(teacher_row["_id"]):
            raise HTTPException(status_code=403, detail="لا يمكنك حذف تسميع سجّله معلم آخر")

    await db.recitations.update_one(
        {"_id": rec_obj_id},
        {"$set": {
            "is_deleted": True,
            "deleted_at": datetime.utcnow(),
            "deleted_by": str(current_user["_id"]),
        }},
    )

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="DELETE_RECITATION",
        payload={
            "recitation_id": recitation_id,
            "student_id": rec.get("student_id"),
            "surah_name": rec.get("surah_name"),
            "evaluation": rec.get("evaluation"),
        },
        client_ip=client_ip(request),
    )
    return {"message": "تم حذف التسميع بنجاح"}


@app.get("/api/analytics/predict/{student_id}")
async def predict_completion(student_id: str, current_user: dict = Depends(get_current_user)):
    """حساب مؤشر الإتقان والتنبؤ بموعد ختم القرآن أو الجزء الحالي"""
    student = await check_student_access(student_id, current_user)
    
    recitations = await db.recitations.find({**NOT_DELETED, "student_id": student_id}).sort("date", 1).to_list(2000)
    
    TOTAL_QURAN_VERSES = 6236
    
    mastery_scores = []
    total_new_verses = 0
    new_recitations = []
    
    for r in recitations:
        mistakes = r.get("mistakes_count", 0)
        hesitations = r.get("hesitations_count", 0)
        tajweed_errors = r.get("tajweed_errors_count", 0)
        
        score = max(0.0, 100.0 - (mistakes * 4.0 + hesitations * 1.5 + tajweed_errors * 2.0))
        mastery_scores.append(score)
        
        if r.get("recitation_type") == "new":
            new_recitations.append(r)
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            total_new_verses += verses_count
            
    avg_mastery = sum(mastery_scores) / len(mastery_scores) if mastery_scores else 85.0
    
    now = datetime.utcnow()
    thirty_days_ago = now - timedelta(days=30)
    recent_verses = 0
    for r in new_recitations:
        r_date = r.get("date", now)
        if isinstance(r_date, str):
            try:
                r_date = datetime.fromisoformat(r_date)
            except ValueError:
                r_date = now
        if r_date >= thirty_days_ago:
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            recent_verses += verses_count
            
    momentum = recent_verses / (30.0 / 7.0)
    
    expected_completion_date = None
    confidence = 70
    
    if len(new_recitations) >= 2:
        first_date = new_recitations[0].get("date", now)
        if isinstance(first_date, str):
            try:
                first_date = datetime.fromisoformat(first_date)
            except ValueError:
                first_date = now
                
        x = []
        y = []
        accumulated = 0
        for r in new_recitations:
            r_date = r.get("date", now)
            if isinstance(r_date, str):
                try:
                    r_date = datetime.fromisoformat(r_date)
                except ValueError:
                    r_date = now
            days = (r_date - first_date).days
            verses_count = max(1, r.get("end_ayah", 0) - r.get("start_ayah", 0) + 1)
            accumulated += verses_count
            x.append(float(days))
            y.append(float(accumulated))
            
        n = len(x)
        mean_x = sum(x) / n
        mean_y = sum(y) / n
        
        num = 0.0
        den = 0.0
        for xi, yi in zip(x, y):
            num += (xi - mean_x) * (yi - mean_y)
            den += (xi - mean_x) ** 2
            
        if den > 0:
            slope = num / den
            intercept = mean_y - slope * mean_x
            
            y_pred = [slope * xi + intercept for xi in x]
            ss_tot = sum((yi - mean_y) ** 2 for yi in y)
            ss_res = sum((yi - ypi) ** 2 for yi, ypi in zip(y, y_pred))
            r_squared = 1.0 - (ss_res / ss_tot) if ss_tot > 0 else 1.0
            
            confidence = max(50, min(82, int(r_squared * 82)))
            
            remaining_verses = max(0, TOTAL_QURAN_VERSES - accumulated)
            if slope > 0.05:
                days_to_complete = remaining_verses / slope
                expected_date = now + timedelta(days=days_to_complete)
                expected_completion_date = expected_date.strftime("%Y-%m-%d")
            else:
                daily_rate = max(0.1, accumulated / max(1, x[-1]))
                days_to_complete = remaining_verses / daily_rate
                expected_date = now + timedelta(days=days_to_complete)
                expected_completion_date = expected_date.strftime("%Y-%m-%d")
                confidence = max(50, int(confidence * 0.8))
        else:
            slope = 0
    else:
        remaining_verses = TOTAL_QURAN_VERSES - total_new_verses
        daily_rate = 5.0
        days_to_complete = remaining_verses / daily_rate
        expected_date = now + timedelta(days=days_to_complete)
        expected_completion_date = expected_date.strftime("%Y-%m-%d")
        confidence = 60
        
    return {
        "student_id": student_id,
        "student_name": student.get("name"),
        "average_mastery_score": round(avg_mastery, 1),
        "momentum_verses_per_week": round(momentum, 1),
        "total_verses_memorized": total_new_verses,
        "remaining_verses": max(0, TOTAL_QURAN_VERSES - total_new_verses),
        "predicted_completion_date": expected_completion_date,
        "confidence_percentage": confidence,
        "accuracy_bracket": "82% consistent linear projection" if confidence >= 75 else "consistent daily rate fallback"
    }


# ==================== Attendance Routes ====================

@app.get("/api/attendance")
async def get_attendance(
    halaqah_id: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_user)
):
    """الحصول على سجلات الحضور"""
    # [AUDIT-2026-05-22 fix: enforce role gate + center isolation; close cross-center leak]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}

    if role in ("center_manager", "teacher"):
        if not current_user.get("center_id"):
            return []
        halaqat = await db.halaqat.find(
            {"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}
        ).to_list(500)
        halaqah_ids_in_scope = {str(h["_id"]) for h in halaqat}
        if not halaqah_ids_in_scope:
            return []
        query["halaqah_id"] = {"$in": list(halaqah_ids_in_scope)}
        if halaqah_id:
            if halaqah_id not in halaqah_ids_in_scope:
                raise HTTPException(status_code=403, detail="حلقة لا تنتمي لمركزك")
            query["halaqah_id"] = halaqah_id
    else:  # admin
        if halaqah_id:
            query["halaqah_id"] = halaqah_id

    if date:
        query["date_str"] = date

    attendance = await db.attendance.find(query).sort("date", -1).to_list(limit)
    result = []
    for a in attendance:
        doc = serialize_doc(a)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


@app.get("/api/attendance/halaqah/{halaqah_id}")
async def get_halaqah_attendance(
    halaqah_id: str,
    date: Optional[str] = None,
    limit: int = Query(300, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """
    [AUDIT-2026-09-03 addition] حضور حلقة محددة في يوم محدد.

    صفحة الحضور في الواجهة تستدعي GET /api/attendance/halaqah/{id} منذ البداية، ولا وجود
    لهذه النقطة في الخادم إطلاقاً — فكانت تعود 404 وتظهر الشاشة فارغة دائماً عند اختيار حلقة.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    halaqah = await db.halaqat.find_one({"_id": safe_object_id(halaqah_id)})
    if not halaqah:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")

    if role not in ["admin", "super_admin"]:
        if not current_user.get("center_id") or halaqah.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="حلقة لا تنتمي لمركزك")

    query: dict = {"halaqah_id": halaqah_id}
    if date:
        query["date_str"] = date

    rows = await db.attendance.find(query).sort("date", -1).to_list(limit)
    result = []
    for a in rows:
        doc = serialize_doc(a)
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


@app.post("/api/attendance")
async def create_attendance(data: AttendanceCreate, current_user: dict = Depends(get_current_user)):
    """تسجيل حضور مجموعة"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    now = datetime.utcnow()
    date_str = data.date or now.strftime("%Y-%m-%d")

    # [AUDIT-2026-05-22 fix: validate every record's student belongs to caller's center]
    role = current_user["role"]
    user_center = current_user.get("center_id")
    halaqah_center_cache: dict = {}

    records = []
    for record in data.records:
        # student must be accessible (404 if missing, 403 if cross-center)
        student = await check_student_access(record.student_id, current_user)

        # halaqah scope check: halaqah's center must match caller's center for non-admin
        if role != "admin":
            cached = halaqah_center_cache.get(record.halaqah_id)
            if cached is None:
                try:
                    h_doc = await db.halaqat.find_one({"_id": safe_object_id(record.halaqah_id)})
                except HTTPException:
                    h_doc = None
                cached = h_doc.get("center_id") if h_doc else None
                halaqah_center_cache[record.halaqah_id] = cached
            if cached != user_center:
                raise HTTPException(status_code=403, detail="لا يمكن تسجيل حضور في حلقة خارج مركزك")
            # also: student must belong to that halaqah (defence in depth)
            if student.get("halaqah_id") and student.get("halaqah_id") != record.halaqah_id:
                raise HTTPException(
                    status_code=400,
                    detail=f"الطالب {student.get('name')} غير مسجل في هذه الحلقة"
                )

        attendance_dict = record.model_dump()
        attendance_dict["date"] = now
        attendance_dict["date_str"] = date_str
        # [AUDIT-2026-09-03 fix: سجل الحضور لم يكن يحمل center_id إطلاقاً، فكل استعلام يُصفّي
        #  عليه يعود فارغاً (نسبة الحضور على لوحة التحكم). يُكتب الآن من مستند الطالب نفسه.]
        attendance_dict["center_id"] = student.get("center_id")
        attendance_dict["recorded_by"] = str(current_user["_id"])
        records.append(attendance_dict)

        # Real-time Parent Absentee warning via SSE
        if record.status == "absent":
            parent_phone = student.get("parent_phone")
            if parent_phone:
                parent_user = await db.users.find_one({"phone": parent_phone, "role": "parent"})
                if parent_user:
                    await push_notification(
                        user_id=str(parent_user["_id"]),
                        event_type="absentee_alert",
                        title="تنبيه غياب",
                        body=f"ابنكم/ابنتكم {student.get('name')} غائب(ة) اليوم عن حلقة التحفيظ.",
                        data={
                            "student_id": record.student_id,
                            "student_name": student.get("name"),
                            "date": date_str,
                        },
                    )

    # [AUDIT-2026-09-03 fix — ازدواج سجلات الحضور] كان insert_many يضيف صفاً جديداً في كل مرة،
    # فإعادة إرسال كشف اليوم (نقرة مزدوجة، أو تصحيح غياب إلى حضور) تُنشئ سجلين متناقضين للطالب
    # نفسه في اليوم نفسه، ويظل الغياب محسوباً في نسبة الحضور إلى الأبد. صار التسجيل عن اليوم
    # نفسه يستبدل السجل السابق (upsert) — وهو ما يتوقعه المعلّم عند التصحيح.
    created = updated_count = 0
    for rec in records:
        key = {"student_id": rec["student_id"], "date_str": rec["date_str"]}
        try:
            res = await db.attendance.update_one(key, {"$set": rec}, upsert=True)
        except DuplicateKeyError:
            # سباق: طلبان متزامنان على المفتاح نفسه (نقرة مزدوجة). الفهرس الفريد ردّ الثاني،
            # فنكتبه تحديثاً — بدون هذا يضيع تصحيح المعلّم بخطأ 500.
            res = await db.attendance.update_one(key, {"$set": rec})
        if res.upserted_id is not None:
            created += 1
        else:
            updated_count += 1

    return {
        "message": f"تم تسجيل حضور {len(records)} طالب",
        "count": len(records),
        "created": created,
        "updated": updated_count,
    }


@app.get("/api/attendance/student/{student_id}")
async def get_student_attendance(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على سجل حضور طالب"""
    await check_student_access(student_id, current_user)
    attendance = await db.attendance.find({"student_id": student_id}).sort("date", -1).to_list(100)
    result = []
    for a in attendance:
        doc = serialize_doc(a)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


# ==================== Fees Routes ====================

@app.get("/api/fees")
async def get_fees(
    status_filter: Optional[FeeStatus] = Query(None, alias="status"),
    student_id: Optional[str] = None,
    limit: int = Query(1000, ge=1, le=5000),
    skip: int = Query(0, ge=0),
    current_user: dict = Depends(get_current_user),
):
    """
    الحصول على سجلات الرسوم.

    [AUDIT-2026-09-03 fix: الواجهة تطلب /fees?status=pending منذ البداية، والخادم لا يعرف
     المعامل أصلاً فيتجاهله FastAPI بصمت ويعيد كل الرسوم — فتظهر «الرسوم المعلّقة» في
     التقارير وقد أُضيف إليها كل رسم مدفوع. المعامل صار مُعرَّفاً ومُتحقَّقاً منه.]
    """
    # [AUDIT-2026-05-22 fix: enforce role-based scoping; admin sees all, others restricted to own data]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher", "parent", "student"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}

    if role in ("center_manager", "teacher"):
        if not current_user.get("center_id"):
            return []
        students = await db.students.find(
            {"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}
        ).to_list(5000)
        student_ids = [str(s["_id"]) for s in students]
        if not student_ids:
            return []
        query["student_id"] = {"$in": student_ids}
    elif role == "parent":
        phone = current_user.get("phone")
        if not phone:
            return []
        children = await db.students.find({"parent_phone": phone}, {"_id": 1}).to_list(100)
        student_ids = [str(s["_id"]) for s in children]
        if not student_ids:
            return []
        query["student_id"] = {"$in": student_ids}
    elif role == "student":
        s_doc = await db.students.find_one({"user_id": str(current_user["_id"])})
        if not s_doc and current_user.get("phone"):
            s_doc = await db.students.find_one({"phone": current_user["phone"]})
        if not s_doc:
            return []
        query["student_id"] = str(s_doc["_id"])
    # admin: no extra filter

    if status_filter:
        query["status"] = status_filter

    if student_id:
        # الفلترة تُضيَّق داخل النطاق المسموح ولا تتجاوزه أبداً
        allowed = query.get("student_id")
        if isinstance(allowed, dict) and student_id not in allowed.get("$in", []):
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لرسوم هذا الطالب")
        if isinstance(allowed, str) and allowed != student_id:
            raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول لرسوم هذا الطالب")
        if allowed is None and role != "admin":
            raise HTTPException(status_code=403, detail="غير مصرح")
        query["student_id"] = student_id

    fees = await db.fees.find(query).skip(skip).limit(limit).to_list(limit)
    result = []
    for f in fees:
        doc = serialize_doc(f)
        if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
            doc["paid_date"] = doc["paid_date"].isoformat()
        result.append(doc)
    return result


@app.post("/api/fees")
async def create_fee(fee: FeeCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء رسوم جديدة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center isolation]
    student = await check_student_access(fee.student_id, current_user)

    if fee.amount is None or fee.amount <= 0:
        raise HTTPException(status_code=400, detail="المبلغ يجب أن يكون أكبر من صفر")
    if not parse_date_boundary(fee.due_date):
        raise HTTPException(status_code=400, detail="تاريخ الاستحقاق غير صالح (YYYY-MM-DD)")

    fee_dict = fee.model_dump()
    fee_dict["status"] = "pending"
    fee_dict["paid_date"] = None
    # [AUDIT-2026-09-03 fix: الرسوم لم تكن تحمل center_id ولا تاريخ إنشاء — فلا يمكن حصر
    #  رسوم مركز ولا حساب إيراد فترة زمنية. يُكتبان الآن من مستند الطالب ووقت الإنشاء.]
    fee_dict["center_id"] = student.get("center_id")
    fee_dict["created_at"] = datetime.utcnow()
    fee_dict["created_by"] = str(current_user["_id"])
    if not fee_dict.get("student_name"):
        fee_dict["student_name"] = student.get("name")
    result = await db.fees.insert_one(fee_dict)

    return {
        "id": str(result.inserted_id),
        "student_id": fee_dict["student_id"],
        "student_name": fee_dict.get("student_name"),
        "amount": fee_dict["amount"],
        "due_date": fee_dict["due_date"],
        "fee_type": fee_dict["fee_type"],
        "notes": fee_dict.get("notes"),
        "status": fee_dict["status"],
        "paid_date": fee_dict["paid_date"]
    }


@app.post("/api/fees/{fee_id}/pay")
async def pay_fee(fee_id: str, current_user: dict = Depends(get_current_user)):
    """تسجيل دفع رسوم"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    fee_obj_id = safe_object_id(fee_id)
    fee = await db.fees.find_one({"_id": fee_obj_id})
    if not fee:
        raise HTTPException(status_code=404, detail="الرسوم غير موجودة")
        
    # Verify BOLA access to this student's fees
    await check_student_access(fee["student_id"], current_user)

    # [AUDIT-2026-09-03 fix: كان دفع رسم مدفوع مسبقاً يعيد كتابة تاريخ الدفع ويضيف قيد
    #  تحصيل ثانياً في سجل التدقيق — نقرتان على الزر تعنيان تحصيلين في السجل المالي.]
    if fee.get("status") == "paid":
        raise HTTPException(status_code=409, detail="هذه الرسوم مدفوعة مسبقاً")

    paid_at = datetime.utcnow()
    updated_res = await db.fees.update_one(
        {"_id": fee_obj_id, "status": {"$ne": "paid"}},
        {"$set": {
            "status": "paid",
            "paid_date": paid_at,
            "collected_by": str(current_user["_id"]),
        }}
    )
    if updated_res.modified_count == 0:
        raise HTTPException(status_code=409, detail="هذه الرسوم مدفوعة مسبقاً")

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="collect_fee",
        payload={"fee_id": fee_id, "amount": fee["amount"], "student_id": fee["student_id"]}
    )
    
    updated = await db.fees.find_one({"_id": fee_obj_id})
    doc = serialize_doc(updated)
    if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
        doc["paid_date"] = doc["paid_date"].isoformat()
    return doc


@app.get("/api/fees/student/{student_id}")
async def get_student_fees(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على رسوم طالب"""
    await check_student_access(student_id, current_user)
    fees = await db.fees.find({"student_id": student_id}).to_list(100)
    result = []
    for f in fees:
        doc = serialize_doc(f)
        if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
            doc["paid_date"] = doc["paid_date"].isoformat()
        result.append(doc)
    return result


# ==================== Salaries Routes ====================

@app.get("/api/salaries")
async def get_salaries(current_user: dict = Depends(get_current_user)):
    """الحصول على سجلات الرواتب"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    # [AUDIT-2026-05-22 fix: fail-closed for managers without center_id (was leaking all centers)]
    query = {}
    if current_user["role"] == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    salaries = await db.salaries.find(query).sort("created_at", -1).to_list(200)
    result = []
    for s in salaries:
        doc = serialize_doc(s)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result


@app.post("/api/salaries")
async def create_salary(salary: SalaryCreate, current_user: dict = Depends(get_current_user)):
    """إضافة راتب معلم"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: center_manager may only pay salaries inside their own center,
    # and the teacher being paid must belong to that center as well]
    if current_user["role"] == "center_manager":
        if salary.center_id != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة راتب لمركز آخر")
        teacher_obj_id = safe_object_id(salary.teacher_id)
        teacher_row = await db.teachers.find_one({"_id": teacher_obj_id})
        if not teacher_row:
            raise HTTPException(status_code=404, detail="المعلم غير موجود")
        if teacher_row.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="هذا المعلم لا ينتمي لمركزك")

    salary_dict = salary.model_dump()
    salary_dict["created_at"] = datetime.utcnow()
    salary_dict["status"] = "paid"
    result = await db.salaries.insert_one(salary_dict)
    
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=salary.center_id,
        action="pay_salary",
        payload={"teacher_id": salary.teacher_id, "amount": salary.amount, "month": salary.month}
    )
    
    doc = salary_dict.copy()
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


# ==================== Expenses Routes ====================

@app.get("/api/expenses")
async def get_expenses(current_user: dict = Depends(get_current_user)):
    """الحصول على المصروفات"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    # [AUDIT-2026-05-22 fix: fail-closed for managers without center_id (was leaking all centers)]
    query = {}
    if current_user["role"] == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    expenses = await db.expenses.find(query).sort("created_at", -1).to_list(200)
    result = []
    for e in expenses:
        doc = serialize_doc(e)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result


@app.post("/api/expenses")
async def create_expense(expense: ExpenseCreate, current_user: dict = Depends(get_current_user)):
    """إضافة مصروف"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center-level isolation]
    if current_user["role"] != "admin" and expense.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإضافة مصروف لمركز آخر")
        
    exp_dict = expense.model_dump()
    exp_dict["created_at"] = datetime.utcnow()
    result = await db.expenses.insert_one(exp_dict)
    
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=expense.center_id,
        action="create_expense",
        payload={"title": expense.title, "amount": expense.amount, "category": expense.category}
    )
    
    doc = exp_dict.copy()
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    """حذف مصروف"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: safe object id parse & secure BOLA]
    exp_obj_id = safe_object_id(expense_id)
    expense = await db.expenses.find_one({"_id": exp_obj_id})
    if not expense:
        raise HTTPException(status_code=404, detail="المصروف غير موجود")
        
    if current_user["role"] != "admin" and expense.get("center_id") != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بحذف مصروف لمركز آخر")
        
    await db.expenses.delete_one({"_id": exp_obj_id})
    
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=expense.get("center_id", "system"),
        action="delete_expense",
        payload={"expense_id": expense_id, "title": expense.get("title"), "amount": expense.get("amount")}
    )
    
    return {"message": "تم حذف المصروف"}


# ==================== Review Plans (خطط المراجعة) ====================

@app.get("/api/review-plans")
async def get_review_plans(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على خطط المراجعة"""
    # [AUDIT-2026-05-22 fix: tight role gate + fail-closed; was leaking all plans to parents/students/scopeless managers]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    if role == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    elif role == "teacher":
        if not current_user.get("center_id"):
            return []
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher:
            return []
        query["teacher_id"] = str(teacher["_id"])
    elif role == "admin" and center_id:
        query["center_id"] = center_id

    plans = await db.review_plans.find(query).sort("created_at", -1).to_list(500)
    result = []
    for p in plans:
        doc = serialize_doc(p)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result


@app.post("/api/review-plans")
async def create_review_plan(plan: ReviewPlanCreate, current_user: dict = Depends(get_current_user)):
    """إضافة خطة مراجعة"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: enforce center_id matches caller's center for non-admin;
    # validate student/teacher (if supplied) belong to the same center]
    if current_user["role"] != "admin":
        if plan.center_id != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء خطة في مركز آخر")

    if plan.student_id:
        student = await check_student_access(plan.student_id, current_user)
        if student.get("center_id") != plan.center_id:
            raise HTTPException(status_code=400, detail="الطالب لا ينتمي للمركز المحدد")

    if plan.teacher_id and current_user["role"] != "admin":
        try:
            t_row = await db.teachers.find_one({"_id": safe_object_id(plan.teacher_id)})
        except HTTPException:
            t_row = None
        if not t_row or t_row.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="المعلم لا ينتمي لمركزك")

    data = plan.model_dump(exclude_none=True)
    data["created_at"] = datetime.utcnow()
    data["created_by"] = str(current_user["_id"])
    result = await db.review_plans.insert_one(data)
    data["id"] = str(result.inserted_id)
    data["created_at"] = data["created_at"].isoformat()
    return data


@app.get("/api/attendance/center")
async def get_center_attendance(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(300, ge=1, le=500)
):
    """حضور مركز كامل لمدير المركز"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: fail-closed for managers without center_id (was leaking all centers)]
    query = {}
    if current_user["role"] == "center_manager":
        if not current_user.get("center_id"):
            return []
        # Get all halaqat in this center
        halaqat = await db.halaqat.find({"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}).to_list(100)
        halaqah_ids = [str(h["_id"]) for h in halaqat]
        if halaqah_ids:
            query["halaqah_id"] = {"$in": halaqah_ids}
    
    attendance = await db.attendance.find(query).sort("date", -1).to_list(limit)
    result = []
    for a in attendance:
        doc = serialize_doc(a)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


# ==================== Financial Summary (إضافة 2026-09-03) ====================

async def _sum_amounts(collection, match: dict) -> float:
    """
    مجموع حقل amount عبر تجميع قاعدة البيانات.

    [AUDIT-2026-09-03 perf: كانت /api/super/dashboard/stats تسحب كل الرسوم وكل الرواتب وكل
     المصروفات إلى ذاكرة الخادم وتجمعها في حلقة Python — يكبر ببطء مع كل مركز جديد إلى أن
     تتجاوز الصفحة المهلة. الجمع الآن داخل قاعدة البيانات.]
    """
    pipeline = [{"$match": match}, {"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    async for row in collection.aggregate(pipeline):
        return float(row.get("total") or 0.0)
    return 0.0


@app.get("/api/finance/summary")
async def get_finance_summary(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    [AUDIT-2026-09-03 addition] الملخّص المالي للمركز خلال فترة: المُحصَّل، المعلّق،
    الرواتب، المصروفات، والصافي.

    كانت صفحة المالية في الواجهة تجمع هذه الأرقام بنفسها من قوائم مُقسَّمة إلى صفحات
    (page 1 فقط)، فتظهر أرقام لا تعبّر عن الفترة كاملة. الحساب صار في الخادم على كل السجلات.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    if role == "center_manager":
        scope_center = current_user.get("center_id")
        if not scope_center:
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        if center_id and center_id != scope_center:
            raise HTTPException(status_code=403, detail="غير مصرح لك بعرض مالية مركز آخر")
    else:
        scope_center = center_id  # None = كل المراكز للمدير العام

    start = parse_date_boundary(from_date, end=False)
    end = parse_date_boundary(to_date, end=True)
    if from_date and not start:
        raise HTTPException(status_code=400, detail="تاريخ البداية غير صالح (YYYY-MM-DD)")
    if to_date and not end:
        raise HTTPException(status_code=400, detail="تاريخ النهاية غير صالح (YYYY-MM-DD)")
    if start and end and start > end:
        raise HTTPException(status_code=400, detail="تاريخ البداية بعد تاريخ النهاية")

    def window(field: str) -> dict:
        rng = {}
        if start:
            rng["$gte"] = start
        if end:
            rng["$lte"] = end
        return {field: rng} if rng else {}

    # الرسوم: قد لا تحمل السجلات القديمة center_id، فيُستكمل النطاق بمعرّفات طلاب المركز
    fee_scope: dict = {}
    if scope_center:
        ids = await scoped_student_ids(scope_center)
        fee_scope = {"$or": [{"center_id": scope_center}, {"student_id": {"$in": ids}}]}

    collected = await _sum_amounts(db.fees, {**fee_scope, "status": "paid", **window("paid_date")})
    pending = await _sum_amounts(db.fees, {**fee_scope, "status": {"$ne": "paid"}})
    pending_count = await db.fees.count_documents({**fee_scope, "status": {"$ne": "paid"}})

    center_scope = {"center_id": scope_center} if scope_center else {}
    salaries = await _sum_amounts(db.salaries, {**center_scope, **window("created_at")})
    expenses = await _sum_amounts(db.expenses, {**center_scope, **window("created_at")})

    return {
        "center_id": scope_center,
        "from": start.isoformat() if start else None,
        "to": end.isoformat() if end else None,
        "revenue": {"fees_collected": round(collected, 2)},
        "outstanding": {"fees_pending": round(pending, 2), "fees_pending_count": pending_count},
        "costs": {
            "salaries_paid": round(salaries, 2),
            "expenses": round(expenses, 2),
            "total": round(salaries + expenses, 2),
        },
        "net_balance": round(collected - salaries - expenses, 2),
        "currency": "FCFA",
        "note": "المُحصَّل يُحسب بتاريخ الدفع الفعلي، والتكاليف بتاريخ التسجيل",
    }


# ==================== CSV Export (إضافة 2026-09-03) ====================

def _csv_response(rows: List[dict], columns: List[tuple], filename: str) -> StreamingResponse:
    """
    تصدير CSV بترميز UTF-8 مع BOM حتى تظهر العربية سليمة في Excel
    (بدون BOM يفتح Excel الملف بترميز خاطئ فتبدو الأسماء رموزاً).
    """
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow([label for _key, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _label in columns])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@app.get("/api/export/students.csv")
async def export_students_csv(current_user: dict = Depends(get_current_user)):
    """
    [AUDIT-2026-09-03 addition] تصدير كشف الطلاب — المركز يحتاج نسخة ورقية/إكسل للإدارة
    وللأرشيف، ولم تكن هناك أي وسيلة لإخراج البيانات من النظام.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {"is_active": True}
    if role == "center_manager":
        if not current_user.get("center_id"):
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        query["center_id"] = current_user["center_id"]

    students = await db.students.find(query).to_list(10000)
    rows = []
    for s in students:
        d = decrypt_student_doc(s)
        rows.append({
            "name": d.get("name"),
            "halaqah_name": d.get("halaqah_name"),
            "phone": d.get("phone"),
            "parent_name": d.get("parent_name"),
            "parent_phone": d.get("parent_phone"),
            "memorization_plan": d.get("memorization_plan"),
            "progress": d.get("progress", 0),
            "current_surah": d.get("current_surah"),
            "enrollment_date": d["enrollment_date"].strftime("%Y-%m-%d") if isinstance(d.get("enrollment_date"), datetime) else "",
        })

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="EXPORT_STUDENTS",
        payload={"rows": len(rows)},
    )

    return _csv_response(rows, [
        ("name", "الاسم"),
        ("halaqah_name", "الحلقة"),
        ("phone", "هاتف الطالب"),
        ("parent_name", "ولي الأمر"),
        ("parent_phone", "هاتف ولي الأمر"),
        ("memorization_plan", "خطة الحفظ"),
        ("progress", "نسبة التقدم"),
        ("current_surah", "السورة الحالية"),
        ("enrollment_date", "تاريخ التسجيل"),
    ], "students.csv")


@app.get("/api/export/attendance.csv")
async def export_attendance_csv(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
):
    """تصدير سجل الحضور لفترة محددة"""
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    if role == "center_manager":
        center = current_user.get("center_id")
        if not center:
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        ids = await scoped_student_ids(center)
        if not ids:
            return _csv_response([], [("date_str", "التاريخ")], "attendance.csv")
        query["$or"] = [{"center_id": center}, {"student_id": {"$in": ids}}]

    rng = {}
    start = parse_date_boundary(from_date)
    end = parse_date_boundary(to_date, end=True)
    if start:
        rng["$gte"] = start
    if end:
        rng["$lte"] = end
    if rng:
        query["date"] = rng

    rows = await db.attendance.find(query).sort("date", -1).to_list(20000)
    status_ar = {"present": "حاضر", "absent": "غائب", "late": "متأخر", "excused": "بعذر"}
    out = [{
        "date_str": r.get("date_str", ""),
        "student_name": r.get("student_name", ""),
        "status": status_ar.get(r.get("status"), r.get("status", "")),
        "notes": r.get("notes", ""),
    } for r in rows]

    return _csv_response(out, [
        ("date_str", "التاريخ"),
        ("student_name", "الطالب"),
        ("status", "الحالة"),
        ("notes", "ملاحظات"),
    ], "attendance.csv")


# ==================== Health Check ====================

@app.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


@app.get("/api/health/ready")
async def readiness_check():
    """
    [AUDIT-2026-09-03 addition] فحص جاهزية حقيقي.
    /api/health كان يجيب "سليم" حتى وقاعدة البيانات ساقطة تماماً، فلا يكشف عطلاً ولا يصلح
    لموازِن حِمل أو لمراقبة. هذا الفحص يلمس قاعدة البيانات فعلاً ويعيد 503 عند فشلها.
    """
    try:
        await db.command("ping")
    except Exception as e:
        logger.error(f"readiness probe failed: {e}")
        return JSONResponse(
            status_code=503,
            content={"status": "unavailable", "database": False, "timestamp": datetime.utcnow().isoformat()},
        )
    return {
        "status": "ready",
        "database": True,
        "environment": "production" if IS_PRODUCTION else "development",
        "version": app.version,
        "timestamp": datetime.utcnow().isoformat(),
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
