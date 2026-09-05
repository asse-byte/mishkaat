"""
التنبؤ بموعد الختم — نموذج انحدار خطّي متعدّد السمات (FR10).

المصدر: تقرير Halaqtna، القسمان 2.3 و4.3 والمتطلَّب FR10. الفكرة التي يقوم
عليها الفصل: يُتنبَّأ بإنتاجية الأسبوع (صفحات) من ثلاث سمات «يفكّر فيها
المحفّظ أصلاً»:

    1. الزخم               momentum        صفحات/أسبوع (متوسط أُسّي)
    2. كثافة الخطأ الموزون  error_density   خطأ موزون/صفحة
    3. نسبة الحضور         attendance_rate 0..1

ما الذي يختلف عن تنبؤ المشكاة السابق؟ ذاك كان انحداراً على **الكمّية وحدها**:
آيات متراكمة مقابل الأيام. طالبان يحفظان العدد نفسه يحصلان على التاريخ نفسه،
وإن كان أحدهما ينقطع نصف الحصص ويُخطئ في كل صفحة. هذه هي المساهمة التي يصرّح
بها التقرير في القسم 2.6: «جودة التلاوة، لا كمّيتها وحدها، تؤثّر في التاريخ
المتوقَّع».

لماذا نموذج مُدرَّب لا صيغة يدوية: بثلاث سمات لا يمكن ملاءمة معاملات من تاريخ
طالب واحد بلا إفراط في الملاءمة. فيُدرَّب النموذج على تاريخ **المركز كلّه** —
كل (طالب، أسبوع) صفٌّ واحد: سماته من الأسابيع السابقة، وهدفه صفحات ذلك
الأسبوع. ثم يُطبَّق على الطالب المطلوب.

الحلّ بالمعادلات الطبيعية (X'X)β = X'y وحذف غاوس بالتمحور الجزئي — لا حاجة
إلى numpy ولا إلى خدمة بايثون منفصلة كما في تصميم التقرير، لأن الخادم هنا
بايثون أصلاً.

**تحذير على الصدق**: هذا نموذج تصميمي على بيانات المركز، وليس نتيجة مُقاسة.
التقرير نفسه يُصنّف هدف «80% من التنبؤات ضمن ±أسبوعين» على أنه هدف تصميمي
يُقاس لاحقاً (NFR10، الجدول 3.4). لذلك تُعاد مع كل تنبؤ: طريقتُه، وعدد صفوف
تدريبه، ومعامل تحديده — ولا يُقدَّم رقمُ ثقةٍ لا يسنده شيء.
"""

from datetime import timedelta
from typing import Dict, List, Optional, Tuple

from app.clock import utcnow
from app.config import TOTAL_QURAN_PAGES, logger
from app.metrics import (
    _as_datetime,
    attendance_rate,
    error_density,
    momentum,
    pages_of,
)

MODEL_VERSION = "mishkaat-lr-3feat-1.0"

# أقل عدد صفوف تدريب يُعتدّ به. أقلّ منه يعود النظام إلى المعدّل الشخصي.
MIN_TRAIN_ROWS = 12

# أقلّ إنتاجية أسبوعية تُقبل حتى لا يُقسَّم على صفر أو على رقم سالب
MIN_WEEKLY_PAGES = 0.05

PAGES_PER_JUZ = TOTAL_QURAN_PAGES / 30.0


