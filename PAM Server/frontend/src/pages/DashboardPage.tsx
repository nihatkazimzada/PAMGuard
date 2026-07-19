import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Users,
  Building2,
  UserCheck,
  FileText,
  Monitor,
  AlertTriangle,
  AlertOctagon,
  Activity,
} from 'lucide-react';
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  CartesianGrid,
} from 'recharts';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { DashboardStats } from '../types';

export default function DashboardPage() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (authLoading) return;
    if (!user || user.role === 'user') {
      navigate('/servers', { replace: true });
      return;
    }

    api
      .getDashboardStats()
      .then(setStats)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user, authLoading, navigate]);

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading dashboard...</div>
      </div>
    );
  }

  if (!stats) return null;

  const statCards = [
    { label: 'Admins', value: stats.num_admins, icon: Users },
    { label: 'Companies', value: stats.num_companies, icon: Building2 },
    { label: 'Regular Users', value: stats.total_regular_users, icon: UserCheck },
    { label: 'Total Requests', value: stats.total_requests, icon: FileText },
    { label: 'Active Sessions', value: stats.active_sessions, icon: Monitor },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {statCards.map((card) => (
          <div
            key={card.label}
            className="bg-slate-800 rounded-xl p-5 border border-slate-700"
          >
            <div className="flex items-center justify-between mb-3">
              <span className="text-slate-400 text-sm">{card.label}</span>
              <card.icon className="w-5 h-5 text-slate-500" />
            </div>
            <p className="text-2xl font-bold text-blue-400">{card.value}</p>
            {card.label === 'Companies' && stats.companies?.length > 0 && (
              <div className="mt-3 space-y-1.5 border-t border-slate-700 pt-3">
                {stats.companies.map((c) => (
                  <div
                    key={c.name}
                    className="flex justify-between text-xs text-slate-400"
                  >
                    <span className="truncate">{c.name}</span>
                    <span className="shrink-0 ml-2">{c.user_count} users</span>
                  </div>
                ))}
              </div>
            )}
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <div className="flex items-center justify-between mb-3">
            <span className="text-red-400 text-sm font-medium">
              Critical Alerts
            </span>
            <AlertOctagon className="w-5 h-5 text-red-400" />
          </div>
          <p className="text-2xl font-bold text-red-400">
            {stats.critical_alerts}
          </p>
        </div>
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <div className="flex items-center justify-between mb-3">
            <span className="text-amber-400 text-sm font-medium">
              High / Warning Alerts
            </span>
            <AlertTriangle className="w-5 h-5 text-amber-400" />
          </div>
          <p className="text-2xl font-bold text-amber-400">
            {stats.warning_alerts}
          </p>
        </div>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <h3 className="text-white font-medium mb-4">
            Failed Login Attempts (24h)
          </h3>
          <ResponsiveContainer width="100%" height={250}>
            <BarChart data={stats.failed_logins || []}>
              <CartesianGrid
                strokeDasharray="3 3"
                stroke="#334155"
                vertical={false}
              />
              <XAxis
                dataKey="hour"
                stroke="#64748b"
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="#64748b"
                tick={{ fontSize: 12 }}
                axisLine={false}
                tickLine={false}
                allowDecimals={false}
              />
              <Tooltip
                contentStyle={{
                  backgroundColor: '#1e293b',
                  border: '1px solid #334155',
                  borderRadius: '8px',
                  fontSize: '13px',
                }}
                labelStyle={{ color: '#e2e8f0' }}
                itemStyle={{ color: '#f87171' }}
              />
              <Bar
                dataKey="count"
                fill="#ef4444"
                radius={[4, 4, 0, 0]}
                maxBarSize={40}
              />
            </BarChart>
          </ResponsiveContainer>
          {(!stats.failed_logins || stats.failed_logins.length === 0) && (
            <p className="text-sm text-slate-500 text-center py-8">
              No failed login data
            </p>
          )}
        </div>

        <div className="bg-slate-800 rounded-xl p-5 border border-slate-700">
          <div className="flex items-center justify-between mb-4">
            <h3 className="text-white font-medium">Recent Activities</h3>
            <button
              onClick={() => navigate('/audit-logs')}
              className="text-sm text-blue-400 hover:text-blue-300 transition"
            >
              View All
            </button>
          </div>
          <div className="space-y-1">
            {(stats.recent_activity ?? []).slice(0, 10).map((log) => (
              <div
                key={log.id}
                onClick={() => navigate('/audit-logs')}
                className="flex items-start gap-3 p-2.5 rounded-lg hover:bg-slate-700/50 transition cursor-pointer"
              >
                <Activity className="w-4 h-4 text-slate-500 mt-0.5 shrink-0" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm text-slate-200 truncate">
                    <span className="font-medium">
                      {log.username || `User #${log.user_id}`}
                    </span>{' '}
                    {log.action}
                    {log.target_type ? ` on ${log.target_type}` : ''}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {new Date(log.created_at).toLocaleString()}
                  </p>
                </div>
              </div>
            ))}
            {(!stats.recent_activity ||
              stats.recent_activity.length === 0) && (
              <p className="text-sm text-slate-500 text-center py-8">
                No recent activity
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
