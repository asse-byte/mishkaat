/**
 * ورقة تقرير الطالب — تُطبع أو تُحفَظ PDF من متصفّح الجهاز (FR15).
 *
 * المتطلَّب في تقرير Halaqtna جاء من المقابلات: وليّ الأمر يسأل «كيف حال ابني؟»
 * ولم يكن بيد المحفّظ ما يناوله. تقارير المشكاة كلها على مستوى المركز، فهذه
 * أوّل ورقة تخصّ طالباً واحداً.
 *
 * **كل لون هنا قيمة سداسية ثابتة، لا رمز من نظام التصميم.** الورقة تُطبع على
 * ورق أبيض دائماً، ورموز النظام تنقلب في الوضع الليلي: من يطبع ليلاً يحصل على
 * نصّ فاتح على ورق أبيض. هذا الخطأ نفسه كان في شهادة المسابقات وإيصال المالية.
 */

const INK = '#151A24';
const INK_2 = '#39404E';
const INK_3 = '#5B6474';
const LINE = '#D8DCE4';
const NICHE = '#1B233C';
const BRASS = '#B0801F';
const BRASS_WASH = '#FBF4E6';

export interface ReportMetrics {
  mastery: number | null;
  momentum: number;
  precision: number | null;
  consistency: number | null;
  review_depth: number | null;
  error_density: number;
  attendance_rate: number;
  pages_memorized: number;
  sessions_count: number;
}

export interface ReportForecast {
  current_juz: number;
  juz_completion_date: string | null;
  juz_eta_days: number;
  quran_completion_date: string | null;
  projected_weekly_pages: number;
  method: string;
}

const METRICS: { key: keyof ReportMetrics; label: string; unit: string }[] = [
  { key: 'mastery',      label: 'الإتقان',      unit: '%' },
  { key: 'momentum',     label: 'الزخم',        unit: 'صفحة/أسبوع' },
  { key: 'precision',    label: 'الدقّة',         unit: '%' },
  { key: 'consistency',  label: 'الانتظام',     unit: '%' },
  { key: 'review_depth', label: 'عمق المراجعة', unit: '%' },
];

