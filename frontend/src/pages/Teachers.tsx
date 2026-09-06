import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import { useAuth } from '@/contexts/AuthContext';
import {
  GraduationCap, Plus, Search, Phone, BookOpen, Edit, Trash2,
  X, CheckCircle2, Users, AlertCircle, Heart, Clock,
  ArrowLeftRight, ChevronRight, Save, Eye,
} from 'lucide-react';
import { teachersApi, halaqatApi } from '@/services/api';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';
import NumberInput from '@/components/ui/NumberInput';

interface TeacherData {
  id: string;
  name: string;
  phone?: string;
  specialization?: string;
  marital_status?: 'single' | 'married' | 'divorced' | 'widowed';
  work_schedule?: 'full_time' | 'part_time';
  salary?: number;
  center_id: string;
  hire_date: string;
  halaqat: string[];
  students_count: number;
  is_active: boolean;
}

interface HalaqahData { id: string; name: string; teacher_name?: string; }

const maritalLabels: Record<string, string> = {
  single: 'أعزب', married: 'متزوج', divorced: 'مطلق', widowed: 'أرمل',
};
const scheduleLabels: Record<string, string> = {
  full_time: 'دوام كامل', part_time: 'دوام جزئي',
};
const specializationOptions = ['حفص عن عاصم', 'ورش عن نافع', 'قالون عن نافع', 'القراءات العشر', 'تجويد فقط'];

const emptyForm = {
  name: '', phone: '', specialization: '',
  marital_status: '' as any,
  work_schedule: '' as any,
  salary: '',
  username: '', password: '',
};

