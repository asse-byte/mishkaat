/**
 * خطة المراجعة.
 *
 * [قرار المالك 2026-09-07] «اجعل خطة المراجعة شيئاً مفهوماً لدى معلّم الحلقة،
 * وكيف يفهمه ويستفيد به.»
 *
 * وما كانت تُفهم ولا يُستفاد بها. كانت الصفحة تعرض جدولاً واحداً ثابتاً مكتوباً
 * في الكود — «السبت: الأجزاء 1-5، الأحد: 6-10…» — يُعرض لكلّ طالبٍ سواءٌ حفظ
 * ثلاثين جزءاً أو نصف جزء. ولم تكن تنادي نقاطَ خطط المراجعة أصلاً: المجموعةُ
 * والموجّهُ في الخادم لم يستعملهما شيءٌ في الواجهة قطّ. وعلامةُ «تمّت» كانت
 * تُقارن رقمَ الجزء بحقل `start_ayah`، فمراجعةُ الآية الثالثة من أيّ سورة
 * تُعلّم يومَ السبت منجزاً — إلى الأبد، بلا نافذةٍ زمنية.
 *
 * وهي الآن تجيب عن السؤال الذي يسأله الشيخ صباحاً: **على مَن ورده اليوم، ومن
 * راجع، ومن تأخّر** — ووردُ كلِّ طالبٍ محسوبٌ من محفوظه هو.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  RefreshCw, CheckCircle2, AlertTriangle, BookOpen, Info, Settings2, X,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import PageHeader from '@/components/ui/PageHeader';
import { errorMessage } from '@/lib/errors';
import api from '@/services/api';

interface Assignment {
  from_juz: number;
  to_juz: number;
  cycle_days: number;
  day_in_cycle: number;
  memorized_juz: number;
  pages_today: number;
}

interface Row {
  student_id: string;
  student_name: string;
  halaqah_name?: string;
  plan_id?: string | null;
  juz_per_day: number;
  assignment: Assignment | null;
  reviewed_today: boolean;
  days_since_review: number | null;
  overdue: boolean;
  reviews_count: number;
}

interface TodayResponse {
  date: string;
  students: Row[];
  summary: { total: number; reviewed_today: number; overdue: number; no_memorization: number };
  explainer: { how: string; default_rate: number };
}

const EVALUATIONS = [
  { value: 'excellent', label: 'ممتاز' },
  { value: 'very_good', label: 'جيد جداً' },
  { value: 'good', label: 'جيد' },
  { value: 'needs_improvement', label: 'يحتاج تحسيناً' },
];

export default function ReviewPlans() {
  const { user } = useAuth();
  const isTeacher = user?.role === 'teacher';
  const canSetRate = isTeacher || user?.role === 'center_manager' || user?.role === 'admin';

  const [data, setData] = useState<TodayResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [recording, setRecording] = useState<Row | null>(null);
  const [evaluation, setEvaluation] = useState('good');
  const [notes, setNotes] = useState('');
  const [rateFor, setRateFor] = useState<Row | null>(null);
  const [rate, setRate] = useState('1');

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const r = await api.get<TodayResponse>('/review-plans/today');
      setData(r.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل ورد اليوم'));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const recordReview = async () => {
    if (!recording?.assignment) return;
    const a = recording.assignment;
    try {
      setBusy(recording.student_id);
      setError('');
      await api.post('/recitations', {
        student_id: recording.student_id,
        // معرّف المحفّظ يأخذه الخادم من توكن المُسجِّل، ولا يُرسَل من هنا
        teacher_id: '',
        surah_name: a.from_juz === a.to_juz
          ? `مراجعة الجزء ${a.from_juz}`
          : `مراجعة الأجزاء ${a.from_juz}–${a.to_juz}`,
        start_ayah: 1,
        end_ayah: 1,
        // الصفحات صريحة — وكانت الشاشة تحشر رقمَ الجزء في start_ayah/end_ayah،
        // فتُسجَّل «مراجعة خمسة أجزاء» في محرّك المقاييس بوصفها خمسَ آيات.
        pages_count: a.pages_today,
        recitation_type: 'review',
        evaluation,
        notes: notes || undefined,
        error_tags: {},
      });
      setRecording(null);
      setNotes('');
      setNotice('سُجّلت المراجعة.');
      await load();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تسجيل المراجعة'));
    } finally {
      setBusy('');
    }
  };

  const saveRate = async () => {
    if (!rateFor) return;
    const value = Number(rate);
    if (!Number.isFinite(value) || value <= 0) {
      setError('المعدّل يجب أن يكون رقماً أكبر من صفر');
      return;
    }
    try {
      setBusy(rateFor.student_id);
      setError('');
      const payload = {
        center_id: user?.center_id || '',
        student_id: rateFor.student_id,
        juz_per_day: value,
        title: `خطة مراجعة — ${rateFor.student_name}`,
      };
      if (rateFor.plan_id) await api.put(`/review-plans/${rateFor.plan_id}`, payload);
      else await api.post('/review-plans', payload);
      setRateFor(null);
      setNotice('حُفظ معدّل المراجعة.');
      await load();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر حفظ المعدّل'));
    } finally {
      setBusy('');
    }
  };

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>;
  }

  const rows = data?.students || [];

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="خطة المراجعة"
        subtitle={`ورد اليوم — ${data?.date || ''}`}
      >
        <button onClick={load} className="btn-primary text-sm">
          <RefreshCw className="w-4 h-4" /> تحديث
        </button>
      </PageHeader>

      {error && (
        <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold border border-red-200">
          {error}
        </div>
      )}
      {notice && (
        <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-sm font-semibold
                        border border-emerald-200 flex items-center justify-between gap-3">
          <span className="flex items-center gap-2">
            <CheckCircle2 className="w-4 h-4 shrink-0" /> {notice}
          </span>
          <button onClick={() => setNotice('')} className="text-xs shrink-0">إخفاء</button>
        </div>
      )}

      {/* شرحٌ في سطرين: ما هذه الصفحة، وكيف يُحسب الورد */}
      <div className="bg-[hsl(var(--muted))] rounded-[var(--radius)] p-4 flex gap-3">
        <Info className="w-5 h-5 text-[hsl(var(--primary))] shrink-0 mt-0.5" />
        <div className="text-sm leading-relaxed">
          <p className="font-bold mb-1">كيف يُحسب ورد اليوم؟</p>
          <p className="text-[hsl(var(--muted-foreground))]">
            {data?.explainer.how}
            {' '}فمن حفظ خمسة أجزاء بمعدّل جزءٍ يومياً يختم دورته في خمسة أيام،
            ومن حفظ ثلاثين يختمها في شهر. والمعدّل يرفعه الشيخ أو يخفضه لكل طالبٍ
            على حدة من زرّ الإعداد بجانب اسمه.
          </p>
        </div>
      </div>

      {/* ملخّص اليوم */}
      <div className="grid grid-cols-2 md:grid-cols-4 gap-3">
        {[
          { label: 'طلاب الحلقة', value: data?.summary.total ?? 0, tone: '' },
          { label: 'راجعوا اليوم', value: data?.summary.reviewed_today ?? 0, tone: 'text-emerald-700' },
          { label: 'متأخّرون', value: data?.summary.overdue ?? 0, tone: 'text-amber-700' },
          { label: 'لم يبدأوا الحفظ', value: data?.summary.no_memorization ?? 0, tone: 'text-[hsl(var(--muted-foreground))]' },
        ].map(s => (
          <div key={s.label}
            className="bg-white rounded-[var(--radius)] border border-[hsl(var(--border))] p-4">
            <p className={`text-2xl font-bold font-mono ${s.tone}`}>{s.value}</p>
            <p className="text-xs font-semibold text-[hsl(var(--muted-foreground))]">{s.label}</p>
          </div>
        ))}
      </div>

      {rows.length === 0 ? (
        <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                        text-center py-16">
          <BookOpen className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
          <p className="text-[hsl(var(--muted-foreground))] font-semibold">
            لا طلاب في نطاقك
          </p>
        </div>
      ) : (
        <div className="space-y-3">
          {rows.map(r => (
            <div key={r.student_id}
              className={`bg-white rounded-[var(--radius-lg)] border p-5 shadow-sm ${
                r.overdue ? 'border-amber-300' : 'border-[hsl(var(--border))]'}`}>
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <h3 className="font-bold flex items-center gap-2">
                    {r.student_name}
                    {r.reviewed_today && (
                      <span className="text-[11px] font-bold bg-emerald-50 text-emerald-700
                                       px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <CheckCircle2 className="w-3 h-3" /> راجع اليوم
                      </span>
                    )}
                    {r.overdue && (
                      <span className="text-[11px] font-bold bg-amber-50 text-amber-800
                                       px-2 py-0.5 rounded-full inline-flex items-center gap-1">
                        <AlertTriangle className="w-3 h-3" /> متأخّر
                      </span>
                    )}
                  </h3>
                  <p className="text-xs text-[hsl(var(--muted-foreground))] mt-0.5">
                    {r.halaqah_name || '—'}
                    {r.assignment ? ` · حفظ ${r.assignment.memorized_juz} جزءاً` : ''}
                    {r.days_since_review !== null
                      ? ` · آخر مراجعة قبل ${r.days_since_review} يوماً`
                      : ' · لم يُسجَّل له مراجعة بعد'}
                  </p>
                </div>

                <div className="flex items-center gap-2 shrink-0">
                  {canSetRate && (
                    <button
                      onClick={() => { setRateFor(r); setRate(String(r.juz_per_day)); setError(''); }}
                      title="معدّل المراجعة اليوميّ"
                      className="p-2 rounded-lg text-[hsl(var(--ink-3))] hover:bg-[hsl(var(--muted))]">
                      <Settings2 className="w-4 h-4" />
                    </button>
                  )}
                  {isTeacher && r.assignment && !r.reviewed_today && (
                    <button
                      onClick={() => { setRecording(r); setEvaluation('good'); setNotes(''); setError(''); }}
                      disabled={busy === r.student_id}
                      className="gradient-primary text-white font-bold px-4 py-2 rounded-xl
                                 text-xs disabled:opacity-60">
                      تسجيل المراجعة
                    </button>
                  )}
                </div>
              </div>

              {r.assignment ? (
                <div className="mt-3 rounded-[var(--radius)] bg-[hsl(var(--muted))] p-3
                                flex flex-wrap items-center gap-x-6 gap-y-1">
                  <span className="text-sm font-bold">
                    وردُ اليوم:{' '}
                    {r.assignment.from_juz === r.assignment.to_juz
                      ? `الجزء ${r.assignment.from_juz}`
                      : `الأجزاء ${r.assignment.from_juz} – ${r.assignment.to_juz}`}
                  </span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">
                    اليوم {r.assignment.day_in_cycle} من {r.assignment.cycle_days} في الدورة
                  </span>
                  <span className="text-xs text-[hsl(var(--muted-foreground))]">
                    ≈ {r.assignment.pages_today} صفحة · بمعدّل {r.juz_per_day} جزء/يوم
                  </span>
                </div>
              ) : (
                <p className="mt-3 text-xs text-[hsl(var(--muted-foreground))]">
                  لا ورد له بعد — يبدأ حين يُسجَّل له حفظ.
                </p>
              )}
            </div>
          ))}
        </div>
      )}

      {/* تسجيل المراجعة */}
      {recording && recording.assignment && (
        <div className="modal-overlay" onClick={() => setRecording(null)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-md"
            onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center
                            justify-between text-white">
              <h3 className="text-lg font-bold">تسجيل مراجعة {recording.student_name}</h3>
              <button onClick={() => setRecording(null)} className="text-white/80 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
              <div className="rounded-[var(--radius)] bg-[hsl(var(--muted))] p-3 text-sm font-bold">
                {recording.assignment.from_juz === recording.assignment.to_juz
                  ? `الجزء ${recording.assignment.from_juz}`
                  : `الأجزاء ${recording.assignment.from_juz} – ${recording.assignment.to_juz}`}
                <span className="font-normal text-xs text-[hsl(var(--muted-foreground))]">
                  {' '}· {recording.assignment.pages_today} صفحة
                </span>
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">التقدير *</label>
                <select value={evaluation} onChange={e => setEvaluation(e.target.value)}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))]
                             text-sm bg-white">
                  {EVALUATIONS.map(e => <option key={e.value} value={e.value}>{e.label}</option>)}
                </select>
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">ملاحظات</label>
                <textarea value={notes} onChange={e => setNotes(e.target.value)}
                  className="w-full p-3 rounded-xl border-2 border-[hsl(var(--border))]
                             text-sm min-h-[70px]" />
              </div>
              <div className="flex gap-2 pt-3 border-t">
                <button onClick={recordReview} disabled={!!busy}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {busy ? 'جارٍ الحفظ...' : 'حفظ المراجعة'}
                </button>
                <button onClick={() => setRecording(null)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* معدّل المراجعة */}
      {rateFor && (
        <div className="modal-overlay" onClick={() => setRateFor(null)}>
          <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-md"
            onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-5 rounded-t-3xl flex items-center
                            justify-between text-white">
              <h3 className="text-lg font-bold">معدّل مراجعة {rateFor.student_name}</h3>
              <button onClick={() => setRateFor(null)} className="text-white/80 hover:text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-4">
              {error && <div className="p-3 bg-red-50 text-red-600 rounded-xl text-xs">{error}</div>}
              <div>
                <label className="text-xs font-bold block mb-1">كم جزءاً يُراجع في اليوم؟</label>
                <input value={rate} onChange={e => setRate(e.target.value)}
                  inputMode="decimal" dir="ltr"
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))]
                             text-sm text-center font-bold" />
                <p className="text-[11px] text-[hsl(var(--muted-foreground))] mt-1.5">
                  يُقبل الكسر: 0.5 يعني نصف جزء يومياً — للمبتدئ الذي يثقُل عليه الجزء.
                  {rateFor.assignment && (
                    <> ومحفوظُه الآن {rateFor.assignment.memorized_juz} جزءاً.</>
                  )}
                </p>
              </div>
              <div className="flex gap-2 pt-3 border-t">
                <button onClick={saveRate} disabled={!!busy}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {busy ? 'جارٍ الحفظ...' : 'حفظ'}
                </button>
                <button onClick={() => setRateFor(null)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
