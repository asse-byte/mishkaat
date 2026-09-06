/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
/**
 * المسابقات القرآنية.
 *
 * ثلاثة أشياء تحكم هذه الشاشة، وكانت الشاشةُ السابقة تخالفها كلَّها:
 *
 *   1. الفروع منفصلة. لكل فرعٍ جدولُه وترتيبُه من واحد. والجدول الواحد الذي
 *      يرتّب الجميع معاً يضع حافظ جزء عمّ في ذيل قائمةٍ صدرُها حفظةُ القرآن
 *      كاملاً، وهي مقارنة لا معنى لها.
 *
 *   2. التحكيم لجنة. كل محكّم يرصد درجتَه وحدها، وتُعرض درجاتُ اللجنة كلِّها
 *      ومتوسّطُها. وكانت درجةً واحدة يمحوها آخرُ من يفتح الشاشة.
 *
 *   3. المعتمَدة مجمَّدة. بعد اعتماد المدير لا زرَّ رصدٍ ولا تسجيل، وتُقرأ
 *      نتائجُ السنوات الماضية من الأرشيف ولا تُمسّ.
 */
import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Trophy, Plus, User, Star, Award, Lock, Archive,
  CheckCircle2, Printer, Gavel, ShieldCheck, Calendar,
} from 'lucide-react';
import api, { studentsApi, teachersApi } from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';
import MishkaatMark from '@/components/ui/MishkaatMark';

type CompStatus = 'draft' | 'active' | 'grading' | 'approved' | 'archived';

interface Judge { teacher_id: string; teacher_name?: string }

interface Competition {
  id: string;
  title: string;
  date: string;
  year: number;
  status: CompStatus;
  branches: string[];
  categories: string[];
  judges: Judge[];
  approved_at?: string | null;
  approved_by?: string | null;
  notes?: string;
}

interface JudgeScore {
  judge_teacher_id: string;
  judge_name?: string;
  hifdh_score: number;
  tajweed_score: number;
  voice_score: number;
  total: number;
  graded_at: string;
}

interface Contestant {
  id: string;
  competition_id: string;
  student_id: string;
  category: string;
  grades?: { hifdh_score: number; tajweed_score: number; voice_score: number } | null;
  judge_scores: JudgeScore[];
  judges_count: number;
  total_score: number;
  rank_in_branch?: number;
  student_name: string;
  halaqah_name?: string;
}

interface BranchBlock { branch: string; contestants: Contestant[]; count: number; legacy?: boolean }
interface Student { id: string; name: string }
interface TeacherLite { id: string; name: string }

const RANK_BADGE = ['🥇 الأول', '🥈 الثاني', '🥉 الثالث'];
const FROZEN: CompStatus[] = ['approved', 'archived'];

const STATUS_LABEL: Record<CompStatus, string> = {
  draft: 'مسوّدة',
  active: 'مفتوحة للتسجيل',
  grading: 'قيد التحكيم',
  approved: 'معتمَدة',
  archived: 'في الأرشيف',
};

