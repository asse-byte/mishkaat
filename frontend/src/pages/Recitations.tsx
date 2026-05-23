import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  BookOpen, Plus, Search, Calendar, User,
  CheckCircle2, X, AlertCircle, Filter, Trash2,
} from 'lucide-react';
import { recitationsApi, studentsApi } from '@/services/api';

// 114 Ø³ÙˆØ±Ø© ÙƒØ§Ù…Ù„Ø©
const ALL_SURAHS = [
  'Ø§Ù„ÙØ§ØªØ­Ø©','Ø§Ù„Ø¨Ù‚Ø±Ø©','Ø¢Ù„ Ø¹Ù…Ø±Ø§Ù†','Ø§Ù„Ù†Ø³Ø§Ø¡','Ø§Ù„Ù…Ø§Ø¦Ø¯Ø©','Ø§Ù„Ø£Ù†Ø¹Ø§Ù…','Ø§Ù„Ø£Ø¹Ø±Ø§Ù','Ø§Ù„Ø£Ù†ÙØ§Ù„',
  'Ø§Ù„ØªÙˆØ¨Ø©','ÙŠÙˆÙ†Ø³','Ù‡ÙˆØ¯','ÙŠÙˆØ³Ù','Ø§Ù„Ø±Ø¹Ø¯','Ø¥Ø¨Ø±Ø§Ù‡ÙŠÙ…','Ø§Ù„Ø­Ø¬Ø±','Ø§Ù„Ù†Ø­Ù„','Ø§Ù„Ø¥Ø³Ø±Ø§Ø¡',
  'Ø§Ù„ÙƒÙ‡Ù','Ù…Ø±ÙŠÙ…','Ø·Ù‡','Ø§Ù„Ø£Ù†Ø¨ÙŠØ§Ø¡','Ø§Ù„Ø­Ø¬','Ø§Ù„Ù…Ø¤Ù…Ù†ÙˆÙ†','Ø§Ù„Ù†ÙˆØ±','Ø§Ù„ÙØ±Ù‚Ø§Ù†','Ø§Ù„Ø´Ø¹Ø±Ø§Ø¡',
  'Ø§Ù„Ù†Ù…Ù„','Ø§Ù„Ù‚ØµØµ','Ø§Ù„Ø¹Ù†ÙƒØ¨ÙˆØª','Ø§Ù„Ø±ÙˆÙ…','Ù„Ù‚Ù…Ø§Ù†','Ø§Ù„Ø³Ø¬Ø¯Ø©','Ø§Ù„Ø£Ø­Ø²Ø§Ø¨','Ø³Ø¨Ø£','ÙØ§Ø·Ø±',
  'ÙŠØ³','Ø§Ù„ØµØ§ÙØ§Øª','Øµ','Ø§Ù„Ø²Ù…Ø±','ØºØ§ÙØ±','ÙØµÙ„Øª','Ø§Ù„Ø´ÙˆØ±Ù‰','Ø§Ù„Ø²Ø®Ø±Ù','Ø§Ù„Ø¯Ø®Ø§Ù†',
  'Ø§Ù„Ø¬Ø§Ø«ÙŠØ©','Ø§Ù„Ø£Ø­Ù‚Ø§Ù','Ù…Ø­Ù…Ø¯','Ø§Ù„ÙØªØ­','Ø§Ù„Ø­Ø¬Ø±Ø§Øª','Ù‚','Ø§Ù„Ø°Ø§Ø±ÙŠØ§Øª','Ø§Ù„Ø·ÙˆØ±',
  'Ø§Ù„Ù†Ø¬Ù…','Ø§Ù„Ù‚Ù…Ø±','Ø§Ù„Ø±Ø­Ù…Ù†','Ø§Ù„ÙˆØ§Ù‚Ø¹Ø©','Ø§Ù„Ø­Ø¯ÙŠØ¯','Ø§Ù„Ù…Ø¬Ø§Ø¯Ù„Ø©','Ø§Ù„Ø­Ø´Ø±','Ø§Ù„Ù…Ù…ØªØ­Ù†Ø©',
  'Ø§Ù„ØµÙ','Ø§Ù„Ø¬Ù…Ø¹Ø©','Ø§Ù„Ù…Ù†Ø§ÙÙ‚ÙˆÙ†','Ø§Ù„ØªØºØ§Ø¨Ù†','Ø§Ù„Ø·Ù„Ø§Ù‚','Ø§Ù„ØªØ­Ø±ÙŠÙ…','Ø§Ù„Ù…Ù„Ùƒ','Ø§Ù„Ù‚Ù„Ù…',
  'Ø§Ù„Ø­Ø§Ù‚Ø©','Ø§Ù„Ù…Ø¹Ø§Ø±Ø¬','Ù†ÙˆØ­','Ø§Ù„Ø¬Ù†','Ø§Ù„Ù…Ø²Ù…Ù„','Ø§Ù„Ù…Ø¯Ø«Ø±','Ø§Ù„Ù‚ÙŠØ§Ù…Ø©','Ø§Ù„Ø¥Ù†Ø³Ø§Ù†',
  'Ø§Ù„Ù…Ø±Ø³Ù„Ø§Øª','Ø§Ù„Ù†Ø¨Ø£','Ø§Ù„Ù†Ø§Ø²Ø¹Ø§Øª','Ø¹Ø¨Ø³','Ø§Ù„ØªÙƒÙˆÙŠØ±','Ø§Ù„Ø§Ù†ÙØ·Ø§Ø±','Ø§Ù„Ù…Ø·ÙÙÙŠÙ†',
  'Ø§Ù„Ø§Ù†Ø´Ù‚Ø§Ù‚','Ø§Ù„Ø¨Ø±ÙˆØ¬','Ø§Ù„Ø·Ø§Ø±Ù‚','Ø§Ù„Ø£Ø¹Ù„Ù‰','Ø§Ù„ØºØ§Ø´ÙŠØ©','Ø§Ù„ÙØ¬Ø±','Ø§Ù„Ø¨Ù„Ø¯','Ø§Ù„Ø´Ù…Ø³',
  'Ø§Ù„Ù„ÙŠÙ„','Ø§Ù„Ø¶Ø­Ù‰','Ø§Ù„Ø´Ø±Ø­','Ø§Ù„ØªÙŠÙ†','Ø§Ù„Ø¹Ù„Ù‚','Ø§Ù„Ù‚Ø¯Ø±','Ø§Ù„Ø¨ÙŠÙ†Ø©','Ø§Ù„Ø²Ù„Ø²Ù„Ø©',
  'Ø§Ù„Ø¹Ø§Ø¯ÙŠØ§Øª','Ø§Ù„Ù‚Ø§Ø±Ø¹Ø©','Ø§Ù„ØªÙƒØ§Ø«Ø±','Ø§Ù„Ø¹ØµØ±','Ø§Ù„Ù‡Ù…Ø²Ø©','Ø§Ù„ÙÙŠÙ„','Ù‚Ø±ÙŠØ´','Ø§Ù„Ù…Ø§Ø¹ÙˆÙ†',
  'Ø§Ù„ÙƒÙˆØ«Ø±','Ø§Ù„ÙƒØ§ÙØ±ÙˆÙ†','Ø§Ù„Ù†ØµØ±','Ø§Ù„Ù…Ø³Ø¯','Ø§Ù„Ø¥Ø®Ù„Ø§Øµ','Ø§Ù„ÙÙ„Ù‚','Ø§Ù„Ù†Ø§Ø³',
];

