/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Trophy, Plus, Search, Calendar, User, Star, Award,
  X, CheckCircle2, AlertCircle, Sparkles, BookOpen,
  Volume2, ShieldAlert, Printer,
} from 'lucide-react';
import api, { studentsApi } from '@/services/api';

interface Competition {
  id: string;
  title: string;
  date: string;
  categories: string[];
}

interface Contestant {
  id: string;
  competition_id: string;
  student_id: string;
  category: string;
  grades?: {
    hifdh_score: number;
    tajweed_score: number;
    voice_score: number;
  };
  total_score: number;
  student_name: string;
}

interface Student { id: string; name: string; }

export default function Competitions() {
  const { user } = useAuth();
  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [contestants, setContestants] = useState<Contestant[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  
  const [selectedComp, setSelectedComp] = useState<Competition | null>(null);
  const [showAddComp, setShowAddComp] = useState(false);
  const [showRegContestant, setShowRegContestant] = useState(false);
  const [showGradeModal, setShowGradeModal] = useState<Contestant | null>(null);
  const [printCert, setPrintCert] = useState<Contestant | null>(null);

  // Form states
  const [compForm, setCompForm] = useState({ title: '', date: '', categories_str: 'القرآن كاملاً، 15 جزءاً، 5 أجزاء، جزء عم' });
  const [regForm, setRegForm] = useState({ student_id: '', category: '' });
  const [gradeForm, setGradeForm] = useState({ hifdh_score: '', tajweed_score: '', voice_score: '', notes: '' });
  const [error, setError] = useState('');

  const loadInitialData = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const [compsResp, studsResp] = await Promise.all([
        api.get<Competition[]>('/competitions'),
        studentsApi.getAll(),
      ]);
      setCompetitions(compsResp.data);
      setStudents(studsResp as unknown as Student[]);
      if (compsResp.data.length > 0) {
        setSelectedComp(compsResp.data[0]);
      }
    } catch {
      setError('حدث خطأ أثناء تحميل بيانات المسابقات القرآنية.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadInitialData();
  }, [loadInitialData]);

  const loadContestants = useCallback(async (compId: string) => {
    try {
      const resp = await api.get<Contestant[]>(`/competitions/${compId}/contestants`);
      setContestants(resp.data);
    } catch { /* silent */ }
  }, []);

  useEffect(() => {
    if (selectedComp) {
      loadContestants(selectedComp.id);
    }
  }, [selectedComp, loadContestants]);

  const handleCreateComp = async () => {
    if (!compForm.title || !compForm.date) {
      setError('الرجاء كتابة عنوان المسابقة وتاريخها');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      const cats = compForm.categories_str.split('،').map(c => c.trim()).filter(Boolean);
      const resp = await api.post<Competition>('/competitions', {
        title: compForm.title,
        date: compForm.date,
        categories: cats
      });
      setCompetitions(prev => [resp.data, ...prev]);
      setSelectedComp(resp.data);
      setShowAddComp(false);
      setCompForm({ title: '', date: '', categories_str: 'القرآن كاملاً، 15 جزءاً، 5 أجزاء، جزء عم' });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'فشل حفظ المسابقة');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegisterContestant = async () => {
    if (!selectedComp || !regForm.student_id || !regForm.category) {
      setError('الرجاء اختيار الطالب والفئة المشارك بها');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      await api.post(`/competitions/${selectedComp.id}/register`, regForm);
      await loadContestants(selectedComp.id);
      setShowRegContestant(false);
      setRegForm({ student_id: '', category: '' });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'فشل تسجيل المتسابق');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGradeSubmit = async () => {
    if (!showGradeModal) return;
    const h = Number(gradeForm.hifdh_score);
    const t = Number(gradeForm.tajweed_score);
    const v = Number(gradeForm.voice_score);

    if (isNaN(h) || h < 0 || h > 70) { setError('درجة الحفظ يجب أن تكون بين 0 و 70'); return; }
    if (isNaN(t) || t < 0 || t > 20) { setError('درجة التجويد يجب أن تكون بين 0 و 20'); return; }
    if (isNaN(v) || v < 0 || v > 10) { setError('درجة حسن الصوت يجب أن تكون بين 0 و 10'); return; }

    try {
      setSubmitting(true);
      setError('');
      await api.post(`/competitions/contestants/${showGradeModal.id}/grade`, {
        hifdh_score: h,
        tajweed_score: t,
        voice_score: v
      });
      if (selectedComp) await loadContestants(selectedComp.id);
      setShowGradeModal(null);
      setGradeForm({ hifdh_score: '', tajweed_score: '', voice_score: '', notes: '' });
    } catch (err: any) {
      setError(err.response?.data?.detail || 'فشل حفظ الدرجات ورصدها');
    } finally {
      setSubmitting(false);
    }
  };

  const openGradeModal = (con: Contestant) => {
    setShowGradeModal(con);
    setGradeForm({
      hifdh_score: con.grades?.hifdh_score?.toString() || '',
      tajweed_score: con.grades?.tajweed_score?.toString() || '',
      voice_score: con.grades?.voice_score?.toString() || '',
      notes: '',
    });
  };

  const triggerPrint = () => {
    window.print();
  };

  const isEditable = user?.role === 'center_manager' || user?.role === 'admin';

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <LoadingSpinner size="lg" />
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">
      
      {/* Printable Certificate Template (Hidden on screen, shown in print) */}
      {printCert && (
        <div className="hidden print:block fixed inset-0 bg-white z-[9999] p-8 text-black" dir="rtl">
          <div className="border-[12px] border-double border-[hsl(152,45%,38%)] p-8 h-[95vh] flex flex-col justify-between items-center text-center rounded-3xl relative">
            
            {/* Elegant Corner Decorations */}
            <div className="absolute top-4 right-4 text-4xl text-[hsl(152,45%,38%)]">❖</div>
            <div className="absolute top-4 left-4 text-4xl text-[hsl(152,45%,38%)]">❖</div>
            <div className="absolute bottom-4 right-4 text-4xl text-[hsl(152,45%,38%)]">❖</div>
            <div className="absolute bottom-4 left-4 text-4xl text-[hsl(152,45%,38%)]">❖</div>

            <div>
              <div className="text-sm font-bold text-[hsl(152,45%,38%)] mb-1">وزارة الشؤون الإسلامية والأوقاف</div>
              <h4 className="text-xs font-semibold mb-6">مِشكاة لإدارة مراكز تحفيظ القرآن الكريم المعتمدة</h4>
              <div className="w-20 h-20 mx-auto mb-4 border-2 border-[hsl(152,45%,38%)] rounded-full flex items-center justify-center font-black text-[hsl(152,45%,38%)] text-xl">
                مِشكاة
              </div>
            </div>

            <div className="space-y-6">
              <h1 className="text-4xl font-extrabold text-[hsl(152,45%,38%)] font-serif tracking-wide">شـهادة تـقدير وتـكريم</h1>
              <p className="text-base font-medium max-w-xl mx-auto leading-relaxed">
                يسر إدارة مركز تحفيظ القرآن الكريم بكل فخر واعتزاز أن تمنح هذه الشهادة للطالب المتميز:
              </p>
              <h2 className="text-3xl font-black text-amber-600 underline decoration-double decoration-1 my-4">{printCert.student_name}</h2>
              <p className="text-sm leading-loose max-w-lg mx-auto">
                وذلك تقديراً لأدائه الاستثنائي وحصوله على فئة <strong className="text-emerald-700">"{printCert.category}"</strong> في 
                <br />
                <strong>{selectedComp?.title}</strong>
                <br />
                بدرجة تفوق إجمالية قدرها <strong className="text-emerald-700">{printCert.total_score} / 100</strong>
              </p>
              <p className="text-xs text-gray-500 italic">"خيركم من تعلم القرآن وعلمه"</p>
            </div>

            <div className="w-full grid grid-cols-2 gap-20 px-12 pt-8 border-t border-gray-100">
              <div className="text-right">
                <span className="text-xs block text-gray-500">توقيع الموجه العام</span>
                <div className="h-10"></div>
                <span className="text-sm font-bold">عـبد المالك سيسي</span>
              </div>
              <div className="text-left">
                <span className="text-xs block text-gray-500">خاتم وتوقيع المركز</span>
                <div className="h-10"></div>
                <span className="text-sm font-semibold">توقيع المشرف العام</span>
              </div>
            </div>

            <div className="text-[10px] text-gray-400">
              حرر بتاريخ: {selectedComp?.date} · النظام محمي بموجب حقوق النشر لـ Abdoul Malick Cisse © 2026
            </div>
          </div>
        </div>
      )}

      {/* Screen Interface */}
      <div className="print:hidden space-y-6">

        {/* Hero */}
        <div className="relative overflow-hidden rounded-3xl gradient-primary p-6 text-white shadow-lg">
          <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5 pointer-events-none" />
          <div className="relative z-10 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-black mb-1">المسابقات القرآنية السنوية</h1>
              <p className="text-white/70 text-sm">تقييم مستويات الحفظ والأداء والتجويد مع الرصد الفوري لعلامات المحكمين</p>
            </div>
            <div className="w-14 h-14 bg-white/15 rounded-2xl flex items-center justify-center animate-float">
              <Trophy className="w-7 h-7 text-white" />
            </div>
          </div>
        </div>

        {/* Competitions Selector Bar */}
        <div className="flex flex-col md:flex-row gap-4 items-start md:items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="text-sm font-bold">المسابقة الحالية:</span>
            <select
              value={selectedComp?.id || ''}
              onChange={e => setSelectedComp(competitions.find(c => c.id === e.target.value) || null)}
              className="h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm font-bold"
            >
              {competitions.length === 0 && <option value="">لا توجد مسابقات مسجلة</option>}
              {competitions.map(c => <option key={c.id} value={c.id}>{c.title}</option>)}
            </select>
          </div>

          <div className="flex gap-2 w-full md:w-auto">
            {isEditable && (
              <button
                onClick={() => setShowAddComp(true)}
                className="gradient-primary text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 shadow-sm text-sm"
              >
                <Plus className="w-4.5 h-4.5" /> إضافة مسابقة جديدة
              </button>
            )}
            {selectedComp && (
              <button
                onClick={() => setShowRegContestant(true)}
                className="gradient-gold text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 shadow-sm text-sm"
              >
                <Plus className="w-4.5 h-4.5" /> تسجيل متسابق
              </button>
            )}
          </div>
        </div>

        {/* Comp Add Modal */}
        {showAddComp && (
          <div className="modal-overlay" onClick={() => setShowAddComp(false)}>
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
              <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
                <h3 className="text-lg font-black flex items-center gap-2">
                  <Trophy className="w-5 h-5 text-[hsl(var(--gold))]" /> إضافة مسابقة سنوية جديدة
                </h3>
                <button onClick={() => setShowAddComp(false)} className="text-white/75 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
                <div>
                  <label className="text-xs font-bold block mb-1">عنوان المسابقة *</label>
                  <input
                    placeholder="مثال: المسابقة الرمضانية الكبرى لحفظ كتاب الله لعام 2026"
                    value={compForm.title}
                    onChange={e => setCompForm({ ...compForm, title: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold block mb-1">تاريخ الانعقاد *</label>
                  <input
                    type="date"
                    value={compForm.date}
                    onChange={e => setCompForm({ ...compForm, date: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm"
                  />
                </div>
                <div>
                  <label className="text-xs font-bold block mb-1">الفئات القرآنية المتاحة (افصل بينها بـ علامة "،")</label>
                  <input
                    value={compForm.categories_str}
                    onChange={e => setCompForm({ ...compForm, categories_str: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm"
                  />
                </div>
                <div className="flex gap-2 pt-3 border-t">
                  <button onClick={handleCreateComp} disabled={submitting} className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                    {submitting ? 'جاري الحفظ...' : 'حفظ المسابقة'}
                  </button>
                  <button onClick={() => setShowAddComp(false)} className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Contestant Reg Modal */}
        {showRegContestant && selectedComp && (
          <div className="modal-overlay" onClick={() => setShowRegContestant(false)}>
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
              <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
                <h3 className="text-lg font-black flex items-center gap-2">
                  <Award className="w-5 h-5 text-[hsl(var(--gold))]" /> تسجيل متسابق جديد
                </h3>
                <button onClick={() => setShowRegContestant(false)} className="text-white/75 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
                <div>
                  <label className="text-xs font-bold block mb-1">اختر الطالب المتسابق *</label>
                  <select
                    value={regForm.student_id}
                    onChange={e => setRegForm({ ...regForm, student_id: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm bg-white"
                  >
                    <option value="">اختر الطالب</option>
                    {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                  </select>
                </div>
                <div>
                  <label className="text-xs font-bold block mb-1">اختر فئة المشاركة *</label>
                  <select
                    value={regForm.category}
                    onChange={e => setRegForm({ ...regForm, category: e.target.value })}
                    className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm bg-white"
                  >
                    <option value="">اختر الفئة</option>
                    {selectedComp.categories.map(cat => <option key={cat} value={cat}>{cat}</option>)}
                  </select>
                </div>
                <div className="flex gap-2 pt-3 border-t">
                  <button onClick={handleRegisterContestant} disabled={submitting} className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                    {submitting ? 'جاري التسجيل...' : 'تأكيد تسجيل المتسابق'}
                  </button>
                  <button onClick={() => setShowRegContestant(false)} className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Contestants grading modal */}
        {showGradeModal && (
          <div className="modal-overlay" onClick={() => setShowGradeModal(null)}>
            <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
              <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
                <h3 className="text-lg font-black flex items-center gap-2">
                  <Star className="w-5 h-5 text-[hsl(var(--gold))]" /> رصد درجات التقييم والتحكيم
                </h3>
                <button onClick={() => setShowGradeModal(null)} className="text-white/75 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                <div className="p-3 bg-emerald-50 rounded-2xl border border-emerald-100 flex items-center gap-2.5">
                  <User className="w-5 h-5 text-emerald-700" />
                  <div>
                    <h4 className="font-bold text-sm text-emerald-800">{showGradeModal.student_name}</h4>
                    <p className="text-[10px] text-emerald-600 font-semibold">المشارك في فئة: {showGradeModal.category}</p>
                  </div>
                </div>
                {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
                <div className="grid grid-cols-3 gap-2">
                  <div>
                    <label className="text-xs font-bold block mb-1 text-center">درجة الحفظ (70) *</label>
                    <input
                      placeholder="0 - 70"
                      value={gradeForm.hifdh_score}
                      onChange={e => setGradeForm({ ...gradeForm, hifdh_score: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-center text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold block mb-1 text-center">أحكام التجويد (20) *</label>
                    <input
                      placeholder="0 - 20"
                      value={gradeForm.tajweed_score}
                      onChange={e => setGradeForm({ ...gradeForm, tajweed_score: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-center text-sm font-bold"
                    />
                  </div>
                  <div>
                    <label className="text-xs font-bold block mb-1 text-center">جمال الصوت (10) *</label>
                    <input
                      placeholder="0 - 10"
                      value={gradeForm.voice_score}
                      onChange={e => setGradeForm({ ...gradeForm, voice_score: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-center text-sm font-bold"
                    />
                  </div>
                </div>
                <div>
                  <label className="text-xs font-bold block mb-1">ملاحظات التحكيم</label>
                  <textarea
                    placeholder="ملاحظات أداء التلاوة والتجويد..."
                    value={gradeForm.notes}
                    onChange={e => setGradeForm({ ...gradeForm, notes: e.target.value })}
                    className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm min-h-[80px]"
                  />
                </div>
                <div className="flex gap-2 pt-3 border-t">
                  <button onClick={handleGradeSubmit} disabled={submitting} className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                    {submitting ? 'جاري الرصد...' : 'تأكيد ورصد الدرجات'}
                  </button>
                  <button onClick={() => setShowGradeModal(null)} className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Leaderboard layout of Contestants */}
        <div className="bg-white rounded-3xl border border-[hsl(var(--border))] shadow-sm overflow-hidden">
          <div className="p-5 border-b border-[hsl(var(--border))] flex items-center justify-between">
            <h3 className="font-black text-base flex items-center gap-2">
              <Trophy className="w-5 h-5 text-amber-500 animate-float" />
              لوحة صدارة المتسابقين والنتائج اللحظية
            </h3>
            <span className="badge-gold text-xs px-2.5 py-1 rounded-full font-bold">{contestants.length} متسابق</span>
          </div>

          {contestants.length === 0 ? (
            <div className="text-center py-16">
              <Award className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
              <p className="text-[hsl(var(--muted-foreground))] font-semibold">لم يتم تسجيل متسابقين بعد في هذه المسابقة</p>
            </div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="bg-[hsl(var(--muted))] text-xs font-bold text-[hsl(var(--muted-foreground))]">
                    <th className="p-4">الترتيب</th>
                    <th className="p-4">اسم الطالب</th>
                    <th className="p-4">الفئة المشارك بها</th>
                    <th className="p-4 text-center">درجة الحفظ (70)</th>
                    <th className="p-4 text-center">التجويد (20)</th>
                    <th className="p-4 text-center">الأداء وحسن الصوت (10)</th>
                    <th className="p-4 text-center font-bold text-[hsl(var(--foreground))]">المجموع (100)</th>
                    <th className="p-4 text-center">الإجراءات</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))] text-sm">
                  {contestants.map((con, idx) => {
                    const isRanked = con.grades;
                    return (
                      <tr key={con.id} className="hover:bg-[hsl(var(--muted))/30] transition-colors">
                        <td className="p-4 font-black">
                          {idx === 0 && con.total_score > 0 ? <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-lg text-xs">🥇 الأول</span> : ''}
                          {idx === 1 && con.total_score > 0 ? <span className="bg-slate-100 text-slate-800 px-2 py-0.5 rounded-lg text-xs">🥈 الثاني</span> : ''}
                          {idx === 2 && con.total_score > 0 ? <span className="bg-orange-100 text-orange-800 px-2 py-0.5 rounded-lg text-xs">🥉 الثالث</span> : ''}
                          {idx > 2 || con.total_score === 0 ? <span className="text-gray-400 font-normal">#{idx + 1}</span> : ''}
                        </td>
                        <td className="p-4 font-bold text-[hsl(var(--foreground))]">{con.student_name}</td>
                        <td className="p-4">{con.category}</td>
                        <td className="p-4 text-center font-mono font-semibold">{con.grades?.hifdh_score ?? '-'}</td>
                        <td className="p-4 text-center font-mono font-semibold">{con.grades?.tajweed_score ?? '-'}</td>
                        <td className="p-4 text-center font-mono font-semibold">{con.grades?.voice_score ?? '-'}</td>
                        <td className="p-4 text-center font-mono font-black text-[hsl(var(--primary))] text-base">
                          {con.total_score > 0 ? `${con.total_score} درجة` : 'لم يرصد بعد'}
                        </td>
                        <td className="p-4 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <button
                              onClick={() => openGradeModal(con)}
                              className="px-3 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold text-xs transition-colors flex items-center gap-1"
                            >
                              <Star className="w-3.5 h-3.5" />
                              {con.grades ? 'تعديل الدرجة' : 'رصد الدرجة'}
                            </button>
                            {con.total_score > 0 && (
                              <button
                                onClick={() => { setPrintCert(con); setTimeout(triggerPrint, 250); }}
                                className="px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-xs transition-colors flex items-center gap-1"
                              >
                                <Printer className="w-3.5 h-3.5" />
                                شهادة تقدير
                              </button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </div>

      </div>
    </div>
  );
}
