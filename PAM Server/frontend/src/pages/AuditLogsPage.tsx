import { useEffect, useState, useCallback } from 'react';
import { Download, Filter, Search, ChevronLeft, ChevronRight } from 'lucide-react';
import { useAuth } from '../AuthContext';
import * as api from '../api';
import type { AuditLog, Company } from '../types';

const PAGE_SIZE = 20;

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString(undefined, {
    year: 'numeric',
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function SecurityBadge({ status }: { status: string }) {
  const s = status?.toLowerCase() || 'info';
  let cls = 'bg-blue-600/20 text-blue-400';
  if (s === 'warning') cls = 'bg-yellow-600/20 text-yellow-400';
  else if (s === 'critical') cls = 'bg-red-600/20 text-red-400';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium ${cls}`}>
      {status || 'Info'}
    </span>
  );
}

export default function AuditLogsPage() {
  const { user } = useAuth();
  const [logs, setLogs] = useState<AuditLog[]>([]);
  const [companies, setCompanies] = useState<Company[]>([]);
  const [loading, setLoading] = useState(true);

  // Filters
  const [dateFrom, setDateFrom] = useState('');
  const [dateTo, setDateTo] = useState('');
  const [eventType, setEventType] = useState('');
  const [performedBy, setPerformedBy] = useState('');
  const [securityStatus, setSecurityStatus] = useState('All');
  const [companyFilter, setCompanyFilter] = useState('');

  // Pagination
  const [page, setPage] = useState(1);
  const [hasMore, setHasMore] = useState(false);
  const [total, setTotal] = useState(0);

  const isRegularUser = user?.role === 'user';
  const isAdmin = user?.role === 'manager';
  const isSuperuser = user?.role === 'admin';

  const fetchLogs = useCallback(async (pageNum: number, append: boolean = false) => {
    setLoading(true);
    try {
      const params: Record<string, string | number> = {
        limit: PAGE_SIZE,
        offset: (pageNum - 1) * PAGE_SIZE,
      };
      if (eventType) params.action = eventType;
      if (performedBy) params.username = performedBy;
      if (securityStatus !== 'All') params.security_status = securityStatus;
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (isSuperuser && companyFilter) params.company_id = Number(companyFilter);
      if (isAdmin && user?.company_id) params.company_id = user.company_id;

      const search = new URLSearchParams();
      Object.entries(params).forEach(([k, v]) => search.set(k, String(v)));
      const qs = search.toString();
      const data = await api.request<AuditLog[]>(`/audit-logs${qs ? `?${qs}` : ''}`);

      setLogs(append ? (prev) => [...prev, ...data] : data);
      setHasMore(data.length === PAGE_SIZE);
      setTotal(pageNum * PAGE_SIZE + (data.length === PAGE_SIZE ? 0 : 0));
    } catch (err) {
      console.error(err);
    } finally {
      setLoading(false);
    }
  }, [eventType, performedBy, securityStatus, dateFrom, dateTo, companyFilter, isSuperuser, isAdmin, user?.company_id]);

  useEffect(() => {
    if (isRegularUser) {
      setLoading(false);
      return;
    }
    fetchLogs(1);
  }, [fetchLogs, isRegularUser]);

  useEffect(() => {
    if (isSuperuser) {
      api.getCompanies().then(setCompanies).catch(console.error);
    }
  }, [isSuperuser]);

  const handleApplyFilters = () => {
    setPage(1);
    fetchLogs(1);
  };

  const handleClearFilters = () => {
    setDateFrom('');
    setDateTo('');
    setEventType('');
    setPerformedBy('');
    setSecurityStatus('All');
    setCompanyFilter('');
    setPage(1);
    fetchLogs(1);
  };

  const handleExportCsv = async () => {
    try {
      const params: Record<string, string> = {};
      if (dateFrom) params.from = dateFrom;
      if (dateTo) params.to = dateTo;
      if (eventType) params.action = eventType;
      if (performedBy) params.username = performedBy;
      if (isSuperuser && companyFilter) params.company_id = companyFilter;
      if (isAdmin && user?.company_id) params.company_id = String(user.company_id);

      const blob = await api.exportAuditLogsCsv(params);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `audit-logs-${new Date().toISOString().slice(0, 10)}.csv`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error(err);
    }
  };

  const handlePrevPage = () => {
    if (page > 1) {
      setPage((p) => p - 1);
      fetchLogs(page - 1);
    }
  };

  const handleNextPage = () => {
    if (hasMore) {
      setPage((p) => p + 1);
      fetchLogs(page + 1);
    }
  };

  if (isRegularUser) {
    return (
      <div className="flex items-center justify-center h-64">
        <div className="text-center">
          <div className="bg-red-600/10 p-4 rounded-full inline-flex mb-4">
            <Search className="w-8 h-8 text-red-400" />
          </div>
          <h2 className="text-xl font-semibold text-red-400">Access Denied</h2>
          <p className="text-slate-400 mt-2">You do not have permission to view audit logs.</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold text-white">Audit Logs</h1>

      {/* Filters */}
      <div className="bg-slate-800 rounded-xl border border-slate-700 p-4 space-y-4">
        <div className="flex items-center gap-2 text-slate-300">
          <Filter className="h-4 w-4" />
          <span className="text-sm font-medium">Filters</span>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs text-slate-400 mb-1">Date From</label>
            <input
              type="date"
              value={dateFrom}
              onChange={(e) => setDateFrom(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Date To</label>
            <input
              type="date"
              value={dateTo}
              onChange={(e) => setDateTo(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Event Type</label>
            <input
              type="text"
              placeholder="e.g. login, create_user"
              value={eventType}
              onChange={(e) => setEventType(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Performed By</label>
            <input
              type="text"
              placeholder="Username"
              value={performedBy}
              onChange={(e) => setPerformedBy(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition placeholder-slate-500"
            />
          </div>
          <div>
            <label className="block text-xs text-slate-400 mb-1">Security Status</label>
            <select
              value={securityStatus}
              onChange={(e) => setSecurityStatus(e.target.value)}
              className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
            >
              <option value="All">All</option>
              <option value="Info">Info</option>
              <option value="Warning">Warning</option>
              <option value="Critical">Critical</option>
            </select>
          </div>
          {isSuperuser && (
            <div>
              <label className="block text-xs text-slate-400 mb-1">Company</label>
              <select
                value={companyFilter}
                onChange={(e) => setCompanyFilter(e.target.value)}
                className="bg-slate-700/50 border border-slate-600 rounded-lg px-3 py-2 text-sm text-slate-100 w-full focus:outline-none focus:ring-2 focus:ring-blue-500 focus:border-transparent transition"
              >
                <option value="">All Companies</option>
                {companies.map((c) => (
                  <option key={c.id} value={c.id}>{c.name}</option>
                ))}
              </select>
            </div>
          )}
        </div>
        <div className="flex gap-3">
          <button
            onClick={handleApplyFilters}
            className="flex items-center gap-1.5 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            <Filter className="h-4 w-4" />
            Apply Filters
          </button>
          <button
            onClick={handleClearFilters}
            className="flex items-center gap-1.5 bg-slate-700 hover:bg-slate-600 text-slate-200 font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            Clear
          </button>
          <button
            onClick={handleExportCsv}
            className="flex items-center gap-1.5 bg-emerald-600 hover:bg-emerald-500 text-white font-medium rounded-lg px-4 py-2 text-sm transition ml-auto"
          >
            <Download className="h-4 w-4" />
            Export CSV
          </button>
        </div>
      </div>

      {/* Table */}
      {loading ? (
        <div className="flex items-center justify-center h-64">
          <div className="text-slate-400">Loading audit logs...</div>
        </div>
      ) : logs.length === 0 ? (
        <div className="bg-slate-800 rounded-xl p-12 flex flex-col items-center justify-center text-slate-500">
          <Search className="w-12 h-12 mb-3" />
          <p className="text-lg">No audit logs found</p>
          <p className="text-sm text-slate-600 mt-1">Try adjusting your filters.</p>
        </div>
      ) : (
        <div className="bg-slate-800 rounded-xl border border-slate-700 overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="sticky top-0 bg-slate-800">
                <tr className="border-b border-slate-700 text-slate-400 text-left">
                  <th className="px-4 py-3 font-medium">Timestamp</th>
                  <th className="px-4 py-3 font-medium">Event Type</th>
                  <th className="px-4 py-3 font-medium">Performed By</th>
                  <th className="px-4 py-3 font-medium">Target</th>
                  <th className="px-4 py-3 font-medium">Action Detail</th>
                  <th className="px-4 py-3 font-medium">Company</th>
                  <th className="px-4 py-3 font-medium">Security Status</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {logs.map((log) => {
                  const extra = log as Record<string, unknown>;
                  return (
                    <tr key={log.id} className="hover:bg-slate-700/50 transition">
                      <td className="px-4 py-3 text-slate-200 text-xs whitespace-nowrap">
                        {formatDate(log.created_at)}
                      </td>
                      <td className="px-4 py-3 text-slate-200">{log.action}</td>
                      <td className="px-4 py-3 text-slate-200">{log.username || '-'}</td>
                      <td className="px-4 py-3 text-slate-300">
                        {log.target_type}{log.target_id ? ` #${log.target_id}` : ''}
                      </td>
                      <td className="px-4 py-3 text-slate-300 max-w-[200px] truncate">
                        {log.details || '-'}
                      </td>
                      <td className="px-4 py-3 text-slate-300">
                        {(extra.company_name as string) || '-'}
                      </td>
                      <td className="px-4 py-3">
                        <SecurityBadge status={(extra.security_status as string) || 'Info'} />
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Pagination */}
      {logs.length > 0 && (
        <div className="flex items-center justify-center gap-4">
          <button
            onClick={handlePrevPage}
            disabled={page <= 1}
            className="flex items-center gap-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            <ChevronLeft className="h-4 w-4" />
            Previous
          </button>
          <span className="text-sm text-slate-400">Page {page} of {hasMore ? `${page}+` : page}</span>
          <button
            onClick={handleNextPage}
            disabled={!hasMore}
            className="flex items-center gap-1.5 bg-slate-700 hover:bg-slate-600 disabled:opacity-50 disabled:cursor-not-allowed text-slate-200 font-medium rounded-lg px-4 py-2 text-sm transition"
          >
            Next
            <ChevronRight className="h-4 w-4" />
          </button>
        </div>
      )}
    </div>
  );
}
