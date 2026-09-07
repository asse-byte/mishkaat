"""
نشاط المراكز — لإدارة النظام.

    GET /api/admin/centers-activity?days=30

[قرار المالك 2026-09-07] «مدير النظام ينبغي أن يعرف مدى مستوى استخدام المنصّة
لأي مركز — بناءً على نسبة حركة البيانات والمعاملات داخل حساب المركز. والهدف:
لو صار حساب مدير النظام يوماً ملكاً لهيئةٍ عامّة لمراقبة مراكز تحفيظ القرآن،
يستطيعون الاستفادة من هذه الميزة.»

**ما كان موجوداً لا يقيس الاستخدام.** لوحةُ مدير النظام تُرتّب المراكز بدرجةٍ
مبنيّة على ثلاثة أعداد ثابتة (طلاب، معلّمون، حلقات). ومركزٌ سجّل مئة طالبٍ ثمّ
هجر النظام سنةً يتصدّر بها مركزاً يعمل فيه عشرون طالباً كلَّ يوم. العددُ يقيس
الحجم، والحركةُ تقيس الاستخدام — وهما شيئان.

**فالقياس هنا على النافذة الزمنية**: كم تسميعاً سُجّل، وكم يومَ حضورٍ رُصد، وكم
عمليةً ماليةً جرت، وكم طالباً أُضيف، ومتى كان آخرُ أثرٍ للمركز. ودرجةُ النشاط
تُنسب إلى حجم المركز لا إلى غيره: مركزٌ بعشرين طالباً يُسمّع كلَّ يوم أنشطُ من
مركزٍ بمئتين يُسمّع مرّةً في الأسبوع، وإن كان عددُ تسميعات الثاني أكبر.

وهذا **قراءةٌ مجرّدة**: أعدادٌ وتواريخ، لا أسماءَ طلابٍ ولا بيانات. الإشراف
يعرف أن المركز يعمل، ولا يقرأ ملفّات الناس.
"""

from datetime import timedelta
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, Query

from app.clock import utcnow
from app.common import NOT_DELETED
from app.db import db
from app.security import get_current_user

router = APIRouter(tags=["نشاط المراكز"])

# وزنُ كلِّ إشارة في درجة النشاط. التسميع أثقلُها لأنه العمل الأصلي للمركز،
# والحضورُ يليه، والماليةُ إشارةُ إدارةٍ حيّة لا إشارةُ تحفيظ.
WEIGHTS = {
    "recitations": 0.45,
    "attendance": 0.30,
    "finance": 0.15,
    "enrollment": 0.10,
}

# سقفُ التطبيع: نشاطٌ يوميّ لكل طالب. من بلغه فقد بلغ أقصى ما يُقاس.
EXPECTED_PER_STUDENT = {
    "recitations": 0.7,   # تسميعٌ كل يوم ونصف تقريباً
    "attendance": 0.9,    # حضورٌ يكاد يكون يوميّاً
    "finance": 0.05,
    "enrollment": 0.02,
}


def _level(score: float) -> str:
    if score >= 75:
        return "استخدامٌ مكثّف"
    if score >= 45:
        return "استخدامٌ منتظم"
    if score >= 15:
        return "استخدامٌ متقطّع"
    if score > 0:
        return "استخدامٌ ضعيف"
    return "لا حركة"


