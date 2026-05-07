import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  FileText, Printer, Users, 
  Calendar, DollarSign, BookOpen, 
  BarChart3,
} from 'lucide-react';
import api from '@/services/api';

const FCFA = (n: number) => new Intl.NumberFormat('fr-FR').format(Math.round(n)) + ' FCFA';

interface ReportData {
  center_name: string;
  generated_at: string;
  students: any[];
  teachers: any[];
  halaqat: any[];
  recitations: any[];
  attendance: any[];
  fees: any[];
}

const REPORT_TYPES = [
  { id: 'attendance',  label: 'تقرير الحضور والغياب',   icon: Calendar,     cls: 'gradient-primary' },
  { id: 'recitations', label: 'تقرير التسميع',           icon: BookOpen,     cls: 'gradient-gold' },
  { id: 'financial',   label: 'التقرير المالي',           icon: DollarSign,   cls: 'bg-[hsl(222,42%,28%)]' },
  { id: 'students',    label: 'تقرير الطلاب',            icon: Users,        cls: 'bg-[hsl(152,45%,38%)]' },
];

function PrintButton({ onClick }: { onClick: () => void }) {
  return (
    <button onClick={onClick}
      className="flex items-center gap-2 gradient-primary text-white font-bold px-5 py-2.5 rounded-xl hover:opacity-90 transition-all shadow-md text-sm">
      <Printer className="w-4 h-4" /> طباعة التقرير
    </button>
  );
}

