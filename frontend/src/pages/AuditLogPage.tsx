import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  ShieldAlert, Search, Calendar, Activity,
  ChevronRight, ChevronLeft, LogIn, LogOut,
  KeyRound, User, RefreshCw,
} from 'lucide-react';
import api from '@/services/api';

interface AuditLog {
  id: string;
  action: string;
  username: string;
  role?: string;
  ip?: string;
  timestamp: string;
}

const actionConfig: Record<string, { label: string; cls: string; icon: typeof LogIn }> = {
  LOGIN_SUCCESS:    { label: 'تسجيل دخول',    cls: 'bg-emerald-100 text-emerald-700', icon: LogIn      },
  LOGIN_FAILED:     { label: 'محاولة فاشلة',   cls: 'bg-red-100 text-red-700',         icon: ShieldAlert },
  LOGOUT:           { label: 'تسجيل خروج',    cls: 'bg-gray-100 text-gray-600',        icon: LogOut     },
  PASSWORD_CHANGED: { label: 'تغيير مرور',    cls: 'bg-purple-100 text-purple-700',    icon: KeyRound   },
};

const roleLabels: Record<string, string> = {
  admin: 'مدير النظام', center_manager: 'مدير مركز',
  teacher: 'محفظ', student: 'طالب', parent: 'ولي أمر',
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
      const res = await api.get(`/audit-logs?skip=${page * limit}&limit=${limit}`);
      setLogs(res.data || []);
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, [page, user]);

  useEffect(() => { fetchLogs(); }, [fetchLogs]);

  if (user?.role !== 'admin') {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <div className="w-20 h-20 bg-red-100 rounded-3xl flex items-center justify-center mb-4 shadow-lg">
          <ShieldAlert className="w-10 h-10 text-red-600" />
        </div>
        <h2 className="text-2xl font-black text-[hsl(var(--foreground))]">غير مصرح بالوصول</h2>
        <p className="text-[hsl(var(--muted-foreground))] mt-2 text-sm">هذه الصفحة مخصصة لمدير النظام فقط.</p>
      </div>
    );
  }

  // Apply client-side filters
  const filtered = logs.filter(log => {
    const matchSearch = !search ||
      (log.username || '').toLowerCase().includes(search.toLowerCase()) ||
      (log.role || '').includes(search);
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
      <div className="relative overflow-hidden rounded-3xl p-6 text-white shadow-xl stat-card-purple">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1 flex items-center gap-2">
              <Activity className="w-6 h-6" /> سجل النشاط
            </h1>
            <p className="text-white/70 text-sm">مراقبة جميع عمليات الدخول والأمان في النظام</p>
          </div>
          <button onClick={fetchLogs}
            className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white font-bold px-4 py-2.5 rounded-xl transition-all text-sm">
            <RefreshCw className="w-4 h-4" /> تحديث
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'إجمالي الأحداث', value: logs.length, cls: 'stat-card-purple' },
          { label: 'دخول ناجح',      value: loginCount,  cls: 'gradient-primary' },
          { label: 'محاولات فاشلة',  value: failedCount, cls: failedCount > 0 ? 'bg-red-600' : 'gradient-primary' },
        ].map(s => (
          <div key={s.label} className={`stat-card rounded-2xl p-5 text-white ${s.cls} shadow-lg`}>
            <p className="text-3xl font-black">{s.value}</p>
            <p className="text-white/70 text-sm mt-1">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Filters */}
      <div className="bg-white rounded-3xl p-5 shadow-sm border border-[hsl(var(--border))]">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
          <div className="relative">
            <Search className="absolute right-3 top-3.5 w-4 h-4 text-[hsl(var(--muted-foreground))]" />
            <input placeholder="بحث بالمستخدم أو الدور..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="form-input pr-9" />
          </div>
          <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
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
      <div className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden">
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
                          <div className="w-8 h-8 gradient-primary rounded-lg flex items-center justify-center text-white text-xs font-black shrink-0">
                            {(log.username || '?').charAt(0).toUpperCase()}
                          </div>
                          <div>
                            <p className="font-bold text-[hsl(var(--foreground))]" dir="ltr">{log.username}</p>
                            {log.role && (
                              <p className="text-xs text-[hsl(var(--muted-foreground))]">
                                {roleLabels[log.role] || log.role}
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

