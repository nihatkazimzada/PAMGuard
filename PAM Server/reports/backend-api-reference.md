# Backend API Reference — PAM Server

> Generated from `main.py` (1563 lines) at `/home/administrator/pam-server/backend-python/`  
> 49 endpoints across 11 route groups + WebSocket + static file serving

---

## Authentication Mechanism

All API endpoints except login, refresh, health, and frontend serving require a JWT access token. The token is passed as a query parameter `?token=` on every request:

```
GET /api/servers?token=eyJhbGciOiJIUzI1NiIs...
POST /api/requests?token=eyJhbGciOiJIUzI1NiIs...
```

The backend extracts the token via `Query(None)` and decodes it with `python-jose`:

```python
payload = verify_token(token)
if not payload:
    raise HTTPException(401, "Not authenticated")
```

The JWT payload contains three claims used for authorization:

```json
{
  "user_id": "uuid-string",
  "username": "user@example.com",
  "role": "superuser | admin | user",
  "company_id": "uuid-string | null",
  "exp": 1700000000,
  "type": "access"
}
```

**Access tokens** expire in 15 minutes. **Refresh tokens** (7-day expiry) are obtained at login and exchanged for new access tokens via `POST /api/auth/refresh`. This design keeps the credentials-in-flight window short while avoiding frequent re-prompting for credentials.

Three roles enforce data scoping:
- **superuser** — cross-company access, can manage companies, servers, and all users
- **admin** — per-company access, can manage company users, approve requests, view sessions
- **user** — can access assigned servers, create requests, use the terminal

---

## 1. Auth Routes

Base path: `/api/auth`

Four endpoints manage authentication and session lifecycle. The fifth (`/api/auth/me`) returns the current user's profile.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 1 | POST | `/api/auth/login` | None | None | `LoginRequest` `{username: str, password: str}` | `{access_token: str, refresh_token: str, user: {id, fullName, username, role, companyId, companyName, status}}` |
| 2 | POST | `/api/auth/refresh` | None (body) | None | `{"refreshToken": str}` | `{access_token: str, refresh_token: str}` |
| 3 | GET | `/api/auth/me` | `?token=` | Any | — | `{id, fullName, username, role, companyId, companyName, status}` |
| 4 | POST | `/api/auth/change-password` | `?token=` | Any | `PasswordChange` `{current_password: str, new_password: str}` | `{"message": "Password changed successfully"}` |
| 5 | POST | `/api/auth/change-username` | `?token=` | Any | `UsernameChange` `{new_username: str}` | `{"message": "Username changed successfully"}` |

**Purpose:** These endpoints handle the full auth lifecycle — credential validation, token issuance, profile retrieval, and self-service credential updates. The `/refresh` endpoint uses a separate JWT secret (`JWT_REFRESH_SECRET`) so that refresh token compromise does not automatically expose access token signing capabilities.

**Usage flow:** Login once → store both tokens → use access token for all requests → when access token expires, call `/refresh` with the refresh token → repeat.

---

## 2. Dashboard Routes

Base path: `/api/dashboard`

Two endpoints return aggregated statistics. The admin/superuser dashboard includes company-wide metrics and security alerts; the user dashboard shows personal request counts and activity.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 6 | GET | `/api/dashboard/stats` | `?token=` | admin, superuser | — | `{adminCount, companyCount, companies: [{id, name, user_count}], userCount, requestCount, serverCount, activeSessionCount, criticalCount, highCount, failedLogins: [{hour, count}], recentActivities: [{timestamp, event_type, performed_by, action_detail, security_status}]}` |
| 7 | GET | `/api/dashboard/user-stats` | `?token=` | any | — | `{pendingCount, approvedCount, activeSessionCount, serverCount, recentRequests: [{id, server_name, server_ip, access_level, status, duration_minutes, description, requested_at}], recentActivities: [{timestamp, event_type, action_detail, security_status}]}` |

**Purpose:** Provides the data backing the two dashboard views in the frontend. The admin dashboard highlights security posture (critical/high alert counts, failed login trends over 24 hours), while the user dashboard focuses on their pending and approved requests.

---

## 3. Company Routes

Base path: `/api/companies`

