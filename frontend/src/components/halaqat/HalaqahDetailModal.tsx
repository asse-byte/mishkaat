/**
 * تفصيل الحلقة للمدير.
 *
 * [قرار المالك 2026-09-06] المدير يرى أداء الحلقات كلِّها، فإذا ضغط على حلقةٍ
 * رأى تفصيلَها: شيخَها وآخرَ تقييمٍ له، وطلابَها ومستوى كلِّ واحد.
 *
 * والمقياسُ الغائب يُكتب «—» لا صفراً: الطالب الذي لم يُسمّع بعد ليس متقناً
 * بدرجة صفر، وإنما لا خبر عنه — والفرق بين الاثنين هو الفرق بين حكمٍ صحيح
 * وحكمٍ ظالم على حلقةٍ استقبلت طلاباً جدداً.
 */
import { useEffect, useState } from 'react';
import { X, Users, Star, GraduationCap, Phone, Briefcase } from 'lucide-react';
import api from '@/services/api';
import { LoadingSpinner } from '@/components/ui/loading';

interface StudentRow {
  id: string; name: string; level?: string;
  memorized_pages?: number; recitations_count: number; attendance_rate: number;
  mastery: number | null; momentum: number | null; precision: number | null;
  consistency: number | null; review_depth: number | null;
}

interface Detail {
  halaqah: { id: string; name: string; schedule?: string; students_count: number };
  teacher: {
    id: string; name: string; phone?: string; specialization?: string;
    teacher_type?: string;
    latest_evaluation?: { tpi: number; evaluation_date: string;
      strengths?: string[]; weaknesses?: string[] } | null;
  } | null;
  summary: {
    mastery: number | null; momentum: number | null;
    consistency: number | null; attendance_rate: number | null;
  };
  students: StudentRow[];
}

/** «—» لا صفر: لا بيانات ≠ درجة صفر. */
const num = (v: number | null | undefined, suffix = '') =>
  v === null || v === undefined ? '—' : `${v}${suffix}`;

