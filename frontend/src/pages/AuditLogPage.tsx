import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  ShieldAlert, Search, Calendar, Activity,
  ChevronRight, ChevronLeft, LogIn, LogOut,
  KeyRound, User, RefreshCw, Wallet, Building2, Award, BookOpen, UserPlus,
} from 'lucide-react';
import api from '@/services/api';
import PageHeader from '@/components/ui/PageHeader';

interface AuditLog {
  id: string;
  action: string;
  username: string;
  role?: string;
  actor_name?: string;
  center_name?: string;
  ip?: string;
  timestamp: string;
}

const actionConfig: Record<string, { label: string; cls: string; icon: typeof LogIn }> = {
  LOGIN_SUCCESS:    { label: 'تسجيل دخول',    cls: 'bg-emerald-100 text-emerald-700', icon: LogIn      },
  LOGIN_FAILED:     { label: 'محاولة فاشلة',   cls: 'bg-red-100 text-red-700',         icon: ShieldAlert },
  LOGOUT:           { label: 'تسجيل خروج',    cls: 'bg-gray-100 text-gray-600',        icon: LogOut     },
  PASSWORD_CHANGED: { label: 'تغيير مرور',    cls: 'bg-purple-100 text-purple-700',    icon: KeyRound   },
  // [إصلاح 2026-10-22] كانت الأنواع الأربعة أعلاه وحدها معرَّفة، فيظهر الباقي رمزاً
  // إنجليزياً («collect_fee») ولا يُختار من الفلتر. هذه كل الأنواع التي يكتبها الخادم.
  LOGIN_DENIED_PENDING:  { label: 'دخول مرفوض: مركز قيد المراجعة', cls: 'bg-amber-100 text-amber-700', icon: ShieldAlert },
  LOGIN_DENIED_DISABLED: { label: 'دخول مرفوض: حساب موقوف',  cls: 'bg-red-100 text-red-700',      icon: ShieldAlert },
  PASSWORD_RESET_VIA_CODE: { label: 'استعادة كلمة المرور',   cls: 'bg-purple-100 text-purple-700', icon: KeyRound },
  ADMIN_RESET_PASSWORD:  { label: 'إعادة تعيين مرور (الإدارة)', cls: 'bg-purple-100 text-purple-700', icon: KeyRound },
  ACCOUNT_PASSWORD_RESET: { label: 'إعادة تعيين مرور حساب', cls: 'bg-purple-100 text-purple-700', icon: KeyRound },
  ACCOUNT_ISSUED:        { label: 'إصدار حساب',             cls: 'bg-sky-100 text-sky-700',       icon: UserPlus },
  PROFILE_UPDATED:       { label: 'تحديث الملف الشخصي',     cls: 'bg-gray-100 text-gray-600',     icon: User },
  PUBLIC_REGISTER_CENTER: { label: 'طلب تسجيل مركز',        cls: 'bg-sky-100 text-sky-700',       icon: Building2 },
  ADMIN_REGISTER_CENTER: { label: 'تسجيل مركز (الإدارة)',   cls: 'bg-sky-100 text-sky-700',       icon: Building2 },
  SUPER_REGISTER_CENTER: { label: 'تسجيل مركز (المدير العام)', cls: 'bg-sky-100 text-sky-700',    icon: Building2 },
  CENTER_APPROVED:       { label: 'اعتماد مركز',            cls: 'bg-emerald-100 text-emerald-700', icon: Building2 },
  CENTER_REJECTED:       { label: 'رفض مركز',               cls: 'bg-red-100 text-red-700',       icon: Building2 },
  SUPER_CENTER_STATUS_CHANGE: { label: 'إيقاف/تفعيل مركز',  cls: 'bg-amber-100 text-amber-700',   icon: Building2 },
  CENTER_LOGO_UPDATED:   { label: 'تحديث شعار المركز',      cls: 'bg-gray-100 text-gray-600',     icon: Building2 },
  TEACHER_TRANSFERRED:   { label: 'نقل محفّظ',              cls: 'bg-sky-100 text-sky-700',       icon: User },
  collect_fee:           { label: 'تحصيل رسوم',             cls: 'bg-emerald-100 text-emerald-700', icon: Wallet },
  update_fee:            { label: 'تعديل رسوم',             cls: 'bg-amber-100 text-amber-700',   icon: Wallet },
  void_fee:              { label: 'إلغاء رسوم',             cls: 'bg-red-100 text-red-700',       icon: Wallet },
  pay_salary:            { label: 'صرف راتب',               cls: 'bg-emerald-100 text-emerald-700', icon: Wallet },
  update_salary:         { label: 'تعديل راتب',             cls: 'bg-amber-100 text-amber-700',   icon: Wallet },
  void_salary:           { label: 'إلغاء راتب',             cls: 'bg-red-100 text-red-700',       icon: Wallet },
  create_expense:        { label: 'إضافة مصروف',            cls: 'bg-emerald-100 text-emerald-700', icon: Wallet },
  update_expense:        { label: 'تعديل مصروف',            cls: 'bg-amber-100 text-amber-700',   icon: Wallet },
  delete_expense:        { label: 'إبطال مصروف',            cls: 'bg-red-100 text-red-700',       icon: Wallet },
  UPDATE_RECITATION:     { label: 'تعديل تسميع',            cls: 'bg-amber-100 text-amber-700',   icon: BookOpen },
  DELETE_RECITATION:     { label: 'حذف تسميع',              cls: 'bg-red-100 text-red-700',       icon: BookOpen },
  UPDATE_ATTENDANCE:     { label: 'تعديل حضور',             cls: 'bg-amber-100 text-amber-700',   icon: Calendar },
  DELETE_ATTENDANCE:     { label: 'حذف حضور',               cls: 'bg-red-100 text-red-700',       icon: Calendar },
  EXPORT_STUDENTS:       { label: 'تصدير بيانات الطلاب',    cls: 'bg-gray-100 text-gray-600',     icon: User },
  COMPETITION_CREATED:   { label: 'إنشاء مسابقة',           cls: 'bg-sky-100 text-sky-700',       icon: Award },
  COMPETITION_APPROVED:  { label: 'اعتماد نتائج مسابقة',    cls: 'bg-emerald-100 text-emerald-700', icon: Award },
  CERTIFICATE_ISSUED:    { label: 'إصدار شهادة',            cls: 'bg-emerald-100 text-emerald-700', icon: Award },
  CERTIFICATE_REVOKED:   { label: 'إلغاء شهادة',            cls: 'bg-red-100 text-red-700',       icon: Award },
};

