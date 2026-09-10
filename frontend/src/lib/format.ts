/**
 * تنسيق الأرقام — مصدر واحد.
 *
 * كان في التطبيق أربعة منسِّقات مختلفة: ar-SA (أرقام هندية وفاصلة عربية)،
 * و fr-FR (مسافة رفيعة لا فاصلة)، و toLocaleString() بلا لغة (تتبع لغة
 * المتصفّح فتختلف من جهاز إلى جهاز)، وأرقامٌ خام بلا تجميع. فيرى المستخدم
 * الرقمَ نفسه بأربع صور في أربع شاشات.
 *
 * القرار: فاصلة إنجليزية كل ثلاث خانات، وأرقام لاتينية — 1,000,000.
 *
 * والسبب ليس الجمال: الرقم غير المجمَّع 1000000 لا يُقرأ بالنظر، فيزيد المستخدم
 * صفراً أو ينقصه ولا يلحظ. ولهذا لا يكفي التنسيق عند العرض: NumberInput يجمّع
 * أثناء الكتابة، فيرى المدخِل ما كتبه مقروءاً قبل الحفظ لا بعده.
 */

/** أرقام لاتينية بفاصلة كل ثلاث خانات. */
export function formatNumber(value: number | string | null | undefined, decimals = 0): string {
  if (value === null || value === undefined || value === '') return '';
  const n = typeof value === 'string' ? Number(stripGrouping(value)) : value;
  if (!Number.isFinite(n)) return '';
  return new Intl.NumberFormat('en-US', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

/** مبلغ مالي: الرقم المجمَّع ثمّ رمز العملة. */
export function formatAmount(
  value: number | string | null | undefined,
  currency = 'FCFA',
): string {
  const formatted = formatNumber(value);
  return formatted === '' ? '' : `${formatted} ${currency}`;
}

/** يُزيل الفواصل والمسافات ليعود النصّ رقماً صالحاً للإرسال. */
export function stripGrouping(text: string): string {
  return (text || '')
    .replace(/[,  \s٬]/g, '')   // فاصلة، ومسافات غير فاصلة، وفاصلة عربية
    .replace(/[٠-٩]/g, d => String(d.charCodeAt(0) - 0x0660))  // أرقام هندية
    .replace(/[۰-۹]/g, d => String(d.charCodeAt(0) - 0x06F0)); // أرقام فارسية
}

/** النصّ المكتوب → رقم. NaN تعني «لا رقم فيه». */
export function parseNumber(text: string): number {
  const cleaned = stripGrouping(text).replace(/[^\d.-]/g, '');
  return cleaned === '' ? NaN : Number(cleaned);
}

/**
 * يُجمّع ما كُتب مع الحفاظ على ما هو قيد الكتابة.
 *
 * تُبقى النقطة العشرية والأصفار بعدها كما كُتبت: لو نُسّق «12.» إلى «12» لاختفت
 * النقطة من تحت إصبع المستخدم في اللحظة التي كتبها فيها.
 */
export function formatWhileTyping(text: string): string {
  const cleaned = stripGrouping(text).replace(/[^\d.]/g, '');
  if (cleaned === '') return '';
  const [intPart, ...rest] = cleaned.split('.');
  const grouped = intPart === '' ? '' : formatNumber(Number(intPart));
  if (rest.length === 0) return grouped;
  return `${grouped}.${rest.join('').slice(0, 2)}`;
}
