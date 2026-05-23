/*
English: This project is proprietary and confidential. All rights reserved to Abdoul Malick Cisse (Copyright © 2026).
Arabic: هذا المشروع ملكية خاصة وسري للغاية. جميع الحقوق محفوظة لـ عبد المالك سيسي (حقوق النشر © 2026).
*/
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from '@/contexts/AuthContext';
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
import AcademicSchedules from '@/pages/AcademicSchedules';
import Competitions from '@/pages/Competitions';
import BulkMessages from '@/pages/BulkMessages';
import { NotFoundPage, ForbiddenPage } from '@/pages/ErrorPages';
import DashboardLayout from '@/components/layout/DashboardLayout';

function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return <LoadingPage />;
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  return <DashboardLayout>{children}</DashboardLayout>;
}

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
          <ProtectedRoute>
            <Centers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/reports"
        element={
          <ProtectedRoute>
            <Reports />
          </ProtectedRoute>
        }
      />
      <Route
        path="/students"
        element={
          <ProtectedRoute>
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
      <Route
        path="/teachers"
        element={
          <ProtectedRoute>
            <Teachers />
          </ProtectedRoute>
        }
      />
      <Route
        path="/halaqat"
        element={
          <ProtectedRoute>
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
          <ProtectedRoute>
            <Attendance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/finance"
        element={
          <ProtectedRoute>
            <Finance />
          </ProtectedRoute>
        }
      />
      <Route
        path="/review-plans"
        element={
          <ProtectedRoute>
            <ReviewPlans />
          </ProtectedRoute>
        }
      />
      <Route
        path="/academic-schedules"
        element={
          <ProtectedRoute>
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
          <ProtectedRoute>
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
