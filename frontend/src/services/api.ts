import axios from 'axios';
import type { AxiosError, InternalAxiosRequestConfig } from 'axios';
import type { AuthResponse, User, DashboardStats, Student, Teacher, Halaqah, Center, Recitation, Attendance, Fee } from '@/types';

const ACCESS_KEY = 'access_token';
const REFRESH_KEY = 'refresh_token';
const USER_KEY = 'user';

/** مخزن التوكنات — نقطة واحدة للقراءة والكتابة والمسح */
export const tokenStore = {
  access: () => localStorage.getItem(ACCESS_KEY),
  refresh: () => localStorage.getItem(REFRESH_KEY),
  save(auth: Pick<AuthResponse, 'access_token' | 'refresh_token'>) {
    localStorage.setItem(ACCESS_KEY, auth.access_token);
    if (auth.refresh_token) {
      localStorage.setItem(REFRESH_KEY, auth.refresh_token);
    }
  },
  clear() {
    localStorage.removeItem(ACCESS_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
  },
};

const api = axios.create({
  baseURL: '/api',
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
  const refresh_token = tokenStore.refresh();
  if (!refresh_token) throw new Error('no refresh token');
  // axios خام لا يمرّ بمعترضات هذا العميل، وإلا لدار التجديد على نفسه عند فشله
  const { data } = await axios.post<AuthResponse>('/api/auth/refresh', { refresh_token });
  tokenStore.save(data);
  return data.access_token;
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
    const refresh_token = tokenStore.refresh();
    await api.post('/auth/logout', refresh_token ? { refresh_token } : {});
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
