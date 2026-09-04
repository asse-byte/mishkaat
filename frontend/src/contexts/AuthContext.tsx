import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { authApi, tokenStore, setSessionExpiredHandler, restoreSession } from '@/services/api';
import type { User, UserRole } from '@/types';

interface AuthContextType {
  user: User | null;
  isLoading: boolean;
  isAuthenticated: boolean;
  login: (username: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  hasRole: (roles: UserRole | UserRole[]) => boolean;
}

const AuthContext = createContext<AuthContextType | undefined>(undefined);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [isLoading, setIsLoading] = useState(true);

  /**
   * [إصلاح 2026-09-04] استعادة الجلسة من كعكة httpOnly لا من localStorage.
   *
   * لم يعد هناك توكن محفوظ في المتصفّح تقرؤه JavaScript، فالإقلاع يبدأ بلا توكن
   * في الذاكرة ويطلب واحداً من /auth/refresh — تصل الكعكة وحدها فيعود المستخدم
   * إلى جلسته. فإن لم تكن هناك كعكة صالحة فلا جلسة، وهو التصرّف الصحيح.
   *
   * ويبقى ما كان: الخادم هو مصدر الدور، والنسخة المحفوظة للعرض السريع فقط.
   */
  const loadUser = useCallback(async () => {
    // عرض متفائل من النسخة المحفوظة (سرعة فقط — ليست مصدر ثقة ولا اعتماداً)
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      try { setUser(JSON.parse(savedUser)); } catch { localStorage.removeItem('user'); }
    }

    // زائر لم يدخل قطّ: لا كعكة ولا ملف محفوظ، فلا داعي لنداء تجديد يعود 401
    // على كل فتحة لصفحة عامة (صفحة الهبوط والتسجيل يراهما غير المسجَّلين).
    if (!savedUser) {
      setIsLoading(false);
      return;
    }

    const restored = await restoreSession();
    if (!restored) {
      tokenStore.clear();
      setUser(null);
      setIsLoading(false);
      return;
    }

    try {
      const verified = await authApi.getMe();
      localStorage.setItem('user', JSON.stringify(verified));
      setUser(verified);
    } catch (error: any) {
      const status = error?.response?.status;
      if (status === 401 || status === 403) {
        tokenStore.clear();
        setUser(null);
      }
      // انقطاع شبكة عابر: نُبقي ما استعدناه ولا نطرد المستخدم
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  // انتهاء الجلسة قد يقع داخل معترض axios؛ هذا يُفرّغ حالة React أيضاً لا التخزين وحده
  useEffect(() => {
    setSessionExpiredHandler(() => {
      setUser(null);
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    });
    return () => setSessionExpiredHandler(null);
  }, []);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await authApi.login(username, password);
      // توكن الوصول إلى الذاكرة؛ وتوكن التجديد وصل في كعكة httpOnly لا تراها هذه الشيفرة
      tokenStore.set(response.access_token);
      localStorage.setItem('user', JSON.stringify(response.user));
      setUser(response.user);
    } finally {
      setIsLoading(false);
    }
  };

  const logout = async () => {
    try {
      await authApi.logout();
    } catch (error) {
      console.error('Logout error:', error);
    } finally {
      tokenStore.clear();
      setUser(null);
    }
  };

  const hasRole = (roles: UserRole | UserRole[]): boolean => {
    if (!user) return false;
    const roleArray = Array.isArray(roles) ? roles : [roles];
    return roleArray.includes(user.role);
  };

  return (
    <AuthContext.Provider
      value={{
        user,
        isLoading,
        isAuthenticated: !!user,
        login,
        logout,
        hasRole,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (context === undefined) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
}
