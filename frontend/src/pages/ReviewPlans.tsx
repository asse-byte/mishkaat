import React, { useState, useEffect } from 'react';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Avatar, AvatarFallback } from '@/components/ui/avatar';
import { LoadingSpinner } from '@/components/ui/loading';
import { useAuth } from '@/contexts/AuthContext';
import {
  RefreshCw,
  Search,
  Calendar,
  BookOpen,
  CheckCircle2,
  Clock,
  Target,
  TrendingUp,
  Star,
  AlertCircle,
  Plus,
  X,
  Users,
} from 'lucide-react';
import { studentsApi, recitationsApi } from '@/services/api';

interface ReviewStudent {
  id: string;
  name: string;
  halaqah_name?: string;
  enrollment_date: string;
  progress: number;
  phone?: string;
  parent_name?: string;
}

interface RecitationData {
  id: string;
  student_id: string;
  surah_name: string;
  start_ayah: number;
  end_ayah: number;
  evaluation: string;
  mistakes_count: number;
  date: string;
  recitation_type: string;
}

const evaluationLabels: Record<string, { text: string; color: string; bgColor: string }> = {
  excellent: { text: 'ممتاز', color: 'text-green-600', bgColor: 'bg-green-100' },
  good: { text: 'جيد', color: 'text-blue-600', bgColor: 'bg-blue-100' },
  acceptable: { text: 'مقبول', color: 'text-amber-600', bgColor: 'bg-amber-100' },
  needs_improvement: { text: 'يحتاج تحسين', color: 'text-red-600', bgColor: 'bg-red-100' },
};

// خطة المراجعة: 5 أجزاء يومياً × 6 أيام = 30 جزء = ختمة كاملة في أسبوع
// 8 دورات سنوياً = مراجعة القرآن 8 مرات في السنة
const REVIEW_PLAN = {
  juzPerDay: 5,
  daysPerCycle: 6,
  restDaysPerWeek: 1,
  cyclesPerYear: 8,
  weeklySchedule: [
    { day: 'السبت', juzRange: '1 - 5', juzList: [1, 2, 3, 4, 5] },
    { day: 'الأحد', juzRange: '6 - 10', juzList: [6, 7, 8, 9, 10] },
    { day: 'الاثنين', juzRange: '11 - 15', juzList: [11, 12, 13, 14, 15] },
    { day: 'الثلاثاء', juzRange: '16 - 20', juzList: [16, 17, 18, 19, 20] },
    { day: 'الأربعاء', juzRange: '21 - 25', juzList: [21, 22, 23, 24, 25] },
    { day: 'الخميس', juzRange: '26 - 30', juzList: [26, 27, 28, 29, 30] },
  ],
};

