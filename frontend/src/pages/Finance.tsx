/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { LoadingSpinner } from '@/components/ui/loading';
import { useAuth } from '@/contexts/AuthContext';
import {
  DollarSign, Plus, TrendingUp, TrendingDown, Users, GraduationCap,
  CheckCircle2, AlertCircle, X, Wallet, Receipt, Landmark, Filter,
  Calendar, Trash2, Printer, Sparkles, Award, Home,
} from 'lucide-react';
import api from '@/services/api';
import { studentsApi, teachersApi } from '@/services/api';

interface Fee { id: string; student_id: string; student_name?: string; amount: number; due_date: string; fee_type: string; status: string; notes?: string; }
interface Salary { id: string; teacher_id: string; teacher_name?: string; amount: number; month: string; center_id: string; notes?: string; created_at: string; }
interface Expense { id: string; title: string; amount: number; category?: string; date: string; center_id: string; notes?: string; created_at: string; }
interface Student { id: string; name: string; }
interface Teacher { id: string; name: string; }
interface Center { id: string; name: string; currency?: string; address?: string; phone?: string; }

const feeTypeLabels: Record<string, string> = { monthly: 'شهري', annual: 'سنوي', registration: 'تسجيل' };
const feeStatusLabels: Record<string, { text: string; cls: string }> = {
  pending: { text: 'معلق', cls: 'bg-amber-100 text-amber-700' },
  paid:    { text: 'مدفوع', cls: 'bg-emerald-100 text-emerald-700' },
  overdue: { text: 'متأخر', cls: 'bg-red-100 text-red-700' },
};
const expenseCategories = ['إيجار', 'كهرباء وماء', 'مستلزمات', 'صيانة', 'نشاطات', 'متنوع'];

type Tab = 'fees' | 'salaries' | 'expenses';

