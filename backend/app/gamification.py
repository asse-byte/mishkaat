"""
طبقة التحفيز متعدّدة المعايير (FR11–FR13).

المصدر: تقرير Halaqtna، القسمان 2.4 و4.3.

الفكرة التي تُميّز هذا التصميم — والتي جاءت من المحفّظين أنفسهم كما يروي القسم
5.3 من التقرير — هي أن **الترتيب الواحد يُثبّط بالضبط من هم أحوج إلى التشجيع**.
الطالب الذي يظهر آخرَ القائمة كل أسبوع يتعلّم أن يتجاهلها. فبدل لوحة واحدة
مركَّبة (وهي ما كانت المشكاة تعرضه) أربعُ لوحات مستقلّة:

    الزخم        من يحفظ أكثر
    الدقّة        من يُخطئ أخفَّ الأخطاء
    الانتظام     من لا يتغيّب
    عمق المراجعة  من يُثبّت ما حفظ

فالبطيء الذي لا يغيب يتصدّر الانتظام، ومن يحفظ قليلاً ويراجع كثيراً يتصدّر
عمق المراجعة. وكلّها مشتقّة من **نفس** سجلّات الجلسات لا من نظام نقاط موازٍ،
فموقع الطالب في أيّ لوحة يمكن تفسيره بالإشارة إلى تسميعاته وحضوره.

سجلّ النقاط (xp_ledger) لا يُعدَّل ولا يُحذف: قيدٌ لكل منح، ومفتاح فريد على
(الطالب، السبب، المصدر) يمنع المنح مرّتين إن أُعيدت معالجة نفس التسميعة.
"""

from typing import Dict, List, Optional

from app.clock import utcnow
from app.config import logger
from app.db import db

# ------------------------------------------------------------------ الأوسمة
# condition_metric: أحد مفاتيح المقاييس أو عدّاد خاصّ. condition_value الحدّ.
BADGES: List[dict] = [
    {"code": "FIRST_STEP",   "label_ar": "أوّل الطريق",     "icon": "sparkles",
     "desc_ar": "أوّل تسميع مسجَّل",              "metric": "sessions_count", "value": 1,   "xp": 20},
    {"code": "JUZ_1",        "label_ar": "الجزء الأوّل",     "icon": "book",
     "desc_ar": "حفظ عشرين صفحة",                "metric": "pages_memorized", "value": 20,  "xp": 100},
    {"code": "JUZ_5",        "label_ar": "خمسة أجزاء",      "icon": "book",
     "desc_ar": "حفظ مئة صفحة",                  "metric": "pages_memorized", "value": 100, "xp": 300},
    {"code": "HALF_QURAN",   "label_ar": "نصف القرآن",      "icon": "award",
     "desc_ar": "حفظ ثلاثمئة وصفحتين",           "metric": "pages_memorized", "value": 302, "xp": 800},
    {"code": "KHATMA",       "label_ar": "الختمة",          "icon": "trophy",
     "desc_ar": "حفظ المصحف كاملاً",             "metric": "pages_memorized", "value": 604, "xp": 2000},
    {"code": "PRECISE",      "label_ar": "متقن التلاوة",     "icon": "target",
     "desc_ar": "دقّة 90% فأعلى",                "metric": "precision",      "value": 90,  "xp": 150},
    {"code": "MASTERY_90",   "label_ar": "إتقان عالٍ",       "icon": "star",
     "desc_ar": "مؤشّر إتقان 90% فأعلى",          "metric": "mastery",        "value": 90,  "xp": 150},
    {"code": "NEVER_ABSENT", "label_ar": "لا يتغيّب",        "icon": "calendar-check",
     "desc_ar": "حضور تامّ في آخر ثماني حصص",     "metric": "consistency",    "value": 100, "xp": 200},
    {"code": "REVIEWER",     "label_ar": "مُثبِّت الحفظ",     "icon": "refresh",
     "desc_ar": "مراجعة تعادل الحفظ الجديد",      "metric": "review_depth",   "value": 100, "xp": 200},
    {"code": "STEADY",       "label_ar": "ثابت الخطى",      "icon": "trending-up",
     "desc_ar": "زخم صفحتين في الأسبوع فأكثر",    "metric": "momentum",       "value": 2,   "xp": 120},
]

BADGE_BY_CODE = {b["code"]: b for b in BADGES}

# ---------------------------------------------------------------- التحدّيات
# التقدّم يُحسب عند القراءة من نفس السجلّات، فلا يوجد عمود progress ينحرف.
CHALLENGES: List[dict] = [
    {"code": "WEEK_PAGES_3",  "label_ar": "ثلاث صفحات هذا الأسبوع", "icon": "book",
     "period": "week",  "metric": "pages_memorized", "target": 3,  "xp": 60},
    {"code": "WEEK_NO_ABSENT", "label_ar": "أسبوع بلا غياب",        "icon": "calendar-check",
     "period": "week",  "metric": "attended_sessions", "target": 2, "xp": 50},
    {"code": "MONTH_PAGES_12", "label_ar": "اثنتا عشرة صفحة هذا الشهر", "icon": "trending-up",
     "period": "month", "metric": "pages_memorized", "target": 12, "xp": 250},
    {"code": "MONTH_REVIEW",   "label_ar": "مراجعة عشر صفحات هذا الشهر", "icon": "refresh",
     "period": "month", "metric": "reviewed_pages",  "target": 10, "xp": 200},
]

CHALLENGE_BY_CODE = {c["code"]: c for c in CHALLENGES}

