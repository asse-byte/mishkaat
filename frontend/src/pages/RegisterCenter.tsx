import React, { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { BookOpen, User, Building, MapPin, Phone, Mail, ArrowRight, CheckCircle2 } from 'lucide-react';
import axios, { AxiosError } from 'axios';

// Get API URL from env or use relative path (assuming proxy is setup in vite.config.ts)
const API_URL = import.meta.env.VITE_API_URL || '';

const RegisterCenter = () => {
  const navigate = useNavigate();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  const [formData, setFormData] = useState({
    centerName: '',
    centerAddress: '',
    managerName: '',
    managerPhone: '',
    managerEmail: '',
    managerUsername: '',
    managerPassword: '',
  });

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setSuccess(false);

    try {
      const payload = {
        name: formData.centerName,
        address: formData.centerAddress,
        phone: formData.managerPhone,
        manager_name: formData.managerName,
        manager_username: formData.managerUsername,
        manager_password: formData.managerPassword,
        manager_email: formData.managerEmail.trim(),
        is_active: true
      };

      // Ensure manager username is provided
      if (!payload.manager_username || !payload.manager_password) {
        throw new Error('يرجى إدخال اسم مستخدم وكلمة مرور للمدير');
      }

      await axios.post(`${API_URL}/api/public/register-center`, payload);
      setSuccess(true);
      setTimeout(() => {
        navigate('/login');
      }, 3000);
      
    } catch (err) {
      if (err instanceof AxiosError) {
        setError(err.response?.data?.detail || err.message || 'حدث خطأ أثناء التسجيل');
      } else {
        setError('حدث خطأ أثناء التسجيل');
      }
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-slate-50 flex" dir="rtl">
      {/* Right Form Section */}
      <div className="w-full lg:w-1/2 flex flex-col justify-center px-4 sm:px-6 lg:px-12 py-12">
        <div className="mb-8">
          <Link to="/" className="inline-flex items-center gap-2 text-[hsl(var(--lamp-strong))] hover:text-[hsl(var(--lamp-strong))] font-medium mb-6 transition-colors">
            <ArrowRight className="w-4 h-4" />
            <span>العودة للرئيسية</span>
          </Link>
          <div className="flex items-center gap-3 mb-6">
            <div className="w-12 h-12 bg-[hsl(var(--niche))] rounded-xl flex items-center justify-center shadow-lg shadow-emerald-200">
              <BookOpen className="w-7 h-7 text-white" />
            </div>
            <h1 className="text-3xl font-bold text-slate-800">إنشاء حساب لمركز جديد</h1>
          </div>
          <p className="text-slate-600">انضم إلينا الآن لإدارة حلقتك بكل سهولة ويسر. الخدمة مجانية بالكامل للمراكز الخيرية.</p>
        </div>

        {error && (
          <div className="bg-red-50 text-red-700 p-4 rounded-xl border border-red-200 mb-6">
            {error}
          </div>
        )}

        {success ? (
          <div className="bg-emerald-50 border border-emerald-200 rounded-[var(--radius)] p-8 text-center shadow-sm">
            <div className="w-16 h-16 bg-emerald-100 text-[hsl(var(--lamp-strong))] rounded-full flex items-center justify-center mx-auto mb-4">
              <CheckCircle2 className="w-8 h-8" />
            </div>
            <h2 className="text-2xl font-bold text-slate-800 mb-2">تم التسجيل بنجاح!</h2>
            <p className="text-slate-600 mb-6">جاري توجيهك لصفحة تسجيل الدخول...</p>
            <Link to="/login" className="px-6 py-2 bg-[hsl(var(--niche))] text-white rounded-lg hover:bg-[hsl(var(--niche))] transition-colors inline-block">
              الانتقال لتسجيل الدخول
            </Link>
          </div>
        ) : (
          <form className="space-y-6" onSubmit={handleSubmit}>
            {/* Center Data */}
            <div className="space-y-4 bg-white p-6 rounded-[var(--radius)] border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                <Building className="w-5 h-5 text-[hsl(var(--lamp-strong))]" />
                <span>بيانات المركز</span>
              </h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">اسم المركز أو المدرسة *</label>
                  <input type="text" name="centerName" value={formData.centerName} onChange={handleChange} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all" placeholder="مثال: مدرسة الإمام عاصم" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">المدينة / الحي *</label>
                  <div className="relative">
                     <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <MapPin className="h-4 w-4 text-[hsl(var(--ink-3))]" />
                     </div>
                     <input type="text" name="centerAddress" value={formData.centerAddress} onChange={handleChange} className="w-full pr-10 pl-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all" placeholder="مثال: الرياض، العقيق" required />
                  </div>
                </div>
              </div>
            </div>

            {/* Manager Data */}
            <div className="space-y-4 bg-white p-6 rounded-[var(--radius)] border border-slate-200 shadow-sm">
              <h3 className="font-bold text-slate-800 mb-4 flex items-center gap-2">
                <User className="w-5 h-5 text-[hsl(var(--lamp-strong))]" />
                <span>بيانات ومعلومات الدخول لمدير المركز</span>
              </h3>
              
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">الاسم الكامل *</label>
                  <input type="text" name="managerName" value={formData.managerName} onChange={handleChange} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all" placeholder="الاسم الرباعي" required />
                </div>
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">اسم الدخول (Username) *</label>
                  <input type="text" dir="ltr" name="managerUsername" value={formData.managerUsername} onChange={handleChange} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all text-right" placeholder="manager123" required />
                </div>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-slate-700 mb-1">رقم الجوال *</label>
                  <div className="relative">
                     <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                        <Phone className="h-4 w-4 text-[hsl(var(--ink-3))]" />
                     </div>
                     <input type="tel" dir="ltr" name="managerPhone" value={formData.managerPhone} onChange={handleChange} className="w-full pr-10 pl-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all text-right" placeholder="05XXXXXXXX" required />
                  </div>
                </div>
                <div>
                  {/* [إصلاح 2026-09-06] كان الحدّ هنا 6 والخادم يشترط 8 مع رقم
                      وحرف، فتُقبل كلمةٌ في المتصفّح ثم يردّها الخادم 400 بلا أن
                      يعرف المستخدم القاعدة أصلاً. القاعدة الآن مكتوبة تحت الحقل. */}
                  <label className="block text-sm font-medium text-slate-700 mb-1">كلمة المرور *</label>
                  <input type="password" dir="ltr" name="managerPassword" value={formData.managerPassword} onChange={handleChange} className="w-full px-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all text-right" placeholder="••••••••" required minLength={8} />
                  <p className="text-xs text-slate-500 mt-1">ثمانية أحرف على الأقل، وفيها رقم وحرف.</p>
                </div>
              </div>

              {/* [إصلاح 2026-09-06] هذا الحقل لم يكن موجوداً إطلاقاً.
                  managerEmail كان في الحالة ولا يربطه شيء بالنموذج، فيُرسَل
                  undefined دائماً، والخادم يشترطه ويردّ 400 «البريد الإلكتروني
                  مطلوب للتحقق». أي أن تسجيل مركز جديد كان متعذّراً بالكامل، لا
                  في حالة طرفية — لا سبيل لأحد أن ينجح فيه. */}
              <div>
                <label className="block text-sm font-medium text-slate-700 mb-1">البريد الإلكتروني *</label>
                <div className="relative">
                  <div className="absolute inset-y-0 right-0 pr-3 flex items-center pointer-events-none">
                    <Mail className="h-4 w-4 text-[hsl(var(--ink-3))]" />
                  </div>
                  <input
                    type="email" dir="ltr" name="managerEmail"
                    value={formData.managerEmail} onChange={handleChange}
                    className="w-full pr-10 pl-4 py-2 border border-slate-300 rounded-lg focus:ring-2 focus:ring-emerald-500 focus:border-emerald-500 outline-none transition-all text-right"
                    placeholder="manager@example.com" required
                  />
                </div>
                <p className="text-xs text-slate-500 mt-1">يُستعمل للتواصل معك بشأن اعتماد المركز.</p>
              </div>
            </div>

            <button type="submit" disabled={loading} className={`w-full bg-[hsl(var(--niche))] hover:bg-[hsl(var(--niche))] text-white font-bold py-4 rounded-xl shadow-lg shadow-emerald-200 transition-all ${loading ? 'opacity-70 cursor-not-allowed' : 'hover:-translate-y-0.5'}`}>
              {loading ? 'جاري إنشاء المركز...' : 'تأكيد وتسجيل المركز'}
            </button>
          </form>
        )}
        
        <p className="mt-8 text-center text-slate-500 text-sm">
          بالتسجيل فإنك توافق على <a href="#" className="text-[hsl(var(--lamp-strong))] hover:underline">الشروط والأحكام</a> الخاصة بالمشكاة.
          <br /><br />
          لديك حساب بالفعل؟ <Link to="/login" className="text-[hsl(var(--lamp-strong))] font-bold hover:underline">تسجيل الدخول</Link>
        </p>
      </div>

      {/* Left Info Section */}
      <div className="hidden lg:flex w-1/2 bg-[hsl(var(--niche))] text-white p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/arabesque.png')] opacity-10" />
        <div className="absolute top-0 left-0 w-96 h-96 bg-[hsl(var(--niche))] rounded-full blur-[100px] opacity-40 -translate-x-1/2 -translate-y-1/2" />
        
        <div className="relative z-10 max-w-lg">
          <h2 className="text-4xl font-bold mb-6 leading-tight">انضم إلى شبكة من المراكز التي تخدم كتاب الله بدقة واحترافية.</h2>
          <p className="text-emerald-100 text-lg mb-12">
            منصة المشكاة أُنشِئت لتخفيف العبء الإداري، لتتفرغ أنت ومعلموك لمتابعة تلاوات وحفظ الطلاب بكل تركيز.
          </p>
          
          <ul className="space-y-6">
            <li className="flex items-start gap-4">
              <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0 mt-1" />
              <div>
                <h4 className="font-bold text-lg mb-1">لوحة تحكم شاملة</h4>
                <p className="text-emerald-100/80 text-sm">إدارة الحضور، الانصراف، ومستويات الطلاب من مكان واحد.</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0 mt-1" />
              <div>
                <h4 className="font-bold text-lg mb-1">موثوقية وسرية</h4>
                <p className="text-emerald-100/80 text-sm">بياناتك محفوظة ومشفرة بأعلى المعايير، وصلاحيات محددة لكل دور.</p>
              </div>
            </li>
            <li className="flex items-start gap-4">
              <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0 mt-1" />
              <div>
                <h4 className="font-bold text-lg mb-1">تطبيق الجوال (PWA)</h4>
                <p className="text-emerald-100/80 text-sm">يمكن استخدام النظام كتطبيق مستقل على أجهزة المعلمين دون إنترنت (Offline Mode).</p>
              </div>
            </li>
          </ul>
        </div>
        
        <div className="relative z-10 opacity-60">
          <p className="text-sm">مشروع وقفي بالكامل - المشكاة 2026</p>
        </div>
      </div>
    </div>
  );
};

export default RegisterCenter;
