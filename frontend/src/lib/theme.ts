/**
 * المظهر — فاتحٌ وداكن، بمصدرٍ واحد.
 *
 * كانت الحالة في مكانين: زرُّ الشريط العلوي يقلب `document.documentElement`
 * ويكتب في التخزين المحلّي، وصفحةُ الإعدادات تحمل حالتَها الخاصّة وتعرض
 * «وضع داكن (قريباً)» معطَّلاً — لميزةٍ تعمل تماماً منذ زمن في الشاشة نفسها.
 * فكانت الإعدادات تُظهر «وضع فاتح» مختاراً والتطبيقُ داكن.
 *
 * فصار المظهر هنا: قراءةٌ واحدة، وكتابةٌ واحدة، وإشعارٌ لكل من يستمع — فلا
 * تتناقض شاشتان على حالةٍ واحدة.
 */
import { useEffect, useState } from 'react';

export type Theme = 'light' | 'dark';

const KEY = 'theme';
const EVENT = 'mishkaat:theme';

/** يُطبّق المظهر على الجذر. تُستدعى مبكّراً حتى لا تُرى ومضةُ اللون الخطأ. */
export function applyTheme(theme: Theme): void {
  const root = document.documentElement;
  if (theme === 'dark') root.classList.add('dark');
  else root.classList.remove('dark');
}

export function readTheme(): Theme {
  try {
    return localStorage.getItem(KEY) === 'dark' ? 'dark' : 'light';
  } catch {
    // متصفّحٌ يمنع التخزين (تصفّحٌ خاصّ، أو إعدادٌ صارم) — الفاتح هو الافتراض
    return 'light';
  }
}

export function setTheme(theme: Theme): void {
  try {
    localStorage.setItem(KEY, theme);
  } catch {
    /* لا يُخزَّن، لكن الجلسة الحالية تتغيّر */
  }
  applyTheme(theme);
  window.dispatchEvent(new CustomEvent(EVENT, { detail: theme }));
}

/** المظهر الحالي ودالّةُ قلبه — يتزامن كل مستدعٍ مع غيره. */
export function useTheme(): { theme: Theme; toggle: () => void; set: (t: Theme) => void } {
  const [theme, setLocal] = useState<Theme>(() => {
    const t = readTheme();
    applyTheme(t);
    return t;
  });

  useEffect(() => {
    const sync = () => setLocal(readTheme());
    window.addEventListener(EVENT, sync);
    // تبويبٌ آخر من التطبيق نفسه غيّر المظهر
    window.addEventListener('storage', sync);
    return () => {
      window.removeEventListener(EVENT, sync);
      window.removeEventListener('storage', sync);
    };
  }, []);

  return {
    theme,
    toggle: () => setTheme(theme === 'dark' ? 'light' : 'dark'),
    set: setTheme,
  };
}
