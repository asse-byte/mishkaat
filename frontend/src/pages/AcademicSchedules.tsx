/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Calendar, Clock, Plus, Search, BookOpen, User,
  Home, Edit2, Trash2, X, CheckCircle2, AlertCircle,
  Sparkles,
} from 'lucide-react';
import api, { halaqatApi, teachersApi } from '@/services/api';

interface ScheduleData {
  id: string;
  subject: string;
  day: string;
  time_slot: string;
  halaqa_id: string;
  teacher_id: string;
  room_number?: string;
  teacher_name?: string;
  halaqa_name?: string;
}

interface Teacher { id: string; name: string; }
interface Halaqah { id: string; name: string; }

const DAYS_OF_WEEK = ['السبت', 'الأحد', 'الإثنين', 'الثلاثاء', 'الأربعاء', 'الخميس'];

const SUBJECT_OPTIONS = [
  'القرآن الكريم',
  'الفقه الإسلامي',
  'أصول الحديث',
  'التفسير العقائدي',
  'اللغة العربية',
  'اللغة الفرنسية',
  'اللغة الإنجليزية',
  'الرياضيات',
  'العلوم العامة',
];

const emptyForm = {
  subject: '',
  day: 'السبت',
  time_slot: '08:00 - 09:30',
  halaqa_id: '',
  teacher_id: '',
  room_number: '',
};

