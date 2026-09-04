import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { AuthResponse, User, DashboardStats, Student, Teacher, Halaqah, Center, Recitation, Attendance, Fee } from '@/types';

const USER_KEY = 'user';

/**
 * [إصلاح 2026-09-04] توكن الوصول في الذاكرة، وتوكن التجديد في كعكة httpOnly.
 *
 * كان الاثنان في localStorage — وكل ما فيه تقرؤه أي شيفرة تعمل في الصفحة.
 * ثغرةُ XSS واحدة (في اعتمادية، في إعلان، في امتداد متصفّح) كانت تكفي لسرقة
 * توكن تجديد صالح سبعة أيام، يُدوَّر بهدوء فيبقى المهاجم داخل الحساب حتى بعد
 * أن يغيّر المالكُ كلمة مرورَه على جهاز آخر.
 *
 * الآن: توكن التجديد لا تراه JavaScript إطلاقاً (الخادم يضعه في كعكة httpOnly
 * ويرسلها المتصفّح تلقائياً إلى /api/auth). وتوكن الوصول يعيش في متغيّر داخل
 * الوحدة وحدها، فيزول بإغلاق التبويب — وعمره ساعة على أي حال.
 *
 * وبقاء الجلسة عبر إعادة التحميل لم يُفقد: عند الإقلاع بلا توكن في الذاكرة
 * تُنادى /auth/refresh، فتصل الكعكة وحدها وتعيد توكن وصول جديداً.
 */
let accessToken: string | null = null;

export const tokenStore = {
  access: () => accessToken,
  set(token: string | null) { accessToken = token; },
  clear() {
    accessToken = null;
    localStorage.removeItem(USER_KEY);
    // بقايا الإصدار السابق: توكنات كانت تُحفَظ في localStorage
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
  },
};

