"""
نظرة المدير على الحلقات.

    GET /api/halaqat-overview               كل حلقات المركز وأداؤها في سطر
    GET /api/halaqat-overview/{halaqah_id}  تفصيل حلقة: شيخُها وطلابُها ومقاييسهم

[قرار المالك 2026-09-06] المدير يرى أداء الحلقات كلِّها، فإذا ضغط على حلقةٍ
رأى تفصيلها: شيخَها وتقييمَه، وطلابَها ومستوى كلِّ واحد.

وهذا **قراءةٌ لا كتابة**: لا يُسجَّل من هنا تسميعٌ ولا حضور — ذاك عمل الشيخ.

والحلقة نطاقٌ قائم بذاته: شيخُ الحلقة يفتح تفصيل حلقاته وحدها، ومحاولةُ فتح
حلقةِ غيره تُردّ بـ403 من `assert_halaqah_in_scope` لا بفحصٍ يدوي هنا.
"""

from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException

from app.common import NOT_DELETED, safe_object_id, serialize_doc
from app.db import db
from app.metrics import attendance_rate, compute_all
from app.scope import assert_halaqah_in_scope, visible_halaqah_ids
from app.security import get_current_user

router = APIRouter(tags=["نظرة الحلقات"])

READERS = ("admin", "super_admin", "center_manager", "teacher")


async def _load_history(student_ids: List[str]):
    recs: Dict[str, List[dict]] = {sid: [] for sid in student_ids}
    atts: Dict[str, List[dict]] = {sid: [] for sid in student_ids}
    if not student_ids:
        return recs, atts
    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": student_ids}}):
        recs.setdefault(r["student_id"], []).append(r)
    async for a in db.attendance.find({"student_id": {"$in": student_ids}}):
        atts.setdefault(a["student_id"], []).append(a)
    return recs, atts


def _attendance_pct(records: List[dict]) -> Optional[float]:
    """نسبة الحضور مئويةً، و None لمن لا سجلَّ حضورٍ له.

    `metrics.attendance_rate` كسرٌ بين صفر وواحد وسمةٌ للتنبؤ، ويُعيد 1.0 لمن
    لا سجلَّ له. وعرضُه كما هو يكتب «0.9%» بدل «90%»، ويُعطي طالباً لم يُرصد
    له حضورٌ قطُّ حضوراً كاملاً فيرفع متوسّط حلقته. فيُحوَّل هنا، ويُقال «لا
    خبر» حيث لا خبر.
    """
    if not records:
        return None
    return round(100.0 * attendance_rate(records), 1)


def _avg(values: List[Optional[float]]) -> Optional[float]:
    """متوسّطٌ يتجاهل «لا بيانات».

    الطالب الذي لم يُسمّع بعد قيمتُه None لا صفر. وعدُّها صفراً يهبط بمتوسّط
    الحلقة كلَّما سُجّل فيها طالبٌ جديد — فتبدو الحلقة متراجعة وهي تنمو.
    """
    present = [v for v in values if v is not None]
    return round(sum(present) / len(present), 1) if present else None


