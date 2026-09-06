/**
 * إصدار حسابَي الطالب ووليّ أمره — بيد المدير.
 *
 * [قرار المالك 2026-09-06] الحساب يُصدَر **بعد** التسجيل: يُسجَّل الطالب أوّلاً،
 * ثمّ يُعطيه المدير اسمَ مستخدمٍ وكلمة مرور، وكذلك وليَّه.
 *
 * كلمة المرور تُعرض **مرّة واحدة** هنا ليسلّمها المدير، ولا تُخزَّن إلا مُعمّاة
 * في الخادم. فلذلك تبقى ظاهرةً في الشاشة حتى يُغلقها المدير بنفسه، مع تنبيهٍ
 * صريح بأنها لن تظهر ثانية — ومن نسيها فليُصدر غيرها.
 */
import { useCallback, useEffect, useState } from 'react';
import { KeyRound, X, Copy, Check, UserCircle2, Users } from 'lucide-react';
import { errorMessage } from '@/lib/errors';
import api from '@/services/api';

type Holder = 'student' | 'parent';

interface AccountBrief {
  id: string; username: string; name?: string; is_active: boolean;
}

interface AccountsState {
  student_name: string;
  parent_name?: string | null;
  parent_phone?: string | null;
  student_account: AccountBrief | null;
  parent_account: AccountBrief | null;
  suggested_password: string;
}

const HOLDER_LABEL: Record<Holder, string> = {
  student: 'الطالب',
  parent: 'وليّ الأمر',
};

