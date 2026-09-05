import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Loader2, Target, TrendingUp, CalendarCheck, RefreshCw } from 'lucide-react';
import api from '@/services/api';
import { useAuth } from '@/contexts/AuthContext';
import PageHeader from '@/components/ui/PageHeader';

/**
 * لوحات الصدارة الأربع.
 *
 * الفكرة ليست أربع نسخ من لوحة واحدة، بل أربعة معايير مستقلّة. الترتيب
 * التنافسي الواحد يُثبّط بالضبط من يظهر في ذيله كل أسبوع — وهو أحوج الطلاب
 * إلى التشجيع. فالبطيء الذي لا يتغيّب يتصدّر «الانتظام»، ومن يحفظ قليلاً
 * ويراجع كثيراً يتصدّر «عمق المراجعة».
 *
 * وكلّها مشتقّة من نفس سجلّات التسميع والحضور لا من نقاط موازية، فموقع
 * الطالب في أيّ لوحة يمكن تفسيره بالرجوع إلى جلساته.
 */

interface Entry {
  rank: number; id: string; name: string; halaqah_name: string;
  value: number; xp: number;
}

interface Board {
  key: string; label_ar: string; unit: string; desc_ar: string;
  entries: Entry[]; total_ranked: number;
}

interface OwnRank { rank: number | null; value: number | null; of: number }

const ICONS: Record<string, React.ElementType> = {
  momentum: TrendingUp, precision: Target, consistency: CalendarCheck, review_depth: RefreshCw,
};

const MEDAL = ['bg-[hsl(var(--lamp))] text-[hsl(225,40%,12%)]',
               'bg-[hsl(var(--muted))] text-[hsl(var(--ink))]',
               'bg-[hsl(var(--warn-wash))] text-[hsl(var(--warn))]'];

export default function Leaderboards() {
  const { user, hasRole } = useAuth();
  const [boards, setBoards] = useState<Board[]>([]);
  const [ownRanks, setOwnRanks] = useState<Record<string, OwnRank>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // الطالب ووليّ الأمر يريان اللوحات دون روابط إلى ملفّات غيرهم
  const canOpenProfiles = hasRole('admin') || hasRole('center_manager') || hasRole('teacher');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const { data } = await api.get('/performance/leaderboards', { params: { limit: 10 } });
      setBoards(data.boards || []);
      setOwnRanks(data.own_ranks || {});
    } catch (e: any) {
      setError(e.response?.data?.detail || 'تعذّر تحميل لوحات الصدارة');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 text-[hsl(var(--primary))] animate-spin" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="لوحات الصدارة"
        subtitle="أربعة معايير مستقلّة: لكلّ اجتهادٍ بابُ تصدُّر"
      >
        <button onClick={load} className="btn-outline-teal text-sm">
          <RefreshCw className="w-4 h-4" /> تحديث
        </button>
      </PageHeader>

      {error && (
        <div className="card p-4 text-sm text-[hsl(var(--danger))]">{error}</div>
      )}

      {!error && boards.length === 0 && (
        <div className="card p-8 text-center text-[hsl(var(--ink-3))]">
          لا توجد بيانات كافية بعد. تظهر اللوحات بعد تسجيل التسميع والحضور.
        </div>
      )}

      <div className="grid lg:grid-cols-2 gap-5">
        {boards.map(board => {
          const Icon = ICONS[board.key] || TrendingUp;
          const own = ownRanks[board.key];
          return (
            <div key={board.key} className="card p-5">
              <div className="flex items-start gap-3 mb-4">
                <div className="w-9 h-9 rounded-lg bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))]
                                flex items-center justify-center shrink-0">
                  <Icon className="w-4.5 h-4.5 text-[hsl(var(--lamp-strong))]" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="text-base font-bold leading-tight">{board.label_ar}</h3>
                  <p className="text-xs text-[hsl(var(--ink-3))]">{board.desc_ar}</p>
                </div>
                <span className="text-[11px] text-[hsl(var(--ink-3))] shrink-0 tabular-nums">
                  {board.total_ranked} طالب
                </span>
              </div>

              {board.entries.length === 0 ? (
                <p className="text-sm text-[hsl(var(--ink-3))] py-4 text-center">لا بيانات في هذا المعيار بعد.</p>
              ) : (
                <ol className="space-y-1.5">
                  {board.entries.map(e => {
                    const mine = own?.rank === e.rank && (user?.role === 'student' || user?.role === 'parent');
                    const row = (
                      <div className={`flex items-center gap-3 px-3 py-2 rounded-[var(--radius-sm)] transition-colors
                                      ${mine ? 'bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))]'
                                             : 'hover:bg-[hsl(var(--surface-2))]'}`}>
                        <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold
                                          tabular-nums shrink-0 ${MEDAL[e.rank - 1] || 'bg-[hsl(var(--surface-2))] text-[hsl(var(--ink-3))]'}`}>
                          {e.rank}
                        </span>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-semibold truncate">{e.name}</p>
                          <p className="text-[11px] text-[hsl(var(--ink-3))] truncate">{e.halaqah_name}</p>
                        </div>
                        <span className="text-sm font-bold tabular-nums shrink-0">
                          {e.value}
                          <span className="text-[10px] font-normal text-[hsl(var(--ink-3))] mr-1">{board.unit}</span>
                        </span>
                      </div>
                    );
                    return (
                      <li key={e.id}>
                        {canOpenProfiles
                          ? <Link to={`/performance/${e.id}`}>{row}</Link>
                          : row}
                      </li>
                    );
                  })}
                </ol>
              )}

              {/* موقع الطالب نفسه حين لا يكون ضمن العشرة الأوائل */}
              {own && own.rank && own.rank > board.entries.length && (
                <div className="mt-3 pt-3 border-t border-[hsl(var(--line-2))] text-xs text-[hsl(var(--ink-3))]">
                  ترتيبك: <b className="text-[hsl(var(--ink))] amount">{own.rank}</b> من {own.of}
                  {own.value !== null && <> · <span className="amount">{own.value}</span> {board.unit}</>}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}
