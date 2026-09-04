"""الحلقات."""

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from typing import Optional

from app.common import safe_object_id, serialize_doc
from app.db import db
from app.models import HalaqahCreate, HalaqahUpdate
from app.security import get_current_user

router = APIRouter()


# ==================== Halaqat Routes ====================

@router.get("/api/halaqat")
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

@router.post("/api/halaqat")
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

@router.put("/api/halaqat/{halaqah_id}")
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

@router.delete("/api/halaqat/{halaqah_id}")
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