CRUD for tenant companies. Only superusers can manage companies. Each company has a unique `tenant_id`, an auto-generated API key for agent communication, and optional billing and contact fields.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 8 | GET | `/api/companies` | `?token=` | superuser | — | `[{id, name, tenant_id, domain, industry, contact_email, contact_phone, billing_email, api_key, server_count, user_count}]` |
| 9 | POST | `/api/companies` | `?token=` | superuser | `CompanyCreate` `{name, tenant_id, domain?, industry?, contact_email, contact_phone?, billing_email?}` | `{id, name, tenant_id, api_key}` |
| 10 | DELETE | `/api/companies/{company_id}` | `?token=` | superuser | — | `{"message": "Company deleted"}` |

**Purpose:** Each company represents an independent tenant. Data isolation is enforced at the query level by filtering on `company_id`. The API key returned at creation time is used by the tenant agent to sign its requests via HMAC-SHA256.

---

## 4. Agent Routes

Base path: `/api/agent`

These three endpoints are called by the Tenant Agent running on managed VMs. They are authenticated via API key + HMAC-SHA256 signature (not JWT). The agent sends its company's API key in the `X-API-Key` header and signs the request body with `HMAC-SHA256(api_key, body)` in the `X-Signature` header.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 11 | POST | `/api/agent/register` | HMAC (X-API-Key + X-Signature) | agent | `{hostname, ip, os_version?, tenant_company_id?, agent_version?}` | `{"message": "Agent registered", "hostname": \<hostname\>}` |
| 12 | POST | `/api/agent/heartbeat` | HMAC (X-API-Key + X-Signature) | agent | `{hostname, status?, load?, last_activity?, uptime_seconds?}` | `{"message": "Heartbeat received"}` |
| 13 | POST | `/api/agent/events` | HMAC (X-API-Key + X-Signature) | agent | `{events: [{event_type, hostname, username?, detail?, timestamp?}]}` or single event object | `{"message": "X events recorded"}` |

**Purpose:** The agent lifecycle — registration on first start, periodic heartbeats to track liveness, and event streaming for actions like account creation, login failures, and sudo usage. Events are written to the audit log with the appropriate `security_status` classification.

---

## 5. User Routes

Base path: `/api/users`

User management endpoints. Admins can create users within their own company (user role only — admins cannot create other admins). Superusers can create users in any company and can assign admin or user roles.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 14 | GET | `/api/users` | `?token=` | any | — (implicitly scoped to own company for non-superusers) | `[{id, full_name, username, role, company_id, company_name, status, last_login}]` |
| 15 | GET | `/api/users/all` | `?token=` | superuser | — | `[{id, full_name, username, role, company_id, company_name, status, last_login}]` |
| 16 | POST | `/api/users` | `?token=` | admin, superuser | `UserCreate` `{full_name, username, password, role?, company_id?}` | `{id, full_name, username, role, company_id}` |
| 17 | PATCH | `/api/users/{user_id}/status` | `?token=` | admin, superuser | `{"status": "active" | "inactive"}` | `{"message": "User activated/deactivated successfully"}` |

**Purpose:** User administration follows the multi-tenant model — `GET /api/users` returns only the requesting user's company users (unless superuser). The create endpoint deducts the billing account balance if configured. Admin users cannot modify other admin accounts.

---

## 6. Server Routes

Base path: `/api/servers`

Target server management. Servers represent the SSH-accessible machines that users can request access to. Each server belongs to a company and stores connection metadata.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 18 | GET | `/api/servers` | `?token=` | any | — (query: `company_id?`, `status?`) | `[{id, name, ip, company_id, company_name, status, port?*, os?*, allowed_connection_types?*}]` |
| 19 | POST | `/api/servers` | `?token=` | superuser | `ServerCreate` `{name, ip, port, allowed_connection_types, os, company_id}` | `{id, name, ip, status}` |
| 20 | GET | `/api/servers/{server_id}` | `?token=` | any | — | `{id, name, ip, company_id, company_name, status, port?*, os?*, allowed_connection_types?*}` |
| 21 | DELETE | `/api/servers/{server_id}` | `?token=` | superuser | — | `{"message": "Server deleted"}` |

> *Fields marked with `*` are omitted from the response for users with the `user` role. Only admins and superusers see port, OS, and allowed connection types.

**Purpose:** Servers are the access targets. The list endpoint applies role-based field masking so that end users see only the server name and IP — connection details are hidden until access is approved. After creation, `check_server_connectivity()` runs asynchronously to test reachability and update the server status.

---

## 7. Request Routes

Base path: `/api/requests`

