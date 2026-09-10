/**
 * تقييم المحفّظ.
 *
 * [قرار المالك 2026-09-06] النظام يقيس الطالب بستّة مقاييس ويترك المحفّظ بلا
 * تقييمٍ يُقرأ. فيُقاس المحفّظ كما يُقاس الطالب: بمعايير مسمّاة كلٌّ من عشرة،
 * ونقاط قوّة ونقاط ضعف مكتوبة — لا رقماً واحداً مبهماً لا يُعرف مِمّ تركّب.
 *
 * وتقييمُ الرجل شأنُه: يقرؤه المدير وصاحبُه، لا زملاؤه — والخادم يحرس هذا.
 */
import { useCallback, useEffect, useState } from 'react';
import { Star, X, TrendingUp, ThumbsUp, AlertTriangle } from 'lucide-react';
import { errorMessage } from '@/lib/errors';
import api from '@/services/api';

const CRITERIA: { key: CriterionKey; label: string; hint: string }[] = [
  { key: 'performance', label: 'الأداء',    hint: 'إتقان التلاوة والتحفيظ وإدارة الحلقة' },
  { key: 'commitment',  label: 'الالتزام',  hint: 'الحضور في وقته والتزام الجدول' },
  { key: 'sincerity',   label: 'الإخلاص',   hint: 'احتساب العمل ورعاية الطلاب' },
  { key: 'seriousness', label: 'الجدّية',   hint: 'ضبط الحلقة ومتابعة المتخلّفين' },
  { key: 'diligence',   label: 'الاجتهاد',  hint: 'المبادرة وتطوير أساليبه' },
];

type CriterionKey =
  'performance' | 'commitment' | 'sincerity' | 'seriousness' | 'diligence';

interface Evaluation {
  id: string;
  evaluation_date: string;
  tpi: number;
  evaluated_by?: string;
  strengths?: string[];
  weaknesses?: string[];
  notes?: string;
  performance?: number; commitment?: number; sincerity?: number;
  seriousness?: number; diligence?: number;
}

/** لونُ الدرجة — الأخضر ثناء، والكهرماني تنبيه، والأحمر مسألةٌ تُعالَج. */
function toneOf(score: number) {
  if (score >= 80) return 'text-emerald-700 bg-emerald-50 border-emerald-200';
  if (score >= 60) return 'text-amber-700 bg-amber-50 border-amber-200';
  return 'text-red-700 bg-red-50 border-red-200';
}

