import type {
  User,
  Company,
  Server,
  Request,
  Session,
  AuditLog,
  Notification,
  BillingAccount,
  BillingTransaction,
  DashboardStats,
  LoginResponse,
} from './types';

export const API_BASE = '/api';

function getToken(): string | null {
  return localStorage.getItem('token');
}

function setToken(token: string): void {
  localStorage.setItem('token', token);
}

function clearToken(): void {
  localStorage.removeItem('token');
  localStorage.removeItem('user');
}

async function request<T>(
  endpoint: string,
  options: RequestInit = {},
): Promise<T> {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${endpoint}`, {
    ...options,
    headers,
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.error || body.message || `Request failed with status ${res.status}`);
  }

  if (res.headers.get('content-type')?.includes('application/json')) {
    return res.json();
  }

  return undefined as T;
}

export async function login(username: string, password: string): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/auth/login', {
    method: 'POST',
    body: JSON.stringify({ username, password }),
  });
  setToken(data.token);
  localStorage.setItem('user', JSON.stringify(data.user));
  return data;
}

export async function refreshToken(): Promise<LoginResponse> {
  const data = await request<LoginResponse>('/auth/refresh', {
    method: 'POST',
  });
  setToken(data.token);
  localStorage.setItem('user', JSON.stringify(data.user));
  return data;
}

export async function getMe(): Promise<User> {
  return request<User>('/auth/me');
}

export async function changePassword(currentPassword: string, newPassword: string): Promise<void> {
  return request<void>('/auth/change-password', {
    method: 'PUT',
    body: JSON.stringify({ current_password: currentPassword, new_password: newPassword }),
  });
}

export async function changeUsername(newUsername: string, password: string): Promise<void> {
  return request<void>('/auth/change-username', {
    method: 'PUT',
    body: JSON.stringify({ new_username: newUsername, password }),
  });
}

export async function getDashboardStats(): Promise<DashboardStats> {
  return request<DashboardStats>('/dashboard/stats');
}

export async function getCompanies(): Promise<Company[]> {
  return request<Company[]>('/companies');
}

export async function createCompany(data: {
  name: string;
  tenant_id?: string;
  industry?: string;
  domain?: string;
  contact_email?: string;
  contact_phone?: string;
  billing_email?: string;
}): Promise<Company> {
  return request<Company>('/companies', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteCompany(id: number): Promise<void> {
  return request<void>(`/companies/${id}`, { method: 'DELETE' });
}

export async function getServers(companyId?: number): Promise<Server[]> {
  const params = companyId ? `?company_id=${companyId}` : '';
  return request<Server[]>(`/servers${params}`);
}

export async function createServer(data: {
  hostname: string;
  ip_address: string;
  port: number;
  os: string;
  company_id: number;
}): Promise<Server> {
  return request<Server>('/servers', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function deleteServer(id: number): Promise<void> {
  return request<void>(`/servers/${id}`, { method: 'DELETE' });
}

export async function getUsers(): Promise<User[]> {
  return request<User[]>('/users');
}

export async function getUsersAll(): Promise<User[]> {
  return request<User[]>('/users/all');
}

export async function createUser(data: {
  username: string;
  email: string;
  password: string;
  role: string;
  company_id?: number;
}): Promise<User> {
  return request<User>('/users', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function updateUserStatus(id: number, status: 'active' | 'inactive'): Promise<User> {
  return request<User>(`/users/${id}/status`, {
    method: 'PUT',
    body: JSON.stringify({ status }),
  });
}

export async function getRequests(params?: {
  status?: string;
  server_id?: number;
  user_id?: number;
}): Promise<Request[]> {
  const search = new URLSearchParams();
  if (params?.status) search.set('status', params.status);
  if (params?.server_id) search.set('server_id', String(params.server_id));
  if (params?.user_id) search.set('user_id', String(params.user_id));
  const qs = search.toString();
  return request<Request[]>(`/requests${qs ? `?${qs}` : ''}`);
}

export async function getMyRequests(): Promise<Request[]> {
  return request<Request[]>('/requests/mine');
}

export async function getPendingRequests(): Promise<Request[]> {
  return request<Request[]>('/requests/pending');
}

export async function createRequest(data: {
  server_id: number;
  reason: string;
  duration_minutes: number;
}): Promise<Request> {
  return request<Request>('/requests', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export async function approveRequest(id: number): Promise<Request> {
  return request<Request>(`/requests/${id}/approve`, { method: 'PUT' });
}

export async function rejectRequest(id: number): Promise<Request> {
  return request<Request>(`/requests/${id}/reject`, { method: 'PUT' });
}

export async function cancelRequest(id: number): Promise<Request> {
  return request<Request>(`/requests/${id}/cancel`, { method: 'PUT' });
}

export async function checkActiveRequest(serverId: number): Promise<Request | null> {
  return request<Request | null>(`/requests/active?server_id=${serverId}`);
}

export async function getSessions(): Promise<Session[]> {
  return request<Session[]>('/sessions');
}

export async function getSession(id: number): Promise<Session> {
  return request<Session>(`/sessions/${id}`);
}

export async function getSessionRecording(id: number): Promise<Blob> {
  const token = getToken();
  const res = await fetch(`${API_BASE}/sessions/${id}/recording`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) throw new Error('Failed to fetch recording');
  return res.blob();
}

export async function terminateSession(id: number): Promise<void> {
  return request<void>(`/sessions/${id}/terminate`, { method: 'PUT' });
}

export async function getAuditLogs(params?: {
  user_id?: number;
  action?: string;
  limit?: number;
  offset?: number;
}): Promise<AuditLog[]> {
  const search = new URLSearchParams();
  if (params?.user_id) search.set('user_id', String(params.user_id));
  if (params?.action) search.set('action', params.action);
  if (params?.limit) search.set('limit', String(params.limit));
  if (params?.offset) search.set('offset', String(params.offset));
  const qs = search.toString();
  return request<AuditLog[]>(`/audit-logs${qs ? `?${qs}` : ''}`);
}

export async function exportAuditLogsCsv(params?: {
  user_id?: number;
  action?: string;
  from?: string;
  to?: string;
}): Promise<Blob> {
  const token = getToken();
  const search = new URLSearchParams();
  if (params?.user_id) search.set('user_id', String(params.user_id));
  if (params?.action) search.set('action', params.action);
  if (params?.from) search.set('from', params.from);
  if (params?.to) search.set('to', params.to);
  const qs = search.toString();

  const res = await fetch(`${API_BASE}/audit-logs/export${qs ? `?${qs}` : ''}`, {
    headers: {
      Authorization: `Bearer ${token}`,
    },
  });

  if (res.status === 401) {
    clearToken();
    window.location.href = '/login';
    throw new Error('Unauthorized');
  }

  if (!res.ok) throw new Error('Failed to export CSV');
  return res.blob();
}

export async function getBillingAccount(companyId?: number): Promise<BillingAccount> {
  const params = companyId ? `?company_id=${companyId}` : '';
  return request<BillingAccount>(`/billing/account${params}`);
}

export async function getBillingTransactions(params?: {
  limit?: number;
  offset?: number;
}): Promise<BillingTransaction[]> {
  const search = new URLSearchParams();
  if (params?.limit) search.set('limit', String(params.limit));
  if (params?.offset) search.set('offset', String(params.offset));
  const qs = search.toString();
  return request<BillingTransaction[]>(`/billing/transactions${qs ? `?${qs}` : ''}`);
}

export async function addFunds(companyId: number, amount: number, description?: string): Promise<BillingTransaction> {
  return request<BillingTransaction>('/billing/add-funds', {
    method: 'POST',
    body: JSON.stringify({ company_id: companyId, amount, description }),
  });
}

export async function getNotifications(): Promise<Notification[]> {
  return request<Notification[]>('/notifications');
}

export async function getUnreadCount(): Promise<{ count: number }> {
  return request<{ count: number }>('/notifications/unread-count');
}

export async function markNotificationRead(id: number): Promise<void> {
  return request<void>(`/notifications/${id}/read`, { method: 'PUT' });
}

export async function markAllNotificationsRead(): Promise<void> {
  return request<void>('/notifications/read-all', { method: 'PUT' });
}

export async function healthCheck(): Promise<{ status: string }> {
  return request<{ status: string }>('/health');
}
