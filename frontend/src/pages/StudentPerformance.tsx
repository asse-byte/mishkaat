import { useCallback, useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import {
  Activity, Award, BookOpen, CalendarCheck, Loader2, RefreshCw,
  Printer, Sparkles, Star, Target, TrendingUp, Trophy,
} from 'lucide-react';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';
import StudentReportSheet from '@/components/ui/StudentReportSheet';

/**
 * صفحة أداء الطالب — المقاييس الخمسة، والتنبؤ، وخريطة الرحلة، والأوسمة.
 *
 * كل رقم هنا يُعرض مع ما يفسّره: المقياس واسمه وما يقيسه، والتنبؤ مع سماته
 * الثلاث وطريقته. الرقم بلا تفسيره لا يُقنع وليَّ أمر ولا يفيد محفّظاً.
 */

interface Metrics {
  mastery: number | null;
  momentum: number;
  precision: number | null;
  consistency: number | null;
  review_depth: number | null;
  error_density: number;
  attendance_rate: number;
  pages_memorized: number;
  sessions_count: number;
}

interface Forecast {
  current_juz: number;
  juz_completion_date: string | null;
  juz_eta_days: number;
  quran_completion_date: string | null;
  quran_eta_days: number;
  projected_weekly_pages: number;
  method: string;
  model_r_squared: number | null;
  model_train_rows: number | null;
  features: { momentum: number; error_density: number; attendance_rate: number };
  disclaimer: string;
}

interface Badge {
  code: string; label_ar: string; desc_ar: string; icon: string;
  value: number; xp: number; earned: boolean; earned_at: string | null;
}

interface Challenge {
  code: string; label_ar: string; icon: string; period: string;
  target: number; current: number; progress_percent: number; completed: boolean; xp: number;
}

interface Perf {
  student_name: string;
  halaqah_name?: string;
  center_name?: string;
  metrics: Metrics;
  forecast: Forecast;
  badges: Badge[];
  total_xp: number;
  challenges: Challenge[];
}

interface Journey {
  pages_memorized: number;
  total_pages: number;
  percent: number;
  reviewed_pages_last_30d: number;
  juz: { juz: number; percent: number; state: 'done' | 'active' | 'todo' }[];
}

const ICONS: Record<string, React.ElementType> = {
  sparkles: Sparkles, book: BookOpen, award: Award, trophy: Trophy, target: Target,
  star: Star, 'calendar-check': CalendarCheck, refresh: RefreshCw, 'trending-up': TrendingUp,
};

/** المقاييس الخمسة وما يقيسه كلٌّ منها — النصّ جزء من المقياس لا زينة حوله. */
const METRIC_CARDS = [
  { key: 'mastery',      label: 'الإتقان',       unit: '%',           hint: 'كلّما قلّ الخطأ في الصفحة ارتفع' },
  { key: 'momentum',     label: 'الزخم',         unit: 'صفحة/أسبوع',  hint: 'وتيرة الحفظ، مُنعَّمة عبر الأسابيع' },
  { key: 'precision',    label: 'الدقّة',          unit: '%',           hint: 'نصيب الأخطاء الخفيفة من مجموعها' },
  { key: 'consistency',  label: 'الانتظام',      unit: '%',           hint: 'الحضور في آخر ثماني حصص' },
  { key: 'review_depth', label: 'عمق المراجعة',  unit: '%',           hint: 'المراجعة نسبةً إلى الحفظ الجديد' },
] as const;

export default function StudentPerformance() {
  const { studentId } = useParams();
  const [perf, setPerf] = useState<Perf | null>(null);
  const [journey, setJourney] = useState<Journey | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    if (!studentId) return;
    try {
      setLoading(true);
      setError('');
      const [p, j] = await Promise.all([
        api.get(`/performance/students/${studentId}`),
        api.get(`/performance/students/${studentId}/journey`),
      ]);
      setPerf(p.data);
      setJourney(j.data);
    } catch (e: any) {
      setError(e.response?.data?.detail || 'تعذّر تحميل بيانات الأداء');
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => { load(); }, [load]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 text-[hsl(var(--primary))] animate-spin" />
    </div>
  );

  if (error || !perf) return (
    <div className="card p-8 text-center">
      <p className="text-[hsl(var(--ink-3))]">{error || 'لا توجد بيانات'}</p>
    </div>
  );

  const m = perf.metrics;
  const f = perf.forecast;
  const earned = perf.badges.filter(b => b.earned);

  return (
    <>
      {/* ورقة وليّ الأمر: لا تظهر على الشاشة، وهي كلّ ما يُطبع */}
      <StudentReportSheet
        studentName={perf.student_name}
        halaqahName={perf.halaqah_name}
        centerName={perf.center_name}
        metrics={m}
        forecast={f}
        journeyPercent={journey?.percent ?? 0}
        totalPages={journey?.total_pages ?? 604}
        badges={perf.badges}
        totalXp={perf.total_xp}
      />

    <div className="space-y-6 animate-fade-in print:hidden">
      <PageHeader
        title={perf.student_name}
        subtitle={`${perf.halaqah_name || 'بلا حلقة'} · ${m.sessions_count} تسميعة · ${perf.total_xp} نقطة`}
      >
        <button onClick={() => window.print()} className="btn-primary text-sm">
          <Printer className="w-4 h-4" /> تقرير لوليّ الأمر
        </button>
        <Link to={`/analytics/${studentId}`} className="btn-outline-teal text-sm">
          <Activity className="w-4 h-4" /> الرسوم البيانية
        </Link>
      </PageHeader>

      {/* ---------------- المقاييس الخمسة ---------------- */}
      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-5 gap-3 stagger">
        {METRIC_CARDS.map(c => {
          const v = m[c.key as keyof Metrics] as number | null;
          return (
            <div key={c.key} className="card p-4">
              <p className="eyebrow">{c.label}</p>
              <p className="num-display text-3xl mt-1 text-[hsl(var(--ink))]">
                {v === null ? '—' : v}
                {v !== null && <span className="text-xs font-normal text-[hsl(var(--ink-3))] mr-1">{c.unit}</span>}
              </p>
              <p className="text-[11px] text-[hsl(var(--ink-3))] mt-1.5 leading-snug">{c.hint}</p>
            </div>
          );
        })}
      </div>

      {/* ---------------- التنبؤ ---------------- */}
      <div className="card p-5">
        <h3 className="text-base font-bold mb-1">موعد الختم المتوقَّع</h3>
        <p className="text-xs text-[hsl(var(--ink-3))] mb-4">{f.disclaimer}</p>

        <div className="grid sm:grid-cols-2 gap-4">
          <div className="p-4 rounded-[var(--radius)] bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))]">
            <p className="eyebrow">الجزء {f.current_juz}</p>
            <p className="num-display text-2xl mt-1 text-[hsl(var(--lamp-strong))]">
              {f.juz_completion_date || 'غير محدَّد'}
            </p>
            <p className="text-xs text-[hsl(var(--ink-3))] mt-1">
              بعد <span className="amount">{f.juz_eta_days}</span> يوماً تقريباً
            </p>
          </div>
          <div className="p-4 rounded-[var(--radius)] bg-[hsl(var(--surface-2))] border border-[hsl(var(--line))]">
            <p className="eyebrow">المصحف كاملاً</p>
            <p className="num-display text-2xl mt-1">{f.quran_completion_date || 'غير محدَّد'}</p>
            <p className="text-xs text-[hsl(var(--ink-3))] mt-1">
              بوتيرة <span className="amount">{f.projected_weekly_pages}</span> صفحة في الأسبوع
            </p>
          </div>
        </div>

        {/* السمات الثلاث: التنبؤ الذي لا يُفسَّر لا يُصدَّق */}
        <div className="mt-4 pt-4 border-t border-[hsl(var(--line-2))]">
          <p className="eyebrow mb-2">محسوب من</p>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="px-2.5 py-1 rounded-full bg-[hsl(var(--surface-2))] border border-[hsl(var(--line))]">
              الزخم <b className="amount">{f.features.momentum}</b> صفحة/أسبوع
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[hsl(var(--surface-2))] border border-[hsl(var(--line))]">
              كثافة الخطأ <b className="amount">{f.features.error_density}</b> لكل صفحة
            </span>
            <span className="px-2.5 py-1 rounded-full bg-[hsl(var(--surface-2))] border border-[hsl(var(--line))]">
              الحضور <b className="amount">{Math.round(f.features.attendance_rate * 100)}</b>%
            </span>
          </div>
          <p className="text-[11px] text-[hsl(var(--ink-3))] mt-2">
            {f.method === 'trained_model'
              ? `نموذج مُدرَّب على ${f.model_train_rows} أسبوعاً من بيانات المركز (R² ${f.model_r_squared})`
              : 'تقدير من وتيرة الطالب نفسه — بيانات المركز لا تكفي لتدريب نموذج بعد'}
          </p>
        </div>
      </div>

      {/* ---------------- خريطة الرحلة ---------------- */}
      {journey && (
        <div className="card p-5">
          <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
            <h3 className="text-base font-bold">خريطة الرحلة</h3>
            <p className="text-xs text-[hsl(var(--ink-3))]">
              <span className="amount">{journey.pages_memorized}</span> من {journey.total_pages} صفحة
              · <span className="amount">{journey.percent}</span>%
            </p>
          </div>
          <div className="grid grid-cols-6 sm:grid-cols-10 gap-1.5">
            {journey.juz.map(j => (
              <div
                key={j.juz}
                title={`الجزء ${j.juz} — ${j.percent}%`}
                className={`aspect-square rounded-md flex items-center justify-center text-[11px] font-bold tabular-nums border ${
                  j.state === 'done'
                    ? 'bg-[hsl(var(--lamp))] text-[hsl(225,40%,12%)] border-transparent'
                    : j.state === 'active'
                      ? 'bg-[hsl(var(--lamp-wash))] text-[hsl(var(--lamp-strong))] border-[hsl(var(--lamp-line))]'
                      : 'bg-[hsl(var(--surface-2))] text-[hsl(var(--ink-3))] border-[hsl(var(--line))]'
                }`}
              >
                {j.juz}
              </div>
            ))}
          </div>
          <p className="text-[11px] text-[hsl(var(--ink-3))] mt-3">
            المراجعة خلال ثلاثين يوماً: <span className="amount">{journey.reviewed_pages_last_30d}</span> صفحة
          </p>
        </div>
      )}

      {/* ---------------- التحدّيات ---------------- */}
      <div className="card p-5">
        <h3 className="text-base font-bold mb-4">التحدّيات الجارية</h3>
        <div className="grid sm:grid-cols-2 gap-3">
          {perf.challenges.map(ch => {
            const Icon = ICONS[ch.icon] || Target;
            return (
              <div key={ch.code} className="p-3 rounded-[var(--radius-sm)] border border-[hsl(var(--line))]">
                <div className="flex items-center gap-2 mb-2">
                  <Icon className={`w-4 h-4 shrink-0 ${ch.completed ? 'text-[hsl(var(--ok))]' : 'text-[hsl(var(--ink-3))]'}`} />
                  <span className="text-sm font-semibold flex-1 min-w-0">{ch.label_ar}</span>
                  <span className="text-xs text-[hsl(var(--ink-3))] tabular-nums shrink-0">
                    {ch.current}/{ch.target}
                  </span>
                </div>
                <div className="h-2 rounded-full bg-[hsl(var(--muted))] overflow-hidden">
                  <div
                    className={`h-full rounded-full ${ch.completed ? 'bg-[hsl(var(--ok))]' : 'bg-[hsl(var(--lamp))]'}`}
                    style={{ width: `${ch.progress_percent}%` }}
                  />
                </div>
              </div>
            );
          })}
        </div>
      </div>

      {/* ---------------- الأوسمة ---------------- */}
      <div className="card p-5">
        <div className="flex flex-wrap items-baseline justify-between gap-2 mb-4">
          <h3 className="text-base font-bold">الأوسمة</h3>
          <p className="text-xs text-[hsl(var(--ink-3))]">
            {earned.length} من {perf.badges.length}
          </p>
        </div>
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-5 gap-3">
          {perf.badges.map(b => {
            const Icon = ICONS[b.icon] || Award;
            return (
              <div
                key={b.code}
                className={`p-3 rounded-[var(--radius-sm)] border text-center ${
                  b.earned
                    ? 'border-[hsl(var(--lamp-line))] bg-[hsl(var(--lamp-wash))]'
                    : 'border-[hsl(var(--line))] opacity-60'
                }`}
              >
                <Icon className={`w-6 h-6 mx-auto mb-1.5 ${b.earned ? 'text-[hsl(var(--lamp-strong))]' : 'text-[hsl(var(--ink-3))]'}`} />
                <p className="text-xs font-bold leading-tight">{b.label_ar}</p>
                <p className="text-[10px] text-[hsl(var(--ink-3))] mt-1 leading-snug">{b.desc_ar}</p>
              </div>
            );
          })}
        </div>
      </div>
    </div>
    </>
  );
}
