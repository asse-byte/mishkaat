/**
 * استخدام المنصّة لكل مركز — لوحة إدارة النظام.
 *
 * [قرار المالك 2026-09-07] «مدير النظام ينبغي أن يعرف مدى مستوى استخدام المنصّة
 * لأيّ مركز، بناءً على نسبة حركة البيانات والمعاملات داخل حساب المركز. والهدف
 * لو صار حساب مدير النظام يوماً ملكاً لهيئةٍ عامّة لمراقبة مراكز التحفيظ.»
 *
 * والفرق عمّا كان: الجدولُ السابق يقيس **الحجم** (كم طالباً سُجّل)، وهذا يقيس
 * **الحركة** (كم عملاً جرى في المدّة). ومركزٌ سجّل مئة طالبٍ ثمّ هجر النظام
 * سنةً يتصدّر بالأوّل ويقع في ذيل الثاني — وهذا هو المقصود.
 *
 * والدرجةُ منسوبة إلى حجم المركز: مركزٌ بعشرين طالباً يُسمّع كلَّ يوم أنشطُ من
 * مركزٍ بمئتين يُسمّع مرّةً في الأسبوع، وإن كان عددُ تسميعات الثاني أكبر.
 */
import { useCallback, useEffect, useState } from 'react';
import { Activity, BookOpen, CalendarCheck, Wallet, UserPlus } from 'lucide-react';
import api from '@/services/api';
import { errorMessage } from '@/lib/errors';
import { formatNumber } from '@/lib/format';

interface CenterActivity {
  id: string;
  name: string;
  is_active: boolean;
  students: number;
  teachers: number;
  halaqat: number;
  recitations: number;
  attendance: number;
  finance_ops: number;
  new_students: number;
  score: number;
  level: string;
  last_activity?: string | null;
  days_since_activity?: number | null;
}

const WINDOWS = [
  { days: 7, label: 'أسبوع' },
  { days: 30, label: 'شهر' },
  { days: 90, label: 'ثلاثة أشهر' },
  { days: 365, label: 'سنة' },
];

/** ألوانُ المستوى — الأخضر عملٌ جارٍ، والأحمر حسابٌ ساكن. */
function levelTone(score: number): string {
  if (score >= 75) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (score >= 45) return 'text-blue-700 bg-blue-50 border-blue-200';
  if (score >= 15) return 'text-amber-700 bg-amber-50 border-amber-200';
  return 'text-rose-700 bg-rose-50 border-rose-200';
}

function sinceLabel(days: number | null | undefined): string {
  if (days === null || days === undefined) return 'لا حركة في المدّة';
  if (days === 0) return 'اليوم';
  if (days === 1) return 'أمس';
  return `قبل ${days} يوماً`;
}

