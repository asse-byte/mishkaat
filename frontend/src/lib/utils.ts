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

export function formatNumber(num: number): string {
  return new Intl.NumberFormat('ar-SA').format(num);
}

export function getInitials(name: string): string {
  return name
    .split(' ')
    .map(word => word[0])
    .join('')
    .slice(0, 2);
}
