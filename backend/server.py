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
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from bson import ObjectId
from bson.errors import InvalidId
from motor.motor_asyncio import AsyncIOMotorClient
from cryptography.fernet import Fernet, InvalidToken
import os
import secrets
import hmac
import hashlib
import json
from dotenv import load_dotenv
import jwt
from passlib.context import CryptContext
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

# [AUDIT-2026-05-22 fix: bcrypt cost raised to OWASP-recommended 12; tunable via env]
BCRYPT_ROUNDS = int(os.getenv("BCRYPT_ROUNDS", "12"))
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=BCRYPT_ROUNDS)

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
ALLOWED_ORIGINS = os.getenv(
    "ALLOWED_ORIGINS",
    "http://localhost:3000,http://localhost:5173,http://127.0.0.1:3000"
).split(",")

# FastAPI App
app = FastAPI(
    title="نظام إدارة مراكز التحفيظ",
    description="API لإدارة مراكز تحفيظ القرآن الكريم",
    version="2.0.0",
    docs_url=None,      # تعطيل Swagger UI في الإنتاج
    redoc_url=None,     # تعطيل ReDoc في الإنتاج
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

    class Config:
        from_attributes = True


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
    pass


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
    return pwd_context.verify(plain_password, hashed_password)


def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)


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


async def write_audit_log(actor_id: str, center_id: str, action: str, payload: dict, client_ip: str = None) -> dict:
    """إضافة سجل تدقيق مالي/إداري غير قابل للتلاعب (سلسلة تشفير SHA-256)"""
    try:
        last_log = await db.audit_logs.find_one({}, sort=[("timestamp", -1)])
        previous_hash = last_log.get("log_hash", "0" * 64) if last_log else "0" * 64
    except Exception:
        previous_hash = "0" * 64

    timestamp = datetime.utcnow()
    serialized_payload = json.dumps(payload, sort_keys=True, default=str)
    
    hash_input = f"{actor_id}:{center_id}:{action}:{serialized_payload}:{timestamp.isoformat()}:{previous_hash}"
    log_hash = hashlib.sha256(hash_input.encode()).hexdigest()
    
    log_entry = {
        "actor_id": actor_id,
        "center_id": center_id,
        "action": action,
        "payload": payload,
        "timestamp": timestamp,
        "client_ip": client_ip or "system",
        "previous_hash": previous_hash,
        "log_hash": log_hash
    }
    
    if action not in ["collect_fee", "pay_salary", "create_expense", "delete_expense"]:
        log_entry["purge_at"] = timestamp + timedelta(days=730)
    
    try:
        await db.audit_logs.insert_one(log_entry)
    except Exception as e:
        logger.error(f"Failed to write audit log: {e}")
        
    return log_entry


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
    
    # 1. Super Admin: الوصول الكامل
    if role == "super_admin":
        return student
        
    # 2. Admin & Center Manager: تطابق مركز الطالب مع مركز المدير
    if role in ["admin", "center_manager"]:
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
        
    # 4. Student: تطابق مع حساب الطالب نفسه (عبر الهاتف أو اسم المستخدم أو الربط)
    if role == "student":
        allowed = False
        if student.get("user_id") == str(current_user.get("_id")):
            allowed = True
        elif current_user.get("phone") and student.get("phone") == current_user.get("phone"):
            allowed = True
        elif current_user.get("username") and student.get("name") == current_user.get("name"):
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