export default function HalaqahDetailModal({
  halaqahId, onClose,
}: { halaqahId: string; onClose: () => void }) {
  const [data, setData] = useState<Detail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    let alive = true;
    api.get<Detail>(`/halaqat-overview/${halaqahId}`)
      .then(r => { if (alive) setData(r.data); })
      .catch(err => {
        if (alive) setError(err.response?.data?.detail || 'تعذّر تحميل تفصيل الحلقة');
      })
      .finally(() => { if (alive) setLoading(false); });
    return () => { alive = false; };
  }, [halaqahId]);

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="bg-white rounded-[var(--radius-lg)] shadow-2xl w-full max-w-3xl max-h-[90vh] overflow-y-auto"
        onClick={e => e.stopPropagation()}>
        <div className="gradient-primary p-5 rounded-t-3xl flex items-center justify-between text-white sticky top-0 z-10">
          <h3 className="text-lg font-bold flex items-center gap-2 min-w-0">
            <Users className="w-5 h-5 text-[hsl(var(--gold))] shrink-0" />
            <span className="truncate">{data?.halaqah.name || 'تفصيل الحلقة'}</span>
          </h3>
          <button onClick={onClose} className="text-white/80 hover:text-white shrink-0" aria-label="إغلاق">
            <X className="w-5 h-5" />
          </button>
        </div>

        <div className="p-5 space-y-5">
          {loading ? (
            <div className="flex justify-center py-12"><LoadingSpinner size="lg" /></div>
          ) : error ? (
            <div className="p-3 bg-red-50 text-red-700 rounded-xl text-sm font-semibold">{error}</div>
          ) : data ? (
            <>
              {/* الشيخ وتقييمه */}
              {data.teacher && (
                <div className="rounded-[var(--radius)] border border-[hsl(var(--border))] p-4">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="w-11 h-11 rounded-[var(--radius)] bg-[hsl(var(--muted))] flex items-center justify-center">
                        <GraduationCap className="w-5 h-5 text-[hsl(var(--primary))]" />
                      </div>
                      <div className="min-w-0">
                        <h4 className="font-bold text-sm">{data.teacher.name}</h4>
                        <p className="text-xs text-[hsl(var(--muted-foreground))] flex items-center gap-2 flex-wrap">
                          {data.teacher.specialization && <span>{data.teacher.specialization}</span>}
                          {data.teacher.phone && (
                            <span className="flex items-center gap-1" dir="ltr">
                              <Phone className="w-3 h-3" />{data.teacher.phone}
                            </span>
                          )}
                          {data.teacher.teacher_type === 'external' && (
                            <span className="flex items-center gap-1">
                              <Briefcase className="w-3 h-3" />خارج الحلقات
                            </span>
                          )}
                        </p>
                      </div>
                    </div>
                    {data.teacher.latest_evaluation ? (
                      <div className="text-left">
                        <span className="text-xs font-bold px-3 py-1.5 rounded-full bg-[hsl(var(--muted))] flex items-center gap-1.5">
                          <Star className="w-3.5 h-3.5 text-[hsl(var(--gold))]" />
                          تقييمه {data.teacher.latest_evaluation.tpi} / 100
                        </span>
                        <p className="text-[10px] text-[hsl(var(--muted-foreground))] mt-1 text-center">
                          {data.teacher.latest_evaluation.evaluation_date}
                        </p>
                      </div>
                    ) : (
                      <span className="text-xs text-[hsl(var(--muted-foreground))]">لم يُقيَّم بعد</span>
                    )}
                  </div>

                  {!!data.teacher.latest_evaluation?.strengths?.length && (
                    <p className="text-xs mt-3">
                      <span className="font-bold text-emerald-700">قوّة: </span>
                      {data.teacher.latest_evaluation.strengths.join(' · ')}
                    </p>
                  )}
                  {!!data.teacher.latest_evaluation?.weaknesses?.length && (
                    <p className="text-xs mt-1">
                      <span className="font-bold text-amber-700">ضعف: </span>
                      {data.teacher.latest_evaluation.weaknesses.join(' · ')}
                    </p>
                  )}
                </div>
              )}

              {/* ملخّص الحلقة */}
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[
                  { label: 'الإتقان', value: num(data.summary.mastery, '%') },
                  { label: 'الاندفاع', value: num(data.summary.momentum) },
                  { label: 'الانتظام', value: num(data.summary.consistency, '%') },
                  { label: 'الحضور', value: num(data.summary.attendance_rate, '%') },
                ].map(s => (
                  <div key={s.label} className="rounded-[var(--radius)] border border-[hsl(var(--border))] p-3 text-center">
                    <p className="text-xl font-bold font-mono text-[hsl(var(--primary))]">{s.value}</p>
                    <p className="text-[11px] font-semibold text-[hsl(var(--muted-foreground))]">{s.label}</p>
                  </div>
                ))}
              </div>

              {/* الطلاب */}
              <div>
                <h4 className="font-bold text-sm mb-3">
                  طلاب الحلقة ({data.halaqah.students_count})
                </h4>
                {data.students.length === 0 ? (
                  <p className="text-sm text-[hsl(var(--muted-foreground))] py-6 text-center">
                    لا طلاب في هذه الحلقة
                  </p>
                ) : (
                  <div className="overflow-x-auto">
                    <table className="w-full text-right border-collapse min-w-[620px]">
                      <thead>
                        <tr className="bg-[hsl(var(--muted))] text-xs font-bold text-[hsl(var(--muted-foreground))]">
                          <th className="p-3">الطالب</th>
                          <th className="p-3 text-center">الإتقان</th>
                          <th className="p-3 text-center">الاندفاع</th>
                          <th className="p-3 text-center">الدقّة</th>
                          <th className="p-3 text-center">الانتظام</th>
                          <th className="p-3 text-center">الحضور</th>
                          <th className="p-3 text-center">التسميعات</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-[hsl(var(--border))] text-sm">
                        {data.students.map(st => (
                          <tr key={st.id} className="hover:bg-[hsl(var(--muted))/30]">
                            <td className="p-3 font-bold">{st.name}</td>
                            <td className="p-3 text-center font-mono">{num(st.mastery, '%')}</td>
                            <td className="p-3 text-center font-mono">{num(st.momentum)}</td>
                            <td className="p-3 text-center font-mono">{num(st.precision, '%')}</td>
                            <td className="p-3 text-center font-mono">{num(st.consistency, '%')}</td>
                            <td className="p-3 text-center font-mono">{num(st.attendance_rate, '%')}</td>
                            <td className="p-3 text-center font-mono">{st.recitations_count}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            </>
          ) : null}
        </div>
      </div>
    </div>
  );
}
