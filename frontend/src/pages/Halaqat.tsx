import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  BookOpen, Plus, Search, Clock, Users, GraduationCap,
  Trash2, X, CheckCircle2, AlertCircle, MapPin, Edit2,
} from 'lucide-react';
import { halaqatApi, teachersApi } from '@/services/api';

interface HalaqahData {
  id: string;
  name: string;
  teacher_id?: string;
  teacher_name?: string;
  center_id: string;
  schedule: string;
  time?: string;
  location?: string;
  max_students: number;
  current_students: number;
  is_active: boolean;
}

interface TeacherData { id: string; name: string; }

const EMPTY_FORM = {
  name: '', teacher_id: '', schedule: '', time_start: '',
  time_end: '', location: '', max_students: '20',
};

export default function Halaqat() {
  const { user } = useAuth();
  const [halaqat, setHalaqat]       = useState<HalaqahData[]>([]);
  const [teachers, setTeachers]     = useState<TeacherData[]>([]);
  const [search, setSearch]         = useState('');
  const [loading, setLoading]       = useState(true);
  const [showForm, setShowForm]     = useState(false);
  const [editItem, setEditItem]     = useState<HalaqahData | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState('');
  const [formData, setFormData]     = useState(EMPTY_FORM);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [halaqatData, teachersData] = await Promise.all([
        halaqatApi.getAll(),
        teachersApi.getAll(),
      ]);
      setHalaqat(halaqatData as unknown as HalaqahData[]);
      setTeachers(teachersData as unknown as TeacherData[]);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const openAdd = () => {
    setEditItem(null);
    setFormData(EMPTY_FORM);
    setError('');
    setShowForm(true);
  };

  const openEdit = (h: HalaqahData) => {
    setEditItem(h);
    const timeParts = h.time ? h.time.split(' - ') : ['', ''];
    setFormData({
      name: h.name,
      teacher_id: h.teacher_id || '',
      schedule: h.schedule || '',
      time_start: timeParts[0] || '',
      time_end: timeParts[1] || '',
      location: h.location || '',
      max_students: String(h.max_students),
    });
    setError('');
    setShowForm(true);
  };

  const handleSubmit = async () => {
    if (!formData.name.trim()) { setError('Ø§Ù„Ø±Ø¬Ø§Ø¡ Ø¥Ø¯Ø®Ø§Ù„ Ø§Ø³Ù… Ø§Ù„Ø­Ù„Ù‚Ø©'); return; }
    const selectedTeacher = teachers.find(t => t.id === formData.teacher_id);
    const time = formData.time_start && formData.time_end
      ? `${formData.time_start} - ${formData.time_end}` : undefined;
    const payload: any = {
      name: formData.name,
      teacher_id: formData.teacher_id || undefined,
      teacher_name: selectedTeacher?.name || undefined,
      center_id: user?.center_id || '',
      schedule: formData.schedule || 'ÙŠÙˆÙ…ÙŠØ§Ù‹',
      time,
      location: formData.location || undefined,
      max_students: parseInt(formData.max_students) || 20,
    };
    try {
      setSubmitting(true); setError('');
      if (editItem) {
        await halaqatApi.update(editItem.id, payload);
      } else {
        await halaqatApi.create(payload);
      }
      setShowForm(false);
      await loadData();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«Ù†Ø§Ø¡ Ø§Ù„Ø­ÙØ¸');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string, name: string) => {
    if (!confirm(`Ù‡Ù„ Ø£Ù†Øª Ù…ØªØ£ÙƒØ¯ Ù…Ù† Ø­Ø°Ù Ø­Ù„Ù‚Ø© "${name}"ØŸ`)) return;
    try {
      await halaqatApi.delete(id);
      await loadData();
    } catch { /* silent */ }
  };

  const filtered = halaqat.filter(
    h => h.name.includes(search) || (h.teacher_name || '').includes(search)
  );

  const totalStudents = halaqat.reduce((s, h) => s + h.current_students, 0);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <div className="text-center">
        <div className="w-16 h-16 gradient-primary rounded-2xl mx-auto mb-4 flex items-center justify-center animate-pulse-soft shadow-xl">
          <BookOpen className="w-8 h-8 text-white" />
        </div>
        <p className="text-[hsl(var(--muted-foreground))] font-medium">Ø¬Ø§Ø±ÙŠ Ø§Ù„ØªØ­Ù…ÙŠÙ„...</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <div className="relative overflow-hidden rounded-3xl p-6 text-white shadow-xl gradient-primary">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ø­Ù„Ù‚Ø§Øª</h1>
            <p className="text-white/70 text-sm">{halaqat.length} Ø­Ù„Ù‚Ø© Â· {totalStudents} Ø·Ø§Ù„Ø¨</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex w-16 h-16 bg-white/15 rounded-2xl items-center justify-center animate-float">
              <BookOpen className="w-8 h-8 text-white" />
            </div>
            {user?.role === 'center_manager' && (
              <button onClick={openAdd}
                className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white font-bold px-4 py-2.5 rounded-xl transition-all text-sm">
                <Plus className="w-4 h-4" /> Ø¥Ø¶Ø§ÙØ© Ø­Ù„Ù‚Ø©
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'Ø§Ù„Ø­Ù„Ù‚Ø§Øª Ø§Ù„Ù†Ø´Ø·Ø©',  value: halaqat.filter(h => h.is_active).length, cls: 'gradient-primary' },
          { label: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ø·Ù„Ø§Ø¨',   value: totalStudents,                            cls: 'gradient-gold' },
          { label: 'Ù…ØªÙˆØ³Ø· Ø§Ù„Ø·Ù„Ø§Ø¨',    value: halaqat.length > 0 ? Math.round(totalStudents / halaqat.length) : 0, cls: 'stat-card-teal' },
        ].map(s => (
          <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <p className="text-3xl font-black">{s.value}</p>
            <p className="text-white/70 text-sm mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute right-3 top-3.5 w-5 h-5 text-[hsl(var(--muted-foreground))]" />
        <input placeholder="Ø§Ù„Ø¨Ø­Ø« Ø¨Ø§Ø³Ù… Ø§Ù„Ø­Ù„Ù‚Ø© Ø£Ùˆ Ø§Ù„Ù…Ø­ÙØ¸..."
          value={search} onChange={e => setSearch(e.target.value)}
          className="form-input pr-10" />
      </div>

      {/* Halaqat Grid */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 text-[hsl(var(--muted-foreground))] bg-white rounded-3xl border-2 border-dashed border-[hsl(var(--border))]">
          <BookOpen className="w-14 h-14 mx-auto mb-3 opacity-30" />
          <p className="font-medium">Ù„Ø§ ØªÙˆØ¬Ø¯ Ø­Ù„Ù‚Ø§Øª{search ? ' Ù…Ø·Ø§Ø¨Ù‚Ø© Ù„Ù„Ø¨Ø­Ø«' : ''}</p>
        </div>
      ) : (
        <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-5 stagger">
          {filtered.map(halaqah => {
            const pct = halaqah.max_students > 0
              ? Math.round(halaqah.current_students / halaqah.max_students * 100)
              : 0;
            const isFull = pct >= 90;
            return (
              <div key={halaqah.id} className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden stat-card">
                {/* Header */}
                <div className="gradient-primary p-5">
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex-1 min-w-0">
                      <h3 className="text-lg font-black text-white truncate">{halaqah.name}</h3>
                      {halaqah.location && (
                        <p className="text-white/70 text-sm mt-0.5 flex items-center gap-1">
                          <MapPin className="w-3.5 h-3.5 shrink-0" />{halaqah.location}
                        </p>
                      )}
                    </div>
                    {/* Actions */}
                    <div className="flex gap-1 shrink-0">
                      {user?.role === 'center_manager' && (
                        <>
                          <button onClick={() => openEdit(halaqah)} title="ØªØ¹Ø¯ÙŠÙ„"
                            className="p-2 rounded-xl bg-white/20 text-white hover:bg-white/30 transition-all">
                            <Edit2 className="w-4 h-4" />
                          </button>
                          <button onClick={() => handleDelete(halaqah.id, halaqah.name)} title="Ø­Ø°Ù"
                            className="p-2 rounded-xl bg-red-400/20 text-white hover:bg-red-400/30 transition-all">
                            <Trash2 className="w-4 h-4" />
                          </button>
                        </>
                      )}
                    </div>
                  </div>
                </div>

                {/* Info */}
                <div className="p-5 space-y-3">
                  {halaqah.teacher_name && (
                    <div className="flex items-center gap-2 text-sm text-[hsl(var(--foreground))]">
                      <GraduationCap className="w-4 h-4 text-[hsl(var(--primary))]" />
                      <span className="font-medium">{halaqah.teacher_name}</span>
                    </div>
                  )}
                  {halaqah.time && (
                    <div className="flex items-center gap-2 text-sm text-[hsl(var(--muted-foreground))]">
                      <Clock className="w-4 h-4" />
                      <span>{halaqah.time} Â· {halaqah.schedule}</span>
                    </div>
                  )}

                  {/* Progress */}
                  <div>
                    <div className="flex items-center justify-between mb-1.5">
                      <div className="flex items-center gap-1.5 text-sm">
                        <Users className="w-4 h-4 text-[hsl(var(--gold))]" />
                        <span className="font-black text-[hsl(var(--foreground))]">{halaqah.current_students}</span>
                        <span className="text-[hsl(var(--muted-foreground))]">/ {halaqah.max_students}</span>
                      </div>
                      <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${isFull ? 'bg-red-100 text-red-600' : 'bg-emerald-100 text-emerald-700'}`}>
                        {pct}% {isFull ? 'Â· Ù…Ù…ØªÙ„Ø¦Ø©' : ''}
                      </span>
                    </div>
                    <div className="h-2 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                      <div className={`h-full rounded-full transition-all ${isFull ? 'stat-card-rose' : 'gradient-primary'}`}
                        style={{ width: `${pct}%` }} />
                    </div>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Add/Edit Modal */}
      {showForm && (
        <div className="modal-overlay animate-fade-in">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="gradient-primary p-6 rounded-t-3xl flex items-center justify-between">
              <h2 className="text-lg font-black text-white">
                {editItem ? 'ØªØ¹Ø¯ÙŠÙ„ Ø§Ù„Ø­Ù„Ù‚Ø©' : 'Ø¥Ø¶Ø§ÙØ© Ø­Ù„Ù‚Ø© Ø¬Ø¯ÙŠØ¯Ø©'}
              </h2>
              <button onClick={() => setShowForm(false)}
                className="p-2 rounded-xl bg-white/20 text-white hover:bg-white/30 transition-all">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ø³Ù… Ø§Ù„Ø­Ù„Ù‚Ø© *</label>
                <input className="form-input" placeholder="Ù…Ø«Ø§Ù„: Ø­Ù„Ù‚Ø© Ø§Ù„ÙØ¬Ø±"
                  value={formData.name}
                  onChange={e => setFormData({ ...formData, name: e.target.value })} />
              </div>
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ù…Ø­ÙØ¸</label>
                <select className="form-input" title="Ø§Ø®ØªØ± Ø§Ù„Ù…Ø­ÙØ¸"
                  value={formData.teacher_id}
                  onChange={e => setFormData({ ...formData, teacher_id: e.target.value })}>
                  <option value="">Ø§Ø®ØªØ± Ø§Ù„Ù…Ø­ÙØ¸</option>
                  {teachers.map(t => <option key={t.id} value={t.id}>{t.name}</option>)}
                </select>
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">ÙˆÙ‚Øª Ø§Ù„Ø¨Ø¯Ø§ÙŠØ©</label>
                  <input type="time" dir="ltr" className="form-input"
                    value={formData.time_start}
                    onChange={e => setFormData({ ...formData, time_start: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">ÙˆÙ‚Øª Ø§Ù„Ù†Ù‡Ø§ÙŠØ©</label>
                  <input type="time" dir="ltr" className="form-input"
                    value={formData.time_end}
                    onChange={e => setFormData({ ...formData, time_end: e.target.value })} />
                </div>
              </div>
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø¬Ø¯ÙˆÙ„ Ø§Ù„Ø¯Ø±Ø§Ø³ÙŠ</label>
                <input className="form-input" placeholder="Ù…Ø«Ø§Ù„: ÙŠÙˆÙ…ÙŠØ§Ù‹ Ø¨Ø¹Ø¯ ØµÙ„Ø§Ø© Ø§Ù„ÙØ¬Ø±"
                  value={formData.schedule}
                  onChange={e => setFormData({ ...formData, schedule: e.target.value })} />
              </div>
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ù…ÙˆÙ‚Ø¹</label>
                  <input className="form-input" placeholder="Ø§Ù„Ù‚Ø§Ø¹Ø© Ø§Ù„Ø±Ø¦ÙŠØ³ÙŠØ©"
                    value={formData.location}
                    onChange={e => setFormData({ ...formData, location: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø­Ø¯ Ø§Ù„Ø£Ù‚ØµÙ‰</label>
                  <input type="number" min="1" dir="ltr" className="form-input"
                    value={formData.max_students}
                    onChange={e => setFormData({ ...formData, max_students: e.target.value })} />
                </div>
              </div>

              {error && (
                <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />{error}
                </div>
              )}

              <div className="flex gap-3 pt-1">
                <button onClick={handleSubmit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all disabled:opacity-60 flex items-center justify-center gap-2">
                  {submitting
                    ? <span className="w-5 h-5 border-2 border-white border-t-transparent rounded-full animate-spin" />
                    : <><CheckCircle2 className="w-5 h-5" />{editItem ? 'Ø­ÙØ¸ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„Ø§Øª' : 'Ø¥Ù†Ø´Ø§Ø¡ Ø§Ù„Ø­Ù„Ù‚Ø©'}</>}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] text-[hsl(var(--foreground))] font-bold hover:bg-[hsl(var(--muted))] transition-all">
                  Ø¥Ù„ØºØ§Ø¡
                </button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

