import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Clock, ExternalLink, XCircle } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Request } from '../types';

function timeAgo(dateStr: string): string {
  const now = Date.now();
  const then = new Date(dateStr).getTime();
  const seconds = Math.floor((now - then) / 1000);
  if (seconds < 60) return 'just now';
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} min ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days}d ago`;
  return new Date(dateStr).toLocaleDateString();
}

const tabs = ['All', 'Pending', 'Approved', 'Rejected'] as const;
type Tab = (typeof tabs)[number];

const statusBadge: Record<string, string> = {
  pending: 'bg-yellow-500/20 text-yellow-400',
  approved: 'bg-green-500/20 text-green-400',
  rejected: 'bg-red-500/20 text-red-400',
  expired: 'bg-slate-500/20 text-slate-400',
  cancelled: 'bg-slate-600/20 text-slate-300',
};

const accessBadge: Record<string, string> = {
  root: 'bg-red-500/20 text-red-400',
  user: 'bg-green-500/20 text-green-400',
};

export default function MyRequestsPage() {
  const { user, loading: authLoading } = useAuth();
  const navigate = useNavigate();
  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState<Tab>('All');
  const [, setTick] = useState(0);

  useEffect(() => {
    if (authLoading) return;
    if (!user) return;

    api
      .getMyRequests()
      .then(setRequests)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user, authLoading]);

  useEffect(() => {
    const timer = setInterval(() => setTick(Date.now()), 10000);
    return () => clearInterval(timer);
  }, []);

  const filtered = requests.filter((r) => {
    if (activeTab === 'All') return true;
    return r.status === activeTab.toLowerCase();
  });

  const isExpired = (r: Request) => new Date(r.expires_at).getTime() < Date.now();

  const handleCancel = async (id: number) => {
    try {
      await api.cancelRequest(id);
      setRequests((prev) => prev.map((r) => (r.id === id ? { ...r, status: 'cancelled' as const } : r)));
    } catch (err) {
      console.error(err);
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">My Requests</h1>

      <div className="inline-flex gap-2">
        {tabs.map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`px-4 py-1.5 rounded-full text-sm font-medium transition ${
              activeTab === tab
                ? 'bg-blue-600 text-white'
                : 'bg-slate-700 text-slate-300 hover:bg-slate-600'
            }`}
          >
            {tab}
          </button>
        ))}
      </div>

      {filtered.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-12 flex flex-col items-center justify-center text-slate-500">
          <Clock className="w-12 h-12 mb-3" />
          <p className="text-lg">No requests found</p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-left">
                <th className="px-4 py-3 font-medium">Request ID</th>
                <th className="px-4 py-3 font-medium">Server Name</th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Access Level</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Description</th>
                <th className="px-4 py-3 font-medium">Requested At</th>
                <th className="px-4 py-3 font-medium">Status</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {filtered.map((r) => (
                <tr key={r.id} className="hover:bg-slate-700/50 transition">
                  <td className="px-4 py-3 text-slate-200 font-mono">
                    {r.id.toString().slice(0, 8)}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {r.server_hostname || `Server #${r.server_id}`}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {(r as Record<string, unknown>).company_name as string || '-'}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        accessBadge[((r as Record<string, unknown>).access_level as string) || 'user'] || 'bg-slate-500/20 text-slate-400'
                      }`}
                    >
                      {((r as Record<string, unknown>).access_level as string) || 'user'}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {((r as Record<string, unknown>).duration_minutes as number)
                      ? `${(r as Record<string, unknown>).duration_minutes as number}m`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-slate-300 max-w-[200px] truncate">
                    {r.reason}
                  </td>
                  <td className="px-4 py-3 text-slate-400 text-xs">
                    {timeAgo(r.created_at)}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block px-2.5 py-0.5 rounded-full text-xs font-medium ${
                        statusBadge[r.status] || 'bg-slate-500/20 text-slate-400'
                      }`}
                    >
                      {r.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    {r.status === 'pending' && (
                      <button
                        onClick={() => handleCancel(r.id)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-500 text-white transition"
                      >
                        <XCircle className="w-3.5 h-3.5 inline mr-1" />
                        Cancel
                      </button>
                    )}
                    {r.status === 'approved' && !isExpired(r) && (
                      <button
                        onClick={() => navigate(`/session/${r.server_id}/${r.id}`)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition"
                      >
                        <ExternalLink className="w-3.5 h-3.5 inline mr-1" />
                        Connect
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
