import React, { useEffect, useState, useCallback } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Users, BookOpen, Calendar, Clock,
  CheckCircle2, Star, FileText, TrendingUp,
  ChevronRight, Award, GraduationCap,
} from 'lucide-react';
import api from '@/services/api';

interface TeacherStats {
  students_count: number;
  halaqat: string[];
  recitations_today: number;
  attendance_rate: number;
  teacher_name: string | null;
}

interface RecitationData {
  id: string;
  student_name: string;
  surah_name: string;
  start_ayah: number;
  end_ayah: number;
  evaluation: string;
  date: string;
}

interface StudentData {
  id: string;
  name: string;
  progress: number;
  halaqah_name?: string;
}

const evalLabel: Record<string, { text: string; cls: string }> = {
  excellent:        { text: 'ممتاز', cls: 'bg-emerald-100 text-emerald-700' },
  good:             { text: 'جيد', cls: 'bg-blue-100 text-blue-700' },
  acceptable:       { text: 'مقبول', cls: 'bg-amber-100 text-amber-700' },
  needs_improvement:{ text: 'يحتاج تحسين', cls: 'bg-red-100 text-red-700' },
};

export default function TeacherDashboard() {
  const { user } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats]             = useState<TeacherStats | null>(null);
  const [recentRecitations, setRecent] = useState<RecitationData[]>([]);
  const [topStudents, setTopStudents] = useState<StudentData[]>([]);
  const [loading, setLoading]         = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [teachersResp, studentsResp, recitationsResp] = await Promise.all([
        api.get('/teachers'),
        api.get('/students'),
        api.get('/recitations?limit=10'),
      ]);

      const teachers: any[] = teachersResp.data || [];
      const students: any[] = studentsResp.data || [];
      const recitations: any[] = recitationsResp.data || [];

      // Find current teacher record
      const myTeacher = teachers.find((t: any) => t.user_id === user?.id) ||
                        teachers.find((t: any) => t.name === user?.name);

      const teacherStudentsCount = myTeacher ? myTeacher.students_count : students.length;

      // Attendance rate from last 30 days (all students)
      const attResp = await api.get('/attendance?limit=100').catch(() => ({ data: [] }));
      const attRecords: any[] = attResp.data || [];
      const presentCount = attRecords.filter((a: any) => a.status === 'present').length;
      const totalAtt = attRecords.length;
      const attendanceRate = totalAtt > 0 ? Math.round(presentCount / totalAtt * 100) : 0;

      // Today's recitations
      const today = new Date().toISOString().slice(0, 10);
      const todayRecitations = recitations.filter((r: any) => r.date?.slice(0, 10) === today);

      setStats({
        students_count: teacherStudentsCount,
        halaqat: myTeacher?.halaqat || [],
        recitations_today: todayRecitations.length,
        attendance_rate: attendanceRate,
        teacher_name: myTeacher?.name || user?.name || null,
      });

      // Top students by progress
      const sorted = [...students].sort((a: any, b: any) => (b.progress || 0) - (a.progress || 0));
      setTopStudents(sorted.slice(0, 5) as StudentData[]);

      // Recent recitations
      setRecent(recitations.slice(0, 6) as RecitationData[]);

    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [user]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-16 h-16 gradient-primary rounded-2xl flex items-center justify-center mx-auto mb-4 animate-pulse-soft shadow-xl">
          <GraduationCap className="w-8 h-8 text-white" />
        </div>
        <p className="text-[hsl(var(--muted-foreground))] font-medium">جاري التحميل...</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl p-7 text-white shadow-xl gradient-primary">
        <div className="absolute top-[-40px] left-[-40px] w-52 h-52 rounded-full bg-white/5" />
        <div className="absolute bottom-[-30px] right-20 w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <p className="text-white/60 text-sm mb-1">مرحباً،</p>
            <h1 className="text-3xl font-black mb-1">{stats?.teacher_name || user?.name}</h1>
            {stats?.halaqat && stats.halaqat.length > 0 && (
              <p className="text-white/70 text-sm">{stats.halaqat.join(' · ')}</p>
            )}
          </div>
          <div className="hidden md:flex w-20 h-20 bg-white/15 rounded-2xl items-center justify-center animate-float">
            <GraduationCap className="w-10 h-10 text-white" />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
        {[
          { title: 'طلابي',          value: stats?.students_count ?? '-',   icon: Users,       cls: 'gradient-primary' },
          { title: 'تسميعات اليوم',  value: stats?.recitations_today ?? 0,  icon: BookOpen,    cls: 'gradient-gold' },
          { title: 'نسبة الحضور',    value: `${stats?.attendance_rate ?? 0}%`, icon: Calendar, cls: 'bg-[hsl(222,42%,28%)]' },
          { title: 'الحلقات',         value: stats?.halaqat.length ?? 0,    icon: BookOpen,    cls: 'bg-[hsl(152,45%,38%)]' },
        ].map(s => (
          <div key={s.title} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-3">
              <s.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-3xl font-black">{s.value}</p>
            <p className="text-white/70 text-sm mt-1 font-medium">{s.title}</p>
          </div>
        ))}
      </div>

      <div className="grid lg:grid-cols-5 gap-5">
        {/* Recent Recitations */}
        <div className="lg:col-span-3 bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <FileText className="w-5 h-5 text-[hsl(var(--primary))]" />
              <h3 className="font-black text-[hsl(var(--foreground))]">آخر التسميعات</h3>
            </div>
            <Link to="/recitations" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
              عرض الكل <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="divide-y divide-[hsl(var(--border))]">
            {recentRecitations.length === 0 ? (
              <div className="py-10 text-center text-[hsl(var(--muted-foreground))]">
                <FileText className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">لا توجد تسميعات مسجَّلة</p>
              </div>
            ) : recentRecitations.map((r, i) => (
              <div key={r.id || i} className="flex items-center gap-4 px-5 py-3.5">
                <div className="w-9 h-9 gradient-primary rounded-xl flex items-center justify-center text-white font-black text-sm shrink-0">
                  {(r.student_name || 'ط').charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[hsl(var(--foreground))] text-sm truncate">{r.student_name || 'طالب'}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{r.surah_name} ({r.start_ayah}-{r.end_ayah})</p>
                </div>
                <div className="flex flex-col items-end gap-1 shrink-0">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${evalLabel[r.evaluation]?.cls}`}>
                    {evalLabel[r.evaluation]?.text || r.evaluation}
                  </span>
                  <span className="text-[10px] text-[hsl(var(--muted-foreground))]">
                    {new Date(r.date).toLocaleDateString('ar-SA')}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Top Students */}
        <div className="lg:col-span-2 bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Award className="w-5 h-5 text-[hsl(var(--gold))]" />
              <h3 className="font-black text-[hsl(var(--foreground))]">المتميزون</h3>
            </div>
            <Link to="/students" className="text-xs text-[hsl(var(--primary))] font-bold flex items-center gap-1 hover:underline">
              الكل <ChevronRight className="w-3 h-3" />
            </Link>
          </div>
          <div className="p-5 space-y-4">
            {topStudents.length === 0 ? (
              <p className="text-center text-[hsl(var(--muted-foreground))] text-sm py-6">لا يوجد طلاب</p>
            ) : topStudents.map((s, i) => (
              <div key={s.id} className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-xl flex items-center justify-center text-white font-black text-sm shrink-0 ${
                  i === 0 ? 'gradient-gold' : i === 1 ? 'bg-[hsl(var(--navy-mid))]' : 'gradient-primary'
                }`}>
                  {i + 1}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[hsl(var(--foreground))] text-sm truncate">{s.name}</p>
                  <div className="flex items-center gap-2 mt-1.5">
                    <div className="flex-1 h-1.5 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                      <div className="h-full gradient-primary rounded-full" style={{ width: `${s.progress || 0}%` }} />
                    </div>
                    <span className="text-xs text-[hsl(var(--muted-foreground))] w-9 shrink-0">{s.progress || 0}%</span>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Quick actions */}
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        {[
          { label: 'تسميع جديد',   icon: BookOpen,  href: '/recitations',   cls: 'gradient-primary' },
          { label: 'تسجيل حضور',   icon: Calendar,  href: '/attendance',    cls: 'gradient-gold' },
          { label: 'قائمة الطلاب', icon: Users,     href: '/students',      cls: 'bg-[hsl(222,42%,28%)]' },
          { label: 'خطط مراجعة',   icon: TrendingUp, href: '/review-plans', cls: 'bg-[hsl(152,45%,38%)]' },
        ].map(a => (
          <button key={a.href} onClick={() => navigate(a.href)}
            className={`${a.cls} rounded-2xl p-5 text-white text-center hover:opacity-90 active:scale-[0.97] transition-all shadow-md stat-card`}>
            <a.icon className="w-7 h-7 mx-auto mb-2" />
            <span className="text-sm font-bold">{a.label}</span>
          </button>
        ))}
      </div>
    </div>
  );
}