The core access workflow — users create requests, admins approve or reject them, and the system provisions JIT user accounts on the target servers.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 22 | GET | `/api/requests` | `?token=` | any | — (query: `status?`, `requester_id?`) | `[{id, requester_id, requester_name, requester_username, server_id, server_name, server_ip, company_name, company_id, access_level, duration_minutes, description, status, requested_at, approved_at, approved_by, expires_at}]` |
| 23 | GET | `/api/requests/my` | `?token=` | any | — (query: `status?`) | `[{... same shape as above ...}]` |
| 24 | POST | `/api/requests` | `?token=` | any | `RequestCreate` `{server_id, access_level, duration_minutes, description?}` | `{id, status}` |
| 25 | POST | `/api/requests/{request_id}/approve` | `?token=` | admin, superuser | — | `{"message": "Request approved"}` |
| 26 | POST | `/api/requests/{request_id}/reject` | `?token=` | admin, superuser | — | `{"message": "Request rejected"}` |
| 27 | POST | `/api/requests/{request_id}/cancel` | `?token=` | any (own only) | — | `{"message": "Request cancelled"}` |
| 28 | DELETE | `/api/requests/{request_id}` | `?token=` | any (own only) | — | `{"message": "Request deleted"}` |
| 29 | GET | `/api/requests/check-active/{server_id}` | `?token=` | any | — | `{"hasActive": bool, "request": {id} \| null}` |

**Purpose:** The request lifecycle is the central business flow. A user creates a request → admin approves → the system provisions a JIT user on the target server → the user connects via the terminal → on expiry or cancellation, the JIT user is revoked. The `check-active` endpoint allows the frontend to skip the request form if the user already has an active approved request for a given server.

---

## 8. Session Routes

Base path: `/api/sessions`

Session records track each terminal connection. They store start/end times, link to the originating request, and capture the full terminal recording.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 30 | GET | `/api/sessions` | `?token=` | any | — | `[{id, request_id, user_id, user_name, user_username, server_id, server_name, server_ip, company_name, started_at, ended_at, status}]` |
| 31 | GET | `/api/sessions/{session_id}` | `?token=` | any | — | `{id, request_id, user_id, user_name, user_username, server_id, server_name, server_ip, server_port, company_name, access_level, started_at, ended_at, status}` |
| 32 | GET | `/api/sessions/{session_id}/recording` | `?token=` | admin, superuser | — | `{"recording": [{timestamp, event, data}, ...]}` |
| 33 | POST | `/api/sessions/{session_id}/terminate` | `?token=` | any (own), admin, superuser | — | `{"message": "Session terminated"}` |

**Purpose:** Sessions are created by the WebSocket terminal handler when a user connects. They are read-only through the REST API — the terminate action is the only write operation. Recordings are stored as JSON arrays and can be replayed in the frontend.

---

## 9. Audit Log Routes

Base path: `/api/audit-logs`

Read-only access to the audit trail. Supports filtering, pagination, and CSV export.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 34 | GET | `/api/audit-logs` | `?token=` | admin, superuser | — (query: `event_type?`, `performed_by?`, `security_status?`, `date_from?`, `date_to?`, `company_id?`, `limit?`, `offset?`) | `{"rows": [{id, timestamp, event_type, performed_by, target, action_detail, company_id, security_status, source}], "total": int}` |
| 35 | GET | `/api/audit-logs/export` | `?token=` | admin, superuser | — (query: same filters) | CSV file download (`Content-Type: text/csv`) |

**Purpose:** Every security-relevant action writes to the audit log. The list endpoint supports pagination (`limit`/`offset`, default 50) and filtering by multiple criteria. The export endpoint returns up to 10,000 rows as a CSV file. Both endpoints scope data by the requesting admin's company (unless superuser).

---

## 10. Billing Routes

Base path: `/api/billing`

Simple billing system. Each admin has a billing account with a balance and a per-user price. Creating a user deducts from the balance if configured.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 36 | GET | `/api/billing/my` | `?token=` | admin, superuser | — | `{id, admin_user_id, balance, price_per_user}` |
| 37 | GET | `/api/billing/transactions` | `?token=` | admin, superuser | — | `[{id, amount, reason, created_at}]` |
| 38 | POST | `/api/billing/add-funds` | `?token=` | admin, superuser | `AddFundsRequest` `{amount, reason?}` | `{id, balance, price_per_user}` |
| 39 | GET | `/api/billing/all` | `?token=` | superuser | — | `[{id, admin_name, admin_username, company_name, balance, price_per_user}]` |

**Purpose:** Tracks per-admin billing balances. New accounts are auto-created with a $100 balance and $5/user price on first access. The `all` endpoint provides superuser visibility into all billing accounts.

---

## 11. Notification Routes

Base path: `/api/notifications`