export default function StudentAccountsModal({
  studentId, studentName, onClose,
}: { studentId: string; studentName: string; onClose: () => void }) {
  const [state, setState] = useState<AccountsState | null>(null);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState<{ holder: Holder; username: string; password: string } | null>(null);
  /** ما صدر الآن — يظهر مرّة واحدة ولا يُقرأ من الخادم بعدها */
  const [issued, setIssued] = useState<{ holder: Holder; username: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      const r = await api.get<AccountsState>(`/students/${studentId}/accounts`);
      setState(r.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل الحسابات'));
    } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => { load(); }, [load]);

  const openForm = (holder: Holder) => {
    setError('');
    setIssued(null);
    const base = holder === 'student' ? 'talib' : 'wali';
    setForm({
      holder,
      username: `${base}${Math.floor(1000 + Math.random() * 9000)}`,
      password: state?.suggested_password || '',
    });
  };

  const issue = async () => {
    if (!form) return;
    try {
      setSubmitting(true);
      setError('');
      const r = await api.post<{ username: string; password: string }>(
        `/students/${studentId}/accounts`,
        { holder: form.holder, username: form.username, password: form.password || undefined });
      setIssued({ holder: form.holder, username: r.data.username, password: r.data.password });
      setForm(null);
      await load();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر إصدار الحساب'));
    } finally {
      setSubmitting(false);
    }
  };

  const reset = async (holder: Holder) => {
    if (!window.confirm(
      `كلمة مرور جديدة لحساب ${HOLDER_LABEL[holder]}؟ ستُغلَق جلساتُه المفتوحة.`
    )) return;
    try {
      setSubmitting(true);
      setError('');
      const r = await api.post<{ password: string }>(
        `/students/${studentId}/accounts/reset`, { holder });
      const acc = holder === 'student' ? state?.student_account : state?.parent_account;
      setIssued({ holder, username: acc?.username || '', password: r.data.password });
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تغيير كلمة المرور'));
    } finally {
      setSubmitting(false);
    }
  };

  const copy = (text: string) => {
    navigator.clipboard?.writeText(text).then(() => {
      setCopied(true);
      setTimeout(() => setCopied(false), 1800);
    }).catch(() => { /* المتصفّح منع النسخ — البيانات ظاهرة للنقل يدوياً */ });
  };

  const card = (holder: Holder, acc: AccountBrief | null) => (
    <div className="rounded-[var(--radius)] border border-[hsl(var(--border))] p-4">
      <div className="flex items-center justify-between gap-3 mb-2">
        <span className="font-bold text-sm flex items-center gap-2">
          {holder === 'student'
            ? <UserCircle2 className="w-4 h-4 text-[hsl(var(--primary))]" />
            : <Users className="w-4 h-4 text-[hsl(var(--primary))]" />}
          حساب {HOLDER_LABEL[holder]}
        </span>
        {acc
          ? <span className="text-[11px] font-bold bg-emerald-50 text-emerald-700 px-2 py-1 rounded-full">
              صادر
            </span>
          : <span className="text-[11px] font-bold bg-[hsl(var(--muted))] px-2 py-1 rounded-full">
              لم يُصدَر
            </span>}
      </div>
      {acc ? (
        <div className="flex items-center justify-between gap-2">
          <span className="text-sm font-mono" dir="ltr">{acc.username}</span>
          <button onClick={() => reset(holder)} disabled={submitting}
            className="text-xs font-bold px-3 py-1.5 rounded-lg bg-amber-50 hover:bg-amber-100 text-amber-800">
            كلمة مرور جديدة
          </button>
        </div>
      ) : (
        <button onClick={() => openForm(holder)}
          className="w-full mt-1 gradient-primary text-white font-bold py-2.5 rounded-xl text-xs">
          إصدار حساب {HOLDER_LABEL[holder]}
        </button>
      )}
    </div>
  );

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white sticky top-0 z-10">
          <h3 className="text-lg font-bold flex items-center gap-2 min-w-0">
            <KeyRound className="w-5 h-5 text-[hsl(var(--gold))] shrink-0" />
            <span className="truncate">حسابات {studentName}</span>
          </h3>
          <button onClick={onClose} className="text-white/80 hover:text-white shrink-0">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-4">
          {error && <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm font-semibold">{error}</div>}

          {issued && (
            <div className="rounded-[var(--radius)] border-2 border-emerald-300 bg-emerald-50 p-4">
              <h4 className="font-bold text-sm text-emerald-900 mb-2">
                بيانات دخول {HOLDER_LABEL[issued.holder]}
              </h4>
              <div className="space-y-1 text-sm font-mono bg-white rounded-xl p-3" dir="ltr">
                <div>{issued.username}</div>
                <div>{issued.password}</div>
              </div>
              <div className="flex items-center justify-between gap-2 mt-2">
                <p className="text-[11px] text-emerald-800 font-semibold">
                  انسخها الآن — لن تظهر كلمة المرور مرّة أخرى.
                </p>
                <button onClick={() => copy(`${issued.username}\n${issued.password}`)}
                  className="text-xs font-bold px-3 py-1.5 rounded-lg bg-white border border-emerald-300 flex items-center gap-1 shrink-0">
                  {copied ? <Check className="w-3.5 h-3.5" /> : <Copy className="w-3.5 h-3.5" />}
                  {copied ? 'نُسخت' : 'نسخ'}
                </button>
              </div>
            </div>
          )}

          {form && (
            <div className="rounded-[var(--radius)] border-2 border-[hsl(var(--border))] p-4 space-y-3">
              <h4 className="font-bold text-sm">إصدار حساب {HOLDER_LABEL[form.holder]}</h4>
              <div>
                <label className="text-xs font-bold block mb-1">اسم المستخدم</label>
                <input value={form.username} dir="ltr"
                  onChange={e => setForm({ ...form, username: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-mono" />
              </div>
              <div>
                <label className="text-xs font-bold block mb-1">
                  كلمة المرور <span className="font-normal">(8 أحرف فأكثر، فيها حرف ورقم)</span>
                </label>
                <input value={form.password} dir="ltr"
                  onChange={e => setForm({ ...form, password: e.target.value })}
                  className="w-full h-11 px-3 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-mono" />
              </div>
              <div className="flex gap-2">
                <button onClick={issue} disabled={submitting}
                  className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl text-sm">
                  {submitting ? 'جارٍ الإصدار...' : 'إصدار'}
                </button>
                <button onClick={() => setForm(null)}
                  className="px-5 py-3 border rounded-xl text-sm font-semibold">إلغاء</button>
              </div>
            </div>
          )}

          {loading ? (
            <p className="text-sm text-[hsl(var(--muted-foreground))]">جارٍ التحميل…</p>
          ) : state ? (
            <div className="space-y-3">
              {card('student', state.student_account)}
              {card('parent', state.parent_account)}
              <p className="text-[11px] text-[hsl(var(--muted-foreground))] leading-relaxed">
                حساب الطالب يرى بياناته وأداءه وترتيبَه ونتائجَ مسابقاته وحدها.
                وحساب وليّ الأمر مربوطٌ بهذا الطالب بعينه، يرى ما يراه ابنُه ولا يتجاوزه.
              </p>
            </div>
          ) : null}
        </div>
      </div>
    </div>
  );
}