@router.get("/api/halaqat-overview")
async def halaqat_overview(current_user: dict = Depends(get_current_user)):
    """كل حلقة في سطر: شيخُها، وعدد طلابها، ومتوسّط إتقانهم وحضورهم."""
    if current_user["role"] not in READERS:
        raise HTTPException(status_code=403, detail="غير مصرح")

    hids = await visible_halaqah_ids(current_user)
    query: dict = {}
    if hids is not None:
        if not hids:
            return {"halaqat": [], "totals": {"halaqat": 0, "students": 0}}
        query["_id"] = {"$in": [safe_object_id(h) for h in hids]}
    else:
        cid = current_user.get("center_id")
        if cid:
            query["center_id"] = cid

    halaqat = await db.halaqat.find(query).to_list(500)
    ids = [str(h["_id"]) for h in halaqat]
    if not ids:
        return {"halaqat": [], "totals": {"halaqat": 0, "students": 0}}

    students = await db.students.find(
        {**NOT_DELETED, "halaqah_id": {"$in": ids}, "is_active": True}).to_list(5000)
    recs, atts = await _load_history([str(s["_id"]) for s in students])

    by_halaqah: Dict[str, List[dict]] = {}
    for s in students:
        by_halaqah.setdefault(s.get("halaqah_id"), []).append(s)

    rows = []
    for h in halaqat:
        hid = str(h["_id"])
        members = by_halaqah.get(hid, [])
        metrics = [compute_all(recs.get(str(s["_id"]), []), atts.get(str(s["_id"]), []))
                   for s in members]
        rows.append({
            "id": hid,
            "name": h.get("name"),
            "teacher_id": h.get("teacher_id"),
            "teacher_name": h.get("teacher_name"),
            "schedule": h.get("schedule"),
            "students_count": len(members),
            "mastery": _avg([m.get("mastery") for m in metrics]),
            "momentum": _avg([m.get("momentum") for m in metrics]),
            "consistency": _avg([m.get("consistency") for m in metrics]),
            "attendance_rate": _avg([
                _attendance_pct(atts.get(str(s["_id"]), [])) for s in members]),
        })

    rows.sort(key=lambda r: (r["mastery"] is None, -(r["mastery"] or 0)))
    return {
        "halaqat": rows,
        "totals": {"halaqat": len(rows), "students": len(students)},
    }


@router.get("/api/halaqat-overview/ranking")
async def halaqat_ranking(current_user: dict = Depends(get_current_user)):
    """
    ترتيب حلقات المركز بالأداء — يراه المحفّظ أيضاً.

    [قرار المالك 2026-09-07] «لخلق التنافس بين المعلّمين، أودّ أن يرى المعلّم
    نسبة الأداء أو التفوّق: أيّ حلقة أفضل في المركز.»

    وهذا **استثناءٌ مقصود** من قاعدة عزل الحلقات، وحدُّه دقيق: تُعاد **أرقامٌ
    مجمّعة واسمُ الحلقة وشيخِها** — متوسّطُ الإتقان والاندفاع والانتظام
    والحضور، وعددُ الطلاب. ولا يُعاد اسمُ طالبٍ واحد من حلقةٍ أخرى ولا مقياسُه
    ولا سجلُّه. فالمحفّظ يعرف موقعَ حلقته بين أخواتها ولا يقرأ بيانات غيره —
    وهو ما يجعل التنافس ممكناً بلا فتح الملفّات.

    وتفصيلُ الحلقة (`/{halaqah_id}`) يبقى محصوراً كما كان: لا يفتحه إلا
    صاحبُها والإدارة.
    """
    if current_user["role"] not in READERS:
        raise HTTPException(status_code=403, detail="غير مصرح")

    cid = current_user.get("center_id")
    if not cid and current_user["role"] not in ("admin", "super_admin"):
        return {"halaqat": [], "mine": []}

    query = {"center_id": cid} if cid else {}
    halaqat = await db.halaqat.find(query).to_list(500)
    ids = [str(h["_id"]) for h in halaqat]
    if not ids:
        return {"halaqat": [], "mine": []}

    students = await db.students.find(
        {**NOT_DELETED, "halaqah_id": {"$in": ids}, "is_active": True}).to_list(5000)
    recs, atts = await _load_history([str(s["_id"]) for s in students])

    by_halaqah: Dict[str, List[dict]] = {}
    for st in students:
        by_halaqah.setdefault(st.get("halaqah_id"), []).append(st)

    mine = await visible_halaqah_ids(current_user)
    mine_set = set(mine) if mine is not None else set()

    rows = []
    for h in halaqat:
        hid = str(h["_id"])
        members = by_halaqah.get(hid, [])
        metrics = [compute_all(recs.get(str(st["_id"]), []), atts.get(str(st["_id"]), []))
                   for st in members]
        rows.append({
            "id": hid,
            "name": h.get("name"),
            "teacher_name": h.get("teacher_name"),
            "students_count": len(members),
            "mastery": _avg([m.get("mastery") for m in metrics]),
            "momentum": _avg([m.get("momentum") for m in metrics]),
            "consistency": _avg([m.get("consistency") for m in metrics]),
            "attendance_rate": _avg([
                _attendance_pct(atts.get(str(st["_id"]), [])) for st in members]),
            "is_mine": hid in mine_set,
        })

    # الترتيب بالإتقان، ومن لا بيانات له في الذيل لا في الصدر
    rows.sort(key=lambda r: (r["mastery"] is None, -(r["mastery"] or 0)))
    for i, r in enumerate(rows, 1):
        r["rank"] = i

    return {
        "halaqat": rows,
        "mine": [r["id"] for r in rows if r["is_mine"]],
        "center_average": {
            "mastery": _avg([r["mastery"] for r in rows]),
            "momentum": _avg([r["momentum"] for r in rows]),
            "consistency": _avg([r["consistency"] for r in rows]),
            "attendance_rate": _avg([r["attendance_rate"] for r in rows]),
        },
    }


