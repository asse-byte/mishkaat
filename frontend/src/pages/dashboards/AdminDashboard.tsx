import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Building2, Plus, Search, MapPin, Phone, User,
  CheckCircle2, Edit, Users, GraduationCap,
  BookOpen, AlertCircle, X, Eye, Calendar, Hash,
  ChevronRight, Trash2, Save,
} from 'lucide-react';
import api, { centersApi } from '@/services/api';
import WelcomeHero from '@/components/ui/WelcomeHero';
import StatCard from '@/components/ui/StatCard';

interface CenterData {
  id: string;
  name: string;
  address: string;
  phone?: string;
  manager_name?: string;
  manager_id?: string;
  is_active: boolean;
  created_at: string;
  students_count: number;
  teachers_count: number;
  halaqat_count: number;
}

interface CenterDetails extends CenterData {
  teachers_list?: any[];
}

const emptyForm = {
  name: '', address: '', phone: '',
  manager_name: '', manager_username: '', manager_password: '', manager_email: '',
};

const emptyEditForm = { name: '', address: '', phone: '', manager_name: '' };

// مكوّن شارة الرقم التسلسلي
const SeqBadge = ({ id }: { id: string }) => (
  <span className="inline-flex items-center gap-1 text-xs font-mono bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] px-2 py-0.5 rounded-md" dir="ltr">
    <Hash className="w-3 h-3" />{id.slice(-8).toUpperCase()}
  </span>
);