export default function Teachers() {
  const { user } = useAuth();
  const [teachers, setTeachers]         = useState<TeacherData[]>([]);
  const [halaqat, setHalaqat]           = useState<HalaqahData[]>([]);
  const [loading, setLoading]           = useState(true);
  const [searchTerm, setSearchTerm]     = useState('');
  const [showAddForm, setShowAddForm]   = useState(false);
  const [formData, setFormData]         = useState(emptyForm);
  const [submitting, setSubmitting]     = useState(false);
  const [error, setError]               = useState('');
  const [selectedTeacher, setSelectedTeacher] = useState<TeacherData | null>(null);
  const [editMode, setEditMode]         = useState(false);
  const [editForm, setEditForm]         = useState<Partial<Omit<TeacherData, 'salary'> & { salary: string }>>({});
  const [showTransfer, setShowTransfer] = useState(false);
  const [transferData, setTransferData] = useState({ from_halaqah_id: '', to_halaqah_id: '' });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [t, h] = await Promise.all([teachersApi.getAll(), halaqatApi.getAll()]);
      setTeachers(t as unknown as TeacherData[]);
      setHalaqat(h as unknown as HalaqahData[]);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSubmit = async () => {
    if (!formData.name) { setError('الرجاء إدخال اسم المحفظ'); return; }
    try {
      setSubmitting(true); setError('');
      await teachersApi.create({
        name: formData.name,
        phone: formData.phone || undefined,
        specialization: formData.specialization || undefined,
        marital_status: formData.marital_status || undefined,
        work_schedule: formData.work_schedule || undefined,
        salary: formData.salary ? Number(formData.salary) : undefined,
        center_id: user?.center_id || '',
        username: formData.username || undefined,
        password: formData.password || undefined,
      } as any);
      setShowAddForm(false);
      setFormData(emptyForm);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'حدث خطأ');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('هل أنت متأكد من حذف هذا المحفظ؟')) return;
    try {
      await teachersApi.delete(id);
      setSelectedTeacher(null);
      await loadData();
    } catch { /* silent */ }
  };

  const handleEditSave = async () => {
    if (!selectedTeacher) return;
    try {
      setSubmitting(true);
      await api.put(`/teachers/${selectedTeacher.id}`, {
        name: editForm.name,
        phone: editForm.phone,
        specialization: editForm.specialization,
        marital_status: editForm.marital_status,
        work_schedule: editForm.work_schedule,
        salary: editForm.salary ? Number(editForm.salary) : undefined,
      });
      setEditMode(false);
      await loadData();
      const updated = teachers.find(t => t.id === selectedTeacher.id);
      if (updated) setSelectedTeacher({ ...updated, ...editForm as any });
    } catch (err: any) {
      alert(err.response?.data?.detail || 'حدث خطأ');
    } finally { setSubmitting(false); }
  };

  const handleTransfer = async () => {
    if (!selectedTeacher || !transferData.from_halaqah_id || !transferData.to_halaqah_id) return;
    try {
      setSubmitting(true);
      const resp = await api.post(`/teachers/${selectedTeacher.id}/transfer`, transferData);
      alert(resp.data.message);
      setShowTransfer(false);
      await loadData();
    } catch (err: any) {
      alert(err.response?.data?.detail || 'حدث خطأ');
    } finally { setSubmitting(false); }
  };

  const filtered = useMemo(() =>
    teachers.filter(t =>
      t.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (t.specialization || '').includes(searchTerm)
    ),
    [teachers, searchTerm]
  );

  const openEdit = (teacher: TeacherData) => {
    setSelectedTeacher(teacher);
    setEditMode(true);
    setEditForm({
      name: teacher.name,
      phone: teacher.phone || '',
      specialization: teacher.specialization || '',
      marital_status: teacher.marital_status,
      work_schedule: teacher.work_schedule,
      salary: teacher.salary?.toString() || '',
    });
  };

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <PageHeader
        title="إدارة المحفظين"
        subtitle={`${teachers.length} محفظ · ${teachers.reduce((s, t) => s + t.students_count, 0)} طالب`}
      />

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button onClick={() => setShowAddForm(true)}
          className="gradient-primary text-white font-bold px-6 py-3 rounded-xl flex items-center gap-2 shadow-md hover:opacity-90 transition-all">
          <Plus className="w-5 h-5" /> إضافة محفظ جديد
        </button>
        <div className="relative flex-1">
          <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <input
            placeholder="البحث باسم المحفظ أو التخصص..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] transition-all"
          />
        </div>
      </div>

      {/* Add Teacher Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between">
              <h3 className="text-lg font-bold text-white flex items-center gap-2">
                <Plus className="w-5 h-5" /> إضافة محفظ جديد
              </h3>
              <button onClick={() => setShowAddForm(false)} className="text-[hsl(var(--ink-3))] hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {/* Basic info */}
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="text-sm font-semibold block mb-1">اسم المحفظ *</label>
                  <input placeholder="الاسم الكامل" value={formData.name}
                    onChange={e => setFormData({ ...formData, name: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">رقم الهاتف</label>
                  <input placeholder="+223 XX XX XX" dir="ltr" value={formData.phone}
                    onChange={e => setFormData({ ...formData, phone: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">التخصص</label>
                  <select value={formData.specialization}
                    onChange={e => setFormData({ ...formData, specialization: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]">
                    <option value="">اختر التخصص</option>
                    {specializationOptions.map(s => <option key={s} value={s}>{s}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">الحالة الاجتماعية</label>
                  <select value={formData.marital_status}
                    onChange={e => setFormData({ ...formData, marital_status: e.target.value as any })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]">
                    <option value="">اختر الحالة</option>
                    <option value="single">أعزب</option>
                    <option value="married">متزوج</option>
                    <option value="divorced">مطلق</option>
                    <option value="widowed">أرمل</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">الفترة</label>
                  <select value={formData.work_schedule}
                    onChange={e => setFormData({ ...formData, work_schedule: e.target.value as any })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]">
                    <option value="">اختر الفترة</option>
                    <option value="full_time">دوام كامل</option>
                    <option value="part_time">دوام جزئي</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">الراتب (FCFA)</label>
                  <NumberInput value={formData.salary}
                    onChange={v => setFormData({ ...formData, salary: v })}
                    placeholder="0" min={0} suffix="FCFA"
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
              </div>
              {/* Login account */}
              <div className="border-t pt-4">
                <h4 className="font-bold text-sm text-[hsl(var(--foreground))] mb-3">حساب الدخول (اختياري)</h4>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="text-sm font-semibold block mb-1">اسم المستخدم</label>
                    <input placeholder="username" dir="ltr" value={formData.username}
                      onChange={e => setFormData({ ...formData, username: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">كلمة المرور</label>
                    <input type="password" placeholder="••••••" dir="ltr" value={formData.password}
                      onChange={e => setFormData({ ...formData, password: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]" />
                  </div>
                </div>
              </div>
              {error && (
                <div className="p-3 rounded-xl bg-red-50 text-red-600 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />{error}
                </div>
              )}
              <div className="flex gap-3">
                <button onClick={handleSubmit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2">
                  {submitting ? <><LoadingSpinner size="sm" />جاري الحفظ...</> : <><CheckCircle2 className="w-4 h-4" />حفظ المحفظ</>}
                </button>
                <button onClick={() => setShowAddForm(false)}
                  className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] font-semibold hover:bg-[hsl(var(--muted))] transition-all">
                  إلغاء
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Teachers Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 rounded-[var(--radius-lg)] bg-white border-2 border-dashed border-[hsl(var(--border))]">
          <GraduationCap className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-40" />
          <p className="text-[hsl(var(--muted-foreground))] font-medium">لا يوجد محفظون مطابقون</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 stagger">
          {filtered.map(teacher => (
            <div key={teacher.id} className="card overflow-hidden">
              {/* كان رأس البطاقة شريطاً كحلياً صمّاء داخل بطاقة فاتحة — بقيّة النظام
                  صارت أسطحاً فاتحة، فيفصله الآن خطّ لا لون كامل. */}
              <div className="p-4 border-b border-[hsl(var(--line-2))]">
                <div className="flex items-start justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-12 h-12 rounded-[var(--radius)] bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))] flex items-center justify-center text-[hsl(var(--lamp-strong))] font-bold text-lg">
                      {teacher.name.charAt(0)}
                    </div>
                    <div>
                      <h3 className="text-base font-bold text-[hsl(var(--ink))]">{teacher.name}</h3>
                      {teacher.specialization && (
                        <p className="eyebrow">{teacher.specialization}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-1">
                    <button onClick={() => { setSelectedTeacher(teacher); setEditMode(false); setShowTransfer(false); }} title="عرض التفاصيل"
                      className="p-1.5 rounded-[var(--radius-sm)] text-[hsl(var(--ink-3))] hover:text-[hsl(var(--ink))] hover:bg-[hsl(var(--surface-2))] transition-colors">
                      <Eye className="w-4 h-4" />
                    </button>
                    <button onClick={() => openEdit(teacher)} title="تعديل"
                      className="p-1.5 rounded-[var(--radius-sm)] text-[hsl(var(--ink-3))] hover:text-[hsl(var(--ink))] hover:bg-[hsl(var(--surface-2))] transition-colors">
                      <Edit className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDelete(teacher.id)} title="حذف"
                      className="p-1.5 rounded-[var(--radius-sm)] text-[hsl(var(--ink-3))] hover:text-[hsl(var(--danger))] hover:bg-[hsl(var(--danger-wash))] transition-colors">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-2 text-sm">
                {teacher.phone && (
                  <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))]">
                    <Phone className="w-4 h-4 text-[hsl(var(--primary))]" />
                    <span dir="ltr">{teacher.phone}</span>
                  </div>
                )}
                <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))]">
                  <BookOpen className="w-4 h-4 text-[hsl(var(--primary))]" />
                  <span>{teacher.halaqat.length > 0 ? teacher.halaqat.join(' · ') : 'لا توجد حلقات'}</span>
                </div>
                {teacher.marital_status && (
                  <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))]">
                    <Heart className="w-4 h-4 text-rose-400" />
                    <span>{maritalLabels[teacher.marital_status]}</span>
                  </div>
                )}
                {teacher.work_schedule && (
                  <div className="flex items-center gap-2 text-[hsl(var(--muted-foreground))]">
                    <Clock className="w-4 h-4 text-amber-500" />
                    <span>{scheduleLabels[teacher.work_schedule]}</span>
                  </div>
                )}
                <div className="flex items-center justify-between pt-2 border-t border-[hsl(var(--border))]">
                  <div className="flex items-center gap-2">
                    <Users className="w-4 h-4 text-[hsl(var(--gold))]" />
                    <span className="font-bold text-[hsl(var(--foreground))]">{teacher.students_count}</span>
                    <span className="text-[hsl(var(--muted-foreground))]">طالب</span>
                  </div>
                  {teacher.salary && (
                    <span className="text-xs font-bold text-[hsl(var(--primary))] bg-[hsl(var(--primary-light))] px-2 py-0.5 rounded-lg">
                      {teacher.salary.toLocaleString()} FCFA
                    </span>
                  )}
                </div>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Teacher Detail / Edit Modal */}
      {selectedTeacher && (
        <div className="modal-overlay" onClick={() => { setSelectedTeacher(null); setEditMode(false); setShowTransfer(false); }}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-[var(--radius)] bg-[hsl(var(--lamp-wash))] border border-[hsl(var(--lamp-line))] flex items-center justify-center text-[hsl(var(--lamp-strong))] font-bold text-2xl">
                    {selectedTeacher.name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-lg font-bold text-white">{selectedTeacher.name}</h2>
                    {selectedTeacher.specialization && <p className="text-sm text-[hsl(var(--ink-3))]">{selectedTeacher.specialization}</p>}
                  </div>
                </div>
                <button onClick={() => { setSelectedTeacher(null); setEditMode(false); }} title="إغلاق" className="text-[hsl(var(--ink-3))] hover:text-white">
                  <X className="w-5 h-5" />
                </button>
              </div>
              {/* action buttons */}
              <div className="flex gap-2 mt-4">
                <button onClick={() => setEditMode(!editMode)} title="تبديل وضع التعديل"
                  className="flex-1 flex items-center justify-center gap-1 py-2 rounded-[var(--radius-sm)] border border-[hsl(var(--line))] hover:border-[hsl(var(--lamp))] text-[hsl(var(--ink-2))] text-sm font-semibold transition-colors">
                  <Edit className="w-4 h-4" /> {editMode ? 'إلغاء التعديل' : 'تعديل'}
                </button>
                <button onClick={() => setShowTransfer(!showTransfer)} title="نقل إلى حلقة أخرى"
                  className="flex-1 flex items-center justify-center gap-1 py-2 rounded-[var(--radius-sm)] border border-[hsl(var(--line))] hover:border-[hsl(var(--lamp))] text-[hsl(var(--ink-2))] text-sm font-semibold transition-colors">
                  <ArrowLeftRight className="w-4 h-4" /> نقل الحلقة
                </button>
                <button onClick={() => handleDelete(selectedTeacher.id)} title="حذف المحفظ"
                  className="px-4 py-2 rounded-xl bg-[hsl(var(--danger))]/30 hover:bg-[hsl(var(--danger))]/50 text-white text-sm font-bold transition-all">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="p-5 space-y-4">
              {editMode ? (
                <div className="space-y-3">
                  {[
                    { label: 'الاسم', key: 'name' },
                    { label: 'الهاتف', key: 'phone', dir: 'ltr' },
                    { label: 'الراتب (FCFA)', key: 'salary', type: 'number', dir: 'ltr' },
                  ].map(f => (
                    <div key={f.key}>
                      <label className="text-sm font-semibold block mb-1">{f.label}</label>
                      <input type={f.type || 'text'} dir={(f as any).dir} title={f.label} placeholder={f.label}
                        value={(editForm as any)[f.key] || ''}
                        onChange={e => setEditForm({ ...editForm, [f.key]: e.target.value })}
                        className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                    </div>
                  ))}
                  <div className="grid grid-cols-2 gap-3">
                    <div>
                      <label className="text-sm font-semibold block mb-1">التخصص</label>
                      <select value={editForm.specialization || ''} title="التخصص"
                        onChange={e => setEditForm({ ...editForm, specialization: e.target.value })}
                        className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                        <option value="">اختر</option>
                        {specializationOptions.map(s => <option key={s} value={s}>{s}</option>)}
                      </select>
                    </div>
                    <div>
                      <label className="text-sm font-semibold block mb-1">الحالة الاجتماعية</label>
                      <select value={editForm.marital_status || ''} title="الحالة الاجتماعية"
                        onChange={e => setEditForm({ ...editForm, marital_status: e.target.value as any })}
                        className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                        <option value="">اختر</option>
                        <option value="single">أعزب</option>
                        <option value="married">متزوج</option>
                        <option value="divorced">مطلق</option>
                        <option value="widowed">أرمل</option>
                      </select>
                    </div>
                    <div className="col-span-2">
                      <label className="text-sm font-semibold block mb-1">الفترة</label>
                      <select value={editForm.work_schedule || ''} title="الفترة"
                        onChange={e => setEditForm({ ...editForm, work_schedule: e.target.value as any })}
                        className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                        <option value="">اختر الفترة</option>
                        <option value="full_time">دوام كامل</option>
                        <option value="part_time">دوام جزئي</option>
                      </select>
                    </div>
                  </div>
                  <button onClick={handleEditSave} disabled={submitting}
                    className="w-full gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2">
                    <Save className="w-4 h-4" /> {submitting ? 'جاري الحفظ...' : 'حفظ التغييرات'}
                  </button>
                </div>
              ) : showTransfer ? (
                <div className="space-y-3 p-4 rounded-[var(--radius)] border-2 border-[hsl(var(--primary))/20] bg-[hsl(var(--accent))]">
                  <h4 className="font-bold text-[hsl(var(--foreground))] flex items-center gap-2">
                    <ArrowLeftRight className="w-4 h-4 text-[hsl(var(--primary))]" /> نقل المحفظ بين الحلقات
                  </h4>
                  <div>
                    <label className="text-sm font-semibold block mb-1">من حلقة</label>
                    <select value={transferData.from_halaqah_id}
                      onChange={e => setTransferData({ ...transferData, from_halaqah_id: e.target.value })}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">اختر الحلقة الحالية</option>
                      {halaqat.map(h => <option key={h.id} value={h.id}>{h.name} {h.teacher_name ? `(${h.teacher_name})` : ''}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">إلى حلقة</label>
                    <select value={transferData.to_halaqah_id}
                      onChange={e => setTransferData({ ...transferData, to_halaqah_id: e.target.value })}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">اختر الحلقة الجديدة</option>
                      {halaqat.filter(h => h.id !== transferData.from_halaqah_id).map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                    </select>
                  </div>
                  <button onClick={handleTransfer} disabled={submitting || !transferData.from_halaqah_id || !transferData.to_halaqah_id}
                    className="w-full gradient-primary text-white font-bold py-2.5 rounded-xl hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2">
                    <ArrowLeftRight className="w-4 h-4" /> تأكيد النقل
                  </button>
                </div>
              ) : (
                <div className="space-y-3 text-sm">
                  {[
                    { label: 'الهاتف', val: selectedTeacher.phone, dir: 'ltr' },
                    { label: 'الحالة الاجتماعية', val: selectedTeacher.marital_status ? maritalLabels[selectedTeacher.marital_status] : null },
                    { label: 'الفترة', val: selectedTeacher.work_schedule ? scheduleLabels[selectedTeacher.work_schedule] : null },
                    { label: 'الراتب', val: selectedTeacher.salary ? `${selectedTeacher.salary.toLocaleString()} FCFA` : null },
                    { label: 'عدد الطلاب', val: `${selectedTeacher.students_count} طالب` },
                    { label: 'الحلقات', val: selectedTeacher.halaqat.length > 0 ? selectedTeacher.halaqat.join(' · ') : 'لا توجد حلقات' },
                    { label: 'تاريخ التعيين', val: new Date(selectedTeacher.hire_date).toLocaleDateString('ar-SA') },
                  ].filter(item => item.val).map(item => (
                    <div key={item.label} className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                      <span className="text-[hsl(var(--muted-foreground))] font-medium">{item.label}</span>
                      <span className="font-bold text-[hsl(var(--foreground))]" dir={(item as any).dir}>{item.val}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
