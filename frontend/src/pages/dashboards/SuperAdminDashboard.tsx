/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect, useCallback } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import {
  Building2, Plus, Search, MapPin, Phone, User,
  CheckCircle2, XCircle, Edit, Users, GraduationCap,
  BookOpen, AlertCircle, X, Eye, Calendar, Hash,
  ShieldAlert, Landmark, ArrowUpRight, ArrowDownRight,
  TrendingUp, CircleDot, RefreshCw, Key,
} from 'lucide-react';
import api, { centersApi } from '@/services/api';

interface CenterData {
  id: string;
  name: string;
  address: string;
  phone?: string;
  manager_name?: string;
  manager_id?: string;
  is_active: boolean;
  approval_status: 'approved' | 'suspended' | 'pending' | 'rejected';
  created_at: string;
  students_count: number;
  teachers_count: number;
  halaqat_count: number;
}

interface GlobalStats {
  total_active_centers: number;
  total_active_students: number;
  total_fees_collected_fcfa: number;
  total_salaries_paid_fcfa: number;
  total_expenses_fcfa: number;
  global_balance_fcfa: number;
}

const emptyForm = {
  name: '', address: '', phone: '',
  manager_name: '', manager_username: '', manager_password: '', manager_email: '',
};

export default function SuperAdminDashboard() {
  const [showAddForm, setShowAddForm]     = useState(false);
  const [searchTerm, setSearchTerm]       = useState('');
  const [centers, setCenters]             = useState<CenterData[]>([]);
  const [stats, setStats]                 = useState<GlobalStats | null>(null);
  const [loading, setLoading]             = useState(true);
  const [refreshing, setRefreshing]       = useState(false);
  const [submitting, setSubmitting]       = useState(false);
  const [error, setError]                 = useState('');
  const [formData, setFormData]           = useState(emptyForm);
  const [selectedCenter, setSelectedCenter] = useState<CenterData | null>(null);
  const [statusUpdatingId, setStatusUpdatingId] = useState<string | null>(null);

  const loadData = useCallback(async () => {
    try {
      setError('');
      const [centersResp, statsResp] = await Promise.all([
        centersApi.getAll(),
        api.get('/api/super/dashboard/stats')
      ]);
      setCenters(centersResp as unknown as CenterData[]);
      setStats(statsResp.data);
    } catch (err: any) {
      setError('حدث خطأ أثناء تحميل بيانات الإشراف العام. الرجاء التحقق من الصلاحيات.');
    }
  }, []);

  useEffect(() => {
    const init = async () => {
      setLoading(true);
      await loadData();
      setLoading(false);
    };
    init();
  }, [loadData]);

  const handleRefresh = async () => {
    setRefreshing(true);
    await loadData();
    setRefreshing(false);
  };

  const handleSubmit = async () => {
    if (!formData.name || !formData.address || !formData.manager_username || !formData.manager_password) {
      setError('الرجاء تعبئة كافة الحقول المطلوبة بما في ذلك حساب المدير');
      return;
    }
    try {
      setSubmitting(true);
      setError('');
      await api.post('/api/super/centers', formData);
      setShowAddForm(false);
      setFormData(emptyForm);
      await loadData();
    } catch (err: any) {
      setError(err.response?.data?.detail || 'حدث خطأ أثناء حفظ المركز الجديد');
    } finally {
      setSubmitting(false);
    }
  };

  const handleToggleStatus = async (center: CenterData) => {
    try {
      setStatusUpdatingId(center.id);
      const nextActive = !center.is_active;
      const nextStatus = nextActive ? 'approved' : 'suspended';
      
      await api.post(`/api/super/centers/${center.id}/status`, {
        is_active: nextActive,
        approval_status: nextStatus
      });
      
      // Update local state smoothly
      setCenters(prev => prev.map(c => c.id === center.id ? { ...c, is_active: nextActive, approval_status: nextStatus } : c));
      await loadData(); // Reload stats as well
    } catch (err: any) {
      alert(err.response?.data?.detail || 'فشل تحديث حالة المركز');
    } finally {
      setStatusUpdatingId(null);
    }
  };

  const filtered = centers.filter(c =>
    c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    c.address.includes(searchTerm) ||
    (c.manager_name || '').toLowerCase().includes(searchTerm.toLowerCase())
  );

  if (loading) return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <LoadingSpinner size="lg" />
        <p className="text-[hsl(var(--muted-foreground))] mt-4 font-medium">جاري تحميل منصة الأوقاف الموحدة...</p>
      </div>
    </div>
  );

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">
      
      {/* Super Admin Top Header Banner */}
      <div className="relative overflow-hidden rounded-3xl gradient-sidebar border-2 border-[hsl(var(--gold))/20] p-6 lg:p-8 text-white shadow-xl">
        <div className="absolute top-[-50px] left-[-50px] w-64 h-64 rounded-full bg-white/5 pointer-events-none" />
        <div className="absolute bottom-[-30px] right-20 w-44 h-44 rounded-full bg-white/5 pointer-events-none" />
        <div className="relative z-10 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2 text-xs font-bold badge-gold text-white px-3 py-1 rounded-full w-fit mb-2">
              <ShieldAlert className="w-3.5 h-3.5" />
              وزارة الشؤون الإسلامية والأوقاف
            </div>
            <h1 className="text-2xl lg:text-3xl font-black mb-1">منصة مِشكاة للإشراف العام والرقابة</h1>
            <p className="text-white/70 text-xs lg:text-sm">لوحة الإدارة المركزية والرقابة المالية لجميع مراكز التحفيظ المسجلة</p>
          </div>
          <div className="flex gap-2">
            <button
              onClick={handleRefresh}
              disabled={refreshing}
              className="p-3 rounded-xl bg-white/10 hover:bg-white/20 transition-all border border-white/10 flex items-center gap-2 text-sm font-semibold"
              title="تحديث البيانات"
            >
              <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin' : ''}`} />
              تحديث
            </button>
            <button
              onClick={() => setShowAddForm(!showAddForm)}
              className="gradient-primary text-white border border-[hsl(var(--primary-light))/40] font-bold px-5 py-3 rounded-xl flex items-center gap-2 shadow-lg hover:opacity-90 transition-all text-sm"
            >
              <Plus className="w-4 h-4" />
              إضافة مركز معتمد
            </button>
          </div>
        </div>
      </div>

      {/* Global SaaS Financial & Enrollment Metrics */}
      {stats && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 stagger">
          
          {/* Active Centers */}
          <div className="stat-card bg-white rounded-2xl p-5 border border-[hsl(var(--border))] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] font-bold mb-1">المراكز المعتمدة</p>
              <p className="text-3xl font-black text-[hsl(var(--primary))]">{stats.total_active_centers}</p>
              <p className="text-[10px] text-emerald-600 font-bold mt-1.5 flex items-center gap-1">
                <CircleDot className="w-3 h-3 fill-emerald-500 animate-pulse" />
                نشطة وتعمل حالياً
              </p>
            </div>
            <div className="w-12 h-12 bg-[hsl(var(--primary-light))] rounded-xl flex items-center justify-center">
              <Building2 className="w-6 h-6 text-[hsl(var(--primary))]" />
            </div>
          </div>

          {/* Active Students */}
          <div className="stat-card bg-white rounded-2xl p-5 border border-[hsl(var(--border))] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] font-bold mb-1">إجمالي الطلاب النشطين</p>
              <p className="text-3xl font-black text-[hsl(var(--gold-dark))]">{stats.total_active_students}</p>
              <p className="text-[10px] text-[hsl(var(--muted-foreground))] font-semibold mt-1.5 flex items-center gap-1">
                <Users className="w-3.5 h-3.5" />
                تحت الإشراف المباشر
              </p>
            </div>
            <div className="w-12 h-12 bg-amber-50 rounded-xl flex items-center justify-center">
              <Users className="w-6 h-6 text-[hsl(var(--gold-dark))]" />
            </div>
          </div>

          {/* Treasury Outflow (Salaries + Expenses) */}
          <div className="stat-card bg-white rounded-2xl p-5 border border-[hsl(var(--border))] shadow-sm flex items-center justify-between">
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] font-bold mb-1">إجمالي المصروفات والرواتب</p>
              <p className="text-2xl font-black text-rose-600">
                {(stats.total_salaries_paid_fcfa + stats.total_expenses_fcfa).toLocaleString()}
                <span className="text-xs font-bold mr-1">FCFA</span>
              </p>
              <p className="text-[10px] text-rose-500 font-semibold mt-1.5 flex items-center gap-0.5">
                <ArrowDownRight className="w-3.5 h-3.5" />
                رواتب: {stats.total_salaries_paid_fcfa.toLocaleString()} FCFA
              </p>
            </div>
            <div className="w-12 h-12 bg-rose-50 rounded-xl flex items-center justify-center">
              <Landmark className="w-6 h-6 text-rose-500" />
            </div>
          </div>

          {/* Global Net Balance */}
          <div className={`stat-card rounded-2xl p-5 border shadow-md flex items-center justify-between transition-colors ${stats.global_balance_fcfa >= 0 ? 'bg-emerald-50/50 border-emerald-100' : 'bg-rose-50/50 border-rose-100'}`}>
            <div>
              <p className="text-xs text-[hsl(var(--muted-foreground))] font-bold mb-1">صافي الرصيد الإجمالي العام</p>
              <p className={`text-2xl font-black ${stats.global_balance_fcfa >= 0 ? 'text-emerald-700' : 'text-rose-700'}`}>
                {stats.global_balance_fcfa.toLocaleString()}
                <span className="text-xs font-bold mr-1">FCFA</span>
              </p>
              <p className={`text-[10px] font-bold mt-1.5 flex items-center gap-0.5 ${stats.global_balance_fcfa >= 0 ? 'text-emerald-600' : 'text-rose-600'}`}>
                {stats.global_balance_fcfa >= 0 ? <ArrowUpRight className="w-3.5 h-3.5" /> : <ArrowDownRight className="w-3.5 h-3.5" />}
                رصيد إيجابي للخزينة العامة
              </p>
            </div>
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${stats.global_balance_fcfa >= 0 ? 'bg-emerald-100 text-emerald-700' : 'bg-rose-100 text-rose-700'}`}>
              <TrendingUp className="w-6 h-6" />
            </div>
          </div>

        </div>
      )}

      {/* Centers Leaderboard & Performance Classification */}
      {centers.length > 0 && (() => {
        const calculateCenterScore = (c: CenterData) => {
          const studentScore = Math.min(40, c.students_count * 2); 
          const teacherScore = Math.min(30, c.teachers_count * 6); 
          const halaqahScore = Math.min(30, c.halaqat_count * 5); 
          return Math.round(studentScore + teacherScore + halaqahScore);
        };

        const getCommitmentLevel = (score: number) => {
          if (score >= 80) return { label: 'ممتاز - التزام كامل', color: 'text-emerald-600 bg-emerald-50 border-emerald-100' };
          if (score >= 50) return { label: 'جيد جداً - نشط', color: 'text-blue-600 bg-blue-50 border-blue-100' };
          if (score >= 25) return { label: 'مقبول - يحتاج متابعة', color: 'text-amber-600 bg-amber-50 border-amber-100' };
          return { label: 'ضعيف - غير ملتزم إدارياً', color: 'text-rose-600 bg-rose-50 border-rose-100' };
        };

        const sortedCenters = [...centers]
          .map(c => ({ ...c, score: calculateCenterScore(c) }))
          .sort((a, b) => b.score - a.score);

        return (
          <div className="bg-white rounded-3xl border border-[hsl(var(--border))] shadow-sm p-6 space-y-4">
            <div className="flex items-center justify-between border-b pb-3">
              <div>
                <h3 className="text-lg font-black flex items-center gap-2 text-emerald-800">
                  <TrendingUp className="w-5.5 h-5.5 text-amber-500 animate-pulse" />
                  تصنيف وتقييم المراكز الأكثر التزاماً وتميزاً
                </h3>
                <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">تقييم تلقائي بناءً على الالتزام الإداري، الحلقات النشطة، وأعداد الطلاب الملتحقين</p>
              </div>
              <span className="badge-gold text-xs px-3 py-1 rounded-full font-bold">التقرير العام للجودة</span>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-right border-collapse">
                <thead>
                  <tr className="border-b border-[hsl(var(--border))] text-xs text-[hsl(var(--muted-foreground))] font-bold">
                    <th className="pb-3 text-center w-16">الترتيب</th>
                    <th className="pb-3">المركز</th>
                    <th className="pb-3 text-center">أعداد الطلاب</th>
                    <th className="pb-3 text-center">المحفظين والحلقات</th>
                    <th className="pb-3 text-center">درجة الالتزام</th>
                    <th className="pb-3 text-center">مستوى التقييم</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-[hsl(var(--border))]/50">
                  {sortedCenters.map((center, idx) => {
                    const level = getCommitmentLevel(center.score);
                    return (
                      <tr key={center.id} className="hover:bg-[hsl(var(--muted))]/30 transition-colors">
                        <td className="py-4 text-center font-bold">
                          {idx === 0 ? <span className="text-xl">🥇</span> : 
                           idx === 1 ? <span className="text-xl">🥈</span> : 
                           idx === 2 ? <span className="text-xl">🥉</span> : 
                           <span className="text-xs text-gray-500 font-mono">#{idx + 1}</span>}
                        </td>
                        <td className="py-4">
                          <span className="font-bold text-gray-800 block">{center.name}</span>
                          <span className="text-[10px] text-[hsl(var(--muted-foreground))]" dir="ltr">{center.address}</span>
                        </td>
                        <td className="py-4 text-center font-bold text-slate-700">{center.students_count} طالب</td>
                        <td className="py-4 text-center text-xs text-slate-500">
                          {center.teachers_count} محفظين / {center.halaqat_count} حلقات
                        </td>
                        <td className="py-4 text-center">
                          <div className="flex items-center justify-center gap-1.5">
                            <div className="w-16 bg-gray-100 h-2 rounded-full overflow-hidden">
                              <div className="bg-emerald-600 h-full rounded-full" style={{ width: `${center.score}%` }} />
                            </div>
                            <span className="text-xs font-mono font-bold text-emerald-700">{center.score}%</span>
                          </div>
                        </td>
                        <td className="py-4 text-center">
                          <span className={`inline-block text-[10px] font-bold px-2.5 py-1 rounded-full border ${level.color}`}>
                            {level.label}
                          </span>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        );
      })()}

      {/* Main UI Search and Management Console */}
      <div className="space-y-4">
        
        {/* Error Notification */}
        {error && (
          <div className="p-4 rounded-xl bg-rose-50 border border-rose-100 text-rose-600 text-sm flex items-center gap-3 animate-shake">
            <AlertCircle className="w-5 h-5 shrink-0" />
            <span className="font-semibold">{error}</span>
            <button onClick={() => setError('')} className="mr-auto text-rose-400 hover:text-rose-600 font-black">✕</button>
          </div>
        )}

        {/* Add Center Panel */}
        {showAddForm && (
          <div className="bg-white rounded-3xl border-2 border-[hsl(var(--primary))/20] shadow-xl p-6 animate-slide-in-up">
            <div className="flex items-center justify-between mb-5 border-b pb-3">
              <h3 className="text-lg font-black text-[hsl(var(--primary))] flex items-center gap-2">
                <Building2 className="w-5 h-5" />
                تسجيل واعتماد مركز تحفيظ جديد
              </h3>
              <button onClick={() => setShowAddForm(false)} className="p-1.5 rounded-lg hover:bg-[hsl(var(--muted))] transition-colors">
                <X className="w-5 h-5 text-[hsl(var(--muted-foreground))]" />
              </button>
            </div>
            <div className="grid md:grid-cols-2 gap-4">
              {[
                { label: 'اسم المركز *', key: 'name', placeholder: 'مثال: مركز الإمام نافع للقرآن الكريم' },
                { label: 'العنوان الجغرافي *', key: 'address', placeholder: 'البلدية - المدينة - الحي' },
                { label: 'رقم الهاتف المعتمد', key: 'phone', placeholder: '+223 XX XX XX XX', dir: 'ltr' },
                { label: 'اسم مدير المركز المعتمد *', key: 'manager_name', placeholder: 'الاسم الكامل للمدير' },
                { label: 'بريد المدير الإلكتروني', key: 'manager_email', placeholder: 'email@example.com', dir: 'ltr' },
                { label: 'اسم مستخدم المدير المعتمد *', key: 'manager_username', placeholder: 'username', dir: 'ltr' },
                { label: 'كلمة مرور المدير المعتمدة *', key: 'manager_password', placeholder: 'كلمة مرور قوية (أرقام وحروف)', dir: 'ltr', type: 'password' },
              ].map(f => (
                <div key={f.key} className={f.key === 'manager_password' ? 'col-span-1' : ''}>
                  <label className="block text-sm font-semibold mb-1.5">{f.label}</label>
                  <input
                    type={f.type || 'text'}
                    placeholder={f.placeholder}
                    dir={(f as any).dir}
                    value={(formData as any)[f.key]}
                    onChange={e => setFormData({ ...formData, [f.key]: e.target.value })}
                    className="w-full h-11 px-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] transition-all text-sm"
                  />
                </div>
              ))}
            </div>
            <div className="flex gap-3 mt-6 pt-4 border-t">
              <button onClick={handleSubmit} disabled={submitting}
                className="flex-1 gradient-primary text-white font-bold py-3 rounded-xl hover:opacity-90 transition-all disabled:opacity-60 flex items-center justify-center gap-2">
                {submitting ? <><LoadingSpinner size="sm" /><span>جاري حفظ واعتماد المركز...</span></> : <><CheckCircle2 className="w-4.5 h-4.5" />تأكيد تسجيل المركز واعتماده</>}
              </button>
              <button onClick={() => setShowAddForm(false)}
                className="px-6 py-3 rounded-xl border-2 border-[hsl(var(--border))] font-semibold hover:bg-[hsl(var(--muted))] transition-all">
                إلغاء
              </button>
            </div>
          </div>
        )}

        {/* Console control header */}
        <div className="flex flex-col sm:flex-row items-center gap-3">
          <div className="relative flex-1 w-full">
            <Search className="absolute right-4 top-3.5 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
            <input
              placeholder="البحث باسم مركز التحفيظ، العنوان، أو اسم المدير المعتمد..."
              value={searchTerm}
              onChange={e => setSearchTerm(e.target.value)}
              className="w-full h-12 pr-12 pl-4 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] transition-all text-[hsl(var(--foreground))]"
            />
          </div>
        </div>

        {/* Center Grid list */}
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <h3 className="text-lg font-black flex items-center gap-2">
              <Building2 className="w-5 h-5 text-[hsl(var(--primary))]" />
              مراكز التحفيظ المسجلة بالمنظومة
            </h3>
            <span className="badge-gold text-xs px-2.5 py-1 rounded-full font-bold">{filtered.length} مركز</span>
          </div>

          {filtered.length === 0 ? (
            <div className="text-center py-20 bg-white rounded-3xl border-2 border-dashed border-[hsl(var(--border))]">
              <Building2 className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-30 animate-pulse" />
              <p className="text-[hsl(var(--muted-foreground))] font-semibold text-base">لا توجد مراكز تحفيظ مطابقة لبحثك</p>
            </div>
          ) : (
            <div className="grid md:grid-cols-2 xl:grid-cols-3 gap-6 stagger">
              {filtered.map(center => {
                const isUpdating = statusUpdatingId === center.id;
                return (
                  <div key={center.id} className="bg-white rounded-3xl shadow-sm border border-[hsl(var(--border))] overflow-hidden flex flex-col hover:shadow-xl transition-all stat-card">
                    {/* Header */}
                    <div className="gradient-primary p-5">
                      <div className="flex items-start justify-between">
                        <div className="flex-1 min-w-0">
                          <h4 className="font-black text-white text-lg truncate leading-snug">{center.name}</h4>
                          <div className="flex items-center gap-1 mt-1.5 text-white/70 text-xs">
                            <MapPin className="w-3.5 h-3.5 shrink-0" />
                            <span className="truncate">{center.address}</span>
                          </div>
                        </div>
                        <div className="flex gap-2">
                          <button
                            onClick={() => setSelectedCenter(center)}
                            className="p-2 rounded-xl bg-white/15 hover:bg-white/30 transition-colors text-white"
                            title="عرض تفاصيل الإحصائيات"
                          >
                            <Eye className="w-4 h-4" />
                          </button>
                        </div>
                      </div>
                    </div>

                    {/* Stats rows */}
                    <div className="grid grid-cols-3 divide-x divide-x-reverse divide-[hsl(var(--border))] border-b border-[hsl(var(--border))]">
                      {[
                        { icon: Users, val: center.students_count, label: 'طالب' },
                        { icon: GraduationCap, val: center.teachers_count, label: 'محفظ' },
                        { icon: BookOpen, val: center.halaqat_count, label: 'حلقة' },
                      ].map((s, idx) => (
                        <div key={idx} className="p-3 text-center">
                          <s.icon className="w-4 h-4 mx-auto mb-1 text-[hsl(var(--primary))]" />
                          <p className="text-xl font-black text-[hsl(var(--foreground))]">{s.val}</p>
                          <p className="text-[10px] text-[hsl(var(--muted-foreground))] font-semibold">{s.label}</p>
                        </div>
                      ))}
                    </div>

                    {/* Body Info */}
                    <div className="p-5 flex-1 flex flex-col justify-between gap-4 text-sm text-[hsl(var(--muted-foreground))]">
                      <div className="space-y-2">
                        {center.phone && (
                          <div className="flex items-center gap-2"><Phone className="w-4 h-4 text-[hsl(var(--primary))] shrink-0" /><span dir="ltr" className="text-xs font-semibold">{center.phone}</span></div>
                        )}
                        {center.manager_name && (
                          <div className="flex items-center gap-2"><User className="w-4 h-4 text-[hsl(var(--primary))] shrink-0" /><span className="text-xs font-medium">المدير: {center.manager_name}</span></div>
                        )}
                        <div className="flex items-center gap-2 pt-1 border-t border-[hsl(var(--border))]">
                          <Calendar className="w-4 h-4 text-[hsl(var(--gold))]" />
                          <span className="text-[10px]">تاريخ التسجيل: {new Date(center.created_at).toLocaleDateString('ar-SA')}</span>
                        </div>
                      </div>

                      {/* State switch action */}
                      <div className="flex items-center justify-between pt-3 border-t">
                        <div className="flex flex-col">
                          <span className="text-[10px] font-bold text-[hsl(var(--muted-foreground))]">الترخيص والاشتراك</span>
                          <span className={`inline-block text-[10px] font-bold px-2 py-0.5 rounded-full w-fit mt-1
                            ${center.is_active && center.approval_status === 'approved' ? 'bg-emerald-50 text-emerald-700 border border-emerald-100' : ''}
                            ${center.approval_status === 'suspended' ? 'bg-amber-50 text-amber-700 border border-amber-100' : ''}
                            ${center.approval_status === 'pending' ? 'bg-blue-50 text-blue-700 border border-blue-100' : ''}
                            ${center.approval_status === 'rejected' ? 'bg-rose-50 text-rose-700 border border-rose-100' : ''}
                          `}>
                            {center.approval_status === 'approved' ? 'معتمد ونشط' : ''}
                            {center.approval_status === 'suspended' ? 'موقوف مؤقتاً' : ''}
                            {center.approval_status === 'pending' ? 'قيد الموافقة' : ''}
                            {center.approval_status === 'rejected' ? 'طلب مرفوض' : ''}
                          </span>
                        </div>
                        <button
                          onClick={() => handleToggleStatus(center)}
                          disabled={isUpdating}
                          className={`px-4 py-2 rounded-xl text-xs font-bold flex items-center gap-2 transition-all ${
                            center.is_active
                              ? 'bg-amber-50 text-amber-700 hover:bg-amber-100 border border-amber-200'
                              : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border border-emerald-200'
                          }`}
                        >
                          {isUpdating ? (
                            <LoadingSpinner size="sm" />
                          ) : center.is_active ? (
                            <><XCircle className="w-3.5 h-3.5" />إيقاف مؤقت</>
                          ) : (
                            <><CheckCircle2 className="w-3.5 h-3.5" />تنشيط معتمد</>
                          )}
                        </button>
                      </div>
                    </div>

                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>

      {/* Selected Center Details Modal */}
      {selectedCenter && (
        <div className="modal-overlay animate-fade-in" onClick={() => setSelectedCenter(null)}>
          <div className="bg-white rounded-3xl shadow-2xl w-full max-w-lg max-h-[90vh] overflow-y-auto" onClick={e => e.stopPropagation()}>
            <div className="gradient-primary p-6 rounded-t-3xl flex items-center justify-between text-white">
              <div>
                <h2 className="text-xl font-black">{selectedCenter.name}</h2>
                <span className="text-xs opacity-80">{selectedCenter.address}</span>
              </div>
              <button onClick={() => setSelectedCenter(null)} className="p-2 rounded-xl bg-white/10 hover:bg-white/20 text-white">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-6 space-y-6">
              
              {/* Detailed metrics */}
              <div className="grid grid-cols-3 gap-3">
                {[
                  { label: 'إجمالي الطلاب', val: selectedCenter.students_count, icon: Users, bg: 'bg-emerald-50 text-emerald-700' },
                  { label: 'إجمالي المحفظين', val: selectedCenter.teachers_count, icon: GraduationCap, bg: 'bg-blue-50 text-blue-700' },
                  { label: 'إجمالي الحلقات', val: selectedCenter.halaqat_count, icon: BookOpen, bg: 'bg-amber-50 text-amber-700' },
                ].map((m, idx) => (
                  <div key={idx} className={`p-4 rounded-2xl text-center ${m.bg}`}>
                    <m.icon className="w-5 h-5 mx-auto mb-1" />
                    <p className="text-2xl font-black">{m.val}</p>
                    <p className="text-[10px] font-bold">{m.label}</p>
                  </div>
                ))}
              </div>

              {/* Administrative contacts */}
              <div className="space-y-3">
                <h4 className="font-bold text-sm border-b pb-2 flex items-center gap-2">
                  <Key className="w-4 h-4 text-[hsl(var(--primary))]" />
                  بيانات الترخيص الإداري والمدير
                </h4>
                <div className="space-y-2 text-xs">
                  <div className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                    <span className="text-[hsl(var(--muted-foreground))]">المدير المسؤول</span>
                    <span className="font-bold">{selectedCenter.manager_name || 'غير محدد'}</span>
                  </div>
                  {selectedCenter.phone && (
                    <div className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                      <span className="text-[hsl(var(--muted-foreground))]">الهاتف المعتمد</span>
                      <span className="font-semibold" dir="ltr">{selectedCenter.phone}</span>
                    </div>
                  )}
                  <div className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                    <span className="text-[hsl(var(--muted-foreground))]">حالة الحساب</span>
                    <span className={`font-bold ${selectedCenter.is_active ? 'text-emerald-600' : 'text-rose-600'}`}>
                      {selectedCenter.is_active ? 'نشط ويعمل' : 'موقوف / مجمد'}
                    </span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                    <span className="text-[hsl(var(--muted-foreground))]">تاريخ التسجيل</span>
                    <span>{new Date(selectedCenter.created_at).toLocaleDateString('ar-SA', { year: 'numeric', month: 'long', day: 'numeric' })}</span>
                  </div>
                  <div className="flex items-center justify-between p-3 rounded-xl bg-[hsl(var(--muted))]">
                    <span className="text-[hsl(var(--muted-foreground))]">معرف المركز (UUID)</span>
                    <span className="font-mono text-[10px]" dir="ltr">{selectedCenter.id}</span>
                  </div>
                </div>
              </div>

              <div className="flex gap-2">
                <button
                  onClick={() => {
                    handleToggleStatus(selectedCenter);
                    setSelectedCenter(null);
                  }}
                  className={`flex-1 py-3 rounded-xl text-xs font-bold border transition-all ${
                    selectedCenter.is_active 
                      ? 'bg-amber-50 text-amber-700 hover:bg-amber-100 border-amber-200' 
                      : 'bg-emerald-50 text-emerald-700 hover:bg-emerald-100 border-emerald-200'
                  }`}
                >
                  {selectedCenter.is_active ? 'إيقاف ترخيص المركز مؤقتاً' : 'تنشيط واعتماد ترخيص المركز'}
                </button>
                <button onClick={() => setSelectedCenter(null)} className="px-6 py-3 rounded-xl bg-[hsl(var(--muted))] hover:bg-[hsl(var(--border))] text-xs font-semibold">
                  إغلاق
                </button>
              </div>

            </div>
          </div>
        </div>
      )}

    </div>
  );
}
