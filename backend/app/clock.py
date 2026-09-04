"""
مصدر الوقت في النظام.

`datetime.utcnow()` مهجورة ومجدولة للحذف من بايثون، وكانت مستعملة في 79 موضعاً.
البديل هنا يعيد **نفس القيمة تماماً**: توقيتاً عالمياً *ساذجاً* (بلا منطقة زمنية).

لماذا ساذجاً لا واعياً، مع أن التوصية الرسمية هي الوعي بالمنطقة؟
كل تاريخ مخزَّن في قاعدة البيانات ساذج، و MongoDB يعيده ساذجاً، والشيفرة
تقارن المخزَّن بالحاضر في عشرات المواضع (انتهاء الرموز، أقفال المحاولات،
نوافذ التقارير). لو صار الحاضر واعياً لانفجرت كل مقارنة بـ:

    TypeError: can't compare offset-naive and offset-aware datetimes

فالانتقال إلى التواريخ الواعية هجرةُ بيانات لا تبديلَ دالة: تتطلب ترحيل كل
صفّ مخزَّن ومراجعة كل مقارنة. ما يفعله هذا الملف هو إزالة الإهمال دون تغيير
قيمة واحدة — والهجرة الكاملة تبقى قراراً مستقلاً متى أُريدت.
"""

from datetime import datetime, timezone


def utcnow() -> datetime:
    """الآن بتوقيت UTC، ساذجاً — بديل مطابق لـ datetime.utcnow()."""
    return datetime.now(timezone.utc).replace(tzinfo=None)


def utc_from_timestamp(ts: float) -> datetime:
    """تحويل طابع زمني إلى UTC ساذج — بديل مطابق لـ datetime.utcfromtimestamp()."""
    return datetime.fromtimestamp(ts, timezone.utc).replace(tzinfo=None)
