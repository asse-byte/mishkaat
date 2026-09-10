/**
 * الشهادات.
 *
 * [قرار المالك 2026-09-07] الإصدار لمدير المركز وحده. والمعلّم والطالب ووليّه
 * يرون ما صدر ويطبعونه، ولا يُصدرون.
 *
 * وقائمةُ «المستحقّون» هي ما يجعل «بعد الختم مباشرة تظهر الشهادة» أمراً
 * واقعاً: لا ينتظر المديرُ أن يُخبره أحد، بل تُعرض عليه الأسماءُ التي بلغت
 * محطّةً ولم تُكرَّم بعد.
 */
import { useCallback, useEffect, useState } from 'react';
import {
  Award, Printer, Trash2, Sparkles, GraduationCap, Search, ScrollText,
} from 'lucide-react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import PageHeader from '@/components/ui/PageHeader';
import CertificateSheet, { type Certificate } from '@/components/certificates/CertificateSheet';
import { errorMessage } from '@/lib/errors';
import { printLandscape } from '@/lib/printLandscape';
import api from '@/services/api';

interface PendingMilestone { milestone: string; label: string }
interface EligibleStudent {
  student_id: string;
  student_name: string;
  halaqah_name?: string;
  pages_memorized: number;
  juz_memorized: number;
  pending: PendingMilestone[];
}

const KIND_LABEL: Record<string, string> = {
  competition: 'مسابقة',
  milestone: 'حفظ',
};

