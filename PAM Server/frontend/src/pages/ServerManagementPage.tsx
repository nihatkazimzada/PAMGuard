import { useEffect, useState } from 'react';
import { Server, Globe, Terminal, Plus, Activity, AlertCircle, X, Loader2 } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Server as ServerType, Company, Request as RequestType } from '../types';

const osOptions = [
  'Ubuntu Server 20.04',
  'Ubuntu Server 22.04',
  'Windows Server 2019',
  'Windows Server 2022',
  'CentOS 9',
  'Rocky Linux 9',
];

interface AddServerForm {
  hostname: string;
  ip_address: string;
  port: string;
  os: string;
  company_id: string;
}

const initialAddForm: AddServerForm = {
  hostname: '',
  ip_address: '',
  port: '22',
  os: '',
  company_id: '',
};

interface RequestForm {
  duration_minutes: string;
  access_level: string;
  description: string;
}

const initialRequestForm: RequestForm = {
  duration_minutes: '60',
  access_level: 'user',
  description: '',
};

export default function ServerManagementPage() {
  const { user: currentUser } = useAuth();
  const [servers, setServers] = useState<ServerType[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [activeRequests, setActiveRequests] = useState<Map<number, RequestType>>(new Map());
  const [loading, setLoading] = useState(true);
  const [selectedCompany, setSelectedCompany] = useState<string>('');

  const [showAddModal, setShowAddModal] = useState(false);
  const [addForm, setAddForm] = useState<AddServerForm>(initialAddForm);
  const [addError, setAddError] = useState('');
  const [addSubmitting, setAddSubmitting] = useState(false);

  const [requestServerId, setRequestServerId] = useState<number | null>(null);
  const [requestForm, setRequestForm] = useState<RequestForm>(initialRequestForm);
  const [requestSubmitting, setRequestSubmitting] = useState(false);
  const [requestError, setRequestError] = useState('');
  const [requestSuccess, setRequestSuccess] = useState('');

  const isSuperuser = currentUser?.role === 'admin';
  const isAdmin = currentUser?.role === 'manager';
  const isUser = currentUser?.role === 'user';

  const fetchServers = () => {
    const companyId = selectedCompany ? Number(selectedCompany) : undefined;
    api
      .getServers(companyId)
      .then(async (data) => {
        setServers(data);
        if (!isUser) {
          const reqs = await api.getRequests({ status: 'approved' });
          const map = new Map<number, RequestType>();
          const currentUserId = currentUser?.id;
          for (const r of reqs) {
            if (r.user_id === currentUserId && r.status === 'approved') {
              map.set(r.server_id, r);
            }
          }
          setActiveRequests(map);
        }
      })
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const fetchCompanies = () => {
    api.getCompanies().then(setCompanies).catch(console.error);
  };

  useEffect(() => {
    fetchServers();
    fetchCompanies();
  }, [selectedCompany]);

  const handleAddServer = async (e: React.FormEvent) => {
    e.preventDefault();
    setAddError('');

    if (!addForm.hostname || !addForm.ip_address || !addForm.company_id) {
      setAddError('Please fill in all required fields');
      return;
    }

    setAddSubmitting(true);
    try {
      await api.createServer({
        hostname: addForm.hostname,
        ip_address: addForm.ip_address,
        port: Number(addForm.port) || 22,
        os: addForm.os,
        company_id: Number(addForm.company_id),
      });
      setShowAddModal(false);
      setAddForm(initialAddForm);
      await fetchServers();
    } catch (err) {
      setAddError(err instanceof Error ? err.message : 'Failed to create server');
    } finally {
      setAddSubmitting(false);
    }
  };

  const handleRequestAccess = async (e: React.FormEvent) => {
    e.preventDefault();
    setRequestError('');
    setRequestSuccess('');

    if (!requestServerId) return;

    const minutes = parseInt(requestForm.duration_minutes, 10);
    if (!minutes || minutes < 1) {
      setRequestError('Duration must be at least 1 minute');
      return;
    }

    setRequestSubmitting(true);
    try {
      const reason = requestForm.access_level === 'root'
        ? `[root] ${requestForm.description}`
        : `[user] ${requestForm.description}`;
      await api.createRequest({
        server_id: requestServerId,
        reason,
        duration_minutes: minutes,
      });
      setRequestSuccess('Access request submitted successfully');
      setRequestForm(initialRequestForm);
      setRequestServerId(null);
    } catch (err) {
      setRequestError(err instanceof Error ? err.message : 'Failed to create request');
    } finally {
      setRequestSubmitting(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading servers...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-2xl font-bold text-white">Server Management</h1>
        <div className="flex items-center gap-4">
          {isSuperuser && (
            <>
              <select
                value={selectedCompany}
                onChange={(e) => setSelectedCompany(e.target.value)}
                className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              >
                <option value="">All Companies</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>
                    {c.name}
                  </option>
                ))}
              </select>
              <button
                onClick={() => {
                  setAddForm(initialAddForm);
                  setAddError('');
                  setShowAddModal(true);
                }}
                className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
              >
                <Plus className="w-4 h-4" />
                Add Target Server
              </button>
            </>
          )}
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-5">
        {servers.map((srv) => {
          const hasApprovedRequest = activeRequests.has(srv.id);
          const approvedReq = activeRequests.get(srv.id);
          const serverActive = true;

          return (
            <div
              key={srv.id}
              className="bg-slate-800 rounded-xl border border-slate-700 p-5"
            >
              <div className="flex items-start justify-between mb-3">
                <div className="flex items-center gap-2 min-w-0">
                  <Server className="w-5 h-5 text-blue-400 shrink-0" />
                  <h3 className="text-white font-semibold truncate">
                    {srv.hostname}
                  </h3>
                </div>
                <span
                  className={`inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full text-xs font-medium shrink-0 ${
                    serverActive
                      ? 'bg-green-500/20 text-green-300'
                      : 'bg-red-500/20 text-red-300'
                  }`}
                >
                  <span
                    className={`w-1.5 h-1.5 rounded-full ${
                      serverActive ? 'bg-green-400' : 'bg-red-400'
                    }`}
                  />
                  {serverActive ? 'Active' : 'Inactive'}
                </span>
              </div>

              <div className="space-y-2 text-sm">
                <div className="flex items-center gap-2 text-slate-400">
                  <Globe className="w-4 h-4 shrink-0" />
                  <span className="text-slate-200">{srv.ip_address}</span>
                </div>
                <div className="text-slate-400">
                  Company: <span className="text-slate-200">{srv.company_name || '\u2014'}</span>
                </div>
                {(isSuperuser || isAdmin) && (
                  <>
                    <div className="flex items-center gap-2 text-slate-400">
                      <Terminal className="w-4 h-4 shrink-0" />
                      <span className="text-slate-200">{srv.os || '\u2014'}</span>
                    </div>
                    <div className="text-slate-400">
                      Port: <span className="text-slate-200">{srv.port}</span>
                    </div>
                    <div className="flex items-center gap-2 text-slate-400">
                      <Activity className="w-4 h-4 shrink-0" />
                      <span className="text-slate-200">SSH</span>
                    </div>
                  </>
                )}
              </div>

              <div className="mt-4">
                {!serverActive ? (
                  <button
                    disabled
                    className="w-full bg-slate-700/50 text-slate-500 font-medium rounded-lg px-4 py-2 text-sm cursor-not-allowed"
                  >
                    Unavailable
                  </button>
                ) : hasApprovedRequest && approvedReq ? (
                  <button
                    onClick={() =>
                      window.open(
                        `/session/${srv.id}/${approvedReq.id}`,
                        '_blank',
                      )
                    }
                    className="w-full bg-green-600 hover:bg-green-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
                  >
                    Connect
                  </button>
                ) : (
                  <button
                    onClick={() => {
                      setRequestForm(initialRequestForm);
                      setRequestError('');
                      setRequestSuccess('');
                      setRequestServerId(srv.id);
                    }}
                    className="w-full bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
                  >
                    Request Access
                  </button>
                )}
              </div>
            </div>
          );
        })}
        {servers.length === 0 && (
          <div className="col-span-full flex items-center justify-center h-32 text-slate-500">
            No servers found
          </div>
        )}
      </div>

      {showAddModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setShowAddModal(false)}
          />
          <div className="relative bg-slate-800 rounded-xl border border-slate-600 w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Add Target Server</h2>
              <button
                onClick={() => setShowAddModal(false)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleAddServer} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Server Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={addForm.hostname}
                  onChange={(e) =>
                    setAddForm((p) => ({ ...p, hostname: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  IP Address <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={addForm.ip_address}
                  onChange={(e) =>
                    setAddForm((p) => ({ ...p, ip_address: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Port Number
                </label>
                <input
                  type="number"
                  value={addForm.port}
                  onChange={(e) =>
                    setAddForm((p) => ({ ...p, port: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Allowed Connection Types
                </label>
                <div className="space-y-2">
                  <label className="flex items-center gap-2 text-slate-300 text-sm">
                    <input
                      type="checkbox"
                      checked
                      disabled
                      className="accent-blue-500"
                    />
                    SSH
                  </label>
                  <label className="flex items-center gap-2 text-slate-500 text-sm cursor-not-allowed">
                    <input
                      type="checkbox"
                      disabled
                      className="accent-blue-500"
                    />
                    RDP (Coming soon)
                  </label>
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Operating System
                </label>
                <select
                  value={addForm.os}
                  onChange={(e) =>
                    setAddForm((p) => ({ ...p, os: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                >
                  <option value="">Select OS</option>
                  {osOptions.map((os) => (
                    <option key={os} value={os}>
                      {os}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Tenant Company <span className="text-red-400">*</span>
                </label>
                <select
                  value={addForm.company_id}
                  onChange={(e) =>
                    setAddForm((p) => ({ ...p, company_id: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                >
                  <option value="">Select company</option>
                  {companies.map((c) => (
                    <option key={c.id} value={c.id}>
                      {c.name}
                    </option>
                  ))}
                </select>
              </div>

              {addError && (
                <div className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">
                  {addError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowAddModal(false)}
                  className="px-4 py-2.5 text-sm font-medium text-slate-300 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={addSubmitting}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {addSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {addSubmitting ? 'Creating...' : 'Create Server'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {requestServerId !== null && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setRequestServerId(null)}
          />
          <div className="relative bg-slate-800 rounded-xl border border-slate-600 w-full max-w-md max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Request Access</h2>
              <button
                onClick={() => setRequestServerId(null)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleRequestAccess} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Duration (minutes) <span className="text-red-400">*</span>
                </label>
                <input
                  type="number"
                  value={requestForm.duration_minutes}
                  onChange={(e) =>
                    setRequestForm((p) => ({
                      ...p,
                      duration_minutes: e.target.value,
                    }))
                  }
                  min={1}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Access Level
                </label>
                <select
                  value={requestForm.access_level}
                  onChange={(e) =>
                    setRequestForm((p) => ({
                      ...p,
                      access_level: e.target.value,
                    }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                >
                  <option value="user">User</option>
                  <option value="root">Root</option>
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Description
                </label>
                <textarea
                  value={requestForm.description}
                  onChange={(e) =>
                    setRequestForm((p) => ({
                      ...p,
                      description: e.target.value,
                    }))
                  }
                  rows={3}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition resize-none"
                />
              </div>

              {requestError && (
                <div className="flex items-center gap-2 text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">
                  <AlertCircle className="w-4 h-4 shrink-0" />
                  {requestError}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setRequestServerId(null)}
                  className="px-4 py-2.5 text-sm font-medium text-slate-300 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={requestSubmitting}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {requestSubmitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {requestSubmitting ? 'Submitting...' : 'Submit Request'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}

      {requestSuccess && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setRequestSuccess('')}
          />
          <div className="relative bg-slate-800 rounded-xl border border-slate-600 w-full max-w-sm p-6 text-center">
            <div className="bg-green-500/10 p-3 rounded-full inline-flex mb-4">
              <Activity className="w-6 h-6 text-green-400" />
            </div>
            <p className="text-slate-200 text-sm">{requestSuccess}</p>
            <button
              onClick={() => setRequestSuccess('')}
              className="mt-4 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-5 py-2 text-sm transition"
            >
              OK
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