const roleLabels: Record<string, string> = {
  admin: 'مدير النظام', center_manager: 'مدير مركز',
  teacher: 'محفظ', student: 'طالب', parent: 'ولي أمر',
  super_admin: 'المدير العام',
};

export default function AuditLogPage() {
  const { user } = useAuth();
  const [logs, setLogs]         = useState<AuditLog[]>([]);
  const [loading, setLoading]   = useState(true);
  const [page, setPage]         = useState(0);
  const limit = 50;

  // Filters
  const [search, setSearch]         = useState('');
  const [filterAction, setFilterAction] = useState('');
  const [filterDate, setFilterDate] = useState('');

  const fetchLogs = useCallback(async () => {
    if (user?.role !== 'admin') return;
    setLoading(true);
    try {
      const action = filterAction ? `&action=${encodeURIComponent(filterAction)}` : '';
      const res = await api.get(`/audit-logs?skip=${page * limit}&limit=${limit}${action}`);
      setLogs(res.data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [page, user, filterAction]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  if (user?.role !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-20 h-20 bg-red-100 rounded-[var(--radius-lg)] flex items-center justify-center mb-4 shadow-lg">
          <ShieldAlert className="w-10 h-10 text-red-600" />
        </div>
        <h2 className="text-2xl font-bold text-[hsl(var(--foreground))]">غير مصرح بالوصول</h2>
        <p className="text-[hsl(var(--muted-foreground))] mt-2 text-sm">هذه الصفحة مخصصة لمدير النظام فقط.</p>
      </div>
    );
  }

  // Apply client-side filters
  const filtered = logs.filter(log => {
    const matchSearch = !search ||
      (log.username || '').toLowerCase().includes(search.toLowerCase()) ||
      (log.actor_name || '').includes(search) ||
      (log.center_name || '').includes(search) ||
      (log.role || '').includes(search) ||
      (roleLabels[log.role || ''] || '').includes(search);
    const matchAction = !filterAction || log.action === filterAction;
    const matchDate   = !filterDate || log.timestamp?.startsWith(filterDate);
    return matchSearch && matchAction && matchDate;
  });

  // Stats from current page
  const loginCount   = logs.filter(l => l.action === 'LOGIN_SUCCESS').length;
  const failedCount  = logs.filter(l => l.action === 'LOGIN_FAILED').length;
  const uniqueUsers  = new Set(logs.map(l => l.username)).size;

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <PageHeader
        title={<><Activity className="w-6 h-6 shrink-0" /> سجل النشاط</>}
        subtitle="مراقبة جميع عمليات الدخول والأمان في النظام"
      >
        <button onClick={fetchLogs} className="btn-primary text-sm">
          <RefreshCw className="w-4 h-4" /> تحديث
        </button>
      </PageHeader>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'إجمالي الأحداث', value: logs.length, tone: 'stat-card-purple' },
          { label: 'دخول ناجح',      value: loginCount,  tone: 'stat-card-green' },
          /* الأحمر هنا يعني خطراً فعلياً: محاولات فاشلة قائمة. بلا محاولات يبقى محايداً. */
          { label: 'محاولات فاشلة',  value: failedCount, tone: failedCount > 0 ? 'stat-card-rose' : 'stat-card-blue' },
        ].map(s => (
          <div key={s.label} className={`${s.tone} p-5`}>
            <p className="num-display text-3xl text-[hsl(var(--ink))]">{s.value}</p>
            <p className="eyebrow mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="card p-5">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="relative">
            <Search className="absolute right-3 top-3.5 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
            <input placeholder="بحث بالمستخدم أو الدور..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="form-input pr-9" />
          </div>
          <select value={filterAction} onChange={e => { setFilterAction(e.target.value); setPage(0); }}
            title="فلتر نوع العملية" className="form-input">
            <option value="">كل الأنواع</option>
            {Object.entries(actionConfig).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <input type="date" value={filterDate} onChange={e => setFilterDate(e.target.value)}
            title="فلتر التاريخ" dir="ltr" className="form-input" />
        </div>
        {(search || filterAction || filterDate) && (
          <div className="flex items-center justify-between mt-3">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              عرض <span className="font-bold text-[hsl(var(--primary))]">{filtered.length}</span> من {logs.length} نتيجة
            </p>
            <button onClick={() => { setSearch(''); setFilterAction(''); setFilterDate(''); }}
              className="text-xs text-[hsl(var(--primary))] font-bold underline">
              مسح الفلاتر
            </button>
          </div>
        )}
      </div>

      {/* Logs Table */}
      <div className="bg-white rounded-[var(--radius-lg)] shadow-sm border border-[hsl(var(--border))] overflow-hidden">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="w-10 h-10 border-4 border-[hsl(var(--primary))] border-t-transparent rounded-full animate-spin" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="py-16 text-center text-[hsl(var(--muted-foreground))]">
            <Activity className="w-12 h-12 mx-auto mb-3 opacity-30" />
            <p className="font-medium">لا توجد أنشطة مسجَّلة</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <th className="px-5 py-3.5 font-bold">المستخدم</th>
                  <th className="px-5 py-3.5 font-bold">نوع العملية</th>
                  <th className="px-5 py-3.5 font-bold hidden md:table-cell">IP</th>
                  <th className="px-5 py-3.5 font-bold">التاريخ والوقت</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[hsl(var(--border))]">
                {filtered.map(log => {
                  const cfg = actionConfig[log.action];
                  const Icon = cfg?.icon || User;
                  return (
                    <tr key={log.id} className="hover:bg-[hsl(var(--muted))]/30 transition-colors">
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-2.5">
                          <div className="w-8 h-8 gradient-primary rounded-lg flex items-center justify-center text-white text-xs font-bold shrink-0">
                            {(log.actor_name || log.username || '?').charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-bold text-[hsl(var(--foreground))]">
                              {log.actor_name || <span dir="ltr">{log.username || '—'}</span>}
                            </p>
                            {(log.role || log.center_name) && (
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                                {[log.role && (roleLabels[log.role] || log.role), log.center_name].filter(Boolean).join(' · ')}
                              </p>
                            )}
                          </div>
                        </div>
                      </td>
                      <td className="px-5 py-3.5">
                        <span className={`inline-flex items-center gap-1.5 text-xs font-bold px-2.5 py-1 rounded-full ${cfg?.cls || 'bg-blue-100 text-blue-700'}`}>
                          <Icon className="w-3.5 h-3.5" />
                          {cfg?.label || log.action}
                        </span>
                      </td>
                      <td className="px-5 py-3.5 hidden md:table-cell">
                        <span className="font-mono text-xs text-[hsl(var(--muted-foreground))] bg-[hsl(var(--muted))] px-2 py-1 rounded" dir="ltr">
                          {log.ip || '—'}
                        </span>
                      </td>
                      <td className="px-5 py-3.5">
                        <div className="flex items-center gap-1.5 text-xs text-[hsl(var(--muted-foreground))]">
                          <Calendar className="w-3.5 h-3.5 shrink-0" />
                          <span dir="ltr">{new Date(log.timestamp).toLocaleString('ar-SA')}</span>
                        </div>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        )}

        {/* Pagination */}
        <div className="p-4 border-t border-[hsl(var(--border))] flex items-center justify-between bg-[hsl(var(--muted))]/30">
          <span className="text-sm text-[hsl(var(--muted-foreground))]">
            صفحة {page + 1} · {logs.length} سجل
          </span>
          <div className="flex gap-2">
            <button onClick={() => setPage(p => Math.max(0, p - 1))} disabled={page === 0}
              className="p-2 rounded-xl border border-[hsl(var(--border))] hover:bg-white disabled:opacity-40 transition-all">
              <ChevronRight className="w-4 h-4" />
            </button>
            <button onClick={() => setPage(p => p + 1)} disabled={logs.length < limit}
              className="p-2 rounded-xl border border-[hsl(var(--border))] hover:bg-white disabled:opacity-40 transition-all">
              <ChevronLeft className="w-4 h-4" />
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

