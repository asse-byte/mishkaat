import React, { useState } from 'react';
import { Link } from 'react-router-dom';
import { Heart, ArrowLeft, Share2, Gift } from 'lucide-react';

// تظاهر بوجود بيانات للحلقات والطلاب المحتاجين للكفالة
const MOCK_OPPORTUNITIES = [
  {
    id: 1,
    type: 'student',
    title: 'كفالة طالب حافظ',
    description: 'يتميم يحفظ القرآن ويحتاج إلى كفالة لتغطية رسوم المركز والمواصلات.',
    amount: 150,
    currency: 'ريال/شهرياً',
    progress: 70,
    tags: ['طالب يتيم', 'مرحلة متقدمة']
  },
  {
    id: 2,
    type: 'halaqa',
    title: 'رعاية حلقة تاج الوقار',
    description: 'حلقة تضم 15 طالباً يحتاجون لمكافآت تشجيعية وتغطية أجر المعلم.',
    amount: 800,
    currency: 'ريال/شهرياً',
    progress: 25,
    tags: ['حلقة كاملة', 'تحفيز مكثف']
  },
  {
    id: 3,
    type: 'project',
    title: 'تطوير منصة المشكاة',
    description: 'دعم تقني كصدقة جارية لاستضافة المنصة وتقديمها مجاناً للمراكز في الدول الفقيرة.',
    amount: 5000,
    currency: 'ريال/مرة واحدة',
    progress: 50,
    tags: ['وقف تقني', 'صدقة جارية']
  }
];

const Sponsorships = () => {
  const [filter, setFilter] = useState('all');

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800" dir="rtl">
      {/* Navbar */}
      <header className="bg-white border-b border-slate-200 sticky top-0 z-50 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-16">
            <div className="flex items-center gap-3">
              <Link to="/" className="w-10 h-10 bg-emerald-100 rounded-lg flex items-center justify-center hover:bg-emerald-200 transition-colors">
                <ArrowLeft className="w-5 h-5 text-emerald-700" />
              </Link>
              <h1 className="text-xl font-bold text-slate-800">بوابة كفالة الحفّاظ</h1>
            </div>
          </div>
        </div>
      </header>

      {/* Hero */}
      <div className="bg-emerald-900 text-white py-16 relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/arabesque.png')] opacity-10" />
        <div className="max-w-7xl mx-auto px-4 relative z-10 text-center">
          <Heart className="w-12 h-12 text-rose-400 fill-rose-400 mx-auto mb-6" />
          <h2 className="text-3xl md:text-5xl font-extrabold mb-4">كُن شريكاً في صناعة جيل القرآن</h2>
          <p className="text-emerald-100 text-lg max-w-2xl mx-auto">
            ساهم في دعم حلقات التحفيظ، كفالة الطلاب الأيتام، أو الوقف التقني لتيسير استمرار المراكز القرآنية وتطورها. دلالتك على الخير كفاعله.
          </p>
        </div>
      </div>

      {/* Content */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12">
        {/* Filters */}
        <div className="flex flex-wrap gap-4 mb-8 justify-center">
          <button 
            onClick={() => setFilter('all')}
            className={`px-6 py-2 rounded-full font-medium transition-colors ${filter === 'all' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600 border border-slate-200 hover:bg-emerald-50'}`}
          >
            الكل
          </button>
          <button 
            onClick={() => setFilter('student')}
            className={`px-6 py-2 rounded-full font-medium transition-colors ${filter === 'student' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600 border border-slate-200 hover:bg-emerald-50'}`}
          >
            كفالة طالب
          </button>
          <button 
            onClick={() => setFilter('halaqa')}
            className={`px-6 py-2 rounded-full font-medium transition-colors ${filter === 'halaqa' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600 border border-slate-200 hover:bg-emerald-50'}`}
          >
            دعم حلقة
          </button>
          <button 
            onClick={() => setFilter('project')}
            className={`px-6 py-2 rounded-full font-medium transition-colors ${filter === 'project' ? 'bg-emerald-600 text-white' : 'bg-white text-slate-600 border border-slate-200 hover:bg-emerald-50'}`}
          >
            الوقف التقني
          </button>
        </div>

        {/* Opportunities List */}
        <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
          {MOCK_OPPORTUNITIES.filter(opt => filter === 'all' || opt.type === filter).map(opt => (
            <div key={opt.id} className="bg-white rounded-2xl border border-slate-200 overflow-hidden hover:shadow-xl hover:-translate-y-1 transition-all flex flex-col">
              <div className="p-6 flex-1">
                <div className="flex gap-2 mb-4">
                  {opt.tags.map(tag => (
                    <span key={tag} className="px-3 py-1 bg-amber-50 text-amber-700 text-xs font-bold rounded-full">
                      {tag}
                    </span>
                  ))}
                </div>
                <h3 className="text-xl font-bold text-slate-800 mb-2">{opt.title}</h3>
                <p className="text-slate-500 text-sm mb-6 leading-relaxed">
                  {opt.description}
                </p>
                
                {/* Progress */}
                <div className="mb-2 flex justify-between text-sm">
                  <span className="font-bold text-emerald-600">{opt.progress}% مكتمل</span>
                  <span className="text-slate-500">الهدف: {opt.amount} {opt.currency}</span>
                </div>
                <div className="w-full bg-slate-100 rounded-full h-2.5 mb-6">
                  <div className="bg-emerald-500 h-2.5 rounded-full" style={{ width: `${opt.progress}%` }}></div>
                </div>
              </div>
              
              <div className="p-4 border-t border-slate-100 bg-slate-50 flex items-center justify-between">
                <button className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white px-4 py-2.5 rounded-lg font-bold transition-colors flex items-center justify-center gap-2">
                  <Gift className="w-4 h-4" />
                  <span>اكفل الآن</span>
                </button>
                <button aria-label="مشاركة" className="w-12 h-12 flex items-center justify-center rounded-lg text-slate-400 hover:text-emerald-600 hover:bg-emerald-50 transition-colors mr-2">
                  <Share2 className="w-5 h-5" />
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};

export default Sponsorships;
