import React, { useEffect, useState } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import api from '@/services/api';
import { useTheme } from '@/lib/theme';
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
  Award,
  User,
  Settings,
  BarChart3,
  Trophy,
  Sun,
  Moon,
  MessageSquare,
  Medal,
} from 'lucide-react';
import type { UserRole } from '@/types';
import MishkaatMark from '@/components/ui/MishkaatMark';
import { NotificationsProvider, useNotifications } from '@/contexts/NotificationsContext';

/* المجموعات: أربع عشرة وجهة في قائمة مسطّحة واحدة تجعل "لوحة التحكم" (يومية)
   و"الإعدادات" (شهرية) متساويتين في الوزن. التجميع يعيد ترتيب الأولوية. */
type NavGroup = 'daily' | 'manage' | 'system';

const GROUP_LABEL: Record<NavGroup, string> = {
  daily:  'العمل اليومي',
  manage: 'الإدارة',
  system: 'النظام',
};

interface NavItem {
  title: string;
  href: string;
  icon: React.ElementType;
  roles: UserRole[];
  group: NavGroup;
}

const navItems: NavItem[] = [
  { title: 'لوحة التحكم', href: '/dashboard',    icon: LayoutDashboard, roles: ['admin','super_admin','center_manager','teacher','student','parent'], group: 'daily' },
  { title: 'المراكز',     href: '/centers',       icon: Building2,       roles: ['admin'], group: 'manage' },
  { title: 'المحفظون',    href: '/teachers',      icon: GraduationCap,   roles: ['center_manager'], group: 'manage' },
  { title: 'الطلاب',      href: '/students',      icon: Users,           roles: ['center_manager','teacher'], group: 'daily' },
  // [قرار المالك 2026-09-06] صفحة الحلقات إدارةُ حلقات، وشيخُ الحلقة لا
  // يُنشئ حلقةً ولا يُسنِد شيوخاً — فلا داعي لها عنده. وهو يعرف حلقته من
  // كل شاشة يعمل فيها.
  { title: 'الحلقات',     href: '/halaqat',       icon: BookOpen,        roles: ['center_manager'], group: 'manage' },
  { title: 'التسميع',     href: '/recitations',   icon: FileText,        roles: ['center_manager','teacher','student','parent'], group: 'daily' },
  { title: 'الحضور والغياب',href: '/attendance',  icon: Calendar,        roles: ['center_manager','teacher'], group: 'daily' },
  { title: 'المالية',     href: '/finance',       icon: DollarSign,      roles: ['center_manager'], group: 'manage' },
  { title: 'التقارير',    href: '/reports',       icon: BarChart3,       roles: ['center_manager'], group: 'manage' },
  { title: 'نظام الترتيب',href: '/rankings',      icon: Trophy,          roles: ['center_manager','teacher'], group: 'manage' },
  { title: 'لوحات الصدارة',href: '/leaderboards', icon: Medal,           roles: ['center_manager','teacher','student','parent'], group: 'daily' },
  { title: 'خطة المراجعة',href: '/review-plans',  icon: RefreshCw,       roles: ['center_manager','teacher','student','parent'], group: 'daily' },
  { title: 'الجدول الدراسي', href: '/academic-schedules', icon: Calendar,      roles: ['center_manager','teacher','student','parent'], group: 'manage' },
  // [قرار المالك 2026-09-06] المسابقات تظهر لشيخ الحلقة فقط إن كان عضواً في
  // لجنة تحكيم مسابقة جارية — يُحسم ذلك في وقت التشغيل لا هنا (isJudge).
  { title: 'المسابقات القرآنية', href: '/competitions',   icon: Trophy,        roles: ['center_manager','student'], group: 'manage' },
  // الشهادات: يُصدرها المدير، ويراها المعلّم والطالب ووليّه ويطبعونها
  { title: 'الشهادات',     href: '/certificates',  icon: Award,           roles: ['center_manager','teacher','student','parent'], group: 'manage' },
  { title: 'المراسلات',    href: '/bulk-messages',     icon: MessageSquare,   roles: ['admin','super_admin','center_manager','teacher','student','parent'], group: 'manage' },
  { title: 'سجل النشاط',  href: '/audit-logs',    icon: Shield,          roles: ['admin'], group: 'system' },
  { title: 'الملف الشخصي',href: '/profile',       icon: User,            roles: ['admin','super_admin','center_manager','teacher','student','parent'], group: 'system' },
  { title: 'الإعدادات',   href: '/settings',      icon: Settings,        roles: ['admin','super_admin','center_manager','teacher','student','parent'], group: 'system' },
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
  const { user: currentUser } = useAuth();
  return (
    <NotificationsProvider enabled={!!currentUser && currentUser.role !== 'admin'}>
      <DashboardShell>{children}</DashboardShell>
    </NotificationsProvider>
  );
}

