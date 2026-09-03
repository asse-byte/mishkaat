import React, { createContext, useContext, useState, useEffect, useCallback } from 'react';
import type { ReactNode } from 'react';
import { authApi, tokenStore, setSessionExpiredHandler } from '@/services/api';
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
   * [إصلاح 2026-09-03] الجلسة تُتحقَّق من الخادم عند الإقلاع.
   *
   * قبله: الدور يُقرأ من localStorage ويُصدَّق كما هو، ونداء getMe معطَّل بتعليق. فمن يفتح أدوات
   * المطوّر ويكتب role: 'super_admin' يرى كل شاشات الإدارة. الخادم يظل يمنع البيانات (تحققتُ من
   * ذلك في مراجعة الخادم)، لكن الواجهة تعرض شاشات ستفشل، وأزراراً لا تعمل، وقوائم فارغة بلا سبب.
   * وكانت الجلسة المنتهية أو الملغاة تبدو صالحة حتى أول نداء يفشل.
   *
   * بعده: الخادم هو مصدر الدور. النسخة المحفوظة تُعرض فوراً لتفادي وميض شاشة الدخول، ثم
   * يُصحّحها ردّ /auth/me — أو تُمسح الجلسة إن رفضه الخادم.
   */
  const loadUser = useCallback(async () => {
    const token = tokenStore.access();
    if (!token) {
      setIsLoading(false);
      return;
    }

    // عرض متفائل من النسخة المحفوظة (سرعة فقط — ليست مصدر ثقة)
    const savedUser = localStorage.getItem('user');
    if (savedUser) {
      try {
        setUser(JSON.parse(savedUser));
      } catch {
        localStorage.removeItem('user');
      }
    }

    try {
      const verified = await authApi.getMe();
      localStorage.setItem('user', JSON.stringify(verified));
      setUser(verified);
    } catch (error: any) {
      // 401 يعالجها معترض التجديد؛ ما يصل هنا يعني أن الجلسة انتهت فعلاً أو أن الحساب عُطّل
      const status = error?.response?.status;
      if (status === 401 || status === 403) {
        tokenStore.clear();
        setUser(null);
      }
      // انقطاع شبكة عابر: نُبقي العرض المتفائل ولا نطرد المستخدم
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
      // يحفظ توكن التجديد أيضاً — بدونه تنتهي الجلسة بعد ساعة بلا رجعة
      tokenStore.save(response);
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