const evalMap: Record<string, { text: string; cls: string }> = {
  excellent:         { text: 'Ù…Ù…ØªØ§Ø²',       cls: 'bg-emerald-100 text-emerald-700' },
  good:              { text: 'Ø¬ÙŠØ¯',         cls: 'bg-blue-100 text-blue-700'       },
  acceptable:        { text: 'Ù…Ù‚Ø¨ÙˆÙ„',       cls: 'bg-amber-100 text-amber-700'     },
  needs_improvement: { text: 'ØªØ­Ø³ÙŠÙ†',       cls: 'bg-red-100 text-red-700'         },
};

const typeMap: Record<string, string> = {
  new: 'Ø¬Ø¯ÙŠØ¯', review: 'Ù…Ø±Ø§Ø¬Ø¹Ø©',
};

interface RecitationData {
  id: string;
  student_id: string;
  student_name?: string;
  teacher_name?: string;
  surah_name: string;
  start_ayah: number;
  end_ayah: number;
  evaluation: string;
  mistakes_count: number;
  notes?: string;
  recitation_type: string;
  date: string;
}

interface StudentData { id: string; name: string; }

const EMPTY_FORM = {
  student_id: '', surah_name: '', start_ayah: '1', end_ayah: '10',
  evaluation: 'excellent', mistakes_count: '0', notes: '', recitation_type: 'new',
};

