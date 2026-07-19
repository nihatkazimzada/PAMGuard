export interface User {
  id: number;
  username: string;
  email: string;
  role: 'admin' | 'manager' | 'user';
  status: 'active' | 'inactive';
  company_id: number | null;
  company_name?: string;
  created_at: string;
  updated_at: string;
}

export interface Company {
  id: number;
  name: string;
  tenant_id?: string;
  domain?: string;
  industry?: string;
  contact_email?: string;
  contact_phone?: string;
  billing_email?: string;
  user_count?: number;
  server_count?: number;
  created_at: string;
}

export interface Server {
  id: number;
  hostname: string;
  ip_address: string;
  port: number;
  os: string;
  company_id: number;
  company_name?: string;
  created_at: string;
  updated_at: string;
}

export type RequestStatus = 'pending' | 'approved' | 'rejected' | 'expired' | 'cancelled';

export interface Request {
  id: number;
  user_id: number;
  username?: string;
  server_id: number;
  server_hostname?: string;
  server_ip?: string;
  reason: string;
  status: RequestStatus;
  approved_by: number | null;
  approved_by_username?: string;
  approved_at: string | null;
  expires_at: string;
  created_at: string;
  updated_at: string;
}

export interface Session {
  id: number;
  user_id: number;
  username?: string;
  server_id: number;
  server_hostname?: string;
  server_ip?: string;
  request_id: number;
  session_type: 'ssh' | 'rdp' | 'vnc';
  status: 'active' | 'terminated' | 'expired';
  started_at: string;
  ended_at: string | null;
  recording_path: string | null;
}

export interface AuditLog {
  id: number;
  user_id: number;
  username?: string;
  action: string;
  target_type: string;
  target_id: number | null;
  details: string | null;
  ip_address: string | null;
  created_at: string;
}

export interface Notification {
  id: number;
  user_id: number;
  title: string;
  message: string;
  type: 'info' | 'success' | 'warning' | 'error';
  read: boolean;
  created_at: string;
}

export interface BillingAccount {
  id: number;
  company_id: number;
  company_name?: string;
  balance: number;
  currency: string;
  created_at: string;
  updated_at: string;
}

export interface BillingTransaction {
  id: number;
  billing_account_id: number;
  amount: number;
  type: 'credit' | 'debit';
  description: string;
  reference_type: string | null;
  reference_id: number | null;
  created_at: string;
}

export interface DashboardStats {
  active_sessions: number;
  pending_requests: number;
  total_servers: number;
  total_users: number;
  recent_activity: AuditLog[];
  num_admins: number;
  num_companies: number;
  companies: { name: string; user_count: number }[];
  total_regular_users: number;
  total_requests: number;
  critical_alerts: number;
  warning_alerts: number;
  failed_logins: { hour: string; count: number }[];
}

export interface LoginResponse {
  token: string;
  user: User;
}

export interface ApiError {
  error: string;
  message?: string;
}
