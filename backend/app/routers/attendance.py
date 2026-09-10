"""الحضور والغياب."""

from app.clock import utcnow

from datetime import datetime
from fastapi import APIRouter
from pymongo.errors import DuplicateKeyError
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from typing import Optional

from app.common import check_student_access, safe_object_id, serialize_doc
from app.config import XP_PER_SESSION, logger
from app.audit import write_audit_log
from app.db import db
from app.gamification import award_xp
from app.metrics import _PRESENT_STATUSES
from app.models import AttendanceCreate, AttendanceUpdate
from app.scope import assert_halaqah_in_scope, teacher_only, visible_halaqah_ids
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
        # [إصلاح 2026-09-06] كان النطاق حلقات المركز كلَّها للاثنين معاً، فيقرأ
        # المحفّظ حضور حلقات غيره. صار كلٌّ في نطاقه: المدير مركزَه، والمحفّظ
        # حلقاته وحدها.
        scope_hids = await visible_halaqah_ids(current_user)
        if scope_hids is None:
            halaqat = await db.halaqat.find(
                {"center_id": current_user["center_id"], "is_active": True}, {"_id": 1}
            ).to_list(500)
            halaqah_ids_in_scope = {str(h["_id"]) for h in halaqat}
        else:
            halaqah_ids_in_scope = set(scope_hids)
        if not halaqah_ids_in_scope:
            return []
        query["halaqah_id"] = {"$in": list(halaqah_ids_in_scope)}
        if halaqah_id:
            if halaqah_id not in halaqah_ids_in_scope:
                raise HTTPException(status_code=403, detail="هذه الحلقة خارج نطاقك")
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
        doc["date"] = doc.get("date", utcnow())
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
        # [إصلاح 2026-09-06] المركز لا يكفي: كان المحفّظ يقرأ كشف حضور أيّ حلقة
        # في مركزه بتمرير معرّفها.
        await assert_halaqah_in_scope(halaqah_id, current_user)

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
    # [قرار المالك 2026-09-06] تسجيل الحضور شهادةٌ يؤدّيها من حضر المجلس.
    # مديرُ المركز يقرأ ويُصحّح بالتعديل، ولا يُنشئ سجلّاً يشهد فيه على ما لم
    # يحضره. والمحفّظ محصور في حلقاته عبر check_student_access أدناه.
    teacher_only(current_user, "تسجيل الحضور")

    now = utcnow()
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

    # [إضافة 2026-09-05 — FR13 في تقرير Halaqtna] نقاط الحضور.
    # المصدر هو (الطالب + تاريخ اليوم) لا معرّف السجلّ: الكشف يُعاد إرساله عند
    # التصحيح، والمفتاح الفريد بهذه الصورة يمنح نقاط اليوم مرّة واحدة مهما
    # أُعيد الإرسال. ومن غاب لا يُمنح شيئاً — النقطة على الحضور لا على الذِّكر.
    for rec in records:
        if rec.get("status") not in _PRESENT_STATUSES:
            continue
        try:
            await award_xp(
                rec["student_id"], XP_PER_SESSION, "attendance",
                f'{rec["student_id"]}:{rec["date_str"]}', rec.get("center_id"),
            )
        except Exception as exc:  # pragma: no cover - لا يُفشل تسجيل الحضور
            logger.warning(f"attendance xp failed: {exc}")

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
        doc["date"] = doc.get("date", utcnow())
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
        doc["date"] = doc.get("date", utcnow())
        if isinstance(doc["date"], datetime):
            doc["date"] = doc["date"].isoformat()
        result.append(doc)
    return result


# ==================== تصحيح الحضور ====================
#
# [قرار المالك 2026-09-07] العملُ الإداري يُصحَّح بعد وقوعه.
#
# ولم يكن للحضور تعديلٌ ولا حذف بأيّ حال: من وسم طالباً غائباً وهو حاضر لا
# سبيل له إلا إعادةُ إرسال كشف اليوم كلِّه — ولا سبيل للمدير أصلاً، لأن
# التسجيل محصورٌ بالشيخ. فيبقى غيابٌ خاطئ في سجلّ الطالب ويُنبَّه وليُّه به.


@router.put("/api/attendance/{record_id}")
async def update_attendance_record(record_id: str, patch: AttendanceUpdate,
                                   current_user: dict = Depends(get_current_user)):
    """تصحيح حالة حضورٍ مرصودة — للشيخ صاحب الحلقة وللإدارة."""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    rec = await db.attendance.find_one({"_id": safe_object_id(record_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="سجلّ الحضور غير موجود")

    # البوّابة نفسها التي تحرس بقية مسارات الطالب — تحصر الشيخ بحلقته
    await check_student_access(rec.get("student_id"), current_user)

    changes = {"status": patch.status, "updated_at": utcnow(),
               "updated_by": str(current_user["_id"])}
    if patch.notes is not None:
        changes["notes"] = patch.notes
    await db.attendance.update_one({"_id": rec["_id"]}, {"$set": changes})

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=rec.get("center_id") or current_user.get("center_id", "system"),
        action="UPDATE_ATTENDANCE",
        payload={"record_id": record_id, "student_id": rec.get("student_id"),
                 "from": rec.get("status"), "to": patch.status,
                 "date": rec.get("date_str")})

    updated = await db.attendance.find_one({"_id": rec["_id"]})
    return serialize_doc(updated)


@router.delete("/api/attendance/{record_id}")
async def delete_attendance_record(record_id: str,
                                   current_user: dict = Depends(get_current_user)):
    """حذف سجلّ حضورٍ رُصد خطأً — لطالبٍ لم يكن في المجلس أصلاً."""
    if current_user["role"] not in ["admin", "super_admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    rec = await db.attendance.find_one({"_id": safe_object_id(record_id)})
    if not rec:
        raise HTTPException(status_code=404, detail="سجلّ الحضور غير موجود")
    await check_student_access(rec.get("student_id"), current_user)

    await db.attendance.delete_one({"_id": rec["_id"]})
    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=rec.get("center_id") or current_user.get("center_id", "system"),
        action="DELETE_ATTENDANCE",
        payload={"record_id": record_id, "student_id": rec.get("student_id"),
                 "date": rec.get("date_str"), "status": rec.get("status")})
    return {"message": "حُذف سجلّ الحضور"}
