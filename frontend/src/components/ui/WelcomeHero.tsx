import React from 'react';
import { Calendar, UserCheck } from 'lucide-react';
import { useTranslation } from '@/lib/i18n';

interface WelcomeHeroProps {
  name: string | null;
  roleTitle: string;
  subtext?: string;
  stats?: {
    label: string;
    value: string | number;
  }[];
}

export default function WelcomeHero({ name, roleTitle, subtext, stats }: WelcomeHeroProps) {
  const { t, locale, isRTL } = useTranslation();

  const formattedDate = new Date().toLocaleDateString(
    locale === 'ar' ? 'ar-SA' : locale === 'fr' ? 'fr-FR' : 'en-US',
    { weekday: 'long', year: 'numeric', month: 'long', day: 'numeric' }
  );

  return (
    <div className="relative overflow-hidden bg-[hsl(var(--sidebar))] text-white rounded-[var(--radius-lg)] p-6 md:p-8 shadow-lg border border-white/5 transition-all mb-6">
      {/* Premium subtle background ornaments */}
      <div className="absolute top-0 right-0 w-80 h-80 bg-[hsl(var(--primary))]/10 rounded-full blur-3xl -translate-y-1/2 translate-x-1/2 pointer-events-none" />
      <div className="absolute bottom-0 left-0 w-64 h-64 bg-[hsl(var(--gold))]/10 rounded-full blur-3xl translate-y-1/3 -translate-x-1/4 pointer-events-none" />
      
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-6">
        <div className="space-y-3">
          <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-white/10 border border-white/15 text-xs font-semibold backdrop-blur-md">
            <UserCheck className="w-3.5 h-3.5 text-[color:var(--color-primary-light)]" />
            <span>{roleTitle}</span>
          </div>

          <h1 className="text-2xl md:text-3xl font-extrabold tracking-tight">
            {t('welcome_greeting')} <span className="text-[hsl(var(--accent-foreground))] dark:text-emerald-400 font-bold">{name || '...'}</span>
          </h1>

          <p className="text-[hsl(var(--ink-3))] text-sm max-w-xl font-medium leading-relaxed">
            {subtext || t('welcome_subtext')}
          </p>

          <div className="flex items-center gap-2 text-white/60 text-xs font-semibold pt-1">
            <Calendar className="w-4 h-4 text-[hsl(var(--accent-foreground))]" />
            <span>{formattedDate}</span>
          </div>
        </div>

        {stats && stats.length > 0 && (
          <div className="grid grid-cols-2 sm:flex sm:items-center gap-3 md:gap-4 shrink-0">
            {stats.map((stat, idx) => (
              <div 
                key={idx} 
                className="bg-white/5 border border-white/10 hover:border-white/20 transition-all rounded-[var(--radius)] p-4 min-w-[120px] text-center"
              >
                <div className="text-2xl font-bold text-[hsl(var(--accent-foreground))] dark:text-emerald-400 amount mb-0.5">
                  {stat.value}
                </div>
                <div className="text-[11px] font-bold text-white/70 uppercase tracking-wider">
                  {stat.label}
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
