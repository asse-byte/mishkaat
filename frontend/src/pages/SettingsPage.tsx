import { useState } from 'react';
import { Settings, Globe, Moon, Bell, Shield, Save, CheckCircle2 } from 'lucide-react';

export default function SettingsPage() {
  const [activeTab, setActiveTab] = useState<'general' | 'notifications' | 'privacy'>('general');
  const [isSaved, setIsSaved] = useState(false);

  const [settings, setSettings] = useState({
    theme: 'light',
    emailNotifications: true,
    smsNotifications: false,
    showAttendanceToParents: true,
    twoFactorAuth: false,
  });

  const handleSave = () => {
    // محاكاة حفظ
    setIsSaved(true);
    setTimeout(() => setIsSaved(false), 3000);
  };

  return (
    <div className="space-y-6 animate-fade-in pb-10">
      <div className="flex justify-between items-center bg-white p-6 rounded-[var(--radius)] shadow-sm border border-[hsl(var(--border))]">
        <div className="flex items-center gap-4">
          <div className="w-14 h-14 rounded-[var(--radius)] bg-gray-100 flex items-center justify-center text-gray-700 shadow-inner">
            <Settings className="w-7 h-7" />
          </div>
          <div>
            <h1 className="text-2xl font-bold text-[hsl(var(--foreground))] mb-1">الإعدادات</h1>
            <p className="text-[hsl(var(--muted-foreground))] text-sm">إدارة تفضيلات النظام وإعدادات الحساب</p>
          </div>
        </div>
      </div>

      <div className="flex flex-col md:flex-row gap-6">
        {/* Sidebar Tabs */}
        <div className="w-full md:w-64 space-y-2">
          <button
            onClick={() => setActiveTab('general')}
            className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all font-semibold ${
              activeTab === 'general'
                ? 'bg-[hsl(var(--primary))] text-white shadow-md'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-[hsl(var(--border))]'
            }`}
          >
            <Globe className="w-5 h-5" />
            عام
          </button>
          <button
            onClick={() => setActiveTab('notifications')}
            className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all font-semibold ${
              activeTab === 'notifications'
                ? 'bg-[hsl(var(--primary))] text-white shadow-md'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-[hsl(var(--border))]'
            }`}
          >
            <Bell className="w-5 h-5" />
            التنبيهات
          </button>
          <button
            onClick={() => setActiveTab('privacy')}
            className={`w-full flex items-center gap-3 px-4 py-3.5 rounded-xl transition-all font-semibold ${
              activeTab === 'privacy'
                ? 'bg-[hsl(var(--primary))] text-white shadow-md'
                : 'bg-white text-gray-600 hover:bg-gray-50 border border-[hsl(var(--border))]'
            }`}
          >
            <Shield className="w-5 h-5" />
            الخصوصية والأمان
          </button>
        </div>

        {/* Content Area */}
        <div className="flex-1 bg-white p-6 md:p-8 rounded-[var(--radius)] shadow-sm border border-[hsl(var(--border))]">
          {activeTab === 'general' && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-xl font-bold mb-6 text-gray-800 border-b pb-4">إعدادات عامة</h2>
              
              <div className="space-y-5">
                {/* [قرار المالك 2026-09-06] النظام بالعربية وحدها، ولا نيّة
                    لإضافة لغةٍ أخرى. وكان هنا مُنتقٍ يَعِد بـ«English (قريباً)»
                    — وعدٌ لا يُوفى، ومفتاحٌ يقلب نصفَ الشاشات لو ضُبط. */}
                <div>
                  <label className="block text-sm font-semibold mb-2">المظهر</label>
                  <div className="flex gap-4">
                    <label className={`flex items-center gap-2 p-3 rounded-xl border cursor-pointer transition-all ${
                      settings.theme === 'light' ? 'border-[hsl(var(--primary))] bg-purple-50 text-[hsl(var(--primary))]' : 'hover:bg-gray-50'
                    }`}>
                      <input 
                        type="radio" 
                        name="theme" 
                        value="light" 
                        checked={settings.theme === 'light'}
                        onChange={() => setSettings({...settings, theme: 'light'})}
                        className="hidden"
                      />
                      <Globe className="w-5 h-5" />
                      وضع فاتح
                    </label>
                    <label className={`flex items-center gap-2 p-3 rounded-xl border cursor-not-allowed opacity-50`}>
                      <input disabled type="radio" name="theme" value="dark" className="hidden" />
                      <Moon className="w-5 h-5" />
                      وضع داكن (قريباً)
                    </label>
                  </div>
                </div>
              </div>
            </div>
          )}

          {activeTab === 'notifications' && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-xl font-bold mb-6 text-gray-800 border-b pb-4">إعدادات الإشعارات</h2>
              
              <div className="space-y-4">
                <label className="flex items-center justify-between p-4 border rounded-xl hover:bg-gray-50 cursor-pointer transition-colors">
                  <div>
                    <h4 className="font-bold text-gray-800">إشعارات البريد الإلكتروني</h4>
                    <p className="text-sm text-gray-500 mt-1">تلقي التحديثات والتقارير عبر الإيميل</p>
                  </div>
                  <div className="relative inline-block w-12 mr-2 align-middle select-none transition duration-200 ease-in">
                    <input type="checkbox" className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none cursor-pointer transition-transform" 
                      style={{ right: settings.emailNotifications ? '0' : '1.5rem', borderColor: settings.emailNotifications ? 'hsl(var(--primary))' : '#ddd' }}
                      checked={settings.emailNotifications}
                      onChange={() => setSettings({...settings, emailNotifications: !settings.emailNotifications})}
                    />
                    <div className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer ${settings.emailNotifications ? 'bg-[hsl(var(--primary))]' : 'bg-gray-300'}`}></div>
                  </div>
                </label>

                <label className="flex items-center justify-between p-4 border rounded-xl hover:bg-gray-50 cursor-pointer transition-colors opacity-60">
                  <div>
                    <h4 className="font-bold text-gray-800">إشعارات SMS</h4>
                    <p className="text-sm text-gray-500 mt-1">تلقي تنبيهات الغياب الفورية (يتطلب اشتراك)</p>
                  </div>
                  <div className="relative inline-block w-12 mr-2 align-middle select-none">
                    <input disabled type="checkbox" className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none" style={{ right: '1.5rem', borderColor: '#ddd' }} />
                    <div className="toggle-label block overflow-hidden h-6 rounded-full bg-gray-300"></div>
                  </div>
                </label>
              </div>
            </div>
          )}

          {activeTab === 'privacy' && (
            <div className="space-y-6 animate-fade-in">
              <h2 className="text-xl font-bold mb-6 text-gray-800 border-b pb-4">الخصوصية والأمان</h2>
              
              <div className="space-y-4">
                <label className="flex items-center justify-between p-4 border rounded-xl hover:bg-gray-50 cursor-pointer transition-colors">
                  <div>
                    <h4 className="font-bold text-gray-800">مشاركة الحضور مع أولياء الأمور</h4>
                    <p className="text-sm text-gray-500 mt-1">السماح لولي الأمر بظهور سجل غياب وتأخر الطالب</p>
                  </div>
                  <div className="relative inline-block w-12 mr-2 align-middle select-none transition duration-200 ease-in">
                    <input type="checkbox" className="toggle-checkbox absolute block w-6 h-6 rounded-full bg-white border-4 appearance-none cursor-pointer transition-transform" 
                      style={{ right: settings.showAttendanceToParents ? '0' : '1.5rem', borderColor: settings.showAttendanceToParents ? 'hsl(var(--primary))' : '#ddd' }}
                      checked={settings.showAttendanceToParents}
                      onChange={() => setSettings({...settings, showAttendanceToParents: !settings.showAttendanceToParents})}
                    />
                    <div className={`toggle-label block overflow-hidden h-6 rounded-full cursor-pointer ${settings.showAttendanceToParents ? 'bg-[hsl(var(--primary))]' : 'bg-gray-300'}`}></div>
                  </div>
                </label>

                <label className="flex items-center justify-between p-4 border rounded-xl hover:bg-gray-50 cursor-pointer transition-colors opacity-60">
                  <div>
                    <h4 className="font-bold text-gray-800">المصادقة الثنائية (2FA)</h4>
                    <p className="text-sm text-gray-500 mt-1">إضافة طبقة حماية ثانية عند تسجيل الدخول</p>
                  </div>
                  <div className="relative inline-block w-12 mr-2 align-middle select-none transition duration-200 ease-in">
                    <button className="text-sm font-bold text-purple-600 bg-purple-50 px-3 py-1.5 rounded-lg">تفعيل قريباً</button>
                  </div>
                </label>
              </div>
            </div>
          )}

          <div className="mt-10 pt-6 border-t flex items-center justify-end gap-4">
            {isSaved && (
              <span className="text-green-600 font-bold flex items-center gap-1 animate-fade-in">
                <CheckCircle2 className="w-5 h-5" />
                تم الحفظ
              </span>
            )}
            <button 
              onClick={handleSave}
              className="btn-primary flex items-center gap-2 px-8 py-2.5 rounded-xl font-bold"
            >
              <Save className="w-5 h-5" />
              حفظ التغييرات
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
