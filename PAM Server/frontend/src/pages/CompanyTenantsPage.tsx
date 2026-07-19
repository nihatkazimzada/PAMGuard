import { useEffect, useState } from 'react';
import { Plus, Trash2, X, Loader2 } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { Company } from '../types';

interface CompanyForm {
  name: string;
  tenant_id: string;
  industry: string;
  domain: string;
  contact_email: string;
  contact_phone_country: string;
  contact_phone_number: string;
  billing_email: string;
}

const industryOptions = [
  'fintech',
  'enterprise',
  'healthcare',
  'technology',
  'education',
  'other',
];

const initialForm: CompanyForm = {
  name: '',
  tenant_id: '',
  industry: '',
  domain: '',
  contact_email: '',
  contact_phone_country: '+1',
  contact_phone_number: '',
  billing_email: '',
};

export default function CompanyTenantsPage() {
  const { user } = useAuth();
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);
  const [showModal, setShowModal] = useState(false);
  const [form, setForm] = useState<CompanyForm>(initialForm);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');
  const [deleteConfirm, setDeleteConfirm] = useState<number | null>(null);

  const fetchCompanies = () => {
    api
      .getCompanies()
      .then(setCompanies)
      .catch(console.error)
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchCompanies();
  }, []);

  if (!user || user.role !== 'admin') {
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

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setSubmitting(true);

    try {
      await api.createCompany({
        name: form.name,
        tenant_id: form.tenant_id || undefined,
        industry: form.industry || undefined,
        domain: form.domain || undefined,
        contact_email: form.contact_email || undefined,
        contact_phone: form.contact_phone_number
          ? `${form.contact_phone_country}${form.contact_phone_number}`
          : undefined,
        billing_email: form.billing_email || undefined,
      });
      setShowModal(false);
      setForm(initialForm);
      await fetchCompanies();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : 'Failed to create company',
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.deleteCompany(id);
      setCompanies((prev) => prev.filter((c) => c.id !== id));
      setDeleteConfirm(null);
    } catch (err) {
      console.error(err);
    }
  };

  const updateForm = (field: keyof CompanyForm, value: string) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-slate-400">Loading companies...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold text-white">Company Tenants</h1>
        <button
          onClick={() => {
            setForm(initialForm);
            setError('');
            setShowModal(true);
          }}
          className="flex items-center gap-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
        >
          <Plus className="w-4 h-4" />
          Add Company
        </button>
      </div>

      <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left text-slate-400 font-medium px-4 py-3">
                  Company Name
                </th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">
                  Tenant ID
                </th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">
                  Domain
                </th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">
                  Assigned Servers
                </th>
                <th className="text-left text-slate-400 font-medium px-4 py-3">
                  User Count
                </th>
                <th className="text-right text-slate-400 font-medium px-4 py-3">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700/50">
              {companies.map((company) => (
                <tr
                  key={company.id}
                  className="hover:bg-slate-700/30 transition"
                >
                  <td className="px-4 py-3 text-slate-200 font-medium">
                    {company.name}
                  </td>
                  <td className="px-4 py-3 text-slate-300 font-mono text-xs">
                    {company.tenant_id || '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-300">
                    {company.domain || '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {company.server_count ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-slate-200">
                    {company.user_count ?? '—'}
                  </td>
                  <td className="px-4 py-3 text-right">
                    {deleteConfirm === company.id ? (
                      <div className="flex items-center justify-end gap-2">
                        <span className="text-xs text-slate-400">
                          Confirm?
                        </span>
                        <button
                          onClick={() => handleDelete(company.id)}
                          className="text-red-400 hover:text-red-300 text-xs font-medium transition"
                        >
                          Delete
                        </button>
                        <button
                          onClick={() => setDeleteConfirm(null)}
                          className="text-slate-400 hover:text-slate-300 text-xs transition"
                        >
                          Cancel
                        </button>
                      </div>
                    ) : (
                      <button
                        onClick={() => setDeleteConfirm(company.id)}
                        className="text-slate-500 hover:text-red-400 transition p-1"
                        title="Delete company"
                      >
                        <Trash2 className="w-4 h-4" />
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {companies.length === 0 && (
                <tr>
                  <td
                    colSpan={6}
                    className="px-4 py-8 text-center text-slate-500"
                  >
                    No companies found
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
              <h2 className="text-lg font-semibold text-white">
                Add Company
              </h2>
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
                  Company Name <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={form.name}
                  onChange={(e) => updateForm('name', e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Tenant ID <span className="text-red-400">*</span>
                </label>
                <input
                  type="text"
                  value={form.tenant_id}
                  onChange={(e) => updateForm('tenant_id', e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Industry
                </label>
                <select
                  value={form.industry}
                  onChange={(e) => updateForm('industry', e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                >
                  <option value="">Select industry</option>
                  {industryOptions.map((opt) => (
                    <option key={opt} value={opt}>
                      {opt.charAt(0).toUpperCase() + opt.slice(1)}
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Domain
                </label>
                <input
                  type="text"
                  value={form.domain}
                  onChange={(e) => updateForm('domain', e.target.value)}
                  placeholder="example.com"
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Contact Email <span className="text-red-400">*</span>
                </label>
                <input
                  type="email"
                  value={form.contact_email}
                  onChange={(e) => updateForm('contact_email', e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  required
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Contact Phone
                </label>
                <div className="flex gap-2">
                  <input
                    type="text"
                    value={form.contact_phone_country}
                    onChange={(e) =>
                      updateForm('contact_phone_country', e.target.value)
                    }
                    placeholder="+1"
                    className="w-24 shrink-0 bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  />
                  <input
                    type="text"
                    value={form.contact_phone_number}
                    onChange={(e) =>
                      updateForm('contact_phone_number', e.target.value)
                    }
                    placeholder="Phone number"
                    className="flex-1 bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                  />
                </div>
              </div>

              <div>
                <label className="block text-sm font-medium text-slate-300 mb-1.5">
                  Billing Email
                </label>
                <input
                  type="email"
                  value={form.billing_email}
                  onChange={(e) => updateForm('billing_email', e.target.value)}
                  className="w-full bg-slate-700/50 border border-slate-600 rounded-lg px-4 py-2.5 text-slate-100 placeholder-slate-400 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
                />
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
                  {submitting && (
                    <Loader2 className="w-4 h-4 animate-spin" />
                  )}
                  {submitting ? 'Creating...' : 'Create Company'}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
