/**
 * علامة مشكاة — كوّة يعلوها قوس، وفي جوفها مصباح.
 *
 * كانت العلامة قبعة تخرّج (GraduationCap) منقولة مع لوحة ألوان مشروع EduGete،
 * وهي رمز مدرسة غربية لا صلة له بدار تحفيظ. الاسم نفسه يعطي الرمز الصحيح:
 * «مَثَلُ نُورِهِ كَمِشْكَاةٍ فِيهَا مِصْبَاحٌ» — المشكاة هي الكوّة في الجدار.
 *
 * مرسومة بأشكال هندسية بسيطة لتبقى مقروءة عند 20px في الشريط الجانبي.
 */
export default function MishkaatMark({
  className = 'w-6 h-6',
  title,
}: { className?: string; title?: string }) {
  return (
    <svg
      viewBox="0 0 24 24"
      className={className}
      fill="none"
      stroke="currentColor"
      strokeWidth="1.6"
      strokeLinecap="round"
      strokeLinejoin="round"
      role={title ? 'img' : 'presentation'}
      aria-hidden={title ? undefined : true}
    >
      {title && <title>{title}</title>}
      {/* الكوّة: قوس مدبَّب يقوم على قائمتين */}
      <path d="M5 21V11a7 7 0 0 1 14 0v10" />
      {/* عتبة الكوّة */}
      <path d="M3.5 21h17" />
      {/* المصباح: لهب فوق جسم مستدير */}
      <path d="M12 8.4c.9-.8.9-1.9.3-2.9-.7 1-1.9 1.3-1.9 2.6a1.7 1.7 0 0 0 3.2.7" />
      <circle cx="12" cy="13.2" r="2.6" />
      {/* شعاعان خفيفان */}
      <path d="M12 17.4V19" opacity=".55" />
      <path d="M8.4 13.2H7M17 13.2h-1.4" opacity=".55" />
    </svg>
  );
}
