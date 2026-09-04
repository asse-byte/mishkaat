"""تصدير CSV."""

from datetime import datetime
from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException
from fastapi import Query
from fastapi.responses import StreamingResponse
from typing import List
from typing import Optional
import csv
import io

from app.audit import write_audit_log
from app.common import parse_date_boundary, scoped_student_ids
from app.db import db
from app.pii import decrypt_student_doc
from app.security import get_current_user

router = APIRouter()


# ==================== CSV Export (إضافة 2026-09-03) ====================

def _csv_response(rows: List[dict], columns: List[tuple], filename: str) -> StreamingResponse:
    """
    تصدير CSV بترميز UTF-8 مع BOM حتى تظهر العربية سليمة في Excel
    (بدون BOM يفتح Excel الملف بترميز خاطئ فتبدو الأسماء رموزاً).
    """
    buffer = io.StringIO()
    buffer.write("﻿")
    writer = csv.writer(buffer)
    writer.writerow([label for _key, label in columns])
    for row in rows:
        writer.writerow([row.get(key, "") for key, _label in columns])
    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@router.get("/api/export/students.csv")
async def export_students_csv(current_user: dict = Depends(get_current_user)):
    """
    [AUDIT-2026-09-03 addition] تصدير كشف الطلاب — المركز يحتاج نسخة ورقية/إكسل للإدارة
    وللأرشيف، ولم تكن هناك أي وسيلة لإخراج البيانات من النظام.
    """
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {"is_active": True}
    if role == "center_manager":
        if not current_user.get("center_id"):
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        query["center_id"] = current_user["center_id"]

    students = await db.students.find(query).to_list(10000)
    rows = []
    for s in students:
        d = decrypt_student_doc(s)
        rows.append({
            "name": d.get("name"),
            "halaqah_name": d.get("halaqah_name"),
            "phone": d.get("phone"),
            "parent_name": d.get("parent_name"),
            "parent_phone": d.get("parent_phone"),
            "memorization_plan": d.get("memorization_plan"),
            "progress": d.get("progress", 0),
            "current_surah": d.get("current_surah"),
            "enrollment_date": d["enrollment_date"].strftime("%Y-%m-%d") if isinstance(d.get("enrollment_date"), datetime) else "",
        })

    await write_audit_log(
        actor_id=str(current_user["_id"]),
        center_id=current_user.get("center_id", "system"),
        action="EXPORT_STUDENTS",
        payload={"rows": len(rows)},
    )

    return _csv_response(rows, [
        ("name", "الاسم"),
        ("halaqah_name", "الحلقة"),
        ("phone", "هاتف الطالب"),
        ("parent_name", "ولي الأمر"),
        ("parent_phone", "هاتف ولي الأمر"),
        ("memorization_plan", "خطة الحفظ"),
        ("progress", "نسبة التقدم"),
        ("current_surah", "السورة الحالية"),
        ("enrollment_date", "تاريخ التسجيل"),
    ], "students.csv")

@router.get("/api/export/attendance.csv")
async def export_attendance_csv(
    from_date: Optional[str] = Query(None, alias="from"),
    to_date: Optional[str] = Query(None, alias="to"),
    current_user: dict = Depends(get_current_user),
):
    """تصدير سجل الحضور لفترة محددة"""
    role = current_user["role"]
    if role not in ["admin", "super_admin", "center_manager"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    if role == "center_manager":
        center = current_user.get("center_id")
        if not center:
            raise HTTPException(status_code=400, detail="حسابك غير مرتبط بمركز")
        ids = await scoped_student_ids(center)
        if not ids:
            return _csv_response([], [("date_str", "التاريخ")], "attendance.csv")
        query["$or"] = [{"center_id": center}, {"student_id": {"$in": ids}}]

    rng = {}
    start = parse_date_boundary(from_date)
    end = parse_date_boundary(to_date, end=True)
    if start:
        rng["$gte"] = start
    if end:
        rng["$lte"] = end
    if rng:
        query["date"] = rng

    rows = await db.attendance.find(query).sort("date", -1).to_list(20000)
    status_ar = {"present": "حاضر", "absent": "غائب", "late": "متأخر", "excused": "بعذر"}
    out = [{
        "date_str": r.get("date_str", ""),
        "student_name": r.get("student_name", ""),
        "status": status_ar.get(r.get("status"), r.get("status", "")),
        "notes": r.get("notes", ""),
    } for r in rows]

    return _csv_response(out, [
        ("date_str", "التاريخ"),
        ("student_name", "الطالب"),
        ("status", "الحالة"),
        ("notes", "ملاحظات"),
    ], "attendance.csv")
