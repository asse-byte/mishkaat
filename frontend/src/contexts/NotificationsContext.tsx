import React, { createContext, useContext } from 'react';
import { useNotificationsSource } from '@/hooks/useNotifications';
import type { StoredNotification } from '@/hooks/useNotifications';

/**
 * مصدر واحد للإشعارات يشترك فيه الجرس وصفحة الإشعارات.
 *
 * أول تركيب استعمل الخطّاف في الموضعين، فنشأت نسختان مستقلّتان: عدّاد الجرس
 * يتأخّر عن الصفحة عند التعليم كمقروء (لكلٍّ حالته)، والأسوأ أن كلاً منهما
 * يفتح قناة SSE خاصة به — اتصالان لكل تبويب بلا داعٍ. المزوّد يجعلهما واحداً.
 */
interface NotificationsValue {
  items: StoredNotification[];
  unread: number;
  loading: boolean;
  reload: () => Promise<void>;
  markRead: (id: string) => Promise<void>;
  markAllRead: () => Promise<void>;
}

const Ctx = createContext<NotificationsValue | null>(null);

export function NotificationsProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: React.ReactNode;
}) {
  const value = useNotificationsSource(enabled);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useNotifications(): NotificationsValue {
  const ctx = useContext(Ctx);
  if (!ctx) {
    // خارج المزوّد (صفحة عامة مثلاً): قيم خاملة بدل الانهيار
    return {
      items: [], unread: 0, loading: false,
      reload: async () => {}, markRead: async () => {}, markAllRead: async () => {},
    };
  }
  return ctx;
}