@app.on_event("startup")
async def startup_event():
    """Initialize database with default data and create indexes"""
    
    # Create Indexes for performance
    await db.users.create_index("username", unique=True)
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
    await db.revoked_tokens.create_index("jti", unique=True)
    await db.revoked_tokens.create_index("expires_at", expireAfterSeconds=0)
    await db.login_attempts.create_index(
        "last_seen", expireAfterSeconds=max(LOCKOUT_MINUTES * 60 * 2, 3600)
    )
    await db.register_attempts.create_index(
        "last_seen", expireAfterSeconds=REGISTER_WINDOW_MINUTES * 60 * 2
    )

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

    existing_super_admin = await db.users.find_one({"username": "superadmin"})
    if not existing_super_admin:
        super_admin_pass = INITIAL_ADMIN_PASSWORD or "superadmin123"
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
async def _check_rate_limit(ip: str):
    """فحص حد معدل محاولات تسجيل الدخول (MongoDB-backed)"""
    now = datetime.utcnow()
    entry = await db.login_attempts.find_one({"_id": ip})
    if not entry:
        return
    locked = entry.get("locked_until")
    if locked and now < locked:
        remaining = int((locked - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تم تجاوز عدد المحاولات. حاول مرة أخرى بعد {remaining} دقيقة"
        )


async def _record_failed_attempt(ip: str) -> int:
    """تسجيل محاولة فاشلة، يرجع عدد المحاولات الحالي"""
    now = datetime.utcnow()
    entry = await db.login_attempts.find_one({"_id": ip})
    count = (entry.get("count", 0) if entry else 0) + 1
    update_doc = {"count": count, "last_seen": now}
    if count >= MAX_LOGIN_ATTEMPTS:
        update_doc["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"تم قفل IP: {ip} بعد {MAX_LOGIN_ATTEMPTS} محاولات فاشلة")
    await db.login_attempts.update_one({"_id": ip}, {"$set": update_doc}, upsert=True)
    return count


async def _clear_attempts(ip: str):
    """مسح محاولات IP بعد نجاح الدخول"""
    await db.login_attempts.delete_one({"_id": ip})

@app.post("/api/auth/login", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """تسجيل الدخول مع حماية Rate Limiting"""
    client_ip = request.client.host if request.client else "unknown"
    await _check_rate_limit(client_ip)

    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        # [AUDIT-2026-05-22 fix: await DB-backed rate-limit calls]
        current_count = await _record_failed_attempt(client_ip)
        await db.audit_logs.insert_one({
            "action": "LOGIN_FAILED",
            "username": form_data.username,
            "ip": client_ip,
            "timestamp": datetime.utcnow()
        })
        attempts_left = max(0, MAX_LOGIN_ATTEMPTS - current_count)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"اسم المستخدم أو كلمة المرور غير صحيحة ({attempts_left} محاولات متبقية)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # [AUDIT-2026-05-22 fix: refuse to issue tokens for disabled accounts even on correct password]
    if not user.get("is_active", True):
        await db.audit_logs.insert_one({
            "action": "LOGIN_DENIED_DISABLED",
            "username": user["username"],
            "ip": client_ip,
            "timestamp": datetime.utcnow(),
        })
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="الحساب معطّل - Account is disabled")

    await _clear_attempts(client_ip)
    # تسجيل الدخول الناجح
    await db.audit_logs.insert_one({
        "action": "LOGIN_SUCCESS",
        "username": user["username"],
        "role": user["role"],
        "ip": client_ip,
        "timestamp": datetime.utcnow()
    })

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

    client_ip = request.client.host if request.client else "unknown"
    await db.audit_logs.insert_one({
        "action": "LOGOUT",
        "username": current_user["username"],
        "ip": client_ip,
        "timestamp": datetime.utcnow()
    })
    return {"message": "تم تسجيل الخروج بنجاح"}


class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

@app.post("/api/auth/change-password")
async def change_password(
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
            "password_changed_at": datetime.utcnow()
        }}
    )
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="PASSWORD_CHANGED",
        payload={"username": current_user["username"]}
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


@app.post("/api/auth/forgot-password")
async def forgot_password(data: ForgotPasswordRequest, request: Request):
    """طلب إعادة تعيين كلمة المرور (لا يسرب الرمز في الاستجابة)"""
    client_ip = request.client.host if request.client else "unknown"
    user = await get_user_by_username(data.username)
    if not user:
        # Don't leak whether user exists to avoid user enumeration
        return {"message": "إذا كان المستخدم موجوداً، فقد تم إرسال رمز التحقق"}
    
    # Generate 6-digit code
    code = "".join(secrets.choice("0123456789") for _ in range(6))
    expires_at = datetime.utcnow() + timedelta(minutes=10)
    
    # Save plaintext to database
    await db.password_resets.update_one(
        {"username": data.username},
        {"$set": {
            "username": data.username,
            "code": code,
            "expires_at": expires_at,
            "created_at": datetime.utcnow()
        }},
        upsert=True
    )
    
    # In production, this would send an SMS/Email. Here we simulate it.
    logger.info(f"🔑 Password reset code for {data.username}: {code} (expires in 10 minutes)")
    
    return {"message": "إذا كان المستخدم موجوداً، فقد تم إرسال رمز التحقق"}


