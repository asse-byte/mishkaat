import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Building2, Plus, Search, MapPin, Phone, User,
  CheckCircle2, XCircle, Edit, Users, GraduationCap,
  BookOpen, AlertCircle, X, Eye, Calendar, Hash,
  ChevronRight, Trash2, Save,
} from 'lucide-react';
import api, { centersApi } from '@/services/api';

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

// مكوّن بطاقة إحصاء
const StatCard = ({ icon: Icon, value, label, color }: { icon: React.ElementType; value: number | string; label: string; color: string }) => (
  <div className={`stat-card rounded-2xl p-5 text-white shadow-lg animate-fade-in ${color}`}>
    <div className="w-11 h-11 bg-white/20 rounded-xl flex items-center justify-center mb-4">
      <Icon className="w-6 h-6 text-white" />
    </div>
    <p className="text-4xl font-black mb-1">{value}</p>
    <p className="text-white/80 text-sm font-medium">{label}</p>
  </div>
);

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

  const loadCenters = useCallback(async () => {
    try {
      setLoading(true);
      const data = await centersApi.getAll();
      setCenters(data as unknown as CenterData[]);
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
    <div className="space-y-6 animate-fade-in">

      {/* Hero banner */}
      <div className="relative overflow-hidden rounded-3xl gradient-primary p-7 text-white shadow-xl">
        <div className="absolute top-[-40px] left-[-40px] w-52 h-52 rounded-full bg-white/5" />
        <div className="absolute bottom-[-30px] right-20 w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <p className="text-white/60 font-medium mb-1 text-sm">لوحة التحكم ·</p>
            <h1 className="text-3xl font-black mb-2">مدير النظام</h1>
            <p className="text-white/75 text-sm">إدارة وتسجيل مراكز تحفيظ القرآن الكريم</p>
          </div>
          <div className="hidden md:flex w-20 h-20 bg-white/15 rounded-2xl items-center justify-center animate-float">
            <Building2 className="w-10 h-10 text-white" />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-4 stagger">
        <StatCard icon={Building2}     value={centers.length}    label="إجمالي المراكز" color="gradient-primary" />
        <StatCard icon={Users}         value={totals.students}   label="إجمالي الطلاب"  color="gradient-gold" />
        <StatCard icon={GraduationCap} value={totals.teachers}   label="المحفظون"        color="bg-[hsl(222,42%,28%)]" />
        <StatCard icon={BookOpen}      value={totals.halaqat}    label="الحلقات"          color="bg-[hsl(152,45%,38%)]" />
      </div>

      {/* Actions bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button
          onClick={() => setShowAddForm(!showAddForm)}
          className="gradient-primary text-white font-bold px-6 py-3 rounded-xl flex items-center gap-2 shadow-md hover:opacity-90 transition-all"
        >
          <Plus className="w-5 h-5" />
          تسجيل مركز جديد
        </button>
        <div className="relative flex-1">
          <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <input
            placeholder="البحث بالاسم أو العنوان أو الرقم التسلسلي..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white
                       focus:outline-none focus:border-[hsl(var(--primary))] transition-all text-[hsl(var(--foreground))]"
          />
        </div>
      </div>

      {/* Add form */}
      {showAddForm && (
        <div className="glass rounded-3xl border-2 border-[hsl(var(--primary))/15] shadow-xl p-6 animate-slide-in-up">
          <div className="flex items-center justify-between mb-5">
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
                  className="w-full h-11 px-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white
                             focus:outline-none focus:border-[hsl(var(--primary))] transition-all"
                />
              </div>
            ))}
          </div>
          {error && (
            <div className="mt-4 p-3 rounded-xl bg-red-50 border border-red-100 text-red-600 text-sm flex items-center gap-2">
              <AlertCircle className="w-4 h-4 shrink-0" />{error}
            </div>
          )}
          <div className="flex gap-3 mt-6">
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
              <div key={center.id} className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden hover:shadow-xl transition-all stat-card">
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
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
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
