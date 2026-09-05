"""
تصنيف أخطاء التسميع الموزون.

المصدر: تقرير Halaqtna، القسم 2.2 والمتطلَّب FR6. الملاحظة المحورية في
Hassan & Zailaini أنّ الخطأ المسجَّل نصّاً حرّاً **لا يمكن مقارنته** لا بين
الطلاب ولا عبر الزمن. ولذلك تُغلَق القائمة على أربعة أنواع، لكلٍّ وزن شدّة
عددي، ويُخزَّن في التسميعة رمزُ النوع وحده لا وزنُه.

هذه النقطة الأخيرة ليست تفصيلاً: لو خُزِّن الوزن مع كل خطأ لصار تعديلُ الوزن
لاحقاً (والتقرير يقول صراحةً إن الأوزان مبدئية وستُعاير) عاجزاً عن إصلاح
البيانات القديمة، ولاختلف نفسُ الخطأ في وزنه من سجلّ إلى آخر. الوزن يعيش هنا
في مكان واحد — وهو ما يسمّيه التقرير إزالةَ التبعية المتعدّية (3NF، القسم 4.7).

لماذا أربعة فقط: المحفّظ يُعلّم الخطأ على هاتفه أثناء الحلقة، فقائمةٌ طويلة
لا تُستعمل. الأربعة تجمع التمييزات اللغوية في نطاقات شدّة عملية.
"""

from typing import Dict, List

# الترتيب من الأشدّ إلى الأخفّ. الأوزان من الجدول 3.4 في التقرير.
ERROR_TYPES: List[dict] = [
    {
        "code": "MEM_GAP",
        "label_ar": "انقطاع الحفظ",
        "label_en": "Memorisation gap",
        "description_ar": "توقّف الطالب ولم يُكمل إلا بالتلقين",
        "weight": 0.85,
        "color": "danger",
    },
    {
        "code": "LNK_ERR",
        "label_ar": "خطأ في الربط",
        "label_en": "Linking error",
        "description_ar": "انتقل إلى آية أو موضع غير الصحيح",
        "weight": 0.50,
        "color": "warn",
    },
    {
        "code": "TAJ_ERR",
        "label_ar": "خطأ تجويد",
        "label_en": "Tajweed error",
        "description_ar": "خلل في المخرج أو المدّ أو الوقف",
        "weight": 0.25,
        "color": "info",
    },
    {
        "code": "SLF_CRT",
        "label_ar": "تصحيح ذاتي",
        "label_en": "Self-correction",
        "description_ar": "أخطأ ثم صحّح بنفسه بلا تلقين",
        "weight": 0.05,
        "color": "ok",
    },
]

WEIGHTS: Dict[str, float] = {e["code"]: e["weight"] for e in ERROR_TYPES}
CODES = set(WEIGHTS)

# خريطة العدّادات القديمة → التصنيف الجديد.
#
# التسميعات المسجَّلة قبل هذا التصنيف تحمل ثلاثة عدّادات حرّة. تجاهلُها يعني
# أن كل مقياس أدائي يبدأ من الصفر ويُهمل تاريخ المركز كلَّه، وهو أسوأ من
# تقريبٍ معلَن. فتُقرأ العدّادات القديمة على أنها أخطاء من هذه الأنواع:
#
#   mistakes_count      → MEM_GAP   (خطأ احتاج تدخّل المحفّظ)
#   tajweed_errors_count→ TAJ_ERR
#   hesitations_count   → SLF_CRT   (تردّد بلا خطأ مستقرّ)
#
# النسبة بين الأوزان القديمة كانت 4.0 : 2.0 : 1.5، وبين الجديدة 0.85 : 0.25 :
# 0.05 — أي أن الترتيب محفوظ والتباعد أوسع. لا يُدّعى أن القيمتين متطابقتان.
LEGACY_FIELD_MAP = {
    "mistakes_count": "MEM_GAP",
    "tajweed_errors_count": "TAJ_ERR",
    "hesitations_count": "SLF_CRT",
}


def normalize_error_tags(recitation: dict) -> Dict[str, int]:
    """
    عدد الأخطاء لكل نوع في تسميعة واحدة، سواءٌ كانت موسومة بالتصنيف الجديد
    أو محمولة على العدّادات القديمة. الجديد يسبق: إن وُجد error_tags استُعمل
    وحده، فلا تُحسب الأخطاء مرّتين في تسميعة كُتبت بالطريقتين.
    """
    tags = recitation.get("error_tags")
    if isinstance(tags, dict) and tags:
        return {c: int(n) for c, n in tags.items() if c in CODES and int(n or 0) > 0}
    out: Dict[str, int] = {}
    for field, code in LEGACY_FIELD_MAP.items():
        n = int(recitation.get(field) or 0)
        if n > 0:
            out[code] = out.get(code, 0) + n
    return out


def weighted_error_load(recitation: dict) -> float:
    """مجموع (عدد الخطأ × وزنه) لتسميعة واحدة."""
    return sum(WEIGHTS[c] * n for c, n in normalize_error_tags(recitation).items())


def high_severity_count(recitation: dict, threshold: float) -> int:
    """عدد الأخطاء التي وزنها ≥ الحدّ — مدخل مقياس الدقّة."""
    return sum(n for c, n in normalize_error_tags(recitation).items() if WEIGHTS[c] >= threshold)


def total_error_count(recitation: dict) -> int:
    return sum(normalize_error_tags(recitation).values())


def is_tagged(recitation: dict) -> bool:
    """
    هل مرّت هذه التسميعة على واجهة الوسم؟

    القاموس الفارغ **موسوم**: يعني أن المحفّظ نظر في الأنواع الأربعة ولم يجد
    خطأً — وهي دقّة 100% لا «لا بيانات». أما غياب الحقل أو None فيعني سجلّاً
    سبق التصنيف (أو عميلاً قديماً)، ولا تُحسب منه دقّة.
    """
    return isinstance(recitation.get("error_tags"), dict)
