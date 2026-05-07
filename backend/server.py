"""
نظام إدارة مراكز تحفيظ القرآن الكريم
Quran Memorization Center Management System
"""

from fastapi import FastAPI, HTTPException, Depends, status, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime, timedelta
from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorClient
import os
import secrets
from dotenv import load_dotenv
import jwt
from passlib.context import CryptContext
import logging

load_dotenv()

logger = logging.getLogger("uvicorn.error")

# Configuration
MONGO_URL = os.getenv("MONGO_URL", "mongodb://localhost:27017")
DB_NAME = os.getenv("DB_NAME", "quran_center")
# مفتاح سري قوي: 64 بايت - يمكن تغييره في .env للإنتاج
SECRET_KEY = os.getenv(
    "SECRET_KEY",
    "9f4a2e8b1d6c3f7a0e5b2d9c4f1a8e3b6d0c7f2a5e8b1d4c9f3a6e0b7d2c5f8a1e"
)
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days
MAX_LOGIN_ATTEMPTS = 5          # أقصى محاولات

LOCKOUT_MINUTES = 15            # مدة الحظر بالدقائق

# Password hashing - bcrypt_rounds=8 للسرعة
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto", bcrypt__rounds=8)

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

UserRole = Literal["admin", "center_manager", "teacher", "student", "parent"]
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


class TokenData(BaseModel):
    username: Optional[str] = None


class CenterBase(BaseModel):
    name: str
    address: str
    phone: Optional[str] = None
    is_active: bool = True


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


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


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


async def get_current_user(token: str = Depends(oauth2_scheme)) -> dict:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except jwt.PyJWTError:
        raise credentials_exception
    
    user = await get_user_by_username(username)
    if user is None:
        raise credentials_exception
    return user


def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc


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
    
    # Upsert all default users (أضف أو تجاهل إذا كان موجوداً)

    default_users = [
        {
            "username": "admin",
            "name": "مدير النظام",
            "email": "admin@quran-center.com",
            "role": "admin",
            "hashed_password": get_password_hash("admin123"),
            "is_active": True,
            "created_at": datetime.utcnow()
        },
        {
            "username": "manager1",
            "name": "أحمد محمد - مدير المركز",
            "email": "manager@quran-center.com",
            "role": "center_manager",
            "center_id": "center_1",
            "hashed_password": get_password_hash("manager123"),
            "is_active": True,
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
            "created_at": datetime.utcnow()
        },
        {
            "username": "parent1",
            "name": "أبو أحمد",
            "email": "parent@quran-center.com",
            "role": "parent",
            "hashed_password": get_password_hash("parent123"),
            "is_active": True,
            "created_at": datetime.utcnow()
        }
    ]
    for u in default_users:
        await db.users.update_one(
            {"username": u["username"]},
            {"$setOnInsert": u},
            upsert=True
        )
    print("✅ Default users ensured")

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
        
        print(f"✅ Default centers created: {center_ids}")
        
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
        print(f"✅ Default teachers created: {teacher_ids}")
        
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
        print(f"✅ Default halaqat created: {halaqah_ids}")
        
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
        
        print("✅ Default students created")


# ==================== Auth Routes ====================

# قاموس تتبع محاولات تسجيل الدخول الفاشلة {ip: {count, locked_until}}
_login_attempts: dict = {}

def _check_rate_limit(ip: str):
    """فحص حد معدل محاولات تسجيل الدخول"""
    now = datetime.utcnow()
    info = _login_attempts.get(ip, {"count": 0, "locked_until": None})
    if info["locked_until"] and now < info["locked_until"]:
        remaining = int((info["locked_until"] - now).total_seconds() / 60) + 1
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail=f"تم تجاوز عدد المحاولات. حاول مرة أخرى بعد {remaining} دقيقة"
        )

