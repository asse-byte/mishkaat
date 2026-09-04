import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import { Eye, EyeOff } from 'lucide-react';
import MishkaatMark from '@/components/ui/MishkaatMark';

/* حُذفت قائمة «اختر الدور» (2026-09-04).
   كانت تطلب من المستخدم اختيار دوره ثم لا تُرسله إلى الخادم إطلاقاً:
   selectedRole لم يكن يُقرأ في handleSubmit. الدور يأتي من الحساب نفسه
   بعد المصادقة، فكان الحقل خطوةً زائدة توحي بأن للاختيار أثراً — ومن اختار
   الدور الخطأ ودخل بنجاح يظنّ أن في النظام عطلاً. */

export default function Login() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    if (!username || !password) { setError('الرجاء إدخال اسم المستخدم وكلمة المرور'); return; }
    try {
      await login(username, password);
      navigate('/dashboard');
    } catch {
      setError('اسم المستخدم أو كلمة المرور غير صحيحة');
    }
  };

  return (
    <div className="login-bg">
      {/* العلامة خارج البطاقة: المصباح في الضوء الساقط من أعلى الكوّة */}
      <div className="w-full max-w-[400px] animate-fade-in">
        <div className="flex flex-col items-center mb-7 text-center">
          <MishkaatMark className="w-12 h-12 text-[hsl(var(--lamp))] mb-3" title="مشكاة" />
          <h1 className="text-white text-2xl">مشكاة</h1>
          <p className="text-white/55 text-sm mt-1">نظام إدارة مراكز تحفيظ القرآن الكريم</p>
        </div>

        <div className="bg-[hsl(var(--surface))] rounded-[var(--radius-lg)] shadow-[var(--shadow-lg)] p-7">
          <h2 className="text-lg mb-6">تسجيل الدخول</h2>

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Username */}
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">اسم المستخدم</label>
            <input
              type="text"
              placeholder="أدخل اسم المستخدم"
              value={username}
              onChange={e => setUsername(e.target.value)}
              dir="ltr"
              className="form-input"
            />
          </div>

          {/* Password */}
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">كلمة المرور</label>
            <div className="relative">
              <input
                type={showPassword ? 'text' : 'password'}
                placeholder="أدخل كلمة المرور"
                value={password}
                onChange={e => setPassword(e.target.value)}
                dir="ltr"
                className="form-input pl-12"
              />
              <button
                type="button"
                aria-label={showPassword ? 'إخفاء كلمة المرور' : 'إظهار كلمة المرور'}
                onClick={() => setShowPassword(!showPassword)}
                className="absolute left-4 top-3.5 text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))] transition-colors"
              >
                {showPassword ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

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
            disabled={isLoading}
            className="btn-primary w-full py-3 text-base mt-2 disabled:opacity-60 disabled:cursor-not-allowed"
          >
            {isLoading ? <><LoadingSpinner size="sm" /><span>جاري الدخول…</span></> : 'تسجيل الدخول'}
          </button>
        </form>

          <div className="mt-5 text-center">
            <button className="text-sm font-semibold text-[hsl(var(--lamp-strong))] hover:underline">
              نسيت كلمة المرور؟
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
