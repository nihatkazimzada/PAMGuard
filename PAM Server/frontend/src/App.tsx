import { Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './AuthContext';
import Layout from './components/Layout';
import LoginPage from './pages/LoginPage';
import DashboardPage from './pages/DashboardPage';
import CompanyTenantsPage from './pages/CompanyTenantsPage';
import UserRegistryPage from './pages/UserRegistryPage';
import ServerManagementPage from './pages/ServerManagementPage';
import MyRequestsPage from './pages/MyRequestsPage';
import PendingApprovalsPage from './pages/PendingApprovalsPage';
import SessionWindowPage from './pages/SessionWindowPage';
import SessionRecordingsPage from './pages/SessionRecordingsPage';
import AuditLogsPage from './pages/AuditLogsPage';
import SettingsPage from './pages/SettingsPage';
import NotificationsPage from './pages/NotificationsPage';

function DefaultRedirect() {
  const { user } = useAuth();
  const isAdmin = user?.role === 'admin' || user?.role === 'manager';
  return <Navigate to={isAdmin ? '/dashboard' : '/servers'} replace />;
}

function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<Layout />}>
        <Route index element={<DefaultRedirect />} />
        <Route path="dashboard" element={<DashboardPage />} />
        <Route path="companies" element={<CompanyTenantsPage />} />
        <Route path="users" element={<UserRegistryPage />} />
        <Route path="servers" element={<ServerManagementPage />} />
        <Route path="my-requests" element={<MyRequestsPage />} />
        <Route path="approvals" element={<PendingApprovalsPage />} />
        <Route path="session/:serverId/:requestId" element={<SessionWindowPage />} />
        <Route path="recordings" element={<SessionRecordingsPage />} />
        <Route path="audit-logs" element={<AuditLogsPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="notifications" element={<NotificationsPage />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}
