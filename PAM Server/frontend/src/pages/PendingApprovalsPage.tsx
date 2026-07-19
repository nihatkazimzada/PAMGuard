import { useEffect, useState } from 'react';
import { CheckCircle, XCircle, User, Server } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Request } from '../types';

const accessBadge: Record<string, string> = {
  root: 'bg-red-500/20 text-red-400',
  user: 'bg-green-500/20 text-green-400',
};

export default function PendingApprovalsPage() {
  const { user, loading: authLoading } = useAuth();
  const [requests, setRequests] = useState<Request[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  useEffect(() => {
    if (authLoading) return;
    if (!user) return;
    if (user.role === 'user') {
      setLoading(false);
      return;
    }

    api
      .getRequests({ status: 'pending' })
      .then(setRequests)
      .catch(console.error)
      .finally(() => setLoading(false));
  }, [user, authLoading]);

  const showMessage = (type: 'success' | 'error', text: string) => {
    setMessage({ type, text });
    setTimeout(() => setMessage(null), 3000);
  };

  const handleApprove = async (id: number) => {
    if (!confirm('Are you sure you want to approve this request?')) return;
    try {
      await api.approveRequest(id);
      showMessage('success', 'Request approved successfully');
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      showMessage('error', (err as Error).message || 'Failed to approve request');
    }
  };

  const handleReject = async (id: number) => {
    if (!confirm('Are you sure you want to reject this request?')) return;
    try {
      await api.rejectRequest(id);
      showMessage('success', 'Request rejected successfully');
      setRequests((prev) => prev.filter((r) => r.id !== id));
    } catch (err) {
      showMessage('error', (err as Error).message || 'Failed to reject request');
    }
  };

  if (authLoading || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading...</div>
      </div>
    );
  }

  if (user?.role === 'user') {
    return (
      <div className="flex flex-col items-center justify-center h-64 text-slate-500">
        <XCircle className="w-12 h-12 mb-3" />
        <p className="text-lg font-medium">Access Denied</p>
        <p className="text-sm">You do not have permission to view this page.</p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Pending Approvals</h1>

      {message && (
        <div
          className={`px-4 py-3 rounded-lg text-sm ${
            message.type === 'success'
              ? 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30'
              : 'bg-red-500/20 text-red-400 border border-red-500/30'
          }`}
        >
          {message.text}
        </div>
      )}

      {requests.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-12 flex flex-col items-center justify-center text-slate-500">
          <CheckCircle className="w-12 h-12 mb-3" />
          <p className="text-lg">No pending approvals</p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700 text-slate-400 text-left">
                <th className="px-4 py-3 font-medium">
                  <User className="w-3.5 h-3.5 inline mr-1.5" />
                  Requester Name
                </th>
                <th className="px-4 py-3 font-medium">
                  <Server className="w-3.5 h-3.5 inline mr-1.5" />
                  Server Name
                </th>
                <th className="px-4 py-3 font-medium">Company</th>
                <th className="px-4 py-3 font-medium">Duration</th>
                <th className="px-4 py-3 font-medium">Description</th>
                <th className="px-4 py-3 font-medium">Access Level</th>
                <th className="px-4 py-3 font-medium">Requested At</th>
                <th className="px-4 py-3 font-medium">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {requests.map((r) => (
                <tr key={r.id} className="hover:bg-slate-700/50 transition">
                  <td className="px-4 py-3 text-slate-200">
                    {r.username || `User #${r.user_id}`}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {r.server_hostname || `Server #${r.server_id}`}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {(r as Record<string, unknown>).company_name as string || '-'}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {((r as Record<string, unknown>).duration_minutes as number)
                      ? `${(r as Record<string, unknown>).duration_minutes as number}m`
                      : '-'}
                  </td>
                  <td className="px-4 py-3 text-slate-300 max-w-[200px] truncate">
                    {r.reason}
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
                  <td className="px-4 py-3 text-slate-400 text-xs">
                    {new Date(r.created_at).toLocaleString()}
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex gap-2">
                      <button
                        onClick={() => handleApprove(r.id)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white transition"
                      >
                        <CheckCircle className="w-3.5 h-3.5 inline mr-1" />
                        Approve
                      </button>
                      <button
                        onClick={() => handleReject(r.id)}
                        className="px-3 py-1.5 text-xs font-medium rounded-lg bg-red-600 hover:bg-red-500 text-white transition"
                      >
                        <XCircle className="w-3.5 h-3.5 inline mr-1" />
                        Reject
                      </button>
                    </div>
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
