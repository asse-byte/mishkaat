"""
الأداء والتنبؤ والتحفيز — المتطلَّبات FR7 إلى FR13 من تقرير Halaqtna.

    GET  /api/performance/error-types            تصنيف الأخطاء وأوزانه
    GET  /api/performance/students/{id}          المقاييس الخمسة + التنبؤ + الأوسمة
    GET  /api/performance/students/{id}/journey  خريطة الرحلة (الأجزاء الثلاثون)
    GET  /api/performance/leaderboards           اللوحات الأربع
    GET  /api/performance/challenges/{id}        تحدّيات الطالب وتقدّمها
    POST /api/performance/recompute              إعادة تقييم الأوسمة لمركز كامل

الصلاحيات: الطالب ووليّ الأمر يريان بيانات الطالب نفسه فقط، ويريان من اللوحات
مواقعَها لا سجلّات غيرهم (FR16). check_student_access هي البوّابة الوحيدة.
"""

from datetime import timedelta
from typing import Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from app.clock import utcnow
from app.common import NOT_DELETED, check_student_access
from app.config import TOTAL_QURAN_PAGES, logger
from app.db import db
from app.errors_taxonomy import ERROR_TYPES
from app.forecast import MODEL_VERSION, fit, predict_weekly_pages, project
from app.gamification import (
    LEADERBOARDS,
    challenge_progress,
    evaluate_badges,
    student_badges,
    total_xp,
    total_xp_bulk,
)
from app.metrics import _PRESENT_STATUSES, _as_datetime, compute_all, pages_of
from app.security import get_current_user

router = APIRouter(tags=["الأداء والتنبؤ والتحفيز"])

# ذاكرة النموذج: التدريب يمرّ على تاريخ المركز كلّه، فلا يُعاد مع كل طلب.
# مفتاحها المركز، وتنتهي صلاحيتها بعد ساعة أو عند إضافة تسميع (invalidate).
_MODEL_CACHE: Dict[str, dict] = {}
_MODEL_TTL_SECONDS = 3600


def invalidate_model(center_id: Optional[str]) -> None:
    if center_id:
        _MODEL_CACHE.pop(center_id, None)


async def _load_history(student_ids: List[str]):
    """التسميعات والحضور لمجموعة طلاب باستعلامين اثنين لا باستعلامين لكل طالب."""
    recs: Dict[str, List[dict]] = {sid: [] for sid in student_ids}
    atts: Dict[str, List[dict]] = {sid: [] for sid in student_ids}
    if not student_ids:
        return recs, atts
    async for r in db.recitations.find({**NOT_DELETED, "student_id": {"$in": student_ids}}):
        recs.setdefault(r["student_id"], []).append(r)
    async for a in db.attendance.find({"student_id": {"$in": student_ids}}):
        atts.setdefault(a["student_id"], []).append(a)
    return recs, atts


async def _center_model(center_id: Optional[str]) -> Optional[dict]:
    """نموذج التنبؤ للمركز، مُدرَّباً عند الحاجة."""
    if not center_id:
        return None
    now = utcnow()
    cached = _MODEL_CACHE.get(center_id)
    if cached and (now - cached["at"]).total_seconds() < _MODEL_TTL_SECONDS:
        return cached["model"]

    ids = [str(s["_id"]) async for s in db.students.find(
        {**NOT_DELETED, "center_id": center_id, "is_active": True}, {"_id": 1})]
    recs, atts = await _load_history(ids)
    model = fit(recs, atts, now)
    _MODEL_CACHE[center_id] = {"model": model, "at": now}
    return model


def _period_stats(recitations: List[dict], attendance: List[dict], now) -> Dict[str, Dict[str, float]]:
    """إحصاءات الأسبوع والشهر التي تُقاس عليها التحدّيات."""
    out: Dict[str, Dict[str, float]] = {}
    for period, days in (("week", 7), ("month", 30)):
        since = now - timedelta(days=days)
        recs = [r for r in recitations if _as_datetime(r.get("date"), now) >= since]
        atts = [a for a in attendance if _as_datetime(a.get("date"), now) >= since]
        out[period] = {
            "pages_memorized": sum(pages_of(r) for r in recs if r.get("recitation_type") != "review"),
            "reviewed_pages": sum(pages_of(r) for r in recs if r.get("recitation_type") == "review"),
            "attended_sessions": sum(1 for a in atts if a.get("status") in _PRESENT_STATUSES),
        }
    return out


# ------------------------------------------------------------------ المسارات
@router.get("/api/performance/error-types")
async def get_error_types(current_user: dict = Depends(get_current_user)):
    """
    تصنيف الأخطاء وأوزانه.

    الواجهة تقرأ الأوزان من هنا ولا تكرّرها: نسخةٌ ثانية منها في الواجهة تعني
    أن معايرة الوزن في الخادم لا تظهر للمستخدم، فيرى رقماً يخالف ما حُسب به.
    """
    return {"error_types": ERROR_TYPES}


