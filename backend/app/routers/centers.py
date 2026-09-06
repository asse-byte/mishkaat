"""المراكز والإشراف العام."""

import re
from app.clock import utcnow

from bson import ObjectId
from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Request
from fastapi import Response
from fastapi import UploadFile
from fastapi import File
import sys

from app.audit import write_audit_log
from app.common import client_ip, safe_object_id, serialize_doc, NOT_VOIDED
from app.config import DB_NAME
from app.db import db
from app.files import IMAGE_TYPES, MAX_LOGO_BYTES, delete_file, read_file, save_upload
from pymongo.errors import DuplicateKeyError
from app.routers.finance import _sum_amounts
from app.models import CenterCreate, SuperCenterCreate, SuperCenterStatusUpdate
from app.security import _check_register_rate, _record_register_attempt, get_current_user, get_password_hash, validate_password_complexity

router = APIRouter()

# تحقّق كافٍ من شكل البريد بلا تبعية إضافية: email-validator غير مثبَّتة،
# و EmailStr في Pydantic تعتمد عليها فتُسقط الإقلاع كلَّه لو استُعملت.
_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s.]+(\.[^@\s.]+)+$")


# ==================== Centers Routes ====================

@router.get("/api/centers")
async def get_centers(current_user: dict = Depends(get_current_user)):
    """الحصول على قائمة المراكز مع إحصائيات"""
    role = current_user["role"]
    # [إصلاح 2026-09-06] كان الشرط "غير super_admin ⇐ احصره في مركزه"، ومدير
    # النظام (admin) دورٌ عامّ بلا center_id — فكان يرى صفراً من خمسة مراكز.
    # وهو صاحب الاعتماد والرفض وإنشاء المراكز، فلا معنى لأن تكون قائمتُه فارغة.
    #
    # ويرى المعلَّقة وغير المفعّلة أيضاً: لو حُجبت عنه لما وجد ما يعتمده أصلاً.
    # الأدوار المحصورة (مدير مركز، محفّظ) تبقى على مركزها وعلى المفعَّل وحده.
    centers_query: dict = {}
    if role in ("admin", "super_admin"):
        pass
    else:
        centers_query["is_active"] = True
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
            center_data["created_at"] = utcnow().isoformat()
        else:
            center_data["created_at"] = center_data["created_at"].isoformat() if isinstance(center_data["created_at"], datetime) else center_data["created_at"]
        result.append(center_data)
    return result

@router.get("/api/public/best-centers")
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

@router.get("/api/admin/system/status")
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
    
    active_rate_locks = await db.login_attempts.count_documents({"locked_until": {"$gt": utcnow()}})
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

@router.post("/api/public/register-center")
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
    # [إصلاح 2026-09-06] الحقل كان يُشترط وجودُه ولا يُتحقّق من شكله، والرسالة
    # تقول إنه «للتحقق» — فيُقبل «أ» بريداً ولا يصل إلى صاحبه شيء أبداً.
    if not _EMAIL_RE.match(center.manager_email.strip()):
        raise HTTPException(status_code=400, detail="صيغة البريد الإلكتروني غير صحيحة")

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
        "created_at": utcnow(),
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
        "created_at": utcnow(),
    }
    # [إصلاح 2026-09-06] فحصُ الاسم أعلاه لا يمنع السباق: طلبان متزامنان
    # بالاسم نفسه يمرّان معاً، فيردّ الفهرسُ الفريد الثانيَ بخطأ 500 غامض.
    try:
        manager_result = await db.users.insert_one(manager_user)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")
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

    # تُحتسب المحاولة الآن لا قبل التحقّق: الحدّ لردع الإغراق لا لمعاقبة الخطأ
    await _record_register_attempt(ip)

    return {
        "id": center_id,
        "name": center_dict["name"],
        "approval_status": "pending",
        "message": "تم استلام طلب التسجيل. سيتم التفعيل بعد مراجعة المدير."
    }

# [AUDIT-2026-05-22 fix: admin approval endpoint for pending centers]
@router.post("/api/centers/{center_id}/approve")
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
        {"$set": {"is_active": True, "approval_status": "approved", "approved_at": utcnow()}}
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

@router.post("/api/centers/{center_id}/reject")
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

@router.get("/api/centers/pending")
async def list_pending_centers(current_user: dict = Depends(get_current_user)):
    """قائمة المراكز قيد الموافقة (للمدير فقط)"""
    if current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="غير مصرح")
    pending = await db.centers.find({"approval_status": "pending"}).sort("created_at", -1).to_list(200)
    return [serialize_doc(c) for c in pending]

@router.post("/api/centers")
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
        "created_at": utcnow(),
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
            "created_at": utcnow()
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

@router.put("/api/centers/{center_id}")
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

# ==================== هويّة المركز: الشعار ====================
#
# [قرار المالك 2026-09-07] «يُسمح لمدير المركز أن يرفع شعار المركز لكي يظهر في
# الشهادات والفواتير وكل الوثائق الإلكترونية التي يصدرها النظام باسم مركز
# تحفيظ القرآن.»
#
# وكانت كلُّ وثيقةٍ تُطبع تحمل علامة «المشكاة» — اسمَ البرنامج لا اسمَ المركز
# الذي يمنح الشهادة. والشهادة تُنسب إلى من يمنحها.


