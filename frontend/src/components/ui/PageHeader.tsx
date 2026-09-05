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
 *
 * `min-w-0` على كتلة العنوان ليست زينة: عنصر flex عرضه الأدنى `auto` أي عرض
 * أطول سطر فيه، فيرفض الانكماش ويدفع الصفحة كلها أعرض من الشاشة. هذا بالضبط ما
 * كان يحدث في الصفحات التي كانت تكتب ترويستها بيدها: على شاشة 375 بكسل كانت
 * صفحة «التقارير» تمتدّ إلى 676 بكسل وتُمرَّر أفقياً.
 */
export default function PageHeader({
  title,
  subtitle,
  className = '',
  children,
}: {
  /** نصّ أو عقدة — بعض الصفحات تسبق عنوانها بأيقونة */
  title: React.ReactNode;
  subtitle?: React.ReactNode;
  /** لحالات مثل `print:hidden` */
  className?: string;
  children?: React.ReactNode;
}) {
  return (
    <header className={`flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 ${className}`}>
      <div className="min-w-0">
        <h1 className="text-xl md:text-2xl flex items-center gap-2">{title}</h1>
        {subtitle && (
          <p className="text-sm text-[hsl(var(--ink-3))] mt-0.5">{subtitle}</p>
        )}
      </div>
      {children && (
        <div className="flex items-center gap-2 shrink-0 flex-wrap">{children}</div>
      )}
    </header>
  );
}
