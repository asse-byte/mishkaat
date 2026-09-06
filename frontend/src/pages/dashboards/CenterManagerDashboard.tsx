import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  Users, GraduationCap, BookOpen,
  Calendar, ChevronLeft, FileText, RefreshCw,
  AlertCircle, Award, Plus,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '@/services/api';
import type { Recitation, Attendance, Fee } from '@/types';
import EmptyState from '@/components/ui/EmptyState';
import { formatAmount } from '@/lib/format';

interface Stats {
  students: number;
  teachers: number;
  halaqat: number;
  present_today: number;
  absent_today: number;
  recitations_this_week: number;
  fees_collected: number;
  fees_pending: number;
}

interface HonorRollStudent {
  id: string;
  name: string;
  halaqah_name: string;
  score: number;
}

// [توحيد 2026-09-06] كان fr-FR يُخرج مسافة رفيعة لا فاصلة، فيختلف عن بقيّة الشاشات
const FCFA = (n: number) => formatAmount(Math.round(n));

const EVAL_LABEL: Record<string, string> = {
  excellent: 'ممتاز', good: 'جيد', acceptable: 'مقبول', needs_improvement: 'يحتاج تحسين',
};

/* عنوان قسم موحّد — كان كل قسم يبني رأسه بنفسه بأوزان وألوان مختلفة */
function SectionHead({ title, to, action }: { title: string; to?: string; action?: string }) {
  return (
    <div className="flex items-baseline justify-between mb-4 gap-3">
      <h3 className="text-base font-bold text-[hsl(var(--ink))]">{title}</h3>
      {to && (
        <Link
          to={to}
          className="text-xs font-semibold text-[hsl(var(--ink-3))] hover:text-[hsl(var(--lamp-strong))] flex items-center gap-0.5 shrink-0 transition-colors"
        >
          {action || 'عرض الكل'}
          <ChevronLeft className="w-3.5 h-3.5" />
        </Link>
      )}
    </div>
  );
}

/* رقم واحد — الشريط الملوّن على الحافّة يأتي من فئة stat-card-* في نظام التصميم */
function Metric({ label, value, icon: Icon, tone, to }: {
  label: string; value: number | string; icon: React.ElementType; tone: string; to: string;
}) {
  return (
    <Link to={to} className={`${tone} block p-4 hoverable-card`}>
      <div className="flex items-start justify-between gap-2 mb-2">
        <span className="eyebrow">{label}</span>
        <Icon className="w-4 h-4 text-[hsl(var(--ink-3))] shrink-0" strokeWidth={1.75} />
      </div>
      <p className="num-display text-3xl text-[hsl(var(--ink))]">{value}</p>
    </Link>
  );
}

