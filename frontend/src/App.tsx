/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
import type { UserRole } from '@/types';
import { LoadingPage } from '@/components/ui/loading';
import Login from '@/pages/Login';
import Dashboard from '@/pages/Dashboard';
import Landing from '@/pages/Landing';
import Sponsorships from '@/pages/Sponsorships';
import RegisterCenter from '@/pages/RegisterCenter';
import Centers from '@/pages/Centers';
import Students from '@/pages/Students';
import Teachers from '@/pages/Teachers';
import Halaqat from '@/pages/Halaqat';
import Recitations from '@/pages/Recitations';
import Attendance from '@/pages/Attendance';
import Finance from '@/pages/Finance';
import ReviewPlans from '@/pages/ReviewPlans';
import ProfilePage from '@/pages/ProfilePage';
import SettingsPage from '@/pages/SettingsPage';
import NotificationsPage from '@/pages/NotificationsPage';
import AuditLogPage from '@/pages/AuditLogPage';
import Reports from '@/pages/Reports';
import Rankings from '@/pages/Rankings';
import StudentAnalytics from '@/pages/StudentAnalytics';
import StudentPerformance from '@/pages/StudentPerformance';
import Leaderboards from '@/pages/Leaderboards';
import AcademicSchedules from '@/pages/AcademicSchedules';
import Competitions from '@/pages/Competitions';
import Certificates from '@/pages/Certificates';
import BulkMessages from '@/pages/BulkMessages';
import { NotFoundPage, ForbiddenPage } from '@/pages/ErrorPages';
import DashboardLayout from '@/components/layout/DashboardLayout';

/**
 * [إصلاح 2026-09-03] حراسة المسارات بالأدوار.
 *
 * قبله: ProtectedRoute تفحص "هل سجّل الدخول؟" فقط. أي مستخدم — طالب أو وليّ أمر — يكتب
 * /finance أو /audit-logs في شريط العنوان فتُفتح له الصفحة. الخادم يمنع البيانات (403)،
 * لكن الصفحة تُرسم ثم تفشل نداءاتها، فيرى المستخدم شاشة مكسورة بدل رسالة واضحة.
 * وصفحة ForbiddenPage كانت موجودة في المشروع ولا يستدعيها أي حارس.
 *
 * قائمة الأدوار هنا تطابق ما يسمح به الخادم فعلاً، لا ما تعرضه القائمة الجانبية —
 * حتى لا نمنع مستخدماً كان الخادم سيخدمه.
 */
function ProtectedRoute({
  children,
  roles,
}: {
  children: React.ReactNode;
  roles?: UserRole[];
}) {
  const { isAuthenticated, isLoading, hasRole } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (roles && !hasRole(roles)) {
    return <DashboardLayout><ForbiddenPage /></DashboardLayout>;
  }

  return <DashboardLayout>{children}</DashboardLayout>;
}

// الأدوار المسموح لها فعلاً في الخادم بالنقاط التي تعتمد عليها كل صفحة
const MANAGEMENT: UserRole[] = ['admin', 'super_admin', 'center_manager'];
const FINANCE: UserRole[] = ['admin', 'center_manager'];            // /expenses و/salaries تمنع super_admin
const AUDIT: UserRole[] = ['admin', 'super_admin'];
const STAFF: UserRole[] = ['admin', 'super_admin', 'center_manager', 'teacher'];
const ATTENDANCE: UserRole[] = ['admin', 'center_manager', 'teacher'];
const PLANS: UserRole[] = ['admin', 'center_manager', 'teacher'];
// [قرار المالك 2026-09-10] الشهادات لا تخصّ المعلّم: يُصدرها المدير، ويراها
// الطالب ووليُّه ويطبعانها.
const CERTIFICATE_VIEWERS: UserRole[] = ['admin', 'super_admin', 'center_manager', 'student', 'parent'];
// [إصلاح 2026-09-07] الجدول الدراسي يقرؤه الجميع، كلٌّ في نطاقه. كان حارسه
// STAFF فيُردّ الطالبُ بـ403 من صفحةٍ يعرضها له الشريطُ الجانبي نفسه — والخادم
// يسمح له بها أصلاً: لا حارسَ دورٍ على القراءة في schedules.py، والنطاق محصورٌ
// بحلقته عبر visible_halaqah_ids. فكان المنعُ في الواجهة وحدها، بلا سبب.
const SCHEDULE_VIEWERS: UserRole[] = ['admin', 'super_admin', 'center_manager', 'teacher', 'student', 'parent'];

function PublicRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (isAuthenticated) {
    return <Navigate to="/dashboard" replace />;
  }

  return <>{children}</>;
}

function AppRoutes() {
  return (
    <Routes>
      <Route
        path="/login"
        element={
          <PublicRoute>
            <Login />
          </PublicRoute>
        }
      />
      <Route
        path="/dashboard"
        element={
          <ProtectedRoute>
            <Dashboard />
          </ProtectedRoute>
        }
      />
      <Route
        path="/centers"
        element={
          <ProtectedRoute roles={MANAGEMENT}>
            <Centers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute roles={FINANCE}>
            <Reports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/students"
        element={
          <ProtectedRoute roles={STAFF}>
            <Students />
          </ProtectedRoute>
        }
      />
      <Route
        path="/rankings"
        element={
          <ProtectedRoute>
            <Rankings />
          </ProtectedRoute>
        }
      />
      <Route
        path="/analytics/:studentId"
        element={
          <ProtectedRoute>
            <StudentAnalytics />
          </ProtectedRoute>
        }
      />
      {/* الأداء والتنبؤ والتحفيز (FR7-FR13). لا تُقيَّد بدور: الخادم يحصر كلَّ
          سائل في نطاقه — الطالب ووليّ الأمر في بيانات الطالب وحدها. */}
      <Route
        path="/performance/:studentId"
        element={
          <ProtectedRoute>
            <StudentPerformance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/leaderboards"
        element={
          <ProtectedRoute>
            <Leaderboards />
          </ProtectedRoute>
        }
      />
      <Route
        path="/teachers"
        element={
          <ProtectedRoute roles={MANAGEMENT}>
            <Teachers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/halaqat"
        element={
          <ProtectedRoute roles={STAFF}>
            <Halaqat />
          </ProtectedRoute>
        }
      />
      <Route
        path="/recitations"
        element={
          <ProtectedRoute>
            <Recitations />
          </ProtectedRoute>
        }
      />
      <Route
        path="/attendance"
        element={
          <ProtectedRoute roles={ATTENDANCE}>
            <Attendance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/finance"
        element={
          <ProtectedRoute roles={FINANCE}>
            <Finance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/review-plans"
        element={
          <ProtectedRoute roles={SCHEDULE_VIEWERS}>
            <ReviewPlans />
          </ProtectedRoute>
        }
      />
      <Route
        path="/academic-schedules"
        element={
          <ProtectedRoute roles={SCHEDULE_VIEWERS}>
            <AcademicSchedules />
          </ProtectedRoute>
        }
      />
      <Route
        path="/competitions"
        element={
          <ProtectedRoute>
            <Competitions />
          </ProtectedRoute>
        }
      />
      <Route
        path="/certificates"
        element={
          <ProtectedRoute roles={CERTIFICATE_VIEWERS}>
            <Certificates />
          </ProtectedRoute>
        }
      />
      <Route
        path="/bulk-messages"
        element={
          <ProtectedRoute>
            <BulkMessages />
          </ProtectedRoute>
        }
      />
      <Route
        path="/profile"
        element={
          <ProtectedRoute>
            <ProfilePage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedRoute>
            <SettingsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/notifications"
        element={
          <ProtectedRoute>
            <NotificationsPage />
          </ProtectedRoute>
        }
      />
      <Route
        path="/audit-logs"
        element={
          <ProtectedRoute roles={AUDIT}>
            <AuditLogPage />
          </ProtectedRoute>
        }
      />
      <Route path="/403" element={<ForbiddenPage />} />
      <Route path="/404" element={<NotFoundPage />} />
      <Route path="/" element={<Landing />} />
      <Route path="/sponsorships" element={<Sponsorships />} />
      <Route path="/register" element={<PublicRoute><RegisterCenter /></PublicRoute>} />
      <Route path="*" element={<Navigate to="/404" replace />} />
    </Routes>

  );
}

export default function App() {
  return (
    <Router>
      <AuthProvider>
        <AppRoutes />
      </AuthProvider>
    </Router>
  );
}
