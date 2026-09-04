import React, { useEffect, useState, useCallback } from 'react';
import { BookOpen, Calendar, TrendingUp, CheckCircle2, DollarSign, AlertCircle } from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/services/api';
import WelcomeHero from '@/components/ui/WelcomeHero';
import EmptyState from '@/components/ui/EmptyState';
import { useTranslation } from '@/lib/i18n';

interface ChildInfo {
  id: string;
  name: string;
  halaqah_name?: string;
  progress: number;
  student_type: string;
  current_surah?: string;
  current_ayah?: number;
  enrollment_date: string;
}

interface FeeInfo {
  id: string;
  amount: number;
  due_date: string;
  fee_type: string;
  status: string;
  student_name?: string;
}

interface RecentRec {
  surah_name: string;
  evaluation: string;
  date: string;
  student_name?: string;
}

const FCFA = (n: number) => new Intl.NumberFormat('fr-FR').format(Math.round(n)) + ' FCFA';

const evalMap: Record<string, string> = {
  excellent: 'ممتاز', good: 'جيد', acceptable: 'مقبول', needs_improvement: 'يحتاج تحسين',
};

export default function ParentDashboard() {
  const { user } = useAuth();
  const { t } = useTranslation();
  const [children, setChildren]       = useState<ChildInfo[]>([]);
  const [fees, setFees]               = useState<FeeInfo[]>([]);
  const [recentRecs, setRecentRecs]   = useState<RecentRec[]>([]);
  const [attendanceMap, setAttendanceMap] = useState<Record<string, number>>({});
  const [loading, setLoading]         = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      // Load all students
      const studentsResp = await api.get('/students');
      const allStudents: any[] = studentsResp.data || [];

      // Filter children: match parent_name by user name, or all if no match
      const myChildren = allStudents.filter(
        (s: any) => s.parent_name === user?.name || s.parent_phone === user?.phone
      );
      const childList = myChildren.length > 0 ? myChildren : allStudents.slice(0, 3);
      setChildren(childList as ChildInfo[]);

      // Load fees
      const feesResp = await api.get('/fees').catch(() => ({ data: [] }));
      const allFees: any[] = feesResp.data || [];

      // Filter fees for my children
      const childIds = childList.map((c: any) => c.id);
      const myFees = allFees.filter((f: any) => childIds.includes(f.student_id));
      setFees(myFees as FeeInfo[]);

      // Load recitations for each child
      const allRecs: RecentRec[] = [];
      for (const child of childList.slice(0, 2)) {
        try {
          const rResp = await api.get(`/recitations/student/${child.id}`);
          const recs: any[] = (rResp.data || []).slice(0, 3);
          allRecs.push(...recs.map((r: any) => ({ ...r, student_name: child.name })));
        } catch { /* silent */ }
      }
      allRecs.sort((a: any, b: any) => (b.date || '').localeCompare(a.date || ''));
      setRecentRecs(allRecs.slice(0, 5));

      // Attendance for each child
      const attMap: Record<string, number> = {};
      for (const child of childList) {
        try {
          const aResp = await api.get(`/attendance/student/${child.id}`);
          const recs: any[] = aResp.data || [];
          const total = recs.length;
          const present = recs.filter((a: any) => a.status === 'present').length;
          attMap[child.id] = total > 0 ? Math.round(present / total * 100) : 0;
        } catch { attMap[child.id] = 0; }
      }
      setAttendanceMap(attMap);

    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [user]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-16 h-16 gradient-primary rounded-[var(--radius)] flex items-center justify-center mx-auto mb-4 animate-pulse-soft shadow-xl">
          <BookOpen className="w-8 h-8 text-white" />
        </div>
        <p className="text-[hsl(var(--muted-foreground))] font-medium">جاري التحميل...</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 page-fade-in pb-10">

      {/* Hero */}
      <WelcomeHero
        name={user?.name || null}
        roleTitle={t('role_parent')}
        subtext={`تابع تقدم ${children.length > 1 ? 'أبنائك' : 'ابنك'} في حفظ القرآن الكريم اليوم.`}
      />

      {/* Children cards */}
      <div>
        <h3 className="text-lg font-bold text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
          <span>أبنائي</span>
          <span className="badge-gold text-xs px-2.5 py-1 rounded-full">{children.length}</span>
        </h3>
        {children.length === 0 ? (
          <EmptyState
            icon={BookOpen}
            title="لا يوجد أبناء مسجلين"
            description="لم يتم ربط حساب بأبنائك بعد في مركز تحفيظ القرآن الكريم."
          />
        ) : (
          <div className="grid md:grid-cols-2 gap-5 stagger">
            {children.map(child => (
              <div key={child.id} className="bg-white rounded-[var(--radius-lg)] shadow-sm border border-[hsl(var(--border))] overflow-hidden stat-card hoverable-card">
                {/* card header */}
                <div className="gradient-primary p-5">
                  <div className="flex items-center gap-4">
                    <div className="w-16 h-16 rounded-[var(--radius)] bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))] flex items-center justify-center text-3xl font-bold text-[hsl(var(--lamp-strong))]">
                      {child.name.charAt(0)}
                    </div>
                    <div>
                      <h4 className="text-xl font-bold text-white">{child.name}</h4>
                      <p className="text-sm text-[hsl(var(--ink-3))]">
                        {child.halaqah_name || 'لم تُحدَّد الحلقة'} · 
                        {child.student_type === 'reviewing' ? ' مراجعة' : ' حفظ'}
                      </p>
                    </div>
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 divide-x divide-x-reverse divide-[hsl(var(--border))] border-b border-[hsl(var(--border))]">
                  {[
                    { icon: TrendingUp, val: `${child.progress}%`, label: 'الحفظ' },
                    { icon: Calendar,   val: `${attendanceMap[child.id] ?? 0}%`, label: 'الحضور' },
                    { icon: BookOpen,   val: child.current_surah ? child.current_surah.slice(0, 6) : '—', label: 'الموقع' },
                  ].map(s => (
                    <div key={s.label} className="p-4 text-center">
                      <s.icon className="w-4 h-4 mx-auto mb-1 text-[hsl(var(--primary))]" />
                      <p className="font-bold text-[hsl(var(--foreground))] text-base amount">{s.val}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">{s.label}</p>
                    </div>
                  ))}
                </div>

                {/* Progress bar */}
                <div className="p-4">
                  <div className="flex justify-between text-xs text-[hsl(var(--muted-foreground))] mb-2">
                    <span>تقدم الحفظ</span>
                    <span className="font-bold text-[hsl(var(--primary))]">{child.progress}%</span>
                  </div>
                  <div className="h-2.5 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                    <div className="h-full gradient-primary rounded-full" style={{ width: `${child.progress}%` }} />
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="grid lg:grid-cols-2 gap-5">
        {/* Recent Recitations */}
        <div className="bg-white rounded-[var(--radius-lg)] shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center gap-2">
            <BookOpen className="w-5 h-5 text-[hsl(var(--primary))]" />
            <h3 className="font-bold text-[hsl(var(--foreground))]">آخر التسميعات</h3>
          </div>
          <div className="divide-y divide-[hsl(var(--border))]">
            {recentRecs.length === 0 ? (
              <div className="p-6">
                <EmptyState
                  icon={BookOpen}
                  title="لا توجد تسميعات مسجَّلة"
                  description={t('empty_no_recitations')}
                />
              </div>
            ) : recentRecs.map((r, i) => (
              <div key={i} className="flex items-center gap-4 px-5 py-4 hover:bg-slate-50 dark:hover:bg-slate-800/40 transition-colors">
                <div className="w-9 h-9 gradient-primary rounded-xl flex items-center justify-center text-white font-bold text-sm shrink-0">
                  {(r.student_name || 'ط').charAt(0)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="font-semibold text-sm text-[hsl(var(--foreground))] truncate">
                    {r.student_name} · {(r as any).surah_name}
                  </p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">
                    {new Date(r.date).toLocaleDateString('ar-SA')}
                  </p>
                </div>
                <span className={`text-xs font-bold px-2 py-0.5 rounded-full shrink-0 ${
                  r.evaluation === 'excellent' ? 'bg-emerald-100 text-emerald-700'
                  : r.evaluation === 'good' ? 'bg-blue-100 text-blue-700'
                  : 'bg-amber-100 text-amber-700'}`}>
                  {evalMap[r.evaluation] || r.evaluation}
                </span>
              </div>
            ))}
          </div>
        </div>

        {/* Fees */}
        <div className="bg-white rounded-[var(--radius-lg)] shadow-sm border border-[hsl(var(--border))] overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-[hsl(var(--gold))]" />
            <h3 className="font-bold text-[hsl(var(--foreground))]">حالة المدفوعات</h3>
          </div>
          <div className="p-5 space-y-3">
            {fees.length === 0 ? (
              <EmptyState
                icon={DollarSign}
                title="لا توجد مدفوعات مسجَّلة"
                description="لا توجد رسوم دراسية معلقة أو مسجلة لهذا الحساب حالياً."
              />
            ) : fees.map(fee => (
              <div key={fee.id} className="flex items-center justify-between p-4 rounded-[var(--radius)] bg-[hsl(var(--muted))] hover:bg-[hsl(var(--border))] transition-colors">
                <div className="flex items-center gap-3">
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center ${
                    fee.status === 'paid' ? 'bg-emerald-100' : 'bg-amber-100'}`}>
                    {fee.status === 'paid'
                      ? <CheckCircle2 className="w-5 h-5 text-emerald-600" />
                      : <AlertCircle className="w-5 h-5 text-amber-600" />}
                  </div>
                  <div>
                    <p className="font-bold text-[hsl(var(--foreground))] text-sm">{fee.student_name}</p>
                    <p className="text-xs text-[hsl(var(--muted-foreground))]">
                      {fee.fee_type === 'monthly' ? 'شهري' : fee.fee_type === 'annual' ? 'سنوي' : 'تسجيل'}
                      {fee.due_date && ` · ${fee.due_date}`}
                    </p>
                  </div>
                </div>
                <div className="text-left">
                  <p className="font-bold text-[hsl(var(--foreground))] text-sm amount" dir="ltr">{FCFA(fee.amount)}</p>
                  <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                    fee.status === 'paid' ? 'bg-emerald-100 text-emerald-700' : 'bg-amber-100 text-amber-700'}`}>
                    {fee.status === 'paid' ? '✅ مدفوع' : '⏳ معلق'}
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