export default function Certificates() {
  const { user } = useAuth();
  const isManager = user?.role === 'center_manager' || user?.role === 'admin'
    || user?.role === 'super_admin';

  const [tab, setTab] = useState<'issued' | 'eligible'>(isManager ? 'eligible' : 'issued');
  const [issued, setIssued] = useState<Certificate[]>([]);
  const [eligible, setEligible] = useState<EligibleStudent[]>([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState('');
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const [search, setSearch] = useState('');
  const [printing, setPrinting] = useState<Certificate | null>(null);

  const load = useCallback(async () => {
    try {
      setLoading(true);
      setError('');
      const certs = await api.get<Certificate[]>('/certificates');
      setIssued(certs.data);
      if (isManager) {
        const el = await api.get<{ students: EligibleStudent[] }>('/certificates/eligible');
        setEligible(el.data.students || []);
      }
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر تحميل الشهادات'));
    } finally {
      setLoading(false);
    }
  }, [isManager]);

  useEffect(() => { load(); }, [load]);

  const issueMilestone = async (studentId: string, milestone: string, label: string) => {
    try {
      setBusy(`${studentId}:${milestone}`);
      setError('');
      const r = await api.post<Certificate>('/certificates/milestone',
        { student_id: studentId, milestone });
      setNotice(`صدرت شهادة «${label}» برقم ${r.data.serial}.`);
      await load();
      setPrinting(r.data);
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر إصدار الشهادة'));
    } finally {
      setBusy('');
    }
  };

  const revoke = async (cert: Certificate) => {
    if (!window.confirm(
      `إلغاء الشهادة ${cert.serial} الصادرة لـ${cert.student_name}؟ يمكن إصدارها من جديد بعد ذلك.`
    )) return;
    try {
      setBusy(cert.id);
      setError('');
      await api.delete(`/certificates/${cert.id}`);
      setNotice('أُلغيت الشهادة.');
      await load();
    } catch (err: unknown) {
      setError(errorMessage(err, 'تعذّر إلغاء الشهادة'));
    } finally {
      setBusy('');
    }
  };

  const preview = (cert: Certificate) => setPrinting(cert);

  const shown = issued.filter(c =>
    !search
    || (c.student_name || '').includes(search)
    || (c.serial || '').includes(search));

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* معاينةٌ على الشاشة قبل الطباعة.
          الطباعةُ مباشرةً من زرّ في جدولٍ تعني أن أوّل ما يراه المدير من
          الشهادة هو نافذةُ الطابعة — فإن كان فيها خطأٌ في الاسم أو المناسبة
          اكتشفه بعد أن خرجت الورقة. المعاينةُ تُريه ما سيطبعه. */}
      {printing && (
        <div className="modal-overlay print:hidden" onClick={() => setPrinting(null)}>
          <div className="w-full max-w-4xl space-y-3" onClick={e => e.stopPropagation()}>
            <div className="bg-white rounded-[var(--radius-lg)] overflow-hidden shadow-2xl">
              <CertificateSheet cert={printing} />
            </div>
            <div className="flex justify-center gap-2">
              <button onClick={() => printLandscape(150)}
                className="gradient-primary text-white font-bold px-6 py-3 rounded-xl
                           text-sm flex items-center gap-2">
                <Printer className="w-4 h-4" /> طباعة
              </button>
              <button onClick={() => setPrinting(null)}
                className="bg-white font-bold px-6 py-3 rounded-xl text-sm border-2
                           border-[hsl(var(--border))]">
                إغلاق
              </button>
            </div>
          </div>
        </div>
      )}

      {/* الورقة وحدها على المطبوع */}
      {printing && (
        <div className="hidden print:block fixed inset-0 z-[9999] bg-white certificate-print">
          <CertificateSheet cert={printing} />
        </div>
      )}

      <div className="print:hidden space-y-6">
        <PageHeader
          title="الشهادات"
          subtitle="شهادات المسابقات ومحطّات الحفظ — يُصدرها مدير المركز"
        />

        {error && (
          <div className="p-3 rounded-xl bg-red-50 text-red-700 text-sm font-semibold border border-red-200">
            {error}
          </div>
        )}
        {notice && (
          <div className="p-3 rounded-xl bg-emerald-50 text-emerald-800 text-sm font-semibold
                          border border-emerald-200 flex items-center justify-between gap-3">
            <span>{notice}</span>
            <button onClick={() => setNotice('')} className="text-xs shrink-0">إخفاء</button>
          </div>
        )}

        {isManager && (
          <div className="flex gap-2">
            {([
              ['eligible', 'المستحقّون', eligible.length],
              ['issued', 'الصادرة', issued.length],
            ] as const).map(([key, label, count]) => (
              <button key={key} onClick={() => setTab(key)}
                className={`px-5 py-2.5 rounded-xl font-bold text-sm border-2 transition-colors ${
                  tab === key
                    ? 'border-[hsl(var(--primary))] bg-[hsl(var(--muted))] text-[hsl(var(--primary))]'
                    : 'border-[hsl(var(--border))]'}`}>
                {label} ({count})
              </button>
            ))}
          </div>
        )}

        {/* المستحقّون */}
        {isManager && tab === 'eligible' && (
          eligible.length === 0 ? (
            <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                            text-center py-16">
              <Sparkles className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
              <p className="text-[hsl(var(--muted-foreground))] font-semibold">
                لا أحد بلغ محطّةً جديدة تنتظر التكريم
              </p>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">
                تظهر هنا أسماءُ الطلاب فور بلوغهم خمسة أجزاء أو عشرة أو نصف القرآن أو ختمه.
              </p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-4">
              {eligible.map(s => (
                <div key={s.student_id}
                  className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                             p-5 shadow-sm space-y-3">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0">
                      <h3 className="font-bold truncate">{s.student_name}</h3>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">
                        {s.halaqah_name || '—'}
                      </p>
                    </div>
                    <span className="text-xs font-bold bg-[hsl(var(--muted))] px-2.5 py-1
                                     rounded-full shrink-0">
                      {s.juz_memorized} جزءاً
                    </span>
                  </div>
                  <div className="space-y-2">
                    {s.pending.map(p => (
                      <button key={p.milestone}
                        onClick={() => issueMilestone(s.student_id, p.milestone, p.label)}
                        disabled={busy === `${s.student_id}:${p.milestone}`}
                        className="w-full gradient-primary text-white font-bold py-2.5 rounded-xl
                                   text-xs flex items-center justify-center gap-2 disabled:opacity-60">
                        <Award className="w-4 h-4" />
                        إصدار شهادة {p.label}
                      </button>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        )}

        {/* الصادرة */}
        {(!isManager || tab === 'issued') && (
          <>
            {issued.length > 6 && (
              <div className="relative">
                <Search className="absolute right-3 top-3.5 w-5 h-5 text-[hsl(var(--muted-foreground))]" />
                <input value={search} onChange={e => setSearch(e.target.value)}
                  placeholder="ابحث باسم الطالب أو رقم الشهادة..."
                  className="form-input pr-10" />
              </div>
            )}

            {shown.length === 0 ? (
              <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                              text-center py-16">
                <ScrollText className="w-14 h-14 mx-auto mb-3 text-[hsl(var(--muted-foreground))] opacity-35" />
                <p className="text-[hsl(var(--muted-foreground))] font-semibold">
                  لا شهادات بعد
                </p>
              </div>
            ) : (
              <div className="bg-white rounded-[var(--radius-lg)] border border-[hsl(var(--border))]
                              shadow-sm overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full text-right border-collapse min-w-[720px]">
                    <thead>
                      <tr className="bg-[hsl(var(--muted))] text-xs font-bold
                                     text-[hsl(var(--muted-foreground))]">
                        <th className="p-3">الرقم</th>
                        <th className="p-3">الطالب</th>
                        <th className="p-3">المناسبة</th>
                        <th className="p-3">النوع</th>
                        <th className="p-3">أصدرها</th>
                        <th className="p-3 text-center">الإجراءات</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[hsl(var(--border))] text-sm">
                      {shown.map(c => (
                        <tr key={c.id} className="hover:bg-[hsl(var(--muted))/30]">
                          <td className="p-3 font-mono text-xs" dir="ltr">{c.serial}</td>
                          <td className="p-3 font-bold">{c.student_name}</td>
                          <td className="p-3 text-xs">
                            {c.subtitle}
                            {c.branch ? ` · ${c.branch}` : ''}
                            {c.rank ? ` · المركز ${c.rank}` : ''}
                          </td>
                          <td className="p-3">
                            <span className="text-[11px] font-bold bg-[hsl(var(--muted))]
                                             px-2 py-1 rounded-full">
                              {KIND_LABEL[c.kind] || c.kind}
                            </span>
                          </td>
                          <td className="p-3 text-xs text-[hsl(var(--muted-foreground))]">
                            {c.issued_by_name || '—'}
                          </td>
                          <td className="p-3">
                            <div className="flex items-center justify-center gap-1.5">
                              <button onClick={() => preview(c)}
                                className="px-3 py-1.5 rounded-lg bg-blue-50 hover:bg-blue-100
                                           text-blue-700 font-bold text-xs flex items-center gap-1">
                                <Printer className="w-3.5 h-3.5" /> عرض وطباعة
                              </button>
                              {isManager && (
                                <button onClick={() => revoke(c)} disabled={busy === c.id}
                                  className="px-3 py-1.5 rounded-lg bg-red-50 hover:bg-red-100
                                             text-red-700 font-bold text-xs flex items-center gap-1
                                             disabled:opacity-60">
                                  <Trash2 className="w-3.5 h-3.5" /> إلغاء
                                </button>
                              )}
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </>
        )}

        {isManager && (
          <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-1.5">
            <GraduationCap className="w-3.5 h-3.5 shrink-0" />
            شهادةُ المسابقة تُصدَر من صفحة المسابقات بعد اعتماد نتائجها.
          </p>
        )}
      </div>
    </div>
  );
}
