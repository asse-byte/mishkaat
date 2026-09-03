import React from 'react';
import { HelpCircle } from 'lucide-react';
import type { LucideIcon } from 'lucide-react';

interface EmptyStateProps {
  icon?: LucideIcon;
  title: string;
  description: string;
  actionLabel?: string;
  onAction?: () => void;
}

export default function EmptyState({ icon: Icon = HelpCircle, title, description, actionLabel, onAction }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center text-center p-8 md:p-12 rounded-3xl border border-dashed border-[hsl(var(--border))] bg-[hsl(var(--card))] transition-all">
      <div className="w-16 h-16 rounded-2xl bg-[hsl(var(--muted))] flex items-center justify-center text-[hsl(var(--muted-foreground))] mb-4 shadow-inner">
        <Icon className="w-8 h-8 opacity-75" />
      </div>

      <h3 className="text-lg font-bold text-[hsl(var(--foreground))] mb-2">
        {title}
      </h3>

      <p className="text-sm text-[hsl(var(--muted-foreground))] max-w-sm leading-relaxed mb-6 font-medium">
        {description}
      </p>

      {actionLabel && onAction && (
        <button
          onClick={onAction}
          className="btn-gradient-teal"
        >
          {actionLabel}
        </button>
      )}
    </div>
  );
}