In-app notification system. Notifications are created by the backend on events (request created, approved, rejected, etc.) and delivered to the user's notification list. The frontend also receives real-time push notifications via WebSocket when the user has an active connection.

| # | Method | Path | Auth | Required Role | Request Body | Response Shape |
|---|--------|------|------|---------------|--------------|----------------|
| 40 | GET | `/api/notifications` | `?token=` | any | — (query: `limit?`, default 50) | `[{id, type, message, link, read, created_at}]` |
| 41 | GET | `/api/notifications/unread-count` | `?token=` | any | — | `{"count": int}` |
| 42 | PATCH | `/api/notifications/{notification_id}/read` | `?token=` | any | — | `{"message": "Marked as read"}` |
| 43 | POST | `/api/notifications/read-all` | `?token=` | any | — | `{"message": "All marked as read"}` |

**Purpose:** Keeps users informed of status changes without external email. The unread count drives the badge on the notification bell in the frontend. The `read-all` endpoint uses a single UPDATE query to mark all of a user's notifications as read in one operation.

---

## 12. WebSocket Terminal

Path: `ws://host/ws/terminal`

| # | Method | Path | Auth | Required Role | Message Flow |
|---|--------|------|------|---------------|--------------|
| 44 | WebSocket | `/ws/terminal` | `?token=` query param | any (with approved request) | Client → Server: JSON `{action, ...}`, Server → Client: JSON `{type, data, ...}` |

**Authentication:** The JWT access token is passed as a query parameter because the browser `WebSocket` API does not support custom headers: `ws://10.0.2.20:3001/ws/terminal?token=eyJ...`

**Client-to-Server Messages:**

| Action | Payload | Purpose |
|--------|---------|---------|
| `join_session` | `{"action": "join_session", "requestId": str, "serverId": str}` | Start a new terminal session |
| `reconnect_session` | `{"action": "reconnect_session", "sessionId": str}` | Reconnect to an existing active session |
| `terminal_input` | `{"type": "terminal_input", "data": str}` | Send keystrokes / commands to the SSH process |
| `terminate_session` | `{"type": "terminate_session"}` | End the current session |
| `close_session` | `{"type": "close_session"}` | Close the session gracefully |

**Server-to-Client Messages:**

| Type | Payload | Purpose |
|------|---------|---------|
| `session_created` | `{"type": "session_created", "data": {"sessionId": str}}` | Confirms the session was created in the database |
| `ssh_ready` | `{"type": "ssh_ready"}` | SSH connection established, shell is ready for input |
| `terminal_output` | `{"type": "terminal_output", "data": str}` | Output from the SSH process (stdout or stderr) |
| `session_ended` | `{"type": "session_ended", "data": {"reason": str}}` | Session has ended (disconnect, expiry, terminate) |
| `session_error` | `{"type": "session_error", "data": str}` | An error occurred during the session |
| `error` | `{"type": "error", "data": str}` | Generic error (auth failure, server not found, etc.) |
| `session_reconnected` | `{"type": "session_reconnected", "data": {"sessionId": str}}` | Confirms reconnection to an existing session |

**Purpose:** The terminal WebSocket is the real-time SSH proxy. All keystrokes are forwarded to the target server's SSH process, and all output is streamed back to the client. The backend records every character, detects suspicious activity in both input and output streams, and enforces session expiry.

---

## 13. Frontend & Utility Endpoints

| # | Method | Path | Auth | Purpose |
|---|--------|------|------|---------|
| 45 | GET | `/` | None | Serves the embedded SPA (single-page application from `frontend_html.py`) |
| 46 | GET | `/index.html` | None | Same as `/` — alternative path for direct index.html requests |
| 47 | GET | `/api/health` | None | Returns `{"status": "ok", "timestamp": "..."}` for monitoring |
| 48 | GET | `/api/download-project` | None | Downloads `LAST_PAM_PROJECT.zip` — full project archive |
| 49 | GET | `/api/download-report` | None | Downloads `report.md` — project documentation |

**Purpose:** The frontend is served directly by FastAPI as an HTML string, eliminating the need for a separate web server or build step in development. The health endpoint is used by startup scripts to verify the backend is ready. Download endpoints provide convenient access to project artifacts.

---

## 5-6 Key Endpoint Examples

### Example 1: Login

```
POST /api/auth/login
Content-Type: application/json

{
  "username": "nihat.kazimzada@example.com",
  "password": "nihat123"
}
```

Response (200):

