import { useState, useEffect } from 'react';

type Locale = 'ar' | 'en' | 'fr';

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
  en: {
    welcome_greeting: 'Welcome back,',
    welcome_subtext: 'We pray for your success and guidance in your Quranic journey today.',
    term_students: 'Students',
    term_teachers: 'Teachers',
    term_halaqat: 'Halaqat (Circles)',
    term_attendance: 'Attendance',
    term_recitations: 'Recitations',
    finance_fees: 'Finance & Fees',
    action_add: 'Add New',
    empty_no_students: 'No students registered at the moment.',
    empty_no_recitations: 'No recitations recorded today.',
    empty_no_halaqat: 'No active halaqat at the moment.',
    empty_general: 'No data available to display.',
    status_present: 'Present',
    status_absent: 'Absent',
    status_excused: 'Excused',
    rate_attendance: 'Attendance Rate',
    recitations_today: "Today's Recitations",
    top_students: 'Top Performing Students',
    recent_activity: 'Recent Activity',
    stats_overview: 'Statistics Overview',
    role_admin: 'System Admin',
    role_super_admin: 'Super Admin',
    role_center_manager: 'Center Manager',
    role_teacher: 'Teacher',
    role_student: 'Student',
    role_parent: 'Parent',
  },
  fr: {
    welcome_greeting: 'Bienvenue,',
    welcome_subtext: 'Que Dieu vous accorde le succès et la guidée dans votre parcours coranique aujourd\'hui.',
    term_students: 'Élèves',
    term_teachers: 'Enseignants',
    term_halaqat: 'Cercles (Halaqat)',
    term_attendance: 'Présence',
    term_recitations: 'Récitations',
    finance_fees: 'Finance & Frais',
    action_add: 'Ajouter',
    empty_no_students: 'Aucun élève inscrit pour le moment.',
    empty_no_recitations: 'Aucune récitation enregistrée aujourd\'hui.',
    empty_no_halaqat: 'Aucun cercle actif pour le moment.',
    empty_general: 'Aucune donnée disponible à afficher.',
    status_present: 'Présent',
    status_absent: 'Absent',
    status_excused: 'Excusé',
    rate_attendance: 'Taux de Présence',
    recitations_today: "Récitations d'aujourd'hui",
    top_students: 'Élèves les plus performants',
    recent_activity: 'Activité Récente',
    stats_overview: 'Aperçu des Statistiques',
    role_admin: 'Administrateur',
    role_super_admin: 'Super Administrateur',
    role_center_manager: 'Directeur de Centre',
    role_teacher: 'Enseignant',
    role_student: 'Élève',
    role_parent: 'Parent',
  }
};

export function useTranslation() {
  const [locale, setLocale] = useState<Locale>(() => {
    return (localStorage.getItem('language') as Locale) || 'ar';
  });

  useEffect(() => {
    const handleStorageChange = () => {
      const currentLanguage = (localStorage.getItem('language') as Locale) || 'ar';
      if (currentLanguage !== locale) {
        setLocale(currentLanguage);
      }
    };

    window.addEventListener('storage', handleStorageChange);
    // Custom event to handle direct local updates
    window.addEventListener('languagechange', handleStorageChange);

    return () => {
      window.removeEventListener('storage', handleStorageChange);
      window.removeEventListener('languagechange', handleStorageChange);
    };
  }, [locale]);

  const changeLanguage = (newLocale: Locale) => {
    localStorage.setItem('language', newLocale);
    setLocale(newLocale);
    // Dispatch a custom event to notify other hook instances
    window.dispatchEvent(new Event('languagechange'));
  };

  const t = (key: keyof typeof translations['ar']) => {
    const dict = translations[locale] || translations['ar'];
    return dict[key] || translations['ar'][key] || String(key);
  };

  const isRTL = locale === 'ar';

  return {
    t,
    locale,
    changeLanguage,
    isRTL,
  };
}
