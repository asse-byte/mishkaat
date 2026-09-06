/**
 * زخارف الشهادة — هندسةٌ إسلامية مرسومة، لا رموز نصّية.
 *
 * كانت زوايا الشهادة أربعةَ محارف «❖» — رمزٌ من جدول المحارف يختلف رسمُه من
 * خطٍّ إلى خطّ وقد لا يُرسم أصلاً، ولا صلة له بالزخرفة الإسلامية.
 *
 * فرُسمت هنا أشكالٌ حقيقية بالمسار: النجمة الثمانية (خاتم سليمان) وهي أشهر
 * وحدات الزخرفة في المصاحف، وتفريعةُ الزاوية، والشريطُ المتشابك. وكلُّها
 * `currentColor` فتأخذ لون سياقها، و`vector-effect` فلا يغلظ خطُّها عند
 * التكبير للطباعة.
 */
import { useId } from 'react';

/** النجمة الثمانية: مربّعان متراكبان بزاوية 45°. */
export function EightPointStar({ className = 'w-8 h-8' }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none"
      stroke="currentColor" strokeWidth="3" aria-hidden="true">
      <rect x="18" y="18" width="64" height="64" />
      <rect x="18" y="18" width="64" height="64" transform="rotate(45 50 50)" />
      <circle cx="50" cy="50" r="12" />
    </svg>
  );
}

/**
 * تفريعة زاوية — قوسٌ ومحاور وثلاث حبّات.
 * تُدار بـ `rotate` من المستدعي لتُغطّي الزوايا الأربع بمكوّنٍ واحد.
 */
export function CornerFlourish({ className = 'w-16 h-16' }: { className?: string }) {
  return (
    <svg viewBox="0 0 100 100" className={className} fill="none"
      stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" aria-hidden="true">
      <path d="M4 96 L4 40 A36 36 0 0 1 40 4 L96 4" />
      <path d="M14 96 L14 46 A32 32 0 0 1 46 14 L96 14" strokeWidth="1.4" />
      <path d="M14 62 C 34 62, 48 48, 48 28" strokeWidth="1.4" />
      <path d="M26 84 C 52 84, 68 68, 68 42" strokeWidth="1.4" />
      <circle cx="48" cy="24" r="3.2" fill="currentColor" stroke="none" />
      <circle cx="70" cy="38" r="2.6" fill="currentColor" stroke="none" />
      <circle cx="24" cy="66" r="2.6" fill="currentColor" stroke="none" />
    </svg>
  );
}

/** شريطٌ زخرفي متكرّر يفصل أقسام الشهادة. */
export function OrnamentDivider({ className = '' }: { className?: string }) {
  return (
    <div className={`flex items-center justify-center gap-3 ${className}`} aria-hidden="true">
      <svg viewBox="0 0 120 12" className="h-3 w-24" fill="none"
        stroke="currentColor" strokeWidth="1.4">
        <path d="M0 6 H36" />
        <path d="M42 6 l6 -5 l6 5 l-6 5 z" />
        <path d="M60 1 v10 M55 6 h10" />
        <path d="M66 6 l6 -5 l6 5 l-6 5 z" />
        <path d="M84 6 H120" />
      </svg>
    </div>
  );
}

/**
 * علامةٌ مائية خفيفة خلف نصّ الشهادة: شبكةٌ من النجوم الثمانية.
 *
 * تُرسم بـ `<pattern>` لا بصورة: تُطبع نظيفةً في أي مقاس، ولا تُحمَّل ملفاً.
 */
export function StarWatermark(
  { className = '', style }: { className?: string; style?: React.CSSProperties },
) {
  // معرّفٌ فريد لكل نسخة: صفحةُ الشهادات ترسم ورقتين معاً (معاينةً على الشاشة
  // ونسخةً للطباعة)، فمعرّفٌ ثابت يعني عنصرين بالمعرّف نفسه في مستندٍ واحد —
  // و url(#id) يتعلّق بالأوّل، فتظهر الزخرفة في إحداهما وتغيب عن الأخرى.
  const id = useId();
  return (
    // width/height صريحان: الـ svg عنصرٌ مُستبدَل له مقاسٌ ذاتيّ (300×150)،
    // و inset وحده لا يمدّه — فكانت الزخرفة تظهر في مستطيلٍ صغير أعلى الورقة
    // بدل أن تعمّها.
    <svg className={className} style={style} aria-hidden="true"
      width="100%" height="100%" preserveAspectRatio="none"
      xmlns="http://www.w3.org/2000/svg">
      <defs>
        <pattern id={id} width="86" height="86" patternUnits="userSpaceOnUse">
          <g fill="none" stroke="currentColor" strokeWidth="1">
            <rect x="24" y="24" width="38" height="38" />
            <rect x="24" y="24" width="38" height="38" transform="rotate(45 43 43)" />
          </g>
        </pattern>
      </defs>
      <rect width="100%" height="100%" fill={`url(#${id})`} />
    </svg>
  );
}
