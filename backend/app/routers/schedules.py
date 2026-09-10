"""الجدول الدراسي."""

from app.clock import utcnow

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from typing import List

from app.common import safe_object_id, serialize_doc
from app.db import db
from app.models import AcademicScheduleCreate, AcademicScheduleResponse
from app.scope import assert_halaqah_in_scope, visible_halaqah_ids
from app.security import get_current_user

router = APIRouter()


# ==================== Academic Schedules Routes ====================

@router.post("/api/academic-schedules", response_model=AcademicScheduleResponse)
async def create_academic_schedule(schedule: AcademicScheduleCreate, current_user: dict = Depends(get_current_user)):
    """إنشاء موعد دراسي أكاديمي جديد"""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    
    center_id = current_user.get("center_id")
    if current_user["role"] in ["admin", "super_admin"] and not center_id:
        center_id = schedule.center_id or "default"
        
    if not center_id:
        raise HTTPException(status_code=400, detail="يجب تحديد المركز")

    # [إصلاح 2026-09-06] كان أيّ شيخ يُضيف حصّة إلى جدول أيّ حلقة في المركز.
    await assert_halaqah_in_scope(schedule.halaqa_id, current_user)

    schedule_dict = schedule.model_dump()
    schedule_dict["center_id"] = center_id
    schedule_dict["created_at"] = utcnow()
    
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

@router.get("/api/academic-schedules", response_model=List[AcademicScheduleResponse])
async def get_academic_schedules(current_user: dict = Depends(get_current_user)):
    """الحصول على الجدول الدراسي الأكاديمي للمركز"""
    role = current_user["role"]
    query = {}
    if role != "super_admin":
        center_id = current_user.get("center_id")
        if not center_id:
            return []
        query["center_id"] = center_id

    # [إصلاح 2026-09-06] كان الجدول يُعرض للمركز كلّه، فيرى شيخُ الحلقة حصصَ
    # حلقات غيره وأسماءَ شيوخها، ويرى الطالبُ جدولَ حلقات ليس فيها. الجدول
    # يخصّ الحلقة، فيُحصر بحلقات النطاق.
    hids = await visible_halaqah_ids(current_user)
    if hids is not None:
        if not hids:
            return []
        query["halaqa_id"] = {"$in": hids}

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

@router.put("/api/academic-schedules/{schedule_id}", response_model=AcademicScheduleResponse)
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

    # [إصلاح 2026-09-06] المركز لا يكفي: الحصّة تخصّ حلقة، والشيخ لا يمسّ جدول
    # حلقة غيره.
    if existing.get("halaqa_id"):
        await assert_halaqah_in_scope(existing["halaqa_id"], current_user)
        
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

@router.delete("/api/academic-schedules/{schedule_id}")
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

    # [إصلاح 2026-09-06] المركز لا يكفي: الحصّة تخصّ حلقة، والشيخ لا يمسّ جدول
    # حلقة غيره.
    if existing.get("halaqa_id"):
        await assert_halaqah_in_scope(existing["halaqa_id"], current_user)
        
    await db.academic_schedules.delete_one({"_id": schedule_obj_id})
    return {"message": "تم حذف الموعد الدراسي بنجاح"}
