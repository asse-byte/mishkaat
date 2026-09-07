/**
 * ترتيب حلقات المركز بالأداء.
 *
 * [قرار المالك 2026-09-07] «لخلق التنافس بين المعلّمين، أودّ أن يرى المعلّم
 * نسبة الأداء أو التفوّق: أيّ حلقة أفضل في المركز.»
 *
 * وهذا **استثناءٌ مقصود** من عزل الحلقات، وحدُّه في الخادم دقيق: أرقامٌ مجمّعة
 * واسمُ الحلقة وشيخِها — ولا اسمَ طالبٍ واحد من حلقةٍ أخرى. فالمحفّظ يعرف
 * موقعَ حلقته بين أخواتها ولا يقرأ بيانات غيره، وتفصيلُ الحلقة يبقى محجوباً.
 */
import { useCallback, useEffect, useState } from 'react';
import { Trophy, Users } from 'lucide-react';
import api from '@/services/api';
import { errorMessage } from '@/lib/errors';

interface HalaqahRow {
  id: string;
  name: string;
  teacher_name?: string;
  students_count: number;
  mastery: number | null;
  momentum: number | null;
  consistency: number | null;
  attendance_rate: number | null;
  is_mine: boolean;
  rank: number;
}

interface RankingResponse {
  halaqat: HalaqahRow[];
  center_average: {
    mastery: number | null; momentum: number | null;
    consistency: number | null; attendance_rate: number | null;
  };
}

/** «—» لا صفر: الحلقة بلا تسميعٍ بعد ليست بإتقان صفر، بل بلا خبر. */
const num = (v: number | null, suffix = '') =>
  v === null || v === undefined ? '—' : `${v}${suffix}`;

const MEDAL = ['🥇', '🥈', '🥉'];

export default function HalaqatRanking() {
  const [data, setData] = useState<RankingResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const r = await api.get<RankingResponse>('/halaqat-overview/ranking');
      setData(r.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل ترتيب الحلقات'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) {
    return (
      <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">
        جارٍ تحميل ترتيب الحلقات…
      </p>
    );
  }
  if (error) {
    return <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold">{error}</div>;
  }
  const rows = data?.halaqat || [];
  if (rows.length === 0) return null;

  const avg = data?.center_average;

  return (
    <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                    shadow-sm overflow-hidden">
      <div className="p-5 border-b border-[hsl(var(--border))] flex flex-wrap
                      items-center justify-between gap-3">
        <div className="min-w-0">
          <h3 className="font-bold text-base flex items-center gap-2">
            <Trophy className="w-5 h-5 text-amber-500 shrink-0" />
            ترتيب حلقات المركز
          </h3>
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
            متوسّطات الحلقة لا سجلّات طلابها — وحلقتُك مُعلَّمة.
          </p>
        </div>
        {avg && (
          <span className="text-xs font-semibold bg-[hsl(var(--muted))] px-3 py-1.5 rounded-full">
            متوسّط المركز: إتقان {num(avg.mastery, '%')} · حضور {num(avg.attendance_rate, '%')}
          </span>
        )}
      </div>

      <div className="overflow-x-auto">
        <table className="w-full text-right border-collapse min-w-[640px]">
          <thead>
            <tr className="bg-[hsl(var(--muted))] text-xs font-bold
                           text-[hsl(var(--muted-foreground))]">
              <th className="p-3 w-16 text-center">الترتيب</th>
              <th className="p-3">الحلقة</th>
              <th className="p-3 text-center">الطلاب</th>
              <th className="p-3 text-center">الإتقان</th>
              <th className="p-3 text-center">الاندفاع</th>
              <th className="p-3 text-center">الانتظام</th>
              <th className="p-3 text-center">الحضور</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-[hsl(var(--border))] text-sm">
            {rows.map(h => (
              <tr key={h.id}
                className={h.is_mine
                  ? 'bg-[hsl(var(--lamp-wash))]'
                  : 'hover:bg-[hsl(var(--muted))/30]'}>
                <td className="p-3 text-center font-bold">
                  {h.mastery !== null && h.rank <= 3
                    ? <span className="text-lg">{MEDAL[h.rank - 1]}</span>
                    : <span className="text-xs text-[hsl(var(--muted-foreground))] font-mono">
                        #{h.rank}
                      </span>}
                </td>
                <td className="p-3">
                  <span className="font-bold">{h.name}</span>
                  {h.is_mine && (
                    <span className="mr-2 text-[10px] font-bold bg-[hsl(var(--lamp))]
                                     text-[hsl(225,40%,12%)] px-2 py-0.5 rounded-full">
                      حلقتك
                    </span>
                  )}
                  <span className="block text-xs text-[hsl(var(--muted-foreground))]">
                    {h.teacher_name || '—'}
                  </span>
                </td>
                <td className="p-3 text-center text-xs">
                  <span className="inline-flex items-center gap-1">
                    <Users className="w-3 h-3 text-[hsl(var(--muted-foreground))]" />
                    {h.students_count}
                  </span>
                </td>
                <td className="p-3 text-center font-mono font-bold text-[hsl(var(--primary))]">
                  {num(h.mastery, '%')}
                </td>
                <td className="p-3 text-center font-mono">{num(h.momentum)}</td>
                <td className="p-3 text-center font-mono">{num(h.consistency, '%')}</td>
                <td className="p-3 text-center font-mono">{num(h.attendance_rate, '%')}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