@router.get("/api/performance/students/{student_id}")
async def student_performance(student_id: str, current_user: dict = Depends(get_current_user)):
    """المقاييس الخمسة، والتنبؤ، والأوسمة، والنقاط — لطالب واحد."""
    student = await check_student_access(student_id, current_user)
    now = utcnow()

    recs, atts = await _load_history([student_id])
    recitations, attendance = recs.get(student_id, []), atts.get(student_id, [])
    snapshot = compute_all(recitations, attendance, now)

    model = await _center_model(student.get("center_id"))
    weekly, method = predict_weekly_pages(
        model, [snapshot["momentum"], snapshot["error_density"], snapshot["attendance_rate"]]
    )
    projection = project(snapshot["pages_memorized"], weekly, now)

    # الأوسمة تُقيَّم عند القراءة أيضاً، لا عند الكتابة وحدها: بيانات موجودة
    # قبل هذه الميزة لن تمنح أصحابها شيئاً إن لم يُقيَّم إلا على تسميع جديد.
    new_badges = await evaluate_badges(student_id, snapshot, student.get("center_id"))

    return {
        "student_id": student_id,
        "student_name": student.get("name"),
        "halaqah_name": student.get("halaqah_name"),
        "metrics": snapshot,
        "forecast": {
            **projection,
            "method": method,
            "model_version": MODEL_VERSION if method == "trained_model" else None,
            "model_r_squared": (model or {}).get("r2") if method == "trained_model" else None,
            "model_train_rows": (model or {}).get("n") if method == "trained_model" else None,
            "features": {
                "momentum": snapshot["momentum"],
                "error_density": snapshot["error_density"],
                "attendance_rate": snapshot["attendance_rate"],
            },
            # صراحةً: هذا تقدير تصميمي لا نتيجة مقيسة (NFR10 في التقرير هدفٌ يُقاس لاحقاً)
            "disclaimer": "تقدير مبنيّ على وتيرة الطالب وجودة تلاوته وحضوره، ويتغيّر بتغيّرها",
        },
        "badges": await student_badges(student_id),
        "newly_earned": [b["code"] for b in new_badges],
        "total_xp": await total_xp(student_id),
        "challenges": challenge_progress(_period_stats(recitations, attendance, now)),
    }


@router.get("/api/performance/students/{student_id}/journey")
async def student_journey(student_id: str, current_user: dict = Depends(get_current_user)):
    """
    خريطة الرحلة: الأجزاء الثلاثون وحالة كلٍّ منها.

    الطالب في التقرير (الجدول 1.1) همّه «تغذية راجعة واضحة ودافع». الرقم
    المجرّد «حفظتَ 143 صفحة» لا يقول له أين هو من المصحف؛ الخريطة تقوله.
    """
    student = await check_student_access(student_id, current_user)
    now = utcnow()
    recs, atts = await _load_history([student_id])
    recitations = recs.get(student_id, [])
    snapshot = compute_all(recitations, atts.get(student_id, []), now)

    pages_per_juz = TOTAL_QURAN_PAGES / 30.0
    done = snapshot["pages_memorized"]

    # الأجزاء التي جرت مراجعتها خلال الشهر — تُميَّز عن المحفوظ الساكن
    since = now - timedelta(days=30)
    reviewed_pages = sum(
        pages_of(r) for r in recitations
        if r.get("recitation_type") == "review" and _as_datetime(r.get("date"), now) >= since
    )

    juz = []
    for i in range(1, 31):
        start = (i - 1) * pages_per_juz
        covered = max(0.0, min(pages_per_juz, done - start))
        juz.append({
            "juz": i,
            "percent": round(100.0 * covered / pages_per_juz, 1),
            "state": "done" if covered >= pages_per_juz - 0.05 else ("active" if covered > 0 else "todo"),
        })

    return {
        "student_id": student_id,
        "student_name": student.get("name"),
        "pages_memorized": done,
        "total_pages": TOTAL_QURAN_PAGES,
        "percent": round(100.0 * done / TOTAL_QURAN_PAGES, 1),
        "reviewed_pages_last_30d": round(reviewed_pages, 1),
        "juz": juz,
    }