@router.get("/api/halaqat-overview/{halaqah_id}")
async def halaqah_detail(halaqah_id: str, current_user: dict = Depends(get_current_user)):
    """تفصيل حلقة: شيخُها وآخرُ تقييمٍ له، وطلابُها ومستوى كلِّ واحد."""
    if current_user["role"] not in READERS:
        raise HTTPException(status_code=403, detail="غير مصرح")
    await assert_halaqah_in_scope(halaqah_id, current_user)

    halaqah = await db.halaqat.find_one({"_id": safe_object_id(halaqah_id)})
    if not halaqah:
        raise HTTPException(status_code=404, detail="الحلقة غير موجودة")

    teacher = None
    evaluation = None
    if halaqah.get("teacher_id"):
        teacher = await db.teachers.find_one({"_id": safe_object_id(halaqah["teacher_id"])})
        # تقييم الشيخ للمدير وحده — الشيخ يقرأ تقييم نفسه من صفحته
        if teacher and current_user["role"] != "teacher":
            latest = await db.teacher_evaluations.find(
                {"teacher_id": str(teacher["_id"])}).sort("created_at", -1).to_list(1)
            evaluation = serialize_doc(latest[0]) if latest else None

    students = await db.students.find(
        {**NOT_DELETED, "halaqah_id": halaqah_id, "is_active": True}).to_list(500)
    sids = [str(s["_id"]) for s in students]
    recs, atts = await _load_history(sids)

    rows = []
    for s in students:
        sid = str(s["_id"])
        m = compute_all(recs.get(sid, []), atts.get(sid, []))
        rows.append({
            "id": sid,
            "name": s.get("name"),
            "level": s.get("level"),
            "memorized_pages": s.get("memorized_pages"),
            "recitations_count": len(recs.get(sid, [])),
            "attendance_rate": _attendance_pct(atts.get(sid, [])),
            **{k: m.get(k) for k in
               ("mastery", "momentum", "precision", "consistency", "review_depth")},
        })
    rows.sort(key=lambda r: (r["mastery"] is None, -(r["mastery"] or 0)))

    return {
        "halaqah": {
            "id": halaqah_id,
            "name": halaqah.get("name"),
            "schedule": halaqah.get("schedule"),
            "students_count": len(students),
        },
        "teacher": {
            "id": str(teacher["_id"]),
            "name": teacher.get("name"),
            "phone": teacher.get("phone"),
            "specialization": teacher.get("specialization"),
            "teacher_type": teacher.get("teacher_type", "halaqah"),
            "latest_evaluation": evaluation,
        } if teacher else None,
        "summary": {
            "mastery": _avg([r["mastery"] for r in rows]),
            "momentum": _avg([r["momentum"] for r in rows]),
            "consistency": _avg([r["consistency"] for r in rows]),
            "attendance_rate": _avg([r["attendance_rate"] for r in rows]),
        },
        "students": rows,
    }
