import { useState, useEffect, useCallback } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import {
  Bell, CheckCircle2, Trash2, BookOpen,
  UserCheck, DollarSign, AlertCircle, RefreshCw,
} from 'lucide-react';
import api from '@/services/api';

interface Notification {
  id: string;
  type: 'recitation' | 'attendance' | 'fee' | 'system';
  title: string;
  message: string;
  date: string;
  read: boolean;
  link?: string;
}

const typeConfig = {
  recitation: { icon: BookOpen,     bg: 'bg-[hsl(var(--primary-light))]',  color: 'text-[hsl(var(--primary))]',  label: 'تسميع'   },
  attendance:  { icon: UserCheck,   bg: 'bg-amber-100',                      color: 'text-amber-600',               label: 'حضور'    },
  fee:         { icon: DollarSign,  bg: 'bg-emerald-100',                    color: 'text-emerald-600',             label: 'مالية'   },
  system:      { icon: AlertCircle, bg: 'bg-[hsl(var(--gold-light))]',       color: 'text-[hsl(var(--gold))]',      label: 'النظام'  },
} as const;

// Build real notifications from API data
async function fetchRealNotifications(user: any): Promise<Notification[]> {
  const notifs: Notification[] = [];
  const today = new Date().toISOString().slice(0, 10);

  try {
    if (user?.role === 'student') {
      // Last recitation
      const recResp = await api.get('/recitations?limit=5').catch(() => ({ data: [] }));
      const recs: any[] = recResp.data || [];
      recs.forEach((r: any) => {
        notifs.push({
          id: `rec_${r.id}`,
          type: 'recitation',
          title: `تسميع ${r.surah_name}`,
          message: `تم تسجيل تسميع سورة ${r.surah_name} (${r.start_ayah}–${r.end_ayah}) بتقدير "${
            r.evaluation === 'excellent' ? 'ممتاز' : r.evaluation === 'good' ? 'جيد' : r.evaluation === 'acceptable' ? 'مقبول' : 'يحتاج تحسين'
          }"`,
          date: new Date(r.date).toLocaleDateString('ar-SA'),
          read: false,
          link: '/recitations',
        });
      });

      // Attendance check
      const attResp = await api.get('/attendance/center?limit=10').catch(() => ({ data: [] }));
      const atts: any[] = attResp.data || [];
      const myAbsent = atts.filter((a: any) => a.status === 'absent' && a.student_id === user.id);
      myAbsent.forEach((a: any) => {
        notifs.push({
          id: `att_${a.id}`,
          type: 'attendance',
          title: 'تسجيل غياب',
          message: `تم تسجيل غيابك يوم ${new Date(a.date || today).toLocaleDateString('ar-SA')}`,
          date: new Date(a.date || today).toLocaleDateString('ar-SA'),
          read: false,
          link: '/attendance',
        });
      });

    } else if (user?.role === 'parent') {
      const recResp = await api.get('/recitations?limit=5').catch(() => ({ data: [] }));
      const recs: any[] = recResp.data || [];
      recs.forEach((r: any) => {
        notifs.push({
          id: `rec_${r.id}`,
          type: 'recitation',
          title: `تسميع ${r.student_name || 'الطالب'}`,
          message: `تم تسجيل تسميع سورة ${r.surah_name} بتقدير "${
            r.evaluation === 'excellent' ? 'ممتاز' : r.evaluation === 'good' ? 'جيد' : r.evaluation === 'acceptable' ? 'مقبول' : 'يحتاج تحسين'
          }" (${r.mistakes_count} أخطاء)`,
          date: new Date(r.date).toLocaleDateString('ar-SA'),
          read: false,
        });
      });

      // Pending fees
      const feeResp = await api.get('/fees?status=pending').catch(() => ({ data: [] }));
      const fees: any[] = feeResp.data || [];
      if (fees.length > 0) {
        const total = fees.reduce((s: number, f: any) => s + (f.amount || 0), 0);
        notifs.push({
          id: 'fees_pending',
          type: 'fee',
          title: 'رسوم غير مسددة',
          message: `يوجد ${fees.length} دفعة غير مسددة بمجموع ${total.toLocaleString('fr-FR')} FCFA`,
          date: today,
          read: false,
          link: '/finance',
        });
      }

    } else if (user?.role === 'teacher') {
      const recResp = await api.get('/recitations?limit=5').catch(() => ({ data: [] }));
      const recs: any[] = recResp.data || [];
      const todayRecs = recs.filter((r: any) => r.date?.startsWith(today));
      if (todayRecs.length > 0) {
        notifs.push({
          id: 'today_recs',
          type: 'recitation',
          title: 'تسميعات اليوم',
          message: `لديك ${todayRecs.length} تسميع مسجَّل اليوم`,
          date: today,
          read: true,
          link: '/recitations',
        });
      }

      // Attendance reminder
      notifs.push({
        id: 'attend_reminder',
        type: 'attendance',
        title: 'تذكير تسجيل الحضور',
        message: `لا تنسَ تسجيل حضور طلابك اليوم ${new Date().toLocaleDateString('ar-SA')}`,
        date: today,
        read: false,
        link: '/attendance',
      });

    } else if (user?.role === 'center_manager') {
      // Pending fees
      const feeResp = await api.get('/fees?status=pending').catch(() => ({ data: [] }));
      const fees: any[] = feeResp.data || [];
      if (fees.length > 0) {
        notifs.push({
          id: 'fees_pending',
          type: 'fee',
          title: 'رسوم غير مسددة',
          message: `يوجد ${fees.length} رسوم غير مسددة تحتاج متابعة`,
          date: today,
          read: false,
          link: '/finance',
        });
      }
      // Today recitations summary
      const recResp = await api.get('/recitations?limit=20').catch(() => ({ data: [] }));
      const recs: any[] = recResp.data || [];
      const todayRecs = recs.filter((r: any) => r.date?.startsWith(today));
      if (todayRecs.length > 0) {
        notifs.push({
          id: 'today_recs',
          type: 'recitation',
          title: 'تسميعات اليوم',
          message: `${todayRecs.length} تسميع مسجَّل اليوم في المركز`,
          date: today,
          read: true,
          link: '/recitations',
        });
      }
    }
  } catch { /* silent */ }

  // Limit & sort by read status
  return notifs.sort((a, b) => Number(a.read) - Number(b.read)).slice(0, 20);
}

