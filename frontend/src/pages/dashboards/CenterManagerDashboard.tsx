import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  Users, GraduationCap, BookOpen, TrendingUp,
  Calendar, DollarSign, ChevronRight, FileText, RefreshCw,
  CheckCircle2, AlertCircle, Clock, Award, Star, Medal
} from 'lucide-react';
import { Link } from 'react-router-dom';
import api from '@/services/api';
import type { Recitation, Attendance, Fee } from '@/types';

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

const FCFA = (n: number) => new Intl.NumberFormat('fr-FR').format(Math.round(n)) + ' FCFA';

export default function CenterManagerDashboard() {
  const { user } = useAuth();
  const [stats, setStats]     = useState<Stats | null>(null);
  const [loading, setLoading] = useState(true);
  const [recentRecitations, setRecentRecitations] = useState<Recitation[]>([]);
  const [recentAttendance, setRecentAttendance]   = useState<Attendance[]>([]);
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

      // Today's attendance stats
      const today = new Date().toISOString().slice(0, 10);
      const todayAtt = attendance.filter((a) => a.date?.slice(0, 10) === today);
      const presentToday = todayAtt.filter((a) => a.status === 'present').length;
      const absentToday  = todayAtt.filter((a) => a.status === 'absent').length;

      // Week recitations
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
      setRecentAttendance(attendance.slice(0, 8));
      setHonorRoll(honorRollData);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-16 h-16 gradient-primary rounded-2xl flex items-center justify-center mx-auto mb-4 animate-pulse-soft shadow-xl">
          <BookOpen className="w-8 h-8 text-white" />
        </div>
        <p className="text-[hsl(var(--muted-foreground))] font-medium">جاري التحميل...</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Welcome banner */}
      <div className="relative overflow-hidden rounded-3xl gradient-primary p-7 text-white shadow-xl">
        <div className="absolute top-[-50px] left-[-50px] w-56 h-56 rounded-full bg-white/5" />
        <div className="absolute bottom-[-30px] right-10 w-44 h-44 rounded-full bg-white/5" />
        <div className="relative z-10">
          <p className="text-white/60 font-medium mb-1 text-sm">مرحباً،</p>
          <h1 className="text-3xl font-black mb-1">{user?.name}</h1>
          <p className="text-white/70 text-sm">
            {new Date().toLocaleDateString('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
          </p>
          {/* Quick overview pills */}
          <div className="flex gap-3 mt-4 flex-wrap">
            {stats && [
              { label: `${stats.students} طالب`, cls: 'bg-white/15' },
              { label: `${stats.teachers} محفظ`, cls: 'bg-white/15' },
              { label: `${stats.halaqat} حلقة`, cls: 'bg-white/15' },
            ].map(p => (
              <span key={p.label} className={`text-sm font-bold px-3 py-1 rounded-full ${p.cls}`}>{p.label}</span>
            ))}
          </div>
        </div>
      </div>

      {/* Main stats grid */}
      {stats && (
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
          {[
            { icon: Users,             val: stats.students,  label: 'الطلاب',          cls: 'gradient-primary', to: '/students' },
            { icon: GraduationCap,     val: stats.teachers,  label: 'المحفظون',         cls: 'gradient-gold',    to: '/teachers' },
            { icon: BookOpen,          val: stats.halaqat,   label: 'الحلقات',          cls: 'bg-[hsl(222,42%,28%)]', to: '/halaqat' },
            { icon: FileText,          val: stats.recitations_this_week, label: 'تسميع هذا الأسبوع', cls: 'bg-[hsl(152,45%,38%)]', to: '/recitations' },
          ].map(s => (
            <Link key={s.label} to={s.to} className={`stat-card rounded-2xl p-5 text-white shadow-lg ${s.cls} hover:opacity-95`}>
              <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-3">
                <s.icon className="w-5 h-5 text-white" />
              </div>
              <p className="text-3xl font-black">{s.val}</p>
              <p className="text-white/75 text-sm mt-1">{s.label}</p>
              <div className="flex items-center gap-1 mt-2 text-white/60 text-xs">
                <ChevronRight className="w-3 h-3" /><span>عرض التفاصيل</span>
              </div>
            </Link>
          ))}
        </div>
      )}

      {/* Honor Roll */}
      {honorRoll.length > 0 && (
        <div className="bg-gradient-to-br from-amber-100 to-amber-50 rounded-3xl p-6 shadow-md border border-amber-200">
          <div className="flex items-center gap-3 mb-5">
            <div className="w-12 h-12 bg-amber-500 rounded-full flex items-center justify-center shadow-lg shadow-amber-200">
              <Award className="w-7 h-7 text-white" />
            </div>
            <div>
              <h3 className="font-black text-amber-900 text-xl">سجل الشرف الماسي</h3>
              <p className="text-amber-700 text-sm font-medium">أفضل الطلاب أداءً هذا الشهر بناءً على التقييم الذكي</p>
            </div>
          </div>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-5 gap-4">
            {honorRoll.map((student, idx) => (
              <div key={student.id} className="bg-white rounded-2xl p-4 text-center shadow-sm border border-amber-100 hover:-translate-y-1 transition-transform relative">
                {idx === 0 && <div className="absolute -top-3 -right-3 w-8 h-8 bg-yellow-400 rounded-full flex items-center justify-center shadow-md animate-bounce"><Star className="w-4 h-4 text-white fill-white" /></div>}
                {idx === 1 && <div className="absolute -top-3 -right-3 w-8 h-8 bg-slate-300 rounded-full flex items-center justify-center shadow-md"><Medal className="w-4 h-4 text-white fill-white" /></div>}
                {idx === 2 && <div className="absolute -top-3 -right-3 w-8 h-8 bg-orange-400 rounded-full flex items-center justify-center shadow-md"><Medal className="w-4 h-4 text-white fill-white" /></div>}
                
                <div className={`w-14 h-14 rounded-full flex items-center justify-center mx-auto mb-3 shadow-inner font-extrabold text-xl ${idx === 0 ? 'bg-gradient-to-tr from-amber-400 to-yellow-200 text-amber-900' : 'bg-slate-100 text-slate-600'}`}>
                  {idx + 1}
                </div>
                <h4 className="font-bold text-slate-800 text-sm mb-1 truncate" title={student.name}>{student.name}</h4>
                <p className="text-xs text-amber-600 font-bold mb-3 truncate">{student.halaqah_name}</p>
                <div className="bg-slate-50 rounded-lg p-2 flex justify-between items-center text-xs">
                  <span className="text-slate-500 font-medium">التقييم</span>
                  <span className="font-black text-emerald-600">{student.score}%</span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Attendance & Finance row */}
      <div className="grid md:grid-cols-2 gap-4">
        {/* Today's attendance */}
        {stats && (
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2">
                <Calendar className="w-4 h-4 text-[hsl(var(--primary))]" /> حضور اليوم
              </h3>
              <Link to="/attendance" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
                عرض الكل <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="grid grid-cols-3 gap-3 text-center">
              <div className="p-3 rounded-2xl bg-emerald-50">
                <CheckCircle2 className="w-5 h-5 mx-auto mb-1 text-emerald-600" />
                <p className="text-2xl font-black text-emerald-700">{stats.present_today}</p>
                <p className="text-xs text-emerald-600 font-medium">حاضر</p>
              </div>
              <div className="p-3 rounded-2xl bg-red-50">
                <AlertCircle className="w-5 h-5 mx-auto mb-1 text-red-500" />
                <p className="text-2xl font-black text-red-600">{stats.absent_today}</p>
                <p className="text-xs text-red-500 font-medium">غائب</p>
              </div>
              <div className="p-3 rounded-2xl bg-[hsl(var(--muted))]">
                <Users className="w-5 h-5 mx-auto mb-1 text-[hsl(var(--muted-foreground))]" />
                <p className="text-2xl font-black text-[hsl(var(--foreground))]">{stats.students}</p>
                <p className="text-xs text-[hsl(var(--muted-foreground))] font-medium">إجمالي</p>
              </div>
            </div>
            {(stats.present_today + stats.absent_today) > 0 && (
              <div className="mt-4">
                <div className="flex justify-between text-xs mb-1.5">
                  <span className="text-[hsl(var(--muted-foreground))]">نسبة الحضور</span>
                  <span className="font-bold text-emerald-600">
                    {Math.round(stats.present_today / (stats.present_today + stats.absent_today) * 100)}%
                  </span>
                </div>
                <div className="h-2 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                  <div className="h-full bg-emerald-500 rounded-full transition-all"
                    style={{ width: `${Math.round(stats.present_today / (stats.present_today + stats.absent_today) * 100)}%` }} />
                </div>
              </div>
            )}
          </div>
        )}

        {/* Financial summary */}
        {stats && (
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <div className="flex items-center justify-between mb-4">
              <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2">
                <DollarSign className="w-4 h-4 text-[hsl(var(--gold))]" /> الملخص المالي
              </h3>
              <Link to="/finance" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
                عرض الكل <ChevronRight className="w-3 h-3" />
              </Link>
            </div>
            <div className="space-y-3">
              <div className="flex items-center justify-between p-3 rounded-2xl bg-emerald-50">
                <div className="flex items-center gap-2">
                  <TrendingUp className="w-4 h-4 text-emerald-600" />
                  <span className="text-sm font-semibold text-emerald-700">الرسوم المحصَّلة</span>
                </div>
                <span className="font-black text-emerald-700 text-sm" dir="ltr">{FCFA(stats.fees_collected)}</span>
              </div>
              <div className="flex items-center justify-between p-3 rounded-2xl bg-amber-50">
                <div className="flex items-center gap-2">
                  <Clock className="w-4 h-4 text-amber-600" />
                  <span className="text-sm font-semibold text-amber-700">الرسوم المعلقة</span>
                </div>
                <span className="font-black text-amber-700 text-sm" dir="ltr">{FCFA(stats.fees_pending)}</span>
              </div>
            </div>
          </div>
        )}
      </div>

      {/* Recent Recitations */}
      <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2">
            <FileText className="w-4 h-4 text-[hsl(var(--primary))]" /> آخر التسميعات
          </h3>
          <Link to="/recitations" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
            عرض الكل <ChevronRight className="w-3 h-3" />
          </Link>
        </div>
        {recentRecitations.length === 0 ? (
          <div className="text-center py-8 text-[hsl(var(--muted-foreground))]">
            <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
            <p className="text-sm">لا توجد تسميعات مسجَّلة</p>
          </div>
        ) : (
          <div className="space-y-2">
            {recentRecitations.map((r) => (
              <div key={r.id} className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))] text-sm">
                <div className="flex items-center gap-3">
                  <div className="w-9 h-9 gradient-primary rounded-xl flex items-center justify-center text-white font-black text-xs">
                    {(r.student_name || 'ط').charAt(0)}
                  </div>
                  <div>
                    <p className="font-semibold text-[hsl(var(--foreground))]">{r.student_name || 'طالب'}</p>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">{r.surah_name} ({r.start_ayah} - {r.end_ayah})</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full eval-${r.evaluation}`}>
                    {r.evaluation === 'excellent' ? 'ممتاز' : r.evaluation === 'good' ? 'جيد' : r.evaluation === 'acceptable' ? 'مقبول' : 'يحتاج تحسين'}
                  </span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">{new Date(r.date).toLocaleDateString('ar-SA')}</span>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Recent Attendance */}
      {recentAttendance.length > 0 && (
        <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2">
              <Calendar className="w-4 h-4 text-[hsl(var(--primary))]" /> آخر سجلات الحضور
            </h3>
            <Link to="/attendance" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
              إدارة الحضور <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="space-y-1.5">
            {recentAttendance.slice(0, 6).map((a, idx) => (
              <div key={a.id || idx} className="flex items-center justify-between px-3 py-2 rounded-xl bg-[hsl(var(--muted))] text-sm">
                <div className="flex items-center gap-2">
                  <div className={`w-7 h-7 rounded-lg flex items-center justify-center text-xs font-black ${
                    a.status === 'present' ? 'bg-emerald-100 text-emerald-700' :
                    a.status === 'absent'  ? 'bg-red-100 text-red-600' :
                    a.status === 'late'    ? 'bg-amber-100 text-amber-700' : 'bg-blue-100 text-blue-700'
                  }`}>
                    {a.status === 'present' ? '✓' : a.status === 'absent' ? '✗' : a.status === 'late' ? 'ت' : 'ع'}
                  </div>
                  <span className="font-medium text-[hsl(var(--foreground))]">{a.student_name || 'طالب'}</span>
                </div>
                <span className="text-xs text-[hsl(var(--muted-foreground))]">{new Date(a.date || Date.now()).toLocaleDateString('ar-SA')}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Quick links */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger">
        {[
          { label: 'إضافة محفظ',   icon: GraduationCap, to: '/teachers',     cls: 'bg-[hsl(var(--primary-light))] text-[hsl(var(--primary))]' },
          { label: 'تسجيل طالب',   icon: Users,          to: '/students',     cls: 'bg-amber-50 text-amber-700' },
          { label: 'إدارة الحضور', icon: Calendar,       to: '/attendance',   cls: 'bg-blue-50 text-blue-700' },
          { label: 'خطط المراجعة', icon: RefreshCw,      to: '/review-plans', cls: 'bg-purple-50 text-purple-700' },
        ].map(link => (
          <Link key={link.label} to={link.to}
            className={`rounded-2xl p-4 flex flex-col items-center gap-2 text-center font-bold text-sm hover:opacity-80 transition-all stat-card ${link.cls}`}>
            <link.icon className="w-6 h-6" />
            <span>{link.label}</span>
          </Link>
        ))}
      </div>
    </div>
  );
}