```json
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "user": {
    "id": "a1b2c3d4-...",
    "fullName": "Nihat Kazimzada",
    "username": "nihat.kazimzada@example.com",
    "role": "superuser",
    "companyId": null,
    "companyName": null,
    "status": "active"
  }
}
```

### Example 2: Create an Access Request

```
POST /api/requests?token=eyJhbGciOiJIUzI1NiIs...
Content-Type: application/json

{
  "server_id": "550e8400-e29b-41d4-a716-446655440000",
  "access_level": "user",
  "duration_minutes": 30,
  "description": "Need to check application logs"
}
```

Response (200):

```json
{
  "id": "660e8400-e29b-41d4-a716-446655440001",
  "status": "pending"
}
```

### Example 3: Approve a Request

```
POST /api/requests/660e8400-e29b-41d4-a716-446655440001/approve?token=eyJhbGciOiJIUzI1NiIs...
```

Response (200):

```json
{
  "message": "Request approved"
}
```

**What happens server-side:** The request status changes to `approved`, an `expires_at` timestamp is set to `now + duration_minutes`, the requester is notified, and the backend attempts to provision a JIT user on the target server by calling `POST http://{server.ip}:8800/agent/provision`. If provisioning succeeds, the request record is updated with `provisioned_username` and `ssh_private_key`.

### Example 4: WebSocket — Join Session

Client connects:

```
ws://10.0.2.20:3001/ws/terminal?token=eyJhbGciOiJIUzI1NiIs...
```

Client sends:

```json
{
  "action": "join_session",
  "requestId": "660e8400-e29b-41d4-a716-446655440001",
  "serverId": "550e8400-e29b-41d4-a716-446655440000"
}
```

Server responds (in order):

```json
{"type": "session_created", "data": {"sessionId": "770e8400-e29b-41d4-a716-446655440002"}}
```

```json
{"type": "ssh_ready"}
```

Then bidirectional streaming begins:

```json
// Client → Server (on every Enter press):
{"type": "terminal_input", "data": "ls -la\n"}

// Server → Client (continuously):
{"type": "terminal_output", "data": "total 24\ndrwxr-xr-x 2 root root 4096 ..."}
```

### Example 5: List Audit Logs with Pagination

```
GET /api/audit-logs?token=eyJhbGciOiJIUzI1NiIs...&limit=5&offset=0&security_status=critical
```

Response (200):

```json
{
  "rows": [
    {
      "id": "880e8400-...",
      "timestamp": "2026-07-11 16:50:20.251341",
      "event_type": "suspicious_command",
      "performed_by": "rashad.guliyev@example.com",
      "target": "770e8400-...",
      "action_detail": "Suspicious command: Privilege escalation: sudo command used",
      "company_id": "990e8400-...",
      "security_status": "critical",
      "source": "pam-server"
    }
  ],
  "total": 1
}
```

### Example 6: Register an Agent (HMAC-signed)

```
POST /api/agent/register
X-API-Key: pam_kapital_627649a1049d
X-Signature: <hmac-sha256-of-body>
Content-Type: application/json

{
  "hostname": "linux-tenant-kapital",
  "ip": "10.0.2.21",
  "os_version": "Ubuntu 22.04.5 LTS",
  "tenant_company_id": "kapital-tech",
  "agent_version": "1.0.0"
}
```

Response (200):

```json
{
  "message": "Agent registered",
  "hostname": "linux-tenant-kapital"
}
```

**Signature calculation:** The agent computes `HMAC-SHA256(api_key, request_body_bytes)` and sends the hex digest as the `X-Signature` header. The backend recomputes the expected signature using the stored API key and compares it with `hmac.compare_digest()`.

---

## Endpoint Summary

| Group | Count | Path Prefix |
|-------|-------|-------------|
| Auth | 5 | `/api/auth/*` |
| Dashboard | 2 | `/api/dashboard/*` |
| Companies | 3 | `/api/companies*` |
| Agent | 3 | `/api/agent/*` |
| Users | 4 | `/api/users*` |
| Servers | 4 | `/api/servers*` |
| Requests | 8 | `/api/requests*` |
| Sessions | 4 | `/api/sessions*` |
| Audit Logs | 2 | `/api/audit-logs*` |
| Billing | 4 | `/api/billing/*` |
| Notifications | 4 | `/api/notifications*` |
| WebSocket | 1 | `/ws/terminal` |
| Frontend | 2 | `/`, `/index.html` |
| Utility | 3 | `/api/health`, `/api/download-project`, `/api/download-report` |
| **Total** | **49** | |
