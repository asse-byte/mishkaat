"""
المقاييس الأدائية الخمسة.

المصدر: تقرير Halaqtna، المتطلَّبات FR7–FR9 والجدول 3.4.

  الإتقان      Mastery      = 100 × (1 − min(1، متوسط كثافة الخطأ ÷ d_max))
  الزخم        Momentum     = متوسط أُسّي متحرّك لصفحات الأسبوع، α = 0.4
  الدقّة        Precision    = 100 × (1 − نصيب الأخطاء شديدة الوزن)
  الانتظام     Consistency  = نسبة الحضور في آخر ثماني حصص مجدولة
  عمق المراجعة  Review depth = صفحات المراجعة ÷ صفحات الحفظ الجديد خلال 4 أسابيع

قرار مقصود: **لا تُخزَّن هذه القيم في وثيقة الطالب**، بل تُحسب عند القراءة من
التسميعات والحضور. هذا ما يقرّره القسم 4.7 من التقرير: القيمة المشتقّة المخزَّنة
تنحرف عن السجلّات التي أنتجتها عند أوّل تعديل أو إبطال، فتُصبح لوحةُ الصدارة غير
قابلة للتفسير بالرجوع إلى الجلسات — وهي بالضبط الخاصّية التي يقوم عليها التحفيز
هنا (القسم 2.6: موقع الطالب في اللوحة يمكن تفسيره دائماً بالإشارة إلى سجلّاته).

الأساس صفحة لا آية: مقاييس التقرير كلّها لكل صفحة، والمشكاة تسجّل نطاق آيات.
فإن أدخل المحفّظ عدد الصفحات صراحةً استُعمل، وإلا اشتُقّ من عدد الآيات
(6236 آية ÷ 604 صفحات). الاشتقاق تقريب معلَن لا قياس.
"""

from datetime import datetime, timedelta
from typing import Dict, List, Optional

from app.clock import utcnow
from app.config import (
    CONSISTENCY_WINDOW_SESSIONS,
    HIGH_SEVERITY_THRESHOLD,
    MASTERY_DMAX,
    MOMENTUM_ALPHA,
    REVIEW_DEPTH_WINDOW_DAYS,
    VERSES_PER_PAGE,
)
from app.errors_taxonomy import (
    high_severity_count,
    is_tagged,
    total_error_count,
    weighted_error_load,
)

_PRESENT_STATUSES = {"present", "late", "excused"}


def pages_of(recitation: dict) -> float:
    """صفحات تسميعة واحدة: المُدخَل صراحةً أوّلاً، ثم الاشتقاق من الآيات."""
    explicit = recitation.get("pages_count")
    if explicit:
        try:
            v = float(explicit)
            if v > 0:
                return v
        except (TypeError, ValueError):
            pass
    start = recitation.get("start_ayah") or 0
    end = recitation.get("end_ayah") or 0
    verses = max(1, int(end) - int(start) + 1)
    return verses / VERSES_PER_PAGE


def _as_datetime(value, fallback):
    if isinstance(value, datetime):
        return value
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", ""))
        except ValueError:
            return fallback
    return fallback


def mastery(recitations: List[dict]) -> Optional[float]:
    """
    مؤشّر الإتقان. الكثافة تُحسب على المجموع لا كمتوسّط متوسّطات: تسميعةٌ من
    نصف صفحة فيها خطأ واحد لا تزن كتسميعةِ عشر صفحات فيها خطأ واحد.
    """
    if not recitations:
        return None
    pages = sum(pages_of(r) for r in recitations)
    if pages <= 0:
        return None
    density = sum(weighted_error_load(r) for r in recitations) / pages
    return round(100.0 * (1.0 - min(1.0, density / MASTERY_DMAX)), 1)


def error_density(recitations: List[dict]) -> float:
    """كثافة الخطأ الموزون لكل صفحة — سمة من سمات التنبؤ (FR10)."""
    pages = sum(pages_of(r) for r in recitations)
    if pages <= 0:
        return 0.0
    return sum(weighted_error_load(r) for r in recitations) / pages


