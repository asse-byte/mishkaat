"""معادلة التقييم الذكي."""

from datetime import datetime
from datetime import timedelta
from typing import List

from app.common import NOT_DELETED
from app.db import db


# [AUDIT-2026-09-03 refactor: كانت معادلة التقييم الذكي مكتوبة مرتين بحرفها في سجل الشرف
#  وفي الترتيب، وقد اختلفتا فعلاً في النافذة الزمنية (30 يوماً مقابل 90 يوماً باسم متغيّر
#  يقول thirty_days_ago). صارت دالة واحدة، فأي تعديل مستقبلي على المعادلة يسري على الشاشتين.]
_EVAL_SCORE_MAP = {"excellent": 100, "good": 80, "acceptable": 60, "needs_improvement": 40}

_ATTENDANCE_SCORE_MAP = {"present": 100, "late": 80, "excused": 60, "absent": 0}

async def compute_student_scores(students: List[dict], days: int) -> List[dict]:
    """
    التقييم الذكي: (حفظ×0.4) + (مراجعة×0.3) + (حضور×0.2) − (أخطاء×0.1)، محصوراً بين 0 و100.

    [AUDIT-2026-09-03 perf: كان سجل الشرف يُطلق استعلامين لكل طالب — 2000 رحلة لقاعدة
     البيانات في مركز فيه ألف طالب على كل فتح للصفحة الرئيسية. صار استعلامين للكل.]
    """
    student_ids = [str(s["_id"]) for s in students]
    if not student_ids:
        return []

    since = datetime.utcnow() - timedelta(days=days)
    rec_by_student: dict = {}
    att_by_student: dict = {}

    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": student_ids}, "date": {"$gte": since}}):
        rec_by_student.setdefault(r["student_id"], []).append(r)
    async for a in db.attendance.find({"student_id": {"$in": student_ids}, "date": {"$gte": since}}):
        att_by_student.setdefault(a["student_id"], []).append(a)

    scored = []
    for s in students:
        sid = str(s["_id"])
        h_sum = h_count = r_sum = r_count = e_sum = 0

        for rec in rec_by_student.get(sid, []):
            score = _EVAL_SCORE_MAP.get(rec.get("evaluation", "good"), 80)
            if rec.get("recitation_type") == "new":
                h_sum += score
                h_count += 1
            else:
                r_sum += score
                r_count += 1
            e_sum += rec.get("mistakes_count", 0)

        a_sum = a_count = 0
        for att in att_by_student.get(sid, []):
            a_sum += _ATTENDANCE_SCORE_MAP.get(att.get("status", "present"), 100)
            a_count += 1

        H = (h_sum / h_count) if h_count else 80    # 80 افتراضياً عند غياب البيانات
        R = (r_sum / r_count) if r_count else 80
        A = (a_sum / a_count) if a_count else 100
        final_score = max(0, min(100, (H * 0.4) + (R * 0.3) + (A * 0.2) - (e_sum * 0.1)))

        scored.append({
            "id": sid,
            "name": s.get("name"),
            "halaqah_name": s.get("halaqah_name", "غير محدد"),
            "score": round(final_score, 1),
            "progress": s.get("progress", 0),
            "has_data": bool(h_count or r_count or a_count),
        })

    scored.sort(key=lambda x: x["score"], reverse=True)
    return scored
