"""الطلاب."""

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import Optional
import re

from app.common import check_student_access, safe_object_id, serialize_doc
from app.db import db
from app.models import StudentCreate, StudentUpdate
from app.pii import decrypt_student_doc, encrypt_student_doc
from app.security import get_current_user

router = APIRouter()


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

@router.get("/api/students/{student_id}")
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

@router.post("/api/students")
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
    doc["enrollment_date"] = doc.get("enrollment_date", datetime.utcnow())
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
