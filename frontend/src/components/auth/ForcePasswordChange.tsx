import React, { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import { errorMessage } from '@/lib/errors';
import MishkaatMark from '@/components/ui/MishkaatMark';

/* من دخل بكلمة مرور مؤقتة أعطاه إياها المسؤول (استعادة كلمة المرور أو إعادة تعيينها
   من الإدارة) لا يصل إلى التطبيق قبل أن يختار كلمته: المؤقتة يعرفها غيره. */
export default function ForcePasswordChange() {
  const { user, changePassword, logout } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [confirm, setConfirm] = useState('');
  const [error, setError] = useState('');
  const [submitting, setSubmitting] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!current || !next) { setError('الرجاء إدخال كلمة المرور المؤقتة والجديدة'); return; }
    if (next !== confirm) { setError('كلمة المرور الجديدة وتأكيدها غير متطابقين'); return; }
    setSubmitting(true);
    try {
      await changePassword(current, next);
    } catch (err) {
      setError(errorMessage(err, 'تعذّر تغيير كلمة المرور'));
    } finally {
      setSubmitting(false);
    }
  };

  const field = (label: string, value: string, set: (v: string) => void, hint?: string) => (
    <div>
      <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">{label}</label>
      <input type="password" value={value} onChange={e => set(e.target.value)} dir="ltr" className="form-input" />
      {hint && <p className="text-xs text-[hsl(var(--ink-3))] mt-1">{hint}</p>}
    </div>
  );

  return (
    <div className="login-bg">
      <div className="w-full max-w-[400px] animate-fade-in">
        <div className="flex flex-col items-center mb-7 text-center">
          <MishkaatMark className="w-12 h-12 text-[hsl(var(--lamp))] mb-3" title="المشكاة" />
          <h1 className="text-white text-2xl">المشكاة</h1>
          <p className="text-white/55 text-sm mt-1">نظام إدارة دور القرآن الكريم</p>
        </div>

        <div className="bg-[hsl(var(--surface))] rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] p-7">
          <h2 className="text-lg mb-2">اختر كلمة مرور جديدة</h2>
          <p className="text-sm text-[hsl(var(--ink-3))] mb-6 leading-relaxed">
            أهلاً {user?.name}. دخلت بكلمة مرور مؤقتة أعطاك إياها المسؤول — اختر الآن كلمةً لا يعرفها غيرك.
          </p>

          <form onSubmit={handleSubmit} className="space-y-4">
            {field('كلمة المرور المؤقتة', current, setCurrent)}
            {field('كلمة المرور الجديدة', next, setNext, 'ثمانية أحرف على الأقل، فيها حرف ورقم')}
            {field('تأكيد كلمة المرور الجديدة', confirm, setConfirm)}

            {error && (
              <div
                role="alert"
                className="p-3 rounded-[var(--radius-sm)] bg-[hsl(var(--danger-wash))] border border-[hsl(var(--danger)/.3)] text-[hsl(var(--danger))] text-sm text-center font-medium"
              >
                {error}
              </div>
            )}

            <button
              type="submit"
              disabled={submitting}
              className="btn-primary w-full py-3 text-base mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
            >
              {submitting ? <><LoadingSpinner size="sm" /><span>جاري الحفظ…</span></> : 'حفظ والمتابعة'}
            </button>
          </form>

          <div className="mt-5 text-center">
            <button type="button" onClick={logout}
              className="text-sm font-semibold text-[hsl(var(--lamp-strong))] hover:underline">
              تسجيل الخروج
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