# اللوحات الأربع: المفتاح، عنوانه، وهل الأعلى أفضل
LEADERBOARDS = [
    {"key": "momentum",     "label_ar": "الزخم",        "unit": "صفحة/أسبوع", "desc_ar": "من يحفظ أكثر"},
    {"key": "precision",    "label_ar": "الدقّة",         "unit": "%",         "desc_ar": "من يُخطئ أخفَّ الأخطاء"},
    {"key": "consistency",  "label_ar": "الانتظام",      "unit": "%",         "desc_ar": "من لا يتغيّب"},
    {"key": "review_depth", "label_ar": "عمق المراجعة",  "unit": "%",         "desc_ar": "من يُثبّت ما حفظ"},
]


# ------------------------------------------------------------ نقاط الخبرة
async def award_xp(
    student_id: str,
    amount: int,
    reason: str,
    source_id: Optional[str] = None,
    center_id: Optional[str] = None,
) -> bool:
    """
    قيدٌ في سجلّ النقاط. يُعيد True إن كُتب فعلاً.

    الفهرس الفريد على (student_id, reason, source_id) هو ما يجعل هذه العملية
    عديمةَ الأثر عند التكرار: إعادةُ معالجة نفس التسميعة لا تمنح النقاط مرّتين.
    الخطأ 11000 هنا نجاحٌ لا فشل.
    """
    if amount <= 0:
        return False
    try:
        await db.xp_ledger.insert_one({
            "student_id": student_id,
            "center_id": center_id,
            "amount": int(amount),
            "reason": reason,
            "source_id": source_id,
            "created_at": utcnow(),
        })
        return True
    except Exception as exc:                       # DuplicateKeyError وغيره
        if "E11000" in str(exc) or "duplicate" in str(exc).lower():
            return False
        logger.warning(f"xp award failed for {student_id}: {exc}")
        return False


async def total_xp(student_id: str) -> int:
    cur = db.xp_ledger.aggregate([
        {"$match": {"student_id": student_id}},
        {"$group": {"_id": None, "total": {"$sum": "$amount"}}},
    ])
    async for row in cur:
        return int(row.get("total") or 0)
    return 0


async def total_xp_bulk(student_ids: List[str]) -> Dict[str, int]:
    """مجموع النقاط لعدّة طلاب باستعلام واحد — لوحة الصدارة تحتاجها دفعةً."""
    if not student_ids:
        return {}
    out: Dict[str, int] = {sid: 0 for sid in student_ids}
    cur = db.xp_ledger.aggregate([
        {"$match": {"student_id": {"$in": student_ids}}},
        {"$group": {"_id": "$student_id", "total": {"$sum": "$amount"}}},
    ])
    async for row in cur:
        out[row["_id"]] = int(row.get("total") or 0)
    return out


# ---------------------------------------------------------------- الأوسمة
async def evaluate_badges(student_id: str, snapshot: dict, center_id: Optional[str] = None) -> List[dict]:
    """
    يمنح كل وسام تحقّق شرطُه ولم يُمنح بعد. يُعيد الأوسمة الجديدة فقط.

    الوسام يُمنح مرّة واحدة ولا يُسحب: من بلغ دقّةَ 90% ثم تراجع لا يُنزع منه
    ما ناله — الوسام شهادةُ إنجازٍ وقع، لا حالةٌ راهنة. الحالة الراهنة تعرضها
    المقاييس واللوحات.
    """
    earned_codes = set()
    async for row in db.student_badges.find({"student_id": student_id}, {"badge_code": 1}):
        earned_codes.add(row.get("badge_code"))

    new_badges = []
    for badge in BADGES:
        if badge["code"] in earned_codes:
            continue
        value = snapshot.get(badge["metric"])
        if value is None or value < badge["value"]:
            continue
        try:
            await db.student_badges.insert_one({
                "student_id": student_id,
                "center_id": center_id,
                "badge_code": badge["code"],
                "earned_at": utcnow(),
            })
        except Exception as exc:
            if "E11000" not in str(exc) and "duplicate" not in str(exc).lower():
                logger.warning(f"badge insert failed: {exc}")
            continue
        await award_xp(student_id, badge["xp"], "badge", badge["code"], center_id)
        new_badges.append(badge)
    return new_badges


async def student_badges(student_id: str) -> List[dict]:
    """كل الأوسمة مع حالة نيلها — المعروضة للطالب تشمل ما لم ينله بعد كهدف."""
    earned: Dict[str, object] = {}
    async for row in db.student_badges.find({"student_id": student_id}):
        earned[row.get("badge_code")] = row.get("earned_at")
    out = []
    for b in BADGES:
        out.append({
            **{k: b[k] for k in ("code", "label_ar", "desc_ar", "icon", "metric", "value", "xp")},
            "earned": b["code"] in earned,
            "earned_at": earned.get(b["code"]),
        })
    return out


# --------------------------------------------------------------- التحدّيات
def challenge_progress(period_stats: Dict[str, Dict[str, float]]) -> List[dict]:
    """
    تقدّم كل تحدٍّ من إحصاءات الفترة المحسوبة عند القراءة.

    period_stats = {"week": {...}, "month": {...}} وكل منها يحمل
    pages_memorized و reviewed_pages و attended_sessions.
    """
    out = []
    for c in CHALLENGES:
        stats = period_stats.get(c["period"], {})
        current = float(stats.get(c["metric"], 0) or 0)
        pct = min(100.0, 100.0 * current / c["target"]) if c["target"] else 0.0
        out.append({
            **{k: c[k] for k in ("code", "label_ar", "icon", "period", "metric", "target", "xp")},
            "current": round(current, 1),
            "progress_percent": round(pct, 1),
            "completed": current >= c["target"],
        })
    return out