def _record_failed_attempt(ip: str):
    """تسجيل محاولة فاشلة"""
    now = datetime.utcnow()
    info = _login_attempts.get(ip, {"count": 0, "locked_until": None})
    info["count"] = info.get("count", 0) + 1
    if info["count"] >= MAX_LOGIN_ATTEMPTS:
        info["locked_until"] = now + timedelta(minutes=LOCKOUT_MINUTES)
        logger.warning(f"تم قفل IP: {ip} بعد {MAX_LOGIN_ATTEMPTS} محاولات فاشلة")
    _login_attempts[ip] = info

def _clear_attempts(ip: str):
    """مسح محاولات IP بعد نجاح الدخول"""
    _login_attempts.pop(ip, None)

@app.post("/api/auth/login", response_model=Token)
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    """تسجيل الدخول مع حماية Rate Limiting"""
    client_ip = request.client.host if request.client else "unknown"
    _check_rate_limit(client_ip)

    user = await authenticate_user(form_data.username, form_data.password)
    if not user:
        _record_failed_attempt(client_ip)
        # تسجيل المحاولة الفاشلة في سجل النشاط
        await db.audit_logs.insert_one({
            "action": "LOGIN_FAILED",
            "username": form_data.username,
            "ip": client_ip,
            "timestamp": datetime.utcnow()
        })
        attempts_left = MAX_LOGIN_ATTEMPTS - _login_attempts.get(client_ip, {}).get("count", 0)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"اسم المستخدم أو كلمة المرور غير صحيحة ({max(0, attempts_left)} محاولات متبقية)",
            headers={"WWW-Authenticate": "Bearer"},
        )

    _clear_attempts(client_ip)
    # تسجيل الدخول الناجح
    await db.audit_logs.insert_one({
        "action": "LOGIN_SUCCESS",
        "username": user["username"],
        "role": user["role"],
        "ip": client_ip,
        "timestamp": datetime.utcnow()
    })

    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user["username"]},
        expires_delta=access_token_expires
    )

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
        user=user_response
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


@app.post("/api/auth/logout")
async def logout(request: Request, current_user: dict = Depends(get_current_user)):
    """تسجيل الخروج"""
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
    if len(data.new_password) < 8:
        raise HTTPException(status_code=400, detail="كلمة المرور الجديدة يجب أن تكون 8 أحرف على الأقل")
    new_hash = get_password_hash(data.new_password)
    await db.users.update_one(
        {"_id": current_user["_id"]},
        {"$set": {"hashed_password": new_hash}}
    )
    await db.audit_logs.insert_one({
        "action": "PASSWORD_CHANGED",
        "username": current_user["username"],
        "timestamp": datetime.utcnow()
    })
    return {"message": "تم تغيير كلمة المرور بنجاح"}


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
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح لك بالوصول")

    logs = await db.audit_logs.find().sort("timestamp", -1).skip(skip).limit(limit).to_list(limit)
    return [{**serialize_doc(log)} for log in logs]


# ==================== Dashboard Routes ====================

