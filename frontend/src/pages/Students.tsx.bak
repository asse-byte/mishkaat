import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import { useAuth } from '@/contexts/AuthContext';
import {
  Users, Plus, Search, Phone, Calendar, BookOpen, Edit, Trash2,
  X, CheckCircle2, TrendingUp, Clock, RefreshCw,
  AlertCircle, MapPin, Eye, Save, User, ChevronDown, ChevronUp, LineChart,
} from 'lucide-react';
import { Link } from 'react-router-dom';
import { studentsApi, halaqatApi } from '@/services/api';
import api from '@/services/api';

const memorizationPlans = [
  { id: 'plan_2_years', name: 'Ø®Ø·Ø© Ø³Ù†ØªÙŠÙ†',   years: 2, description: 'Ù„Ù„Ù…ØªÙØ±ØºÙŠÙ†'   },
  { id: 'plan_3_years', name: 'Ø®Ø·Ø© 3 Ø³Ù†ÙˆØ§Øª', years: 3, description: 'Ù„Ù„Ù…Ù†ØªØ¸Ù…ÙŠÙ†'   },
  { id: 'plan_4_years', name: 'Ø®Ø·Ø© 4 Ø³Ù†ÙˆØ§Øª', years: 4, description: 'Ù„Ù„Ø¯Ø§Ø±Ø³ÙŠÙ†'    },
  { id: 'plan_5_years', name: 'Ø®Ø·Ø© 5 Ø³Ù†ÙˆØ§Øª', years: 5, description: 'Ù„Ù„Ù…Ø¨ØªØ¯Ø¦ÙŠÙ†'   },
];

const planLabels: Record<string, string> = {
  plan_2_years: 'Ø®Ø·Ø© Ø³Ù†ØªÙŠÙ†', plan_3_years: 'Ø®Ø·Ø© 3 Ø³Ù†ÙˆØ§Øª',
  plan_4_years: 'Ø®Ø·Ø© 4 Ø³Ù†ÙˆØ§Øª', plan_5_years: 'Ø®Ø·Ø© 5 Ø³Ù†ÙˆØ§Øª', plan_review: 'Ø®Ø·Ø© Ù…Ø±Ø§Ø¬Ø¹Ø©',
};

interface StudentData {
  id: string;
  name: string;
  date_of_birth?: string;
  phone?: string;
  parent_name?: string;
  parent_phone?: string;
  guardian_address?: string;
  halaqah_id?: string;
  halaqah_name?: string;
  memorization_plan?: string;
  student_type: 'memorizing' | 'reviewing';
  enrollment_date: string;
  progress: number;
  current_surah?: string;
  current_ayah?: number;
  center_id: string;
}

interface HalaqahData { id: string; name: string; }

const emptyForm = {
  name: '', date_of_birth: '', phone: '',
  parent_name: '', parent_phone: '', guardian_address: '',
  halaqah_id: '', halaqah_name: '',
};