export default function AdminDashboard() {
  const [showAddForm, setShowAddForm]     = useState(false);
  const [searchTerm, setSearchTerm]       = useState('');
  const [centers, setCenters]             = useState<CenterData[]>([]);
  const [loading, setLoading]             = useState(true);
  const [submitting, setSubmitting]       = useState(false);
  const [error, setError]                 = useState('');
  const [formData, setFormData]           = useState(emptyForm);
  const [selectedCenter, setSelectedCenter] = useState<CenterDetails | null>(null);
  const [detailsLoading, setDetailsLoading] = useState(false);
  const [editMode, setEditMode]           = useState(false);
  const [editForm, setEditForm]           = useState(emptyEditForm);
  const [sysStatus, setSysStatus]         = useState<any>(null);

  const loadCenters = useCallback(async () => {
    try {
      setLoading(true);
      const [data, sysResp] = await Promise.all([
        centersApi.getAll(),
        api.get('/admin/system/status')
      ]);
      setCenters(data as unknown as CenterData[]);
      setSysStatus(sysResp.data);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadCenters(); }, [loadCenters]);

  const handleSubmit = async () => {
    if (!formData.name || !formData.address) { setError('الرجاء إدخال اسم المركز والعنوان'); return; }
    try {
      setSubmitting(true); setError('');
      await centersApi.create(formData as any);
      setShowAddForm(false);
      setFormData(emptyForm);
      await loadCenters();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'حدث خطأ أثناء حفظ المركز');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('هل أنت متأكد من حذف هذا المركز؟ لا يمكن التراجع عن هذا الإجراء.')) return;
    try {
      await centersApi.delete(id);
      setSelectedCenter(null);
      await loadCenters();
    } catch { /* silent */ }
  };

  const openDetails = async (center: CenterData) => {
    setSelectedCenter(center as CenterDetails);
    setEditMode(false);
    setEditForm({ name: center.name, address: center.address, phone: center.phone || '', manager_name: center.manager_name || '' });
    try {
      setDetailsLoading(true);
      const resp = await api.get(`/centers/${center.id}/details`);
      setSelectedCenter(resp.data);
      setEditForm({ name: resp.data.name, address: resp.data.address, phone: resp.data.phone || '', manager_name: resp.data.manager_name || '' });
    } catch { /* silent */ }
    finally { setDetailsLoading(false); }
  };

  const handleEditSave = async () => {
    if (!selectedCenter) return;
    try {
      setSubmitting(true);
      await api.put(`/centers/${selectedCenter.id}`, editForm);
      setEditMode(false);
      await loadCenters();
      await openDetails({ ...selectedCenter, ...editForm });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'حدث خطأ أثناء الحفظ');
    } finally { setSubmitting(false); }
  };

  const filtered = centers.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.address.includes(searchTerm) ||
    c.id.slice(-8).toUpperCase().includes(searchTerm.toUpperCase())
  );

  const totals = {
    students: centers.reduce((s, c) => s + c.students_count, 0),
    teachers: centers.reduce((s, c) => s + c.teachers_count, 0),
    halaqat:  centers.reduce((s, c) => s + c.halaqat_count, 0),
  };

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
    <div className="space-y-6 page-fade-in pb-10 text-[hsl(var(--foreground))]">

      {/* Hero banner */}
      <WelcomeHero
        name={null}
        roleTitle="مدير النظام"
        subtext="إدارة وتسجيل مراكز تحفيظ القرآن الكريم"
        stats={[
          { label: 'إجمالي المراكز', value: centers.length },
          { label: 'إجمالي الطلاب', value: totals.students },
        ]}
      />

      {/* Add center action */}
      <div className="flex justify-end">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="btn-gradient-teal text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 shadow-lg hover:opacity-90 transition-all text-sm cursor-pointer"
        >
          <Plus className="w-4 h-4" />
          تسجيل مركز جديد
        </button>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
        <StatCard icon={Building2}     value={centers.length}    title="إجمالي المراكز"  gradientClass="stat-card-blue" />
        <StatCard icon={Users}         value={totals.students}   title="إجمالي الطلاب"   gradientClass="stat-card-teal" />
        <StatCard icon={GraduationCap} value={totals.teachers}   title="المحفظون"         gradientClass="stat-card-purple" />
        <StatCard icon={BookOpen}      value={totals.halaqat}    title="الحلقات"           gradientClass="stat-card-green" />
      </div>

      {/* System Health & Security Monitor */}
      {sysStatus && (
        <div className="bg-[hsl(var(--card))] rounded-3xl border border-[hsl(var(--border))] shadow-sm p-6 space-y-6">
          <div className="flex items-center justify-between border-b pb-3">
            <div>
              <h3 className="text-lg font-black flex items-center gap-2 text-emerald-800">
                <span className="text-xl">🛡️</span>
                مراقبة أمان النظام وتشغيل قاعدة البيانات
              </h3>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">حالة اتصال الخادم الموحد، إحصائيات محاولات تسجيل الدخول، ومحاولات الاختراق</p>
            </div>
            <span className="badge-gold text-xs px-3 py-1 rounded-full font-bold">لوحة المراقبة الفنية</span>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Connection Status Card */}
            <div className="p-5 rounded-2xl bg-[hsl(var(--muted))] border border-[hsl(var(--border))] flex items-center gap-4">
              <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${sysStatus.db_connected ? 'bg-emerald-50 text-emerald-700' : 'bg-rose-50 text-rose-700'}`}>
                <div className={`w-3.5 h-3.5 rounded-full ${sysStatus.db_connected ? 'bg-emerald-600 animate-pulse' : 'bg-rose-600'}`} />
              </div>
              <div className="flex-1 min-w-0">
                <span className="text-xs text-[hsl(var(--muted-foreground))] font-bold block">قاعدة البيانات الموحدة</span>
                <span className="font-bold text-sm text-[hsl(var(--foreground))] block truncate">
                  {sysStatus.db_connected ? '🟢 متصل بنجاح' : '🔴 غير متصل'}
                </span>
                <span className="text-[10px] text-[hsl(var(--muted-foreground))] font-mono" dir="ltr">{sysStatus.db_type}</span>
              </div>
            </div>

            {/* Login successes progress */}
            <div className="p-5 rounded-2xl bg-[hsl(var(--muted))] border border-[hsl(var(--border))] flex flex-col justify-between">
              <div>
                <span className="text-xs text-[hsl(var(--muted-foreground))] font-bold block mb-1">عمليات تسجيل الدخول الناجحة</span>
                <div className="flex items-center justify-between font-mono font-black text-emerald-600 text-lg">
                  <span>{sysStatus.login_attempts.success} عملية</span>
                  <span className="text-xs font-bold text-[hsl(var(--muted-foreground))]">
                    {sysStatus.login_attempts.total > 0 
                      ? `${Math.round((sysStatus.login_attempts.success / sysStatus.login_attempts.total) * 100)}%` 
                      : '0%'}
                  </span>
                </div>
              </div>
              <div className="w-full bg-[hsl(var(--border))] h-2 rounded-full overflow-hidden mt-3">
                <div 
                  className="bg-emerald-600 h-full rounded-full" 
                  style={{ width: `${sysStatus.login_attempts.total > 0 ? (sysStatus.login_attempts.success / sysStatus.login_attempts.total) * 100 : 0}%` }} 
                />
              </div>
            </div>

            {/* Login failures progress */}
            <div className="p-5 rounded-2xl bg-[hsl(var(--muted))] border border-[hsl(var(--border))] flex flex-col justify-between">
              <div>
                <span className="text-xs text-[hsl(var(--muted-foreground))] font-bold block mb-1">عمليات تسجيل الدخول الفاشلة</span>
                <div className="flex items-center justify-between font-mono font-black text-rose-600 text-lg">
                  <span>{sysStatus.login_attempts.failed} محاولة</span>
                  <span className="text-xs font-bold text-[hsl(var(--muted-foreground))]">
                    {sysStatus.login_attempts.total > 0 
                      ? `${Math.round((sysStatus.login_attempts.failed / sysStatus.login_attempts.total) * 100)}%` 
                      : '0%'}
                  </span>
                </div>
              </div>
              <div className="w-full bg-[hsl(var(--border))] h-2 rounded-full overflow-hidden mt-3">
                <div 
                  className="bg-rose-600 h-full rounded-full" 
                  style={{ width: `${sysStatus.login_attempts.total > 0 ? (sysStatus.login_attempts.failed / sysStatus.login_attempts.total) * 100 : 0}%` }} 
                />
              </div>
            </div>
          </div>

          {/* Operational Metrics Subpanel */}
          <div className="grid grid-cols-2 lg:grid-cols-4 gap-4 pt-4 border-t border-[hsl(var(--border))]/60">
            <div className="text-center p-3 bg-[hsl(var(--muted))]/50 rounded-xl">
              <span className="text-[10px] font-bold text-[hsl(var(--muted-foreground))] block">إجمالي محاولات الدخول</span>
              <span className="font-mono font-black text-lg text-[hsl(var(--foreground))]">{sysStatus.login_attempts.total}</span>
            </div>
            <div className="text-center p-3 bg-[hsl(var(--muted))]/50 rounded-xl">
              <span className="text-[10px] font-bold text-[hsl(var(--muted-foreground))] block">حسابات محظورة مؤقتاً (Rate-limits)</span>
              <span className="font-mono font-black text-lg text-amber-600">{sysStatus.login_attempts.active_locks} نشطة</span>
            </div>
            <div className="text-center p-3 bg-[hsl(var(--muted))]/50 rounded-xl">
              <span className="text-[10px] font-bold text-[hsl(var(--muted-foreground))] block">محاولات تسجيل المراكز</span>
              <span className="font-mono font-black text-lg text-[hsl(var(--foreground))]">{sysStatus.public_register_attempts} محاولة</span>
            </div>
            <div className="text-center p-3 bg-[hsl(var(--muted))]/50 rounded-xl">
              <span className="text-[10px] font-bold text-[hsl(var(--muted-foreground))] block">إجمالي سجل النشاط المشفّر</span>
              <span className="font-mono font-black text-lg text-[hsl(var(--foreground))]">{sysStatus.total_audit_logs} حدث</span>
            </div>
          </div>
        </div>
      )}

      {/* Centers Leaderboard & Performance Classification */}
      {centers.length > 0 && (() => {
        const calculateCenterScore = (c: CenterData) => {
          const studentScore = Math.min(40, c.students_count * 2); 
          const teacherScore = Math.min(30, c.teachers_count * 6); 
          const halaqahScore = Math.min(30, c.halaqat_count * 5); 
          return Math.round(studentScore + teacherScore + halaqahScore);
        };

        const getCommitmentLevel = (score: number) => {
          if (score >= 80) return { label: 'ممتاز - التزام كامل', color: 'text-emerald-600 bg-emerald-50 border-emerald-100' };
          if (score >= 50) return { label: 'جيد جداً - نشط', color: 'text-blue-600 bg-blue-50 border-blue-100' };
          if (score >= 25) return { label: 'مقبول - يحتاج متابعة', color: 'text-amber-600 bg-amber-50 border-amber-100' };
          return { label: 'ضعيف - غير ملتزم إدارياً', color: 'text-rose-600 bg-rose-50 border-rose-100' };
        };

        const sortedCenters = [...centers]
          .map(c => ({ ...c, score: calculateCenterScore(c) }))
          .sort((a, b) => b.score - a.score);

        return (
          <div className="bg-[hsl(var(--card))] rounded-3xl border border-[hsl(var(--border))] shadow-sm p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="text-lg font-black flex items-center gap-2 text-emerald-800">
                  <span className="text-xl">🏆</span>
                  تصنيف وتقييم المراكز الأكثر التزاماً وتميزاً
                </h3>
                <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">تقييم تلقائي بناءً على الالتزام الإداري، الحلقات النشطة، وأعداد الطلاب الملتحقين</p>
              </div>
              <span className="badge-gold text-xs px-3 py-1 rounded-full font-bold">تقرير جودة المراكز</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="border-b border-[hsl(var(--border))] text-xs text-[hsl(var(--muted-foreground))] font-bold">
                    <th className="pb-3 text-center w-16">الترتيب</th>
                    <th className="pb-3">المركز</th>
                    <th className="pb-3 text-center">أعداد الطلاب</th>
                    <th className="pb-3 text-center">المحفظين والحلقات</th>
                    <th className="pb-3 text-center">درجة الالتزام</th>
                    <th className="pb-3 text-center">مستوى التقييم</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]/50">
                  {sortedCenters.map((center, idx) => {
                    const level = getCommitmentLevel(center.score);
                    return (
                      <tr key={center.id} className="hover:bg-[hsl(var(--muted))]/30 transition-colors">
                        <td className="py-4 text-center font-bold">
                          {idx === 0 ? <span className="text-xl">🥇</span> : 
                           idx === 1 ? <span className="text-xl">🥈</span> : 
                           idx === 2 ? <span className="text-xl">🥉</span> : 
                           <span className="text-xs text-gray-500 font-mono">#{idx + 1}</span>}
                        </td>
                        <td className="py-4">
                          <span className="font-bold text-[hsl(var(--foreground))] block">{center.name}</span>
                          <span className="text-[10px] text-[hsl(var(--muted-foreground))]" dir="ltr">{center.address}</span>
                        </td>
                        <td className="py-4 text-center font-bold text-[hsl(var(--foreground))]">{center.students_count} طالب</td>
                        <td className="py-4 text-center text-xs text-[hsl(var(--muted-foreground))]">
                          {center.teachers_count} محفظين / {center.halaqat_count} حلقات
                        </td>
                        <td className="py-4 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <div className="w-16 bg-gray-100 h-2 rounded-full overflow-hidden">
                              <div className="bg-emerald-600 h-full rounded-full" style={{ width: `${center.score}%` }} />
                            </div>
                            <span className="text-xs font-mono font-bold text-emerald-700">{center.score}%</span>
                          </div>
                        </td>
                        <td className="py-4 text-center">
                          <span className={`inline-block text-[10px] font-bold px-2.5 py-1 rounded-full border ${level.color}`}>
                            {level.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* Actions bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div className="relative flex-1">
          <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <input
            placeholder="البحث بالاسم أو العنوان أو الرقم التسلسلي..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-[hsl(var(--background))]
                       focus:outline-none focus:border-[hsl(var(--primary))] transition-all text-[hsl(var(--foreground))]"
          />
        </div>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="bg-[hsl(var(--card))] rounded-3xl border-2 border-[hsl(var(--primary))/15] shadow-xl p-6 animate-slide-in-up">
          <div className="flex items-center justify-between mb-5 border-b border-[hsl(var(--border))] pb-3">
            <h3 className="text-lg font-black text-[hsl(var(--foreground))] flex items-center gap-2">
              <Plus className="w-5 h-5 text-[hsl(var(--primary))]" />
              تسجيل مركز جديد
            </h3>
            <button onClick={() => setShowAddForm(false)} title="إغلاق" className="p-2 rounded-lg hover:bg-[hsl(var(--muted))] transition-colors">
              <X className="w-5 h-5 text-[hsl(var(--muted-foreground))]" />
            </button>
          </div>
          <div className="grid md:grid-cols-2 gap-4">
            {[
              { label: 'اسم المركز *', key: 'name', placeholder: 'مثال: مركز النور للقرآن الكريم', dir: 'rtl' },
              { label: 'العنوان *', key: 'address', placeholder: 'المدينة - الحي', dir: 'rtl' },
              { label: 'رقم الهاتف', key: 'phone', placeholder: '+223 XX XX XX XX', dir: 'ltr' },
              { label: 'اسم المدير', key: 'manager_name', placeholder: 'الاسم الكامل', dir: 'rtl' },
              { label: 'اسم مستخدم المدير', key: 'manager_username', placeholder: 'username', dir: 'ltr' },
              { label: 'كلمة مرور المدير', key: 'manager_password', placeholder: '••••••', dir: 'ltr', type: 'password' },
            ].map(f => (
              <div key={f.key}>
                <label className="block text-sm font-semibold text-[hsl(var(--foreground))] mb-1.5">{f.label}</label>
                <input
                  type={f.type || 'text'}
                  placeholder={f.placeholder}
                  dir={f.dir}
                  value={(formData as any)[f.key]}
                  onChange={e => setFormData({ ...formData, [f.key]: e.target.value })}
                  className="w-full h-11 px-4 rounded-xl border-2 border-[hsl(var(--border))] bg-[hsl(var(--background))] text-[hsl(var(--foreground))]
                             focus:outline-none focus:border-[hsl(var(--primary))] transition-all"
                />
              </div>
            ))}
          </div>
          {error && (
            <div className="mt-4 p-3 rounded-xl bg-rose-50 border border-rose-100 text-rose-600 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
          <div className="flex gap-3 mt-6 pt-4 border-t border-[hsl(var(--border))]">
            <button onClick={handleSubmit} disabled={submitting}
              className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all disabled:opacity-60 flex items-center justify-center gap-2">
              {submitting ? <><LoadingSpinner size="sm" /><span>جاري الحفظ...</span></> : <><CheckCircle2 className="w-4 h-4" />حفظ المركز</>}
            </button>
            <button onClick={() => setShowAddForm(false)}
              className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] font-semibold hover:bg-[hsl(var(--muted))] transition-all">
              إلغاء
            </button>
          </div>
        </div>
      )}

      {/* Centers list */}
      <div>
        <div className="flex items-center gap-3 mb-4">
          <h3 className="text-lg font-black text-[hsl(var(--foreground))] flex items-center gap-2">
            <Building2 className="w-5 h-5 text-[hsl(var(--primary))]" />
            قائمة المراكز المسجلة
          </h3>
          <span className="badge-gold text-xs px-2.5 py-1 rounded-full">{filtered.length}</span>
        </div>

        {filtered.length === 0 ? (
          <div className="text-center py-16 rounded-3xl bg-white border-2 border-dashed border-[hsl(var(--border))]">
            <Building2 className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-40" />
            <p className="text-[hsl(var(--muted-foreground))] font-medium">لا توجد مراكز مطابقة</p>
          </div>
        ) : (
          <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5 stagger">
            {filtered.map(center => (
              <div key={center.id} className="bg-[hsl(var(--card))] rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden hover:shadow-xl transition-all stat-card">
                {/* Card header */}
                <div className="gradient-primary p-4">
                  <div className="flex items-start justify-between">
                    <div className="flex-1">
                      <h4 className="font-black text-white text-base leading-snug">{center.name}</h4>
                      <div className="flex items-center gap-1.5 mt-1 text-white/70 text-xs">
                        <MapPin className="w-3 h-3" />
                        <span>{center.address}</span>
                      </div>
                      <div className="mt-2">
                        <SeqBadge id={center.id} />
                      </div>
                    </div>
                    <div className="flex gap-1.5 mr-2">
                      <button
                        onClick={() => openDetails(center)}
                        className="p-1.5 rounded-lg bg-white/15 hover:bg-white/30 transition-colors text-white"
                        title="عرض التفاصيل"
                      >
                        <Eye className="w-4 h-4" />
                      </button>
                      <button
                        onClick={() => handleDelete(center.id)}
                        className="p-1.5 rounded-lg bg-white/15 hover:bg-red-500/60 transition-colors text-white"
                        title="حذف المركز"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    </div>
                  </div>
                </div>

                {/* Stats row */}
                <div className="grid grid-cols-3 divide-x divide-x-reverse divide-[hsl(var(--border))] border-b border-[hsl(var(--border))]">
                  {[
                    { icon: Users, val: center.students_count, label: 'طالب' },
                    { icon: GraduationCap, val: center.teachers_count, label: 'محفظ' },
                    { icon: BookOpen, val: center.halaqat_count, label: 'حلقة' },
                  ].map(s => (
                    <div key={s.label} className="p-3 text-center">
                      <s.icon className="w-4 h-4 mx-auto mb-1 text-[hsl(var(--primary))]" />
                      <p className="text-xl font-black text-[hsl(var(--foreground))]">{s.val}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">{s.label}</p>
                    </div>
                  ))}
                </div>

                {/* Details */}
                <div className="p-4 space-y-2 text-sm text-[hsl(var(--muted-foreground))]">
                  {center.phone && (
                    <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-[hsl(var(--primary))]" /><span dir="ltr">{center.phone}</span></div>
                  )}
                  {center.manager_name && (
                    <div className="flex items-center gap-2"><User className="w-4 h-4 text-[hsl(var(--primary))]" /><span>{center.manager_name}</span></div>
                  )}
                  <div className="flex items-center gap-2 pt-1">
                    <Calendar className="w-4 h-4 text-[hsl(var(--gold))]" />
                    <span className="text-xs">تاريخ التسجيل: {new Date(center.created_at).toLocaleDateString('ar-SA')}</span>
                  </div>
                  <button
                    onClick={() => openDetails(center)}
                    className="w-full mt-2 flex items-center justify-center gap-1 text-[hsl(var(--primary))] text-xs font-bold hover:underline"
                  >
                    <ChevronRight className="w-3.5 h-3.5" /> عرض كامل البيانات
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Center Details Modal */}
      {selectedCenter && (
        <div className="modal-overlay" onClick={() => setSelectedCenter(null)}>
          <div className="bg-[hsl(var(--card))] rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            {/* Modal header */}
            <div className="gradient-primary p-6 rounded-t-3xl">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="text-xl font-black text-white mb-1">{selectedCenter.name}</h2>
                  <SeqBadge id={selectedCenter.id} />
                </div>
                <div className="flex gap-2">
                  {!editMode ? (
                    <button onClick={() => setEditMode(true)} title="تعديل" className="p-2 rounded-xl bg-white/15 hover:bg-white/25 text-white transition-colors">
                      <Edit className="w-4 h-4" />
                    </button>
                  ) : (
                    <button onClick={handleEditSave} disabled={submitting} title="حفظ" className="p-2 rounded-xl bg-white/20 hover:bg-white/30 text-white transition-colors">
                      <Save className="w-4 h-4" />
                    </button>
                  )}
                  <button onClick={() => handleDelete(selectedCenter.id)} title="حذف" className="p-2 rounded-xl bg-red-500/30 hover:bg-red-500/50 text-white transition-colors">
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button onClick={() => setSelectedCenter(null)} title="إغلاق" className="p-2 rounded-xl bg-white/15 hover:bg-white/25 text-white transition-colors">
                    <X className="w-4 h-4" />
                  </button>
                </div>
              </div>
            </div>

            <div className="p-6 space-y-5">
              {detailsLoading ? (
                <div className="flex justify-center py-8"><LoadingSpinner size="lg" /></div>
              ) : (
                <>
                  {/* Stats */}
                  <div className="grid grid-cols-3 gap-3">
                    {[
                      { icon: Users, val: selectedCenter.students_count, label: 'طالب', cls: 'bg-emerald-50 text-emerald-700' },
                      { icon: GraduationCap, val: selectedCenter.teachers_count, label: 'محفظ', cls: 'bg-blue-50 text-blue-700' },
                      { icon: BookOpen, val: selectedCenter.halaqat_count, label: 'حلقة', cls: 'bg-amber-50 text-amber-700' },
                    ].map(s => (
                      <div key={s.label} className={`rounded-2xl p-4 text-center ${s.cls}`}>
                        <s.icon className="w-5 h-5 mx-auto mb-1" />
                        <p className="text-2xl font-black">{s.val}</p>
                        <p className="text-xs font-medium">{s.label}</p>
                      </div>
                    ))}
                  </div>

                  {/* Edit form / info */}
                  {editMode ? (
                    <div className="space-y-3 p-4 rounded-2xl border-2 border-[hsl(var(--primary))/20] bg-[hsl(var(--primary-light))]">
                      <h4 className="font-bold text-[hsl(var(--foreground))] mb-3">تعديل بيانات المركز</h4>
                      {([
                        { label: 'اسم المركز', key: 'name' },
                        { label: 'العنوان', key: 'address' },
                        { label: 'رقم الهاتف', key: 'phone', dir: 'ltr' },
                        { label: 'اسم المدير', key: 'manager_name' },
                      ] as const).map(f => (
                        <div key={f.key}>
                          <label className="text-sm font-semibold text-[hsl(var(--foreground))] block mb-1">{f.label}</label>
                          <input
                            value={(editForm as any)[f.key]}
                            dir={(f as any).dir}
                            title={f.label}
                            placeholder={f.label}
                            onChange={e => setEditForm({ ...editForm, [f.key]: e.target.value })}
                            className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                          />
                        </div>
                      ))}
                      <div className="flex gap-2 mt-3">
                        <button onClick={handleEditSave} disabled={submitting}
                          className="flex-1 gradient-primary text-white font-bold py-2.5 rounded-xl text-sm hover:opacity-90 disabled:opacity-60">
                          {submitting ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                        </button>
                        <button onClick={() => setEditMode(false)} className="px-4 py-2.5 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-semibold">
                          إلغاء
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="space-y-3 text-sm">
                      {(selectedCenter.phone) && (
                        <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--muted))]">
                          <Phone className="w-4 h-4 text-[hsl(var(--primary))] shrink-0" />
                          <span dir="ltr">{selectedCenter.phone}</span>
                        </div>
                      )}
                      {selectedCenter.manager_name && (
                        <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--muted))]">
                          <User className="w-4 h-4 text-[hsl(var(--primary))] shrink-0" />
                          <span>المدير: {selectedCenter.manager_name}</span>
                        </div>
                      )}
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--muted))]">
                        <MapPin className="w-4 h-4 text-[hsl(var(--primary))] shrink-0" />
                        <span>{selectedCenter.address}</span>
                      </div>
                      <div className="flex items-center gap-3 p-3 rounded-xl bg-[hsl(var(--muted))]">
                        <Calendar className="w-4 h-4 text-[hsl(var(--gold-dark))] shrink-0" />
                        <span>تاريخ التسجيل: {new Date(selectedCenter.created_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
                      </div>
                    </div>
                  )}

                  {/* Teachers list */}
                  {selectedCenter.teachers_list && selectedCenter.teachers_list.length > 0 && (
                    <div>
                      <h4 className="font-black text-[hsl(var(--foreground))] mb-3 flex items-center gap-2">
                        <GraduationCap className="w-4 h-4 text-[hsl(var(--primary))]" />
                        المحفظون ({selectedCenter.teachers_list.length})
                      </h4>
                      <div className="space-y-2">
                        {selectedCenter.teachers_list.map((t: any) => (
                          <div key={t.id} className="flex items-center justify-between p-3 rounded-xl border border-[hsl(var(--border))] bg-[hsl(var(--muted))/40]">
                            <div className="flex items-center gap-3">
                              <div className="w-9 h-9 rounded-xl gradient-primary flex items-center justify-center text-white font-black text-sm">
                                {t.name.charAt(0)}
                              </div>
                              <div>
                                <p className="font-semibold text-sm text-[hsl(var(--foreground))]">{t.name}</p>
                                {t.specialization && <p className="text-xs text-[hsl(var(--muted-foreground))]">{t.specialization}</p>}
                              </div>
                            </div>
                            <div className="text-left text-xs text-[hsl(var(--muted-foreground))]">
                              <p>{t.students_count} طالب</p>
                              {t.halaqat?.length > 0 && <p>{t.halaqat.join(' · ')}</p>}
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