const api = axios.create({
  baseURL: '/api',
  // لازم لإرسال كعكة توكن التجديد إلى /api/auth
  withCredentials: true,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = tokenStore.access();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

/**
 * [إصلاح 2026-09-03] تجديد صامت للتوكن.
 *
 * قبله: الواجهة تحفظ توكن الوصول وحده وتتجاهل refresh_token تماماً، فكان كل مستخدم يُقذَف إلى
 * شاشة الدخول كل ساعة في منتصف عمله. والمعترض القديم كان يمسح الجلسة عند أي 401 — بما فيها 401
 * الناتجة عن كلمة مرور خاطئة في شاشة الدخول نفسها.
 *
 * بعده: أول 401 على طلب عادي تُطلق تجديداً واحداً (single-flight: الطلبات المتزامنة تنتظر النتيجة
 * نفسها ولا تستهلك كل واحدة توكن تجديد — والخادم يُدوّر توكن التجديد ويُبطل القديم، فتجديدان
 * متوازيان كانا سيُبطلان أحدهما الآخر ويُخرجان المستخدم).
 */
const AUTH_PATHS = ['/auth/login', '/auth/refresh', '/auth/logout'];
const isAuthPath = (url?: string) => !!url && AUTH_PATHS.some((p) => url.includes(p));

let refreshInFlight: Promise<string> | null = null;

async function refreshAccessToken(): Promise<string> {
  // لا يُقرأ توكن تجديد من هنا: الكعكة httpOnly يرسلها المتصفّح وحده.
  // axios خام لا يمرّ بمعترضات هذا العميل، وإلا لدار التجديد على نفسه عند فشله.
  const { data } = await axios.post<AuthResponse>('/api/auth/refresh', {}, { withCredentials: true });
  tokenStore.set(data.access_token);
  return data.access_token;
}

/** يُستدعى عند الإقلاع: يستعيد الجلسة من الكعكة وحدها */
export async function restoreSession(): Promise<AuthResponse | null> {
  try {
    const { data } = await axios.post<AuthResponse>('/api/auth/refresh', {}, { withCredentials: true });
    tokenStore.set(data.access_token);
    return data;
  } catch {
    return null;
  }
}

/** تُضبط من AuthProvider حتى يُفرَّغ حالة React أيضاً، لا التخزين فقط */
let onSessionExpired: (() => void) | null = null;
export const setSessionExpiredHandler = (fn: (() => void) | null) => {
  onSessionExpired = fn;
};

function endSession() {
  tokenStore.clear();
  if (onSessionExpired) {
    onSessionExpired();
  } else if (window.location.pathname !== '/login') {
    window.location.href = '/login';
  }
}

api.interceptors.response.use(
  (response) => response,
  async (error: AxiosError) => {
    const original = error.config as (InternalAxiosRequestConfig & { _retried?: boolean }) | undefined;

    // 403 ليست انتهاء جلسة بل نقص صلاحية — إخراج المستخدم عندها خطأ
    if (error.response?.status !== 401 || !original || original._retried || isAuthPath(original.url)) {
      return Promise.reject(error);
    }

    original._retried = true;
    try {
      if (!refreshInFlight) {
        refreshInFlight = refreshAccessToken().finally(() => {
          refreshInFlight = null;
        });
      }
      const token = await refreshInFlight;
      original.headers.Authorization = `Bearer ${token}`;
      return api(original);
    } catch {
      endSession();
      return Promise.reject(error);
    }
  }
);

// Auth endpoints
export const authApi = {
  login: async (username: string, password: string): Promise<AuthResponse> => {
    const formData = new FormData();
    formData.append('username', username);
    formData.append('password', password);
    const response = await api.post<AuthResponse>('/auth/login', formData, {
      headers: { 'Content-Type': 'multipart/form-data' },
    });
    return response.data;
  },

  // [إصلاح 2026-09-03] يُرسل توكن التجديد ليُبطله الخادم فعلاً.
  // بدونه يبقى التوكن صالحاً سبعة أيام بعد "الخروج" — وهو ما يعنيه الخروج على جهاز مشترك.
  logout: async (): Promise<void> => {
    // الخادم يُبطل توكن التجديد ويمسح الكعكة؛ لا شيء يُرسَل من هنا
    await api.post('/auth/logout', {});
  },

  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },
};

// Dashboard endpoints
export const dashboardApi = {
  // [إصلاح 2026-09-03] كان `/dashboard/${role}` — مسار لا وجود له في الخادم (404 مؤكدة).
  // الخادم يستنتج الدور من التوكن ويردّ إحصاءات النطاق المناسب.
  getStats: async (): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>('/dashboard/stats');
    return response.data;
  },
};

// Centers endpoints
export const centersApi = {
  getAll: async (): Promise<Center[]> => {
    const response = await api.get<Center[]>('/centers');
    return response.data;
  },
  
  // [إصلاح 2026-09-03] المسار الحقيقي هو /centers/{id}/details
  getById: async (id: string): Promise<Center> => {
    const response = await api.get<Center>(`/centers/${id}/details`);
    return response.data;
  },
  
  create: async (data: Partial<Center>): Promise<Center> => {
    const response = await api.post<Center>('/centers', data);
    return response.data;
  },
  
  update: async (id: string, data: Partial<Center>): Promise<Center> => {
    const response = await api.put<Center>(`/centers/${id}`, data);
    return response.data;
  },
  
  delete: async (id: string): Promise<void> => {
    await api.delete(`/centers/${id}`);
  },
};

// Students endpoints
export const studentsApi = {
  getAll: async (): Promise<Student[]> => {
    const response = await api.get<Student[]>('/students');
    return response.data;
  },
  
  getById: async (id: string): Promise<Student> => {
    const response = await api.get<Student>(`/students/${id}`);
    return response.data;
  },
  
  create: async (data: Partial<Student>): Promise<Student> => {
    const response = await api.post<Student>('/students', data);
    return response.data;
  },
  
  update: async (id: string, data: Partial<Student>): Promise<Student> => {
    const response = await api.put<Student>(`/students/${id}`, data);
    return response.data;
  },
  
  delete: async (id: string): Promise<void> => {
    await api.delete(`/students/${id}`);
  },
};

