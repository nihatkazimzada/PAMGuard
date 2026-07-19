import { NavLink, Outlet, useLocation } from 'react-router-dom';
import {
  LayoutDashboard,
  Building2,
  Users,
  Server,
  FileText,
  CheckSquare,
  Monitor,
  ScrollText,
  Settings,
  Bell,
  Shield,
  LogOut,
} from 'lucide-react';
import { useAuth } from '../AuthContext';

interface NavItem {
  to: string;
  label: string;
  icon: React.ReactNode;
  roles: ('admin' | 'manager' | 'user')[];
}

const navItems: NavItem[] = [
  { to: '/dashboard', label: 'Dashboard', icon: <LayoutDashboard size={20} />, roles: ['admin', 'manager'] },
  { to: '/companies', label: 'Company Tenants', icon: <Building2 size={20} />, roles: ['admin'] },
  { to: '/users', label: 'User Registry', icon: <Users size={20} />, roles: ['admin', 'manager'] },
  { to: '/servers', label: 'Server Management', icon: <Server size={20} />, roles: ['admin', 'manager', 'user'] },
  { to: '/my-requests', label: 'My Requests', icon: <FileText size={20} />, roles: ['admin', 'manager', 'user'] },
  { to: '/approvals', label: 'Pending Approvals', icon: <CheckSquare size={20} />, roles: ['admin', 'manager'] },
  { to: '/recordings', label: 'Session Recordings', icon: <Monitor size={20} />, roles: ['admin', 'manager'] },
  { to: '/audit-logs', label: 'Audit Logs', icon: <ScrollText size={20} />, roles: ['admin', 'manager'] },
  { to: '/settings', label: 'Settings', icon: <Settings size={20} />, roles: ['admin', 'manager', 'user'] },
];

const pageTitles: Record<string, string> = {
  '/dashboard': 'Dashboard',
  '/companies': 'Company Tenants',
  '/users': 'User Registry',
  '/servers': 'Server Management',
  '/my-requests': 'My Requests',
  '/approvals': 'Pending Approvals',
  '/recordings': 'Session Recordings',
  '/audit-logs': 'Audit Logs',
  '/settings': 'Settings',
  '/notifications': 'Notifications',
};

const unreadCount = 3;

export default function Layout() {
  const { user, logout } = useAuth();
  const location = useLocation();

  const basePath = '/' + location.pathname.split('/')[1];
  const pageTitle = pageTitles[basePath] || 'PAM Console';

  const filteredItems = navItems.filter(
    (item) => user && item.roles.includes(user.role)
  );

  return (
    <div className="flex h-screen bg-slate-950 text-slate-100">
      <aside className="fixed left-0 top-0 z-30 flex h-full w-64 flex-col bg-slate-900 border-r border-slate-800">
        <div className="flex h-16 items-center gap-3 px-6 border-b border-slate-800">
          <Shield className="h-7 w-7 text-blue-500" />
          <span className="text-lg font-bold tracking-tight">PAM Console</span>
        </div>

        <nav className="flex-1 overflow-y-auto px-3 py-4 space-y-1">
          {filteredItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === '/dashboard'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                  isActive
                    ? 'bg-blue-600/20 text-blue-400'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`
              }
            >
              {item.icon}
              <span>{item.label}</span>
            </NavLink>
          ))}
        </nav>

        {user && (
          <div className="border-t border-slate-800 px-4 py-4">
            <div className="flex items-center gap-3">
              <div className="flex h-9 w-9 items-center justify-center rounded-full bg-blue-600/30 text-sm font-semibold text-blue-400 uppercase">
                {user.username.charAt(0)}
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-sm font-medium truncate">{user.username}</p>
                <span className="inline-block mt-0.5 rounded bg-slate-800 px-2 py-0.5 text-xs font-medium capitalize text-slate-300">
                  {user.role}
                </span>
              </div>
            </div>
          </div>
        )}
      </aside>

      <div className="flex flex-1 flex-col pl-64">
        <header className="sticky top-0 z-20 flex h-16 items-center justify-between border-b border-slate-800 bg-slate-900/80 backdrop-blur-sm px-8">
          <h1 className="text-xl font-semibold">{pageTitle}</h1>

          <div className="flex items-center gap-4">
            <NavLink
              to="/notifications"
              className="relative rounded-lg p-2 text-slate-400 hover:text-slate-100 hover:bg-slate-800 transition-colors"
            >
              <Bell size={20} />
              {unreadCount > 0 && (
                <span className="absolute -top-0.5 -right-0.5 flex h-4.5 w-4.5 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white leading-none">
                  {unreadCount > 9 ? '9+' : unreadCount}
                </span>
              )}
            </NavLink>

            <button
              onClick={logout}
              className="flex items-center gap-2 rounded-lg px-3 py-2 text-sm text-slate-400 hover:text-red-400 hover:bg-slate-800 transition-colors"
            >
              <LogOut size={18} />
              <span className="hidden sm:inline">Logout</span>
            </button>
          </div>
        </header>

        <main className="flex-1 overflow-y-auto p-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
