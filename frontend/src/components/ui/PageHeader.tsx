import React from 'react';

/**
 * ترويسة صفحة موحّدة.
 *
 * كانت كل صفحة تفتح بلوحة كحلية صمّاء (rounded-[var(--radius-lg)] p-6 text-white gradient-primary)
 * فيها دائرة زخرفية شفّافة. المشكلة ليست الذوق: اللوحة تأخذ ١٢٠ بكسل من أعلى كل
 * شاشة لتقول اسم الصفحة — وهو مكتوب أصلاً في الشريط العلوي وفي الشريط الجانبي —
 * فيُدفع العمل الحقيقي تحت الطيّة. والعنوان الأبيض على الكحلي كان أثقل عنصر في
 * الصفحة، أي أن أقلّ شيء فائدةً كان أشدّها حضوراً.
 *
 * البديل سطر طباعي واحد: العنوان، وسطر يشرح، وأزرار الفعل في الطرف المقابل.
 */
export default function PageHeader({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: React.ReactNode;
  children?: React.ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2">
      <div className="min-w-0">
        <h1 className="text-xl md:text-2xl">{title}</h1>
        {subtitle && (
          <p className="text-sm text-[hsl(var(--ink-3))] mt-0.5">{subtitle}</p>
        )}
      </div>
      {children && (
        <div className="flex items-center gap-2 shrink-0">{children}</div>
      )}
    </header>
  );
}
