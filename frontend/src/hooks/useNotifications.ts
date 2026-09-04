import { useState, useEffect, useCallback, useRef } from 'react';
import api from '@/services/api';

/**
 * الإشعارات المحفوظة على الخادم + البثّ الحيّ.
 *
 * كانت صفحة الإشعارات تُركّب تنبيهاتها من /recitations و/attendance و/fees،
 * و«مقروء» و«حذف» يغيّران حالة React وحدها فيعودان بإعادة التحميل. وكان
 * تنبيه غياب الطالب — وهو الإشعار الحقيقي الوحيد الذي يكتبه الخادم — لا
 * يظهر في الصفحة إطلاقاً.
 *
 * هذا الخطّاف يصل الصفحة بـ /api/notifications: الحالة تُحفَظ على الخادم،
 * والجديد يصل حيّاً عبر قناة SSE بلا إعادة تحميل.
 */

export interface StoredNotification {
  id: string;
  type: string;
  title: string;
  body: string;
  data?: Record<string, unknown>;
  read: boolean;
  created_at: string;
}

/** لا يُستدعى مباشرةً من المكوّنات: NotificationsProvider هو من يستهلكه.
 *  الاستدعاء المباشر يفتح قناة SSE إضافية لكل مكوّن. */
export function useNotificationsSource(enabled = true) {
  const [items, setItems] = useState<StoredNotification[]>([]);
  const [unread, setUnread] = useState(0);
  const [loading, setLoading] = useState(true);
  const esRef = useRef<EventSource | null>(null);
  const retryRef = useRef<number>(0);

  const load = useCallback(async () => {
    if (!enabled) { setLoading(false); return; }
    try {
      const { data } = await api.get('/notifications', { params: { limit: 50 } });
      setItems(data.items || []);
      setUnread(data.unread_count || 0);
    } catch {
      /* المستخدم غير مسجَّل أو الشبكة منقطعة — لا نُفرغ ما هو معروض */
    } finally {
      setLoading(false);
    }
  }, [enabled]);

  useEffect(() => { load(); }, [load]);

  /**
   * قناة البثّ.
   *
   * EventSource لا يرسل رؤوساً، فلا يمكن تمرير توكن الوصول فيه — ولهذا يُطلب
   * أولاً «تذكرة» برأس Authorization عادي، ثم تُفتح القناة بها. التذكرة تعيش
   * دقيقة وتُستهلَك مرة واحدة، فلا يتسرّب توكن طويل العمر إلى سجلّات الخادم
   * ولا إلى تاريخ المتصفّح.
   */
  useEffect(() => {
    if (!enabled) return;
    let closed = false;
    let timer: number | undefined;

    const connect = async () => {
      if (closed) return;
      try {
        const { data } = await api.post('/notifications/stream-ticket');
        if (closed) return;
        const es = new EventSource(`/api/notifications/stream?ticket=${encodeURIComponent(data.ticket)}`);
        esRef.current = es;

        es.onmessage = () => { /* keep-alive */ };
        es.onopen = () => { retryRef.current = 0; };

        // الخادم يرسل نوع الحدث في event:، فنستمع للأنواع المعروفة وللافتراضي
        const onEvent = () => { load(); };
        ['absentee_alert', 'notification', 'message'].forEach(t => es.addEventListener(t, onEvent));

        es.onerror = () => {
          es.close();
          esRef.current = null;
          if (closed) return;
          // تراجع أُسّي محدود: القناة تُقطع طبيعياً (وكيل، نوم الجهاز) فلا نُغرق الخادم
          retryRef.current = Math.min(retryRef.current + 1, 5);
          timer = window.setTimeout(connect, 1000 * 2 ** retryRef.current);
        };
      } catch {
        if (closed) return;
        retryRef.current = Math.min(retryRef.current + 1, 5);
        timer = window.setTimeout(connect, 1000 * 2 ** retryRef.current);
      }
    };

    connect();
    return () => {
      closed = true;
      if (timer) window.clearTimeout(timer);
      esRef.current?.close();
      esRef.current = null;
    };
  }, [enabled, load]);

  const markRead = useCallback(async (id: string) => {
    setItems(prev => prev.map(n => (n.id === id ? { ...n, read: true } : n)));
    setUnread(u => Math.max(0, u - 1));
    try { await api.post(`/notifications/${id}/read`); } catch { load(); }
  }, [load]);

  const markAllRead = useCallback(async () => {
    setItems(prev => prev.map(n => ({ ...n, read: true })));
    setUnread(0);
    try { await api.post('/notifications/read-all'); } catch { load(); }
  }, [load]);

  return { items, unread, loading, reload: load, markRead, markAllRead };
}
