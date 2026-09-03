import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import { Eye, EyeOff, ChevronDown } from 'lucide-react';
import MishkaatMark from '@/components/ui/MishkaatMark';

const roles = [
  { value: 'admin',          label: 'المدير العام'  },
  { value: 'center_manager', label: 'مدير المركز'  },
  { value: 'teacher',        label: 'معلم'          },
  { value: 'student',        label: 'طالب'          },
  { value: 'parent',         label: 'ولي أمر'       },
];

export default function Login() {
  const navigate = useNavigate();
  const { login, isLoading } = useAuth();
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [selectedRole, setSelectedRole] = useState('');
  const [dropdownOpen, setDropdownOpen] = useState(false);
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

  const selectedRoleLabel = roles.find(r => r.value === selectedRole)?.label || '';

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
          {/* Role dropdown */}
          <div>
            <label className="block text-sm font-semibold text-[hsl(var(--ink-2))] mb-1.5">اختر الدور</label>
            <div className="relative">
              <button
                type="button"
                onClick={() => setDropdownOpen(!dropdownOpen)}
                className="form-input flex items-center justify-between cursor-pointer text-right w-full"
              >
                <span className={selectedRole ? 'text-[hsl(var(--foreground))]' : 'text-[hsl(var(--muted-foreground))]'}>
                  {selectedRoleLabel || 'اختر نوع حسابك'}
                </span>
                <ChevronDown className={`w-5 h-5 text-[hsl(var(--muted-foreground))] transition-transform ${dropdownOpen ? 'rotate-180' : ''}`} />
              </button>
              {dropdownOpen && (
                <div className="absolute top-full right-0 left-0 mt-1 bg-white border border-[hsl(var(--border))] rounded-xl shadow-xl z-50 overflow-hidden animate-slide-in-up">
                  {roles.map(r => (
                    <button
                      key={r.value}
                      type="button"
                      onClick={() => {
                        setSelectedRole(r.value);
                        setDropdownOpen(false);
                      }}
                      className={`w-full px-4 py-3 text-right text-sm font-medium hover:bg-[hsl(var(--accent))] transition-colors border-b border-[hsl(var(--border))] last:border-b-0
                        ${selectedRole === r.value ? 'bg-[hsl(var(--accent))] text-[hsl(var(--primary))] font-bold' : 'text-[hsl(var(--foreground))]'}`}
                    >
                      {r.label}
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>

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
