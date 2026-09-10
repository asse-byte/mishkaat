import { type ClassValue, clsx } from "clsx"
import { twMerge } from "tailwind-merge"

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatDate(date: Date | string): string {
  const d = new Date(date);
  return d.toLocaleDateString('ar-SA', {
    year: 'numeric',
    month: 'long',
    day: 'numeric',
  });
}

/** @deprecated استعمل formatNumber من lib/format — هذه تُخرج أرقاماً هندية
 *  وفاصلةً عربية، فيختلف الرقم عن بقيّة الشاشات. باقية لئلا ينكسر مستدعٍ قديم. */
export { formatNumber } from './format';

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .slice(0, 2);
}
