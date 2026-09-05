import React, { useState, useEffect, useCallback } from 'react';
import { Trophy, Loader2, Activity } from 'lucide-react';
import api from '@/services/api';

import { Link } from 'react-router-dom';
import PageHeader from '@/components/ui/PageHeader';

interface RankingStudent {
  id: string;
  name: string;
  halaqah_name: string;
  score: number;
  progress: number;
  category: 'best' | 'weak' | 'average';
}

export default function Rankings() {

  const [rankings, setRankings] = useState<RankingStudent[]>([]);
  const [loading, setLoading] = useState(true);

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const res = await api.get('/analytics/rankings');
      setRankings(res.data);
    } catch { /* */ } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  if (loading) return (
    <div className="flex items-center justify-center h-64">
      <Loader2 className="w-8 h-8 text-[hsl(var(--primary))] animate-spin" />
    </div>
  );

  const bestStudents = rankings.filter(r => r.category === 'best');
  const weakStudents = rankings.filter(r => r.category === 'weak');
  const avgStudents = rankings.filter(r => r.category === 'average');

  return (
    <div className="space-y-6 animate-fade-in">
      <PageHeader
        title="نظام الترتيب الذكي"
        subtitle="تقييم الطلاب بناءً على معادلة رياضية ذكية للحضور والتسميع والمراجعة"
      />

      <div className="grid md:grid-cols-2 gap-6">
        {/* Best Students */}
        <div className="card p-5">
          <h3 className="font-bold text-emerald-700 mb-4 flex items-center gap-2">
            <Trophy className="w-5 h-5" /> أفضل الطلاب (85% فما فوق)
          </h3>
          <div className="space-y-3">
            {bestStudents.length === 0 ? <p className="text-sm text-slate-500">لا يوجد طلاب في هذه الفئة حالياً.</p> : null}
            {bestStudents.map((s, idx) => (
              <div key={s.id} className="flex justify-between items-center p-3 rounded-[var(--radius)] bg-emerald-50 border border-emerald-100">
                <div className="flex gap-3 items-center">
                  <div className="w-8 h-8 rounded-full bg-emerald-200 text-emerald-800 font-bold flex items-center justify-center text-sm">{idx + 1}</div>
                  <div>
                    <p className="font-bold text-slate-800">{s.name}</p>
                    <p className="text-xs text-emerald-600">{s.halaqah_name}</p>
                  </div>
                </div>
                <div className="text-left">
                  <p className="font-bold text-emerald-600 text-lg">{s.score}%</p>
                  <Link to={`/analytics/${s.id}`} className="text-[10px] text-emerald-700 bg-emerald-200 px-2 py-1 rounded-full hover:bg-emerald-300">تحليل الأداء</Link>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Weak Students */}
        <div className="card p-5">
          <h3 className="font-bold text-red-600 mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5" /> الطلاب الضعفاء (أقل من 65%)
          </h3>
          <div className="space-y-3">
            {weakStudents.length === 0 ? <p className="text-sm text-slate-500">لا يوجد طلاب في هذه الفئة حالياً.</p> : null}
            {weakStudents.map((s, idx) => (
              <div key={s.id} className="flex justify-between items-center p-3 rounded-[var(--radius)] bg-red-50 border border-red-100">
                <div className="flex gap-3 items-center">
                  <div className="w-8 h-8 rounded-full bg-red-200 text-red-800 font-bold flex items-center justify-center text-sm">{idx + 1}</div>
                  <div>
                    <p className="font-bold text-slate-800">{s.name}</p>
                    <p className="text-xs text-red-500">{s.halaqah_name}</p>
                  </div>
                </div>
                <div className="text-left">
                  <p className="font-bold text-red-600 text-lg">{s.score}%</p>
                  <Link to={`/analytics/${s.id}`} className="text-[10px] text-red-700 bg-red-200 px-2 py-1 rounded-full hover:bg-red-300">تحليل الأداء</Link>
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Average Students */}
      {avgStudents.length > 0 && (
      <div className="card p-5 mt-6">
          <h3 className="font-bold text-slate-700 mb-4">بقية الطلاب</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-sm text-right">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-4 py-3 rounded-r-xl font-bold">اسم الطالب</th>
                  <th className="px-4 py-3 font-bold">الحلقة</th>
                  <th className="px-4 py-3 font-bold text-center">التقييم الذكي</th>
                  <th className="px-4 py-3 rounded-l-xl font-bold text-center">الإجراءات</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {avgStudents.map(s => (
                  <tr key={s.id} className="hover:bg-slate-50/50">
                    <td className="px-4 py-3 font-bold text-slate-800">{s.name}</td>
                    <td className="px-4 py-3 text-slate-500">{s.halaqah_name}</td>
                    <td className="px-4 py-3 text-center font-bold text-slate-700">{s.score}%</td>
                    <td className="px-4 py-3 text-center">
                        <Link to={`/analytics/${s.id}`} className="text-xs text-blue-600 font-bold hover:underline">عرض التحليل</Link>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
      </div>
      )}
    </div>
  );
}
