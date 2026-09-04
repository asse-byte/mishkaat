import React from 'react';
import { TrendingUp, TrendingDown } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';
import { cn } from '@/lib/utils';

interface StatCardProps {
  title: string;
  value: string | number;
  icon: LucideIcon;
  gradientClass: 'stat-card-blue' | 'stat-card-green' | 'stat-card-amber' | 'stat-card-purple' | 'stat-card-rose' | 'stat-card-teal';
  trend?: {
    value: string | number;
    isPositive: boolean;
  };
  onClick?: () => void;
}

export default function StatCard({ title, value, icon: Icon, gradientClass, trend, onClick }: StatCardProps) {
  return (
    <div
      onClick={onClick}
      className={cn(
        "stat-card hoverable-card flex flex-col justify-between p-5 rounded-[var(--radius)] transition-all select-none",
        gradientClass,
        onClick && "cursor-pointer"
      )}
    >
      <div className="flex items-center justify-between gap-4 mb-4">
        <div className="flex-1 min-w-0">
          <p className="text-xs font-bold text-[hsl(var(--muted-foreground))] uppercase tracking-wider truncate mb-1">
            {title}
          </p>
          <h3 className="text-3xl font-bold text-[hsl(var(--foreground))] amount leading-none">
            {value}
          </h3>
        </div>
        
        <div className="w-12 h-12 rounded-xl flex items-center justify-center bg-white/60 dark:bg-black/10 border border-white/40 dark:border-black/5 shadow-inner shrink-0 text-[hsl(var(--primary))] dark:text-teal-400">
          <Icon className="w-6 h-6" />
        </div>
      </div>

      {trend && (
        <div className="flex items-center gap-1.5 mt-auto pt-2 border-t border-black/5 dark:border-white/5">
          {trend.isPositive ? (
            <TrendingUp className="w-4 h-4 text-emerald-600 dark:text-emerald-400" />
          ) : (
            <TrendingDown className="w-4 h-4 text-rose-600 dark:text-rose-400" />
          )}
          <span className={cn(
            "text-xs font-bold amount",
            trend.isPositive ? "text-emerald-600 dark:text-emerald-400" : "text-rose-600 dark:text-rose-400"
          )}>
            {trend.value}
          </span>
          <span className="text-[10px] text-[hsl(var(--muted-foreground))] font-semibold">
            مقارنة بالشهر السابق
          </span>
        </div>
      )}
    </div>
  );
}