@router.get("/api/admin/centers-activity")
async def centers_activity(days: int = Query(30, ge=7, le=365),
                           current_user: dict = Depends(get_current_user)):
    """حركة كل مركز خلال نافذةٍ زمنية، ودرجةُ استخدامٍ منسوبة إلى حجمه."""
    if current_user["role"] not in ("admin", "super_admin"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    now = utcnow()
    since = now - timedelta(days=days)

    centers = await db.centers.find({}).to_list(500)
    if not centers:
        return {"days": days, "centers": [], "totals": {}}

    cids = [str(c["_id"]) for c in centers]
    counts: Dict[str, Dict[str, int]] = {
        cid: {"students": 0, "teachers": 0, "halaqat": 0,
              "recitations": 0, "attendance": 0, "finance": 0, "enrollment": 0}
        for cid in cids}
    last_seen: Dict[str, object] = {}

    def bump(cid, key, n=1):
        if cid in counts:
            counts[cid][key] += n

    def touch(cid, when):
        if cid not in counts or when is None:
            return
        prev = last_seen.get(cid)
        if prev is None or when > prev:
            last_seen[cid] = when

    # الأحجام
    async for row in db.students.aggregate([
            {"$match": {**NOT_DELETED, "center_id": {"$in": cids}, "is_active": True}},
            {"$group": {"_id": "$center_id", "n": {"$sum": 1}}}]):
        bump(row["_id"], "students", row["n"])
    async for row in db.teachers.aggregate([
            {"$match": {"center_id": {"$in": cids}, "is_active": True}},
            {"$group": {"_id": "$center_id", "n": {"$sum": 1}}}]):
        bump(row["_id"], "teachers", row["n"])
    async for row in db.halaqat.aggregate([
            {"$match": {"center_id": {"$in": cids}, "is_active": True}},
            {"$group": {"_id": "$center_id", "n": {"$sum": 1}}}]):
        bump(row["_id"], "halaqat", row["n"])

    # الحركة داخل النافذة
    async for row in db.attendance.aggregate([
            {"$match": {"center_id": {"$in": cids}, "date": {"$gte": since}}},
            {"$group": {"_id": "$center_id", "n": {"$sum": 1},
                        "last": {"$max": "$date"}}}]):
        bump(row["_id"], "attendance", row["n"])
        touch(row["_id"], row.get("last"))

    for coll, key in ((db.fees, "finance"), (db.salaries, "finance"),
                      (db.expenses, "finance")):
        async for row in coll.aggregate([
                {"$match": {"center_id": {"$in": cids}, "created_at": {"$gte": since}}},
                {"$group": {"_id": "$center_id", "n": {"$sum": 1},
                            "last": {"$max": "$created_at"}}}]):
            bump(row["_id"], key, row["n"])
            touch(row["_id"], row.get("last"))

    async for row in db.students.aggregate([
            {"$match": {**NOT_DELETED, "center_id": {"$in": cids},
                        "enrollment_date": {"$gte": since}}},
            {"$group": {"_id": "$center_id", "n": {"$sum": 1},
                        "last": {"$max": "$enrollment_date"}}}]):
        bump(row["_id"], "enrollment", row["n"])
        touch(row["_id"], row.get("last"))

    # التسميعات لا تحمل center_id (سجلّاتٌ قديمة)، فتُنسب عبر طلابها.
    student_center: Dict[str, str] = {}
    async for s in db.students.find(
            {**NOT_DELETED, "center_id": {"$in": cids}}, {"center_id": 1}):
        student_center[str(s["_id"])] = s["center_id"]
    if student_center:
        async for r in db.recitations.find(
                {**NOT_DELETED, "date": {"$gte": since}},
                {"student_id": 1, "date": 1}):
            cid = student_center.get(r.get("student_id"))
            if cid:
                bump(cid, "recitations")
                touch(cid, r.get("date"))

    rows: List[dict] = []
    for c in centers:
        cid = str(c["_id"])
        n = counts[cid]
        students = max(n["students"], 1)
        # كلُّ إشارةٍ تُنسب إلى ما يُتوقَّع من مركزٍ بهذا الحجم في هذه المدّة
        score = 0.0
        parts = {}
        for key, weight in WEIGHTS.items():
            expected = EXPECTED_PER_STUDENT[key] * students * days
            ratio = min(1.0, n[key] / expected) if expected > 0 else 0.0
            parts[key] = round(100 * ratio, 1)
            score += weight * ratio * 100
        seen = last_seen.get(cid)
        # التاريخ يُحوَّل هنا: هذه صفوفٌ نبنيها نحن لا وثائق مونغو، فلا يمرّ
        # عليها serialize_doc (يطلب _id ويسقط بـ KeyError بدونه).
        seen_iso = seen.isoformat() if hasattr(seen, "isoformat") else seen
        rows.append({
            "id": cid,
            "name": c.get("name"),
            "is_active": c.get("is_active", True),
            "approval_status": c.get("approval_status"),
            "students": n["students"],
            "teachers": n["teachers"],
            "halaqat": n["halaqat"],
            "recitations": n["recitations"],
            "attendance": n["attendance"],
            "finance_ops": n["finance"],
            "new_students": n["enrollment"],
            "score": round(score, 1),
            "level": _level(score),
            "breakdown": parts,
            "last_activity": seen_iso,
            "days_since_activity": (now - seen).days if seen else None,
        })

    rows.sort(key=lambda r: -r["score"])
    return {
        "days": days,
        "centers": rows,
        "totals": {
            "centers": len(rows),
            "active_centers": sum(1 for r in rows if r["score"] > 0),
            "students": sum(r["students"] for r in rows),
            "recitations": sum(r["recitations"] for r in rows),
            "attendance": sum(r["attendance"] for r in rows),
        },
    }