// Teachers endpoints
export const teachersApi = {
  getAll: async (): Promise<Teacher[]> => {
    const response = await api.get<Teacher[]>('/teachers');
    return response.data;
  },
  
  create: async (data: Partial<Teacher>): Promise<Teacher> => {
    const response = await api.post<Teacher>('/teachers', data);
    return response.data;
  },
  
  update: async (id: string, data: Partial<Teacher>): Promise<Teacher> => {
    const response = await api.put<Teacher>(`/teachers/${id}`, data);
    return response.data;
  },
  
  delete: async (id: string): Promise<void> => {
    await api.delete(`/teachers/${id}`);
  },
};

// Halaqat endpoints
export const halaqatApi = {
  getAll: async (): Promise<Halaqah[]> => {
    const response = await api.get<Halaqah[]>('/halaqat');
    return response.data;
  },
  
  create: async (data: Partial<Halaqah>): Promise<Halaqah> => {
    const response = await api.post<Halaqah>('/halaqat', data);
    return response.data;
  },
  
  update: async (id: string, data: Partial<Halaqah>): Promise<Halaqah> => {
    const response = await api.put<Halaqah>(`/halaqat/${id}`, data);
    return response.data;
  },
  
  delete: async (id: string): Promise<void> => {
    await api.delete(`/halaqat/${id}`);
  },
};

// Recitations endpoints
export const recitationsApi = {
  getAll: async (): Promise<Recitation[]> => {
    const response = await api.get<Recitation[]>('/recitations');
    return response.data;
  },
  
  getByStudent: async (studentId: string): Promise<Recitation[]> => {
    const response = await api.get<Recitation[]>(`/recitations/student/${studentId}`);
    return response.data;
  },
  
  create: async (data: Partial<Recitation>): Promise<Recitation> => {
    const response = await api.post<Recitation>('/recitations', data);
    return response.data;
  },

  // حذف ناعم: يبقى السجل في قاعدة البيانات ويخرج من كل حساب ودرجة
  remove: async (id: string): Promise<void> => {
    await api.delete(`/recitations/${id}`);
  },
};

// Attendance endpoints
export const attendanceApi = {
  getAll: async (): Promise<Attendance[]> => {
    const response = await api.get<Attendance[]>('/attendance');
    return response.data;
  },
  
  getByStudent: async (studentId: string): Promise<Attendance[]> => {
    const response = await api.get<Attendance[]>(`/attendance/student/${studentId}`);
    return response.data;
  },
  
  getByHalaqah: async (halaqahId: string, date?: string): Promise<Attendance[]> => {
    const params = date ? { date } : {};
    const response = await api.get<Attendance[]>(`/attendance/halaqah/${halaqahId}`, { params });
    return response.data;
  },
  
  create: async (data: Partial<Attendance>): Promise<Attendance> => {
    const response = await api.post<Attendance>('/attendance', data);
    return response.data;
  },

};

// Fees endpoints
export const feesApi = {
  getAll: async (): Promise<Fee[]> => {
    const response = await api.get<Fee[]>('/fees');
    return response.data;
  },
  
  getByStudent: async (studentId: string): Promise<Fee[]> => {
    const response = await api.get<Fee[]>(`/fees/student/${studentId}`);
    return response.data;
  },
  
  create: async (data: Partial<Fee>): Promise<Fee> => {
    const response = await api.post<Fee>('/fees', data);
    return response.data;
  },
  
  markAsPaid: async (id: string): Promise<Fee> => {
    const response = await api.post<Fee>(`/fees/${id}/pay`);
    return response.data;
  },
};

export default api;