export default function ReviewPlans() {
  const { user } = useAuth();
  const [searchTerm, setSearchTerm] = useState('');
  const [selectedStudent, setSelectedStudent] = useState<string | null>(null);
  const [reviewStudents, setReviewStudents] = useState<ReviewStudent[]>([]);
  const [studentRecitations, setStudentRecitations] = useState<RecitationData[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingRecitations, setLoadingRecitations] = useState(false);
  const [showRecordForm, setShowRecordForm] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  // Record review form
  const [reviewForm, setReviewForm] = useState({
    juz_start: '', juz_end: '', evaluation: 'excellent', mistakes: '0', notes: '',
  });

  useEffect(() => {
    const loadStudents = async () => {
      try {
        setLoading(true);
        const allStudents = await studentsApi.getAll() as any[];
        const reviewing = allStudents.filter(s => s.student_type === 'reviewing' || s.memorization_plan === 'plan_review');
        setReviewStudents(reviewing);
      } catch (err) {
        console.error('Error loading review students:', err);
      } finally {
        setLoading(false);
      }
    };
    loadStudents();
  }, []);

  useEffect(() => {
    if (!selectedStudent) return;
    const loadRecitations = async () => {
      try {
        setLoadingRecitations(true);
        const data = await recitationsApi.getByStudent(selectedStudent) as RecitationData[];
        setStudentRecitations(data.filter(r => r.recitation_type === 'review'));
      } catch (err) {
        console.error('Error loading recitations:', err);
      } finally {
        setLoadingRecitations(false);
      }
    };
    loadRecitations();
  }, [selectedStudent]);

  const handleRecordReview = async () => {
    if (!selectedStudent) return;
    const student = reviewStudents.find(s => s.id === selectedStudent);
    try {
      setSubmitting(true);
      await recitationsApi.create({
        student_id: selectedStudent,
        student_name: student?.name,
        teacher_id: user?.id || '',
        teacher_name: user?.name || '',
        surah_name: `الأجزاء ${reviewForm.juz_start}-${reviewForm.juz_end}`,
        start_ayah: parseInt(reviewForm.juz_start) || 1,
        end_ayah: parseInt(reviewForm.juz_end) || 5,
        evaluation: reviewForm.evaluation,
        mistakes_count: parseInt(reviewForm.mistakes) || 0,
        notes: reviewForm.notes || undefined,
        recitation_type: 'review',
      } as any);
      setShowRecordForm(false);
      setReviewForm({ juz_start: '', juz_end: '', evaluation: 'excellent', mistakes: '0', notes: '' });
      // Reload recitations
      const data = await recitationsApi.getByStudent(selectedStudent) as RecitationData[];
      setStudentRecitations(data.filter(r => r.recitation_type === 'review'));
    } catch (err) {
      console.error('Error recording review:', err);
    } finally {
      setSubmitting(false);
    }
  };

  const filteredStudents = reviewStudents.filter(
    (student) => student.name.includes(searchTerm)
  );

  const selectedStudentData = selectedStudent
    ? reviewStudents.find(s => s.id === selectedStudent)
    : null;

  // Calculate how many review cycles completed based on recitations
  const completedReviews = studentRecitations.length;
  const cyclesCompleted = Math.floor(completedReviews / 6); // 6 days per cycle

  if (loading) {
    return <div className="flex items-center justify-center h-64"><LoadingSpinner size="lg" /></div>;
  }

  return (
    <div className="space-y-6 animate-fade-in">
      {/* Header */}
      <div className="relative overflow-hidden rounded-3xl gradient-primary p-6 text-white shadow-lg">
        <div className="absolute top-[-30px] left-[-30px] w-40 h-40 rounded-full bg-white/5" />
        <div className="relative z-10 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-black mb-1">خطط المراجعة والتثبيت</h1>
            <p className="text-white/70 text-sm">إدارة ومتابعة طلاب مراجعة القرآن الكريم</p>
          </div>
          <div className="w-14 h-14 bg-white/15 rounded-2xl flex items-center justify-center animate-float">
            <RefreshCw className="w-7 h-7 text-white" />
          </div>
        </div>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-4 gap-3 stagger">
        {[
          { icon: Users,     val: reviewStudents.length,      label: 'طالب مراجعة',     cls: 'gradient-primary' },
          { icon: Target,    val: REVIEW_PLAN.daysPerCycle,   label: 'أيام للدورة',      cls: 'gradient-gold' },
          { icon: BookOpen,  val: REVIEW_PLAN.juzPerDay,      label: 'أجزاء يومياً',     cls: 'stat-card-teal' },
          { icon: Star,      val: REVIEW_PLAN.cyclesPerYear,  label: 'دورات سنوياً',     cls: 'bg-[hsl(152,45%,38%)]' },
        ].map(s => (
          <div key={s.label} className={`rounded-2xl p-4 text-white shadow-sm ${s.cls}`}>
            <s.icon className="w-5 h-5 mb-2 opacity-80" />
            <p className="text-2xl font-black">{s.val}</p>
            <p className="text-white/75 text-xs mt-0.5">{s.label}</p>
          </div>
        ))}
      </div>

      {/* Search */}
      <div className="relative">
        <Search className="absolute right-3 top-3 h-5 w-5 text-[hsl(var(--muted-foreground))]" />
        <Input
          placeholder="البحث عن طالب مراجعة..."
          value={searchTerm}
          onChange={(e) => setSearchTerm(e.target.value)}
          className="pr-10"
        />
      </div>

      {/* Review Plan Methodology */}
      <Card className="bg-gradient-to-l from-green-50 to-emerald-50 border-green-200">
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-green-700">
            <BookOpen className="w-5 h-5" />
            منهجية المراجعة والتثبيت
          </CardTitle>
          <CardDescription className="text-green-600">
            خطة منظمة لمراجعة القرآن الكريم كاملاً بشكل دوري
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid md:grid-cols-4 gap-4 mb-6">
            <div className="text-center p-4 bg-white rounded-lg shadow-sm">
              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-2 text-white font-bold">1</div>
              <h4 className="font-semibold text-sm">المراجعة اليومية</h4>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">5 أجزاء يومياً بتدبر وإتقان</p>
            </div>
            <div className="text-center p-4 bg-white rounded-lg shadow-sm">
              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-2 text-white font-bold">2</div>
              <h4 className="font-semibold text-sm">الختمة الأسبوعية</h4>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">ختمة كاملة كل 6 أيام + يوم راحة</p>
            </div>
            <div className="text-center p-4 bg-white rounded-lg shadow-sm">
              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-2 text-white font-bold">3</div>
              <h4 className="font-semibold text-sm">التسميع اليومي</h4>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">تسميع على المحفظ لضمان الإتقان</p>
            </div>
            <div className="text-center p-4 bg-white rounded-lg shadow-sm">
              <div className="w-10 h-10 bg-green-500 rounded-full flex items-center justify-center mx-auto mb-2 text-white font-bold">4</div>
              <h4 className="font-semibold text-sm">التقييم الدوري</h4>
              <p className="text-xs text-[hsl(var(--muted-foreground))] mt-1">8 دورات مراجعة سنوياً</p>
            </div>
          </div>

          {/* Weekly Schedule Table */}
          <div className="bg-white rounded-lg p-4">
            <h4 className="font-semibold mb-3 text-green-700">الجدول الأسبوعي للمراجعة</h4>
            <div className="grid grid-cols-6 gap-2">
              {REVIEW_PLAN.weeklySchedule.map((day) => (
                <div key={day.day} className="text-center p-3 rounded-lg bg-green-50 border border-green-200">
                  <p className="font-semibold text-green-700 text-sm">{day.day}</p>
                  <p className="text-lg font-bold text-green-600 mt-1">{day.juzRange}</p>
                  <p className="text-xs text-[hsl(var(--muted-foreground))]">5 أجزاء</p>
                </div>
              ))}
            </div>
            <div className="mt-3 p-3 rounded-lg bg-amber-50 border border-amber-200 text-center">
              <p className="text-sm text-amber-700">
                <strong>يوم الجمعة:</strong> راحة ومراجعة حرة
              </p>
            </div>
          </div>
        </CardContent>
      </Card>

      {reviewStudents.length === 0 ? (
        <Card>
          <CardContent className="py-12 text-center">
            <RefreshCw className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-50" />
            <h3 className="text-lg font-semibold mb-2">لا يوجد طلاب مراجعة حالياً</h3>
            <p className="text-[hsl(var(--muted-foreground))]">
              لتسجيل طالب مراجعة، اذهب لصفحة الطلاب واختر "طالب مراجعة وتثبيت" عند التسجيل
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid lg:grid-cols-2 gap-6">
          {/* Students List */}
          <div className="space-y-4">
            <h3 className="font-semibold text-lg">طلاب المراجعة ({filteredStudents.length})</h3>
            {filteredStudents.map((student) => (
              <Card
                key={student.id}
                className={`cursor-pointer transition-all ${
                  selectedStudent === student.id
                    ? 'ring-2 ring-green-500 shadow-lg'
                    : 'hover:shadow-md'
                }`}
                onClick={() => setSelectedStudent(student.id)}
              >
                <CardContent className="p-4">
                  <div className="flex items-center gap-4">
                    <Avatar className="w-14 h-14 bg-green-500">
                      <AvatarFallback className="text-white text-lg">
                        {student.name.charAt(0)}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex-1">
                      <div className="flex items-center gap-2 flex-wrap">
                        <h3 className="font-bold">{student.name}</h3>
                        <span className="text-xs px-2 py-1 rounded-full bg-green-100 text-green-700">
                          مراجعة وتثبيت
                        </span>
                      </div>
                      {student.halaqah_name && (
                        <p className="text-sm text-[hsl(var(--muted-foreground))]">
                          {student.halaqah_name}
                        </p>
                      )}
                    </div>
                    <div className="text-center">
                      <div className="text-2xl font-bold text-green-600">100%</div>
                      <p className="text-xs text-[hsl(var(--muted-foreground))]">حافظ للقرآن</p>
                    </div>
                  </div>
                </CardContent>
              </Card>
            ))}
          </div>

          {/* Selected Student Details */}
          <div>
            {selectedStudentData ? (
              <div className="space-y-4">
                <Card>
                  <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                      <Calendar className="w-5 h-5" />
                      جدول المراجعة - {selectedStudentData.name}
                    </CardTitle>
                    <CardDescription>
                      متابعة الدورات والمراجعات اليومية
                    </CardDescription>
                  </CardHeader>
                  <CardContent>
                    {/* Schedule */}
                    <div className="space-y-3">
                      {REVIEW_PLAN.weeklySchedule.map((day, index) => {
                        // Check if there's a recitation for this day range
                        const hasRecitation = studentRecitations.some(r => {
                          const startJuz = r.start_ayah;
                          return day.juzList.includes(startJuz);
                        });
                        
                        return (
                          <div
                            key={day.day}
                            className={`p-3 rounded-lg border ${
                              hasRecitation
                                ? 'bg-green-50 border-green-200'
                                : 'bg-[hsl(var(--muted))] border-[hsl(var(--border))]'
                            }`}
                          >
                            <div className="flex items-center justify-between">
                              <div className="flex items-center gap-3">
                                {hasRecitation ? (
                                  <CheckCircle2 className="w-5 h-5 text-green-500" />
                                ) : (
                                  <div className="w-5 h-5 rounded-full border-2 border-gray-300" />
                                )}
                                <span className="font-medium">{day.day}</span>
                              </div>
                              <div className="flex gap-1">
                                {day.juzList.map((j) => (
                                  <span
                                    key={j}
                                    className={`w-7 h-7 text-xs rounded flex items-center justify-center font-medium ${
                                      hasRecitation
                                        ? 'bg-green-500 text-white'
                                        : 'bg-gray-200 text-gray-600'
                                    }`}
                                  >
                                    {j}
                                  </span>
                                ))}
                              </div>
                            </div>
                          </div>
                        );
                      })}
                    </div>

                    {/* Record Review Button */}
                    <Button
                      className="w-full mt-4 gap-2"
                      onClick={() => setShowRecordForm(true)}
                    >
                      <Plus className="w-4 h-4" />
                      تسجيل مراجعة اليوم
                    </Button>
                  </CardContent>
                </Card>

                {/* Recent Reviews */}
                <Card>
                  <CardHeader>
                    <CardTitle className="text-base flex items-center gap-2">
                      <TrendingUp className="w-5 h-5" />
                      سجل المراجعات الأخيرة
                    </CardTitle>
                  </CardHeader>
                  <CardContent>
                    {loadingRecitations ? (
                      <div className="text-center py-4"><LoadingSpinner size="sm" /></div>
                    ) : studentRecitations.length === 0 ? (
                      <p className="text-center text-[hsl(var(--muted-foreground))] py-4">
                        لا توجد مراجعات مسجلة بعد
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {studentRecitations.slice(0, 10).map((rec) => (
                          <div key={rec.id} className="flex items-center justify-between p-2 rounded bg-[hsl(var(--muted))]">
                            <div className="flex items-center gap-2">
                              <CheckCircle2 className="w-4 h-4 text-green-500" />
                              <span className="text-sm font-medium">{rec.surah_name}</span>
                            </div>
                            <div className="flex items-center gap-3">
                              <span className={`text-xs px-2 py-1 rounded-full ${evaluationLabels[rec.evaluation]?.bgColor} ${evaluationLabels[rec.evaluation]?.color}`}>
                                {evaluationLabels[rec.evaluation]?.text}
                              </span>
                              <span className="text-xs text-[hsl(var(--muted-foreground))]">
                                {new Date(rec.date).toLocaleDateString('ar-SA')}
                              </span>
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </CardContent>
                </Card>
              </div>
            ) : (
              <Card className="h-full flex items-center justify-center">
                <CardContent className="text-center py-12">
                  <RefreshCw className="w-16 h-16 mx-auto mb-4 text-[hsl(var(--muted-foreground))] opacity-50" />
                  <p className="text-[hsl(var(--muted-foreground))]">
                    اختر طالباً لعرض جدول المراجعة والتسميع
                  </p>
                </CardContent>
              </Card>
            )}
          </div>
        </div>
      )}

      {/* Record Review Modal */}
      {showRecordForm && selectedStudentData && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <Card className="w-full max-w-lg">
            <CardHeader>
              <div className="flex items-center justify-between">
                <CardTitle>تسجيل مراجعة - {selectedStudentData.name}</CardTitle>
                <Button variant="ghost" size="icon" onClick={() => setShowRecordForm(false)}>
                  <X className="w-5 h-5" />
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 gap-4">
                <div className="space-y-2">
                  <Label>من جزء</Label>
                  <Input type="number" placeholder="1" min="1" max="30"
                    value={reviewForm.juz_start}
                    onChange={(e) => setReviewForm({...reviewForm, juz_start: e.target.value})} />
                </div>
                <div className="space-y-2">
                  <Label>إلى جزء</Label>
                  <Input type="number" placeholder="5" min="1" max="30"
                    value={reviewForm.juz_end}
                    onChange={(e) => setReviewForm({...reviewForm, juz_end: e.target.value})} />
                </div>
              </div>

              {/* Quick Selection */}
              <div className="space-y-2">
                <Label className="text-sm">اختيار سريع</Label>
                <div className="grid grid-cols-3 gap-2">
                  {REVIEW_PLAN.weeklySchedule.map((day) => (
                    <Button key={day.day} variant="outline" size="sm"
                      onClick={() => setReviewForm({
                        ...reviewForm,
                        juz_start: String(day.juzList[0]),
                        juz_end: String(day.juzList[day.juzList.length - 1]),
                      })}
                      className="text-xs"
                    >
                      {day.day} ({day.juzRange})
                    </Button>
                  ))}
                </div>
              </div>

              <div className="space-y-2">
                <Label>التقييم</Label>
                <select className="w-full h-11 px-3 rounded-lg border border-[hsl(var(--input))] bg-transparent"
                  value={reviewForm.evaluation}
                  onChange={(e) => setReviewForm({...reviewForm, evaluation: e.target.value})}>
                  <option value="excellent">ممتاز - حفظ متين</option>
                  <option value="good">جيد - أخطاء قليلة</option>
                  <option value="acceptable">مقبول - يحتاج مراجعة أكثر</option>
                  <option value="needs_improvement">يحتاج تحسين - أخطاء كثيرة</option>
                </select>
              </div>

              <div className="space-y-2">
                <Label>عدد الأخطاء</Label>
                <Input type="number" placeholder="0" value={reviewForm.mistakes}
                  onChange={(e) => setReviewForm({...reviewForm, mistakes: e.target.value})} />
              </div>

              <div className="space-y-2">
                <Label>ملاحظات المحفظ</Label>
                <textarea className="w-full h-20 px-3 py-2 rounded-lg border border-[hsl(var(--input))] bg-transparent resize-none"
                  placeholder="ملاحظات حول المراجعة..."
                  value={reviewForm.notes}
                  onChange={(e) => setReviewForm({...reviewForm, notes: e.target.value})} />
              </div>

              <div className="flex gap-3 pt-4">
                <Button className="flex-1" onClick={handleRecordReview} disabled={submitting}>
                  {submitting ? <LoadingSpinner size="sm" /> : <><CheckCircle2 className="w-4 h-4 ml-2" />حفظ المراجعة</>}
                </Button>
                <Button variant="outline" onClick={() => setShowRecordForm(false)}>إلغاء</Button>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