export default function NotificationsPage() {
  const { user } = useAuth();
  const [notifications, setNotifications] = useState<Notification[]>([]);
  const [loading, setLoading]             = useState(true);
  const [filter, setFilter]               = useState<'all' | 'unread'>('all');

  const load = useCallback(async () => {
    if (!user) return;
    setLoading(true);
    const data = await fetchRealNotifications(user);
    setNotifications(data);
    setLoading(false);
  }, [user]);

  useEffect(() => { load(); }, [load]);

  const filtered    = notifications.filter(n => filter === 'all' || !n.read);
  const unreadCount = notifications.filter(n => !n.read).length;

  const markRead    = (id: string) => setNotifications(prev => prev.map(n => n.id === id ? { ...n, read: true } : n));
  const markAllRead = ()           => setNotifications(prev => prev.map(n => ({ ...n, read: true })));
  const remove      = (id: string) => setNotifications(prev => prev.filter(n => n.id !== id));

  return (
    <div className="space-y-6 animate-fade-in">

      {/* Header */}
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold mb-1 flex items-center gap-2">
              <Bell className="w-6 h-6" /> الإشعارات
            </h1>
            <p className="text-sm text-[hsl(var(--ink-3))]">
              {unreadCount > 0 ? `لديك ${unreadCount} إشعار غير مقروء` : 'جميع الإشعارات مقروءة'}
            </p>
          </div>
          <button onClick={load}
            className="btn-primary text-sm">
            <RefreshCw className="w-4 h-4" /> تحديث
          </button>
        </div>
      </div>

      {/* Controls */}
      <div className="flex items-center justify-between gap-4 bg-white rounded-[var(--radius)] p-4 shadow-sm border border-[hsl(var(--border))]">
        <div className="flex gap-2">
          {(['all', 'unread'] as const).map(f => (
            <button key={f} onClick={() => setFilter(f)}
              className={`px-4 py-2 rounded-xl text-sm font-bold transition-all ${
                filter === f ? 'gradient-primary text-white shadow-md' : 'bg-[hsl(var(--muted))] text-[hsl(var(--muted-foreground))] hover:text-[hsl(var(--foreground))]'}`}>
              {f === 'all' ? 'الكل' : `غير المقروءة (${unreadCount})`}
            </button>
          ))}
        </div>
        {unreadCount > 0 && (
          <button onClick={markAllRead}
            className="flex items-center gap-1.5 text-sm font-bold text-[hsl(var(--primary))] hover:text-[hsl(var(--primary))]/80 transition-colors">
            <CheckCircle2 className="w-4 h-4" /> قراءة الكل
          </button>
        )}
      </div>

      {/* List */}
      {loading ? (
        <div className="flex items-center justify-center h-48">
          <div className="text-center">
            <div className="w-12 h-12 gradient-primary rounded-[var(--radius)] mx-auto mb-3 flex items-center justify-center animate-pulse-soft">
              <Bell className="w-6 h-6 text-white" />
            </div>
            <p className="text-sm text-[hsl(var(--muted-foreground))]">جاري تحميل الإشعارات...</p>
          </div>
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-16 bg-white rounded-[var(--radius-lg)] border-2 border-dashed border-[hsl(var(--border))] text-[hsl(var(--muted-foreground))]">
          <Bell className="w-14 h-14 mx-auto mb-3 opacity-30" />
          <p className="font-medium">لا توجد إشعارات {filter === 'unread' ? 'غير مقروءة' : ''}</p>
          <p className="text-sm mt-1">ستظهر هنا الإشعارات المرتبطة بنشاطك في النظام</p>
        </div>
      ) : (
        <div className="space-y-3">
          {filtered.map(n => {
            const cfg = typeConfig[n.type];
            const Icon = cfg.icon;
            return (
              <div key={n.id}
                className={`flex items-start gap-4 p-5 rounded-[var(--radius)] border transition-all stat-card ${
                  n.read
                    ? 'bg-white border-[hsl(var(--border))]'
                    : 'bg-[hsl(var(--primary-light))]/40 border-[hsl(var(--primary))]/20 shadow-sm'
                }`}>
                {/* Icon */}
                <div className={`w-12 h-12 rounded-[var(--radius)] flex items-center justify-center shrink-0 ${cfg.bg}`}>
                  <Icon className={`w-5 h-5 ${cfg.color}`} />
                </div>

                {/* Content */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div>
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className={`font-bold text-sm ${!n.read ? 'text-[hsl(var(--primary))]' : 'text-[hsl(var(--foreground))]'}`}>
                          {n.title}
                        </h3>
                        <span className={`text-[10px] font-bold px-2 py-0.5 rounded-full ${cfg.bg} ${cfg.color}`}>
                          {cfg.label}
                        </span>
                        {!n.read && (
                          <span className="w-2 h-2 bg-[hsl(var(--primary))] rounded-full" />
                        )}
                      </div>
                      <p className="text-sm text-[hsl(var(--muted-foreground))] mt-0.5 leading-relaxed">{n.message}</p>
                    </div>
                    <span className="text-xs text-[hsl(var(--muted-foreground))] bg-[hsl(var(--muted))] px-2 py-1 rounded-lg shrink-0 whitespace-nowrap">
                      {n.date}
                    </span>
                  </div>

                  <div className="mt-3 flex gap-3">
                    {!n.read && (
                      <button onClick={() => markRead(n.id)}
                        className="text-xs font-bold text-[hsl(var(--primary))] hover:opacity-70 transition-colors flex items-center gap-1">
                        <CheckCircle2 className="w-3.5 h-3.5" /> تعليم كمقروء
                      </button>
                    )}
                    <button onClick={() => remove(n.id)}
                      className="text-xs font-bold text-red-500 hover:text-red-700 transition-colors flex items-center gap-1">
                      <Trash2 className="w-3.5 h-3.5" /> حذف
                    </button>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
