import React, { useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { cn, getInitials } from '@/lib/utils';
import {
  BookOpen,
  LayoutDashboard,
  Users,
  GraduationCap,
  Building2,
  Calendar,
  DollarSign,
  FileText,
  LogOut,
  Menu,
  X,
  ChevronLeft,
  RefreshCw,
  Bell,
  Shield,
  User,
  Settings,
  BarChart3,
  Trophy,
  Sun,
  Moon,
  MessageSquare,
} from 'lucide-react';
import type { UserRole } from '@/types';

interface NavItem {
  title: string;
  href: string;
  icon: React.ElementType;
  roles: UserRole[];
}

const navItems: NavItem[] = [
  { title: 'لوحة التحكم', href: '/dashboard',    icon: LayoutDashboard, roles: ['admin','super_admin','center_manager','teacher','student','parent'] },
  { title: 'المراكز',     href: '/centers',       icon: Building2,       roles: ['admin'] },
  { title: 'المحفظون',    href: '/teachers',      icon: GraduationCap,   roles: ['center_manager'] },
  { title: 'الطلاب',      href: '/students',      icon: Users,           roles: ['center_manager','teacher'] },
  { title: 'الحلقات',     href: '/halaqat',       icon: BookOpen,        roles: ['center_manager','teacher'] },
  { title: 'التسميع',     href: '/recitations',   icon: FileText,        roles: ['center_manager','teacher','student','parent'] },
  { title: 'الحضور والغياب',href: '/attendance',  icon: Calendar,        roles: ['center_manager','teacher'] },
  { title: 'المالية',     href: '/finance',       icon: DollarSign,      roles: ['center_manager'] },
  { title: 'التقارير',    href: '/reports',       icon: BarChart3,       roles: ['center_manager'] },
  { title: 'نظام الترتيب',href: '/rankings',      icon: Trophy,          roles: ['center_manager','teacher'] },
  { title: 'خطط المراجعة',href: '/review-plans',  icon: RefreshCw,       roles: ['center_manager','teacher'] },
  { title: 'الجدول الدراسي', href: '/academic-schedules', icon: Calendar,      roles: ['center_manager','teacher','student','parent'] },
  { title: 'المسابقات القرآنية', href: '/competitions',   icon: Trophy,        roles: ['center_manager','teacher','student'] },
  { title: 'البث الجماعي',  href: '/bulk-messages',     icon: MessageSquare,   roles: ['admin','super_admin','center_manager','teacher'] },
  { title: 'سجل النشاط',  href: '/audit-logs',    icon: Shield,          roles: ['admin'] },
  { title: 'الملف الشخصي',href: '/profile',       icon: User,            roles: ['admin','super_admin','center_manager','teacher','student','parent'] },
  { title: 'الإعدادات',   href: '/settings',      icon: Settings,        roles: ['admin','super_admin','center_manager','teacher','student','parent'] },
];

const roleLabels: Record<UserRole, string> = {
  admin: 'مدير النظام',
  super_admin: 'المدير العام (الأوقاف/الوزارة)',
  center_manager: 'مدير المركز',
  teacher: 'محفظ',
  student: 'طالب',
  parent: 'ولي أمر',
};

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  const { user, logout, hasRole } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const [darkMode, setDarkMode] = useState(() => {
    const saved = localStorage.getItem('theme');
    if (saved === 'dark') {
      document.documentElement.classList.add('dark');
      return true;
    } else {
      document.documentElement.classList.remove('dark');
      return false;
    }
  });

  const toggleDarkMode = () => {
    if (darkMode) {
      document.documentElement.classList.remove('dark');
      localStorage.setItem('theme', 'light');
      setDarkMode(false);
    } else {
      document.documentElement.classList.add('dark');
      localStorage.setItem('theme', 'dark');
      setDarkMode(true);
    }
  };

  const filteredNavItems = navItems.filter(item => item.roles.some(r => hasRole(r)));
  const currentTitle = filteredNavItems.find(item => item.href === location.pathname)?.title || 'لوحة التحكم';

  const handleLogout = async () => {
    await logout();
    navigate('/login');
  };

  return (
    <div className="min-h-screen bg-[hsl(var(--background))] flex" dir="rtl">
      {/* Overlay mobile */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/50 backdrop-blur-sm lg:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      {/* Sidebar */}
      <aside
        id="sidebar"
        className={cn(
          'fixed top-0 right-0 z-50 h-full w-72 gradient-sidebar shadow-2xl transition-transform duration-300 lg:translate-x-0 flex flex-col',
          sidebarOpen ? 'translate-x-0' : 'translate-x-full lg:translate-x-0'
        )}
      >
        <div className="flex flex-col h-full">

          {/* Logo */}
          <div className="flex items-center justify-between p-5 border-b border-white/8">
            <div className="flex items-center gap-3">
              <div className="w-11 h-11 gradient-primary rounded-xl flex items-center justify-center shadow-lg">
                <BookOpen className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="font-black text-white text-sm leading-tight">نظام المشكاة</h1>
                <p className="text-white/45 text-[10px] font-bold tracking-widest" dir="ltr">MISHKAAT</p>
              </div>
            </div>
            <button
              onClick={() => setSidebarOpen(false)}
              aria-label="إغلاق القائمة الجانبية"
              className="lg:hidden p-1.5 rounded-lg text-white/50 hover:text-white hover:bg-white/10 transition-all"
            >
              <X className="w-5 h-5" aria-hidden="true" />
            </button>
          </div>

          {/* User card */}
          {user && (
            <div className="m-4 p-4 rounded-2xl bg-white/6 border border-white/8">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl gradient-primary flex items-center justify-center text-white font-black text-sm shadow-lg">
                  {getInitials(user.name)}
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-white font-semibold text-sm truncate">{user.name}</p>
                  <span className="inline-block text-[10px] font-bold px-2.5 py-0.5 rounded-full mt-0.5 badge-gold">
                    {roleLabels[user.role]}
                  </span>
                </div>
              </div>
            </div>
          )}

          {/* Nav */}
          <nav className="flex-1 px-3 py-2 space-y-0.5 overflow-y-auto">
            {filteredNavItems.map(item => {
              const isActive = location.pathname === item.href;
              return (
                <Link
                  key={item.href}
                  to={item.href}
                  onClick={() => setSidebarOpen(false)}
                  className={cn(
                    'nav-item flex items-center gap-3 px-4 py-3 text-sm font-medium transition-all',
                    isActive
                      ? 'active text-white shadow-lg'
                      : 'text-white/60 hover:text-white'
                  )}
                >
                  <item.icon className="w-4.5 h-4.5 shrink-0 w-5 h-5" />
                  <span className="flex-1">{item.title}</span>
                  {isActive && <ChevronLeft className="w-4 h-4 opacity-60" />}
                </Link>
              );
            })}
          </nav>

          {/* Logout */}
          <div className="p-4 border-t border-white/8">
            <button
              onClick={handleLogout}
              aria-label="تسجيل الخروج من النظام"
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                         text-white/60 hover:text-red-400 hover:bg-red-500/10 transition-all"
            >
              <LogOut className="w-5 h-5" aria-hidden="true" />
              <span>تسجيل الخروج</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main */}
      <div className="flex-1 lg:mr-72 flex flex-col min-h-screen">
        {/* Topbar */}
        <header className="sticky top-0 z-30 bg-white/92 backdrop-blur-md border-b border-[hsl(var(--border))] px-5 py-3 shadow-sm">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-3">
              <button
                onClick={() => setSidebarOpen(true)}
                aria-label="فتح القائمة الجانبية"
                className="lg:hidden p-2 rounded-xl hover:bg-[hsl(var(--muted))] transition-colors text-[hsl(var(--foreground))]"
              >
                <Menu className="w-6 h-6" aria-hidden="true" />
              </button>
              <div>
                <h2 className="font-bold text-[hsl(var(--foreground))] text-base">{currentTitle}</h2>
                <p className="text-xs text-[hsl(var(--muted-foreground))] hidden sm:block">
                  {new Date().toLocaleDateString('ar-SA', { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' })}
                </p>
              </div>
            </div>

            <div className="flex items-center gap-2">
              {/* Theme Toggle Button */}
              <button
                onClick={toggleDarkMode}
                aria-label="تغيير المظهر"
                className="p-2 rounded-xl hover:bg-[hsl(var(--muted))] transition-colors text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
              >
                {darkMode ? <Sun className="w-5 h-5" /> : <Moon className="w-5 h-5" />}
              </button>

              {user?.role !== 'admin' && (
                <Link
                  to="/notifications"
                  aria-label="الإشعارات"
                  className="relative p-2 rounded-xl hover:bg-[hsl(var(--muted))] transition-colors text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                >
                  <Bell className="w-5 h-5" aria-hidden="true" />
                  <span className="absolute top-2 left-2 w-2 h-2 bg-red-500 rounded-full border-2 border-white" aria-hidden="true" />
                </Link>
              )}
              {user && (
                <Link to="/profile">
                  <div className="w-9 h-9 rounded-xl gradient-primary flex items-center justify-center text-white font-black text-xs shadow-md">
                    {getInitials(user.name)}
                  </div>
                </Link>
              )}
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 p-5 md:p-7">
          {children}
        </main>
      </div>
    </div>
  );
}
