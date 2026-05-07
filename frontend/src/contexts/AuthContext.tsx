import React, { createContext, useContext, useState, useEffect, useCallback, ReactNode } from 'react';
import { authApi } from '@/services/api';
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

  const loadUser = useCallback(async () => {
    const token = localStorage.getItem('access_token');
    const savedUser = localStorage.getItem('user');
    
    if (token && savedUser) {
      try {
        setUser(JSON.parse(savedUser));
        // Optionally verify token with backend
        // const userData = await authApi.getMe();
        // setUser(userData);
      } catch (error) {
        console.error('Failed to load user:', error);
        localStorage.removeItem('access_token');
        localStorage.removeItem('user');
      }
    }
    setIsLoading(false);
  }, []);

  useEffect(() => {
    loadUser();
  }, [loadUser]);

  const login = async (username: string, password: string) => {
    setIsLoading(true);
    try {
      const response = await authApi.login(username, password);
      localStorage.setItem('access_token', response.access_token);
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
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
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