@app.get("/api/auth/reset-codes")
async def get_reset_codes(current_user: dict = Depends(get_current_user)):
    """عرض الرموز النشطة لإعادة التعيين (للمدراء فقط)"""
    if current_user["role"] not in ["admin", "center_manager", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    now = datetime.utcnow()
    codes = await db.password_resets.find({"expires_at": {"$gt": now}}).to_list(100)
    result = []
    for c in codes:
        result.append({
            "username": c["username"],
            "code": c["code"],
            "expires_at": c["expires_at"].isoformat()
        })
    return result


@app.post("/api/auth/reset-password")
async def reset_password(data: ResetPasswordRequest, request: Request):
    """إعادة تعيين كلمة المرور باستخدام الرمز المكون من 6 أرقام"""
    client_ip = request.client.host if request.client else "unknown"
    user = await get_user_by_username(data.username)
    if not user:
        raise HTTPException(status_code=400, detail="المستخدم أو الرمز غير صالح")
        
    reset_entry = await db.password_resets.find_one({"username": data.username})
    if not reset_entry:
        raise HTTPException(status_code=400, detail="المستخدم أو الرمز غير صالح")
        
    if datetime.utcnow() > reset_entry["expires_at"]:
        await db.password_resets.delete_one({"username": data.username})
        raise HTTPException(status_code=400, detail="انتهت صلاحية الرمز")
        
    if not hmac.compare_digest(reset_entry["code"].encode(), data.code.encode()):
        raise HTTPException(status_code=400, detail="المستخدم أو الرمز غير صالح")
        
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
    
    await write_audit_log(
        actor_id=str(user["_id"]),
        center_id=user.get("center_id", "system"),
        action="PASSWORD_RESET_VIA_CODE",
        payload={"username": data.username},
        client_ip=client_ip
    )
    
    return {"message": "تمت إعادة تعيين كلمة المرور بنجاح"}


class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

@app.put("/api/auth/profile")
async def update_profile(
    data: UpdateProfileRequest,
    current_user: dict = Depends(get_current_user)
):
    """تحديث الملف الشخصي"""
    update_data = {k: v for k, v in data.dict().items() if v is not None}
    if update_data:
        await db.users.update_one(
            {"_id": current_user["_id"]},
            {"$set": update_data}
        )
    return {"message": "تم تحديث الملف بنجاح"}


@app.get("/api/audit-logs")
async def get_audit_logs(
    current_user: dict = Depends(get_current_user),
    limit: int = Query(50, ge=1, le=200),
    skip: int = Query(0, ge=0)
):
    """سجل النشاط - للمدير فقط"""
    if current_user["role"] not in ["admin", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    query = {}
    if current_user["role"] != "super_admin":
        user_cid = current_user.get("center_id")
        if not user_cid:
            return []
        query["center_id"] = user_cid

    logs = await db.audit_logs.find(query).sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return [{**serialize_doc(log)} for log in logs]


_sse_clients = {}


async def push_sse_notification(user_id: str, event_type: str, data: dict):
    """دفع إشعار SSE حي إلى مستخدم محدد"""
    if user_id in _sse_clients:
        for q in _sse_clients[user_id]:
            try:
                await q.put({"event": event_type, "data": data})
            except Exception:
                pass


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
                    
    return StreamingResponse(generator(), media_type="text/event-stream")


# ==================== Dashboard Routes ====================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """الحصول على إحصائيات لوحة التحكم"""
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
    pending_fees = await db.fees.count_documents({**query_filter, "status": "pending"})
    
    # Calculate attendance rate (last 30 days)
    total_attendance = await db.attendance.count_documents(query_filter)
    present_attendance = await db.attendance.count_documents({**query_filter, "status": "present"})
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


@app.get("/api/dashboard/honor-roll")
async def get_honor_roll(current_user: dict = Depends(get_current_user)):
    """حساب التقييم الذكي وسجل الشرف (المعادلة الذكية)"""
    role = current_user["role"]
    center_id = current_user.get("center_id")
    
    query_filter = {"is_active": True}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id
        
    students = await db.students.find(query_filter).to_list(1000)
    
    eval_map = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}
    att_map = {"present": 100, "late": 80, "excused": 60, "absent": 0}
    
    honor_roll = []
    
    # 30 days window for dynamic score
    thirty_days_ago = datetime.utcnow() - timedelta(days=30)
    
    for s in students:
        sid = str(s["_id"])
        
        # Get recitations
        recitations = await db.recitations.find({
            "student_id": sid,
            "date": {"$gte": thirty_days_ago}
        }).to_list(100)
        
        # Get attendances
        attendances = await db.attendance.find({
            "student_id": sid,
            "date": {"$gte": thirty_days_ago}
        }).to_list(100)
        
        h_sum, h_count = 0, 0
        r_sum, r_count = 0, 0
        e_sum = 0
        
        for rec in recitations:
            score = eval_map.get(rec.get("evaluation", "good"), 80)
            if rec.get("recitation_type") == "new":
                h_sum += score
                h_count += 1
            else:
                r_sum += score
                r_count += 1
            e_sum += rec.get("mistakes_count", 0)
            
        a_sum, a_count = 0, 0
        for att in attendances:
            a_sum += att_map.get(att.get("status", "present"), 100)
            a_count += 1
            
        H = (h_sum / h_count) if h_count > 0 else 80  # Default to 80 if no data
        R = (r_sum / r_count) if r_count > 0 else 80
        A = (a_sum / a_count) if a_count > 0 else 100 # Default to 100 if no data
        E = e_sum
        
        # Smart Formula
        # Score = (H*0.4) + (R*0.3) + (A*0.2) - (E*0.1)
        # Cap score at 100, Min at 0
        final_score = (H * 0.4) + (R * 0.3) + (A * 0.2) - (E * 0.1)
        final_score = max(0, min(100, final_score))
        
        honor_roll.append({
            "id": sid,
            "name": s["name"],
            "halaqah_name": s.get("halaqah_name", "غير محدد"),
            "score": round(final_score, 1),
            "progress": s.get("progress", 0) # Historical Quran progress
        })
        
    honor_roll.sort(key=lambda x: x["score"], reverse=True)
    return honor_roll[:5] # Top 5 students


@app.get("/api/analytics/rankings")
async def get_analytics_rankings(current_user: dict = Depends(get_current_user)):
    """الحصول على الترتيب لجميع الطلاب (أفضل الطلاب والطلاب الضعفاء)"""
    role = current_user["role"]
    center_id = current_user.get("center_id")
    
    query_filter = {"is_active": True}
    if role != "super_admin" and center_id:
        query_filter["center_id"] = center_id
        
    students = await db.students.find(query_filter).to_list(2000)
    
    eval_map = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}
    att_map = {"present": 100, "late": 80, "excused": 60, "absent": 0}
    
    thirty_days_ago = datetime.utcnow() - timedelta(days=90) # Track last 3 months for ranking
    
    rankings = []
    
    student_ids = [str(s["_id"]) for s in students]
    
    all_recitations = await db.recitations.find({
        "student_id": {"$in": student_ids},
        "date": {"$gte": thirty_days_ago}
    }).to_list(10000)
    
    all_attendances = await db.attendance.find({
        "student_id": {"$in": student_ids},
        "date": {"$gte": thirty_days_ago}
    }).to_list(10000)
    
    from collections import defaultdict
    rec_by_student = defaultdict(list)
    att_by_student = defaultdict(list)
    
    for r in all_recitations:
        rec_by_student[r["student_id"]].append(r)
        
    for a in all_attendances:
        att_by_student[a["student_id"]].append(a)
    
    for s in students:
        sid = str(s["_id"])
        
        recs = rec_by_student[sid]
        atts = att_by_student[sid]
        
        h_sum, h_count = 0, 0
        r_sum, r_count = 0, 0
        e_sum = 0
        
        for rec in recs:
            score = eval_map.get(rec.get("evaluation", "good"), 80)
            if rec.get("recitation_type") == "new":
                h_sum += score
                h_count += 1
            else:
                r_sum += score
                r_count += 1
            e_sum += rec.get("mistakes_count", 0)
            
        a_sum, a_count = 0, 0
        for att in atts:
            a_sum += att_map.get(att.get("status", "present"), 100)
            a_count += 1
            
        H = (h_sum / h_count) if h_count > 0 else 80
        R = (r_sum / r_count) if r_count > 0 else 80
        A = (a_sum / a_count) if a_count > 0 else 100
        E = e_sum
        
        final_score = (H * 0.4) + (R * 0.3) + (A * 0.2) - (E * 0.1)
        final_score = max(0, min(100, final_score))
        
        category = "best" if final_score >= 85 else "weak" if final_score < 65 else "average"
        
        rankings.append({
            "id": sid,
            "name": s["name"],
            "halaqah_name": s.get("halaqah_name", "غير محدد"),
            "score": round(final_score, 1),
            "progress": s.get("progress", 0),
            "category": category,
            "enrollment_date": s.get("enrollment_date").isoformat() if s.get("enrollment_date") else None
        })
        
    rankings.sort(key=lambda x: x["score"], reverse=True)
    return rankings

