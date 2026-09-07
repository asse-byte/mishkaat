"""نماذج الطلب والاستجابة (Pydantic)."""

from datetime import datetime
from pydantic import BaseModel
from pydantic import ConfigDict
from pydantic import field_validator
from typing import Dict
from typing import List
from typing import Literal
from typing import Optional


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
    # حسابا الطالب ووليّه — يُصدرهما المدير بعد التسجيل، والربط بالمعرّف
    user_id: Optional[str] = None
    parent_user_id: Optional[str] = None
    enrollment_date: datetime
    progress: float = 0
    current_surah: Optional[str] = None
    current_ayah: Optional[int] = None

class TeacherBase(BaseModel):
    name: str
    phone: Optional[str] = None
    center_id: str
    # [قرار المالك 2026-09-06] في المركز معلّمون ليسوا شيوخ حلقات: معلّم لغة،
    # ومعلّم تجويد يزور الحلقات، وإداريّ يُدرّس. كانوا يُسجَّلون محفّظين فتُطلب
    # لهم حلقة، أو لا يُسجَّلون أصلاً. و«الخارجي» ليس نطاقاً أوسع بل أضيق:
    # لا حلقة له، فلا طلاب في نطاقه — وهذا ما يقوله scope.py أصلاً.
    teacher_type: Literal["halaqah", "external"] = "halaqah"
    job_title: Optional[str] = None
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
    teacher_type: Optional[Literal["halaqah", "external"]] = None
    job_title: Optional[str] = None
    specialization: Optional[str] = None
    marital_status: Optional[Literal["single", "married", "divorced", "widowed"]] = None
    work_schedule: Optional[Literal["full_time", "part_time"]] = None
    salary: Optional[float] = None
    halaqah_id: Optional[str] = None
    is_active: Optional[bool] = None

class TeacherTransferRequest(BaseModel):
    from_halaqah_id: str
    to_halaqah_id: str

# تقييم المحفّظ — معايير المالك (2026-09-06).
#
# النظام يقيس الطالب بمقاييس ستّة ويترك المحفّظ بلا تقييم يُقرأ. وطلبُ المالك
# أن يُقاس المحفّظ كما يُقاس الطالب: بدرجات على معايير مسمّاة، ونقاط قوّة
# ونقاط ضعف مكتوبة — لا رقماً واحداً مبهماً لا يُعرف مِمّ تركّب.
#
# كل معيار من 10، والمجموع من 100. والمعايير مفتوحة للقراءة على صاحبها وحده:
# تقييمُ الرجل شأنُه، لا يُعرض على زملائه.
TEACHER_CRITERIA: Dict[str, str] = {
    "performance": "الأداء",
    "commitment": "الالتزام",
    "sincerity": "الإخلاص",
    "seriousness": "الجدّية",
    "diligence": "الاجتهاد",
}


class TeacherEvaluationBase(BaseModel):
    teacher_id: str
    evaluation_date: str

    # معايير المالك الخمسة — كلٌّ من 10
    performance: Optional[int] = None
    commitment: Optional[int] = None
    sincerity: Optional[int] = None
    seriousness: Optional[int] = None
    diligence: Optional[int] = None

    strengths: List[str] = []
    weaknesses: List[str] = []

    # المعايير القديمة — تبقى اختيارية لئلّا تسقط تقييماتٌ سابقة من القراءة
    attendance_rate: Optional[float] = None
    tajweed_proficiency: Optional[int] = None
    student_retention: Optional[int] = None
    average_memorization_speed: Optional[float] = None
    discipline: Optional[int] = None

    notes: Optional[str] = None

    @field_validator("performance", "commitment", "sincerity", "seriousness",
                     "diligence", mode="after")
    @classmethod
    def _ten_scale(cls, v):
        if v is not None and not (0 <= v <= 10):
            raise ValueError("الدرجة من 0 إلى 10")
        return v


class TeacherEvaluationCreate(TeacherEvaluationBase):
    pass


class TeacherEvaluationResponse(TeacherEvaluationBase):
    id: str
    center_id: str
    tpi: float
    teacher_name: Optional[str] = None
    evaluated_by: Optional[str] = None
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

