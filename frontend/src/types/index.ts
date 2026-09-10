export type UserRole = 'admin' | 'super_admin' | 'center_manager' | 'teacher' | 'student' | 'parent';

export interface User {
  id: string;
  username: string;
  name: string;
  email?: string;
  role: UserRole;
  center_id?: string;
  phone?: string;
  created_at: string;
  is_active: boolean;
}

export interface Center {
  id: string;
  name: string;
  address: string;
  phone?: string;
  manager_id?: string;
  manager_name?: string;
  /** عملة المركز — تُقرأ في شاشة المالية، وكانت غائبة عن النوع */
  currency?: string;
  status?: string;
  /** شعار المركز في مخزن الملفّات؛ يُقرأ من /api/centers/{id}/logo */
  logo_file_id?: string | null;
  created_at: string;
  is_active: boolean;
}

export interface Student {
  id: string;
  name: string;
  date_of_birth?: string;
  phone?: string;
  parent_id?: string;
  center_id: string;
  halaqah_id?: string;
  enrollment_date: string;
  is_active: boolean;
}

export interface Teacher {
  id: string;
  user_id: string;
  name: string;
  phone?: string;
  center_id: string;
  specialization?: string;
  hire_date: string;
  is_active: boolean;
}

export interface Halaqah {
  id: string;
  name: string;
  teacher_id: string;
  center_id: string;
  schedule: string;
  max_students: number;
  current_students: number;
  is_active: boolean;
}

export interface Recitation {
  id: string;
  student_id: string;
  teacher_id: string;
  date: string;
  surah_number: number;
  surah_name: string;
  start_ayah: number;
  end_ayah: number;
  evaluation: 'excellent' | 'good' | 'acceptable' | 'needs_improvement';
  mistakes_count: number;
  notes?: string;
  recitation_type: 'new' | 'review';
  // Populated by API
  student_name?: string;
}

export interface Attendance {
  id: string;
  student_id: string;
  halaqah_id: string;
  date: string;
  status: 'present' | 'absent' | 'late' | 'excused';
  notes?: string;
  // Populated by API
  student_name?: string;
  date_str?: string;
}

export interface Fee {
  id: string;
  student_id: string;
  amount: number;
  due_date: string;
  paid_date?: string;
  status: 'pending' | 'paid' | 'overdue';
  fee_type: 'monthly' | 'annual' | 'registration';
  notes?: string;
}

export interface QuranSurah {
  number: number;
  name: string;
  english_name: string;
  ayah_count: number;
  revelation_type: 'meccan' | 'medinan';
  juz_start: number;
  juz_end: number;
}

export interface MemorizationProgress {
  student_id: string;
  total_ayahs_memorized: number;
  total_juz_completed: number;
  current_surah: number;
  current_ayah: number;
  completion_percentage: number;
  last_updated: string;
}

export interface DashboardStats {
  total_students?: number;
  total_teachers?: number;
  total_centers?: number;
  total_halaqat?: number;
  attendance_rate?: number;
  memorization_progress?: number;
  pending_fees?: number;
  recent_activities?: Activity[];
}

export interface Activity {
  id: string;
  type: 'recitation' | 'attendance' | 'payment' | 'enrollment';
  description: string;
  timestamp: string;
  user_id: string;
}

export interface AuthResponse {
  access_token: string;
  token_type: string;
  user: User;
  // [إصلاح 2026-09-03] الخادم يُصدر هذين منذ البداية ولم تكن الواجهة تعرفهما،
  // فكان المستخدم يُطرَد إلى شاشة الدخول عند انتهاء صلاحية التوكن (ساعة) بلا تجديد.
  refresh_token?: string | null;
  expires_in?: number | null;
}

export interface ApiError {
  detail: string;
}
