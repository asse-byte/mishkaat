"""المحفّظون وتقييماتهم."""

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import List
from typing import Optional

from app.audit import write_audit_log
from app.common import redact_teacher, safe_object_id, serialize_doc
from app.db import db
from app.models import TeacherCreate, TeacherEvaluationCreate, TeacherEvaluationResponse, TeacherTransferRequest, TeacherUpdate
from app.security import get_current_user, get_password_hash, validate_password_complexity

router = APIRouter()


# ==================== Teachers Routes ====================

@router.get("/api/teachers")
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

@router.post("/api/teachers")
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

@router.put("/api/teachers/{teacher_id}")
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

@router.post("/api/teachers/{teacher_id}/transfer")
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

@router.delete("/api/teachers/{teacher_id}")
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

@router.post("/api/teachers/{teacher_id}/evaluations", response_model=TeacherEvaluationResponse)
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

@router.get("/api/teachers/{teacher_id}/evaluations", response_model=List[TeacherEvaluationResponse])
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