export default function Competitions() {
  const { user } = useAuth();
  const isManager = user?.role === 'center_manager' || user?.role === 'admin' || user?.role === 'super_admin';
  const isTeacher = user?.role === 'teacher';

  const [competitions, setCompetitions] = useState<Competition[]>([]);
  const [blocks, setBlocks] = useState<BranchBlock[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [teachers, setTeachers] = useState<TeacherLite[]>([]);
  const [branchOptions, setBranchOptions] = useState<string[]>([]);
  const [years, setYears] = useState<number[]>([]);
  const [yearFilter, setYearFilter] = useState<string>('');
  /** سجلّ المحفّظ — لا يحمله حساب المستخدم، فيُقرأ من الخادم لنعرف أيّ درجةٍ درجتي */
  const [myTeacherId, setMyTeacherId] = useState<string>('');

  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [selectedComp, setSelectedComp] = useState<Competition | null>(null);
  const [showAddComp, setShowAddComp] = useState(false);
  const [showRegContestant, setShowRegContestant] = useState(false);
  const [showGradeModal, setShowGradeModal] = useState<Contestant | null>(null);
  const [printCert, setPrintCert] = useState<Contestant | null>(null);

  const [compForm, setCompForm] = useState<{
    title: string; date: string; branches: string[]; judges: string[];
  }>({ title: '', date: '', branches: [], judges: [] });
  const [regForm, setRegForm] = useState({ student_id: '', category: '' });
  const [gradeForm, setGradeForm] = useState({ hifdh_score: '', tajweed_score: '', voice_score: '' });

  const frozen = !!selectedComp && FROZEN.includes(selectedComp.status);
  // الشيخ لا يرصد إلا إن كان في لجنة هذه المسابقة — والخادم يمنعه أيضاً
  const amJudge = !!selectedComp && isTeacher && !!myTeacherId &&
    selectedComp.judges.some(j => j.teacher_id === myTeacherId);
  const canGrade = isTeacher && !frozen && amJudge;

  const loadCompetitions = useCallback(async (year?: string) => {
    const resp = await api.get<Competition[]>('/competitions', {
      params: year ? { year: Number(year) } : undefined,
    });
    setCompetitions(resp.data);
    setSelectedComp(prev => {
      const still = prev && resp.data.find(c => c.id === prev.id);
      return still || resp.data[0] || null;
    });
  }, []);

  useEffect(() => {
    (async () => {
      try {
        setLoading(true);
        setError('');
        const [, yearsResp, branchesResp] = await Promise.all([
          loadCompetitions(),
          api.get<{ years: number[] }>('/competitions/years'),
          api.get<{ branches: string[] }>('/competitions/branches'),
        ]);
        setYears(yearsResp.data.years || []);
        setBranchOptions(branchesResp.data.branches || []);
        setCompForm(f => ({ ...f, branches: branchesResp.data.branches || [] }));
        if (isManager) {
          const [studs, teachs] = await Promise.all([studentsApi.getAll(), teachersApi.getAll()]);
          setStudents(studs as unknown as Student[]);
          setTeachers((teachs as unknown as TeacherLite[]) || []);
        } else if (isTeacher) {
          const mine = await api.get<{ teacher_id: string | null }>('/competitions/my-role');
          setMyTeacherId(mine.data.teacher_id || '');
        }
      } catch {
        setError('تعذّر تحميل المسابقات.');
      } finally {
        setLoading(false);
      }
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const loadContestants = useCallback(async (compId: string) => {
    try {
      const resp = await api.get<{ branches: BranchBlock[] }>(`/competitions/${compId}/contestants`);
      setBlocks(resp.data.branches || []);
    } catch (err: any) {
      setBlocks([]);
      setError(err.response?.data?.detail || 'تعذّر تحميل نتائج المسابقة.');
    }
  }, []);

  useEffect(() => {
    if (selectedComp) loadContestants(selectedComp.id);
    else setBlocks([]);
  }, [selectedComp, loadContestants]);

  const handleYearChange = async (y: string) => {
    setYearFilter(y);
    setLoading(true);
    try { await loadCompetitions(y); } finally { setLoading(false); }
  };

  const handleCreateComp = async () => {
    if (!compForm.title || !compForm.date) {
      setError('اكتب عنوان المسابقة وتاريخها');
      return;
    }
    if (compForm.branches.length === 0) {
      setError('اختر فرعاً واحداً على الأقل');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      const resp = await api.post<Competition>('/competitions', {
        title: compForm.title,
        date: compForm.date,
        branches: compForm.branches,
        judges: compForm.judges.map(id => ({ teacher_id: id })),
      });
      setCompetitions(prev => [resp.data, ...prev]);
      setSelectedComp(resp.data);
      setShowAddComp(false);
      setCompForm({ title: '', date: '', branches: branchOptions, judges: [] });
      setNotice('أُنشئت المسابقة وعُيّنت لجنتها.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'تعذّر حفظ المسابقة');
    } finally {
      setSubmitting(false);
    }
  };

  const handleApprove = async () => {
    if (!selectedComp) return;
    if (!window.confirm(
      'اعتماد النتائج يُجمّدها نهائياً: لا رصدَ بعده ولا تسجيلَ ولا تعديل. هل تعتمدها؟'
    )) return;
    try {
      setSubmitting(true);
      setError('');
      const resp = await api.post<{ ungraded_contestants: number }>(
        `/competitions/${selectedComp.id}/approve`);
      const left = resp.data.ungraded_contestants;
      setNotice(left > 0
        ? `اعتُمدت النتائج وجُمّدت — مع تنبيه: ${left} متسابقاً بلا درجة.`
        : 'اعتُمدت النتائج وجُمّدت.');
      await loadCompetitions(yearFilter);
      await loadContestants(selectedComp.id);
      setSelectedComp(c => (c ? { ...c, status: 'approved' } : c));
    } catch (err: any) {
      setError(err.response?.data?.detail || 'تعذّر اعتماد النتائج');
    } finally {
      setSubmitting(false);
    }
  };

  const handleArchive = async () => {
    if (!selectedComp) return;
    try {
      setSubmitting(true);
      await api.post(`/competitions/${selectedComp.id}/archive`);
      setNotice('نُقلت المسابقة إلى الأرشيف.');
      setSelectedComp(c => (c ? { ...c, status: 'archived' } : c));
      await loadCompetitions(yearFilter);
    } catch (err: any) {
      setError(err.response?.data?.detail || 'تعذّرت الأرشفة');
    } finally {
      setSubmitting(false);
    }
  };

  const handleRegisterContestant = async () => {
    if (!selectedComp || !regForm.student_id || !regForm.category) {
      setError('اختر الطالب والفرع');
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
      setError(err.response?.data?.detail || 'تعذّر تسجيل المتسابق');
    } finally {
      setSubmitting(false);
    }
  };

  const handleGradeSubmit = async () => {
    if (!showGradeModal) return;
    const h = Number(gradeForm.hifdh_score);
    const t = Number(gradeForm.tajweed_score);
    const v = Number(gradeForm.voice_score);
    if (isNaN(h) || h < 0 || h > 70) { setError('درجة الحفظ بين 0 و 70'); return; }
    if (isNaN(t) || t < 0 || t > 20) { setError('درجة التجويد بين 0 و 20'); return; }
    if (isNaN(v) || v < 0 || v > 10) { setError('درجة الصوت بين 0 و 10'); return; }
    try {
      setSubmitting(true);
      setError('');
      await api.post(`/competitions/contestants/${showGradeModal.id}/grade`, {
        hifdh_score: h, tajweed_score: t, voice_score: v,
      });
      if (selectedComp) {
        await loadContestants(selectedComp.id);
        if (selectedComp.status === 'active') {
          setSelectedComp({ ...selectedComp, status: 'grading' });
        }
      }
      setShowGradeModal(null);
      setGradeForm({ hifdh_score: '', tajweed_score: '', voice_score: '' });
      setNotice('رُصدت درجتُك. الدرجة النهائية متوسّط درجات اللجنة.');
    } catch (err: any) {
      setError(err.response?.data?.detail || 'تعذّر رصد الدرجة');
    } finally {
      setSubmitting(false);
    }
  };

  const openGradeModal = (con: Contestant) => {
    // درجتي أنا إن كنت رصدتُها من قبل، لا متوسّط اللجنة
    const mine = con.judge_scores.find(s => s.judge_teacher_id === myTeacherId);
    setShowGradeModal(con);
    setError('');
    setGradeForm({
      hifdh_score: mine ? String(mine.hifdh_score) : '',
      tajweed_score: mine ? String(mine.tajweed_score) : '',
      voice_score: mine ? String(mine.voice_score) : '',
    });
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>;
  }

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">

      {/* شهادة التقدير — تُطبع على ورق أبيض، فألوانها قيم ثابتة لا رموز النظام
          (الرموز تنقلب في الوضع الليلي فتُطبع فاتحاً على أبيض). */}
      {printCert && (
        <div className="hidden print:block fixed inset-0 bg-white z-[9999] p-8 text-[#151A24]" dir="rtl">
          <div className="border-[12px] border-double border-[#1B233C] p-8 h-[95vh] flex flex-col justify-between items-center text-center rounded-[var(--radius-lg)] relative">
            <div className="absolute top-4 right-4 text-4xl text-[#B0801F]">❖</div>
            <div className="absolute top-4 left-4 text-4xl text-[#B0801F]">❖</div>
            <div className="absolute bottom-4 right-4 text-4xl text-[#B0801F]">❖</div>
            <div className="absolute bottom-4 left-4 text-4xl text-[#B0801F]">❖</div>
            <div>
              <h4 className="text-xs font-semibold mb-6">المشكاة لإدارة دور ومراكز تحفيظ القرآن الكريم</h4>
              <div className="w-20 h-20 mx-auto mb-4 border-2 border-[#1B233C] rounded-full flex items-center justify-center text-[#B0801F]">
                <MishkaatMark className="w-11 h-11" title="المشكاة" />
              </div>
            </div>
            <div className="space-y-6">
              <h1 className="text-4xl font-extrabold text-[#1B233C] font-serif tracking-wide">شـهادة تـقدير وتـكريم</h1>
              <p className="text-base font-medium max-w-xl mx-auto leading-relaxed">
                يسرّ إدارة مركز تحفيظ القرآن الكريم أن تمنح هذه الشهادة للطالب:
              </p>
              <h2 className="text-3xl font-bold text-[#B0801F] underline decoration-double decoration-1 my-4">{printCert.student_name}</h2>
              <p className="text-sm leading-loose max-w-lg mx-auto">
                لحصوله على المركز <strong className="text-[#1B233C]">{printCert.rank_in_branch}</strong> في فرع
                {' '}<strong className="text-[#1B233C]">«{printCert.category}»</strong> من
                <br />
                <strong>{selectedComp?.title}</strong>
                <br />
                بمجموع <strong className="text-[#1B233C]">{printCert.total_score} / 100</strong>
                {printCert.judges_count > 0 && (
                  <span className="text-xs"> (متوسّط درجات {printCert.judges_count} من المحكّمين)</span>
                )}
              </p>
              <p className="text-xs text-[#5B6474] italic">«خيركم من تعلّم القرآن وعلّمه»</p>
            </div>
            <div className="w-full grid grid-cols-2 gap-20 px-12 pt-8 border-t border-[#D8DCE4]">
              <div className="text-right">
                <span className="text-xs block text-[#5B6474]">رئيس لجنة التحكيم</span>
                <div className="h-10" />
                <span className="text-sm font-bold">{selectedComp?.judges[0]?.teacher_name || '—'}</span>
              </div>
              <div className="text-left">
                <span className="text-xs block text-[#5B6474]">مدير المركز</span>
                <div className="h-10" />
                <span className="text-sm font-semibold">{selectedComp?.approved_by || '—'}</span>
              </div>
            </div>
            <div className="text-[10px] text-[#767E8C]">
              حُرّر بتاريخ: {selectedComp?.date}
            </div>
          </div>
        </div>
      )}

      <div className="print:hidden space-y-6">
        <PageHeader
          title="المسابقات القرآنية"
          subtitle="نتائج كل فرع على حدة، برصد لجنة التحكيم واعتماد إدارة المركز"
        />

        {error && (
          <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold border border-red-200">
            {error}
          </div>
        )}
        {notice && (
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-sm font-semibold border border-emerald-200 flex items-center justify-between">
            <span>{notice}</span>
            <button onClick={() => setNotice('')} className="text-xs">إخفاء</button>
          </div>
        )}

        {/* شريط الاختيار: المسابقة، والسنة (الأرشيف)، والإجراءات */}
        <div className="flex flex-col lg:flex-row gap-3 lg:items-center justify-between">
          <div className="flex flex-wrap items-center gap-2 min-w-0">
            <select
              value={selectedComp?.id || ''}
              onChange={e => setSelectedComp(competitions.find(c => c.id === e.target.value) || null)}
              className="h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white text-sm font-bold max-w-full"
            >
              {competitions.length === 0 && <option value="">لا توجد مسابقات</option>}
              {competitions.map(c => (
                <option key={c.id} value={c.id}>{c.title} — {c.year}</option>
              ))}
            </select>

            <select
              value={yearFilter}
              onChange={e => handleYearChange(e.target.value)}
              className="h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white text-sm font-semibold"
              aria-label="سنة المسابقات"
            >
              <option value="">كل السنوات</option>
              {years.map(y => <option key={y} value={y}>{y}</option>)}
            </select>

            {selectedComp && (
              <span className={`text-xs font-bold px-3 py-1.5 rounded-full inline-flex items-center gap-1.5 ${
                frozen ? 'bg-slate-100 text-slate-700'
                  : selectedComp.status === 'grading' ? 'bg-amber-100 text-amber-800'
                  : 'bg-emerald-100 text-emerald-800'}`}>
                {frozen ? <Lock className="w-3.5 h-3.5" /> : <Calendar className="w-3.5 h-3.5" />}
                {STATUS_LABEL[selectedComp.status]}
              </span>
            )}
          </div>

          <div className="flex flex-wrap gap-2">
            {isManager && (
              <button onClick={() => { setShowAddComp(true); setError(''); }}
                className="gradient-primary text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 text-sm">
                <Plus className="w-4 h-4" /> مسابقة جديدة
              </button>
            )}
            {isManager && selectedComp && !frozen && (
              <>
                <button onClick={() => { setShowRegContestant(true); setError(''); }}
                  className="gradient-gold text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 text-sm">
                  <Plus className="w-4 h-4" /> تسجيل متسابق
                </button>
                <button onClick={handleApprove} disabled={submitting}
                  className="bg-emerald-600 hover:bg-emerald-700 text-white font-bold px-5 py-3 rounded-xl flex items-center gap-2 text-sm">
                  <ShieldCheck className="w-4 h-4" /> اعتماد النتائج
                </button>
              </>
            )}
            {isManager && selectedComp?.status === 'approved' && (
              <button onClick={handleArchive} disabled={submitting}
                className="border-2 border-[hsl(var(--border))] font-bold px-5 py-3 rounded-xl flex items-center gap-2 text-sm">
                <Archive className="w-4 h-4" /> نقل إلى الأرشيف
              </button>
            )}
          </div>
        </div>

        {/* لجنة التحكيم وحالة التجميد */}
        {selectedComp && (
          <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))] p-4 flex flex-wrap items-center gap-x-6 gap-y-2">
            <span className="text-sm font-bold flex items-center gap-1.5">
              <Gavel className="w-4 h-4 text-[hsl(var(--primary))]" /> لجنة التحكيم:
            </span>
            {selectedComp.judges.length === 0 ? (
              <span className="text-sm text-[hsl(var(--muted-foreground))]">لم تُعيَّن لجنة بعد</span>
            ) : selectedComp.judges.map(j => (
              <span key={j.teacher_id} className="text-xs font-semibold bg-[hsl(var(--muted))] px-3 py-1.5 rounded-full">
                {j.teacher_name || j.teacher_id}
              </span>
            ))}
            {frozen && (
              <span className="text-xs font-bold text-slate-600 flex items-center gap-1.5 w-full sm:w-auto">
                <Lock className="w-3.5 h-3.5" />
                النتائج معتمَدة ومجمَّدة — لا تُعدَّل
                {selectedComp.approved_by ? ` (اعتمدها ${selectedComp.approved_by})` : ''}
              </span>
            )}
          </div>
        )}

        {/* النتائج: كل فرع جدولٌ مستقلّ بترتيبه من واحد */}
        {blocks.length === 0 ? (
          <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))] text-center py-16">
            <Award className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
            <p className="text-[hsl(var(--muted-foreground))] font-semibold">
              {selectedComp ? 'لا متسابقين في هذه المسابقة بعد' : 'لا توجد مسابقات'}
            </p>
          </div>
        ) : blocks.map(block => (
          <div key={block.branch}
            className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))] shadow-sm overflow-hidden">
            <div className="p-4 border-b border-[hsl(var(--border))] flex items-center justify-between gap-3">
              <h3 className="font-bold text-base flex items-center gap-2 min-w-0">
                <Trophy className="w-5 h-5 text-amber-500 shrink-0" />
                <span className="truncate">فرع {block.branch}</span>
              </h3>
              <span className="badge-gold text-xs px-2.5 py-1 rounded-full font-bold shrink-0">
                {block.count} متسابق
              </span>
            </div>

            {block.count === 0 ? (
              <p className="text-center py-8 text-sm text-[hsl(var(--muted-foreground))]">
                لا متسابقين في هذا الفرع
              </p>
            ) : (
              <div className="overflow-x-auto">
                <table className="w-full text-right border-collapse min-w-[720px]">
                  <thead>
                    <tr className="bg-[hsl(var(--muted))] text-xs font-bold text-[hsl(var(--muted-foreground))]">
                      <th className="p-3">الترتيب</th>
                      <th className="p-3">الطالب</th>
                      <th className="p-3">الحلقة</th>
                      <th className="p-3 text-center">الحفظ (70)</th>
                      <th className="p-3 text-center">التجويد (20)</th>
                      <th className="p-3 text-center">الصوت (10)</th>
                      <th className="p-3 text-center">المحكّمون</th>
                      <th className="p-3 text-center">المجموع (100)</th>
                      <th className="p-3 text-center">الإجراءات</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[hsl(var(--border))] text-sm">
                    {block.contestants.map(con => {
                      const rank = con.rank_in_branch || 0;
                      const graded = con.judges_count > 0;
                      return (
                        <tr key={con.id} className="hover:bg-[hsl(var(--muted))/30] transition-colors">
                          <td className="p-3 font-bold whitespace-nowrap">
                            {graded && rank <= 3
                              ? <span className="bg-amber-100 text-amber-800 px-2 py-0.5 rounded-lg text-xs">{RANK_BADGE[rank - 1]}</span>
                              : <span className="text-[hsl(var(--muted-foreground))] font-normal">#{rank}</span>}
                          </td>
                          <td className="p-3 font-bold">{con.student_name}</td>
                          <td className="p-3 text-xs text-[hsl(var(--muted-foreground))]">{con.halaqah_name || '—'}</td>
                          <td className="p-3 text-center font-mono">{con.grades?.hifdh_score ?? '—'}</td>
                          <td className="p-3 text-center font-mono">{con.grades?.tajweed_score ?? '—'}</td>
                          <td className="p-3 text-center font-mono">{con.grades?.voice_score ?? '—'}</td>
                          <td className="p-3 text-center">
                            {graded ? (
                              <span title={con.judge_scores.map(s => `${s.judge_name || 'محكّم'}: ${s.total}`).join(' · ')}
                                className="text-xs font-bold bg-[hsl(var(--muted))] px-2 py-1 rounded-full cursor-help">
                                {con.judges_count}
                              </span>
                            ) : <span className="text-xs text-[hsl(var(--muted-foreground))]">—</span>}
                          </td>
                          <td className="p-3 text-center font-mono font-bold text-[hsl(var(--primary))]">
                            {graded ? con.total_score : 'لم تُرصد'}
                          </td>
                          <td className="p-3 text-center">
                            <div className="flex items-center justify-center gap-1.5">
                              {canGrade && (
                                <button onClick={() => openGradeModal(con)}
                                  className="px-3 py-1.5 rounded-lg bg-emerald-50 hover:bg-emerald-100 text-emerald-700 font-bold text-xs flex items-center gap-1">
                                  <Star className="w-3.5 h-3.5" />
                                  {con.judge_scores.some(s => s.judge_teacher_id === myTeacherId)
                                    ? 'تعديل درجتي' : 'رصد درجتي'}
                                </button>
                              )}
                              {graded && (
                                <button onClick={() => { setPrintCert(con); setTimeout(() => window.print(), 250); }}
                                  className="px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100 text-blue-700 font-bold text-xs flex items-center gap-1">
                                  <Printer className="w-3.5 h-3.5" /> شهادة
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
        ))}

        {isManager && selectedComp && !frozen && (
          <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1.5">
            <CheckCircle2 className="w-3.5 h-3.5" />
            رصدُ الدرجات للجنة التحكيم — الإدارة تعتمد النتيجة ولا تضعها.
          </p>
        )}
      </div>

      {/* إنشاء مسابقة + تعيين اللجنة */}
      {showAddComp && (
        <div className="modal-overlay print:hidden" onClick={() => setShowAddComp(false)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Trophy className="w-5 h-5 text-[hsl(var(--gold))]" /> مسابقة جديدة
              </h3>
              <button onClick={() => setShowAddComp(false)} className="text-white/80 hover:text-white">✕</button>
            </div>
            <div className="p-5 space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
              <div>
                <label className="text-xs font-bold block mb-1">عنوان المسابقة *</label>
                <input value={compForm.title} onChange={e => setCompForm({ ...compForm, title: e.target.value })}
                  placeholder="المسابقة الرمضانية الكبرى"
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm" />
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">تاريخ الانعقاد *</label>
                <input type="date" value={compForm.date}
                  onChange={e => setCompForm({ ...compForm, date: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm" />
              </div>
              <div>
                <label className="text-xs font-bold block mb-2">فروع المسابقة *</label>
                <div className="space-y-1.5">
                  {branchOptions.map(b => (
                    <label key={b} className="flex items-center gap-2 text-sm font-semibold cursor-pointer">
                      <input type="checkbox" className="w-4 h-4"
                        checked={compForm.branches.includes(b)}
                        onChange={e => setCompForm(f => ({
                          ...f,
                          branches: e.target.checked
                            ? [...f.branches, b]
                            : f.branches.filter(x => x !== b),
                        }))} />
                      {b}
                    </label>
                  ))}
                </div>
              </div>
              <div>
                <label className="text-xs font-bold block mb-2">
                  لجنة التحكيم — الشيوخ الذين يرصدون الدرجات
                </label>
                {teachers.length === 0 ? (
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">لا يوجد محفّظون مسجّلون</p>
                ) : (
                  <div className="space-y-1.5 max-h-44 overflow-y-auto border rounded-xl p-3">
                    {teachers.map(t => (
                      <label key={t.id} className="flex items-center gap-2 text-sm font-semibold cursor-pointer">
                        <input type="checkbox" className="w-4 h-4"
                          checked={compForm.judges.includes(t.id)}
                          onChange={e => setCompForm(f => ({
                            ...f,
                            judges: e.target.checked
                              ? [...f.judges, t.id]
                              : f.judges.filter(x => x !== t.id),
                          }))} />
                        {t.name}
                      </label>
                    ))}
                  </div>
                )}
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-1.5">
                  تظهر المسابقة لأعضاء اللجنة وحدهم، وتختفي عنهم بعد اعتماد النتائج.
                </p>
              </div>
              <div className="flex gap-2 pt-3 border-t">
                <button onClick={handleCreateComp} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ الحفظ...' : 'حفظ المسابقة'}
                </button>
                <button onClick={() => setShowAddComp(false)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* تسجيل متسابق */}
      {showRegContestant && selectedComp && (
        <div className="modal-overlay print:hidden" onClick={() => setShowRegContestant(false)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Award className="w-5 h-5 text-[hsl(var(--gold))]" /> تسجيل متسابق
              </h3>
              <button onClick={() => setShowRegContestant(false)} className="text-white/80 hover:text-white">✕</button>
            </div>
            <div className="p-5 space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
              <div>
                <label className="text-xs font-bold block mb-1">الطالب *</label>
                <select value={regForm.student_id}
                  onChange={e => setRegForm({ ...regForm, student_id: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm bg-white">
                  <option value="">اختر الطالب</option>
                  {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">الفرع *</label>
                <select value={regForm.category}
                  onChange={e => setRegForm({ ...regForm, category: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm bg-white">
                  <option value="">اختر الفرع</option>
                  {(selectedComp.branches || selectedComp.categories).map(cat => (
                    <option key={cat} value={cat}>{cat}</option>
                  ))}
                </select>
              </div>
              <div className="flex gap-2 pt-3 border-t">
                <button onClick={handleRegisterContestant} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ التسجيل...' : 'تسجيل'}
                </button>
                <button onClick={() => setShowRegContestant(false)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* رصد درجة محكّم */}
      {showGradeModal && (
        <div className="modal-overlay print:hidden" onClick={() => setShowGradeModal(null)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
            onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white">
              <h3 className="text-lg font-bold flex items-center gap-2">
                <Star className="w-5 h-5 text-[hsl(var(--gold))]" /> رصد درجتي
              </h3>
              <button onClick={() => setShowGradeModal(null)} className="text-white/80 hover:text-white">✕</button>
            </div>
            <div className="p-5 space-y-4">
              <div className="p-3 bg-emerald-50 rounded-[var(--radius)] border border-emerald-100 flex items-center gap-2.5">
                <User className="w-5 h-5 text-emerald-700" />
                <div>
                  <h4 className="font-bold text-sm text-emerald-800">{showGradeModal.student_name}</h4>
                  <p className="text-[10px] text-emerald-700 font-semibold">فرع {showGradeModal.category}</p>
                </div>
              </div>
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
              <div className="grid grid-cols-3 gap-2">
                {([
                  ['hifdh_score', 'الحفظ (70)', '0 - 70'],
                  ['tajweed_score', 'التجويد (20)', '0 - 20'],
                  ['voice_score', 'الصوت (10)', '0 - 10'],
                ] as const).map(([key, label, ph]) => (
                  <div key={key}>
                    <label className="text-xs font-bold block mb-1 text-center">{label} *</label>
                    <input inputMode="decimal" placeholder={ph}
                      value={gradeForm[key]}
                      onChange={e => setGradeForm({ ...gradeForm, [key]: e.target.value })}
                      className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-center text-sm font-bold" />
                  </div>
                ))}
              </div>

              {showGradeModal.judge_scores.length > 0 && (
                <div className="rounded-xl border border-[hsl(var(--border))] p-3">
                  <h5 className="text-xs font-bold mb-2">درجات اللجنة المرصودة</h5>
                  <ul className="space-y-1 text-xs">
                    {showGradeModal.judge_scores.map(s => (
                      <li key={s.judge_teacher_id} className="flex justify-between">
                        <span className="font-semibold">{s.judge_name || 'محكّم'}</span>
                        <span className="font-mono font-bold">{s.total}</span>
                      </li>
                    ))}
                  </ul>
                  <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-2 pt-2 border-t">
                    المجموع النهائي متوسّط درجات اللجنة: {showGradeModal.total_score}
                  </p>
                </div>
              )}

              <div className="flex gap-2 pt-3 border-t">
                <button onClick={handleGradeSubmit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ الرصد...' : 'رصد درجتي'}
                </button>
                <button onClick={() => setShowGradeModal(null)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
