"""
خطط المراجعة.

    GET /api/review-plans/today   ورد اليوم لكل طالبٍ في نطاق المستدعي
    GET/POST/PUT/DELETE /api/review-plans   خطّةٌ مكتوبة تُخصّص لطالب

[قرار المالك 2026-09-07] «اجعل خطة المراجعة شيئاً مفهوماً لدى معلّم الحلقة،
وكيف يفهمه ويستفيد به.»

**وما كان لا يُفهم ولا يُستفاد به.** كانت الشاشة تعرض جدولاً واحداً ثابتاً
مكتوباً في الكود — «السبت: الأجزاء 1-5، الأحد: 6-10…» — لكل طالبٍ في المركز،
سواءٌ حفظ ثلاثين جزءاً أو جزءاً واحداً. ولا تنادي هذه النقاطَ أصلاً: مجموعةُ
`review_plans` وموجّهُها لم يكن يستعملهما شيءٌ في الواجهة قطّ.

وعلامةُ «تمّت» كانت تُقارن رقمَ الجزء بحقل `start_ayah` في التسميع — فمراجعةُ
الآية الثالثة من أيّ سورة تُعلّم «السبت» منجزاً، إلى الأبد، بلا نافذةٍ زمنية.

**فصار ورد اليوم يُحسب لكل طالبٍ من محفوظه هو**: من حفظ خمسة أجزاء يدور عليها
في خمسة أيام، ومن حفظ ثلاثين يدور عليها في شهر — بمعدّلٍ يُحدّده الشيخ لكل
طالب. والدورةُ تُشتقّ من التاريخ لا من حالةٍ مخزَّنة: لا شيء «يُنسى تحديثه»،
واليومُ نفسُه يُعطي الوردَ نفسه لكل من يفتح الشاشة.

وتُقرن به إجابةُ السؤال الذي يسأله الشيخ فعلاً: **من راجع اليوم ومن تأخّر.**
"""

from datetime import date, datetime, timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter
from fastapi import Depends
from fastapi import HTTPException

from app.clock import utcnow
from app.common import NOT_DELETED, check_student_access, safe_object_id, serialize_doc
from app.config import TOTAL_QURAN_PAGES
from app.db import db
from app.metrics import compute_all
from app.models import ReviewPlanCreate
from app.scope import student_query
from app.security import get_current_user

router = APIRouter()

PAGES_PER_JUZ = TOTAL_QURAN_PAGES / 30.0

# مبدأ الدوران: كم جزءاً يُراجعه الطالب في اليوم افتراضاً، بحسب سعة محفوظه.
# القاعدة المعمول بها في حِلَق التحفيظ: يدور الحافظُ على محفوظه في شهرٍ على
# الأكثر — فمن حفظ ثلاثين جزءاً يراجع جزءاً كلَّ يوم، ومن حفظ خمسةً يراجع جزءاً
# فيختم دورتَه في خمسة أيام. والشيخ يرفع المعدّل أو يخفضه لطالبٍ بعينه.
DEFAULT_JUZ_PER_DAY = 1.0

# مبدأ التاريخ: أوّلُ يومٍ في الدورة. ثابتٌ حتى يتّفق كلُّ من يفتح الشاشة على
# الورد نفسه، ولا يتغيّر الوردُ بإعادة تحميل الصفحة.
_EPOCH = date(2026, 1, 3)   # سبتٌ، فتبدأ الدورة مع بداية الأسبوع الدراسي


