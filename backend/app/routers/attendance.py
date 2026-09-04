"""الحضور والغياب."""

from datetime import datetime
from fastapi import APIRouter
from pymongo.errors import DuplicateKeyError
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import Optional

from app.common import check_student_access, safe_object_id, serialize_doc
from app.db import db
from app.models import AttendanceCreate
from app.security import get_current_user
from app.sse import push_notification

router = APIRouter()


# ==================== Attendance Routes ====================

@router.get("/api/attendance")
async def get_attendance(
    halaqah_id: Optional[str] = None,
    date: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
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

    attendance = await db.attendance.find(query).sort("date", -1).to_list(limit)
    result = []
    for a in attendance:
        doc = serialize_doc(a)
        doc["date"] = doc.get("date", datetime.utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result

@router.get("/api/attendance/halaqah/{halaqah_id}")
async def get_halaqah_attendance(
    halaqah_id: str,
    date: Optional[str] = None,
    limit: int = Query(300, ge=1, le=1000),
    current_user: dict = Depends(get_current_user),
):
    """
    [AUDIT-2026-09-03 addition] حضور حلقة محددة في يوم محدد.

    صفحة الحضور في الواجهة تستدعي GET /api/attendance/halaqah/{id} منذ البداية، ولا وجود
    لهذه النقطة في الخادم إطلاقاً — فكانت تعود 404 وتظهر الشاشة فارغة دائماً عند اختيار حلقة.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    halaqah = await db.halaqat.find_one({"_id": safe_object_id(halaqah_id)})
    if not halaqah:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")

    if role not in ["admin", "super_admin"]:
        if not current_user.get("center_id") or halaqah.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="حلقة لا تنتمي لمركزك")

    query: dict = {"halaqah_id": halaqah_id}
    if date:
        query["date_str"] = date

    rows = await db.attendance.find(query).sort("date", -1).to_list(limit)
    result = []
    for a in rows:
        doc = serialize_doc(a)
        if isinstance(doc.get("date"), datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result

@router.post("/api/attendance")
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
        # [AUDIT-2026-09-03 fix: سجل الحضور لم يكن يحمل center_id إطلاقاً، فكل استعلام يُصفّي
        #  عليه يعود فارغاً (نسبة الحضور على لوحة التحكم). يُكتب الآن من مستند الطالب نفسه.]
        attendance_dict["center_id"] = student.get("center_id")
        attendance_dict["recorded_by"] = str(current_user["_id"])
        records.append(attendance_dict)

        # Real-time Parent Absentee warning via SSE
        if record.status == "absent":
            parent_phone = student.get("parent_phone")
            if parent_phone:
                parent_user = await db.users.find_one({"phone": parent_phone, "role": "parent"})
                if parent_user:
                    await push_notification(
                        user_id=str(parent_user["_id"]),
                        event_type="absentee_alert",
                        title="تنبيه غياب",
                        body=f"ابنكم/ابنتكم {student.get('name')} غائب(ة) اليوم عن حلقة التحفيظ.",
                        data={
                            "student_id": record.student_id,
                            "student_name": student.get("name"),
                            "date": date_str,
                        },
                    )

    # [AUDIT-2026-09-03 fix — ازدواج سجلات الحضور] كان insert_many يضيف صفاً جديداً في كل مرة،
    # فإعادة إرسال كشف اليوم (نقرة مزدوجة، أو تصحيح غياب إلى حضور) تُنشئ سجلين متناقضين للطالب
    # نفسه في اليوم نفسه، ويظل الغياب محسوباً في نسبة الحضور إلى الأبد. صار التسجيل عن اليوم
    # نفسه يستبدل السجل السابق (upsert) — وهو ما يتوقعه المعلّم عند التصحيح.
    created = updated_count = 0
    for rec in records:
        key = {"student_id": rec["student_id"], "date_str": rec["date_str"]}
        try:
            res = await db.attendance.update_one(key, {"$set": rec}, upsert=True)
        except DuplicateKeyError:
            # سباق: طلبان متزامنان على المفتاح نفسه (نقرة مزدوجة). الفهرس الفريد ردّ الثاني،
            # فنكتبه تحديثاً — بدون هذا يضيع تصحيح المعلّم بخطأ 500.
            res = await db.attendance.update_one(key, {"$set": rec})
        if res.upserted_id is not None:
            created += 1
        else:
            updated_count += 1

    return {
        "message": f"تم تسجيل حضور {len(records)} طالب",
        "count": len(records),
        "created": created,
        "updated": updated_count,
    }

@router.get("/api/attendance/student/{student_id}")
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

@router.get("/api/attendance/center")
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
