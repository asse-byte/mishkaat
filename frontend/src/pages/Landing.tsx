/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { useAuth } from '@/contexts/AuthContext';
import { 
  BookOpen, Users, Star, Heart, Shield, ArrowLeft, 
  CheckCircle2, ChevronDown, Award, Trophy, Building2, 
  MapPin, TrendingUp
} from 'lucide-react';
import MishkaatMark from '@/components/ui/MishkaatMark';

const Landing = () => {
  const { isAuthenticated } = useAuth();
  const [bestCenters, setBestCenters] = useState<any[]>([]);
  const [loadingCenters, setLoadingCenters] = useState(true);

  useEffect(() => {
    const apiUrl = import.meta.env.VITE_API_URL || '';
    fetch(`${apiUrl}/api/public/best-centers`)
      .then(res => res.json())
      .then(data => {
        if (Array.isArray(data)) {
          setBestCenters(data);
        }
      })
      .catch(() => {})
      .finally(() => setLoadingCenters(false));
  }, []);

  return (
    <div className="min-h-screen bg-slate-50 font-sans text-slate-800" dir="rtl">
      {/* Navbar */}
      <header className="sticky top-0 z-50 bg-white/80 backdrop-blur-md border-b border-emerald-100 shadow-sm">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="flex justify-between items-center h-20">
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 bg-gradient-to-br from-[hsl(var(--niche))] to-[hsl(var(--niche-2))] rounded-xl flex items-center justify-center shadow-lg shadow-emerald-200">
                <MishkaatMark className="w-7 h-7 text-[hsl(var(--lamp))]" title="المشكاة" />
              </div>
              <div>
                <h1 className="text-2xl font-bold bg-clip-text text-transparent bg-gradient-to-l from-[hsl(var(--niche))] to-[hsl(var(--niche-2))]">المشكاة</h1>
                <p className="text-xs text-[hsl(var(--lamp-strong))] font-medium hidden sm:block">لإدارة دور القرآن الكريم</p>
              </div>
            </div>
            <nav className="hidden md:flex gap-8 font-medium text-slate-600">
              <a href="#best-centers" className="hover:text-[hsl(var(--lamp-strong))] transition-colors">أفضل المراكز</a>
              <a href="#features" className="hover:text-[hsl(var(--lamp-strong))] transition-colors">المميزات</a>
              <a href="#about" className="hover:text-[hsl(var(--lamp-strong))] transition-colors">عن النظام</a>
              <a href="#impact" className="hover:text-[hsl(var(--lamp-strong))] transition-colors">الأثر الخيري</a>
            </nav>
            <div className="flex items-center gap-4">
              {isAuthenticated ? (
                <Link to="/dashboard" className="px-6 py-2.5 bg-[hsl(var(--niche))] text-white font-medium rounded-lg hover:bg-[hsl(var(--niche))] transition-all shadow-md hover:shadow-lg shadow-emerald-200 flex items-center gap-2">
                  <span>لوحة التحكم</span>
                  <ArrowLeft className="w-4 h-4" />
                </Link>
              ) : (
                <Link to="/login" className="px-6 py-2.5 bg-[hsl(var(--niche))] text-white font-medium rounded-lg hover:bg-[hsl(var(--niche))] transition-all shadow-md hover:shadow-lg shadow-emerald-200 flex items-center gap-2">
                  <span>تسجيل الدخول</span>
                  <ArrowLeft className="w-4 h-4" />
                </Link>
              )}
            </div>
          </div>
        </div>
      </header>

      {/* Hero Section */}
      <section className="relative overflow-hidden pt-20 pb-32">
        {/* Background Patterns */}
        <div className="absolute inset-0 bg-emerald-50/50 -z-10" />
        <div className="absolute top-0 right-0 -translate-y-12 translate-x-1/3 w-[800px] h-[800px] bg-emerald-100 rounded-full blur-3xl opacity-50 -z-10" />
        <div className="absolute bottom-0 left-0 translate-y-1/3 -translate-x-1/3 w-[600px] h-[600px] bg-amber-100 rounded-full blur-3xl opacity-50 -z-10" />

        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 text-center relative z-10">
          <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-emerald-100 text-[hsl(var(--lamp-strong))] font-medium text-sm mb-8 animate-fade-in-up">
            <Star className="w-4 h-4" />
            <span>مشروع خيري وقفي لخدمة كتاب الله</span>
          </div>
          
          <h1 className="text-5xl md:text-7xl font-extrabold text-slate-800 mb-8 leading-tight tracking-tight">
            المنصة المتكاملة لإدارة <br />
            <span className="text-transparent bg-clip-text bg-gradient-to-l from-[hsl(var(--niche))] to-[hsl(var(--niche-2))]">
              مدارس تحفيظ القرآن الكريم
            </span>
          </h1>
          
          <p className="text-xl text-slate-600 mb-12 max-w-3xl mx-auto leading-relaxed">
            "المشكاة" هو نظام سحابي متطور يهدف إلى تيسير الإدارة وتسهيل متابعة الحفظ والمراجعة للمراكز القرآنية، في بيئة رقمية آمنة وعصرية تلبي احتياجات المعلمين والأهالي.
          </p>
          
          <div className="flex flex-col sm:flex-row gap-4 justify-center items-center">
            <Link to="/register" className="w-full sm:w-auto px-8 py-4 bg-[hsl(var(--niche))] text-white font-bold rounded-xl hover:bg-[hsl(var(--niche))] transition-all shadow-xl shadow-emerald-200 flex items-center justify-center gap-2 text-lg hover:-translate-y-1">
              <span>سجل مركزك مجاناً</span>
              <BookOpen className="w-5 h-5" />
            </Link>
            <a href="#best-centers" className="w-full sm:w-auto px-8 py-4 bg-white text-slate-700 font-bold rounded-xl border-2 border-slate-200 hover:border-emerald-200 hover:bg-emerald-50 transition-all flex items-center justify-center gap-2 text-lg hover:-translate-y-1">
              <span>استكشف أفضل المراكز</span>
              <ChevronDown className="w-5 h-5" />
            </a>
          </div>
        </div>

        {/* Dashboard Mockup (Abstracted) */}
        <div className="mt-20 max-w-5xl mx-auto px-4 relative">
          <div className="rounded-[var(--radius)] border border-slate-200/60 bg-white/60 p-2 shadow-2xl backdrop-blur-xl">
            <div className="rounded-xl border border-slate-100 bg-white p-4 shadow-inner">
               <div className="flex gap-2 mb-4 px-2">
                 <div className="w-3 h-3 rounded-full bg-red-400"></div>
                 <div className="w-3 h-3 rounded-full bg-amber-400"></div>
                 <div className="w-3 h-3 rounded-full bg-emerald-400"></div>
               </div>
               <div className="h-[400px] bg-slate-50 rounded-lg flex flex-col md:flex-row gap-4 p-4">
                 <div className="w-full md:w-1/4 bg-white rounded-md shadow-sm border border-slate-100 p-4 space-y-4">
                   <div className="h-8 bg-slate-100 rounded w-full"></div>
                   <div className="h-8 bg-slate-100 rounded w-3/4"></div>
                   <div className="h-8 bg-emerald-50 rounded border border-emerald-100 w-5/6"></div>
                   <div className="h-8 bg-slate-100 rounded w-full"></div>
                 </div>
                 <div className="flex-1 flex flex-col gap-4">
                     <div className="flex gap-4">
                       <div className="h-24 bg-gradient-to-br from-[hsl(var(--niche))] to-[hsl(var(--niche-2))] rounded-xl flex-1 p-4 flex flex-col justify-between">
                          <div className="h-4 bg-white/30 rounded w-1/3"></div>
                          <div className="h-8 bg-white/40 rounded w-1/2"></div>
                       </div>
                       <div className="h-24 bg-white rounded-xl shadow-sm border border-slate-100 flex-1 p-4 space-y-2">
                          <div className="h-4 bg-slate-100 rounded w-1/3"></div>
                          <div className="h-8 bg-slate-200 rounded w-1/2"></div>
                       </div>
                       <div className="hidden sm:block h-24 bg-white rounded-xl shadow-sm border border-slate-100 flex-1 p-4 space-y-2">
                          <div className="h-4 bg-slate-100 rounded w-1/3"></div>
                          <div className="h-8 bg-slate-200 rounded w-1/2"></div>
                       </div>
                     </div>
                     <div className="flex-1 bg-white rounded-xl shadow-sm border border-slate-100 p-4 space-y-4">
                        <div className="h-6 bg-slate-100 rounded w-1/4 mb-6"></div>
                        {[...Array(4)].map((_, i) => (
                          <div key={i} className="h-12 bg-slate-50 rounded flex items-center px-4 space-x-reverse space-x-4">
                            <div className="w-8 h-8 rounded-full bg-slate-200 shrink-0"></div>
                            <div className="h-4 bg-slate-200 rounded w-1/4"></div>
                            <div className="h-4 bg-slate-100 rounded flex-1"></div>
                          </div>
                        ))}
                     </div>
                  </div>
               </div>
            </div>
          </div>
        </div>
      </section>

      {/* Public Leaderboard Showcase */}
      <section id="best-centers" className="py-24 bg-slate-100/60 border-y border-slate-200/50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-amber-100 text-amber-800 font-bold text-sm mb-4">
              <Trophy className="w-4 h-4 text-amber-500 animate-bounce" />
              <span>لوحة الشرف الوطنية لمراكز التحفيظ</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-extrabold text-slate-800 mb-4">
              أفضل مراكز تحفيظ القرآن الكريم أداءً وجودة
            </h2>
            <p className="text-slate-600 max-w-2xl mx-auto text-base">
              تقييم وتصنيف المراكز بكل شفافية بناءً على نسبة الطلاب المتفوقين، المحفظين المعتمدين، والالتزام بالبرامج التعليمية والإدارية لتسهيل اختيار المركز الأنسب لتسجيل ابنك.
            </p>
          </div>

          {loadingCenters ? (
            <div className="flex justify-center py-12">
              <div className="animate-spin rounded-full h-10 w-10 border-b-2 border-emerald-600" />
            </div>
          ) : bestCenters.length === 0 ? (
            <div className="text-center py-12 text-slate-500 font-medium">
              لا توجد مراكز نشطة مصنفة حالياً بالمنظومة
            </div>
          ) : (
            <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8 stagger">
              {bestCenters.map((center, idx) => {
                const getBadgeColor = (rank: number) => {
                  if (rank === 0) return 'bg-amber-100 text-amber-800 border-amber-200';
                  if (rank === 1) return 'bg-slate-100 text-slate-800 border-slate-200';
                  if (rank === 2) return 'bg-orange-100 text-orange-800 border-orange-200';
                  return 'bg-slate-50 text-slate-600 border-slate-100';
                };
                const getRankLabel = (rank: number) => {
                  if (rank === 0) return '🥇 المركز الأول';
                  if (rank === 1) return '🥈 المركز الثاني';
                  if (rank === 2) return '🥉 المركز الثالث';
                  return `الترتيب #${rank + 1}`;
                };
                
                return (
                  <div key={center.id} className="bg-white rounded-[var(--radius-lg)] border border-slate-200/60 p-6 flex flex-col justify-between shadow-sm hover:shadow-xl hover:-translate-y-1 transition-all">
                    <div>
                      {/* Top Rank Badge */}
                      <div className="flex items-center justify-between mb-4">
                        <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full border text-xs font-bold ${getBadgeColor(idx)}`}>
                          {getRankLabel(idx)}
                        </span>
                        <div className="flex items-center gap-1">
                          <TrendingUp className="w-4 h-4 text-[hsl(var(--lamp-strong))]" />
                          <span className="text-xs font-mono font-bold text-[hsl(var(--lamp-strong))]">{center.score}% جودة</span>
                        </div>
                      </div>

                      {/* Center Info */}
                      <h3 className="text-xl font-bold text-slate-800 mb-2 leading-snug">{center.name}</h3>
                      <p className="text-xs text-slate-500 flex items-center gap-1 mb-4">
                        <MapPin className="w-3.5 h-3.5 text-[hsl(var(--lamp-strong))] shrink-0" />
                        <span className="truncate">{center.address}</span>
                      </p>
                    </div>

                    {/* Stats details */}
                    <div className="pt-4 border-t border-slate-100 flex items-center justify-between">
                      <div className="text-center flex-1 border-l border-slate-100">
                        <p className="text-lg font-bold text-slate-800">{center.students_count}</p>
                        <p className="text-[10px] text-slate-500 font-bold">طالب نشط</p>
                      </div>
                      <div className="text-center flex-1 border-l border-slate-100">
                        <p className="text-lg font-bold text-slate-800">{center.teachers_count}</p>
                        <p className="text-[10px] text-slate-500 font-bold">محفّظ معتمد</p>
                      </div>
                      <div className="text-center flex-1">
                        <p className="text-lg font-bold text-slate-800">{center.halaqat_count}</p>
                        <p className="text-[10px] text-slate-500 font-bold">حلقة قرآنية</p>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </section>

      {/* Features Section */}
      <section id="features" className="py-24 bg-white">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="text-center mb-16">
            <h2 className="text-3xl font-bold text-slate-800 mb-4">مميزات صُممت لخدمة القرآن</h2>
            <p className="text-slate-600 max-w-2xl mx-auto text-lg">
              نوفر جميع الأدوات الإدارية التي تحتاجها المدارس للتركيز على المهمة الأسمى: تحفيظ كتاب الله.
            </p>
          </div>

          <div className="grid md:grid-cols-2 lg:grid-cols-3 gap-8">
            <FeatureCard 
              icon={<BookOpen className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="متابعة الحفظ والمراجعة"
              description="تسجيل يومي دقيق لمقدار الحفظ والمراجعة لكل طالب مع رصد درجات التجويد والتميز."
            />
            <FeatureCard 
              icon={<Users className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="بوابة أولياء الأمور"
              description="إشراك الأهل في رحلة أبنائهم عبر لوحة تحكم تظهر التطور، تقارير الحضور، وتنبيهات المعلم."
            />
            <FeatureCard 
              icon={<Award className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="شهادات رقمية معتمدة"
              description="إصدار تلقائي لشهادات الإنجاز عند إتمام الأجزاء، مزودة برمز استجابة سريعة (QR) للتحقق."
            />
            <FeatureCard 
              icon={<Star className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="سجل الشرف والتحفيز"
              description="نظام نقاط ومكافآت ولوحة شرف عامة لتشجيع الطلاب على التنافس المحمود في حفظ الآيات."
            />
            <FeatureCard 
              icon={<Shield className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="صلاحيات وإدارة آمنة"
              description="أدوار مخصصة للإدارة، المالية، المعلمين لتنظيم العمل وحماية البيانات بموثوقية عالية."
            />
            <FeatureCard 
              icon={<Heart className="w-6 h-6 text-[hsl(var(--lamp-strong))]" />}
              title="كفالة الحفّاظ (قريباً)"
              description="بناء جسر بين المدارس والمتبرعين لتبني الطلاب المتميزين أو تغطية المصروفات التشغيلية للمركز."
            />
          </div>
        </div>
      </section>

      {/* Impact/Donation Section */}
      <section id="impact" className="py-24 bg-[hsl(var(--niche))] text-white relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/arabesque.png')] opacity-10" />
        <div className="absolute -left-48 top-1/2 -translate-y-1/2 w-[500px] h-[500px] bg-[hsl(var(--niche))] rounded-full blur-[100px] opacity-40" />
        
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 relative z-10 text-center lg:text-right flex flex-col lg:flex-row items-center gap-16">
          <div className="flex-1">
            <div className="inline-flex items-center gap-2 px-4 py-2 rounded-full bg-[hsl(var(--niche-2))]/50 border border-emerald-700/50 text-emerald-200 text-sm mb-6">
              <Heart className="w-4 h-4 fill-emerald-200" />
              <span>وقف تقني</span>
            </div>
            <h2 className="text-3xl md:text-5xl font-bold mb-6 leading-tight">
              مشروع خيري لك، <br />
              وصرح معمور بكتاب الله.
            </h2>
            <p className="text-emerald-100 text-lg mb-8 leading-relaxed max-w-2xl mx-auto lg:mx-0">
              "المشكاة" ليس مجرد نظام، بل هو مشروع وقفي يهدف لتطويع التقنية لخدمة الدين. بإمكانك المساهمة في تطوير النظام، أو كفالة مراكز بأكملها ونيل أجر "دعم حُفّاظ القرآن".
            </p>
            <ul className="space-y-4 mb-10 text-right w-fit mx-auto lg:mx-0">
              <li className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0" />
                <span className="text-lg">تخفيف العبء الإداري عن مديري الحلقات.</span>
              </li>
              <li className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0" />
                <span className="text-lg">ربط الأهل بالمسجد وحلقات التحفيظ.</span>
              </li>
              <li className="flex items-center gap-3">
                <CheckCircle2 className="w-6 h-6 text-amber-400 shrink-0" />
                <span className="text-lg">منصة مجانية بالكامل للمراكز الخيرية.</span>
              </li>
            </ul>
            <div className="flex flex-col sm:flex-row gap-4 justify-center lg:justify-start">
              <button className="px-8 py-4 bg-[hsl(var(--lamp))] text-[hsl(225_45%_10%)] font-bold rounded-xl hover:bg-amber-400 transition-all shadow-lg flex items-center justify-center gap-2 text-lg">
                <Heart className="w-5 h-5" />
                <span>ساهم في الوقف التقني</span>
              </button>
            </div>
          </div>
          
          <div className="lg:w-[500px] relative">
            <div className="aspect-square rounded-full bg-[hsl(var(--niche-2))]/50 border-4 border-emerald-700/50 flex items-center justify-center relative overflow-hidden backdrop-blur-sm shadow-2xl">
              <div className="text-center p-8">
                 <h3 className="text-6xl font-bold text-amber-400 mb-2">{bestCenters.length}</h3>
                 <p className="text-xl text-emerald-200">مركز قرآني معتمد بالمنظومة</p>
              </div>
            </div>
            {/* Decor elements */}
            <div className="absolute -top-8 -right-8 w-24 h-24 bg-[hsl(var(--lamp))] rounded-full blur-2xl opacity-40"></div>
            <div className="absolute -bottom-8 -left-8 w-32 h-32 bg-emerald-400 rounded-full blur-2xl opacity-40"></div>
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-[hsl(var(--niche))] border-t border-white/10 pt-16 pb-8 text-white/70">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
          <div className="grid grid-cols-1 md:grid-cols-4 gap-12 mb-12">
            <div className="col-span-1 md:col-span-2">
              <div className="flex items-center gap-3 mb-6">
                <div className="w-10 h-10 bg-[hsl(var(--niche))] rounded-lg flex items-center justify-center">
                  <MishkaatMark className="w-6 h-6 text-[hsl(var(--lamp))]" title="المشكاة" />
                </div>
                <h3 className="text-2xl font-bold text-white">المشكاة</h3>
              </div>
              <p className="text-white/70 text-sm leading-relaxed max-w-sm">
                نظام المشكاة لإدارة دور القرآن الكريم، مشروع وقفي يهدف لتسهيل وميكنة العمل في المدارس القرآنية لتعزيز الحفظ والمراجعة.
              </p>
            </div>
            <div>
              <h4 className="text-white font-bold mb-6">روابط هامة</h4>
              <ul className="space-y-4 text-sm">
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">عن النظام</a></li>
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">دليل الاستخدام</a></li>
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">تسجيل مركز جديد</a></li>
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">الدعم الفني</a></li>
              </ul>
            </div>
            <div>
              <h4 className="text-white font-bold mb-6">ساهم معنا</h4>
              <ul className="space-y-4 text-sm">
                <li><Link to="/sponsorships" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">بوابة الكفالة</Link></li>
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">تطوير النظام (GitHub)</a></li>
                <li><a href="#" className="text-white/70 hover:text-[hsl(var(--lamp))] transition-colors">اتصل بنا</a></li>
              </ul>
            </div>
          </div>
          <div className="pt-8 border-t border-slate-800 text-center text-sm flex flex-col md:flex-row justify-between items-center gap-4">
            <p>جميع الحقوق محفوظة &copy; {new Date().getFullYear()} المشكاة لدور القرآن.</p>
            <p className="flex items-center gap-1">
              صُنع بحب <Heart className="w-4 h-4 text-rose-500 fill-rose-500" /> لخدمة كتاب الله.
            </p>
          </div>
        </div>
      </footer>
    </div>
  );
};

function FeatureCard({ icon, title, description }: { icon: React.ReactNode, title: string, description: string }) {
  return (
    <div className="bg-white rounded-[var(--radius)] p-8 border border-slate-100 hover:border-emerald-200 hover:shadow-xl hover:-translate-y-1 hover:shadow-emerald-100 transition-all group">
      <div className="w-14 h-14 bg-emerald-50 rounded-xl flex items-center justify-center mb-6 group-hover:scale-110 group-hover:bg-emerald-100 transition-all">
        {icon}
      </div>
      <h3 className="text-xl font-bold text-slate-800 mb-3">{title}</h3>
      <p className="text-slate-600 leading-relaxed">{description}</p>
    </div>
  );
}

export default Landing;
