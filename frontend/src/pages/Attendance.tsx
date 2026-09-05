import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  CheckCircle2, XCircle, Clock, AlertCircle,
  Users, Search, Calendar, Save, RefreshCw,
  Eye, TrendingUp, BarChart3,
} from 'lucide-react';
import { halaqatApi } from '@/services/api';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';

interface StudentRow {
  id: string;
  name: string;
  status: 'present' | 'absent' | 'late' | 'excused';
}
interface HalaqahOption { id: string; name: string; }

const statusConfig = {
  present: { label: 'حاضر',  icon: CheckCircle2, cls: 'bg-emerald-100 text-emerald-700 border-emerald-300', activeCls: 'gradient-primary text-white border-transparent' },
  absent:  { label: 'غائب',  icon: XCircle,      cls: 'bg-red-50 text-red-600 border-red-200',              activeCls: 'bg-[hsl(var(--danger))] text-white border-transparent' },
  late:    { label: 'متأخر', icon: Clock,         cls: 'bg-amber-50 text-amber-700 border-amber-200',        activeCls: 'gradient-gold text-white border-transparent' },
  excused: { label: 'معذور', icon: AlertCircle,   cls: 'bg-blue-50 text-blue-600 border-blue-200',           activeCls: 'bg-[hsl(var(--info))] text-white border-transparent' },
} as const;
type StatusKey = keyof typeof statusConfig;

