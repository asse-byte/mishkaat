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
  LOGIN_SUCCESS:    { label: 'ØªØ³Ø¬ÙŠÙ„ Ø¯Ø®ÙˆÙ„',    cls: 'bg-emerald-100 text-emerald-700', icon: LogIn      },
  LOGIN_FAILED:     { label: 'Ù…Ø­Ø§ÙˆÙ„Ø© ÙØ§Ø´Ù„Ø©',   cls: 'bg-red-100 text-red-700',         icon: ShieldAlert },
  LOGOUT:           { label: 'ØªØ³Ø¬ÙŠÙ„ Ø®Ø±ÙˆØ¬',    cls: 'bg-gray-100 text-gray-600',        icon: LogOut     },
  PASSWORD_CHANGED: { label: 'ØªØºÙŠÙŠØ± Ù…Ø±ÙˆØ±',    cls: 'bg-purple-100 text-purple-700',    icon: KeyRound   },
};

const roleLabels: Record<string, string> = {
  admin: 'Ù…Ø¯ÙŠØ± Ø§Ù„Ù†Ø¸Ø§Ù…', center_manager: 'Ù…Ø¯ÙŠØ± Ù…Ø±ÙƒØ²',
  teacher: 'Ù…Ø­ÙØ¸', student: 'Ø·Ø§Ù„Ø¨', parent: 'ÙˆÙ„ÙŠ Ø£Ù…Ø±',
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
        <h2 className="text-2xl font-black text-[hsl(var(--foreground))]">ØºÙŠØ± Ù…ØµØ±Ø­ Ø¨Ø§Ù„ÙˆØµÙˆÙ„</h2>
        <p className="text-[hsl(var(--muted-foreground))] mt-2 text-sm">Ù‡Ø°Ù‡ Ø§Ù„ØµÙØ­Ø© Ù…Ø®ØµØµØ© Ù„Ù…Ø¯ÙŠØ± Ø§Ù„Ù†Ø¸Ø§Ù… ÙÙ‚Ø·.</p>
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
              <Activity className="w-6 h-6" /> Ø³Ø¬Ù„ Ø§Ù„Ù†Ø´Ø§Ø·
            </h1>
            <p className="text-white/70 text-sm">Ù…Ø±Ø§Ù‚Ø¨Ø© Ø¬Ù…ÙŠØ¹ Ø¹Ù…Ù„ÙŠØ§Øª Ø§Ù„Ø¯Ø®ÙˆÙ„ ÙˆØ§Ù„Ø£Ù…Ø§Ù† ÙÙŠ Ø§Ù„Ù†Ø¸Ø§Ù…</p>
          </div>
          <button onClick={fetchLogs}
            className="flex items-center gap-2 bg-white/20 hover:bg-white/30 text-white font-bold px-4 py-2.5 rounded-xl transition-all text-sm">
            <RefreshCw className="w-4 h-4" /> ØªØ­Ø¯ÙŠØ«
          </button>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="grid grid-cols-3 gap-4 stagger">
        {[
          { label: 'Ø¥Ø¬Ù…Ø§Ù„ÙŠ Ø§Ù„Ø£Ø­Ø¯Ø§Ø«', value: logs.length, cls: 'stat-card-purple' },
          { label: 'Ø¯Ø®ÙˆÙ„ Ù†Ø§Ø¬Ø­',      value: loginCount,  cls: 'gradient-primary' },
          { label: 'Ù…Ø­Ø§ÙˆÙ„Ø§Øª ÙØ§Ø´Ù„Ø©',  value: failedCount, cls: failedCount > 0 ? 'bg-red-600' : 'gradient-primary' },
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
            <input placeholder="Ø¨Ø­Ø« Ø¨Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù… Ø£Ùˆ Ø§Ù„Ø¯ÙˆØ±..." value={search}
              onChange={e => setSearch(e.target.value)}
              className="form-input pr-9" />
          </div>
          <select value={filterAction} onChange={e => setFilterAction(e.target.value)}
            title="ÙÙ„ØªØ± Ù†ÙˆØ¹ Ø§Ù„Ø¹Ù…Ù„ÙŠØ©" className="form-input">
            <option value="">ÙƒÙ„ Ø§Ù„Ø£Ù†ÙˆØ§Ø¹</option>
            {Object.entries(actionConfig).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
          </select>
          <input type="date" value={filterDate} onChange={e => setFilterDate(e.target.value)}
            title="ÙÙ„ØªØ± Ø§Ù„ØªØ§Ø±ÙŠØ®" dir="ltr" className="form-input" />
        </div>
        {(search || filterAction || filterDate) && (
          <div className="flex items-center justify-between mt-3">
            <p className="text-sm text-[hsl(var(--muted-foreground))]">
              Ø¹Ø±Ø¶ <span className="font-bold text-[hsl(var(--primary))]">{filtered.length}</span> Ù…Ù† {logs.length} Ù†ØªÙŠØ¬Ø©
            </p>
            <button onClick={() => { setSearch(''); setFilterAction(''); setFilterDate(''); }}
              className="text-xs text-[hsl(var(--primary))] font-bold underline">
              Ù…Ø³Ø­ Ø§Ù„ÙÙ„Ø§ØªØ±
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
            <p className="font-medium">Ù„Ø§ ØªÙˆØ¬Ø¯ Ø£Ù†Ø´Ø·Ø© Ù…Ø³Ø¬ÙŽÙ‘Ù„Ø©</p>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-right text-sm">
              <thead>
                <tr className="bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))]">
                  <th className="px-5 py-3.5 font-bold">Ø§Ù„Ù…Ø³ØªØ®Ø¯Ù…</th>
                  <th className="px-5 py-3.5 font-bold">Ù†ÙˆØ¹ Ø§Ù„Ø¹Ù…Ù„ÙŠØ©</th>
                  <th className="px-5 py-3.5 font-bold hidden md:table-cell">IP</th>
                  <th className="px-5 py-3.5 font-bold">Ø§Ù„ØªØ§Ø±ÙŠØ® ÙˆØ§Ù„ÙˆÙ‚Øª</th>
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
                          {log.ip || 'â€”'}
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
            ØµÙØ­Ø© {page + 1} Â· {logs.length} Ø³Ø¬Ù„
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

