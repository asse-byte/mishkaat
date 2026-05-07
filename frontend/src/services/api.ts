import axios, { AxiosError } from 'axios';
import type { AuthResponse, User, DashboardStats, Student, Teacher, Halaqah, Center, Recitation, Attendance, Fee } from '@/types';

const api = axios.create({
  baseURL: '/api',
  headers: {
    'Content-Type': 'application/json',
  },
});

// Request interceptor to add auth token
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Response interceptor for error handling
api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('access_token');
      localStorage.removeItem('user');
      window.location.href = '/login';
    }
    return Promise.reject(error);
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
  
  logout: async (): Promise<void> => {
    await api.post('/auth/logout');
  },
  
  getMe: async (): Promise<User> => {
    const response = await api.get<User>('/auth/me');
    return response.data;
  },
};

// Dashboard endpoints
export const dashboardApi = {
  getStats: async (role: string): Promise<DashboardStats> => {
    const response = await api.get<DashboardStats>(`/dashboard/${role}`);
    return response.data;
  },
};

// Centers endpoints
export const centersApi = {
  getAll: async (): Promise<Center[]> => {
    const response = await api.get<Center[]>('/centers');
    return response.data;
  },
  
  getById: async (id: string): Promise<Center> => {
    const response = await api.get<Center>(`/centers/${id}`);
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
  
  getById: async (id: string): Promise<Teacher> => {
    const response = await api.get<Teacher>(`/teachers/${id}`);
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
  
  getById: async (id: string): Promise<Halaqah> => {
    const response = await api.get<Halaqah>(`/halaqat/${id}`);
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
  
  update: async (id: string, data: Partial<Recitation>): Promise<Recitation> => {
    const response = await api.put<Recitation>(`/recitations/${id}`, data);
    return response.data;
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
  
  update: async (id: string, data: Partial<Attendance>): Promise<Attendance> => {
    const response = await api.put<Attendance>(`/attendance/${id}`, data);
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
  
  update: async (id: string, data: Partial<Fee>): Promise<Fee> => {
    const response = await api.put<Fee>(`/fees/${id}`, data);
    return response.data;
  },
  
  markAsPaid: async (id: string): Promise<Fee> => {
    const response = await api.post<Fee>(`/fees/${id}/pay`);
    return response.data;
  },
};

export default api;