export default function StudentReportSheet({
  studentName,
  halaqahName,
  centerName,
  metrics,
  forecast,
  journeyPercent,
  totalPages,
  badges,
  totalXp,
}: {
  studentName: string;
  halaqahName?: string;
  centerName?: string;
  metrics: ReportMetrics;
  forecast: ReportForecast;
  journeyPercent: number;
  totalPages: number;
  badges: { label_ar: string; earned: boolean }[];
  totalXp: number;
}) {
  const today = new Date().toLocaleDateString('ar-EG', {
    year: 'numeric', month: 'long', day: 'numeric',
  });
  const earned = badges.filter(b => b.earned);

  return (
    <div
      className="hidden print:block"
      dir="rtl"
      style={{ background: '#fff', color: INK, padding: '18mm 14mm', fontSize: '11pt' }}
    >
      {/* ---------------- الترويسة ---------------- */}
      <header style={{ borderBottom: `2px solid ${NICHE}`, paddingBottom: 12, marginBottom: 18 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-end', gap: 16 }}>
          <div>
            <p style={{ fontSize: '9pt', color: INK_3, margin: 0 }}>
              {centerName || 'مركز تحفيظ القرآن الكريم'}
            </p>
            <h1 style={{ fontSize: '18pt', margin: '2px 0 0', color: NICHE }}>
              تقرير متابعة الطالب
            </h1>
          </div>
          <div style={{ textAlign: 'left' }}>
            <p style={{ fontSize: '9pt', color: INK_3, margin: 0 }}>نظام المشكاة</p>
            <p style={{ fontSize: '9pt', color: INK_3, margin: 0 }}>{today}</p>
          </div>
        </div>
      </header>

      {/* ---------------- بطاقة الطالب ---------------- */}
      <section style={{ marginBottom: 16 }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '11pt' }}>
          <tbody>
            <tr>
              <td style={{ padding: '4px 0', color: INK_3, width: '22%' }}>اسم الطالب</td>
              <td style={{ padding: '4px 0', fontWeight: 700 }}>{studentName}</td>
              <td style={{ padding: '4px 0', color: INK_3, width: '18%' }}>الحلقة</td>
              <td style={{ padding: '4px 0', fontWeight: 700 }}>{halaqahName || '—'}</td>
            </tr>
            <tr>
              <td style={{ padding: '4px 0', color: INK_3 }}>المحفوظ</td>
              <td style={{ padding: '4px 0', fontWeight: 700 }}>
                {metrics.pages_memorized} صفحة من {totalPages} ({journeyPercent}%)
              </td>
              <td style={{ padding: '4px 0', color: INK_3 }}>عدد الجلسات</td>
              <td style={{ padding: '4px 0', fontWeight: 700 }}>{metrics.sessions_count}</td>
            </tr>
          </tbody>
        </table>
      </section>

      {/* ---------------- المقاييس ---------------- */}
      <section style={{ marginBottom: 16 }}>
        <h2 style={{ fontSize: '12pt', color: NICHE, margin: '0 0 8px' }}>مؤشّرات الأداء</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5pt' }}>
          <tbody>
            {METRICS.map(m => {
              const v = metrics[m.key] as number | null;
              return (
                <tr key={m.key} style={{ borderBottom: `1px solid ${LINE}` }}>
                  <td style={{ padding: '6px 0', color: INK_2, width: '35%' }}>{m.label}</td>
                  <td style={{ padding: '6px 0', fontWeight: 700, width: '20%' }}>
                    {v === null ? 'لم يُقَس بعد' : `${v} ${m.unit}`}
                  </td>
                  <td style={{ padding: '6px 0' }}>
                    {/* شريط بسيط: الطابعة قد تُسقط الخلفيات، فالإطار يبقى دالاً */}
                    {v !== null && m.key !== 'momentum' && (
                      <span style={{
                        display: 'inline-block', width: '100%', maxWidth: 220, height: 8,
                        border: `1px solid ${LINE}`, position: 'relative',
                      }}>
                        <span style={{
                          display: 'block', height: '100%',
                          width: `${Math.min(100, v)}%`, background: BRASS,
                        }} />
                      </span>
                    )}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
        <p style={{ fontSize: '8.5pt', color: INK_3, marginTop: 6 }}>
          الإتقان يقيس قلّة الخطأ في الصفحة · الزخم وتيرة الحفظ الأسبوعية ·
          الدقّة نصيب الأخطاء الخفيفة · الانتظام الحضور في آخر ثماني حصص ·
          عمق المراجعة نسبة المراجعة إلى الحفظ الجديد.
        </p>
      </section>

      {/* ---------------- التوقّع ---------------- */}
      <section style={{
        marginBottom: 16, background: BRASS_WASH,
        border: `1px solid ${BRASS}`, padding: '10px 12px',
      }}>
        <h2 style={{ fontSize: '12pt', color: NICHE, margin: '0 0 6px' }}>موعد الختم المتوقَّع</h2>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10.5pt' }}>
          <tbody>
            <tr>
              <td style={{ padding: '3px 0', color: INK_2, width: '35%' }}>
                ختم الجزء {forecast.current_juz}
              </td>
              <td style={{ padding: '3px 0', fontWeight: 700 }}>
                {forecast.juz_completion_date || 'غير محدَّد'}
                {forecast.juz_eta_days > 0 && (
                  <span style={{ color: INK_3, fontWeight: 400 }}>
                    {' '}— بعد نحو {forecast.juz_eta_days} يوماً
                  </span>
                )}
              </td>
            </tr>
            <tr>
              <td style={{ padding: '3px 0', color: INK_2 }}>ختم المصحف كاملاً</td>
              <td style={{ padding: '3px 0', fontWeight: 700 }}>
                {forecast.quran_completion_date || 'غير محدَّد بالوتيرة الحالية'}
              </td>
            </tr>
          </tbody>
        </table>
        <p style={{ fontSize: '8.5pt', color: INK_3, margin: '6px 0 0' }}>
          تقدير محسوب من وتيرة الطالب ({forecast.projected_weekly_pages} صفحة أسبوعياً)
          وجودة تلاوته (كثافة الخطأ {metrics.error_density} لكل صفحة) وحضوره
          ({Math.round(metrics.attendance_rate * 100)}%). يتغيّر بتغيّرها، وليس وعداً.
        </p>
      </section>

      {/* ---------------- الأوسمة ---------------- */}
      {earned.length > 0 && (
        <section style={{ marginBottom: 16 }}>
          <h2 style={{ fontSize: '12pt', color: NICHE, margin: '0 0 6px' }}>
            الأوسمة المُحرَزة ({earned.length}) · {totalXp} نقطة
          </h2>
          <p style={{ fontSize: '10.5pt', margin: 0, lineHeight: 1.9 }}>
            {earned.map(b => b.label_ar).join(' · ')}
          </p>
        </section>
      )}

      {/* ---------------- التوقيعات ---------------- */}
      <footer style={{ marginTop: 28, paddingTop: 10, borderTop: `1px solid ${LINE}` }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '10pt' }}>
          <tbody>
            <tr>
              <td style={{ width: '50%', paddingLeft: 24 }}>
                <p style={{ color: INK_3, margin: '0 0 26px' }}>توقيع المحفّظ</p>
                <div style={{ borderBottom: `1px solid ${LINE}` }} />
              </td>
              <td style={{ width: '50%', paddingRight: 24 }}>
                <p style={{ color: INK_3, margin: '0 0 26px' }}>اطّلاع وليّ الأمر</p>
                <div style={{ borderBottom: `1px solid ${LINE}` }} />
              </td>
            </tr>
          </tbody>
        </table>
        <p style={{ fontSize: '8pt', color: INK_3, marginTop: 14, textAlign: 'center' }}>
          صدر آلياً من نظام المشكاة في {today}
        </p>
      </footer>
    </div>
  );
}
