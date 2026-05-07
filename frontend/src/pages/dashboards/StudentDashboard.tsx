import React, { useEffect, useState, useCallback } from 'react';
import { BookOpen, Calendar, TrendingUp, Trophy, CheckCircle2, Star, FileText } from 'lucide-react';

import { useAuth } from '@/contexts/AuthContext';
import api from '@/services/api';

interface StudentInfo {
  id: string;
  name: string;
  progress: number;
  current_surah?: string;
  current_ayah?: number;
  halaqah_name?: string;
  student_type: string;
}

interface RecitationData {
  id: string;
  surah_name: string;
  start_ayah: number;
  end_ayah: number;
  evaluation: string;
  mistakes_count: number;
  date: string;
}

const evalMap: Record<string, { text: string; cls: string }> = {
  excellent:         { text: 'ممتاز',       cls: 'bg-emerald-100 text-emerald-700' },
  good:              { text: 'جيد',         cls: 'bg-blue-100 text-blue-700'       },
  acceptable:        { text: 'مقبول',       cls: 'bg-amber-100 text-amber-700'     },
  needs_improvement: { text: 'تحسين',       cls: 'bg-red-100 text-red-700'         },
};

export default function StudentDashboard() {
  const { user } = useAuth();
  const [studentInfo, setStudentInfo]     = useState<StudentInfo | null>(null);
  const [recitations, setRecitations]     = useState<RecitationData[]>([]);
  const [attendedDays, setAttendedDays]   = useState(0);
  const [totalAttDays, setTotalAttDays]   = useState(0);
  const [loading, setLoading]             = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const studentsResp = await api.get('/students');
      const allStudents: any[] = studentsResp.data || [];

      // Find my student record (match by user name)
      const me = allStudents.find((s: any) =>
        s.name === user?.name || s.user_id === user?.id
      ) || allStudents[0] || null;

      if (me) {
        setStudentInfo(me as StudentInfo);

        // Recitations
        const rResp = await api.get(`/recitations/student/${me.id}`).catch(() => ({ data: [] }));
        setRecitations((rResp.data || []) as RecitationData[]);

        // Attendance
        const aResp = await api.get(`/attendance/student/${me.id}`).catch(() => ({ data: [] }));
        const attRecords: any[] = aResp.data || [];
        const attended = attRecords.filter((a: any) => a.status === 'present').length;
        setAttendedDays(attended);
        setTotalAttDays(attRecords.length || attended);
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [user]);

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

  const progress = studentInfo?.progress || 0;
  const memorizedJuz = Math.round(progress / 100 * 30);
  const attRate = totalAttDays > 0 ? Math.round(attendedDays / totalAttDays * 100) : 0;

  // Achievements based on real data
  const achievements = [
    { title: `حفظت ${memorizedJuz} جزءاً`, icon: Trophy, unlocked: memorizedJuz > 0 },
    { title: `${recitations.length} تسميع مسجَّل`, icon: FileText, unlocked: recitations.length >= 5 },
    { title: 'نسبة حضور ممتازة', icon: Calendar, unlocked: attRate >= 80 },
    {
      title: 'تسميع ممتاز',
      icon: Star,
      unlocked: recitations.some(r => r.evaluation === 'excellent'),
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Hero */}
      <div className="relative overflow-hidden rounded-3xl p-7 text-white shadow-xl gradient-primary">
        <div className="absolute top-[-40px] left-[-40px] w-52 h-52 rounded-full bg-white/5" />
        <div className="absolute bottom-[-30px] right-20 w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <p className="text-white/60 text-sm mb-1">مرحباً،</p>
            <h1 className="text-3xl font-black mb-2">{studentInfo?.name || user?.name}</h1>
            {studentInfo?.current_surah && (
              <div className="inline-flex items-center gap-2 bg-white/20 rounded-xl px-4 py-2 text-sm font-semibold">
                <BookOpen className="w-4 h-4" />
                <span>{studentInfo.current_surah} · آية {studentInfo.current_ayah}</span>
              </div>
            )}
            {studentInfo?.halaqah_name && (
              <p className="text-white/60 text-sm mt-2">{studentInfo.halaqah_name}</p>
            )}
          </div>
          <div className="hidden md:flex flex-col items-center justify-center w-24 h-24 bg-white/15 rounded-2xl animate-float">
            <span className="text-4xl font-black">{progress}%</span>
            <span className="text-white/70 text-xs">مكتمل</span>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'أجزاء محفوظة', value: memorizedJuz, sub: 'من 30',  icon: BookOpen,   cls: 'gradient-primary' },
          { label: 'نسبة الحفظ',   value: `${progress}%`, sub: '',      icon: TrendingUp, cls: 'gradient-gold' },
          { label: 'أيام الحضور',  value: attendedDays, sub: `من ${totalAttDays}`, icon: Calendar, cls: 'bg-[hsl(222,42%,28%)]' },
        ].map(s => (
          <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center mb-3">
              <s.icon className="w-5 h-5 text-white" />
            </div>
            <p className="text-2xl font-black">{s.value}</p>
            {s.sub && <p className="text-white/60 text-xs">{s.sub}</p>}
            <p className="text-white/80 text-sm font-medium mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Progress map */}
      <div className="bg-white rounded-3xl p-6 shadow-sm border border-[hsl(var(--border))]">
        <div className="flex items-center justify-between mb-4">
          <h3 className="font-black text-[hsl(var(--foreground))]">تقدم الحفظ</h3>
          <span className="text-sm font-bold text-[hsl(var(--primary))]">{memorizedJuz} / 30 جزءاً</span>
        </div>
        <div className="h-4 bg-[hsl(var(--muted))] rounded-full overflow-hidden mb-5">
          <div className="h-full gradient-primary rounded-full transition-all duration-700" style={{ width: `${progress}%` }} />
        </div>
        <div className="grid grid-cols-10 gap-1.5">
          {[...Array(30)].map((_, i) => (
            <div key={i} title={`جزء ${i + 1}`}
              className={`aspect-square rounded-lg text-[10px] flex items-center justify-center font-bold
                ${i < memorizedJuz ? 'gradient-primary text-white shadow-sm'
                : i === memorizedJuz ? 'gradient-gold text-white shadow-sm animate-pulse-soft'
                : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]'}`}>
              {i + 1}
            </div>
          ))}
        </div>
        <div className="flex gap-5 mt-4 text-xs text-[hsl(var(--muted-foreground))]">
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded gradient-primary inline-block" />محفوظ</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded gradient-gold inline-block" />قيد الحفظ</span>
          <span className="flex items-center gap-1.5"><span className="w-3 h-3 rounded bg-[hsl(var(--muted))] inline-block" />لم يُحفظ</span>
        </div>
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Recent Recitations */}
        <div className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[hsl(var(--primary))]" />
            <h3 className="font-black text-[hsl(var(--foreground))]">التسميعات الأخيرة</h3>
          </div>
          <div className="divide-y divide-[hsl(var(--border))]">
            {recitations.length === 0 ? (
              <div className="py-10 text-center text-[hsl(var(--muted-foreground))]">
                <BookOpen className="w-10 h-10 mx-auto mb-2 opacity-30" />
                <p className="text-sm">لا توجد تسميعات مسجَّلة</p>
              </div>
            ) : recitations.slice(0, 5).map((r, i) => (
              <div key={r.id || i} className="flex items-center gap-4 px-5 py-4">
                <div className="text-center w-14 shrink-0">
                  <p className="text-xs text-[hsl(var(--muted-foreground))] font-medium">
                    {new Date(r.date).toLocaleDateString('ar-SA', { day: 'numeric', month: 'short' })}
                  </p>
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-[hsl(var(--foreground))] text-sm truncate">{r.surah_name}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">آية {r.start_ayah} - {r.end_ayah}</p>
                </div>
                <div className="text-left shrink-0">
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-lg ${evalMap[r.evaluation]?.cls}`}>
                    {evalMap[r.evaluation]?.text}
                  </span>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    {r.mistakes_count === 0 ? '🎉 لا أخطاء' : `${r.mistakes_count} أخطاء`}
                  </p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Achievements */}
        <div className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center gap-2">
            <Trophy className="w-5 h-5 text-[hsl(var(--gold))]" />
            <h3 className="font-black text-[hsl(var(--foreground))]">الإنجازات</h3>
          </div>
          <div className="p-5 space-y-3">
            {achievements.map((a, i) => (
              <div key={i} className={`flex items-center gap-4 p-4 rounded-2xl border-2 transition-all ${a.unlocked ? 'border-amber-200 bg-amber-50' : 'border-[hsl(var(--border))] opacity-50'}`}>
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center shadow-sm ${a.unlocked ? 'gradient-gold' : 'bg-[hsl(var(--muted))]'}`}>
                  <a.icon className="w-6 h-6 text-white" />
                </div>
                <div className="flex-1">
                  <p className="font-bold text-[hsl(var(--foreground))] text-sm">{a.title}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
                    {a.unlocked ? '✅ تم الإنجاز' : '🔒 لم تُفتح بعد'}
                  </p>
                </div>
                {a.unlocked && <CheckCircle2 className="w-5 h-5 text-emerald-500 shrink-0" />}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
