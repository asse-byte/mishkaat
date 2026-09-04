import React, { useState, useEffect, useCallback } from 'react';
import { useParams, Link } from 'react-router-dom';
import { Loader2, ArrowRight, User, Award, CheckCircle, Calculator, BrainCircuit } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar } from 'recharts';
import api from '@/services/api';

interface AnalyticsData {
  student: {
    name: string;
    halaqah_name: string;
  };
  timeline: {
    date: string;
    recitation_score: number | null;
    attendance_score: number | null;
    mistakes: number | null;
  }[];
}

export default function StudentAnalytics() {
  const { studentId } = useParams();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get(`/analytics/student/${studentId}`);
      setData(res.data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, [studentId]);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 text-[hsl(var(--primary))] animate-spin" />
    </div>
  );

  if (!data || !data.student) return (
    <div className="text-center py-10">
      <p className="text-slate-500">الطالب غير موجود.</p>
    </div>
  );

  const { student, timeline } = data;
  
  // Calculate specific averages
  const totalScores = timeline.reduce((acc, t) => acc + (t.recitation_score || 0), 0);
  const totalMistakes = timeline.reduce((acc, t) => acc + (t.mistakes || 0), 0);
  const validRecitationCount = timeline.filter((t) => t.recitation_score !== null).length;
  
  const avgScore = validRecitationCount > 0 ? totalScores / validRecitationCount : 0;
  const avgMistakes = validRecitationCount > 0 ? totalMistakes / validRecitationCount : 0;

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="flex items-center justify-between">
        <Link to="/students" className="text-slate-500 hover:text-slate-800 flex items-center gap-1 font-bold text-sm">
          <ArrowRight className="w-4 h-4" /> العودة لقائمة الطلاب
        </Link>
      </div>

      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-2 flex flex-col md:flex-row items-center gap-6">
        <div className="w-20 h-20 bg-white/20 rounded-full flex items-center justify-center backdrop-blur-sm border-2 border-white/40">
           <User className="w-10 h-10 text-white" />
        </div>
        <div className="text-center md:text-right">
          <h1 className="text-3xl font-bold mb-1">{student.name}</h1>
          <p className="text-[hsl(var(--ink-3))] font-medium">{student.halaqah_name}</p>
        </div>
        <div className="mr-auto hidden md:block opacity-20">
            <BrainCircuit className="w-32 h-32" />
        </div>
      </div>

      <div className="grid md:grid-cols-3 gap-4">
          <div className="card p-5 flex items-center gap-4">
              <div className="w-12 h-12 bg-emerald-100 rounded-full flex items-center justify-center">
                  <Award className="w-6 h-6 text-emerald-600" />
              </div>
              <div>
                  <p className="text-slate-500 text-sm font-bold">متوسط التقييم العام</p>
                  <p className="text-2xl font-bold text-emerald-600">{avgScore.toFixed(1)}%</p>
              </div>
          </div>
          <div className="card p-5 flex items-center gap-4">
              <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center">
                  <CheckCircle className="w-6 h-6 text-blue-600" />
              </div>
              <div>
                  <p className="text-slate-500 text-sm font-bold">إجمالي التسميعات (6 شهور)</p>
                  <p className="text-2xl font-bold text-blue-600">{validRecitationCount}</p>
              </div>
          </div>
          <div className="card p-5 flex items-center gap-4">
              <div className="w-12 h-12 bg-red-100 rounded-full flex items-center justify-center">
                  <Calculator className="w-6 h-6 text-red-600" />
              </div>
              <div>
                  <p className="text-slate-500 text-sm font-bold">متوسط الأخطاء لكل تسميع</p>
                  <p className="text-2xl font-bold text-red-600">{avgMistakes.toFixed(1)}</p>
              </div>
          </div>
      </div>

      <div className="card p-6">
        <h3 className="font-bold text-slate-800 mb-6 flex items-center gap-2">
            <BrainCircuit className="w-5 h-5 text-slate-500" /> منحنى تحليل الأداء الشامل
        </h3>
        
        {timeline.length === 0 ? (
            <p className="text-center text-slate-500 py-10">لا توجد بيانات متاحة لهذا الطالب في آخر 6 أشهر.</p>
        ) : (
            <div className="h-80 w-full" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={timeline} margin={{ top: 5, right: 30, left: 20, bottom: 5 }}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.5} />
                <XAxis dataKey="date" />
                <YAxis domain={[0, 100]} />
                <Tooltip />
                <Legend />
                <Line type="monotone" dataKey="recitation_score" name="تقييم التسميع" stroke="#0ea5e9" strokeWidth={3} activeDot={{ r: 8 }} />
                <Line type="monotone" dataKey="attendance_score" name="تقييم الحضور" stroke="#10b981" strokeWidth={3} />
                </LineChart>
            </ResponsiveContainer>
            </div>
        )}
      </div>
      
      {/* mistakes chart */}
      {timeline.length > 0 && (
      <div className="card p-6">
        <h3 className="font-bold text-slate-800 mb-6 text-center">معدل الأخطاء في التسميع عبر الزمن</h3>
        <div className="h-64 w-full" dir="ltr">
            <ResponsiveContainer width="100%" height="100%">
                <BarChart data={timeline}>
                <CartesianGrid strokeDasharray="3 3" opacity={0.3} />
                <XAxis dataKey="date" />
                <YAxis />
                <Tooltip />
                <Legend />
                <Bar dataKey="mistakes" name="عدد الأخطاء" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
            </ResponsiveContainer>
        </div>
      </div>
      )}
    </div>
  );
}
