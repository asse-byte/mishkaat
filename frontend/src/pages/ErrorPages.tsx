import { Link } from 'react-router-dom';
import { Home, AlertTriangle } from 'lucide-react';

export function NotFoundPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center max-w-md w-full animate-fade-in pb-10">
        <div className="mb-6 relative">
          <div className="text-[150px] font-black text-purple-100 leading-none select-none">404</div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-24 h-24 bg-[hsl(var(--primary))] rounded-full flex items-center justify-center shadow-xl animate-float">
              <AlertTriangle className="w-12 h-12 text-white" />
            </div>
          </div>
        </div>
        
        <h1 className="text-3xl font-black text-gray-900 mb-3">الصفحة غير موجودة</h1>
        <p className="text-gray-500 mb-8 leading-relaxed">
          عذراً، لم نتمكن من العثور على الصفحة التي تبحث عنها. 
          قد يكون الرابط غير صحيح أو تم نقل الصفحة.
        </p>

        <Link 
          to="/dashboard"
          className="btn-primary inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-full font-bold shadow-lg shadow-purple-500/30 hover:shadow-purple-500/50 transition-all hover:-translate-y-1"
        >
          <Home className="w-5 h-5" />
          العودة للرئيسية
        </Link>
      </div>
    </div>
  );
}

export function ForbiddenPage() {
  return (
    <div className="min-h-screen bg-gray-50 flex items-center justify-center p-4">
      <div className="text-center max-w-md w-full animate-fade-in pb-10">
        <div className="mb-6 relative">
          <div className="text-[150px] font-black text-red-100 leading-none select-none">403</div>
          <div className="absolute inset-0 flex items-center justify-center">
            <div className="w-24 h-24 bg-red-600 rounded-full flex items-center justify-center shadow-xl animate-float">
              <AlertTriangle className="w-12 h-12 text-white" />
            </div>
          </div>
        </div>
        
        <h1 className="text-3xl font-black text-gray-900 mb-3">غير مصرح لك</h1>
        <p className="text-gray-500 mb-8 leading-relaxed">
          عذراً، لا تملك الصلاحيات الكافية للوصول إلى هذه الصفحة.
          يرجى التواصل مع الإدارة إذا كنت تعتقد أن هذا خطأ.
        </p>

        <Link 
          to="/dashboard"
          className="bg-gray-900 hover:bg-black text-white inline-flex items-center justify-center gap-2 px-8 py-3.5 rounded-full font-bold shadow-lg transition-all hover:-translate-y-1"
        >
          <Home className="w-5 h-5" />
          العودة للرئيسية
        </Link>
      </div>
    </div>
  );
}