@router.post("/api/centers/{center_id}/logo")
async def upload_center_logo(center_id: str, file: UploadFile = File(...),
                             current_user: dict = Depends(get_current_user)):
    """رفع شعار المركز — لمديره أو لمدير النظام."""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    if (current_user["role"] == "center_manager"
            and center_id != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل مركز آخر")

    center = await db.centers.find_one({"_id": safe_object_id(center_id)})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")

    saved = await save_upload(
        file, kind="center_logo", center_id=center_id,
        owner_id=str(current_user["_id"]),
        max_bytes=MAX_LOGO_BYTES, allowed=IMAGE_TYPES)

    old = center.get("logo_file_id")
    await db.centers.update_one(
        {"_id": center["_id"]},
        {"$set": {"logo_file_id": saved["file_id"], "logo_updated_at": utcnow()}})
    # الشعار القديم يُحذف بعد نجاح الجديد لا قبله: لو فشل الرفع لبقي المركز بلا شعار
    if old:
        await delete_file(old)

    await write_audit_log(
        actor_id=str(current_user["_id"]), center_id=center_id,
        action="CENTER_LOGO_UPDATED", payload={"size": saved["size"]})
    return {"message": "رُفع شعار المركز", **saved}


@router.get("/api/centers/{center_id}/logo")
async def get_center_logo(center_id: str):
    """
    شعار المركز — **بلا مصادقة عن قصد**.

    الشعار علامةٌ عامّة تظهر على شهادةٍ تُسلَّم للطالب وفاتورةٍ تُعطى لوليّه،
    فليس فيه ما يُحمى. والبديل — قراءتُه بترويسة مصادقة — يعني أن كل `<img>`
    في كل وثيقةٍ تُطبع يحتاج إلى جلبٍ يدويّ وتحويلٍ إلى عنوان بيانات، وهو
    تعقيدٌ يُشترى بلا ثمنٍ يقابله.
    """
    center = await db.centers.find_one({"_id": safe_object_id(center_id)},
                                       {"logo_file_id": 1})
    if not center or not center.get("logo_file_id"):
        raise HTTPException(status_code=404, detail="لا شعار لهذا المركز")
    data, meta = await read_file(center["logo_file_id"])
    return Response(
        content=data,
        media_type=meta.get("content_type", "application/octet-stream"),
        headers={
            "Cache-Control": "public, max-age=300",
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; sandbox",
        },
    )


@router.delete("/api/centers/{center_id}/logo")
async def remove_center_logo(center_id: str,
                             current_user: dict = Depends(get_current_user)):
    """إزالة الشعار — تعود الوثائق إلى علامة النظام."""
    if current_user["role"] not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")
    if (current_user["role"] == "center_manager"
            and center_id != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="غير مصرح لك بتعديل مركز آخر")

    center = await db.centers.find_one({"_id": safe_object_id(center_id)})
    if not center:
        raise HTTPException(status_code=404, detail="المركز غير موجود")
    if center.get("logo_file_id"):
        await delete_file(center["logo_file_id"])
    await db.centers.update_one(
        {"_id": center["_id"]},
        {"$unset": {"logo_file_id": "", "logo_updated_at": ""}})
    return {"message": "أُزيل شعار المركز"}


@router.delete("/api/centers/{center_id}")
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

@router.get("/api/centers/{center_id}/details")
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
        doc["hire_date"] = doc.get("hire_date", utcnow())
        if isinstance(doc["hire_date"], datetime):
            doc["hire_date"] = doc["hire_date"].isoformat()
        teachers_list.append(doc)
    
    # Registration info
    center_data["created_at"] = center_data.get("created_at", utcnow())
    if isinstance(center_data["created_at"], datetime):
        center_data["created_at"] = center_data["created_at"].isoformat()
    
    center_data["students_count"] = students_count
    center_data["teachers_count"] = teachers_count
    center_data["halaqat_count"] = halaqat_count
    center_data["teachers_list"] = teachers_list
    
    return center_data

@router.post("/api/super/centers")
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
        "created_at": utcnow(),
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
        "created_at": utcnow(),
    }
    
    # [إصلاح 2026-09-06] فحصُ الاسم أعلاه لا يمنع السباق: طلبان متزامنان
    # بالاسم نفسه يمرّان معاً، فيردّ الفهرسُ الفريد الثانيَ بخطأ 500 غامض.
    try:
        manager_result = await db.users.insert_one(manager_user)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="اسم المستخدم موجود بالفعل")
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

@router.post("/api/super/centers/{center_id}/status")
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

@router.get("/api/super/dashboard/stats")
async def super_get_global_stats(current_user: dict = Depends(get_current_user)):
    """إحصائيات إجمالية عالمية للجمعية أو الوزارة (super_admin)"""
    if current_user["role"] != "super_admin":
        raise HTTPException(status_code=403, detail="غير مصرح - للمدير العام فقط")

    total_active_centers = await db.centers.count_documents({"is_active": True})
    total_active_students = await db.students.count_documents({"is_active": True})
    
    # Financial aggregate in FCFA (الجمع داخل قاعدة البيانات — انظر _sum_amounts)
    total_fees_fcfa = await _sum_amounts(db.fees, {"status": "paid"})
    total_salaries_fcfa = await _sum_amounts(db.salaries, {})
    total_expenses_fcfa = await _sum_amounts(db.expenses, dict(NOT_VOIDED))

    global_balance_fcfa = total_fees_fcfa - total_salaries_fcfa - total_expenses_fcfa

    return {
        "total_active_centers": total_active_centers,
        "total_active_students": total_active_students,
        "total_fees_collected_fcfa": total_fees_fcfa,
        "total_salaries_paid_fcfa": total_salaries_fcfa,
        "total_expenses_fcfa": total_expenses_fcfa,
        "global_balance_fcfa": global_balance_fcfa
    }