def momentum(recitations: List[dict], now=None) -> float:
    """
    الزخم: صفحات في الأسبوع بمتوسّط أُسّي متحرّك.

    التنعيم مقصود: المجموع الخام لآخر ثلاثين يوماً (وهو ما كانت المشكاة تحسبه)
    يقفز عند أسبوع عطلة ثم يهبط، فيتأرجح التنبؤ المبني عليه. المتوسّط الأُسّي
    يُبقي وزن الأسبوع الأحدث أعلى دون أن يمحو ما قبله. والأسابيع الخالية تدخل
    الحساب أصفاراً حقيقية لا فجوات تُقفَز — وإلا كافأ المؤشّرُ الانقطاعَ.
    """
    if not recitations:
        return 0.0
    now = now or utcnow()
    new_only = [r for r in recitations if r.get("recitation_type") != "review"]
    if not new_only:
        return 0.0

    buckets: Dict[int, float] = {}
    for r in new_only:
        d = _as_datetime(r.get("date"), now)
        weeks_ago = max(0, (now - d).days // 7)
        buckets[weeks_ago] = buckets.get(weeks_ago, 0.0) + pages_of(r)
    if not buckets:
        return 0.0

    oldest = max(buckets)
    ewma = buckets.get(oldest, 0.0)
    for w in range(oldest - 1, -1, -1):
        ewma = MOMENTUM_ALPHA * buckets.get(w, 0.0) + (1 - MOMENTUM_ALPHA) * ewma
    return round(ewma, 2)


def precision(recitations: List[dict]) -> Optional[float]:
    """
    الدقّة: نصيب الأخطاء شديدة الوزن من مجموع الأخطاء، مقلوباً.

    تُحسب من التسميعات **الموسومة بالتصنيف** وحدها. العدّادات القديمة لا تحمل
    نوع الخطأ، وخريطتُها تفترض أن كل «خطأ» انقطاعُ حفظ — وهو افتراض يصحّ
    للكثافة (حيث المقدار هو المهمّ والترتيب محفوظ) ولا يصحّ هنا: لو أُدخلت
    لخرجت الدقّة صفراً لكل طالب سبقت بياناتُه التصنيف، فيتذيّل لوحةَ الدقّة
    بحكمٍ لم تُقسه، وهو عين ما صُمّمت اللوحات الأربع لتجنّبه.

    None تعني «لم يُوسَم بعد»، وتُعرض شرطةً لا صفراً.
    """
    tagged = [r for r in recitations if is_tagged(r)]
    if not tagged:
        return None
    total = sum(total_error_count(r) for r in tagged)
    if total <= 0:
        return 100.0
    severe = sum(high_severity_count(r, HIGH_SEVERITY_THRESHOLD) for r in tagged)
    return round(100.0 * (1.0 - severe / total), 1)


def consistency(attendance: List[dict]) -> Optional[float]:
    """الانتظام: نسبة الحضور في آخر ثماني حصص مجدولة للطالب."""
    if not attendance:
        return None
    now = utcnow()
    recent = sorted(attendance, key=lambda a: _as_datetime(a.get("date"), now), reverse=True)
    recent = recent[:CONSISTENCY_WINDOW_SESSIONS]
    attended = sum(1 for a in recent if a.get("status") in _PRESENT_STATUSES)
    return round(100.0 * attended / len(recent), 1)


def attendance_rate(attendance: List[dict]) -> float:
    """نسبة الحضور على كل السجلّ — سمة من سمات التنبؤ (FR10)."""
    if not attendance:
        return 1.0
    attended = sum(1 for a in attendance if a.get("status") in _PRESENT_STATUSES)
    return attended / len(attendance)


def review_depth(recitations: List[dict], now=None) -> Optional[float]:
    """
    عمق المراجعة: صفحات المراجعة ÷ صفحات الحفظ الجديد خلال أربعة أسابيع.

    يُعاد نسبةً مئوية مقصوصة عند 200: من يراجع ضِعف ما يحفظ بلغ أقصى ما يقيسه
    هذا المؤشّر، ولا يصحّ أن يتصدّر اللوحةَ من توقّف عن الحفظ نهائياً وواصل
    المراجعة — فتصير النسبة بلا حدّ.
    """
    now = now or utcnow()
    since = now - timedelta(days=REVIEW_DEPTH_WINDOW_DAYS)
    window = [r for r in recitations if _as_datetime(r.get("date"), now) >= since]
    if not window:
        return None
    reviewed = sum(pages_of(r) for r in window if r.get("recitation_type") == "review")
    fresh = sum(pages_of(r) for r in window if r.get("recitation_type") != "review")
    if fresh <= 0:
        return 200.0 if reviewed > 0 else None
    return round(min(200.0, 100.0 * reviewed / fresh), 1)


def compute_all(recitations: List[dict], attendance: List[dict], now=None) -> dict:
    """
    المقاييس الخمسة لطالب واحد.

    None تعني «لا توجد بيانات كافية»، لا «صفر». الفرق يهمّ: طالبٌ جديد بلا
    تسميع ليس طالباً إتقانُه صفر، وإدراجه في لوحة الصدارة بصفر يظلمه ويشوّه
    الترتيب معاً.
    """
    now = now or utcnow()
    return {
        "mastery": mastery(recitations),
        "momentum": momentum(recitations, now),
        "precision": precision(recitations),
        "consistency": consistency(attendance),
        "review_depth": review_depth(recitations, now),
        # سمات التنبؤ مكشوفة عمداً حتى تكون النتيجة قابلة للتفسير أمام وليّ الأمر
        "error_density": round(error_density(recitations), 3),
        "attendance_rate": round(attendance_rate(attendance), 3),
        "pages_memorized": round(
            sum(pages_of(r) for r in recitations if r.get("recitation_type") != "review"), 1
        ),
        "sessions_count": len(recitations),
    }
