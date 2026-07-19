import { useEffect, useState } from 'react';
import { Plus, X, Loader2 } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { User as UserType, Company } from '../types';

interface UserForm {
  full_name: string;
  username: string;
  password: string;
  role: string;
  company_id: string;
}

const initialForm: UserForm = {
  full_name: '',
  username: '',
  password: '',
  role: 'user',
  company_id: '',
};

const roleDisplay: Record<string, string> = {
  admin: 'Superuser',
  manager: 'Admin',
  user: 'User',
};

const roleToInternal: Record<string, string> = {
  Superuser: 'admin',
  Admin: 'manager',
  User: 'user',
};

const badgeColors: Record<string, string> = {
  admin: 'bg-purple-500/20 text-purple-300',
  manager: 'bg-blue-500/20 text-blue-300',
  user: 'bg-green-500/20 text-green-300',
};

function roleBadge(role: string) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-xs font-medium ${badgeColors[role] || badgeColors.user}`}>
      {roleDisplay[role] || role}
    </span>
  );
}

function statusBadge(status: string) {
  const isActive = status === 'active';
  return (
    <span
      className={`px-2 py-0.5 rounded-full text-xs font-medium ${
        isActive
          ? 'bg-green-500/20 text-green-300'
          : 'bg-red-500/20 text-red-300'
      }`}
    >
      {isActive ? 'Active' : 'Inactive'}
    </span>
  );
}

export default function UserRegistryPage() {
  const { user: currentUser } = useAuth();
  const [users, setUsers] = useState<UserType[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<UserForm>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [passwordError, setPasswordError] = useState('');

  const isSuperuser = currentUser?.role === 'admin';
  const isAdmin = currentUser?.role === 'manager';
  const isUser = currentUser?.role === 'user';

  const fetchUsers = () => {
    const fetcher = isSuperuser ? api.getUsersAll() : api.getUsers();
    fetcher
      .then(setUsers)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  const fetchCompanies = () => {
    api.getCompanies().then(setCompanies).catch(console.error);
  };

  useEffect(() => {
    if (isUser) {
      setLoading(false);
      return;
    }
    fetchUsers();
    fetchCompanies();
  }, [isUser]);

  if (isUser) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="bg-red-600/10 p-4 rounded-full inline-flex mb-4">
            <X className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-red-400">Access Denied</h2>
          <p className="text-slate-400 mt-2">
            You do not have permission to view this page.
          </p>
        </div>
      </div>
    );
  }

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading users...</div>
      </div>
    );
  }

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setPasswordError('');

    if (form.password.length < 6) {
      setPasswordError('Password must be at least 6 characters');
      return;
    }

    setSubmitting(true);

    try {
      const roleValue = roleToInternal[form.role] || form.role;
      await api.createUser({
        username: form.username,
        email: form.full_name,
        password: form.password,
        role: roleValue,
        company_id: form.company_id ? Number(form.company_id) : undefined,
      });
      setShowModal(false);
      setForm(initialForm);
      await fetchUsers();
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to create user');
    } finally {
      setSubmitting(false);
    }
  };

  const handleStatusToggle = async (targetUser: UserType) => {
    const newStatus = targetUser.status === 'active' ? 'inactive' : 'active';
    try {
      await api.updateUserStatus(targetUser.id, newStatus);
      setUsers((prev) =>
        prev.map((u) =>
          u.id === targetUser.id ? { ...u, status: newStatus } : u,
        ),
      );
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to update user status',
      );
    }
  };

  const canToggleStatus = (targetUser: UserType) => {
    if (isSuperuser) return true;
    if (isAdmin && targetUser.role === 'manager') return false;
    return false;
  };

  const openAddModal = () => {
    setForm({
      ...initialForm,
      role: isSuperuser ? 'Admin' : 'User',
      company_id: isSuperuser ? '' : String(currentUser?.company_id ?? ''),
    });
    setError('');
    setPasswordError('');
    setShowModal(true);
  };

  const formatDate = (dateStr: string) => {
    if (!dateStr) return '\u2014';
    return new Date(dateStr).toLocaleString();
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">User Registry</h1>
        <button
          onClick={openAddModal}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
        >
          <Plus className="w-4 h-4" />
          Add User
        </button>
      </div>

      {error && (
        <div className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">
          {error}
        </div>
      )}

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="sticky top-0 bg-slate-800">
              <tr className="border-b border-slate-700">
                <th className="text-left text-slate-400 font-medium px-4 py-3">Full Name</th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">Username</th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">Role</th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">Company Name</th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">Status</th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">Last Login</th>
                <th className="text-right text-slate-400 font-medium px-4 py-3">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {users.map((u) => (
                <tr key={u.id} className="hover:bg-slate-700/30 transition">
                  <td className="px-4 py-3 text-slate-200">{u.email}</td>
                  <td className="px-4 py-3 text-slate-200 font-mono text-xs">{u.username}</td>
                  <td className="px-4 py-3">{roleBadge(u.role)}</td>
                  <td className="px-4 py-3 text-slate-300">{u.company_name || '\u2014'}</td>
                  <td className="px-4 py-3">{statusBadge(u.status)}</td>
                  <td className="px-4 py-3 text-slate-400 text-xs">{formatDate(u.updated_at)}</td>
                  <td className="px-4 py-3 text-right">
                    <button
                      onClick={() => handleStatusToggle(u)}
                      disabled={!canToggleStatus(u)}
                      className={`text-xs font-medium rounded-lg px-3 py-1.5 transition ${
                        !canToggleStatus(u)
                          ? 'text-slate-600 cursor-not-allowed'
                          : u.status === 'active'
                            ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                            : 'bg-green-600/20 text-green-300 hover:bg-green-600/30'
                      }`}
                    >
                      {u.status === 'active' ? 'Deactivate' : 'Activate'}
                    </button>
                  </td>
                </tr>
              ))}
              {users.length === 0 && (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-slate-500">
                    No users found
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>

      {showModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          <div
            className="absolute inset-0 bg-black/60"
            onClick={() => setShowModal(false)}
          />
          <div className="relative bg-slate-800 rounded-xl border border-slate-600 w-full max-w-lg max-h-[90vh] overflow-y-auto p-6">
            <div className="flex items-center justify-between mb-6">
              <h2 className="text-lg font-semibold text-white">Add User</h2>
              <button
                onClick={() => setShowModal(false)}
                className="text-slate-400 hover:text-slate-200 transition"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Full Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={form.full_name}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, full_name: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Username <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={form.username}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, username: e.target.value }))
                  }
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Password <span className="text-red-400">*</span>
                </label>
                <input
                  type="password"
                  value={form.password}
                  onChange={(e) => {
                    setForm((p) => ({ ...p, password: e.target.value }));
                    setPasswordError('');
                  }}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                  minLength={6}
                />
                {passwordError && (
                  <p className="mt-1 text-xs text-red-400">{passwordError}</p>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Role <span className="text-red-400">*</span>
                </label>
                {isSuperuser ? (
                  <select
                    value={form.role}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, role: e.target.value }))
                    }
                    className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  >
                    <option value="Admin">Admin</option>
                    <option value="User">User</option>
                  </select>
                ) : (
                  <div className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-400 cursor-not-allowed">
                    User
                  </div>
                )}
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Company <span className="text-red-400">*</span>
                </label>
                {isSuperuser ? (
                  <select
                    value={form.company_id}
                    onChange={(e) =>
                      setForm((p) => ({ ...p, company_id: e.target.value }))
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
                ) : (
                  <div className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-400 cursor-not-allowed">
                    {companies.find((c) => c.id === currentUser?.company_id)?.name || ''}
                  </div>
                )}
              </div>

              {error && (
                <div className="text-sm text-red-400 bg-red-400/10 rounded-lg px-4 py-2">
                  {error}
                </div>
              )}

              <div className="flex justify-end gap-3 pt-2">
                <button
                  type="button"
                  onClick={() => setShowModal(false)}
                  className="px-4 py-2.5 text-sm font-medium text-slate-300 hover:text-white transition"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={submitting}
                  className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-5 py-2.5 text-sm transition disabled:opacity-60 disabled:cursor-not-allowed"
                >
                  {submitting && <Loader2 className="w-4 h-4 animate-spin" />}
                  {submitting ? 'Creating...' : 'Create User'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