export default function Finance() {
  const { user } = useAuth();
  const [tab, setTab] = useState<Tab>('fees');
  const [fees, setFees]         = useState<Fee[]>([]);
  const [salaries, setSalaries] = useState<Salary[]>([]);
  const [expenses, setExpenses] = useState<Expense[]>([]);
  const [students, setStudents] = useState<Student[]>([]);
  const [teachers, setTeachers] = useState<Teacher[]>([]);
  const [center, setCenter]     = useState<Center | null>(null);
  const [loading, setLoading]   = useState(true);

  // Forms
  const [showFeeForm, setShowFeeForm]         = useState(false);
  const [showSalaryForm, setShowSalaryForm]   = useState(false);
  const [showExpenseForm, setShowExpenseForm] = useState(false);
  const [submitting, setSubmitting]           = useState(false);
  const [feeForm, setFeeForm]   = useState({ student_id: '', amount: '', due_date: '', fee_type: 'monthly' as any, notes: '' });
  const [salaryForm, setSalaryForm] = useState({ teacher_id: '', amount: '', month: new Date().toISOString().slice(0, 7), notes: '' });
  const [expenseForm, setExpenseForm] = useState({ title: '', amount: '', category: '', date: new Date().toISOString().slice(0, 10), notes: '' });
  
  // Printing voucher state
  const [printVoucher, setPrintVoucher] = useState<{
    type: 'fee' | 'salary' | 'expense';
    title: string;
    targetName: string;
    amount: number;
    date: string;
    notes?: string;
    refId: string;
  } | null>(null);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [f, sal, exp, s, t, centersList] = await Promise.all([
        api.get('/fees'),
        api.get('/salaries'),
        api.get('/expenses'),
        studentsApi.getAll(),
        teachersApi.getAll(),
        api.get('/centers'),
      ]);
      setFees(f.data);
      setSalaries(sal.data);
      setExpenses(exp.data);
      setStudents(s as unknown as Student[]);
      setTeachers(t as unknown as Teacher[]);
      if (centersList.data && centersList.data.length > 0) {
        setCenter(centersList.data[0]);
      }
    } catch { /* silent */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  // Dynamic currency format matching center setting
  const formatCurrency = useCallback((amount: number) => {
    const code = center?.currency || 'FCFA';
    return new Intl.NumberFormat('fr-FR', { style: 'decimal' }).format(Math.round(amount)) + ' ' + code;
  }, [center]);

  const handlePayFee = async (id: string) => {
    try {
      await api.post(`/fees/${id}/pay`);
      await loadData();
    } catch { /* silent */ }
  };

  const handleAddFee = async () => {
    if (!feeForm.student_id || !feeForm.amount) return;
    const student = students.find(s => s.id === feeForm.student_id);
    try {
      setSubmitting(true);
      await api.post('/fees', {
        student_id: feeForm.student_id,
        student_name: student?.name,
        amount: Number(feeForm.amount),
        due_date: feeForm.due_date,
        fee_type: feeForm.fee_type,
        notes: feeForm.notes || undefined,
      });
      setShowFeeForm(false);
      setFeeForm({ student_id: '', amount: '', due_date: '', fee_type: 'monthly', notes: '' });
      await loadData();
    } catch { /* silent */ }
    finally { setSubmitting(false); }
  };

  const handleAddSalary = async () => {
    if (!salaryForm.teacher_id || !salaryForm.amount) return;
    const teacher = teachers.find(t => t.id === salaryForm.teacher_id);
    try {
      setSubmitting(true);
      await api.post('/salaries', {
        teacher_id: salaryForm.teacher_id,
        teacher_name: teacher?.name,
        amount: Number(salaryForm.amount),
        month: salaryForm.month,
        center_id: user?.center_id || '',
        notes: salaryForm.notes || undefined,
      });
      setShowSalaryForm(false);
      await loadData();
    } catch { /* silent */ }
    finally { setSubmitting(false); }
  };

  const handleAddExpense = async () => {
    if (!expenseForm.title || !expenseForm.amount) return;
    try {
      setSubmitting(true);
      await api.post('/expenses', {
        title: expenseForm.title,
        amount: Number(expenseForm.amount),
        category: expenseForm.category || undefined,
        date: expenseForm.date,
        center_id: user?.center_id || '',
        notes: expenseForm.notes || undefined,
      });
      setShowExpenseForm(false);
      setExpenseForm({ title: '', amount: '', category: '', date: new Date().toISOString().slice(0, 10), notes: '' });
      await loadData();
    } catch { /* silent */ }
    finally { setSubmitting(false); }
  };

  const handleDeleteExpense = async (id: string) => {
    if (!confirm('حذف هذا المصروف؟')) return;
    await api.delete(`/expenses/${id}`);
    await loadData();
  };

  const handleTriggerPrint = (voucher: typeof printVoucher) => {
    setPrintVoucher(voucher);
    setTimeout(() => {
      window.print();
    }, 250);
  };

  const summary = useMemo(() => {
    const totalFees     = fees.filter(f => f.status === 'paid').reduce((s, f) => s + f.amount, 0);
    const pendingFees   = fees.filter(f => f.status === 'pending').reduce((s, f) => s + f.amount, 0);
    const totalSalaries = salaries.reduce((s, sal) => s + sal.amount, 0);
    const totalExpenses = expenses.reduce((s, e) => s + e.amount, 0);
    const net = totalFees - totalSalaries - totalExpenses;
    return { totalFees, pendingFees, totalSalaries, totalExpenses, net };
  }, [fees, salaries, expenses]);

  if (loading) return (
    <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>
  );

  return (
    <div className="space-y-6 animate-fade-in text-[hsl(var(--foreground))]">
      
      {/* Dynamic CSS Print Styling */}
      <style>{`
        @media print {
          body * {
            visibility: hidden;
          }
          #print-section, #print-section * {
            visibility: visible;
          }
          #print-section {
            position: absolute;
            left: 0;
            top: 0;
            width: 100%;
            height: 100%;
            background: white !important;
            color: black !important;
            padding: 30px;
          }
          .no-print {
            display: none !important;
          }
        }
      `}</style>

      {/* Printable Receipt layout */}
      {printVoucher && (
        <div id="print-section" className="hidden print:block" dir="rtl">
          <div className="border-4 border-double border-[hsl(152,45%,38%)] p-6 rounded-2xl flex flex-col justify-between h-[90vh] text-center">
            
            {/* Header */}
            <div>
              <div className="text-xs font-bold text-[hsl(152,45%,38%)]">المملكة المغربية / الشؤون الإسلامية المعتمدة</div>
              <h1 className="text-xl font-extrabold text-[hsl(152,45%,38%)] mt-2">سند إيصال مالي رسمي</h1>
              <p className="text-[10px] text-gray-500 mt-1">إدارة التحفيظ والتعليم الأكاديمي المتكامل</p>
            </div>

            {/* Voucher Details */}
            <div className="my-6 space-y-4 text-right px-6 text-sm">
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-500 font-semibold">اسم المركز:</span>
                <span className="font-bold text-gray-800">{center?.name || 'مركز تحفيظ معتمد'}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-500 font-semibold">رقم السند المالي:</span>
                <span className="font-mono font-bold text-gray-800" dir="ltr">#{printVoucher.refId.slice(-8).toUpperCase()}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-500 font-semibold">نوع الحركة المالية:</span>
                <span className="font-bold text-gray-800">{printVoucher.title}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-500 font-semibold">المستفيد / العميل:</span>
                <span className="font-bold text-emerald-800">{printVoucher.targetName}</span>
              </div>
              <div className="flex justify-between border-b pb-2">
                <span className="text-gray-500 font-semibold">التاريخ:</span>
                <span className="font-semibold text-gray-800">{printVoucher.date}</span>
              </div>
              <div className="flex justify-between border-b pb-2 bg-emerald-50 p-2 rounded-lg">
                <span className="text-emerald-800 font-bold">المبلغ المدفوع:</span>
                <span className="font-black text-emerald-800 text-lg" dir="ltr">{formatCurrency(printVoucher.amount)}</span>
              </div>
              {printVoucher.notes && (
                <div className="flex justify-between border-b pb-2">
                  <span className="text-gray-500 font-semibold">ملاحظات:</span>
                  <span className="font-medium text-gray-700">{printVoucher.notes}</span>
                </div>
              )}
            </div>

            {/* QR Placeholder and sign */}
            <div className="flex flex-col items-center gap-2">
              <div className="w-16 h-16 border border-dashed border-gray-400 flex items-center justify-center font-mono text-[9px] text-gray-400">
                [QR CODE]
              </div>
              <span className="text-[9px] text-gray-400 font-mono" dir="ltr">{printVoucher.refId}</span>
            </div>

            {/* Stamp and Signatures */}
            <div className="grid grid-cols-3 gap-6 px-4 pt-4 border-t border-gray-100 text-xs">
              <div>
                <span className="text-gray-500 block mb-6">توقيع المستلم</span>
                <div className="h-6 border-b border-gray-200"></div>
              </div>
              <div>
                <span className="text-gray-500 block mb-6">خاتم المركز الرسمي</span>
                <div className="h-6 border-b border-gray-200"></div>
              </div>
              <div>
                <span className="text-gray-500 block mb-6">توقيع المدير المسؤول</span>
                <div className="h-6 border-b border-gray-200"></div>
              </div>
            </div>

            <div className="text-[9px] text-gray-400">
              النظام محمي وموثق قانونياً باسم المطور الرسمي Abdoul Malick Cisse © 2026
            </div>
          </div>
        </div>
      )}

      {/* Screen Interface */}
      <div className="print:hidden space-y-6">

        {/* Header */}
        <div className="relative overflow-hidden rounded-3xl gradient-primary p-6 text-white shadow-lg">
          <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
          <div className="relative z-10 flex items-center justify-between">
            <div>
              <h1 className="text-2xl font-black mb-1">الإدارة المالية</h1>
              <p className="text-white/70 text-sm">رسوم الطلاب · رواتب المحفظين · مصروفات المركز</p>
            </div>
            <div className="w-14 h-14 bg-white/15 rounded-2xl flex items-center justify-center animate-float">
              <Wallet className="w-7 h-7 text-white" />
            </div>
          </div>
        </div>

        {/* Summary cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger">
          {[
            { label: 'رسوم محصَّلة',   val: formatCurrency(summary.totalFees),    icon: TrendingUp,   cls: 'gradient-primary' },
            { label: 'رسوم معلقة',    val: formatCurrency(summary.pendingFees),  icon: AlertCircle,  cls: 'gradient-gold' },
            { label: 'رواتب مدفوعة',  val: formatCurrency(summary.totalSalaries),icon: GraduationCap,cls: 'bg-[hsl(222,42%,28%)]' },
            { label: 'مصروفات',       val: formatCurrency(summary.totalExpenses), icon: TrendingDown, cls: 'bg-[hsl(0,60%,45%)]' },
          ].map(s => (
            <div key={s.label} className={`rounded-2xl p-4 text-white ${s.cls} shadow-sm`}>
              <s.icon className="w-5 h-5 mb-2 opacity-80" />
              <p className="text-sm font-black leading-tight" dir="ltr">{s.val}</p>
              <p className="text-white/75 text-xs mt-1">{s.label}</p>
            </div>
          ))}
        </div>

        {/* Net balance */}
        <div className={`rounded-2xl p-5 flex items-center justify-between ${summary.net >= 0 ? 'bg-emerald-50 border-2 border-emerald-200' : 'bg-red-50 border-2 border-red-200'}`}>
          <div className="flex items-center gap-3">
            <div className={`w-12 h-12 rounded-xl flex items-center justify-center ${summary.net >= 0 ? 'bg-emerald-500' : 'bg-red-500'}`}>
              <Landmark className="w-6 h-6 text-white" />
            </div>
            <div>
              <p className={`font-black text-lg ${summary.net >= 0 ? 'text-emerald-700' : 'text-red-700'}`} dir="ltr">
                {formatCurrency(Math.abs(summary.net))}
              </p>
              <p className={`text-sm ${summary.net >= 0 ? 'text-emerald-600' : 'text-red-600'}`}>
                {summary.net >= 0 ? 'صافي الربح المالي للمركز' : 'عجز في الميزانية المالية'}
              </p>
            </div>
          </div>
        </div>

        {/* Tabs */}
        <div className="flex gap-2 p-1 bg-[hsl(var(--muted))] rounded-2xl">
          {([
            { id: 'fees', label: 'رسوم الطلاب', icon: Users },
            { id: 'salaries', label: 'رواتب المحفظين', icon: GraduationCap },
            { id: 'expenses', label: 'المصروفات', icon: Receipt },
          ] as const).map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              className={`flex-1 flex items-center justify-center gap-2 py-2.5 rounded-xl text-sm font-bold transition-all ${
                tab === t.id ? 'bg-white text-[hsl(var(--primary))] shadow-sm' : 'text-[hsl(var(--muted-foreground))]'}`}>
              <t.icon className="w-4 h-4" />
              <span className="hidden sm:inline">{t.label}</span>
            </button>
          ))}
        </div>

        {/* ===== FEES ===== */}
        {tab === 'fees' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2"><Users className="w-4 h-4 text-[hsl(var(--primary))]" />رسوم الطلاب</h3>
              <button onClick={() => setShowFeeForm(true)} className="gradient-primary text-white font-bold px-4 py-2 rounded-xl flex items-center gap-1 text-sm hover:opacity-90">
                <Plus className="w-4 h-4" />إضافة رسوم
              </button>
            </div>
            {showFeeForm && (
              <div className="bg-[hsl(var(--accent))] rounded-2xl p-4 border-2 border-[hsl(var(--primary))/20] space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="text-sm font-semibold block mb-1">الطالب *</label>
                    <select value={feeForm.student_id} onChange={e => setFeeForm({...feeForm, student_id: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">اختر الطالب</option>
                      {students.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">المبلغ *</label>
                    <input type="number" placeholder="0" dir="ltr" value={feeForm.amount} onChange={e => setFeeForm({...feeForm, amount: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">نوع الرسوم</label>
                    <select value={feeForm.fee_type} onChange={e => setFeeForm({...feeForm, fee_type: e.target.value as any})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="monthly">شهري</option>
                      <option value="annual">سنوي</option>
                      <option value="registration">تسجيل</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">تاريخ الاستحقاق</label>
                    <input type="date" value={feeForm.due_date} onChange={e => setFeeForm({...feeForm, due_date: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">ملاحظات</label>
                    <input placeholder="اختياري" value={feeForm.notes} onChange={e => setFeeForm({...feeForm, notes: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={handleAddFee} disabled={submitting}
                    className="flex-1 gradient-primary text-white font-bold py-2.5 rounded-xl text-sm hover:opacity-90 disabled:opacity-60">
                    {submitting ? 'جاري الحفظ...' : 'إضافة الرسوم'}
                  </button>
                  <button onClick={() => setShowFeeForm(false)} className="px-4 py-2.5 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {fees.length === 0 ? (
                <div className="text-center py-10 text-[hsl(var(--muted-foreground))]"><DollarSign className="w-12 h-12 mx-auto mb-2 opacity-30" /><p>لا توجد رسوم مسجَّلة</p></div>
              ) : fees.map(fee => (
                <div key={fee.id} className="bg-white rounded-2xl p-4 border border-[hsl(var(--border))] flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 gradient-primary rounded-xl flex items-center justify-center text-white font-black text-sm">
                      {(fee.student_name || 'ط').charAt(0)}
                    </div>
                    <div>
                      <p className="font-bold text-sm text-[hsl(var(--foreground))]">{fee.student_name || 'طالب'}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">{feeTypeLabels[fee.fee_type]} · {fee.due_date}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <p className="font-black text-[hsl(var(--foreground))]" dir="ltr">{formatCurrency(fee.amount)}</p>
                    <span className={`text-xs font-bold px-2.5 py-1 rounded-full ${feeStatusLabels[fee.status]?.cls}`}>
                      {feeStatusLabels[fee.status]?.text}
                    </span>
                    {fee.status === 'pending' && (
                      <button onClick={() => handlePayFee(fee.id)}
                        className="p-1.5 rounded-lg gradient-primary text-white hover:opacity-80 transition-all" title="تسجيل الدفع">
                        <CheckCircle2 className="w-4 h-4" />
                      </button>
                    )}
                    {fee.status === 'paid' && (
                      <button
                        onClick={() => handleTriggerPrint({
                          type: 'fee',
                          title: `رسوم دراسية (${feeTypeLabels[fee.fee_type]})`,
                          targetName: fee.student_name || 'طالب معتمد',
                          amount: fee.amount,
                          date: fee.due_date,
                          notes: fee.notes,
                          refId: fee.id,
                        })}
                        className="p-1.5 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                        title="طباعة إيصال الرسوم"
                      >
                        <Printer className="w-4 h-4" />
                      </button>
                    )}
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== SALARIES ===== */}
        {tab === 'salaries' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2"><GraduationCap className="w-4 h-4 text-[hsl(var(--primary))]" />رواتب المحفظين</h3>
              <button onClick={() => setShowSalaryForm(true)} className="gradient-primary text-white font-bold px-4 py-2 rounded-xl flex items-center gap-1 text-sm hover:opacity-90">
                <Plus className="w-4 h-4" />صرف راتب
              </button>
            </div>
            {showSalaryForm && (
              <div className="bg-[hsl(var(--accent))] rounded-2xl p-4 border-2 border-[hsl(var(--primary))/20] space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="text-sm font-semibold block mb-1">المحفظ *</label>
                    <select value={salaryForm.teacher_id} onChange={e => setSalaryForm({...salaryForm, teacher_id: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">اختر المحفظ</option>
                      {teachers.map(t => <option key={t.id} value={t.id}>{(t as any).name}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">المبلغ *</label>
                    <input type="number" placeholder="0" dir="ltr" value={salaryForm.amount} onChange={e => setSalaryForm({...salaryForm, amount: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">الشهر</label>
                    <input type="month" value={salaryForm.month} onChange={e => setSalaryForm({...salaryForm, month: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div className="col-span-2">
                    <label className="text-sm font-semibold block mb-1">ملاحظات</label>
                    <input placeholder="اختياري" value={salaryForm.notes} onChange={e => setSalaryForm({...salaryForm, notes: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={handleAddSalary} disabled={submitting}
                    className="flex-1 gradient-primary text-white font-bold py-2.5 rounded-xl text-sm hover:opacity-90 disabled:opacity-60">
                    {submitting ? 'جاري الحفظ...' : 'صرف الراتب'}
                  </button>
                  <button onClick={() => setShowSalaryForm(false)} className="px-4 py-2.5 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {salaries.length === 0 ? (
                <div className="text-center py-10 text-[hsl(var(--muted-foreground))]"><GraduationCap className="w-12 h-12 mx-auto mb-2 opacity-30" /><p>لا توجد رواتب مسجَّلة</p></div>
              ) : salaries.map(sal => (
                <div key={sal.id} className="bg-white rounded-2xl p-4 border border-[hsl(var(--border))] flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 gradient-gold rounded-xl flex items-center justify-center text-white font-black text-sm">
                      {(sal.teacher_name || 'م').charAt(0)}
                    </div>
                    <div>
                      <p className="font-bold text-sm text-[hsl(var(--foreground))]">{sal.teacher_name || 'محفظ'}</p>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">شهر: {sal.month}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-3">
                    <div className="text-left">
                      <p className="font-black text-[hsl(var(--foreground))]" dir="ltr">{formatCurrency(sal.amount)}</p>
                      <span className="text-[10px] font-bold px-2 py-0.5 rounded-full bg-emerald-100 text-emerald-700">مدفوع</span>
                    </div>
                    <button
                      onClick={() => handleTriggerPrint({
                        type: 'salary',
                        title: 'مسير رواتب موظفين ومحفظين',
                        targetName: sal.teacher_name || 'محفظ معتمد',
                        amount: sal.amount,
                        date: sal.month,
                        notes: sal.notes,
                        refId: sal.id,
                      })}
                      className="p-1.5 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                      title="طباعة سند صرف الراتب"
                    >
                      <Printer className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ===== EXPENSES ===== */}
        {tab === 'expenses' && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-black text-[hsl(var(--foreground))] flex items-center gap-2"><Receipt className="w-4 h-4 text-[hsl(var(--primary))]" />مصروفات المركز</h3>
              <button onClick={() => setShowExpenseForm(true)} className="gradient-primary text-white font-bold px-4 py-2 rounded-xl flex items-center gap-1 text-sm hover:opacity-90">
                <Plus className="w-4 h-4" />إضافة مصروف
              </button>
            </div>
            {showExpenseForm && (
              <div className="bg-[hsl(var(--accent))] rounded-2xl p-4 border-2 border-[hsl(var(--primary))/20] space-y-3">
                <div className="grid grid-cols-2 gap-3">
                  <div className="col-span-2">
                    <label className="text-sm font-semibold block mb-1">عنوان المصروف *</label>
                    <input placeholder="مثال: إيجار القاعة" value={expenseForm.title} onChange={e => setExpenseForm({...expenseForm, title: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">المبلغ *</label>
                    <input type="number" placeholder="0" dir="ltr" value={expenseForm.amount} onChange={e => setExpenseForm({...expenseForm, amount: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">التصنيف</label>
                    <select value={expenseForm.category} onChange={e => setExpenseForm({...expenseForm, category: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm">
                      <option value="">اختر التصنيف</option>
                      {expenseCategories.map(c => <option key={c} value={c}>{c}</option>)}
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">التاريخ</label>
                    <input type="date" value={expenseForm.date} onChange={e => setExpenseForm({...expenseForm, date: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                  <div>
                    <label className="text-sm font-semibold block mb-1">ملاحظات</label>
                    <input placeholder="اختياري" value={expenseForm.notes} onChange={e => setExpenseForm({...expenseForm, notes: e.target.value})}
                      className="w-full h-10 px-3 rounded-xl border-2 border-[hsl(var(--border))] bg-white focus:outline-none focus:border-[hsl(var(--primary))] text-sm" />
                  </div>
                </div>
                <div className="flex gap-2">
                  <button onClick={handleAddExpense} disabled={submitting}
                    className="flex-1 gradient-primary text-white font-bold py-2.5 rounded-xl text-sm hover:opacity-90 disabled:opacity-60">
                    {submitting ? 'جاري الحفظ...' : 'إضافة المصروف'}
                  </button>
                  <button onClick={() => setShowExpenseForm(false)} className="px-4 py-2.5 rounded-xl border-2 border-[hsl(var(--border))] text-sm font-semibold">إلغاء</button>
                </div>
              </div>
            )}
            <div className="space-y-2">
              {expenses.length === 0 ? (
                <div className="text-center py-10 text-[hsl(var(--muted-foreground))]"><Receipt className="w-12 h-12 mx-auto mb-2 opacity-30" /><p>لا توجد مصروفات مسجَّلة</p></div>
              ) : expenses.map(exp => (
                <div key={exp.id} className="bg-white rounded-2xl p-4 border border-[hsl(var(--border))] flex items-center justify-between gap-4">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-red-100 rounded-xl flex items-center justify-center">
                      <TrendingDown className="w-5 h-5 text-red-500" />
                    </div>
                    <div>
                      <p className="font-bold text-sm text-[hsl(var(--foreground))]">{exp.title}</p>
                      <div className="flex gap-2 text-xs text-[hsl(var(--muted-foreground))]">
                        {exp.category && <span className="bg-[hsl(var(--muted))] px-1.5 py-0.5 rounded">{exp.category}</span>}
                        <span className="flex items-center gap-0.5"><Calendar className="w-3 h-3" />{exp.date}</span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-1.5">
                    <p className="font-black text-red-600" dir="ltr">{formatCurrency(exp.amount)}</p>
                    <button
                      onClick={() => handleTriggerPrint({
                        type: 'expense',
                        title: `فاتورة مصروفات (${exp.category || 'متنوع'})`,
                        targetName: exp.title,
                        amount: exp.amount,
                        date: exp.date,
                        notes: exp.notes,
                        refId: exp.id,
                      })}
                      className="p-1.5 rounded-lg bg-blue-50 text-blue-600 border border-blue-200 hover:bg-blue-100 transition-all"
                      title="طباعة الفاتورة"
                    >
                      <Printer className="w-4 h-4" />
                    </button>
                    <button onClick={() => handleDeleteExpense(exp.id)} className="p-1.5 rounded-lg text-red-400 hover:bg-red-50 transition-all">
                      <Trash2 className="w-4 h-4" />
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}
      </div>

    </div>
  );
}