export default function Recitations() {
  const { user } = useAuth();
  const [recitations, setRecitations] = useState<RecitationData[]>([]);
  const [students, setStudents]       = useState<StudentData[]>([]);
  const [loading, setLoading]         = useState(true);
  const [showForm, setShowForm]       = useState(false);
  const [submitting, setSubmitting]   = useState(false);
  const [error, setError]             = useState('');
  const [formData, setFormData]       = useState(EMPTY_FORM);

  // Filters
  const [search, setSearch]           = useState('');
  const [filterEval, setFilterEval]   = useState('');
  const [filterType, setFilterType]   = useState('');
  const [filterDate, setFilterDate]   = useState('');

  // Only teachers can add recitations; center_manager monitors
  const canAdd = user?.role === 'teacher';

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [recData, stuData] = await Promise.all([
        recitationsApi.getAll(),
        studentsApi.getAll(),
      ]);
      setRecitations(recData as unknown as RecitationData[]);
      setStudents(stuData as unknown as StudentData[]);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSubmit = async () => {
    if (!formData.student_id || !formData.surah_name) {
      setError('Ø§Ù„Ø±Ø¬Ø§Ø¡ Ø§Ø®ØªÙŠØ§Ø± Ø§Ù„Ø·Ø§Ù„Ø¨ ÙˆØ§Ù„Ø³ÙˆØ±Ø©'); return;
    }
    const student = students.find(s => s.id === formData.student_id);
    try {
      setSubmitting(true); setError('');
      await recitationsApi.create({
        student_id: formData.student_id,
        student_name: student?.name,
        teacher_id: user?.id || '',
        teacher_name: user?.name || '',
        surah_name: formData.surah_name,
        start_ayah: parseInt(formData.start_ayah) || 1,
        end_ayah: parseInt(formData.end_ayah) || 10,
        evaluation: formData.evaluation,
        mistakes_count: parseInt(formData.mistakes_count) || 0,
        notes: formData.notes || undefined,
        recitation_type: formData.recitation_type,
      } as any);
      setShowForm(false);
      setFormData(EMPTY_FORM);
      await loadData();
    } catch (e: any) {
      setError(e.response?.data?.detail || 'Ø­Ø¯Ø« Ø®Ø·Ø£ Ø£Ø«Ù†Ø§Ø¡ Ø­ÙØ¸ Ø§Ù„ØªØ³Ù…ÙŠØ¹');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Ù‡Ù„ Ø£Ù†Øª Ù…ØªØ£ÙƒØ¯ Ù…Ù† Ø­Ø°Ù Ù‡Ø°Ø§ Ø§Ù„ØªØ³Ù…ÙŠØ¹ØŸ')) return;
    try {
      await recitationsApi.update(id, { is_deleted: true } as any);
      await loadData();
    } catch { /* silent */ }
  };

  const filtered = recitations.filter(r => {
    const matchSearch = (!search || (r.student_name || '').includes(search) || r.surah_name.includes(search));
    const matchEval   = (!filterEval || r.evaluation === filterEval);
    const matchType   = (!filterType || r.recitation_type === filterType);
    const matchDate   = (!filterDate || r.date?.startsWith(filterDate));
    return matchSearch && matchEval && matchType && matchDate;
  });

  // Stats
  const totalExcellent = recitations.filter(r => r.evaluation === 'excellent').length;
  const avgMistakes = recitations.length > 0
    ? (recitations.reduce((s, r) => s + (r.mistakes_count || 0), 0) / recitations.length).toFixed(1)
    : '0';

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
            <h1 className="text-2xl font-black mb-1">Ø³Ø¬Ù„ Ø§Ù„ØªØ³Ù…ÙŠØ¹</h1>
            <p className="text-white/70 text-sm">{recitations.length} ØªØ³Ù…ÙŠØ¹ Ù…Ø³Ø¬ÙŽÙ‘Ù„</p>
          </div>
          <div className="flex items-center gap-3">
            <div className="hidden md:flex w-16 h-16 bg-white/15 rounded-2xl items-center justify-center animate-float">
              <BookOpen className="w-8 h-8 text-white" />
            </div>
            {canAdd && (
              <button onClick={() => { setShowForm(true); setFormData(EMPTY_FORM); setError(''); }}
                className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white font-bold px-4 py-2.5 rounded-xl transition-all text-sm">
                <Plus className="w-4 h-4" /> ØªØ³Ù…ÙŠØ¹ Ø¬Ø¯ÙŠØ¯
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„ØªØ³Ù…ÙŠØ¹Ø§Øª', value: recitations.length, cls: 'gradient-primary' },
          { label: 'ØªÙ‚ÙŠÙŠÙ… Ù…Ù…ØªØ§Ø²',      value: totalExcellent,     cls: 'gradient-gold' },
          { label: 'Ù…ØªÙˆØ³Ø· Ø§Ù„Ø£Ø®Ø·Ø§Ø¡',    value: avgMistakes,        cls: 'stat-card-teal' },
        ].map(s => (
          <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <p className="text-3xl font-black">{s.value}</p>
            <p className="text-white/70 text-sm mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
          <div className="relative">
            <Search className="absolute right-3 top-3.5 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
            <input placeholder="Ø¨Ø­Ø« Ø¨Ø§Ù„Ø§Ø³Ù… Ø£Ùˆ Ø§Ù„Ø³ÙˆØ±Ø©..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="form-input pr-9" />
          </div>
          <select value={filterEval} onChange={e => setFilterEval(e.target.value)}
            title="ÙÙ„ØªØ± Ø§Ù„ØªÙ‚ÙŠÙŠÙ…" className="form-input">
            <option value="">ÙƒÙ„ Ø§Ù„ØªÙ‚ÙŠÙŠÙ…Ø§Øª</option>
            {Object.entries(evalMap).map(([k, v]) => <option key={k} value={k}>{v.text}</option>)}
          </select>
          <select value={filterType} onChange={e => setFilterType(e.target.value)}
            title="ÙÙ„ØªØ± Ø§Ù„Ù†ÙˆØ¹" className="form-input">
            <option value="">Ø§Ù„ÙƒÙ„ (Ø¬Ø¯ÙŠØ¯/Ù…Ø±Ø§Ø¬Ø¹Ø©)</option>
            <option value="new">Ø¬Ø¯ÙŠØ¯</option>
            <option value="review">Ù…Ø±Ø§Ø¬Ø¹Ø©</option>
          </select>
          <input type="date" value={filterDate} onChange={e => setFilterDate(e.target.value)}
            title="ÙÙ„ØªØ± Ø§Ù„ØªØ§Ø±ÙŠØ®" className="form-input" dir="ltr" />
        </div>
        {(search || filterEval || filterType || filterDate) && (
          <p className="text-xs text-[hsl(var(--muted-foreground))] mt-3">
            Ø¹Ø±Ø¶ {filtered.length} Ù…Ù† {recitations.length} Ù†ØªÙŠØ¬Ø©
            <button onClick={() => { setSearch(''); setFilterEval(''); setFilterType(''); setFilterDate(''); }}
              className="mr-3 text-[hsl(var(--primary))] font-bold underline">Ù…Ø³Ø­ Ø§Ù„ÙÙ„Ø§ØªØ±</button>
          </p>
        )}
      </div>

      {/* List */}
      <div className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
        {filtered.length === 0 ? (
          <div className="py-16 text-center text-[hsl(var(--muted-foreground))]">
            <BookOpen className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">{recitations.length === 0 ? 'Ù„Ø§ ØªÙˆØ¬Ø¯ ØªØ³Ù…ÙŠØ¹Ø§Øª Ø¨Ø¹Ø¯' : 'Ù„Ø§ ØªÙˆØ¬Ø¯ Ù†ØªØ§Ø¦Ø¬'}</p>
          </div>
        ) : (
          <div className="divide-y divide-[hsl(var(--border))]">
            {filtered.map(rec => (
              <div key={rec.id} className="flex items-center gap-4 px-5 py-4 hover:bg-[hsl(var(--muted))]/30 transition-colors">
                {/* Avatar */}
                <div className="w-10 h-10 gradient-primary rounded-xl flex items-center justify-center text-white font-black text-sm shrink-0">
                  {(rec.student_name || 'Ø·').charAt(0)}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap mb-0.5">
                    <p className="font-bold text-[hsl(var(--foreground))] text-sm">{rec.student_name || 'Ø·Ø§Ù„Ø¨'}</p>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${evalMap[rec.evaluation]?.cls}`}>
                      {evalMap[rec.evaluation]?.text}
                    </span>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      rec.recitation_type === 'new' ? 'bg-purple-100 text-purple-700' : 'bg-gray-100 text-gray-600'}`}>
                      {typeMap[rec.recitation_type] || rec.recitation_type}
                    </span>
                  </div>
                  <div className="flex flex-wrap gap-3 text-xs text-[hsl(var(--muted-foreground))]">
                    <span className="flex items-center gap-1">
                      <BookOpen className="w-3.5 h-3.5" />{rec.surah_name} ({rec.start_ayah}â€“{rec.end_ayah})
                    </span>
                    <span className="flex items-center gap-1">
                      <Calendar className="w-3.5 h-3.5" />{new Date(rec.date).toLocaleDateString('ar-SA')}
                    </span>
                    {rec.teacher_name && (
                      <span className="flex items-center gap-1">
                        <User className="w-3.5 h-3.5" />{rec.teacher_name}
                      </span>
                    )}
                  </div>
                  {rec.notes && (
                    <p className="mt-1 text-xs text-[hsl(var(--muted-foreground))] bg-[hsl(var(--muted))] px-2 py-1 rounded-lg inline-block">
                      {rec.notes}
                    </p>
                  )}
                </div>

                {/* Mistakes */}
                <div className="text-center shrink-0">
                  <p className={`text-lg font-black ${rec.mistakes_count === 0 ? 'text-emerald-600' : 'text-amber-600'}`}>
                    {rec.mistakes_count}
                  </p>
                  <p className="text-[10px] text-[hsl(var(--muted-foreground))]">Ø£Ø®Ø·Ø§Ø¡</p>
                </div>

                {/* Delete (teacher/manager only) */}
                {canAdd && (
                  <button onClick={() => handleDelete(rec.id)} title="Ø­Ø°Ù"
                    className="p-2 rounded-xl text-[hsl(var(--muted-foreground))] hover:text-red-600 hover:bg-red-50 transition-all shrink-0">
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Add Modal */}
      {showForm && (
        <div className="modal-overlay animate-fade-in">
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto">
            <div className="gradient-primary p-6 rounded-t-3xl flex items-center justify-between">
              <h2 className="text-lg font-black text-white">ØªØ³Ø¬ÙŠÙ„ ØªØ³Ù…ÙŠØ¹ Ø¬Ø¯ÙŠØ¯</h2>
              <button onClick={() => setShowForm(false)}
                className="p-2 rounded-xl bg-white/20 text-white hover:bg-white/30 transition-all">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-4">

              {/* Student */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø·Ø§Ù„Ø¨ *</label>
                <select className="form-input" title="Ø§Ø®ØªØ± Ø§Ù„Ø·Ø§Ù„Ø¨"
                  value={formData.student_id}
                  onChange={e => setFormData({ ...formData, student_id: e.target.value })}>
                  <option value="">Ø§Ø®ØªØ± Ø§Ù„Ø·Ø§Ù„Ø¨</option>
                  {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>

              {/* Surah */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„Ø³ÙˆØ±Ø© *</label>
                <select className="form-input" title="Ø§Ø®ØªØ± Ø§Ù„Ø³ÙˆØ±Ø©"
                  value={formData.surah_name}
                  onChange={e => setFormData({ ...formData, surah_name: e.target.value })}>
                  <option value="">Ø§Ø®ØªØ± Ø§Ù„Ø³ÙˆØ±Ø©</option>
                  {ALL_SURAHS.map((s, i) => (
                    <option key={s} value={s}>{i + 1}. {s}</option>
                  ))}
                </select>
              </div>

              {/* Ayahs */}
              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ù…Ù† Ø¢ÙŠØ©</label>
                  <input type="number" min="1" className="form-input" dir="ltr"
                    value={formData.start_ayah}
                    onChange={e => setFormData({ ...formData, start_ayah: e.target.value })} />
                </div>
                <div>
                  <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø¥Ù„Ù‰ Ø¢ÙŠØ©</label>
                  <input type="number" min="1" className="form-input" dir="ltr"
                    value={formData.end_ayah}
                    onChange={e => setFormData({ ...formData, end_ayah: e.target.value })} />
                </div>
              </div>

              {/* Type */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ù†ÙˆØ¹ Ø§Ù„ØªØ³Ù…ÙŠØ¹</label>
                <div className="flex gap-3">
                  {[{ k: 'new', label: 'Ø­ÙØ¸ Ø¬Ø¯ÙŠØ¯' }, { k: 'review', label: 'Ù…Ø±Ø§Ø¬Ø¹Ø©' }].map(opt => (
                    <label key={opt.k} className={`flex-1 flex items-center justify-center gap-2 p-3 rounded-xl border-2 cursor-pointer transition-all font-bold text-sm ${
                      formData.recitation_type === opt.k
                        ? 'gradient-primary text-white border-transparent'
                        : 'border-[hsl(var(--border))] text-[hsl(var(--foreground))] hover:border-[hsl(var(--primary))]'}`}>
                      <input type="radio" name="rtype" value={opt.k} className="sr-only"
                        checked={formData.recitation_type === opt.k}
                        onChange={() => setFormData({ ...formData, recitation_type: opt.k })} />
                      {opt.label}
                    </label>
                  ))}
                </div>
              </div>

              {/* Evaluation */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø§Ù„ØªÙ‚ÙŠÙŠÙ…</label>
                <div className="grid grid-cols-2 gap-2">
                  {Object.entries(evalMap).map(([k, v]) => (
                    <label key={k} className={`flex items-center gap-2 p-3 rounded-xl border-2 cursor-pointer transition-all font-bold text-sm ${
                      formData.evaluation === k ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary-light))] text-[hsl(var(--primary))]' : 'border-[hsl(var(--border))] hover:border-[hsl(var(--primary))]'}`}>
                      <input type="radio" name="eval" value={k} className="sr-only"
                        checked={formData.evaluation === k}
                        onChange={() => setFormData({ ...formData, evaluation: k })} />
                      <span className={`w-2.5 h-2.5 rounded-full ${k === 'excellent' ? 'bg-emerald-500' : k === 'good' ? 'bg-blue-500' : k === 'acceptable' ? 'bg-amber-500' : 'stat-card-rose'}`} />
                      {v.text}
                    </label>
                  ))}
                </div>
              </div>

              {/* Mistakes */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ø¹Ø¯Ø¯ Ø§Ù„Ø£Ø®Ø·Ø§Ø¡</label>
                <input type="number" min="0" className="form-input" dir="ltr"
                  value={formData.mistakes_count}
                  onChange={e => setFormData({ ...formData, mistakes_count: e.target.value })} />
              </div>

              {/* Notes */}
              <div>
                <label className="block text-sm font-bold text-[hsl(var(--foreground))] mb-1.5">Ù…Ù„Ø§Ø­Ø¸Ø§Øª</label>
                <textarea rows={3} placeholder="Ù…Ù„Ø§Ø­Ø¸Ø§Øª Ø¥Ø¶Ø§ÙÙŠØ©..."
                  className="w-full px-4 py-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white font-[Tajawal] text-[hsl(var(--foreground))] placeholder:text-[hsl(var(--muted-foreground))] focus:outline-none focus:border-[hsl(var(--primary))] resize-none transition-colors text-sm"
                  value={formData.notes}
                  onChange={e => setFormData({ ...formData, notes: e.target.value })} />
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
                    : <><CheckCircle2 className="w-5 h-5" />Ø­ÙØ¸ Ø§Ù„ØªØ³Ù…ÙŠØ¹</>}
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