@router.get("/api/performance/leaderboards")
async def leaderboards(
    limit: int = Query(10, ge=1, le=50),
    halaqah_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
):
    """
    اللوحات الأربع.

    القاعدة التي تقوم عليها (تقرير Halaqtna، القسم 2.4 نقلاً عن Sailer et al.):
    الترتيب التنافسي الواحد يُثبّط من يظهر في ذيله دائماً. أربع لوحات تعني أن
    لكلّ اجتهادٍ بابَ تصدُّر.

    الطالب ووليّ الأمر يريان اللوحات — وهي بيانات مجمّعة (اسم ورتبة وقيمة) لا
    سجلّات جلسات — ويُعاد لهما موقعُهما صراحةً في own_ranks.
    """
    center_id = current_user.get("center_id")
    role = current_user.get("role")

    query = {**NOT_DELETED, "is_active": True}
    if role != "admin":
        if not center_id:
            raise HTTPException(status_code=403, detail="لا يوجد مركز مرتبط بحسابك")
        query["center_id"] = center_id
    if halaqah_id:
        query["halaqah_id"] = halaqah_id

    students = [s async for s in db.students.find(query)]
    ids = [str(s["_id"]) for s in students]
    if not ids:
        return {"boards": [], "definitions": LEADERBOARDS, "own_ranks": {}}

    recs, atts = await _load_history(ids)
    now = utcnow()
    xp = await total_xp_bulk(ids)

    rows = []
    for s in students:
        sid = str(s["_id"])
        m = compute_all(recs.get(sid, []), atts.get(sid, []), now)
        rows.append({
            "id": sid,
            "name": s.get("name"),
            "halaqah_name": s.get("halaqah_name", "غير محدّد"),
            "xp": xp.get(sid, 0),
            **{k: m[k] for k in ("momentum", "precision", "consistency", "review_depth")},
        })

    # موقع الطالب نفسه إن كان الطالب أو وليّ أمره هو السائل.
    # الربط بنفس قواعد check_student_access: user_id للطالب، ورقم الهاتف
    # لوليّ الأمر — لا بالاسم، فالاسم قابل للتعديل ذاتياً وليس مُعرِّف ملكية.
    own_id = None
    if role in ("student", "parent"):
        uid, phone = str(current_user.get("_id")), current_user.get("phone")
        for r_row, s_row in ((r, s_doc) for r, s_doc in zip(rows, students)):
            if role == "student" and (
                s_row.get("user_id") == uid or (phone and s_row.get("phone") == phone)
            ):
                own_id = r_row["id"]
                break
            if role == "parent" and phone and (
                s_row.get("parent_phone") == phone or s_row.get("phone") == phone
            ):
                own_id = r_row["id"]
                break

    boards, own_ranks = [], {}
    for board in LEADERBOARDS:
        key = board["key"]
        # من لا بيانات له لا يدخل اللوحة بصفر: الصفر حكمٌ، والغياب ليس حكماً
        ranked = sorted(
            [r for r in rows if r.get(key) is not None],
            key=lambda r: r[key], reverse=True,
        )
        for i, r in enumerate(ranked, 1):
            r[f"_rank_{key}"] = i
        if own_id:
            mine = next((r for r in ranked if r["id"] == own_id), None)
            own_ranks[key] = {
                "rank": ranked.index(mine) + 1 if mine else None,
                "value": mine[key] if mine else None,
                "of": len(ranked),
            }
        boards.append({
            **board,
            "entries": [
                {"rank": i, "id": r["id"], "name": r["name"],
                 "halaqah_name": r["halaqah_name"], "value": r[key], "xp": r["xp"]}
                for i, r in enumerate(ranked[:limit], 1)
            ],
            "total_ranked": len(ranked),
        })

    return {"boards": boards, "definitions": LEADERBOARDS, "own_ranks": own_ranks}


@router.get("/api/performance/challenges/{student_id}")
async def student_challenges(student_id: str, current_user: dict = Depends(get_current_user)):
    await check_student_access(student_id, current_user)
    now = utcnow()
    recs, atts = await _load_history([student_id])
    return {
        "student_id": student_id,
        "challenges": challenge_progress(
            _period_stats(recs.get(student_id, []), atts.get(student_id, []), now)
        ),
        "total_xp": await total_xp(student_id),
    }


@router.post("/api/performance/recompute")
async def recompute_center(current_user: dict = Depends(get_current_user)):
    """
    إعادة تقييم الأوسمة لكل طلاب المركز، وإبطال ذاكرة النموذج.

    تلزم مرّة بعد تفعيل هذه الميزة على مركز له تاريخ سابق: الأوسمة تُمنح عند
    الكتابة وعند قراءة صفحة الطالب، فمن لم تُفتح صفحتُه لن ينال ما استحقّه.
    """
    if current_user["role"] not in ("admin", "center_manager"):
        raise HTTPException(status_code=403, detail="غير مصرح")

    center_id = current_user.get("center_id")
    query = {**NOT_DELETED, "is_active": True}
    if current_user["role"] != "admin":
        if not center_id:
            raise HTTPException(status_code=403, detail="لا يوجد مركز مرتبط بحسابك")
        query["center_id"] = center_id

    students = [s async for s in db.students.find(query)]
    ids = [str(s["_id"]) for s in students]
    recs, atts = await _load_history(ids)
    now = utcnow()

    awarded = 0
    for s in students:
        sid = str(s["_id"])
        snapshot = compute_all(recs.get(sid, []), atts.get(sid, []), now)
        awarded += len(await evaluate_badges(sid, snapshot, s.get("center_id")))

    invalidate_model(center_id)
    logger.info(f"performance recompute: {len(ids)} students, {awarded} badges awarded")
    return {"students_evaluated": len(ids), "badges_awarded": awarded}