export default function CenterActivityPanel() {
  const [days, setDays] = useState(30);
  const [rows, setRows] = useState<CenterActivity[]>([]);
  const [totals, setTotals] = useState<Record<string, number>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const r = await api.get<{ centers: CenterActivity[]; totals: Record<string, number> }>(
        '/admin/centers-activity', { params: { days } });
      setRows(r.data.centers || []);
      setTotals(r.data.totals || {});
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل حركة المراكز'));
    } finally {
      setLoading(false);
    }
  }, [days]);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="bg-[hsl(var(--card))] rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                    shadow-sm p-6 space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b pb-3">
        <div className="min-w-0">
          <h3 className="text-lg font-bold flex items-center gap-2">
            <Activity className="w-5 h-5 text-[hsl(var(--primary))]" />
            استخدام المنصّة في كل مركز
          </h3>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
            حركةُ التسميع والحضور والمالية خلال المدّة، منسوبةً إلى حجم المركز —
            لا عددُ المسجَّلين فيه.
          </p>
        </div>
        <div className="flex gap-1.5 shrink-0">
          {WINDOWS.map(w => (
            <button key={w.days} onClick={() => setDays(w.days)}
              className={`px-3 py-1.5 rounded-lg text-xs font-bold border transition-colors ${
                days === w.days
                  ? 'border-[hsl(var(--primary))] bg-[hsl(var(--muted))] text-[hsl(var(--primary))]'
                  : 'border-[hsl(var(--border))]'}`}>
              {w.label}
            </button>
          ))}
        </div>
      </div>

      {error && (
        <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold">{error}</div>
      )}

      {!loading && rows.length > 0 && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          {[
            { label: 'مراكز فيها حركة', value: `${totals.active_centers ?? 0} / ${totals.centers ?? 0}`, Icon: Activity },
            { label: 'تسميعات', value: formatNumber(totals.recitations ?? 0), Icon: BookOpen },
            { label: 'سجلّات حضور', value: formatNumber(totals.attendance ?? 0), Icon: CalendarCheck },
            { label: 'طلاب', value: formatNumber(totals.students ?? 0), Icon: UserPlus },
          ].map(({ label, value, Icon }) => (
            <div key={label} className="rounded-[var(--radius)] border border-[hsl(var(--border))] p-3">
              <Icon className="w-4 h-4 text-[hsl(var(--primary))] mb-1" />
              <p className="text-lg font-bold font-mono">{value}</p>
              <p className="text-[11px] text-[hsl(var(--muted-foreground))]">{label}</p>
            </div>
          ))}
        </div>
      )}

      {loading ? (
        <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">جارٍ الحساب…</p>
      ) : rows.length === 0 ? (
        <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">لا مراكز</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-right border-collapse min-w-[820px]">
            <thead>
              <tr className="border-b border-[hsl(var(--border))] text-xs
                             text-[hsl(var(--muted-foreground))] font-bold">
                <th className="pb-3 text-center w-14">#</th>
                <th className="pb-3">المركز</th>
                <th className="pb-3 text-center">الحجم</th>
                <th className="pb-3 text-center">تسميع</th>
                <th className="pb-3 text-center">حضور</th>
                <th className="pb-3 text-center">مالية</th>
                <th className="pb-3 text-center">آخر حركة</th>
                <th className="pb-3 text-center">درجة الاستخدام</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-[hsl(var(--border))]/50 text-sm">
              {rows.map((c, idx) => (
                <tr key={c.id} className="hover:bg-[hsl(var(--muted))]/30 transition-colors">
                  <td className="py-3 text-center font-mono text-xs text-[hsl(var(--muted-foreground))]">
                    {idx + 1}
                  </td>
                  <td className="py-3">
                    <span className="font-bold block">{c.name}</span>
                    {!c.is_active && (
                      <span className="text-[10px] text-rose-600 font-bold">موقوف</span>
                    )}
                  </td>
                  <td className="py-3 text-center text-xs text-[hsl(var(--muted-foreground))]">
                    {c.students} طالب · {c.halaqat} حلقة
                  </td>
                  <td className="py-3 text-center font-mono">{formatNumber(c.recitations)}</td>
                  <td className="py-3 text-center font-mono">{formatNumber(c.attendance)}</td>
                  <td className="py-3 text-center font-mono">
                    <span className="inline-flex items-center gap-1">
                      <Wallet className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                      {formatNumber(c.finance_ops)}
                    </span>
                  </td>
                  <td className="py-3 text-center text-xs text-[hsl(var(--muted-foreground))]">
                    {sinceLabel(c.days_since_activity)}
                  </td>
                  <td className="py-3">
                    <div className="flex items-center justify-center gap-2">
                      <div className="w-16 bg-[hsl(var(--muted))] h-2 rounded-full overflow-hidden">
                        <div className="h-full rounded-full bg-[hsl(var(--primary))]"
                          style={{ width: `${Math.min(100, c.score)}%` }} />
                      </div>
                      <span className={`text-[10px] font-bold px-2 py-1 rounded-full border
                                        ${levelTone(c.score)}`}>
                        {c.level}
                      </span>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