export default function TeacherEvaluationModal({
  teacherId, teacherName, canEvaluate, onClose,
}: {
  teacherId: string;
  teacherName: string;
  /** المدير يُقيّم؛ والمحفّظ يقرأ تقييم نفسه ولا يكتبه */
  canEvaluate: boolean;
  onClose: () => void;
}) {
  const [history, setHistory] = useState<Evaluation[]>([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [showForm, setShowForm] = useState(false);

  const [scores, setScores] = useState<Record<CriterionKey, number>>({
    performance: 7, commitment: 7, sincerity: 7, seriousness: 7, diligence: 7,
  });
  const [strengths, setStrengths] = useState('');
  const [weaknesses, setWeaknesses] = useState('');
  const [notes, setNotes] = useState('');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get<Evaluation[]>(`/teachers/${teacherId}/evaluations`);
      setHistory(r.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل التقييمات'));
    } finally {
      setLoading(false);
    }
  }, [teacherId]);

  useEffect(() => { load(); }, [load]);

  const total = CRITERIA.reduce((s, c) => s + (scores[c.key] || 0), 0) * 2;

  const submit = async () => {
    try {
      setSubmitting(true);
      setError('');
      await api.post(`/teachers/${teacherId}/evaluations`, {
        teacher_id: teacherId,
        evaluation_date: new Date().toISOString().slice(0, 10),
        ...scores,
        // سطرٌ لكل نقطة — أوضح من فقرةٍ واحدة عند القراءة بعد شهور
        strengths: strengths.split('\n').map(s => s.trim()).filter(Boolean),
        weaknesses: weaknesses.split('\n').map(s => s.trim()).filter(Boolean),
        notes: notes || undefined,
      });
      setShowForm(false);
      setStrengths(''); setWeaknesses(''); setNotes('');
      await load();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر حفظ التقييم'));
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white sticky top-0 z-10">
          <h3 className="text-lg font-bold flex items-center gap-2 min-w-0">
            <Star className="w-5 h-5 text-[hsl(var(--gold))] shrink-0" />
            <span className="truncate">تقييم {teacherName}</span>
          </h3>
          <button onClick={onClose} className="text-white/80 hover:text-white shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {error && (
            <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm font-semibold">{error}</div>
          )}

          {canEvaluate && !showForm && (
            <button onClick={() => setShowForm(true)}
              className="w-full gradient-primary text-white font-bold py-3 rounded-xl text-sm">
              تقييم جديد
            </button>
          )}

          {showForm && (
            <div className="rounded-[var(--radius)] border-2 border-[hsl(var(--border))] p-4 space-y-4">
              <div className="flex items-center justify-between">
                <h4 className="font-bold text-sm">المعايير — كلٌّ من 10</h4>
                <span className={`text-sm font-bold px-3 py-1 rounded-full border ${toneOf(total)}`}>
                  {total} / 100
                </span>
              </div>

              {CRITERIA.map(c => (
                <div key={c.key}>
                  <div className="flex items-baseline justify-between mb-1">
                    <label className="text-sm font-bold">{c.label}</label>
                    <span className="text-xs text-[hsl(var(--muted-foreground))]">{c.hint}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <input type="range" min={0} max={10} step={1}
                      value={scores[c.key]}
                      onChange={e => setScores(s => ({ ...s, [c.key]: Number(e.target.value) }))}
                      className="flex-1 accent-[hsl(var(--primary))]" />
                    <span className="w-9 text-center font-mono font-bold text-sm">
                      {scores[c.key]}
                    </span>
                  </div>
                </div>
              ))}

              <div className="grid sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs font-bold block mb-1 flex items-center gap-1.5">
                    <ThumbsUp className="w-3.5 h-3.5 text-emerald-600" /> نقاط القوّة
                  </label>
                  <textarea value={strengths} onChange={e => setStrengths(e.target.value)}
                    placeholder={'نقطة في كل سطر\nمثال: حضورٌ منتظم'}
                    className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm min-h-[90px]" />
                </div>
                <div>
                  <label className="text-xs font-bold block mb-1 flex items-center gap-1.5">
                    <AlertTriangle className="w-3.5 h-3.5 text-amber-600" /> نقاط الضعف
                  </label>
                  <textarea value={weaknesses} onChange={e => setWeaknesses(e.target.value)}
                    placeholder={'نقطة في كل سطر\nمثال: تأخّرٌ في رفع التسميعات'}
                    className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm min-h-[90px]" />
                </div>
              </div>

              <div>
                <label className="text-xs font-bold block mb-1">ملاحظات</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                  className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm min-h-[60px]" />
              </div>

              <div className="flex gap-2">
                <button onClick={submit} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ الحفظ...' : 'حفظ التقييم'}
                </button>
                <button onClick={() => setShowForm(false)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          )}

          <div>
            <h4 className="font-bold text-sm mb-3 flex items-center gap-2">
              <TrendingUp className="w-4 h-4 text-[hsl(var(--primary))]" /> سجلّ التقييمات
            </h4>
            {loading ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))]">جارٍ التحميل…</p>
            ) : history.length === 0 ? (
              <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">
                لم يُقيَّم بعد
              </p>
            ) : (
              <div className="space-y-3">
                {history.map(ev => (
                  <div key={ev.id} className="rounded-[var(--radius)] border border-[hsl(var(--border))] p-4">
                    <div className="flex items-center justify-between mb-2 gap-2">
                      <span className="text-xs font-semibold text-[hsl(var(--muted-foreground))]">
                        {ev.evaluation_date}
                        {ev.evaluated_by ? ` · قيّمه ${ev.evaluated_by}` : ''}
                      </span>
                      <span className={`text-sm font-bold px-3 py-1 rounded-full border ${toneOf(ev.tpi)}`}>
                        {ev.tpi} / 100
                      </span>
                    </div>

                    <div className="flex flex-wrap gap-1.5 mb-2">
                      {CRITERIA.filter(c => ev[c.key] !== undefined && ev[c.key] !== null).map(c => (
                        <span key={c.key}
                          className="text-[11px] font-semibold bg-[hsl(var(--muted))] px-2 py-1 rounded-full">
                          {c.label} {ev[c.key]}/10
                        </span>
                      ))}
                    </div>

                    {!!ev.strengths?.length && (
                      <p className="text-xs mb-1">
                        <span className="font-bold text-emerald-700">قوّة: </span>
                        {ev.strengths.join(' · ')}
                      </p>
                    )}
                    {!!ev.weaknesses?.length && (
                      <p className="text-xs mb-1">
                        <span className="font-bold text-amber-700">ضعف: </span>
                        {ev.weaknesses.join(' · ')}
                      </p>
                    )}
                    {ev.notes && (
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">{ev.notes}</p>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
