"""مساعدات مشتركة وفحوص الملكية."""

from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
from fastapi import HTTPException
from fastapi import Request
from fastapi import status
from typing import List
from typing import Optional

from app.config import TRUST_PROXY
from app.db import db


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

def serialize_doc(doc: dict) -> dict:
    """Convert MongoDB document to JSON-serializable dict"""
    if doc is None:
        return None
    doc = dict(doc)
    doc["id"] = str(doc.pop("_id"))
    return doc

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
        
    # 3. Teacher: الطالب من إحدى حلقاته هو، لا من مركزه فحسب
    # [إصلاح 2026-09-06] كان الشرط المركز وحده، فشيخُ الحلقة يقرأ ملفّ أيّ طالب
    # في المركز — اسمَه وهاتفَ وليّه وتسميعاتِه وحضورَه ومقاييسَ أدائه وتاريخَ
    # ختمه المتوقَّع — ولو كان في حلقة غيره. وهذه هي البوّابة التي تمرّ منها كل
    # نقاط النهاية التي تأخذ student_id، فالثغرة كانت واحدة والتسريب في عشرة.
    if role == "teacher":
        if student.get("center_id") != current_user.get("center_id"):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="غير مصرح لك بالوصول لبيانات هذا الطالب في مركز آخر"
            )
        from app.scope import teacher_halaqah_ids
        hids = await teacher_halaqah_ids(current_user)
        if not student.get("halaqah_id") or student["halaqah_id"] not in hids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="هذا الطالب ليس من حلقتك"
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
    # [2026-09-06] الربط بالمعرّف أوّلاً: حسابُ وليّ الأمر يُصدره المدير ويُكتب
    # معرّفُه على الطالب (parent_user_id)، فلا يبقى الربطُ معلّقاً برقم هاتفٍ
    # يتغيّر أو يُترك فارغاً. ومطابقةُ الهاتف تبقى للحسابات القديمة.
    if role == "parent":
        allowed = False
        uid = str(current_user.get("_id"))
        user_phone = current_user.get("phone")
        if student.get("parent_user_id") == uid:
            allowed = True
        elif user_phone and (
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

# الأدوار التي يُحدَّد وصولها لبيانات الطلاب عبر رقم الهاتف
_PHONE_SCOPED_ROLES = {"parent", "student"}

# [إصلاح 2026-09-03] مرشِّح الحذف الناعم للتسميعات.
# "$ne": True وليس "is_deleted": False — فالسجلات القديمة لا تحمل الحقل إطلاقاً،
# وشرط المساواة بـ False كان سيُخفيها كلها.
NOT_DELETED = {"is_deleted": {"$ne": True}}

# ==================== Dashboard Routes ====================

async def scoped_student_ids(center_id: Optional[str], cap: int = 20000) -> List[str]:
    """معرّفات طلاب مركز واحد — تُستعمل لتحديد نطاق الجداول التي لا تحمل center_id"""
    if not center_id:
        return []
    rows = await db.students.find({"center_id": center_id}, {"_id": 1}).to_list(cap)
    return [str(r["_id"]) for r in rows]

# [إصلاح 2026-09-04] المصروف لم يعد يُمحى.
# "$ne": True لا "== False" — فالصفوف القديمة لا تحمل الحقل إطلاقاً وشرطُ
# المساواة بـ False كان سيُخفيها كلها من كل مجموع.
NOT_VOIDED = {"voided": {"$ne": True}}