export default function Reports() {
  const { user } = useAuth();
  const [activeReport, setActiveReport] = useState('attendance');
  const [data, setData]                 = useState<ReportData | null>(null);
  const [loading, setLoading]           = useState(true);
  const [filterHalaqah, setFilterHalaqah] = useState('');
  const [filterMonth, setFilterMonth]   = useState(new Date().toISOString().slice(0, 7));

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [stuResp, tchResp, halResp, recResp, attResp, feeResp] = await Promise.all([
        api.get('/students').catch(() => ({ data: [] })),
        api.get('/teachers').catch(() => ({ data: [] })),
        api.get('/halaqat').catch(() => ({ data: [] })),
        api.get('/recitations?limit=500').catch(() => ({ data: [] })),
        api.get('/attendance/center?limit=500').catch(() => ({ data: [] })),
        api.get('/fees').catch(() => ({ data: [] })),
      ]);
      setData({
        center_name: user?.name || 'المركز',
        generated_at: new Date().toLocaleString('ar-SA'),
        students:    stuResp.data || [],
        teachers:    tchResp.data || [],
        halaqat:     halResp.data || [],
        recitations: recResp.data || [],
        attendance:  attResp.data || [],
        fees:        feeResp.data || [],
      });
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [user]);

  useEffect(() => { loadData(); }, [loadData]);

  const handlePrint = () => {
    window.print();
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-16 h-16 gradient-primary rounded-2xl mx-auto mb-4 flex items-center justify-center animate-pulse-soft shadow-xl">
          <FileText className="w-8 h-8 text-white" />
        </div>
        <p className="text-[hsl(var(--muted-foreground))] font-medium">جاري تحميل بيانات التقارير...</p>
      </div>
    </div>
  );

  // ── Computed values ──────────────────────────────────────────
  const filteredAtt = data?.attendance.filter(a =>
    (!filterHalaqah || a.halaqah_id === filterHalaqah) &&
    (!filterMonth || a.date?.startsWith(filterMonth))
  ) || [];
  const filteredRec = data?.recitations.filter(r =>
    (!filterHalaqah || r.halaqah_id === filterHalaqah) &&
    (!filterMonth || r.date?.startsWith(filterMonth))
  ) || [];

  const attPresent = filteredAtt.filter(a => a.status === 'present').length;
  const attAbsent  = filteredAtt.filter(a => a.status === 'absent').length;
  const attRate    = filteredAtt.length > 0 ? Math.round(attPresent / filteredAtt.length * 100) : 0;

  const recExcellent = filteredRec.filter(r => r.evaluation === 'excellent').length;
  const recAvgMistakes = filteredRec.length > 0
    ? (filteredRec.reduce((s, r) => s + (r.mistakes_count || 0), 0) / filteredRec.length).toFixed(1) : '0';

  const feePaid    = (data?.fees || []).filter(f => f.status === 'paid');
  const feePending = (data?.fees || []).filter(f => f.status === 'pending');
  const totalPaid  = feePaid.reduce((s, f) => s + (f.amount || 0), 0);
  const totalPend  = feePending.reduce((s, f) => s + (f.amount || 0), 0);

  // Per-halaqah attendance summary
  const halaqahAttStats = (data?.halaqat || []).map(h => {
    const hAtt = filteredAtt.filter(a => a.halaqah_id === h.id);
    const hPres = hAtt.filter(a => a.status === 'present').length;
    return { ...h, total: hAtt.length, present: hPres, rate: hAtt.length > 0 ? Math.round(hPres / hAtt.length * 100) : 0 };
  });

  // Per-halaqah recitation summary
  const halaqahRecStats = (data?.halaqat || []).map(h => {
    const hRec = filteredRec.filter(r => r.halaqah_id === h.id);
    const hExc = hRec.filter(r => r.evaluation === 'excellent').length;
    return { ...h, total: hRec.length, excellent: hExc, rate: hRec.length > 0 ? Math.round(hExc / hRec.length * 100) : 0 };
  });

  return (
    <div className="space-y-6 animate-fade-in print:space-y-4">

      {/* Header — hidden when printing */}
      <div className="relative overflow-hidden rounded-3xl p-6 text-white shadow-xl gradient-primary print:hidden">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">إصدار التقارير</h1>
            <p className="text-white/70 text-sm">تقارير شاملة قابلة للطباعة والتصدير</p>
          </div>
          <PrintButton onClick={handlePrint} />
        </div>
      </div>

      {/* Report Type Selector */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 print:hidden">
        {REPORT_TYPES.map(rt => (
          <button key={rt.id} onClick={() => setActiveReport(rt.id)}
            className={`rounded-2xl p-4 flex flex-col items-center gap-2 text-center font-bold text-sm transition-all stat-card ${
              activeReport === rt.id
                ? `${rt.cls} text-white shadow-lg`
                : 'bg-white border border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))] hover:border-[hsl(var(--primary))]'}`}>
            <rt.icon className="w-6 h-6" />
            <span>{rt.label}</span>
          </button>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))] print:hidden">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className="block text-sm font-bold mb-1.5">الحلقة</label>
            <select value={filterHalaqah} onChange={e => setFilterHalaqah(e.target.value)} title="الحلقة" className="form-input">
              <option value="">كل الحلقات</option>
              {(data?.halaqat || []).map((h: any) => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-bold mb-1.5">الشهر</label>
            <input type="month" value={filterMonth} onChange={e => setFilterMonth(e.target.value)} className="form-input" dir="ltr" />
          </div>
        </div>
      </div>

      {/* ── PRINT HEADER (shown only when printing) ─────────── */}
      <div className="hidden print:block text-center border-b-2 border-gray-200 pb-4 mb-6">
        <h1 className="text-3xl font-black text-gray-900">مركز {data?.center_name} لتحفيظ القرآن الكريم</h1>
        <h2 className="text-xl font-bold text-gray-700 mt-1">
          {REPORT_TYPES.find(r => r.id === activeReport)?.label}
        </h2>
        <p className="text-sm text-gray-500 mt-1">تاريخ الإصدار: {data?.generated_at}</p>
        {filterMonth && <p className="text-sm text-gray-500">الفترة: {filterMonth}</p>}
      </div>

      {/* ── ATTENDANCE REPORT ─────────────────────────────── */}
      {activeReport === 'attendance' && (
        <div className="space-y-5">
          {/* KPI cards */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'إجمالي سجلات الحضور', val: filteredAtt.length, cls: 'gradient-primary' },
              { label: 'الحاضرون',             val: attPresent,         cls: 'bg-emerald-600' },
              { label: 'نسبة الحضور',          val: `${attRate}%`,      cls: attRate >= 80 ? 'bg-emerald-600' : attRate >= 60 ? 'gradient-gold' : 'bg-red-600' },
            ].map(s => (
              <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
                <p className="text-3xl font-black">{s.val}</p>
                <p className="text-white/80 text-sm mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Per-halaqah */}
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
              <BarChart3 className="w-5 h-5 text-[hsl(var(--primary))]" /> الحضور حسب الحلقة
            </h3>
            <table className="w-full text-sm text-right">
              <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                <tr>
                  <th className="px-4 py-3 rounded-r-xl font-bold">الحلقة</th>
                  <th className="px-4 py-3 font-bold">إجمالي السجلات</th>
                  <th className="px-4 py-3 font-bold">الحاضرون</th>
                  <th className="px-4 py-3 font-bold">الغائبون</th>
                  <th className="px-4 py-3 rounded-l-xl font-bold">نسبة الحضور</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {halaqahAttStats.map(h => (
                  <tr key={h.id} className="hover:bg-[hsl(var(--muted))]/30">
                    <td className="px-4 py-3 font-bold text-[hsl(var(--foreground))]">{h.name}</td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{h.total}</td>
                    <td className="px-4 py-3 text-emerald-600 font-bold">{h.present}</td>
                    <td className="px-4 py-3 text-red-600 font-bold">{h.total - h.present}</td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <div className="flex-1 h-2 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                          <div className={`h-full rounded-full ${h.rate >= 80 ? 'bg-emerald-500' : h.rate >= 60 ? 'bg-amber-500' : 'bg-red-500'}`} style={{ width: `${h.rate}%` }} />
                        </div>
                        <span className={`font-black text-xs ${h.rate >= 80 ? 'text-emerald-600' : h.rate >= 60 ? 'text-amber-600' : 'text-red-600'}`}>{h.rate}%</span>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Individual records */}
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4">سجل الحضور التفصيلي ({filteredAtt.length} سجل)</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-right">
                <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <tr>
                    <th className="px-4 py-3 font-bold rounded-r-xl">الطالب</th>
                    <th className="px-4 py-3 font-bold">الحلقة</th>
                    <th className="px-4 py-3 font-bold">التاريخ</th>
                    <th className="px-4 py-3 font-bold rounded-l-xl">الحالة</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]">
                  {filteredAtt.slice(0, 50).map((a: any, i: number) => (
                    <tr key={a.id || i} className="hover:bg-[hsl(var(--muted))]/20">
                      <td className="px-4 py-2.5 font-medium">{a.student_name || '—'}</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{a.halaqah_name || '—'}</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{new Date(a.date || Date.now()).toLocaleDateString('ar-SA')}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${a.status==='present'?'bg-emerald-100 text-emerald-700':a.status==='absent'?'bg-red-100 text-red-700':a.status==='late'?'bg-amber-100 text-amber-700':'bg-blue-100 text-blue-700'}`}>
                          {a.status==='present'?'حاضر':a.status==='absent'?'غائب':a.status==='late'?'متأخر':'معذور'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
              {filteredAtt.length > 50 && <p className="text-center text-xs text-[hsl(var(--muted-foreground))] mt-3">عرض أول 50 سجل من {filteredAtt.length}</p>}
            </div>
          </div>
        </div>
      )}

      {/* ── RECITATIONS REPORT ────────────────────────────── */}
      {activeReport === 'recitations' && (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'إجمالي التسميعات', val: filteredRec.length, cls: 'gradient-primary' },
              { label: 'تقييم ممتاز',      val: recExcellent,       cls: 'gradient-gold' },
              { label: 'متوسط الأخطاء',    val: recAvgMistakes,     cls: 'bg-[hsl(222,42%,28%)]' },
            ].map(s => (
              <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
                <p className="text-3xl font-black">{s.val}</p>
                <p className="text-white/80 text-sm mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          {/* Per-halaqah recitation */}
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
              <BookOpen className="w-5 h-5 text-[hsl(var(--primary))]" /> التسميع حسب الحلقة
            </h3>
            <table className="w-full text-sm text-right">
              <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                <tr>
                  <th className="px-4 py-3 font-bold rounded-r-xl">الحلقة</th>
                  <th className="px-4 py-3 font-bold">إجمالي التسميعات</th>
                  <th className="px-4 py-3 font-bold">ممتاز</th>
                  <th className="px-4 py-3 font-bold rounded-l-xl">نسبة الممتاز</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {halaqahRecStats.map(h => (
                  <tr key={h.id} className="hover:bg-[hsl(var(--muted))]/30">
                    <td className="px-4 py-3 font-bold">{h.name}</td>
                    <td className="px-4 py-3 text-[hsl(var(--muted-foreground))]">{h.total}</td>
                    <td className="px-4 py-3 text-emerald-600 font-bold">{h.excellent}</td>
                    <td className="px-4 py-3 font-black text-[hsl(var(--primary))]">{h.rate}%</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* All recitations */}
          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4">سجل التسميع التفصيلي</h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-right">
                <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <tr>
                    <th className="px-4 py-3 font-bold rounded-r-xl">الطالب</th>
                    <th className="px-4 py-3 font-bold">السورة</th>
                    <th className="px-4 py-3 font-bold">النوع</th>
                    <th className="px-4 py-3 font-bold">التقييم</th>
                    <th className="px-4 py-3 font-bold">الأخطاء</th>
                    <th className="px-4 py-3 font-bold rounded-l-xl">التاريخ</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]">
                  {filteredRec.slice(0, 50).map((r: any, i: number) => (
                    <tr key={r.id || i} className="hover:bg-[hsl(var(--muted))]/20">
                      <td className="px-4 py-2.5 font-medium">{r.student_name || '—'}</td>
                      <td className="px-4 py-2.5">{r.surah_name} ({r.start_ayah}–{r.end_ayah})</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{r.recitation_type === 'new' ? 'جديد' : 'مراجعة'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${r.evaluation==='excellent'?'bg-emerald-100 text-emerald-700':r.evaluation==='good'?'bg-blue-100 text-blue-700':r.evaluation==='acceptable'?'bg-amber-100 text-amber-700':'bg-red-100 text-red-700'}`}>
                          {r.evaluation==='excellent'?'ممتاز':r.evaluation==='good'?'جيد':r.evaluation==='acceptable'?'مقبول':'تحسين'}
                        </span>
                      </td>
                      <td className="px-4 py-2.5 text-center font-bold">{r.mistakes_count}</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{new Date(r.date).toLocaleDateString('ar-SA')}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── FINANCIAL REPORT ──────────────────────────────── */}
      {activeReport === 'financial' && (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'إجمالي المحصَّل',  val: FCFA(totalPaid), cls: 'gradient-primary' },
              { label: 'رسوم معلقة',       val: FCFA(totalPend), cls: 'gradient-gold' },
              { label: 'صافي الإيرادات',   val: FCFA(totalPaid - totalPend), cls: 'bg-[hsl(222,42%,28%)]' },
            ].map(s => (
              <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
                <p className="text-xl font-black" dir="ltr">{s.val}</p>
                <p className="text-white/80 text-sm mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
              <DollarSign className="w-5 h-5 text-[hsl(var(--gold))]" /> تفاصيل الرسوم
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-right">
                <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <tr>
                    <th className="px-4 py-3 font-bold rounded-r-xl">الطالب</th>
                    <th className="px-4 py-3 font-bold">المبلغ</th>
                    <th className="px-4 py-3 font-bold">الشهر</th>
                    <th className="px-4 py-3 font-bold rounded-l-xl">الحالة</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]">
                  {(data?.fees || []).map((f: any, i: number) => (
                    <tr key={f.id || i} className="hover:bg-[hsl(var(--muted))]/20">
                      <td className="px-4 py-2.5 font-medium">{f.student_name || '—'}</td>
                      <td className="px-4 py-2.5 font-bold" dir="ltr">{FCFA(f.amount || 0)}</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{f.month || f.due_date?.slice(0, 7) || '—'}</td>
                      <td className="px-4 py-2.5">
                        <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${f.status==='paid'?'bg-emerald-100 text-emerald-700':'bg-amber-100 text-amber-700'}`}>
                          {f.status==='paid' ? 'مدفوع' : 'معلق'}
                        </span>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ── STUDENTS REPORT ───────────────────────────────── */}
      {activeReport === 'students' && (
        <div className="space-y-5">
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: 'إجمالي الطلاب',    val: data?.students.length || 0, cls: 'gradient-primary' },
              { label: 'إجمالي المحفظين',  val: data?.teachers.length || 0, cls: 'gradient-gold' },
              { label: 'إجمالي الحلقات',   val: data?.halaqat.length || 0,  cls: 'bg-[hsl(222,42%,28%)]' },
            ].map(s => (
              <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
                <p className="text-3xl font-black">{s.val}</p>
                <p className="text-white/80 text-sm mt-1">{s.label}</p>
              </div>
            ))}
          </div>

          <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
            <h3 className="font-black text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
              <Users className="w-5 h-5 text-[hsl(var(--primary))]" /> قائمة الطلاب الكاملة
            </h3>
            <div className="overflow-x-auto">
              <table className="w-full text-sm text-right">
                <thead className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <tr>
                    <th className="px-4 py-3 font-bold rounded-r-xl">#</th>
                    <th className="px-4 py-3 font-bold">اسم الطالب</th>
                    <th className="px-4 py-3 font-bold">الحلقة</th>
                    <th className="px-4 py-3 font-bold">التقدم</th>
                    <th className="px-4 py-3 font-bold rounded-l-xl">تاريخ التسجيل</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]">
                  {(data?.students || []).map((s: any, i: number) => (
                    <tr key={s.id || i} className="hover:bg-[hsl(var(--muted))]/20">
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{i + 1}</td>
                      <td className="px-4 py-2.5 font-bold text-[hsl(var(--foreground))]">{s.name}</td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">{s.halaqah_name || '—'}</td>
                      <td className="px-4 py-2.5">
                        <div className="flex items-center gap-2">
                          <div className="w-20 h-1.5 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                            <div className="h-full gradient-primary rounded-full" style={{ width: `${s.progress || 0}%` }} />
                          </div>
                          <span className="text-xs font-bold">{s.progress || 0}%</span>
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-[hsl(var(--muted-foreground))]">
                        {s.enrollment_date ? new Date(s.enrollment_date).toLocaleDateString('ar-SA') : '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* Print action bottom */}
      <div className="flex justify-center pt-2 print:hidden">
        <PrintButton onClick={handlePrint} />
      </div>
    </div>
  );
}
