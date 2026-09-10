import { useEffect, useState } from 'react';
import { formatWhileTyping, parseNumber, stripGrouping } from '@/lib/format';

/**
 * حقل رقمي يُجمّع الخانات أثناء الكتابة: 1,000,000 لا 1000000.
 *
 * السبب ليس الشكل. الرقم غير المجمَّع لا يُقرأ بالنظر، فيزيد المدخِل صفراً أو
 * ينقصه ولا يلحظ — ومبلغٌ في مليون بدل مئة ألف خطأٌ يُكتشف بعد أن يدخل السجلّ
 * المالي. التجميعُ أثناء الكتابة يُري الخطأ في اللحظة التي يقع فيها.
 *
 * الحقل من نوع text لا number عن قصد: حقل number لا يقبل الفاصلة أصلاً، ولا
 * يعرض تجميعاً، ويُظهر سهمَي زيادة يمكن أن يُغيّرا المبلغ بلمسة عابرة على
 * الهاتف. و inputMode="decimal" يفتح لوحة الأرقام على الجوّال.
 *
 * القيمة المُعادة عبر onChange رقمٌ نظيف بلا فواصل — لا يرى المستدعي التنسيق.
 */
export default function NumberInput({
  value,
  onChange,
  placeholder,
  className = 'form-input',
  disabled,
  required,
  min,
  suffix,
  id,
  'aria-label': ariaLabel,
}: {
  /** القيمة الخام: رقم أو نصّ رقمي أو '' */
  value: number | string;
  /** تُستدعى بالنصّ الخام بلا فواصل، ليبقى المستدعي على ما اعتاده */
  onChange: (raw: string) => void;
  placeholder?: string;
  className?: string;
  disabled?: boolean;
  required?: boolean;
  min?: number;
  /** رمز يظهر داخل الحقل، كالعملة */
  suffix?: string;
  id?: string;
  'aria-label'?: string;
}) {
  const [text, setText] = useState(() => formatWhileTyping(String(value ?? '')));

  // تغيّر القيمة من الخارج (إعادة تعيين النموذج، أو تحميل سجلّ للتعديل)
  useEffect(() => {
    const incoming = stripGrouping(String(value ?? ''));
    if (incoming !== stripGrouping(text)) {
      setText(formatWhileTyping(String(value ?? '')));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const handle = (raw: string) => {
    const shown = formatWhileTyping(raw);
    setText(shown);
    const n = parseNumber(shown);
    onChange(Number.isNaN(n) ? '' : String(n));
  };

  const input = (
    <input
      id={id}
      type="text"
      inputMode="decimal"
      dir="ltr"
      className={className}
      style={suffix ? { paddingLeft: '3.5rem' } : undefined}
      placeholder={placeholder}
      disabled={disabled}
      required={required}
      aria-label={ariaLabel}
      value={text}
      onChange={e => handle(e.target.value)}
      onBlur={() => {
        const n = parseNumber(text);
        if (!Number.isNaN(n) && min !== undefined && n < min) {
          handle(String(min));
        }
      }}
    />
  );

  if (!suffix) return input;
  return (
    <div className="relative">
      {input}
      <span className="absolute inset-y-0 left-3 flex items-center text-xs font-semibold
                       text-[hsl(var(--ink-3))] pointer-events-none">
        {suffix}
      </span>
    </div>
  );
}
