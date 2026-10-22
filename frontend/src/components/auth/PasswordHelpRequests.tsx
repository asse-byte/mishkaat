import { useCallback, useEffect, useState } from 'react';
import { KeyRound, Copy, Check } from 'lucide-react';
import api from '@/services/api';
import { errorMessage } from '@/lib/errors';

interface HelpRequest {
  id: string;
  username: string;
  name?: string;
  role?: string;
  phone?: string;
  requested_at: string;
}

const ROLE_LABEL: Record<string, string> = {
  student: 'طالب', parent: 'وليّ أمر', teacher: 'محفّظ',
  center_manager: 'مدير مركز', admin: 'مدير النظام', super_admin: 'المدير العام',
};

/* طلبات «نسيت كلمة المرور» التي يملك هذا المستخدم معالجتها. لا تظهر إلا إن وُجد طلب:
   كلمة مرور مؤقتة تُعرض مرّة واحدة ليبلّغها المسؤول، ويغيّرها صاحبها عند الدخول. */
export default function PasswordHelpRequests() {
  const [requests, setRequests] = useState<HelpRequest[]>([]);
  const [issued, setIssued] = useState<Record<string, string>>({});
  const [busy, setBusy] = useState('');
  const [copied, setCopied] = useState('');
  const [error, setError] = useState('');

  const load = useCallback(async () => {
    try {
      const { data } = await api.get<HelpRequest[]>('/auth/password-help-requests');
      setRequests(data);
    } catch { /* القائمة ثانوية في اللوحة: إن تعذّرت لا تحجب ما سواها */ }
  }, []);

  useEffect(() => { load(); }, [load]);

  const resolve = async (r: HelpRequest) => {
    setBusy(r.id);
    setError('');
    try {
      const { data } = await api.post<{ password: string }>(`/auth/password-help-requests/${r.id}/resolve`);
      setIssued(m => ({ ...m, [r.id]: data.password }));
    } catch (err) {
      setError(errorMessage(err, 'تعذّر إصدار كلمة المرور المؤقتة'));
    } finally {
      setBusy('');
    }
  };

  const copy = async (id: string, text: string) => {
    try { await navigator.clipboard.writeText(text); setCopied(id); } catch { /* النسخ اختياري */ }
  };

  const done = (id: string) => {
    setRequests(rs => rs.filter(r => r.id !== id));
    setIssued(m => { const rest = { ...m }; delete rest[id]; return rest; });
  };

  if (requests.length === 0) return null;

  return (
    <section className="card p-5 border-[hsl(var(--lamp))]" aria-labelledby="password-help-title">
      <div className="flex items-center gap-2 mb-1">
        <KeyRound className="w-5 h-5 text-[hsl(var(--lamp-strong))]" />
        <h3 id="password-help-title" className="text-base font-bold text-[hsl(var(--ink))]">
          طلبات استعادة كلمة المرور ({requests.length})
        </h3>
      </div>
      <p className="text-sm text-[hsl(var(--ink-3))] mb-4">
        تأكّد من صاحب الطلب — باتصالٍ مثلاً — ثم أعطه كلمة مرور مؤقتة، وسيُطلب منه تغييرها عند دخوله.
      </p>

      {error && <div role="alert" className="mb-3 text-sm text-[hsl(var(--danger))]">{error}</div>}

      <ul className="divide-y divide-[hsl(var(--border))]">
        {requests.map(r => (
          <li key={r.id} className="py-3 flex flex-wrap items-center justify-between gap-3">
            <div className="min-w-0">
              <p className="font-bold text-[hsl(var(--ink))]">
                {r.name || r.username}
                <span className="text-xs font-semibold text-[hsl(var(--ink-3))] ms-2">{ROLE_LABEL[r.role || ''] || r.role}</span>
              </p>
              <p className="text-xs text-[hsl(var(--ink-3))]">
                <span dir="ltr">{r.username}</span>
                {r.phone && <> · <span dir="ltr">{r.phone}</span></>}
                {' · '}{new Date(r.requested_at).toLocaleString('ar', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })}
              </p>
            </div>

            {issued[r.id] ? (
              <div className="flex items-center gap-2">
                <code dir="ltr" className="px-3 py-1.5 rounded-[var(--radius-sm)] bg-[hsl(var(--lamp-wash))] font-bold tracking-wider">
                  {issued[r.id]}
                </code>
                <button type="button" onClick={() => copy(r.id, issued[r.id])} aria-label="نسخ كلمة المرور"
                  className="p-2 rounded-[var(--radius-sm)] hover:bg-[hsl(var(--muted))]">
                  {copied === r.id ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
                </button>
                <button type="button" onClick={() => done(r.id)} className="btn-primary text-sm px-3 py-1.5">
                  بلّغته
                </button>
              </div>
            ) : (
              <button type="button" onClick={() => resolve(r)} disabled={busy === r.id}
                className="btn-primary text-sm px-3 py-1.5 disabled:opacity-60">
                كلمة مرور مؤقتة
              </button>
            )}
          </li>
        ))}
      </ul>
    </section>
  );
}