@app.get("/api/dashboard/stats")
async def get_dashboard_stats(current_user: dict = Depends(get_current_user)):
    """الحصول على إحصائيات لوحة التحكم"""
    role = current_user["role"]
    center_id = current_user.get("center_id")
    
    query_filter = {}
    if role in ["center_manager", "teacher"] and center_id:
        query_filter["center_id"] = center_id
    
    total_students = await db.students.count_documents({**query_filter, "is_active": True})
    total_teachers = await db.teachers.count_documents({**query_filter, "is_active": True})
    total_centers = await db.centers.count_documents({"is_active": True})
    total_halaqat = await db.halaqat.count_documents({**query_filter, "is_active": True})
    pending_fees = await db.fees.count_documents({"status": "pending"})
    
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
    if role in ["center_manager", "teacher"] and center_id:
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
    if role in ["center_manager", "teacher"] and center_id:
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
    student = await db.students.find_one({"_id": ObjectId(student_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
        
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
        "student": serialize_doc(student),
        "timeline": timeline_list
    }


# ==================== Centers Routes ====================

@app.get("/api/centers")
async def get_centers(current_user: dict = Depends(get_current_user)):
    """الحصول على قائمة المراكز مع إحصائيات"""
    centers = await db.centers.find({"is_active": True}).to_list(100)
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


@app.post("/api/public/register-center")
async def public_register_center(center: CenterCreate):
    """تسجيل مركز جديد بشكل عام ومستقل"""
    center_dict = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
        "manager_name": center.manager_name,
        "is_active": True,
        "created_at": datetime.utcnow(),
    }
    
    # Create manager account
    if not center.manager_username or not center.manager_password:
        raise HTTPException(status_code=400, detail="يجب إدخال اسم المستخدم وكلمة المرور للمدير")
        
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
        "created_at": datetime.utcnow()
    }
    manager_result = await db.users.insert_one(manager_user)
    center_dict["manager_id"] = str(manager_result.inserted_id)
    
    result = await db.centers.insert_one(center_dict)
    center_id = str(result.inserted_id)
    
    # Update manager's center_id
    await db.users.update_one(
        {"_id": ObjectId(center_dict["manager_id"])},
        {"$set": {"center_id": center_id}}
    )
    
    return {
        "id": center_id,
        "name": center_dict["name"],
        "message": "تم إكمال التسجيل بنجاح. يمكنك الآن تسجيل الدخول."
    }


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
    
    update_data = {
        "name": center.name,
        "address": center.address,
        "phone": center.phone,
    }
    if center.manager_name:
        update_data["manager_name"] = center.manager_name
    
    result = await db.centers.update_one(
        {"_id": ObjectId(center_id)},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    
    updated = await db.centers.find_one({"_id": ObjectId(center_id)})
    return serialize_doc(updated)


@app.delete("/api/centers/{center_id}")
async def delete_center(center_id: str, current_user: dict = Depends(get_current_user)):
    """حذف مركز (تعطيل)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.centers.update_one(
        {"_id": ObjectId(center_id)},
        {"$set": {"is_active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    return {"message": "تم حذف المركز بنجاح"}


@app.get("/api/centers/{center_id}/details")
async def get_center_details(center_id: str, current_user: dict = Depends(get_current_user)):
    """تفاصيل مركز واحد مع كامل البيانات"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    center = await db.centers.find_one({"_id": ObjectId(center_id)})
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


# ==================== Students Routes ====================

@app.get("/api/students")
async def get_students(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة الطلاب"""
    query = {"is_active": True}
    
    # Filter by center for managers/teachers
    if current_user["role"] in ["center_manager", "teacher"] and current_user.get("center_id"):
        query["center_id"] = current_user["center_id"]
    elif center_id:
        query["center_id"] = center_id
    
    students = await db.students.find(query).to_list(1000)
    result = []
    for s in students:
        doc = serialize_doc(s)
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
    
    student_dict = student.model_dump()
    enrollment_date = datetime.utcnow()
    student_dict["enrollment_date"] = enrollment_date
    student_dict["progress"] = 0
    student_dict["current_surah"] = None
    student_dict["current_ayah"] = None
    
    result = await db.students.insert_one(student_dict)
    
    # Update halaqah student count
    if student.halaqah_id:
        try:
            count = await db.students.count_documents({"halaqah_id": student.halaqah_id, "is_active": True})
            await db.halaqat.update_one(
                {"_id": ObjectId(student.halaqah_id)},
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
    
    update_data = {k: v for k, v in student.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
    
    result = await db.students.update_one(
        {"_id": ObjectId(student_id)},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    updated = await db.students.find_one({"_id": ObjectId(student_id)})
    doc = serialize_doc(updated)
    doc["enrollment_date"] = doc.get("enrollment_date", datetime.utcnow())
    if isinstance(doc["enrollment_date"], datetime):
        doc["enrollment_date"] = doc["enrollment_date"].isoformat()
    return doc


@app.delete("/api/students/{student_id}")
async def delete_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """حذف طالب (تعطيل)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    # Get student to find halaqah
    student = await db.students.find_one({"_id": ObjectId(student_id)})
    if not student:
        raise HTTPException(status_code=404, detail="الطالب غير موجود")
    
    await db.students.update_one(
        {"_id": ObjectId(student_id)},
        {"$set": {"is_active": False}}
    )
    
    # Update halaqah count
    if student.get("halaqah_id"):
        try:
            count = await db.students.count_documents({"halaqah_id": student["halaqah_id"], "is_active": True})
            await db.halaqat.update_one(
                {"_id": ObjectId(student["halaqah_id"])},
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
    query = {"is_active": True}
    
    if current_user["role"] in ["center_manager", "teacher"] and current_user.get("center_id"):
        query["center_id"] = current_user["center_id"]
    elif center_id:
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
    
    update_data = {k: v for k, v in teacher.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
    
    result = await db.teachers.update_one(
        {"_id": ObjectId(teacher_id)},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    updated = await db.teachers.find_one({"_id": ObjectId(teacher_id)})
    return serialize_doc(updated)


@app.post("/api/teachers/{teacher_id}/transfer")
async def transfer_teacher(teacher_id: str, data: TeacherTransferRequest, current_user: dict = Depends(get_current_user)):
    """نقل محفظ من حلقة إلى حلقة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    # Update teacher's halaqah in halaqat collection
    await db.halaqat.update_one(
        {"_id": ObjectId(data.from_halaqah_id)},
        {"$unset": {"teacher_id": "", "teacher_name": ""}}
    )
    teacher = await db.teachers.find_one({"_id": ObjectId(teacher_id)})
    if not teacher:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    
    to_halaqah = await db.halaqat.find_one({"_id": ObjectId(data.to_halaqah_id)})
    if not to_halaqah:
        raise HTTPException(status_code=404, detail="الحلقة الهدف غير موجودة")
    
    await db.halaqat.update_one(
        {"_id": ObjectId(data.to_halaqah_id)},
        {"$set": {"teacher_id": teacher_id, "teacher_name": teacher["name"]}}
    )
    return {"message": f"تم نقل المحفظ {teacher['name']} إلى {to_halaqah['name']} بنجاح"}


@app.delete("/api/teachers/{teacher_id}")
async def delete_teacher(teacher_id: str, current_user: dict = Depends(get_current_user)):
    """حذف معلم (تعطيل)"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.teachers.update_one(
        {"_id": ObjectId(teacher_id)},
        {"$set": {"is_active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="المعلم غير موجود")
    return {"message": "تم حذف المعلم بنجاح"}


# ==================== Halaqat Routes ====================

@app.get("/api/halaqat")
async def get_halaqat(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على قائمة الحلقات"""
    query = {"is_active": True}
    
    if current_user["role"] in ["center_manager", "teacher"] and current_user.get("center_id"):
        query["center_id"] = current_user["center_id"]
    elif center_id:
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
    
    update_data = {k: v for k, v in halaqah.model_dump().items() if v is not None}
    if not update_data:
        raise HTTPException(status_code=400, detail="لا توجد بيانات للتحديث")
    
    result = await db.halaqat.update_one(
        {"_id": ObjectId(halaqah_id)},
        {"$set": update_data}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")
    
    updated = await db.halaqat.find_one({"_id": ObjectId(halaqah_id)})
    return serialize_doc(updated)


@app.delete("/api/halaqat/{halaqah_id}")
async def delete_halaqah(halaqah_id: str, current_user: dict = Depends(get_current_user)):
    """حذف حلقة"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    result = await db.halaqat.update_one(
        {"_id": ObjectId(halaqah_id)},
        {"$set": {"is_active": False}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")
    return {"message": "تم حذف الحلقة بنجاح"}


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
    query = {}
    
    # مدير المركز: يرى جميع تسميعات مركزه
    if current_user["role"] == "center_manager" and current_user.get("center_id"):
        # Get all students in this center and filter by them
        students = await db.students.find({"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}).to_list(1000)
        student_ids = [str(s["_id"]) for s in students]
        if student_ids:
            query["student_id"] = {"$in": student_ids}
    elif current_user["role"] == "teacher" and current_user.get("center_id"):
        # المعلم: يرى تسميعاته هو فقط
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if teacher:
            query["teacher_id"] = str(teacher["_id"])
    elif current_user["role"] == "student":
        # الطالب: يرى تسميعاته فقط
        student = await db.students.find_one({"user_id": str(current_user["_id"])}) if False else None
        pass
    
    if halaqah_id:
        query["halaqah_id"] = halaqah_id
    if student_id:
        query["student_id"] = student_id
    if center_id and current_user["role"] == "admin":
        students = await db.students.find({"center_id": center_id, "is_active": True}, {"_id": 1}).to_list(1000)
        student_ids = [str(s["_id"]) for s in students]
        if student_ids:
            query["student_id"] = {"$in": student_ids}
    
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
        "notes": recitation_dict.get("notes"),
        "recitation_type": recitation_dict["recitation_type"],
        "date": recitation_dict["date"].isoformat()
    }


@app.get("/api/recitations/student/{student_id}")
async def get_student_recitations(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على تسميعات طالب محدد"""
    recitations = await db.recitations.find({"student_id": student_id}).sort("date", -1).to_list(100)
    result = []
    for r in recitations:
        doc = serialize_doc(r)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


# ==================== Attendance Routes ====================

@app.get("/api/attendance")
async def get_attendance(
    halaqah_id: Optional[str] = None,
    date: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على سجلات الحضور"""
    query = {}
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
    
    records = []
    for record in data.records:
        attendance_dict = record.model_dump()
        attendance_dict["date"] = now
        attendance_dict["date_str"] = date_str
        records.append(attendance_dict)
    
    if records:
        await db.attendance.insert_many(records)
    
    return {"message": f"تم تسجيل حضور {len(records)} طالب", "count": len(records)}


@app.get("/api/attendance/student/{student_id}")
async def get_student_attendance(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على سجل حضور طالب"""
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
    fees = await db.fees.find().to_list(100)
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
    
    result = await db.fees.update_one(
        {"_id": ObjectId(fee_id)},
        {"$set": {"status": "paid", "paid_date": datetime.utcnow()}}
    )
    if result.modified_count == 0:
        raise HTTPException(status_code=404, detail="الرسوم غير موجودة")
    
    fee = await db.fees.find_one({"_id": ObjectId(fee_id)})
    doc = serialize_doc(fee)
    if doc.get("paid_date") and isinstance(doc["paid_date"], datetime):
        doc["paid_date"] = doc["paid_date"].isoformat()
    return doc


@app.get("/api/fees/student/{student_id}")
async def get_student_fees(student_id: str, current_user: dict = Depends(get_current_user)):
    """الحصول على رسوم طالب"""
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
    query = {}
    if current_user["role"] == "center_manager" and current_user.get("center_id"):
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
    salary_dict = salary.model_dump()
    salary_dict["created_at"] = datetime.utcnow()
    salary_dict["status"] = "paid"
    result = await db.salaries.insert_one(salary_dict)
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
    query = {}
    if current_user["role"] == "center_manager" and current_user.get("center_id"):
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
    exp_dict = expense.model_dump()
    exp_dict["created_at"] = datetime.utcnow()
    result = await db.expenses.insert_one(exp_dict)
    doc = exp_dict.copy()
    doc["id"] = str(result.inserted_id)
    doc["created_at"] = doc["created_at"].isoformat()
    return doc


@app.delete("/api/expenses/{expense_id}")
async def delete_expense(expense_id: str, current_user: dict = Depends(get_current_user)):
    """حذف مصروف"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    await db.expenses.delete_one({"_id": ObjectId(expense_id)})
    return {"message": "تم حذف المصروف"}


# ==================== Review Plans (خطط المراجعة) ====================

@app.get("/api/review-plans")
async def get_review_plans(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على خطط المراجعة"""
    query = {}
    if current_user["role"] == "center_manager" and current_user.get("center_id"):
        query["center_id"] = current_user["center_id"]
    elif current_user["role"] == "teacher" and current_user.get("center_id"):
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if teacher:
            query["teacher_id"] = str(teacher["_id"])
    elif center_id and current_user["role"] == "admin":
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
async def create_review_plan(data: dict, current_user: dict = Depends(get_current_user)):
    """إضافة خطة مراجعة"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
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
    
    query = {}
    if current_user["role"] == "center_manager" and current_user.get("center_id"):
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
