import React from 'react';
import { Shield, BookOpen, Users, DollarSign, Calendar, Settings } from 'lucide-react';
import { cn } from '@/lib/utils';

type PermissionKey = 'students' | 'teachers' | 'finance' | 'attendance' | 'halaqat' | 'settings' | 'general';

interface PermissionBadgeProps {
  permission: PermissionKey;
  label: string;
  className?: string;
}

const permissionConfigs: Record<PermissionKey, { cls: string; icon: React.ElementType }> = {
  students: {
    cls: 'bg-emerald-50 text-emerald-700 border-emerald-200 dark:bg-emerald-950/40 dark:text-emerald-300 dark:border-emerald-800',
    icon: Users
  },
  teachers: {
    cls: 'bg-blue-50 text-blue-700 border-blue-200 dark:bg-blue-950/40 dark:text-blue-300 dark:border-blue-800',
    icon: BookOpen
  },
  finance: {
    cls: 'bg-amber-50 text-amber-700 border-amber-200 dark:bg-amber-950/40 dark:text-amber-300 dark:border-amber-800',
    icon: DollarSign
  },
  attendance: {
    cls: 'bg-rose-50 text-rose-700 border-rose-200 dark:bg-rose-950/40 dark:text-rose-300 dark:border-rose-800',
    icon: Calendar
  },
  halaqat: {
    cls: 'bg-purple-50 text-purple-700 border-purple-200 dark:bg-purple-950/40 dark:text-purple-300 dark:border-purple-800',
    icon: BookOpen
  },
  settings: {
    cls: 'bg-slate-100 text-slate-700 border-slate-200 dark:bg-slate-800/40 dark:text-slate-300 dark:border-slate-700',
    icon: Settings
  },
  general: {
    cls: 'bg-teal-50 text-teal-700 border-teal-200 dark:bg-teal-950/40 dark:text-teal-300 dark:border-teal-800',
    icon: Shield
  }
};

export default function PermissionBadge({ permission, label, className }: PermissionBadgeProps) {
  const config = permissionConfigs[permission] || permissionConfigs.general;
  const Icon = config.icon;

  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 px-3 py-1 text-xs font-bold rounded-full border transition-all",
        config.cls,
        className
      )}
    >
      <Icon className="w-3.5 h-3.5 shrink-0" />
      <span>{label}</span>
    </span>
  );
}