export default function Students() {
  const { user } = useAuth();
  const [students, setStudents]         = useState<StudentData[]>([]);
  const [halaqat, setHalaqat]           = useState<HalaqahData[]>([]);
  const [loading, setLoading]           = useState(true);
  const [searchTerm, setSearchTerm]     = useState('');
  const [showAddForm, setShowAddForm]   = useState(false);
  const [formData, setFormData]         = useState(emptyForm);
  const [selectedPlan, setSelectedPlan] = useState('');
  const [studentType, setStudentType]   = useState<'memorizing'|'reviewing'>('memorizing');
  const [submitting, setSubmitting]     = useState(false);
  const [error, setError]               = useState('');
  const [selectedStudent, setSelectedStudent] = useState<StudentData | null>(null);
  const [editMode, setEditMode]         = useState(false);
  const [editForm, setEditForm]         = useState<Partial<StudentData>>({});
  const [expandedId, setExpandedId]     = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [s, h] = await Promise.all([studentsApi.getAll(), halaqatApi.getAll()]);
      setStudents(s as unknown as StudentData[]);
      setHalaqat(h as unknown as HalaqahData[]);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  const handleSubmit = async () => {
    if (!formData.name) { setError('Ø§Ù„Ø±Ø¬Ø§Ø¡ Ø¥Ø¯Ø®Ø§Ù„ Ø§Ø³Ù… Ø§Ù„Ø·Ø§Ù„Ø¨'); return; }
    const halaqahObj = halaqat.find(h => h.id === formData.halaqah_id);
    try {
      setSubmitting(true); setError('');
      await studentsApi.create({
        name: formData.name,
        date_of_birth: formData.date_of_birth || undefined,
        phone: formData.phone || undefined,
        parent_name: formData.parent_name || undefined,
        parent_phone: formData.parent_phone || undefined,
        guardian_address: formData.guardian_address || undefined,
        center_id: user?.center_id || '',
        halaqah_id: formData.halaqah_id || undefined,
        halaqah_name: halaqahObj?.name || undefined,
        memorization_plan: (studentType === 'reviewing' ? 'plan_review' : selectedPlan) || undefined,
        student_type: studentType,
      } as Partial<StudentData>);
      setShowAddForm(false);
      setFormData(emptyForm);
      setSelectedPlan('');
      setStudentType('memorizing');
      await loadData();
    } catch (err) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      setError(errorObj.response?.data?.detail || 'Ø­Ø¯Ø« Ø®Ø·Ø£');
    } finally { setSubmitting(false); }
  };

  const handleDelete = async (id: string) => {
    if (!confirm('Ù‡Ù„ Ø£Ù†Øª Ù…ØªØ£ÙƒØ¯ Ù…Ù† Ø­Ø°Ù Ù‡Ø°Ø§ Ø§Ù„Ø·Ø§Ù„Ø¨ØŸ')) return;
    try {
      await studentsApi.delete(id);
      setSelectedStudent(null);
      await loadData();
    } catch { /* silent */ }
  };

  const handleEditSave = async () => {
    if (!selectedStudent) return;
    try {
      setSubmitting(true);
      await api.put(`/students/${selectedStudent.id}`, editForm);
      setEditMode(false);
      await loadData();
    } catch (err) {
      const errorObj = err as { response?: { data?: { detail?: string } } };
      alert(errorObj.response?.data?.detail || 'Ø­Ø¯Ø« Ø®Ø·Ø£');
    } finally { setSubmitting(false); }
  };

  const openStudent = (student: StudentData) => {
    setSelectedStudent(student);
    setEditMode(false);
    setEditForm({ ...student });
  };

  const filtered = useMemo(() =>
    students.filter(s =>
      s.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
      (s.halaqah_name || '').includes(searchTerm) ||
      (s.parent_name || '').includes(searchTerm)
    ),
    [students, searchTerm]
  );

  const stats = useMemo(() => ({
    memorizing: students.filter(s => s.student_type === 'memorizing').length,
    reviewing:  students.filter(s => s.student_type === 'reviewing').length,
    avgProgress: students.length > 0 ? Math.round(students.reduce((a, s) => a + (s.progress || 0), 0) / students.length) : 0,
    completed:  students.filter(s => s.progress >= 100).length,
  }), [students]);

  if (loading) return (
    <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
  );

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <div className="relative overflow-hidden rounded-3xl gradient-primary p-6 text-white shadow-lg">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">Ø¥Ø¯Ø§Ø±Ø© Ø§Ù„Ø·Ù„Ø§Ø¨</h1>
            <p className="text-white/70 text-sm">Ø¥Ø¬Ù…Ø§Ù„ÙŠ: {students.length} Ø·Ø§Ù„Ø¨</p>
          </div>
          <div className="w-14 h-14 bg-white/15 rounded-2xl flex items-center justify-center animate-float">
            <Users className="w-7 h-7 text-white" />
          </div>
        </div>
      </div>

      {/* Stats */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger">
        {[
          { icon: BookOpen,    val: stats.memorizing,   label: 'Ø·Ù„Ø§Ø¨ Ø§Ù„Ø­ÙØ¸',    bg: 'gradient-primary' },
          { icon: RefreshCw,   val: stats.reviewing,    label: 'Ø·Ù„Ø§Ø¨ Ø§Ù„Ù…Ø±Ø§Ø¬Ø¹Ø©', bg: 'gradient-gold' },
          { icon: TrendingUp,  val: `${stats.avgProgress}%`, label: 'Ù…ØªÙˆØ³Ø· Ø§Ù„ØªÙ‚Ø¯Ù…', bg: 'stat-card-teal' },
          { icon: CheckCircle2,val: stats.completed,    label: 'Ø£ØªÙ…ÙˆØ§ Ø§Ù„Ø­ÙØ¸',   bg: 'bg-[hsl(152,45%,38%)]' },
        ].map(s => (
          <div key={s.label} className={`rounded-2xl p-4 text-white ${s.bg} shadow-sm`}>
            <s.icon className="w-5 h-5 mb-2 opacity-80" />
            <p className="text-2xl font-black">{s.val}</p>
            <p className="text-white/75 text-xs mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Actions */}
      <div className="flex flex-col sm:flex-row gap-3">
        <button onClick={() => setShowAddForm(true)}
          className="gradient-primary text-white font-bold px-6 py-3 rounded-xl flex items-center gap-2 shadow-md hover:opacity-90 transition-all">
          <Plus className="w-5 h-5" /> ØªØ³Ø¬ÙŠÙ„ Ø·Ø§Ù„Ø¨ Ø¬Ø¯ÙŠØ¯
        </button>
        <div className="relative flex-1">
          <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
          <input
            placeholder="Ø§Ù„Ø¨Ø­Ø« Ø¨Ø§Ù„Ø§Ø³Ù… Ø£Ùˆ Ø§Ù„Ø­Ù„Ù‚Ø© Ø£Ùˆ Ø§Ø³Ù… ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±..."
            value={searchTerm}
            onChange={e => setSearchTerm(e.target.value)}
            className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] transition-all"
          />
        </div>
      </div>

      {/* Add Modal */}
      {showAddForm && (
        <div className="modal-overlay" onClick={() => setShowAddForm(false)}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between sticky top-0">
              <h3 className="text-lg font-black text-white flex items-center gap-2">
                <Plus className="w-5 h-5" /> ØªØ³Ø¬ÙŠÙ„ Ø·Ø§Ù„Ø¨ Ø¬Ø¯ÙŠØ¯
              </h3>
              <button onClick={() => setShowAddForm(false)} className="text-white/70 hover:text-white" aria-label="Ø¥ØºÙ„Ø§Ù‚ Ø§Ù„Ù†Ø§ÙØ°Ø©"><X className="w-5 h-5" aria-hidden="true" /></button>
            </div>
            <div className="p-5 space-y-5">
              {/* Student type */}
              <div className="grid grid-cols-2 gap-3">
                {(['memorizing', 'reviewing'] as const).map(type => (
                  <button key={type} onClick={() => { setStudentType(type); if (type === 'reviewing') setSelectedPlan('plan_review'); }}
                    className={`p-4 rounded-2xl border-2 text-center transition-all ${
                      studentType === type ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary-light))]' : 'border-[hsl(var(--border))]'}`}>
                    {type === 'memorizing' ? <BookOpen className="w-7 h-7 mx-auto mb-2 text-[hsl(var(--primary))]" /> : <RefreshCw className="w-7 h-7 mx-auto mb-2 text-[hsl(var(--primary))]" />}
                    <p className="font-bold text-sm">{type === 'memorizing' ? 'Ø·Ø§Ù„Ø¨ Ø­ÙØ¸' : 'Ø·Ø§Ù„Ø¨ Ù…Ø±Ø§Ø¬Ø¹Ø©'}</p>
                  </button>
                ))}
              </div>

              {/* Basic info */}
              <div className="grid grid-cols-2 gap-3">
                <div className="col-span-2">
                  <label className="text-sm font-semibold block mb-1">Ø§Ø³Ù… Ø§Ù„Ø·Ø§Ù„Ø¨ *</label>
                  <input placeholder="Ø§Ù„Ø§Ø³Ù… Ø§Ù„ÙƒØ§Ù…Ù„" value={formData.name}
                    onChange={e => setFormData({...formData, name: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…ÙŠÙ„Ø§Ø¯</label>
                  <input type="date" title="ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…ÙŠÙ„Ø§Ø¯" value={formData.date_of_birth}
                    onChange={e => setFormData({...formData, date_of_birth: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">Ù‡Ø§ØªÙ Ø§Ù„Ø·Ø§Ù„Ø¨</label>
                  <input placeholder="+223 XX XX XX" dir="ltr" value={formData.phone}
                    onChange={e => setFormData({...formData, phone: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">Ø§Ø³Ù… ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±</label>
                  <input placeholder="Ø§Ø³Ù… ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±" value={formData.parent_name}
                    onChange={e => setFormData({...formData, parent_name: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div>
                  <label className="text-sm font-semibold block mb-1">Ù‡Ø§ØªÙ ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±</label>
                  <input placeholder="+223 XX XX XX" dir="ltr" value={formData.parent_phone}
                    onChange={e => setFormData({...formData, parent_phone: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-semibold block mb-1">Ø¹Ù†ÙˆØ§Ù† ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±</label>
                  <input placeholder="Ø§Ù„Ù…Ø¯ÙŠÙ†Ø©ØŒ Ø§Ù„Ø­ÙŠØŒ Ø§Ù„Ø´Ø§Ø±Ø¹" value={formData.guardian_address}
                    onChange={e => setFormData({...formData, guardian_address: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] focus:outline-none focus:border-[hsl(var(--primary))]" />
                </div>
                <div className="col-span-2">
                  <label className="text-sm font-semibold block mb-1">Ø§Ù„Ø­Ù„Ù‚Ø©</label>
                  <select value={formData.halaqah_id} aria-label="Ø§Ù„Ø­Ù„Ù‚Ø©"
                    onChange={e => setFormData({...formData, halaqah_id: e.target.value})}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))]">
                    <option value="">Ø§Ø®ØªØ± Ø§Ù„Ø­Ù„Ù‚Ø©</option>
                    {halaqat.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                  </select>
                </div>
              </div>

              {/* Plan selection */}
              {studentType === 'memorizing' && (
                <div>
                  <label className="text-sm font-semibold block mb-2">Ø®Ø·Ø© Ø§Ù„Ø­ÙØ¸</label>
                  <div className="grid grid-cols-2 gap-2">
                    {memorizationPlans.map(plan => (
                      <button key={plan.id} onClick={() => setSelectedPlan(plan.id)}
                        className={`p-3 rounded-xl border-2 text-center transition-all ${
                          selectedPlan === plan.id ? 'border-[hsl(var(--primary))] bg-[hsl(var(--primary-light))]' : 'border-[hsl(var(--border))]'}`}>
                        <Clock className="w-5 h-5 mx-auto mb-1 text-[hsl(var(--primary))]" />
                        <p className="font-bold text-xs">{plan.name}</p>
                        <p className="text-[10px] text-[hsl(var(--muted-foreground))]">{plan.description}</p>
                      </button>
                    ))}
                  </div>
                </div>
              )}

              {error && (
                <div className="p-3 rounded-xl bg-red-50 text-red-600 text-sm flex items-center gap-2">
                  <AlertCircle className="w-4 h-4" />{error}
                </div>
              )}
              <div className="flex gap-3">
                <button onClick={handleSubmit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2">
                  {submitting ? <><LoadingSpinner size="sm" />Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø­ÙØ¸...</> : <><CheckCircle2 className="w-4 h-4" />ØªØ³Ø¬ÙŠÙ„ Ø§Ù„Ø·Ø§Ù„Ø¨</>}
                </button>
                <button onClick={() => setShowAddForm(false)}
                  className="px-5 py-3 rounded-xl border-2 border-[hsl(var(--border))] font-semibold hover:bg-[hsl(var(--muted))]">
                  Ø¥Ù„ØºØ§Ø¡
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Students List */}
      {filtered.length === 0 ? (
        <div className="text-center py-16 rounded-3xl bg-white border-2 border-dashed border-[hsl(var(--border))]">
          <Users className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-40" />
          <p className="text-[hsl(var(--muted-foreground))] font-medium">Ù„Ø§ ÙŠÙˆØ¬Ø¯ Ø·Ù„Ø§Ø¨ Ù…Ø·Ø§Ø¨Ù‚ÙˆÙ†</p>
        </div>
      ) : (
        <div className="space-y-3 stagger">
          {filtered.map(student => (
            <div key={student.id} className="bg-white rounded-2xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
              <div className="flex items-center gap-4 p-4">
                {/* Avatar */}
                <div className={`w-12 h-12 rounded-xl flex items-center justify-center text-white font-black text-lg shrink-0 ${student.student_type === 'reviewing' ? 'gradient-gold' : 'gradient-primary'}`}>
                  {student.name.charAt(0)}
                </div>

                {/* Info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 flex-wrap">
                    <h3 className="font-black text-[hsl(var(--foreground))]">{student.name}</h3>
                    <span className={`text-xs font-bold px-2 py-0.5 rounded-full ${
                      student.student_type === 'reviewing' ? 'bg-amber-100 text-amber-700' : 'bg-emerald-100 text-emerald-700'}`}>
                      {student.student_type === 'reviewing' ? 'Ù…Ø±Ø§Ø¬Ø¹Ø©' : 'Ø­ÙØ¸'}
                    </span>
                    {student.memorization_plan && (
                      <span className="text-xs font-bold px-2 py-0.5 rounded-full bg-[hsl(var(--primary-light))] text-[hsl(var(--primary))]">
                        {planLabels[student.memorization_plan]}
                      </span>
                    )}
                  </div>
                  <div className="flex gap-3 text-xs text-[hsl(var(--muted-foreground))] mt-1 flex-wrap">
                    {student.halaqah_name && <span className="flex items-center gap-1"><BookOpen className="w-3 h-3" />{student.halaqah_name}</span>}
                    {student.parent_name && <span className="flex items-center gap-1"><User className="w-3 h-3" />{student.parent_name}</span>}
                  </div>
                </div>

                {/* Progress */}
                <div className="text-center px-3 py-2 bg-[hsl(var(--muted))] rounded-xl shrink-0">
                  <p className="text-lg font-black text-[hsl(var(--primary))]">{student.progress || 0}%</p>
                  <p className="text-[10px] text-[hsl(var(--muted-foreground))]">ØªÙ‚Ø¯Ù…</p>
                </div>

                {/* Actions */}
                <div className="flex gap-1 shrink-0">
                  <button onClick={() => openStudent(student)} title="Ø¹Ø±Ø¶ Ø§Ù„Ù…Ù„Ù"
                    className="p-2 rounded-xl bg-[hsl(var(--primary-light))] text-[hsl(var(--primary))] hover:opacity-80 transition-all">
                    <Eye className="w-4 h-4" />
                  </button>
                  <Link to={`/analytics/${student.id}`} title="ØªØ­Ù„ÙŠÙ„ Ø§Ù„Ø£Ø¯Ø§Ø¡"
                    className="p-2 flex items-center justify-center rounded-xl bg-blue-50 text-blue-600 hover:opacity-80 transition-all">
                    <LineChart className="w-4 h-4" />
                  </Link>
                  <button onClick={() => handleDelete(student.id)} title="Ø­Ø°Ù Ø§Ù„Ø·Ø§Ù„Ø¨"
                    className="p-2 rounded-xl bg-red-50 text-red-500 hover:opacity-80 transition-all">
                    <Trash2 className="w-4 h-4" />
                  </button>
                  <button onClick={() => setExpandedId(expandedId === student.id ? null : student.id)} title="ØªÙˆØ³ÙŠØ¹/Ø·ÙŠ"
                    className="p-2 rounded-xl bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:opacity-80 transition-all">
                    {expandedId === student.id ? <ChevronUp className="w-4 h-4" /> : <ChevronDown className="w-4 h-4" />}
                  </button>
                </div>
              </div>

              {/* Expanded details */}
              {expandedId === student.id && (
                <div className="border-t border-[hsl(var(--border))] px-4 pb-4 pt-3 grid grid-cols-2 md:grid-cols-3 gap-3 text-sm animate-slide-in-up">
                  {[
                    { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…ÙŠÙ„Ø§Ø¯', val: student.date_of_birth, icon: Calendar },
                    { label: 'Ù‡Ø§ØªÙ Ø§Ù„Ø·Ø§Ù„Ø¨', val: student.phone, icon: Phone, dir: 'ltr' },
                    { label: 'Ù‡Ø§ØªÙ ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', val: student.parent_phone, icon: Phone, dir: 'ltr' },
                    { label: 'Ø¹Ù†ÙˆØ§Ù† ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', val: student.guardian_address, icon: MapPin },
                    { label: 'Ø§Ù„Ø³ÙˆØ±Ø© Ø§Ù„Ø­Ø§Ù„ÙŠØ©', val: student.current_surah ? `${student.current_surah} (${student.current_ayah})` : null, icon: BookOpen },
                    { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„ØªØ³Ø¬ÙŠÙ„', val: new Date(student.enrollment_date).toLocaleDateString('ar-SA'), icon: Calendar },
                  ].filter(item => item.val).map(item => (
                    <div key={item.label} className="p-2.5 rounded-xl bg-[hsl(var(--muted))]">
                      <div className="flex items-center gap-1.5 mb-1">
                        <item.icon className="w-3.5 h-3.5 text-[hsl(var(--primary))]" />
                        <span className="text-[hsl(var(--muted-foreground))] text-xs">{item.label}</span>
                      </div>
                      <p className="font-semibold text-[hsl(var(--foreground))]" dir={'dir' in item ? (item.dir as 'ltr' | 'rtl') : undefined}>{item.val}</p>
                    </div>
                  ))}
                  {/* progress bar */}
                  <div className="col-span-full">
                    <div className="flex justify-between text-xs mb-1">
                      <span className="text-[hsl(var(--muted-foreground))]">ØªÙ‚Ø¯Ù… Ø§Ù„Ø­ÙØ¸</span>
                      <span className="font-bold text-[hsl(var(--primary))]">{student.progress || 0}%</span>
                    </div>
                    <div className="h-2 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                      <div className="h-full gradient-primary rounded-full transition-all" style={{ width: `${student.progress || 0}%` }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Student Detail / Edit Modal */}
      {selectedStudent && (
        <div className="modal-overlay" onClick={() => setSelectedStudent(null)}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className={`p-5 rounded-t-3xl ${selectedStudent.student_type === 'reviewing' ? 'gradient-gold' : 'gradient-primary'}`}>
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-14 h-14 rounded-2xl bg-white/20 flex items-center justify-center text-white font-black text-2xl">
                    {selectedStudent.name.charAt(0)}
                  </div>
                  <div>
                    <h2 className="text-lg font-black text-white">{selectedStudent.name}</h2>
                    <p className="text-white/70 text-sm">
                      {selectedStudent.student_type === 'reviewing' ? 'Ø·Ø§Ù„Ø¨ Ù…Ø±Ø§Ø¬Ø¹Ø©' : 'Ø·Ø§Ù„Ø¨ Ø­ÙØ¸'}
                      {selectedStudent.memorization_plan && ` Â· ${planLabels[selectedStudent.memorization_plan]}`}
                    </p>
                  </div>
                </div>
                <button onClick={() => setSelectedStudent(null)} className="text-white/70 hover:text-white" aria-label="Ø¥ØºÙ„Ø§Ù‚ Ø§Ù„Ù†Ø§ÙØ°Ø©"><X className="w-5 h-5" aria-hidden="true" /></button>
              </div>
              <div className="flex gap-2 mt-4">
                <button onClick={() => setEditMode(!editMode)} title="ØªØ¨Ø¯ÙŠÙ„ ÙˆØ¶Ø¹ Ø§Ù„ØªØ¹Ø¯ÙŠÙ„"
                  className="flex-1 flex items-center justify-center gap-1 py-2 rounded-xl bg-white/15 hover:bg-white/25 text-white text-sm font-bold">
                  <Edit className="w-4 h-4" /> {editMode ? 'Ø¥Ù„ØºØ§Ø¡' : 'ØªØ¹Ø¯ÙŠÙ„'}
                </button>
                <button onClick={() => handleDelete(selectedStudent.id)} title="Ø­Ø°Ù Ø§Ù„Ø·Ø§Ù„Ø¨"
                  className="px-4 py-2 rounded-xl bg-red-500/30 hover:bg-red-500/50 text-white text-sm font-bold">
                  <Trash2 className="w-4 h-4" />
                </button>
              </div>
            </div>

            <div className="p-5">
              {/* Progress bar */}
              <div className="mb-4">
                <div className="flex justify-between text-sm mb-2">
                  <span className="font-semibold text-[hsl(var(--foreground))]">ØªÙ‚Ø¯Ù… Ø§Ù„Ø­ÙØ¸</span>
                  <span className="font-black text-[hsl(var(--primary))]">{selectedStudent.progress || 0}%</span>
                </div>
                <div className="h-3 bg-[hsl(var(--muted))] rounded-full overflow-hidden">
                  <div className="h-full gradient-primary rounded-full" style={{ width: `${selectedStudent.progress || 0}%` }} />
                </div>
                {selectedStudent.current_surah && (
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                    Ø§Ù„Ù…ÙˆÙ‚Ø¹ Ø§Ù„Ø­Ø§Ù„ÙŠ: {selectedStudent.current_surah} - Ø¢ÙŠØ© {selectedStudent.current_ayah}
                  </p>
                )}
              </div>

              {editMode ? (
                <div className="space-y-3">
                  {[
                    { label: 'Ø§Ù„Ø§Ø³Ù…', key: 'name' },
                    { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…ÙŠÙ„Ø§Ø¯', key: 'date_of_birth', type: 'date' },
                    { label: 'Ù‡Ø§ØªÙ Ø§Ù„Ø·Ø§Ù„Ø¨', key: 'phone', dir: 'ltr' },
                    { label: 'Ø§Ø³Ù… ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', key: 'parent_name' },
                    { label: 'Ù‡Ø§ØªÙ ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', key: 'parent_phone', dir: 'ltr' },
                    { label: 'Ø¹Ù†ÙˆØ§Ù† ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', key: 'guardian_address' },
                  ].map(f => (
                    <div key={f.key}>
                      <label className="text-sm font-semibold block mb-1">{f.label}</label>
                      <input type={f.type || 'text'} dir={'dir' in f ? (f.dir as 'ltr' | 'rtl') : undefined} title={f.label} placeholder={f.label}
                        value={(editForm[f.key as keyof typeof editForm] as string) || ''}
                        onChange={e => setEditForm({ ...editForm, [f.key]: e.target.value })}
                        className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                    </div>
                  ))}
                  <div>
                    <label className="text-sm font-semibold block mb-1">Ø§Ù„Ø­Ù„Ù‚Ø©</label>
                    <select value={editForm.halaqah_id || ''} aria-label="Ø§Ù„Ø­Ù„Ù‚Ø©"
                      onChange={e => {
                        const h = halaqat.find(h => h.id === e.target.value);
                        setEditForm({ ...editForm, halaqah_id: e.target.value, halaqah_name: h?.name || '' });
                      }}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">Ø§Ø®ØªØ± Ø§Ù„Ø­Ù„Ù‚Ø©</option>
                      {halaqat.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
                    </select>
                  </div>
                  <button onClick={handleEditSave} disabled={submitting}
                    className="w-full gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 disabled:opacity-60 flex items-center justify-center gap-2">
                    <Save className="w-4 h-4" /> {submitting ? 'Ø¬Ø§Ø±ÙŠ Ø§Ù„Ø­ÙØ¸...' : 'Ø­ÙØ¸ Ø§Ù„ØªØºÙŠÙŠØ±Ø§Øª'}
                  </button>
                </div>
              ) : (
                <div className="space-y-2 text-sm">
                  {[
                    { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„Ù…ÙŠÙ„Ø§Ø¯', val: selectedStudent.date_of_birth },
                    { label: 'Ù‡Ø§ØªÙ Ø§Ù„Ø·Ø§Ù„Ø¨', val: selectedStudent.phone, dir: 'ltr' },
                    { label: 'Ø§Ù„Ø­Ù„Ù‚Ø©', val: selectedStudent.halaqah_name },
                    { label: 'Ø§Ø³Ù… ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', val: selectedStudent.parent_name },
                    { label: 'Ù‡Ø§ØªÙ ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', val: selectedStudent.parent_phone, dir: 'ltr' },
                    { label: 'Ø¹Ù†ÙˆØ§Ù† ÙˆÙ„ÙŠ Ø§Ù„Ø£Ù…Ø±', val: selectedStudent.guardian_address },
                    { label: 'ØªØ§Ø±ÙŠØ® Ø§Ù„ØªØ³Ø¬ÙŠÙ„', val: new Date(selectedStudent.enrollment_date).toLocaleDateString('ar-SA') },
                  ].filter(item => item.val).map(item => (
                    <div key={item.label} className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                      <span className="text-[hsl(var(--muted-foreground))]">{item.label}</span>
                      <span className="font-bold text-[hsl(var(--foreground))]" dir={'dir' in item ? (item.dir as 'ltr' | 'rtl') : undefined}>{item.val}</span>
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

