/**
 * نصوصٌ مشتركة — بالعربية وحدها.
 *
 * [قرار المالك 2026-09-06] «النظام يكون باللغة العربية فقط، وليس لديّ النيّة
 * إطلاقاً إضافةُ لغةٍ أخرى.»
 *
 * وكان هنا ثلاثة قواميس (ar / en / fr) تُختار بـ localStorage.language، وفي
 * الإعدادات مُنتقي لغةٍ يَعِد بـ«English (قريباً)». فلم يكن هذا اختياراً
 * معطَّلاً بل قنبلةً موقوتة: قيمةٌ واحدة في التخزين المحلّي تقلب نصفَ لوحات
 * التحكّم إلى الإنجليزية وتقلب اتجاه الصفحة معها، بلا زرٍّ يُعيدها.
 *
 * فبقي `t()` كما هو حتى لا تتغيّر الشاشات التي تستدعيه، وذهب ما سواه.
 */
import { useMemo } from 'react';

const translations = {
  ar: {
    welcome_greeting: 'مرحباً بك،',
    welcome_subtext: 'نسأل الله لك التوفيق والقبول في مسيرتك القرآنية اليوم.',
    term_students: 'الطلاب',
    term_teachers: 'المحفظون',
    term_halaqat: 'الحلقات',
    term_attendance: 'الحضور والغياب',
    term_recitations: 'التسميع',
    finance_fees: 'المالية والرسوم',
    action_add: 'إضافة جديد',
    empty_no_students: 'لا يوجد طلاب مسجلين حالياً.',
    empty_no_recitations: 'لا توجد جلسات تسميع مسجلة اليوم.',
    empty_no_halaqat: 'لا توجد حلقات نشطة حالياً.',
    empty_general: 'لا توجد بيانات لعرضها.',
    status_present: 'حاضر',
    status_absent: 'غائب',
    status_excused: 'مستأذن',
    rate_attendance: 'نسبة الحضور',
    recitations_today: 'تسميع اليوم',
    top_students: 'الطلاب الأكثر تميزاً',
    recent_activity: 'النشاط الأخير',
    stats_overview: 'نظرة عامة على الإحصائيات',
    role_admin: 'مدير النظام',
    role_super_admin: 'المدير العام',
    role_center_manager: 'مدير المركز',
    role_teacher: 'محفظ',
    role_student: 'طالب',
    role_parent: 'ولي أمر',
  },
};

type Key = keyof typeof translations['ar'];

export function useTranslation() {
  const t = useMemo(() => (key: Key) => translations.ar[key] || String(key), []);
  // يبقيان في الواجهة لأن الشاشات تقرؤهما، وقيمتُهما ثابتة
  return { t, locale: 'ar' as const, isRTL: true };
}
