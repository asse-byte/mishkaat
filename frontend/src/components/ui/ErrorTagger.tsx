import { useEffect, useState } from 'react';
import api from '@/services/api';

/**
 * وسم أخطاء التسميع بتصنيف مغلق موزون (FR6).
 *
 * كان الحقل الوحيد «عدد الأخطاء: 3». وثلاثةُ تصحيحاتٍ ذاتية ليست كثلاثة
 * انقطاعات في الحفظ، فالرقم الواحد يخلط ما لا يُخلط ولا يقبل المقارنة بين
 * طالبين ولا عبر الزمن — وهي ملاحظة Hassan & Zailaini التي بُني عليها التصنيف.
 *
 * الأوزان تُقرأ من الخادم ولا تُكتب هنا: نسخةٌ ثانية منها في الواجهة تعني أن
 * معايرة الوزن في الخادم لا تظهر للمحفّظ، فيرى رقماً يخالف ما حُسب به.
 */

export interface ErrorType {
  code: string;
  label_ar: string;
  description_ar: string;
  weight: number;
  color: 'danger' | 'warn' | 'info' | 'ok';
}

const TONE: Record<ErrorType['color'], { bg: string; text: string; ring: string }> = {
  danger: { bg: 'bg-[hsl(var(--danger-wash))]', text: 'text-[hsl(var(--danger))]', ring: 'hsl(var(--danger))' },
  warn:   { bg: 'bg-[hsl(var(--warn-wash))]',   text: 'text-[hsl(var(--warn))]',   ring: 'hsl(var(--warn))' },
  info:   { bg: 'bg-[hsl(var(--info-wash))]',   text: 'text-[hsl(var(--info))]',   ring: 'hsl(var(--info))' },
  ok:     { bg: 'bg-[hsl(var(--ok-wash))]',     text: 'text-[hsl(var(--ok))]',     ring: 'hsl(var(--ok))' },
};

export function useErrorTypes() {
  const [types, setTypes] = useState<ErrorType[]>([]);
  useEffect(() => {
    let alive = true;
    api.get('/performance/error-types')
      .then(({ data }) => { if (alive) setTypes(data.error_types || []); })
      .catch(() => { /* الوسم اختياري: يبقى النموذج صالحاً بدونه */ });
    return () => { alive = false; };
  }, []);
  return types;
}

export default function ErrorTagger({
  types,
  value,
  onChange,
}: {
  types: ErrorType[];
  value: Record<string, number>;
  onChange: (v: Record<string, number>) => void;
}) {
  if (types.length === 0) return null;

  const set = (code: string, n: number) => {
    const next = { ...value };
    if (n <= 0) delete next[code];
    else next[code] = n;
    onChange(next);
  };

  const load = types.reduce((s, t) => s + t.weight * (value[t.code] || 0), 0);
  const total = Object.values(value).reduce((s, n) => s + n, 0);

  return (
    <div>
      <div className="flex items-baseline justify-between mb-2 gap-2 flex-wrap">
        <label className="block text-sm font-bold text-[hsl(var(--foreground))]">
          الأخطاء حسب نوعها
        </label>
        {total > 0 && (
          <span className="text-xs text-[hsl(var(--ink-3))]">
            {total} خطأ · حِمل موزون <span className="amount">{load.toFixed(2)}</span>
          </span>
        )}
      </div>

      <div className="space-y-2">
        {types.map(t => {
          const tone = TONE[t.color] ?? TONE.info;
          const n = value[t.code] || 0;
          return (
            <div
              key={t.code}
              className={`flex items-center gap-3 p-2.5 rounded-[var(--radius-sm)] border ${
                n > 0 ? tone.bg : 'bg-transparent'
              }`}
              style={{ borderColor: n > 0 ? tone.ring : 'hsl(var(--line))' }}
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className={`text-sm font-semibold ${n > 0 ? tone.text : ''}`}>{t.label_ar}</span>
                  <span className="text-[10px] text-[hsl(var(--ink-3))] tabular-nums shrink-0">
                    وزن {t.weight}
                  </span>
                </div>
                <p className="text-xs text-[hsl(var(--ink-3))] truncate">{t.description_ar}</p>
              </div>

              {/* أزرار لا حقل رقمي: المحفّظ يَسِم أثناء الحلقة على هاتفه */}
              <div className="flex items-center gap-1 shrink-0">
                <button
                  type="button"
                  aria-label={`إنقاص ${t.label_ar}`}
                  onClick={() => set(t.code, Math.max(0, n - 1))}
                  disabled={n === 0}
                  className="w-9 h-9 rounded-lg border border-[hsl(var(--line))] text-lg leading-none
                             disabled:opacity-35 hover:bg-[hsl(var(--surface-2))] transition-colors"
                >
                  −
                </button>
                <span className="w-8 text-center font-bold tabular-nums text-sm">{n}</span>
                <button
                  type="button"
                  aria-label={`زيادة ${t.label_ar}`}
                  onClick={() => set(t.code, n + 1)}
                  className="w-9 h-9 rounded-lg border border-[hsl(var(--line))] text-lg leading-none
                             hover:bg-[hsl(var(--surface-2))] transition-colors"
                >
                  +
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