# ==================== المسابقات القرآنية ====================
# [إعادة بناء 2026-09-06 — قرار المالك]
#
# الفروع منفصلة تماماً: كل فرع ترتيبُه ونتائجُه وحده، فلا يُقارَن حافظُ جزء عمّ
# بحافظ القرآن كاملاً. والفرع ليس نصّاً حرّاً بل قائمة مغلقة، وإلا كتبه كلُّ
# مركزٍ بصيغة مختلفة فتعذّر جمعُ النتائج أو أرشفتُها.
COMPETITION_BRANCHES = [
    "القرآن كاملاً",
    "15 جزءاً",
    "10 أجزاء",
    "5 أجزاء",
    "جزء عمّ",
]

CompetitionStatus = Literal["draft", "active", "grading", "approved", "archived"]


class CompetitionJudge(BaseModel):
    """عضو لجنة التحكيم: شيخُ حلقةٍ يُقيّم المتسابقين."""
    teacher_id: str
    teacher_name: Optional[str] = None


class CompetitionBase(BaseModel):
    title: str
    date: str
    year: Optional[int] = None
    branches: List[str] = COMPETITION_BRANCHES
    judges: List[CompetitionJudge] = []
    notes: Optional[str] = None


class CompetitionCreate(CompetitionBase):
    pass


class CompetitionUpdate(BaseModel):
    title: Optional[str] = None
    date: Optional[str] = None
    branches: Optional[List[str]] = None
    judges: Optional[List[CompetitionJudge]] = None
    notes: Optional[str] = None


class CompetitionResponse(CompetitionBase):
    id: str
    center_id: str
    status: CompetitionStatus = "active"
    approved_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    created_at: datetime
    # للتوافق مع الواجهة القديمة التي تقرأ categories
    categories: List[str] = []


class ContestantGrades(BaseModel):
    hifdh_score: float
    tajweed_score: float
    voice_score: float


class JudgeScore(BaseModel):
    """درجةُ محكّمٍ واحد. الدرجة النهائية متوسّط درجات اللجنة."""
    judge_teacher_id: str
    judge_name: Optional[str] = None
    hifdh_score: float
    tajweed_score: float
    voice_score: float
    total: float
    notes: Optional[str] = None
    graded_at: datetime


class CompetitionContestantBase(BaseModel):
    student_id: str
    category: str          # اسم الفرع
    notes: Optional[str] = None


class CompetitionContestantCreate(CompetitionContestantBase):
    pass


class CompetitionContestantResponse(CompetitionContestantBase):
    id: str
    competition_id: str
    center_id: str
    grades: Optional[ContestantGrades] = None
    judge_scores: List[JudgeScore] = []
    total_score: float = 0.0
    judges_count: int = 0
    rank_in_branch: Optional[int] = None
    student_name: Optional[str] = None
    halaqah_name: Optional[str] = None
    created_at: datetime

# ==================== الشهادات ====================
#
# [قرار المالك 2026-09-07] «مدير المركز هو الذي يصدر الشهادة للطالب وليس
# المعلّم. بعدما تُدخل اللجنة الدرجات يعتمدها المدير ثمّ يُصدر الشهادة. وحتى
# بعد ختم الطالب للقرآن يظهر إصدار الشهادة للحافظ، وكذلك بعد نصف القرآن
# و15 جزءاً.»
#
# والإصدار **فعلٌ يُسجَّل** لا زرَّ طباعةٍ عابر: له رقمٌ متسلسل، ومَن أصدره،
# ومتى. فشهادةٌ يُشكَّك فيها تُراجَع في السجلّ، ولا تُطبع مرّتين بلا علم.

MilestoneKind = Literal["juz5", "juz10", "half", "khatm"]

# الحدّ بالصفحات لا بالأجزاء: التسميع يُقاس بالصفحات، والجزء ≈ 20.13 صفحة.
MILESTONES: Dict[str, Dict[str, object]] = {
    "juz5":  {"label": "حفظ خمسة أجزاء",      "juz": 5,  "order": 1},
    "juz10": {"label": "حفظ عشرة أجزاء",      "juz": 10, "order": 2},
    "half":  {"label": "حفظ نصف القرآن الكريم", "juz": 15, "order": 3},
    "khatm": {"label": "ختم القرآن الكريم كاملاً", "juz": 30, "order": 4},
}