export default function AcademicSchedules() {
  const { user } = useAuth();
  const [schedules, setSchedules] = useState<ScheduleData[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [halaqat, setHalaqat] = useState<Halaqah[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [showAddForm, setShowAddForm] = useState(false);
  const [formData, setFormData] = useState(emptyForm);
  const [error, setError] = useState('');
  const [selectedDay, setSelectedDay] = useState<string>('السبت');
  const [searchTerm, setSearchTerm] = useState('');
  const [editingId, setEditingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [schedsResp, teachersResp, halaqatResp] = await Promise.all([
        api.get<ScheduleData[]>('/academic-schedules'),
        teachersApi.getAll(),
        halaqatApi.getAll(),
      ]);
      setSchedules(schedsResp.data);
      setTeachers(teachersResp as unknown as Teacher[]);
      setHalaqat(halaqatResp as unknown as Halaqah[]);
    } catch (err) {
      setError('حدث خطأ أثناء تحميل جدول الحصص الدراسي.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleSubmit = async () => {
    if (!formData.subject || !formData.day || !formData.time_slot || !formData.halaqa_id || !formData.teacher_id) {
      setError('الرجاء إدخال كافة الحقول الإجبارية المميزة بنجمة');
      return;
    }

    try {
      setSubmitting(true);
      setError('');
      if (editingId) {
        await api.put(`/academic-schedules/${editingId}`, formData);
      } else {
        await api.post('/academic-schedules', formData);
      }
      setShowAddForm(false);
      setFormData(emptyForm);
      setEditingId(null);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'حدث خطأ أثناء حفظ الجدول الدراسي');
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (sched: ScheduleData) => {
    setEditingId(sched.id);
    setFormData({
      subject: sched.subject,
      day: sched.day,
      time_slot: sched.time_slot,
      halaqa_id: sched.halaqa_id,
      teacher_id: sched.teacher_id,
      room_number: sched.room_number || '',
    });
    setShowAddForm(true);
  };

  const handleDelete = async (id: string) => {
    if (!confirm('هل أنت متأكد من حذف هذه الحصة الدراسية من الجدول؟')) return;
    try {
      await api.delete(`/academic-schedules/${id}`);
      await loadData();
    } catch (err) {
      alert('فشل حذف الحصة الدراسية');
    }
  };

  const filteredSchedules = schedules.filter(s => {
    const matchesDay = s.day === selectedDay;
    const matchesSearch = s.subject.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (s.teacher_name || '').toLowerCase().includes(searchTerm.toLowerCase()) ||
      (s.halaqa_name || '').toLowerCase().includes(searchTerm.toLowerCase());
    return matchesDay && matchesSearch;
  });

  const isEditable = user?.role === 'center_manager' || user?.role === 'admin';

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">

      {/* Header banner */}
      <div className="relative overflow-hidden rounded-3xl gradient-primary p-6 text-white shadow-lg">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5 pointer-events-none" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">الجدول الدراسي الأكاديمي الأسبوعي</h1>
            <p className="text-white/70 text-sm">مواءمة وتنسيق الحصص الشرعية والقرآنية ومواد اللغات والرياضيات</p>
          </div>
          <div className="w-14 h-14 bg-white/15 rounded-2xl flex items-center justify-center animate-float">
            <Calendar className="w-7 h-7 text-white" />
          </div>
        </div>
      </div>

      {/* Actions and search bar */}
      <div className="flex flex-col sm:flex-row gap-3">
        {isEditable && (
          <button
            onClick={() => { setEditingId(null); setFormData(emptyForm); setShowAddForm(true); }}
            className="gradient-primary text-white font-bold px-6 py-3 rounded-xl flex items-center gap-2 shadow-md hover:opacity-90 transition-all text-sm"
          >
            <Plus className="w-5 h-5" /> إضافة حصة دراسية جديدة
          </button>
        )}
        <div className="relative flex-1">
          <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <input
            placeholder="البحث باسم المادة، الحلقة، أو المعلم..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] transition-all text-sm"
          />
        </div>
      </div>

      {/* Weekday Selection Bar */}
      <div className="flex overflow-x-auto gap-2 pb-2 scrollbar-thin">
        {DAYS_OF_WEEK.map(day => (
          <button
            key={day}
            onClick={() => setSelectedDay(day)}
            className={`px-5 py-3 rounded-xl font-bold transition-all text-sm shrink-0 shadow-sm ${
              selectedDay === day
                ? 'gradient-primary text-white scale-105'
                : 'bg-white border border-[hsl(var(--border))] hover:bg-[hsl(var(--muted))]'
            }`}
          >
            {day}
          </button>
        ))}
      </div>

      {/* Add / Edit Schedule Form Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
              <h3 className="text-lg font-black flex items-center gap-2">
                <Sparkles className="w-5 h-5 text-[hsl(var(--gold))]" />
                {editingId ? 'تعديل حصة مجدولة' : 'إضافة حصة دراسية جديدة'}
              </h3>
              <button onClick={() => setShowAddForm(false)} className="text-white/70 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            
            <div className="p-5 space-y-4">
              {error && (
                <div className="p-3 rounded-xl bg-rose-50 text-rose-600 text-xs flex items-center gap-2 border border-rose-100">
                  <AlertCircle className="w-4 h-4" />{error}
                </div>
              )}

              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="text-xs font-bold block mb-1">المادة الدراسية *</label>
                  <select
                    value={formData.subject}
                    onChange={e => setFormData({ ...formData, subject: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  >
                    <option value="">اختر المادة الدراسية</option>
                    {SUBJECT_OPTIONS.map(opt => <option key={opt} value={opt}>{opt}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold block mb-1">اليوم الدراسي *</label>
                  <select
                    value={formData.day}
                    onChange={e => setFormData({ ...formData, day: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  >
                    {DAYS_OF_WEEK.map(d => <option key={d} value={d}>{d}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold block mb-1">الفترة الزمنية *</label>
                  <input
                    placeholder="مثال: 08:00 - 09:30"
                    value={formData.time_slot}
                    onChange={e => setFormData({ ...formData, time_slot: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  />
                </div>

                <div>
                  <label className="text-xs font-bold block mb-1">الحلقة / الصف *</label>
                  <select
                    value={formData.halaqa_id}
                    onChange={e => setFormData({ ...formData, halaqa_id: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  >
                    <option value="">اختر الحلقة</option>
                    {halaqat.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                  </select>
                </div>

                <div>
                  <label className="text-xs font-bold block mb-1">المعلم / المحفظ *</label>
                  <select
                    value={formData.teacher_id}
                    onChange={e => setFormData({ ...formData, teacher_id: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  >
                    <option value="">اختر المعلم</option>
                    {teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                  </select>
                </div>

                <div className="col-span-2">
                  <label className="text-xs font-bold block mb-1">رقم القاعة / الغرفة الدراسية</label>
                  <input
                    placeholder="مثال: قاعة 3A"
                    value={formData.room_number}
                    onChange={e => setFormData({ ...formData, room_number: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm"
                  />
                </div>
              </div>

              <div className="flex gap-2 pt-4 border-t">
                <button
                  onClick={handleSubmit}
                  disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2"
                >
                  {submitting ? <LoadingSpinner size="sm" /> : <><CheckCircle2 className="w-4 h-4" />حفظ الحصة المجدولة</>}
                </button>
                <button
                  onClick={() => setShowAddForm(false)}
                  className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-semibold hover:bg-[hsl(var(--muted))]"
                >
                  إلغاء
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Interactive visual layout of Schedules */}
      {filteredSchedules.length === 0 ? (
        <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-[hsl(var(--border))]">
          <Calendar className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-35" />
          <p className="text-[hsl(var(--muted-foreground))] font-semibold">لا توجد حصص دراسية مجدولة ليوم {selectedDay}</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-4 stagger">
          {filteredSchedules.map(sched => {
            const isLanguage = sched.subject.includes('فرنسية') || sched.subject.includes('إنجليزية');
            return (
              <div
                key={sched.id}
                className="bg-white rounded-3xl border border-[hsl(var(--border))] overflow-hidden flex flex-col justify-between hover:shadow-xl transition-all stat-card"
              >
                <div className={`p-4 ${isLanguage ? 'gradient-gold text-white' : 'gradient-primary text-white'}`}>
                  <div className="flex items-start justify-between">
                    <div>
                      <span className="text-[10px] uppercase font-bold badge-gold text-white px-2 py-0.5 rounded-md">
                        {isLanguage ? 'مادة لغات أكاديمية' : 'مادة شرعية / حفظ'}
                      </span>
                      <h3 className="text-lg font-black mt-1 leading-snug">{sched.subject}</h3>
                    </div>
                    {isEditable && (
                      <div className="flex gap-1">
                        <button
                          onClick={() => handleEdit(sched)}
                          className="p-1.5 rounded-lg bg-white/10 hover:bg-white/20 text-white transition-colors"
                          title="تعديل"
                        >
                          <Edit2 className="w-3.5 h-3.5" />
                        </button>
                        <button
                          onClick={() => handleDelete(sched.id)}
                          className="p-1.5 rounded-lg bg-white/10 hover:bg-red-500/50 text-white transition-colors"
                          title="حذف"
                        >
                          <Trash2 className="w-3.5 h-3.5" />
                        </button>
                      </div>
                    )}
                  </div>
                </div>

                <div className="p-5 space-y-3 text-sm text-[hsl(var(--muted-foreground))]">
                  <div className="flex items-center gap-2.5">
                    <Clock className="w-4.5 h-4.5 text-[hsl(var(--primary))]" />
                    <span className="font-semibold text-xs" dir="ltr">{sched.time_slot}</span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <BookOpen className="w-4.5 h-4.5 text-[hsl(var(--primary))]" />
                    <span>حلقة: <strong className="text-[hsl(var(--foreground))]">{sched.halaqa_name}</strong></span>
                  </div>
                  <div className="flex items-center gap-2.5">
                    <User className="w-4.5 h-4.5 text-[hsl(var(--primary))]" />
                    <span>المعلم: <strong className="text-[hsl(var(--foreground))]">{sched.teacher_name}</strong></span>
                  </div>
                  {sched.room_number && (
                    <div className="flex items-center gap-2.5 pt-2 border-t">
                      <Home className="w-4.5 h-4.5 text-[hsl(var(--gold-dark))]" />
                      <span>رقم القاعة: <strong className="text-[hsl(var(--foreground))]">{sched.room_number}</strong></span>
                    </div>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}

    </div>
  );
}