function DashboardShell({ children }: { children: React.ReactNode }) {
  // عدّاد الإشعارات غير المقروءة — مشترك مع صفحة الإشعارات، وقناة SSE واحدة
  const { unread } = useNotifications();
  const { user, logout, hasRole } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [sidebarOpen, setSidebarOpen] = useState(false);
  // المظهر من مصدرٍ واحد يشترك فيه هذا الزرّ وصفحة الإعدادات (lib/theme.ts)
  const { theme, toggle: toggleDarkMode } = useTheme();
  const darkMode = theme === 'dark';

  /**
   * المسابقات لشيخ الحلقة: تظهر وتختفي بحسب عضويّته في لجنة تحكيمٍ **جارية**.
   *
   * [قرار المالك 2026-09-06] التحكيم مهمّةٌ لها وقت لا صلاحيةٌ دائمة: يراها
   * المحكّم ما دامت المسابقة قائمة، فإذا اعتُمدت نتائجُها اختفى البند عنه.
   * والخادم يمنعه من الرصد على كل حال — هذا إخفاء البند لا حراسته.
   */
  const [judgingNow, setJudgingNow] = useState(false);
  useEffect(() => {
    let alive = true;
    if (user?.role !== 'teacher') { setJudgingNow(false); return; }
    api.get<{ is_judge: boolean }>('/competitions/my-role')
      .then(r => { if (alive) setJudgingNow(!!r.data.is_judge); })
      .catch(() => { if (alive) setJudgingNow(false); });
    return () => { alive = false; };
  }, [user?.role, user?.id]);

  const filteredNavItems = navItems.filter(item => {
    if (item.href === '/competitions' && user?.role === 'teacher') return judgingNow;
    return item.roles.some(r => hasRole(r));
  });
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
              {/* علامة المشكاة نفسها التي على أيقونة التطبيق — كانت هنا أيقونة
                  كتاب عامّة، فلا يرى المستخدم داخل التطبيق ما ثبّته على شاشته */}
              <div className="w-11 h-11 rounded-xl flex items-center justify-center shadow-lg bg-[hsl(var(--niche-2))] border border-white/10">
                <MishkaatMark className="w-7 h-7 text-[hsl(var(--lamp))]" title="المشكاة" />
              </div>
              <div>
                <h1 className="font-bold text-white text-sm leading-tight">نظام المشكاة</h1>
                <p className="text-white/50 text-[10px] font-semibold tracking-widest" dir="ltr">MISHKAAT</p>
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
            <div className="m-4 p-4 rounded-[var(--radius)] bg-white/6 border border-white/8">
              <div className="flex items-center gap-3">
                <div className="w-11 h-11 rounded-xl gradient-primary flex items-center justify-center text-white font-bold text-sm shadow-lg">
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
          <nav className="flex-1 px-3 py-2 overflow-y-auto">
            {(['daily', 'manage', 'system'] as const).map(group => {
              const items = filteredNavItems.filter(i => i.group === group);
              if (items.length === 0) return null;
              return (
                <div key={group}>
                  <p className="nav-group-label">{GROUP_LABEL[group]}</p>
                  <div className="space-y-0.5">
                    {items.map(item => {
                      const isActive = location.pathname === item.href;
                      return (
                        <Link
                          key={item.href}
                          to={item.href}
                          onClick={() => setSidebarOpen(false)}
                          aria-current={isActive ? 'page' : undefined}
                          className={cn(
                            'nav-item flex items-center gap-3 px-4 py-2.5 text-sm',
                            isActive ? 'active' : 'text-white/60 hover:text-white'
                          )}
                        >
                          <item.icon className="w-[18px] h-[18px] shrink-0" strokeWidth={1.75} />
                          <span className="flex-1">{item.title}</span>
                        </Link>
                      );
                    })}
                  </div>
                </div>
              );
            })}
          </nav>

          {/* Logout */}
          <div className="p-4 border-t border-white/8">
            <button
              onClick={handleLogout}
              aria-label="تسجيل الخروج من النظام"
              className="w-full flex items-center gap-3 px-4 py-3 rounded-xl text-sm font-medium
                         text-white/60 hover:text-red-400 hover:bg-[hsl(var(--danger))]/10 transition-all"
            >
              <LogOut className="w-5 h-5" aria-hidden="true" />
              <span>تسجيل الخروج</span>
            </button>
          </div>
        </div>
      </aside>

      {/* Main.
          min-w-0 ليست تجميلاً: هذا العمود عنصر flex، وعرضه الأدنى الافتراضي
          (min-width:auto) هو عرض أعرض محتوى غير قابل للانكماش داخله. فأيّ بطاقة
          فيها اسم طويل أو رقم لا ينكسر كانت تدفع التطبيق كلَّه أعرض من الشاشة —
          صفحة «التقارير» كانت 676 بكسل على شاشة 375، تُمرَّر أفقياً بكاملها بما
          فيها الشريط العلوي. مع min-w-0 يبقى العمود بعرض الشاشة ويتولّى المحتوى
          أمر فيضانه بنفسه (التفافاً أو تمريراً داخل صندوقه). */}
      <div className="flex-1 min-w-0 lg:mr-72 flex flex-col min-h-screen">
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
                  aria-label={unread > 0 ? `الإشعارات — ${unread} غير مقروء` : "الإشعارات"}
                  className="relative p-2 rounded-xl hover:bg-[hsl(var(--muted))] transition-colors text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]"
                >
                  <Bell className="w-5 h-5" aria-hidden="true" />
                  {/* كانت النقطة الحمراء ظاهرة دائماً بلا علاقة بوجود شيء غير مقروء —
                      شارةٌ تقول «لديك جديد» في كل الأحوال تُعلِّم المستخدمَ تجاهلَها.
                      صارت تظهر عند وجود غير مقروء فعلاً، وتحمل عددَه. */}
                  {unread > 0 && (
                    <span className="absolute -top-0.5 -left-0.5 min-w-[18px] h-[18px] px-1 flex items-center justify-center text-[10px] font-bold rounded-full bg-[hsl(var(--danger))] text-white border-2 border-[hsl(var(--surface))] tabular-nums">
                      {unread > 99 ? '99+' : unread}
                    </span>
                  )}
                </Link>
              )}
              {user && (
                <Link to="/profile">
                  <div className="w-9 h-9 rounded-xl gradient-primary flex items-center justify-center text-white font-bold text-xs shadow-md">
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