/* ─────────────────────────────────────────────
   Component: Teacher mode – record attendance
───────────────────────────────────────────── */
function TeacherAttendance() {
  const { user } = useAuth();
  const [halaqat, setHalaqat]         = useState<HalaqahOption[]>([]);
  const [selectedHalaqah, setSelected] = useState('');
  const [selectedDate, setDate]        = useState(new Date().toISOString().slice(0, 10));
  const [students, setStudents]        = useState<StudentRow[]>([]);
  const [search, setSearch]            = useState('');
  const [loading, setLoading]          = useState(true);
  const [loadingStu, setLoadingStu]    = useState(false);
  const [saving, setSaving]            = useState(false);
  const [savedMsg, setSavedMsg]        = useState('');

  useEffect(() => {
    halaqatApi.getAll().then((data: any) => {
      setHalaqat(data || []);
      if (data?.length > 0) setSelected(data[0].id);
    }).catch(() => {}).finally(() => setLoading(false));
  }, []);

  const loadStudents = useCallback(async () => {
    if (!selectedHalaqah) return;
    setLoadingStu(true);
    try {
      const [attResp, stuResp] = await Promise.all([
        api.get(`/attendance/halaqah/${selectedHalaqah}`, { params: { date: selectedDate } }).catch(() => ({ data: [] })),
        api.get('/students', { params: { halaqah_id: selectedHalaqah } }).catch(() => ({ data: [] })),
      ]);
      let stuData: any[] = stuResp.data || [];
      if (stuData.length > 0 && stuData[0]?.halaqah_id !== undefined)
        stuData = stuData.filter((s: any) => s.halaqah_id === selectedHalaqah);
      const existing: any[] = attResp.data || [];
      setStudents(stuData.map((s: any) => {
        const rec = existing.find((a: any) => a.student_id === s.id);
        return { id: s.id, name: s.name, status: (rec?.status as StatusKey) || 'present' };
      }));
      setSavedMsg('');
    } catch { /* silent */ }
    finally { setLoadingStu(false); }
  }, [selectedHalaqah, selectedDate]);

  useEffect(() => { loadStudents(); }, [loadStudents]);

  const updateStatus = (id: string, status: StatusKey) => {
    setStudents(prev => prev.map(s => s.id === id ? { ...s, status } : s));
    setSavedMsg('');
  };

  const handleSave = async () => {
    if (!students.length) return;
    setSaving(true);
    try {
      await api.post('/attendance', {
        records: students.map(s => ({ student_id: s.id, student_name: s.name, halaqah_id: selectedHalaqah, status: s.status, date: selectedDate })),
        date: selectedDate,
      });
      setSavedMsg('✅ تم حفظ الحضور بنجاح');
    } catch { setSavedMsg('❌ فشل حفظ الحضور'); }
    finally { setSaving(false); }
  };

  const filtered = students.filter(s => s.name.includes(search));
  const stats = {
    present: students.filter(s => s.status === 'present').length,
    absent:  students.filter(s => s.status === 'absent').length,
    late:    students.filter(s => s.status === 'late').length,
    excused: students.filter(s => s.status === 'excused').length,
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader title="تسجيل الحضور والغياب" subtitle="سجّل حضور طلابك يومياً" />

      {/* Filters */}
      <div className="card p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">الحلقة</label>
            <select value={selectedHalaqah} onChange={e => setSelected(e.target.value)} title="الحلقة" className="form-input">
              {halaqat.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">التاريخ</label>
            <input type="date" value={selectedDate} onChange={e => setDate(e.target.value)} className="form-input" dir="ltr" />
          </div>
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">بحث</label>
            <div className="relative"><Search className="absolute right-3 top-3.5 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
              <input placeholder="بحث عن طالب..." value={search} onChange={e => setSearch(e.target.value)} className="form-input pr-9" />
            </div>
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-4 gap-3">
        {(Object.entries(statusConfig) as [StatusKey, typeof statusConfig[StatusKey]][]).map(([key, cfg]) => {
          const Icon = cfg.icon;
          return (
            <div key={key} className="bg-white rounded-[var(--radius)] p-4 shadow-sm border border-[hsl(var(--border))] text-center">
              <div className={`w-10 h-10 rounded-xl flex items-center justify-center mx-auto mb-2 ${key==='present'?'bg-emerald-100':key==='absent'?'bg-red-100':key==='late'?'bg-amber-100':'bg-blue-100'}`}>
                <Icon className={`w-5 h-5 ${key==='present'?'text-emerald-600':key==='absent'?'text-red-600':key==='late'?'text-amber-600':'text-blue-600'}`} />
              </div>
              <p className="text-2xl font-bold">{stats[key]}</p>
              <p className="text-xs text-[hsl(var(--muted-foreground))] font-medium">{cfg.label}</p>
            </div>
          );
        })}
      </div>

      {/* Students list */}
      <div className="bg-white rounded-[var(--radius-lg)] shadow-sm border border-[hsl(var(--border))] overflow-hidden">
        <div className="p-5 border-b border-[hsl(var(--border))] flex items-center justify-between">
          <div className="flex items-center gap-2"><Users className="w-5 h-5 text-[hsl(var(--primary))]" />
            <h3 className="font-bold">{halaqat.find(h => h.id === selectedHalaqah)?.name || 'الحلقة'} · {selectedDate}</h3>
          </div>
          <span className="text-sm text-[hsl(var(--muted-foreground))]">{students.length} طالب</span>
        </div>
        {loadingStu ? (
          <div className="flex items-center justify-center py-16"><div className="w-8 h-8 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" /></div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-[hsl(var(--muted-foreground))]"><Users className="w-12 h-12 mx-auto mb-3 opacity-30" /><p>{search ? 'لا نتائج' : 'لا يوجد طلاب'}</p></div>
        ) : (
          <div className="divide-y divide-[hsl(var(--border))]">
            {filtered.map((student, idx) => (
              <div key={student.id} className={`flex items-center gap-4 px-5 py-3.5 hover:bg-[hsl(var(--muted))]/40 ${student.status==='absent'?'bg-red-50/40':''}`}>
                <div className="w-8 h-8 gradient-primary rounded-xl flex items-center justify-center text-white font-bold text-xs shrink-0">{idx+1}</div>
                <p className="flex-1 font-semibold">{student.name}</p>
                <div className="flex gap-1.5 shrink-0">
                  {(Object.entries(statusConfig) as [StatusKey, typeof statusConfig[StatusKey]][]).map(([key, cfg]) => {
                    const Icon = cfg.icon;
                    return (
                      <button key={key} title={cfg.label} onClick={() => updateStatus(student.id, key)}
                        className={`flex items-center gap-1 px-2.5 py-1.5 rounded-xl border text-xs font-bold transition-all ${student.status===key ? cfg.activeCls : cfg.cls+' hover:opacity-80'}`}>
                        <Icon className="w-3.5 h-3.5" />
                        <span className="hidden sm:inline">{cfg.label}</span>
                      </button>
                    );
                  })}
                </div>
              </div>
            ))}
          </div>
        )}
        {students.length > 0 && (
          <div className="p-5 border-t border-[hsl(var(--border))] flex items-center justify-between gap-4">
            {savedMsg && <span className={`text-sm font-medium ${savedMsg.startsWith('✅')?'text-emerald-600':'text-red-600'}`}>{savedMsg}</span>}
            <div className="flex gap-3 mr-auto">
              <button onClick={loadStudents} className="flex items-center gap-2 px-4 py-2.5 rounded-xl border-2 border-[hsl(var(--border))] font-bold hover:bg-[hsl(var(--muted))] transition-all text-sm">
                <RefreshCw className="w-4 h-4" /> تحديث
              </button>
              <button onClick={handleSave} disabled={saving}
                className="flex items-center gap-2 gradient-primary text-white font-bold px-6 py-2.5 rounded-xl hover:opacity-90 transition-all disabled:opacity-60 text-sm shadow-md">
                {saving ? <span className="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin" /> : <Save className="w-4 h-4" />}
                حفظ الحضور
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Component: Manager mode – monitor only
───────────────────────────────────────────── */
function ManagerAttendanceMonitor() {
  const [halaqat, setHalaqat]           = useState<HalaqahOption[]>([]);
  const [selectedHalaqah, setSelected]  = useState('');
  const [selectedDate, setDate]         = useState(new Date().toISOString().slice(0, 10));
  const [records, setRecords]           = useState<any[]>([]);
  const [allRecords, setAllRecords]     = useState<any[]>([]);
  const [loading, setLoading]           = useState(true);

  useEffect(() => {
    const init = async () => {
      try {
        const h: any[] = await halaqatApi.getAll() as any[];
        setHalaqat(h || []);
        if (h?.length > 0) setSelected(h[0].id);
        const allAtt = await api.get('/attendance/center?limit=200').catch(() => ({ data: [] }));
        setAllRecords(allAtt.data || []);
      } catch { /* silent */ }
      finally { setLoading(false); }
    };
    init();
  }, []);

  useEffect(() => {
    const filtered = allRecords.filter((a: any) => {
      const matchH = !selectedHalaqah || a.halaqah_id === selectedHalaqah;
      const matchD = !selectedDate || a.date?.startsWith(selectedDate);
      return matchH && matchD;
    });
    setRecords(filtered);
  }, [selectedHalaqah, selectedDate, allRecords]);

  // Stats
  const present = records.filter(r => r.status === 'present').length;
  const absent  = records.filter(r => r.status === 'absent').length;
  const late    = records.filter(r => r.status === 'late').length;
  const total   = records.length;
  const rate    = total > 0 ? Math.round(present / total * 100) : 0;

  // Per-halaqah stats
  const halaqahStats = halaqat.map(h => {
    const hRecs = allRecords.filter(r => r.halaqah_id === h.id);
    const hPresent = hRecs.filter(r => r.status === 'present').length;
    return { ...h, total: hRecs.length, present: hPresent, rate: hRecs.length > 0 ? Math.round(hPresent / hRecs.length * 100) : 0 };
  });

  if (loading) return <div className="flex items-center justify-center h-64"><div className="w-8 h-8 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" /></div>;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-1">مراقبة الحضور والغياب</h1>
            <p className="text-sm text-[hsl(var(--ink-3))]">عرض شامل لحضور جميع الحلقات والطلاب</p>
          </div>        </div>
      </div>

      {/* Overall stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
        {[
          { label: 'حضور', val: present, cls: 'stat-card-teal' },
          { label: 'غياب', val: absent,  cls: 'stat-card-rose' },
          { label: 'تأخر', val: late,    cls: 'stat-card-amber' },
          { label: 'نسبة الحضور', val: `${rate}%`, cls: 'stat-card-teal' },
        ].map(s => (
          <div key={s.label} className={`${s.cls} p-5`}>
            <p className="num-display text-3xl text-[hsl(var(--ink))]">{s.val}</p>
            <p className="eyebrow mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Per-halaqah summary */}
      <div className="card p-5">
        <h3 className="font-bold text-[hsl(var(--foreground))] mb-4 flex items-center gap-2">
          <BarChart3 className="w-5 h-5 text-[hsl(var(--primary))]" /> ملخص الحضور حسب الحلقة
        </h3>
        <div className="space-y-4">
          {halaqahStats.map(h => (
            <div key={h.id}>
              <div className="flex items-center justify-between mb-1.5 text-sm">
                <span className="font-bold text-[hsl(var(--foreground))]">{h.name}</span>
                <div className="flex items-center gap-3 text-[hsl(var(--muted-foreground))]">
                  <span>{h.present}/{h.total}</span>
                  <span className={`font-bold ${h.rate >= 80 ? 'text-emerald-600' : h.rate >= 60 ? 'text-amber-600' : 'text-red-600'}`}>{h.rate}%</span>
                </div>
              </div>
              <div className="h-2.5 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                <div className={`h-full rounded-full ${h.rate >= 80 ? 'bg-[hsl(var(--ok))]' : h.rate >= 60 ? 'bg-[hsl(var(--warn))]' : 'stat-card-rose'}`} style={{ width: `${h.rate}%` }} />
              </div>
            </div>
          ))}
          {halaqahStats.length === 0 && <p className="text-center text-[hsl(var(--muted-foreground))] py-4 text-sm">لا توجد حلقات</p>}
        </div>
      </div>

      {/* Filter + Detail */}
      <div className="card p-5">
        <div className="grid grid-cols-2 gap-4 mb-5">
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">الحلقة</label>
            <select value={selectedHalaqah} onChange={e => setSelected(e.target.value)} title="الحلقة" className="form-input">
              <option value="">كل الحلقات</option>
              {halaqat.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">التاريخ</label>
            <input type="date" value={selectedDate} onChange={e => setDate(e.target.value)} className="form-input" dir="ltr" />
          </div>
        </div>
        <div className="space-y-1.5">
          {records.length === 0 ? (
            <p className="text-center text-[hsl(var(--muted-foreground))] py-6 text-sm">لا توجد سجلات بهذه المعايير</p>
          ) : records.slice(0, 20).map((r: any, i: number) => (
            <div key={r.id || i} className="flex items-center justify-between px-4 py-3 rounded-xl bg-[hsl(var(--muted))]/50 text-sm">
              <div className="flex items-center gap-3">
                <div className={`w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold ${r.status==='present'?'bg-emerald-100 text-emerald-700':r.status==='absent'?'bg-red-100 text-red-600':r.status==='late'?'bg-amber-100 text-amber-700':'bg-blue-100 text-blue-700'}`}>
                  {r.status==='present'?'✓':r.status==='absent'?'✗':r.status==='late'?'ت':'ع'}
                </div>
                <div>
                  <p className="font-semibold text-[hsl(var(--foreground))]">{r.student_name || 'طالب'}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">{r.halaqah_name || ''}</p>
                </div>
              </div>
              <div className="text-left">
                <span className={`text-xs font-bold px-2 py-1 rounded-full ${r.status==='present'?'bg-emerald-100 text-emerald-700':r.status==='absent'?'bg-red-100 text-red-600':r.status==='late'?'bg-amber-100 text-amber-700':'bg-blue-100 text-blue-700'}`}>
                  {r.status==='present'?'حاضر':r.status==='absent'?'غائب':r.status==='late'?'متأخر':'معذور'}
                </span>
                <p className="text-[10px] text-[hsl(var(--muted-foreground))] mt-0.5 text-center">{new Date(r.date || Date.now()).toLocaleDateString('ar-SA')}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ─────────────────────────────────────────────
   Main Export – role switcher
───────────────────────────────────────────── */
export default function Attendance() {
  const { user } = useAuth();
  if (user?.role === 'center_manager') return <ManagerAttendanceMonitor />;
  return <TeacherAttendance />;
}