CertificateKind = Literal["competition", "milestone"]


class MilestoneCertificateCreate(BaseModel):
    student_id: str
    milestone: MilestoneKind
    notes: Optional[str] = None


class CertificateResponse(BaseModel):
    id: str
    serial: str
    kind: CertificateKind
    center_id: str
    center_name: Optional[str] = None
    student_id: str
    student_name: Optional[str] = None
    halaqah_name: Optional[str] = None
    title: str
    subtitle: Optional[str] = None
    # المسابقات
    competition_id: Optional[str] = None
    branch: Optional[str] = None
    rank: Optional[int] = None
    score: Optional[float] = None
    judges_names: List[str] = []
    # المحطّات
    milestone: Optional[str] = None
    pages_memorized: Optional[float] = None
    notes: Optional[str] = None
    issued_by: Optional[str] = None
    issued_by_name: Optional[str] = None
    issued_at: datetime


class MessageAttachment(BaseModel):
    """وثيقةٌ مرفقة برسالة — تُرفع أوّلاً ثمّ تُذكر أوصافُها هنا."""
    file_id: str
    filename: str
    content_type: Optional[str] = None
    size: Optional[int] = None


class MessageReply(BaseModel):
    teacher_id: str
    teacher_name: str
    content: str
    timestamp: datetime

class BulkMessageBase(BaseModel):
    recipient_role: str
    subject: str
    content: str
    attachments: List[MessageAttachment] = []

class BulkMessageCreate(BulkMessageBase):
    pass

class BulkMessageResponse(BulkMessageBase):
    id: str
    center_id: str
    sender_id: str
    sender_role: Optional[str] = None
    edited_at: Optional[datetime] = None
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

    # [إضافة 2026-09-05 — FR6 في تقرير Halaqtna] وسم الأخطاء بتصنيف مغلق موزون.
    # العدّادات الثلاثة أعلاه تبقى كما هي لتوافق البيانات والواجهات القديمة؛
    # error_tags حين يوجد يسبقها فلا يُحسب الخطأ مرّتين (errors_taxonomy).
    # القيمة: {رمز النوع: عدد الأخطاء}، والرموز يتحقّق منها المُصادِق أدناه.
    error_tags: Optional[Dict[str, int]] = None

    # عدد صفحات التسميعة. المقاييس الأدائية كلها لكل صفحة، والنطاق يُسجَّل
    # بالآيات — فإن تُرك فارغاً اشتُقّ من عدد الآيات، وهو تقريب معلَن.
    pages_count: Optional[float] = None

    @field_validator("error_tags")
    @classmethod
    def _check_error_tags(cls, v):
        if v is None:
            return v
        from app.errors_taxonomy import CODES
        cleaned = {}
        for code, count in v.items():
            if code not in CODES:
                raise ValueError(f"نوع خطأ غير معروف: {code}")
            n = int(count or 0)
            if n < 0:
                raise ValueError("عدد الأخطاء لا يكون سالباً")
            if n:
                cleaned[code] = n
        return cleaned

    @field_validator("pages_count")
    @classmethod
    def _check_pages(cls, v):
        if v is None:
            return v
        if v <= 0 or v > 604:
            raise ValueError("عدد الصفحات خارج المدى المعقول")
        return v

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

# [AUDIT-2026-05-22 fix: refresh-token rotation endpoint]
class RefreshRequest(BaseModel):
    # اختياري: المصدر الأول كعكة httpOnly، والجسم يبقى مقبولاً لعميل غير متصفّحي
    refresh_token: Optional[str] = None

class LogoutBody(BaseModel):
    refresh_token: Optional[str] = None

class ChangePasswordRequest(BaseModel):
    current_password: str
    new_password: str

class ForgotPasswordRequest(BaseModel):
    username: str

class ResetPasswordRequest(BaseModel):
    username: str
    code: str
    new_password: str

class AdminResetPasswordRequest(BaseModel):
    username: str
    new_password: str

class UpdateProfileRequest(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None

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

# ==================== Bulk Messaging Routes ====================

class ReplyPayload(BaseModel):
    content: str
