import { useState } from 'react';
import { useAuth } from '@/contexts/AuthContext';
import { LoadingSpinner } from '@/components/ui/loading';
import { User, Key, Save, AlertCircle, CheckCircle2, Shield } from 'lucide-react';
import api from '@/services/api';

export default function ProfilePage() {
  const { user, logout } = useAuth();
  const [activeTab, setActiveTab] = useState<'info' | 'security'>('info');
  const [isLoading, setIsLoading] = useState(false);
  const [message, setMessage] = useState<{ type: 'success' | 'error', text: string } | null>(null);

  // Form states
  const [profileData, setProfileData] = useState({
    name: user?.name || '',
    email: user?.email || '',
    phone: user?.phone || '',
  });

  const [passwordData, setPasswordData] = useState({
    currentPassword: '',
    newPassword: '',
    confirmPassword: '',
  });

  const handleProfileUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setMessage(null);
    try {
      await api.put('/auth/profile', profileData);
      setMessage({ type: 'success', text: 'تم تحديث البيانات بنجاح. قد تحتاج لتسجيل الدخول مرة أخرى لتحديث كامل.' });
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'حدث خطأ أثناء التحديث' });
    } finally {
      setIsLoading(false);
    }
  };

  const handlePasswordUpdate = async (e: React.FormEvent) => {
    e.preventDefault();
    if (passwordData.newPassword !== passwordData.confirmPassword) {
      setMessage({ type: 'error', text: 'كلمة المرور الجديدة غير متطابقة' });
      return;
    }
    setIsLoading(true);
    setMessage(null);
    try {
      await api.post('/auth/change-password', {
        current_password: passwordData.currentPassword,
        new_password: passwordData.newPassword,
      });
      setMessage({ type: 'success', text: 'تم تغيير كلمة المرور بنجاح! الرجاء تسجيل الدخول بكلمة المرور الجديدة.' });
      setPasswordData({ currentPassword: '', newPassword: '', confirmPassword: '' });
      setTimeout(() => logout(), 3000);
    } catch (error: any) {
      setMessage({ type: 'error', text: error.response?.data?.detail || 'حدث خطأ أثناء التحديث' });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="space-y-6 animate-fade-in pb-10">
      <div className="flex justify-between items-center bg-white p-6 rounded-[var(--radius)] shadow-sm border border-[hsl(var(--border))]">
        <div className="flex items-center gap-5">
          <div className="w-16 h-16 rounded-[var(--radius)] bg-emerald-100 flex items-center justify-center text-emerald-700 shadow-inner">
            <User className="w-8 h-8" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[hsl(var(--foreground))]">{user?.name}</h1>
            <p className="text-[hsl(var(--muted-foreground))] flex items-center gap-2 mt-1">
              <Shield className="w-4 h-4" />
              {user?.role === 'admin' ? 'مدير عام' : 
               user?.role === 'center_manager' ? 'مدير مركز' : 
               user?.role === 'teacher' ? 'معلم' : 
               user?.role === 'student' ? 'طالب' : 'ولي أمر'}
            </p>
          </div>
        </div>
      </div>

      {message && (
        <div className={`p-4 rounded-xl flex items-center gap-3 ${
          message.type === 'success' ? 'bg-green-50 text-green-700 border border-green-200' : 'bg-red-50 text-red-700 border border-red-200'
        }`}>
          {message.type === 'success' ? <CheckCircle2 className="w-5 h-5 flex-shrink-0" /> : <AlertCircle className="w-5 h-5 flex-shrink-0" />}
          <p className="font-medium">{message.text}</p>
        </div>
      )}

      <div className="grid grid-cols-1 md:grid-cols-4 gap-6">
        <div className="md:col-span-1 space-y-2">
          <button
            onClick={() => setActiveTab('info')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'info' 
                ? 'bg-[hsl(var(--primary))] text-white shadow-md' 
                : 'hover:bg-[hsl(var(--muted))] text-[hsl(var(--foreground))]'
            }`}
          >
            <User className="w-5 h-5" />
            <span className="font-semibold text-sm">البيانات الشخصية</span>
          </button>
          <button
            onClick={() => setActiveTab('security')}
            className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all ${
              activeTab === 'security' 
                ? 'bg-[hsl(var(--primary))] text-white shadow-md' 
                : 'hover:bg-purple-50 text-[hsl(var(--foreground))]'
            }`}
          >
            <Key className="w-5 h-5" />
            <span className="font-semibold text-sm">الأمان وكلمة المرور</span>
          </button>
        </div>

        <div className="md:col-span-3 bg-white p-6 md:p-8 rounded-[var(--radius)] shadow-sm border border-[hsl(var(--border))]">
          {activeTab === 'info' ? (
            <form onSubmit={handleProfileUpdate} className="space-y-6">
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                <User className="w-6 h-6 text-[hsl(var(--primary))]" />
                البيانات الأساسية
              </h2>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div>
                  <label className="block text-sm font-semibold mb-2">الاسم الكامل</label>
                  <input
                    type="text"
                    value={profileData.name}
                    onChange={e => setProfileData({...profileData, name: e.target.value})}
                    className="form-input w-full"
                    required
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-2">اسم المستخدم (للدخول)</label>
                  <input
                    type="text"
                    value={user?.username}
                    className="form-input w-full bg-gray-50 cursor-not-allowed"
                    disabled
                  />
                  <p className="text-xs text-gray-400 mt-1">لا يمكن تغيير اسم المستخدم</p>
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-2">البريد الإلكتروني</label>
                  <input
                    type="email"
                    value={profileData.email}
                    onChange={e => setProfileData({...profileData, email: e.target.value})}
                    className="form-input w-full"
                    dir="ltr"
                    placeholder="example@mail.com"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-2">رقم الهاتف</label>
                  <input
                    type="text"
                    value={profileData.phone}
                    onChange={e => setProfileData({...profileData, phone: e.target.value})}
                    className="form-input w-full"
                    dir="ltr"
                  />
                </div>
              </div>

              <div className="pt-4 flex justify-end">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="gradient-primary flex items-center gap-2 px-6 py-2.5 rounded-xl text-white font-bold disabled:opacity-50 transition-all hover:opacity-90 shadow-md"
                >
                  {isLoading ? <LoadingSpinner size="sm" /> : <Save className="w-5 h-5" />}
                  حفظ التعديلات
                </button>
              </div>
            </form>
          ) : (
            <form onSubmit={handlePasswordUpdate} className="space-y-6">
              <h2 className="text-xl font-bold mb-6 flex items-center gap-2">
                <Key className="w-6 h-6 text-[hsl(var(--primary))]" />
                تغيير كلمة المرور
              </h2>
              
              <div className="space-y-5 max-w-md">
                <div>
                  <label className="block text-sm font-semibold mb-2">كلمة المرور الحالية</label>
                  <input
                    type="password"
                    value={passwordData.currentPassword}
                    onChange={e => setPasswordData({...passwordData, currentPassword: e.target.value})}
                    className="form-input w-full"
                    required
                    dir="ltr"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-2">كلمة المرور الجديدة</label>
                  <input
                    type="password"
                    value={passwordData.newPassword}
                    onChange={e => setPasswordData({...passwordData, newPassword: e.target.value})}
                    className="form-input w-full"
                    required
                    minLength={8}
                    dir="ltr"
                  />
                </div>
                <div>
                  <label className="block text-sm font-semibold mb-2">تأكيد كلمة المرور الجديدة</label>
                  <input
                    type="password"
                    value={passwordData.confirmPassword}
                    onChange={e => setPasswordData({...passwordData, confirmPassword: e.target.value})}
                    className="form-input w-full"
                    required
                    minLength={8}
                    dir="ltr"
                  />
                </div>
              </div>

              <div className="pt-4">
                <button
                  type="submit"
                  disabled={isLoading}
                  className="bg-gray-900 hover:bg-gray-800 text-white flex items-center gap-2 px-6 py-2.5 rounded-xl transition-all disabled:opacity-50 font-bold"
                >
                  {isLoading ? <LoadingSpinner size="sm" /> : <Shield className="w-5 h-5" />}
                  تحديث كلمة المرور
                </button>
              </div>
            </form>
          )}
        </div>
      </div>
    </div>
  );
}