# ----------------------------------------------------------------- جبر خطّي
def _solve(a: List[List[float]], b: List[float]) -> Optional[List[float]]:
    """حذف غاوس بالتمحور الجزئي. None عند الشذوذ."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        pivot = max(range(col, n), key=lambda r: abs(m[r][col]))
        if abs(m[pivot][col]) < 1e-12:
            return None
        m[col], m[pivot] = m[pivot], m[col]
        pv = m[col][col]
        for r in range(col + 1, n):
            f = m[r][col] / pv
            if f:
                for c in range(col, n + 1):
                    m[r][c] -= f * m[col][c]
    x = [0.0] * n
    for r in range(n - 1, -1, -1):
        s = m[r][n] - sum(m[r][c] * x[c] for c in range(r + 1, n))
        x[r] = s / m[r][r]
    return x


def _ols(rows: List[Tuple[List[float], float]]) -> Optional[dict]:
    """انحدار خطّي بأصغر المربّعات مع حدّ ثابت. يُعيد المعاملات و R²."""
    if len(rows) < MIN_TRAIN_ROWS:
        return None
    k = len(rows[0][0]) + 1                       # +1 للحدّ الثابت
    xtx = [[0.0] * k for _ in range(k)]
    xty = [0.0] * k
    for feats, y in rows:
        x = [1.0] + list(feats)
        for i in range(k):
            xty[i] += x[i] * y
            for j in range(k):
                xtx[i][j] += x[i] * x[j]
    beta = _solve(xtx, xty)
    if beta is None:
        return None

    ys = [y for _, y in rows]
    mean_y = sum(ys) / len(ys)
    ss_tot = sum((y - mean_y) ** 2 for y in ys)
    ss_res = 0.0
    for feats, y in rows:
        pred = beta[0] + sum(b * f for b, f in zip(beta[1:], feats))
        ss_res += (y - pred) ** 2
    r2 = 1.0 - (ss_res / ss_tot) if ss_tot > 1e-12 else 0.0
    return {
        "beta": _constrain_signs(beta),
        "beta_raw": beta,
        "r2": round(max(-1.0, min(1.0, r2)), 3),
        "n": len(rows),
    }


# اتجاه كل سمة معروف من المجال، فلا يُترك للبيانات وحدها:
#   الزخم        ↑  حفظٌ أكثر لا يُبطئ
#   كثافة الخطأ  ↓  خطأٌ أكثر لا يُسرّع
#   نسبة الحضور  ↑  حضورٌ أكثر لا يُبطئ
FEATURE_SIGNS = (+1, -1, +1)


def _constrain_signs(beta: List[float]) -> List[float]:
    """
    يُصفّر أيّ معامل خالف اتجاهه المعروف.

    الانحدار على بيانات مركز صغير قد يُخرج معاملاً موجباً لكثافة الخطأ: من
    يقرأ صفحات أكثر يتراكم عليه خطأ أكثر، فيلتقط النموذج الارتباطَ لا السببية.
    لو تُرك كذلك لقال النظام لوليّ الأمر إن كثرة أخطاء ابنه تُقدّم موعد ختمه —
    وهو ما يُفقد التنبؤَ مصداقيتَه كلَّها مهما حسُن R².

    التصفير لا القلب: نحن نرفض ادّعاءً يخالف المجال، ولا ندّعي ضدَّه بلا دليل.
    """
    out = list(beta)
    for i, sign in enumerate(FEATURE_SIGNS, start=1):
        if i < len(out) and out[i] * sign < 0:
            out[i] = 0.0
    return out


# --------------------------------------------------------- بناء صفوف التدريب
def build_training_rows(
    recitations_by_student: Dict[str, List[dict]],
    attendance_by_student: Dict[str, List[dict]],
    now=None,
) -> List[Tuple[List[float], float]]:
    """
    صفٌّ لكل (طالب، أسبوع) فيه حفظٌ سابق.

    السمات تُحسب من **ما قبل** الأسبوع فقط، والهدف صفحات الأسبوع نفسه. لو
    حُسبت السمات على الفترة كلها لتسرّب الهدفُ إلى مدخلاته وصار R² وهماً.
    """
    now = now or utcnow()
    rows: List[Tuple[List[float], float]] = []

    for sid, recs in recitations_by_student.items():
        if len(recs) < 3:
            continue
        atts = attendance_by_student.get(sid, [])
        dated = sorted(
            ((_as_datetime(r.get("date"), now), r) for r in recs), key=lambda p: p[0]
        )
        first = dated[0][0]
        total_weeks = max(1, int((now - first).days // 7))

        for w in range(1, total_weeks + 1):
            w_start = first + timedelta(days=7 * w)
            w_end = w_start + timedelta(days=7)

            past_recs = [r for d, r in dated if d < w_start]
            if len(past_recs) < 2:
                continue
            target_pages = sum(
                pages_of(r)
                for d, r in dated
                if w_start <= d < w_end and r.get("recitation_type") != "review"
            )
            past_atts = [a for a in atts if _as_datetime(a.get("date"), now) < w_start]

            rows.append((
                [
                    momentum(past_recs, w_start),
                    error_density(past_recs),
                    attendance_rate(past_atts),
                ],
                target_pages,
            ))
    return rows


def fit(recitations_by_student, attendance_by_student, now=None) -> Optional[dict]:
    rows = build_training_rows(recitations_by_student, attendance_by_student, now)
    model = _ols(rows)
    if model is None:
        logger.info(f"forecast: not enough training rows ({len(rows)}) — falling back")
    return model


# ------------------------------------------------------------------- التنبؤ
def predict_weekly_pages(model: Optional[dict], features: List[float]) -> Tuple[float, str]:
    """
    إنتاجية الأسبوع المتوقَّعة، والطريقة المستعملة.

    عند غياب النموذج — أو حين يخرج بقيمة غير معقولة — يُستعمل الزخم نفسه
    كتقدير، وهو ما كان النظام يفعله ضمناً. الاسم المُعاد يقول أيّهما جرى، فلا
    يظهر التقدير الاحتياطي بمظهر النموذج.
    """
    mom = features[0]
    if model:
        beta = model["beta"]
        pred = beta[0] + sum(b * f for b, f in zip(beta[1:], features))
        # حارس المعقولية: النموذج المُدرَّب على بيانات قليلة قد يُخرج قيمة سالبة
        # أو أضعافَ ما حفظه الطالبُ يوماً. عندها لا يُقدَّم على أنه نموذج.
        if MIN_WEEKLY_PAGES <= pred <= max(4.0 * max(mom, 1.0), 20.0):
            return pred, "trained_model"
    return max(mom, MIN_WEEKLY_PAGES), "momentum_fallback"


def project(
    pages_done: float,
    weekly_pages: float,
    now=None,
) -> Dict[str, Optional[str]]:
    """موعدا ختم الجزء الحالي والقرآن كاملاً من إنتاجية أسبوعية."""
    now = now or utcnow()
    weekly = max(MIN_WEEKLY_PAGES, weekly_pages)
    daily = weekly / 7.0

    juz_index = min(30, int(pages_done // PAGES_PER_JUZ) + 1)
    pages_into_juz = pages_done - (juz_index - 1) * PAGES_PER_JUZ
    juz_remaining = max(0.0, PAGES_PER_JUZ - pages_into_juz)
    quran_remaining = max(0.0, TOTAL_QURAN_PAGES - pages_done)

    def date_after(pages: float) -> Optional[str]:
        if pages <= 0:
            return None
        days = pages / daily
        if days > 365 * 60:            # أبعد من عمرٍ كامل: لا يُعرض تاريخاً موهماً
            return None
        return (now + timedelta(days=days)).strftime("%Y-%m-%d")

    return {
        "current_juz": juz_index,
        "pages_done": round(pages_done, 1),
        "juz_pages_remaining": round(juz_remaining, 1),
        "quran_pages_remaining": round(quran_remaining, 1),
        "juz_completion_date": date_after(juz_remaining),
        "juz_eta_days": round(juz_remaining / daily) if juz_remaining > 0 else 0,
        "quran_completion_date": date_after(quran_remaining),
        "quran_eta_days": round(quran_remaining / daily) if quran_remaining > 0 else 0,
        "projected_weekly_pages": round(weekly, 2),
    }
