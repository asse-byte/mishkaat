"""الطلاب."""

from app.clock import utcnow

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import Optional
import re

from app.common import NOT_DELETED, check_student_access, safe_object_id, serialize_doc
from app.config import TOTAL_QURAN_PAGES, VERSES_PER_PAGE
from app.db import db
from app.models import StudentCreate, StudentUpdate
from app.pii import decrypt_student_doc, encrypt_student_doc
from app.scope import student_query, teacher_halaqah_ids
from app.security import get_current_user

router = APIRouter()


async def memorization_progress(student_ids: list) -> dict:
    """
    [إصلاح 2026-10-22] نسبة الحفظ والسورة الحالية محسوبتان من التسميع.

    كانت `progress` و`current_surah` حقلين يُكتبان صفراً عند التسجيل ولا يحدّثهما
    شيء بعد ذلك، فتعرض لوحة الطالب «0 / 30 جزءاً» ولوحة وليّ الأمر «الحفظ 0%» مهما
    سمّع. الحساب هنا هو حساب metrics.pages_memorized نفسه (صفحات الحفظ الجديد:
    المُدخَلة صراحةً، وإلا آيات النطاق ÷ VERSES_PER_PAGE)، بتجميعٍ واحد للقائمة كلّها.
    """
    if not student_ids:
        return {}
    verses = {"$max": [1, {"$add": [{"$subtract": ["$end_ayah", "$start_ayah"]}, 1]}]}
    pages = {"$cond": [{"$gt": [{"$ifNull": ["$pages_count", 0]}, 0]},
                       "$pages_count", {"$divide": [verses, VERSES_PER_PAGE]}]}
    rows = db.recitations.aggregate([
        {"$match": {**NOT_DELETED, "student_id": {"$in": student_ids},
                    "recitation_type": {"$ne": "review"}}},
        {"$sort": {"date": 1}},
        {"$group": {"_id": "$student_id", "pages": {"$sum": pages},
                    "surah": {"$last": "$surah_name"}, "ayah": {"$last": "$end_ayah"}}},
    ])
    out = {}
    async for r in rows:
        out[r["_id"]] = {
            "progress": round(min(100.0, 100.0 * r["pages"] / TOTAL_QURAN_PAGES), 1),
            "current_surah": r.get("surah"),
            "current_ayah": r.get("ayah"),
        }
    return out


# ==================== Students Routes ====================

@router.get("/api/students")
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

    # [إصلاح 2026-09-06] النطاق من scope.student_query لا من نسخةٍ محلّية.
    # كانت هذه الدالة تعيد بناء قواعد كل دور بنفسها، فتباعدت عن المصدر: وليّ
    # الأمر كان يُطابَق برقم هاتفه وحده، فحسابٌ أصدره المدير ورُبط بالمعرّف
    # (parent_user_id) بلا هاتفٍ مسجَّل يرى قائمةً فارغة ولا يفهم لماذا.
    base: dict = {"is_active": True}
    if role in ["super_admin", "admin"] and center_id:
        base["center_id"] = center_id

    query = await student_query(current_user, base)
    if query is None:
        return []

    if halaqah_id:
        # المحفّظ لا يوسّع نطاقه بتمرير حلقة غيره في المعامل
        if role == "teacher" and halaqah_id not in (query.get("halaqah_id", {}).get("$in") or []):
            return []
        # فلترة الحلقة تُطبَّق فوق نطاق الدور، فلا تُوسِّعه
        query["halaqah_id"] = halaqah_id

    if search:
        # [AUDIT-2026-09-03 fix: يجب تهريب رموز الـ regex وإلا صار البحث تعبيراً نمطياً
        #  يتحكم به المستخدم (استنزاف للمعالج بـ ReDoS)]
        safe = re.escape(search.strip())
        if safe:
            query["name"] = {"$regex": safe, "$options": "i"}

    students = await db.students.find(query).skip(skip).limit(limit).to_list(limit)
    progress = await memorization_progress([str(s["_id"]) for s in students])
    result = []
    for s in students:
        # [AUDIT-2026-05-22 fix: decrypt PII before serialization]
        doc = serialize_doc(decrypt_student_doc(s))
        doc.update(progress.get(doc["id"], {}))
        doc["enrollment_date"] = doc.get("enrollment_date", utcnow())
        if isinstance(doc["enrollment_date"], datetime):
            doc["enrollment_date"] = doc["enrollment_date"].isoformat()
        result.append(doc)
    return result

@router.get("/api/students/{student_id}")
async def get_student(student_id: str, current_user: dict = Depends(get_current_user)):
    """
    [AUDIT-2026-09-03 addition] جلب طالب واحد — كانت الواجهة تستدعيها (studentsApi.getById)
    ولا وجود لها في الخادم، فتُرجع 404 دائماً. تمرّ عبر نفس فحص الملكية.
    """
    student = await check_student_access(student_id, current_user)
    doc = serialize_doc(decrypt_student_doc(student))
    doc.update((await memorization_progress([doc["id"]])).get(doc["id"], {}))
    if isinstance(doc.get("enrollment_date"), datetime):
        doc["enrollment_date"] = doc["enrollment_date"].isoformat()
    return doc

@router.post("/api/students")
async def create_student(student: StudentCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء طالب جديد"""
    if current_user["role"] not in ["admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
        
    # [AUDIT-2026-05-22 fix: secure BOLA center isolation]
    if current_user["role"] != "admin" and student.center_id != current_user.get("center_id"):
        raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء طالب في مركز آخر")
    
    student_dict = student.model_dump()
    enrollment_date = utcnow()
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

@router.put("/api/students/{student_id}")
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
    await db.students.update_one(
        {"_id": student_obj_id},
        {"$set": encrypt_student_doc(update_data)}
    )

    updated = await db.students.find_one({"_id": student_obj_id})
    # [AUDIT-2026-05-22 fix: decrypt PII for the response]
    doc = serialize_doc(decrypt_student_doc(updated))
    doc["enrollment_date"] = doc.get("enrollment_date", utcnow())
    if isinstance(doc["enrollment_date"], datetime):
        doc["enrollment_date"] = doc["enrollment_date"].isoformat()
    return doc

@router.delete("/api/students/{student_id}")
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
