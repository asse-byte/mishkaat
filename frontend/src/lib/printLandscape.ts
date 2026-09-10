/**
 * طباعةٌ أفقيّة لورقةٍ بعينها.
 *
 * الشهادة مُصمَّمة بنسبة A4 العرضية (297×210)، وطباعتُها على ورقةٍ طوليّة
 * تُصغّرها إلى ثلثَي الصفحة وتترك أسفلها فارغاً — فتخرج شهادةٌ صغيرة في أعلى
 * ورقةٍ كبيرة.
 *
 * و`@page` لا تقبل مُحدِّداً، فلا يمكن أن يُقال في ملفّ CSS ثابت «أفقيّة
 * للشهادة وطوليّة لغيرها». فتُحقن القاعدة عند الضغط وتُرفع بعد انتهاء
 * الطباعة، حتى لا يخرج الإيصالُ المالي أفقيّاً لأن أحداً طبع شهادةً قبله.
 */
const STYLE_ID = 'mishkaat-landscape-page';

export function printLandscape(delayMs = 400): void {
  let style = document.getElementById(STYLE_ID) as HTMLStyleElement | null;
  if (!style) {
    style = document.createElement('style');
    style.id = STYLE_ID;
    style.textContent = '@page { size: A4 landscape; margin: 8mm; }';
    document.head.appendChild(style);
  }

  const cleanup = () => {
    document.getElementById(STYLE_ID)?.remove();
    window.removeEventListener('afterprint', cleanup);
  };
  window.addEventListener('afterprint', cleanup);

  // مهلةٌ تكفي لرسم الورقة وتحميل شعار المركز قبل فتح نافذة الطباعة
  window.setTimeout(() => {
    window.print();
    // متصفّحاتٌ لا تُطلق afterprint — تُرفع القاعدة على كل حال
    window.setTimeout(cleanup, 1500);
  }, delayMs);
}