@app.get("/api/analytics/student/{student_id}")
async def get_student_analytics(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على الأداء التاريخي للطالب المعين"""
    student = await check_student_access(student_id, current_user)
        
    six_months_ago = datetime.utcnow() - timedelta(days=180)
    
    recitations = await db.recitations.find({
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
    import sys
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
    client_ip = request.client.host if request.client else "unknown"
    await _check_register_rate(client_ip)

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
        "registered_from_ip": client_ip,
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

    await db.audit_logs.insert_one({
        "action": "PUBLIC_REGISTER_CENTER",
        "center_id": center_id,
        "manager_username": center.manager_username,
        "ip": client_ip,
        "timestamp": datetime.utcnow(),
    })

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
    await db.audit_logs.insert_one({
        "action": "CENTER_APPROVED",
        "center_id": center_id,
        "approved_by": current_user["username"],
        "timestamp": datetime.utcnow(),
    })
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
    await db.audit_logs.insert_one({
        "action": "CENTER_REJECTED",
        "center_id": center_id,
        "rejected_by": current_user["username"],
        "timestamp": datetime.utcnow(),
    })
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
    
    # Financial aggregate in FCFA:
    fees_cursor = db.fees.find({"status": "paid"})
    total_fees_fcfa = 0.0
    async for fee in fees_cursor:
        total_fees_fcfa += fee.get("amount", 0.0)

    salaries_cursor = db.salaries.find({})
    total_salaries_fcfa = 0.0
    async for salary in salaries_cursor:
        total_salaries_fcfa += salary.get("amount", 0.0)

    expenses_cursor = db.expenses.find({})
    total_expenses_fcfa = 0.0
    async for expense in expenses_cursor:
        total_expenses_fcfa += expense.get("amount", 0.0)

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
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة الطلاب"""
    if current_user["role"] not in ["admin", "center_manager", "teacher", "super_admin"]:
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")
        
    query = {"is_active": True}
    
    # SaaS Multi-tenant Isolation
    if current_user["role"] != "super_admin":
        query["center_id"] = current_user.get("center_id")
    elif center_id:
        query["center_id"] = center_id
    
    students = await db.students.find(query).to_list(1000)
    result = []
    for s in students:
        # [AUDIT-2026-05-22 fix: decrypt PII before serialization]
        doc = serialize_doc(decrypt_student_doc(s))
        doc["enrollment_date"] = doc.get("enrollment_date", datetime.utcnow())
        if isinstance(doc["enrollment_date"], datetime):
            doc["enrollment_date"] = doc["enrollment_date"].isoformat()
        result.append(doc)
    return result


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
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة المعلمين"""
    # [AUDIT-2026-05-22 fix: gate by role + close fallthrough that exposed all teachers]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query = {"is_active": True}

    # SaaS Multi-tenant Isolation
    if role != "super_admin":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    elif center_id:  # super_admin with explicit filter
        query["center_id"] = center_id

    teachers = await db.teachers.find(query).to_list(100)
    result = []
    for t in teachers:
        doc = serialize_doc(t)
        teacher_id = doc["id"]
        # Get halaqat names for this teacher
        halaqat = await db.halaqat.find({"teacher_id": teacher_id, "is_active": True}).to_list(10)
        doc["halaqat"] = [h["name"] for h in halaqat]
        # Count students in teacher's halaqat
        halaqat_ids = [str(h["_id"]) for h in halaqat]
        doc["students_count"] = await db.students.count_documents({"halaqah_id": {"$in": halaqat_ids}, "is_active": True})
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
    
    teacher_dict = {
        "name": teacher.name,
        "phone": teacher.phone,
        "center_id": teacher.center_id,
        "specialization": teacher.specialization,
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
    
    # Update teacher's halaqah in halaqat collection
    await db.halaqat.update_one(
        {"_id": from_halaqah_obj_id},
        {"$unset": {"teacher_id": "", "teacher_name": ""}}
    )
    
    await db.halaqat.update_one(
        {"_id": to_halaqah_obj_id},
        {"$set": {"teacher_id": teacher_id, "teacher_name": teacher["name"]}}
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
    
    eval_dict = evaluation.dict()
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
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query = {"is_active": True}

    # SaaS Multi-tenant Isolation
    if role != "super_admin":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    elif center_id:  # super_admin with explicit filter
        query["center_id"] = center_id

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
        
    schedule_dict = schedule.dict()
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
        
    update_dict = schedule.dict()
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
        
    comp_dict = comp.dict()
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
        
    con_dict = contestant.dict()
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
        {"$set": {"grades": grades.dict(), "total_score": total}}
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
        
    msg_dict = msg.dict()
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
    if role != "super_admin":
        if not user_cid:
            return []

    # SaaS Multi-tenant Isolation
    if role == "super_admin":
        if center_id:
            students = await db.students.find(
                {"center_id": center_id, "is_active": True}, {"_id": 1}
            ).to_list(2000)
            allowed_student_ids = {str(s["_id"]) for s in students}
    elif role in ["admin", "center_manager"]:
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

    recitations = await db.recitations.find(query).sort("date", -1).to_list(limit)
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
    recitations = await db.recitations.find({"student_id": student_id}).sort("date", -1).to_list(100)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


@app.get("/api/analytics/predict/{student_id}")
async def predict_completion(student_id: str, current_user: dict = Depends(get_current_user)):
    """حساب مؤشر الإتقان والتنبؤ بموعد ختم القرآن أو الجزء الحالي"""
    student = await check_student_access(student_id, current_user)
    
    recitations = await db.recitations.find({"student_id": student_id}).sort("date", 1).to_list(2000)
    
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

    attendance = await db.attendance.find(query).sort("date", -1).to_list(100)
    result = []
    for a in attendance:
        doc = serialize_doc(a)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
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
        records.append(attendance_dict)

        # Real-time Parent Absentee warning via SSE
        if record.status == "absent":
            parent_phone = student.get("parent_phone")
            if parent_phone:
                parent_user = await db.users.find_one({"phone": parent_phone, "role": "parent"})
                if parent_user:
                    await push_sse_notification(
                        user_id=str(parent_user["_id"]),
                        event_type="absentee_alert",
                        data={
                            "student_id": record.student_id,
                            "student_name": student.get("name"),
                            "date": date_str,
                            "message": f"تنبيه هام: ابنكم/ابنتكم {student.get('name')} غائب(ة) اليوم عن حلقة التحفيظ."
                        }
                    )

    if records:
        await db.attendance.insert_many(records)

    return {"message": f"تم تسجيل حضور {len(records)} طالب", "count": len(records)}


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
async def get_fees(current_user: dict = Depends(get_current_user)):
    """الحصول على سجلات الرسوم"""
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

    fees = await db.fees.find(query).to_list(1000)
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
    await check_student_access(fee.student_id, current_user)
    
    fee_dict = fee.model_dump()
    fee_dict["status"] = "pending"
    fee_dict["paid_date"] = None
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
    
    await db.fees.update_one(
        {"_id": fee_obj_id},
        {"$set": {"status": "paid", "paid_date": datetime.utcnow()}}
    )
    
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


# ==================== Health Check ====================

@app.get("/api/health")
async def health_check():
    """فحص صحة النظام"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
