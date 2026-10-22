import React from 'react';
import { useAuth } from '@/contexts/AuthContext';
import AdminDashboard from './dashboards/AdminDashboard';
import SuperAdminDashboard from './dashboards/SuperAdminDashboard';
import CenterManagerDashboard from './dashboards/CenterManagerDashboard';
import TeacherDashboard from './dashboards/TeacherDashboard';
import StudentDashboard from './dashboards/StudentDashboard';
import ParentDashboard from './dashboards/ParentDashboard';
import PasswordHelpRequests from '@/components/auth/PasswordHelpRequests';

function RoleDashboard({ role }: { role: string }) {
  switch (role) {
    case 'admin':
      return <AdminDashboard />;
    case 'super_admin':
      return <SuperAdminDashboard />;
    case 'center_manager':
      return <CenterManagerDashboard />;
    case 'teacher':
      return <TeacherDashboard />;
    case 'student':
      return <StudentDashboard />;
    case 'parent':
      return <ParentDashboard />;
    default:
      return <AdminDashboard />;
  }
}

export default function Dashboard() {
  const { user } = useAuth();

  if (!user) return null;

  // من يملك إعادة تعيين كلمات المرور يرى طلبات «نسيت كلمة المرور» أعلى لوحته
  if (['admin', 'super_admin', 'center_manager'].includes(user.role)) {
    return (
      <div className="space-y-5">
        <PasswordHelpRequests />
        <RoleDashboard role={user.role} />
      </div>
    );
  }
  return <RoleDashboard role={user.role} />;
}