export default function CenterManagerDashboard() {
  const { user } = useAuth();
  const [stats, setStats]     = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentRecitations, setRecentRecitations] = useState<Recitation[]>([]);
  const [honorRoll, setHonorRoll] = useState<HonorRollStudent[]>([]);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [statsResp, recitationsResp, feesResp, attendanceResp, honorRollResp] = await Promise.all([
        api.get('/dashboard/stats'),
        api.get('/recitations?limit=5'),
        api.get('/fees'),
        api.get('/attendance/center?limit=10'),
        api.get('/dashboard/honor-roll').catch(() => ({ data: [] }))
      ]);

      const rawStats = statsResp.data;
      const fees: Fee[] = feesResp.data || [];
      const attendance: Attendance[] = attendanceResp.data || [];
      const honorRollData: HonorRollStudent[] = honorRollResp.data || [];

      const today = new Date().toISOString().slice(0, 10);
      const todayAtt = attendance.filter((a) => a.date?.slice(0, 10) === today);
      const presentToday = todayAtt.filter((a) => a.status === 'present').length;
      const absentToday  = todayAtt.filter((a) => a.status === 'absent').length;

      const weekAgo = new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString();
      const recitations: Recitation[] = recitationsResp.data || [];
      const weekRecitations = recitations.filter((r) => r.date >= weekAgo).length;

      setStats({
        students: rawStats.total_students || 0,
        teachers: rawStats.total_teachers || 0,
        halaqat:  rawStats.total_halaqat || 0,
        present_today: presentToday,
        absent_today: absentToday,
        recitations_this_week: weekRecitations,
        fees_collected: fees.filter((f) => f.status === 'paid').reduce((s: number, f) => s + f.amount, 0),
        fees_pending: fees.filter((f) => f.status === 'pending').reduce((s: number, f) => s + f.amount, 0),
      });

      setRecentRecitations(recitations.slice(0, 5));
      setHonorRoll(honorRollData);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="space-y-4 pb-10">
      <div className="skeleton h-8 w-64" />
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
        {[0, 1, 2, 3].map(i => <div key={i} className="skeleton h-24" />)}
      </div>
      <div className="skeleton h-56" />
    </div>
  );

  const marked = stats ? stats.present_today + stats.absent_today : 0;
  const attendanceRate = marked > 0 ? Math.round((stats!.present_today / marked) * 100) : null;

  /* سجل الشرف لا يُعرض ما لم تتباين الدرجات فعلاً.
     المعادلة ترجع 80/80/100 افتراضياً لمن لا بيانات له، فيظهر الطلاب جميعاً بالدرجة
     نفسها مرتَّبين بميداليات ذهب وفضة — ترتيب لا يقوم على شيء. */
  const scores = honorRoll.map(s => s.score);
  const hasSignal = scores.length > 1 && Math.max(...scores) - Math.min(...scores) >= 1;

  const today = new Date().toLocaleDateString('ar', {
    weekday: 'long', day: 'numeric', month: 'long', year: 'numeric',
  });

  return (
    <div className="space-y-5 page-fade-in pb-10">

      {/* ترويسة: سطر واحد. كانت لوحة سوداء ضخمة تكرّر الأرقام نفسها الظاهرة تحتها مباشرة */}
      <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
        <div>
          <h1 className="text-xl md:text-2xl">
            {user?.name ? `أهلاً، ${user.name.split(' - ')[0]}` : 'أهلاً بك'}
          </h1>
          <p className="text-sm text-[hsl(var(--ink-3))] mt-0.5">{today}</p>
        </div>
        <Link to="/attendance" className="btn-primary text-sm">
          <Calendar className="w-4 h-4" strokeWidth={2} />
          تسجيل حضور اليوم
        </Link>
      </header>

      {/* الأرقام الأربعة */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger">
          <Metric label="الطلاب"   value={stats.students} icon={Users}         tone="stat-card-teal"   to="/students" />
          <Metric label="المحفظون" value={stats.teachers} icon={GraduationCap} tone="stat-card-purple" to="/teachers" />
          <Metric label="الحلقات"  value={stats.halaqat}  icon={BookOpen}      tone="stat-card-blue"   to="/halaqat" />
          <Metric label="تسميع هذا الأسبوع" value={stats.recitations_this_week} icon={FileText} tone="stat-card-green" to="/recitations" />
        </div>
      )}

      {/* عمل اليوم — رُفع إلى الأعلى لأنه ما يفعله مدير المركز كل صباح */}
      <div className="grid lg:grid-cols-3 gap-4">

        <div className="card p-5 lg:col-span-2">
          <SectionHead title="حضور اليوم" to="/attendance" action="إدارة الحضور" />

          {marked === 0 ? (
            <div className="flex flex-wrap items-center justify-between gap-4 rounded-[var(--radius-sm)] bg-[hsl(var(--warn-wash))] border border-[hsl(var(--warn)/.25)] p-4">
              <div className="flex items-start gap-3">
                <AlertCircle className="w-5 h-5 text-[hsl(var(--warn))] shrink-0 mt-0.5" strokeWidth={2} />
                <div>
                  <p className="font-semibold text-[hsl(var(--ink))] text-sm">لم يُسجَّل حضور اليوم بعد</p>
                  <p className="text-xs text-[hsl(var(--ink-2))] mt-0.5">
                    {stats?.students ?? 0} طالباً في انتظار التسجيل
                  </p>
                </div>
              </div>
              <Link to="/attendance" className="btn-primary text-sm shrink-0">ابدأ التسجيل</Link>
            </div>
          ) : (
            <>
              <div className="flex items-end gap-6 mb-4">
                <div>
                  <p className="num-display text-4xl text-[hsl(var(--ink))]">{attendanceRate}%</p>
                  <p className="eyebrow mt-1">نسبة الحضور</p>
                </div>
                <div className="flex gap-5 pb-1">
                  <div>
                    <p className="num-display text-xl text-[hsl(var(--ok))]">{stats!.present_today}</p>
                    <p className="eyebrow">حاضر</p>
                  </div>
                  <div>
                    <p className="num-display text-xl text-[hsl(var(--danger))]">{stats!.absent_today}</p>
                    <p className="eyebrow">غائب</p>
                  </div>
                  <div>
                    <p className="num-display text-xl text-[hsl(var(--ink-3))]">{Math.max(0, (stats?.students ?? 0) - marked)}</p>
                    <p className="eyebrow">لم يُسجَّل</p>
                  </div>
                </div>
              </div>
              <div
                className="h-1.5 rounded-full bg-[hsl(var(--muted))] overflow-hidden"
                role="progressbar"
                aria-valuenow={attendanceRate ?? 0}
                aria-valuemin={0}
                aria-valuemax={100}
                aria-label="نسبة الحضور"
              >
                <div className="h-full bg-[hsl(var(--ok))] rounded-full transition-all duration-500"
                     style={{ width: `${attendanceRate}%` }} />
              </div>
            </>
          )}
        </div>

        {/* المالية */}
        {stats && (
          <div className="card p-5">
            <SectionHead title="المالية" to="/finance" />
            <div className="space-y-4">
              <div>
                <p className="eyebrow">محصَّلة</p>
                <p className="num-display text-2xl text-[hsl(var(--ok))] amount mt-0.5" dir="ltr">
                  {FCFA(stats.fees_collected)}
                </p>
              </div>
              <div className="border-t border-[hsl(var(--line-2))] pt-4">
                <p className="eyebrow">معلّقة</p>
                <p className="num-display text-2xl text-[hsl(var(--ink-2))] amount mt-0.5" dir="ltr">
                  {FCFA(stats.fees_pending)}
                </p>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* آخر التسميعات */}
      <div className="card p-5">
        <SectionHead title="آخر التسميعات" to="/recitations" />
        {recentRecitations.length === 0 ? (
          <div className="py-4">
            <EmptyState
              icon={FileText}
              title="لا توجد تسميعات مسجَّلة"
              description="لا توجد جلسات تسميع مسجلة اليوم."
            />
            <div className="flex justify-center mt-4">
              <Link to="/recitations" className="btn-outline-teal text-sm">
                <Plus className="w-4 h-4" strokeWidth={2} />
                سجّل أول تسميع
              </Link>
            </div>
          </div>
        ) : (
          <ul className="divide-y divide-[hsl(var(--line-2))] -mx-1">
            {recentRecitations.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-3 py-2.5 px-1">
                <div className="min-w-0">
                  <p className="font-semibold text-sm text-[hsl(var(--ink))] truncate">
                    {r.student_name || 'طالب'}
                  </p>
                  <p className="text-xs text-[hsl(var(--ink-3))] truncate">
                    {r.surah_name}
                    <span className="amount mx-1" dir="ltr">{r.start_ayah}–{r.end_ayah}</span>
                  </p>
                </div>
                <div className="flex items-center gap-2.5 shrink-0">
                  <span className={`text-[11px] px-2 py-0.5 rounded-full eval-${r.evaluation}`}>
                    {EVAL_LABEL[r.evaluation] ?? r.evaluation}
                  </span>
                  <time className="text-xs text-[hsl(var(--ink-3))] tabular-nums">
                    {new Date(r.date).toLocaleDateString('ar', { day: 'numeric', month: 'short' })}
                  </time>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* سجل الشرف — قائمة مرتَّبة هادئة، وتظهر فقط عند وجود تباين حقيقي */}
      {hasSignal && (
        <div className="card p-5">
          <SectionHead title="الأعلى أداءً هذا الشهر" to="/rankings" action="الترتيب الكامل" />
          <ol className="divide-y divide-[hsl(var(--line-2))] -mx-1">
            {honorRoll.slice(0, 5).map((s, idx) => (
              <li key={s.id} className="flex items-center gap-3 py-2.5 px-1">
                <span className={`num-display w-6 text-center text-sm shrink-0 ${
                  idx === 0 ? 'text-[hsl(var(--lamp-strong))]' : 'text-[hsl(var(--ink-3))]'
                }`}>
                  {idx + 1}
                </span>
                {idx === 0 && <Award className="w-4 h-4 text-[hsl(var(--lamp))] shrink-0" strokeWidth={2} />}
                <div className="min-w-0 flex-1">
                  <p className="font-semibold text-sm text-[hsl(var(--ink))] truncate">{s.name}</p>
                  <p className="text-xs text-[hsl(var(--ink-3))] truncate">{s.halaqah_name}</p>
                </div>
                <span className="num-display text-sm text-[hsl(var(--ink-2))] shrink-0">{s.score}%</span>
              </li>
            ))}
          </ol>
        </div>
      )}

      {/* إجراءات سريعة — أسلوب واحد. كانت ثلاثة أساليب توحي بترتيب أهمية غير موجود */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'تسجيل طالب',   icon: Users,          to: '/students' },
          { label: 'إضافة محفظ',   icon: GraduationCap,  to: '/teachers' },
          { label: 'إدارة الحضور', icon: Calendar,       to: '/attendance' },
          { label: 'خطط المراجعة', icon: RefreshCw,      to: '/review-plans' },
        ].map(link => (
          <Link
            key={link.label}
            to={link.to}
            className="card p-4 flex items-center gap-2.5 text-sm font-semibold text-[hsl(var(--ink))] hover:border-[hsl(var(--lamp))] transition-colors"
          >
            <link.icon className="w-4 h-4 text-[hsl(var(--lamp-strong))] shrink-0" strokeWidth={1.75} />
            <span className="truncate">{link.label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