def _plan_for(pages: float, juz_per_day: float, today: date) -> Optional[dict]:
    """
    وردُ اليوم: الأجزاء التي يدور عليها الطالب اليوم من محفوظه.

    None لمن لم يحفظ شيئاً بعد — ولا يُختلق له وردٌ من العدم.
    """
    memorized_juz = pages / PAGES_PER_JUZ
    if memorized_juz < 0.5:
        return None

    per_day = max(0.5, juz_per_day)
    total = max(1, int(round(memorized_juz)))
    cycle_days = max(1, int(-(-total // per_day)))     # تقريبٌ لأعلى
    day_index = (today - _EPOCH).days % cycle_days

    start = day_index * per_day + 1
    end = min(total, start + per_day - 1)
    return {
        "from_juz": round(start, 1),
        "to_juz": round(end, 1),
        "cycle_days": cycle_days,
        "day_in_cycle": day_index + 1,
        "memorized_juz": round(memorized_juz, 1),
        "pages_today": round((end - start + 1) * PAGES_PER_JUZ, 1),
    }


# ==================== Review Plans (خطط المراجعة) ====================

@router.get("/api/review-plans")
async def get_review_plans(
    center_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user)
):
    """الحصول على خطط المراجعة"""
    # [AUDIT-2026-05-22 fix: tight role gate + fail-closed; was leaking all plans to parents/students/scopeless managers]
    role = current_user["role"]
    if role not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query: dict = {}
    if role == "center_manager":
        if not current_user.get("center_id"):
            return []
        query["center_id"] = current_user["center_id"]
    elif role == "teacher":
        if not current_user.get("center_id"):
            return []
        teacher = await db.teachers.find_one({"user_id": str(current_user["_id"]), "is_active": True})
        if not teacher:
            return []
        query["teacher_id"] = str(teacher["_id"])
    elif role == "admin" and center_id:
        query["center_id"] = center_id

    plans = await db.review_plans.find(query).sort("created_at", -1).to_list(500)
    result = []
    for p in plans:
        doc = serialize_doc(p)
        if doc.get("created_at") and isinstance(doc["created_at"], datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        result.append(doc)
    return result

@router.post("/api/review-plans")
async def create_review_plan(plan: ReviewPlanCreate, current_user: dict = Depends(get_current_user)):
    """إضافة خطة مراجعة"""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    # [AUDIT-2026-05-22 fix: enforce center_id matches caller's center for non-admin;
    # validate student/teacher (if supplied) belong to the same center]
    if current_user["role"] != "admin":
        if plan.center_id != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="غير مصرح لك بإنشاء خطة في مركز آخر")

    if plan.student_id:
        student = await check_student_access(plan.student_id, current_user)
        if student.get("center_id") != plan.center_id:
            raise HTTPException(status_code=400, detail="الطالب لا ينتمي للمركز المحدد")

    if plan.teacher_id and current_user["role"] != "admin":
        try:
            t_row = await db.teachers.find_one({"_id": safe_object_id(plan.teacher_id)})
        except HTTPException:
            t_row = None
        if not t_row or t_row.get("center_id") != current_user.get("center_id"):
            raise HTTPException(status_code=403, detail="المعلم لا ينتمي لمركزك")

    data = plan.model_dump(exclude_none=True)
    data["created_at"] = utcnow()
    data["created_by"] = str(current_user["_id"])
    result = await db.review_plans.insert_one(data)
    data["id"] = str(result.inserted_id)
    data["created_at"] = data["created_at"].isoformat()
    return data


@router.put("/api/review-plans/{plan_id}")
async def update_review_plan(plan_id: str, patch: ReviewPlanCreate,
                             current_user: dict = Depends(get_current_user)):
    """تعديل خطّة مراجعة — لمن يملك إنشاءها."""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    plan = await db.review_plans.find_one({"_id": safe_object_id(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="الخطّة غير موجودة")
    if (current_user["role"] != "admin"
            and plan.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذه الخطّة تخصّ مركزاً آخر")

    changes = {k: v for k, v in patch.model_dump(exclude_unset=True).items()
               if k not in ("center_id",)}
    changes["updated_at"] = utcnow()
    changes["updated_by"] = str(current_user["_id"])
    await db.review_plans.update_one({"_id": plan["_id"]}, {"$set": changes})
    return serialize_doc({**plan, **changes})


@router.delete("/api/review-plans/{plan_id}")
async def delete_review_plan(plan_id: str,
                             current_user: dict = Depends(get_current_user)):
    """حذف خطّة مراجعة."""
    if current_user["role"] not in ["admin", "center_manager", "teacher"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    plan = await db.review_plans.find_one({"_id": safe_object_id(plan_id)})
    if not plan:
        raise HTTPException(status_code=404, detail="الخطّة غير موجودة")
    if (current_user["role"] != "admin"
            and plan.get("center_id") != current_user.get("center_id")):
        raise HTTPException(status_code=403, detail="هذه الخطّة تخصّ مركزاً آخر")

    await db.review_plans.delete_one({"_id": plan["_id"]})
    return {"message": "حُذفت الخطّة"}


@router.get("/api/review-plans/today")
async def review_today(current_user: dict = Depends(get_current_user)):
    """
    ورد اليوم لكل طالبٍ في نطاق المستدعي، ومن راجع ومن تأخّر.

    هذا ما يفتحه الشيخ صباحاً: اسمُ الطالب، وما عليه اليوم، وهل سمّعه، ومنذ
    متى لم يُراجع. لا جدولَ عامّاً يحفظه، ولا حساباً يجريه بنفسه.
    """
    if current_user["role"] not in ["admin", "super_admin", "center_manager",
                                    "teacher", "student", "parent"]:
        raise HTTPException(status_code=403, detail="غير مصرح")

    query = await student_query(current_user, {**NOT_DELETED, "is_active": True})
    if query is None:
        return {"date": utcnow().strftime("%Y-%m-%d"), "students": []}

    students = await db.students.find(query).to_list(2000)
    sids = [str(s["_id"]) for s in students]
    if not sids:
        return {"date": utcnow().strftime("%Y-%m-%d"), "students": []}

    # خططٌ مخصّصة إن وُجدت — تُغيّر المعدّل اليوميّ لطالبٍ بعينه
    plans: Dict[str, dict] = {}
    async for pl in db.review_plans.find({"student_id": {"$in": sids}}):
        plans[pl["student_id"]] = pl

    recs: Dict[str, List[dict]] = {sid: [] for sid in sids}
    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": sids}}):
        recs.setdefault(r["student_id"], []).append(r)

    now = utcnow()
    today = now.date()
    today_str = now.strftime("%Y-%m-%d")

    rows = []
    for st in students:
        sid = str(st["_id"])
        history = recs.get(sid, [])
        pages = compute_all(history, []).get("pages_memorized") or 0.0

        plan_doc = plans.get(sid) or {}
        per_day = float(plan_doc.get("juz_per_day") or DEFAULT_JUZ_PER_DAY)
        assignment = _plan_for(pages, per_day, today)

        reviews = [r for r in history if r.get("recitation_type") == "review"]
        done_today = any(
            (r.get("date_str") == today_str)
            or (isinstance(r.get("date"), datetime) and r["date"].date() == today)
            for r in reviews)

        last = None
        for r in reviews:
            d = r.get("date")
            if isinstance(d, datetime) and (last is None or d > last):
                last = d
        days_since = (now - last).days if last else None

        rows.append({
            "student_id": sid,
            "student_name": st.get("name"),
            "halaqah_id": st.get("halaqah_id"),
            "halaqah_name": st.get("halaqah_name"),
            "plan_id": str(plan_doc["_id"]) if plan_doc.get("_id") else None,
            "juz_per_day": per_day,
            "assignment": assignment,
            "reviewed_today": done_today,
            "days_since_review": days_since,
            # متأخّرٌ من مضى على آخر مراجعةٍ له أكثرُ من دورته، أو لم يُراجع قطّ
            "overdue": (assignment is not None and not done_today and (
                days_since is None or days_since > assignment["cycle_days"])),
            "reviews_count": len(reviews),
        })

    # المتأخّرون أوّلاً: الشاشة تُقدّم من يحتاج تدخّلاً
    rows.sort(key=lambda r: (not r["overdue"], r["reviewed_today"],
                             -(r["days_since_review"] or 0)))
    return {
        "date": today_str,
        "students": rows,
        "summary": {
            "total": len(rows),
            "reviewed_today": sum(1 for r in rows if r["reviewed_today"]),
            "overdue": sum(1 for r in rows if r["overdue"]),
            "no_memorization": sum(1 for r in rows if r["assignment"] is None),
        },
        "explainer": {
            "how": ("ورد اليوم يُحسب من محفوظ كل طالب: يدور على ما حفظه بمعدّل "
                    "الأجزاء المحدَّد له، فيختم دورته ثم يبدأها من جديد."),
            "default_rate": DEFAULT_JUZ_PER_DAY,
        },
    }
