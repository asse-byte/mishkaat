/**
 * رسالة الخطأ القادمة من الخادم.
 *
 * كان كلُّ نداءٍ يكتب `catch (err: any)` ثمّ يتسلّق
 * `err.response.data.detail` بيده — وهو نمطٌ يُسكِت المدقّق ويُخفي الرسالة
 * العربية التي كتبها الخادم إن اختلف شكلُ الجواب قليلاً.
 *
 * هنا تُقرأ الرسالة مرّة واحدة وبلا `any`: إن كان في الجواب `detail` نصّاً
 * عُرض، وإلا عُرض النصّ البديل. ولا تُعرض رسالة `Error` التقنية للمستخدم —
 * «Network Error» لا تقول له شيئاً.
 */
export function errorMessage(err: unknown, fallback: string): string {
  if (typeof err === 'object' && err !== null && 'response' in err) {
    const res = (err as { response?: { data?: { detail?: unknown } } }).response;
    const detail = res?.data?.detail;
    if (typeof detail === 'string' && detail.trim()) return detail;
    // FastAPI يُعيد قائمةً عند فشل التحقّق من الحمولة
    if (Array.isArray(detail) && detail.length) {
      const first = detail[0] as { msg?: unknown };
      if (typeof first?.msg === 'string') return first.msg;
    }
  }
  return fallback;
}
