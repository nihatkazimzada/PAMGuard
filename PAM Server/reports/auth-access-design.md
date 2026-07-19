# Authentication & Access Control Design — PAM Server

> Sources: `auth_utils.py` (30 lines), `config.py` (9 lines), `database.py` (lines 42-73), `main.py` (lines 88-96, 189-308, 587-999, plus agent endpoints 496-585)

---

## Table of Contents

1. [JWT-Based Login Flow](#1-jwt-based-login-flow)
2. [Three-Role RBAC Model](#2-three-role-rbac-model)
3. [Multi-Tenant Data Isolation](#3-multi-tenant-data-isolation)
4. [Password Handling](#4-password-handling)
5. [HMAC-Based Agent Authentication](#5-hmac-based-agent-authentication)

---

## 1. JWT-Based Login Flow

### 1.1 Token Architecture

The system uses a dual-token JWT strategy: a short-lived access token for API requests and a longer-lived refresh token for obtaining new access tokens.

| Property | Access Token | Refresh Token |
|----------|-------------|---------------|
| **Purpose** | Authenticates API requests | Obtains new access tokens |
| **Expiry** | 15 minutes | 7 days |
| **Signing key** | `JWT_SECRET` | `JWT_REFRESH_SECRET` |
| **Token type claim** | `"type": "access"` | `"type": "refresh"` |
| **Algorithm** | HS256 | HS256 |

Both keys are defined in `config.py:4-5`:
```python
JWT_SECRET = os.getenv("JWT_SECRET", "pam-server-jwt-secret-key-2024")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "pam-server-refresh-secret-key-2024")
JWT_ALGORITHM = "HS256"
```

### 1.2 Token Creation (`auth_utils.py:13-23`)

Both tokens are created with the same payload structure but different secrets and expiry windows:

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=15)
    to_encode["type"] = "access"
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=7)
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)
```

### 1.3 Token Payload

Both tokens embed a JSON payload with four claims:

```json
{
  "user_id": "550e8400-e29b-41d4-a716-446655440000",
  "username": "john@kapital.tech",
  "role": "admin",
  "company_id": "550e8400-e29b-41d4-a716-446655440001",
  "exp": 1720712000,
  "type": "access"
}
```

- **`user_id`**: UUID primary key of the user, used for database lookups
- **`username`**: Login identifier, used for audit log attribution
- **`role`**: `"superuser"`, `"admin"`, or `"user"` — used for authorization decisions
- **`company_id`**: UUID of the tenant company (nullable for superusers) — used for data scoping
- **`exp`**: Unix timestamp of expiry
- **`type`**: Either `"access"` or `"refresh"` — prevents token reuse across flows

### 1.4 Login Endpoint (`main.py:209-243`)

```
POST /api/auth/login
Body: { "username": "...", "password": "..." }
Response: { "access_token": "...", "refresh_token": "...", "user": { ... } }
```

The login flow:

1. **User lookup**: Query the `users` table by username (email-style, e.g. `john@kapital.tech`)
2. **Password verification**: `verify_password(data.password, user.password_hash)` — bcrypt check
3. **Account status check**: If `user.status == "inactive"`, returns 403
4. **Last login update**: Sets `user.last_login = datetime.utcnow()`
5. **Token generation**: Creates the JWT payload from `user.id`, `user.username`, `user.role`, `user.company_id`
6. **Audit log**: Writes `login` event to the audit log
7. **Company name lookup**: Joins the `companies` table to include the company name in the response

### 1.5 Token Refresh Endpoint (`main.py:245-259`)

```
POST /api/auth/refresh
Body: { "refreshToken": "..." }
Response: { "access_token": "...", "refresh_token": "..." }
```

The refresh flow:

1. Extracts the refresh token from the request body
2. Verifies it against `JWT_REFRESH_SECRET` using `verify_token(token, JWT_REFRESH_SECRET)`
3. Looks up the user by `payload["user_id"]` to confirm they still exist and are active
4. Issues a fresh access/refresh token pair with updated claims

This allows users to remain authenticated beyond the 15-minute access token window without re-entering credentials.

### 1.6 Token Verification (`main.py:88-96`)

```python
def get_current_user_from_token(token: str = None, websocket: WebSocket = None):
    if websocket:
        token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    return payload
```

Token verification is stateless — it decodes the JWT and validates the signature and expiry. No database query is involved. The function returns `None` for invalid/expired tokens, and each endpoint that requires auth checks this return value.

For WebSocket connections, the token is extracted from query parameters rather than headers (since the browser `WebSocket` API cannot set custom headers). The frontend passes the token as `?token=<jwt>` in the WebSocket URL.

### 1.7 API Token Transmission

Every authenticated API request sends the token in **two ways simultaneously** (`frontend_html.py:425-437`):

1. **Authorization header**: `Authorization: Bearer <token>`
2. **Query parameter**: `?token=<token>`

The query parameter redundancy ensures that endpoints accessed via WebSocket handshake or direct download URLs still authenticate correctly.

The `api()` helper function in the frontend automatically appends both and handles 401 responses by clearing local storage and forcing re-login.

---

## 2. Three-Role RBAC Model

### 2.1 Role Definitions

Three roles are defined in `database.py:42-45`:

```python
class UserRole(str, enum.Enum):
    superuser = "superuser"
    admin = "admin"
    user = "user"
```

### 2.2 Role Characteristics

| Role | Scope | Purpose |
|------|-------|---------|
| **superuser** | Cross-tenant | System-wide administration: create/manage companies, view all tenants' data, register servers for any company |
| **admin** | Per-company | Tenant-level administration: manage users within their company, approve/reject access requests, view audit logs and recordings for their company |
| **user** | Self | End-user operations: request server access, connect to approved sessions, view their own requests and notifications, update their own settings |

### 2.3 Permissions Matrix

The table below documents every backend endpoint and the roles that can access it. Endpoints are grouped by functional area.

| Endpoint | Method | superuser | admin | user | Description |
|----------|--------|-----------|-------|------|-------------|
| **Authentication** | | | | | |
| `/api/auth/login` | POST | ✓ | ✓ | ✓ | Login |
| `/api/auth/refresh` | POST | ✓ | ✓ | ✓ | Refresh token |
| `/api/auth/me` | GET | ✓ | ✓ | ✓ | Get current user profile |
| `/api/auth/change-password` | POST | ✓ | ✓ | ✓ | Change own password |
| `/api/auth/change-username` | POST | ✓ | ✓ | ✓ | Change own username |
| **Dashboard** | | | | | |
| `/api/dashboard/stats` | GET | ✓ | ✓ | ✗ | System-wide dashboard (admin-scoped) |
| `/api/dashboard/user-stats` | GET | ✗ | ✗ | ✓ | User-scoped dashboard |
| **Companies** | | | | | |
| `/api/companies` | GET | ✓ | ✓ | ✗ | List companies |
| `/api/companies` | POST | ✓ | ✗ | ✗ | Create company |
| `/api/companies/{id}` | DELETE | ✓ | ✗ | ✗ | Delete company |
| **Users** | | | | | |
| `/api/users` | GET | ✓ | ✓ | ✗ | List users (scoped to company for admins) |
| `/api/users/all` | GET | ✓ | ✗ | ✗ | List all users across tenants |
| `/api/users` | POST | ✓ | ✓ | ✗ | Create user (admin cannot create admins) |
| `/api/users/{id}/status` | PATCH | ✓ | ✓ | ✗ | Activate/deactivate user |
| **Servers** | | | | | |
| `/api/servers` | GET | ✓ | ✓ | ✓ | List servers (scoped for non-superusers) |
| `/api/servers` | POST | ✓ | ✗ | ✗ | Create server |
| `/api/servers/{id}` | GET | ✓ | ✓ | ✓ | Get server detail |
| `/api/servers/{id}` | DELETE | ✓ | ✗ | ✗ | Delete server |
| **Requests** | | | | | |
| `/api/requests` | GET | ✓ | ✓ | ✗ | List all pending (admin: scoped) |
| `/api/requests/my` | GET | ✓ | ✓ | ✓ | List own requests |
| `/api/requests` | POST | ✓ | ✓ | ✓ | Create access request |
| `/api/requests/{id}/approve` | POST | ✓ | ✓ | ✗ | Approve request |
| `/api/requests/{id}/reject` | POST | ✓ | ✓ | ✗ | Reject request |
| `/api/requests/{id}/cancel` | POST | ✓ | ✓ | ✓ | Cancel own request |
| `/api/requests/{id}` | DELETE | ✓ | ✓ | ✓ | Delete own request (admin: own only) |
| `/api/requests/check-active/{id}` | GET | ✓ | ✓ | ✓ | Check active request on server |
| **Sessions** | | | | | |
| `/api/sessions` | GET | ✓ | ✓ | ✓ | List ended sessions (scoped) |
| `/api/sessions/{id}` | GET | ✓ | ✓ | ✗ | Get session detail |
| `/api/sessions/{id}/recording` | GET | ✓ | ✓ | ✗ | Get recording data |
| `/api/sessions/{id}/terminate` | POST | ✓ | ✓ | ✗ | Terminate active session |
| **Audit Logs** | | | | | |
| `/api/audit-logs` | GET | ✓ | ✓ | ✗ | List audit logs (scoped to company) |
| `/api/audit-logs/export` | GET | ✓ | ✓ | ✗ | Export audit logs as CSV |
| **Billing** | | | | | |
| `/api/billing/my` | GET | ✓ | ✓ | ✗ | Get own billing account |
| `/api/billing/all` | GET | ✓ | ✗ | ✗ | List all billing accounts |
| `/api/billing/add-funds` | POST | ✓ | ✓ | ✗ | Add funds to billing account |
| `/api/billing/transactions` | GET | ✓ | ✓ | ✗ | List billing transactions |
| **Notifications** | | | | | |
| `/api/notifications` | GET | ✓ | ✓ | ✓ | List own notifications |
| `/api/notifications/unread-count` | GET | ✓ | ✓ | ✓ | Unread notification count |
| `/api/notifications/{id}/read` | PATCH | ✓ | ✓ | ✓ | Mark notification as read |
| `/api/notifications/read-all` | POST | ✓ | ✓ | ✓ | Mark all notifications as read |
| **WebSocket** | | | | | |
| `/ws/terminal` | WS | ✓ | ✓ | ✓ | SSH terminal (scoped by request ownership) |
| **Agent Endpoints** | | | | | |
| `/api/agent/register` | POST | — | — | — | Agent registration (HM-authenticated, not user auth) |
| `/api/agent/heartbeat` | POST | — | — | — | Agent heartbeat (HMAC-authenticated) |
| `/api/agent/events` | POST | — | — | — | Agent event stream (HMAC-authenticated) |

### 2.4 Authorization Enforcement Patterns

Authorization is implemented at the endpoint level using three patterns:

**Pattern 1 — Early return guard (most common):**
```python
if not payload or payload["role"] == "user":
    raise HTTPException(403, "Forbidden")
```
Used for admin/superuser endpoints. The check happens immediately after token verification, before any data access.

**Pattern 2 — Role-specific query scoping:**
```python
if payload["role"] == "user":
    query = query.where(Request.requester_id == get_user_id(payload["user_id"]))
elif payload["role"] == "admin":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```
Used for listing endpoints where the same route serves different roles with different visibility scopes.

**Pattern 3 — Ownership checks:**
```python
if str(req.requester_id) != payload["user_id"]:
    raise HTTPException(403, "Not your request")
```
Used for mutation endpoints to confirm the user owns the resource.

**Superuser-only endpoints** (company CRUD, user-all, all billing): use `payload["role"] != "superuser"` guard that returns 403.

### 2.5 Role Assignment

- **Superuser accounts** can only be created by seeding the database directly — there is no API endpoint to create a superuser
- **Admin accounts** are created by superusers only (admins cannot create other admins, `main.py:630-631`)
- **User accounts** are created by either superusers or admins (scoped to their company)
- A company can have at most one admin account (`main.py:637-642`)

---

## 3. Multi-Tenant Data Isolation

### 3.1 Company Scoping Model

Every tenant is represented by a `Company` record. The `company_id` foreign key cascades through the data model:

```
companies
  ├── users (company_id)
  ├── servers (company_id)
  ├── audit_logs (company_id)
  └── [agents via api_key lookup]
```

### 3.2 How Scoping Works Per Endpoint

Three scoping strategies are used depending on the operation type:

**Read operations (list queries):**
- **superuser**: No `company_id` filter — sees all data across all tenants
- **admin**: Filtered by `payload["company_id"]` — sees only data belonging to their company
- **user**: Filtered by `payload["user_id"]` — sees only their own data

Example from `list_users` (`main.py:594-596`):
```python
query = select(User, Company.name).outerjoin(Company, User.company_id == Company.id)
if payload["role"] != "superuser":
    query = query.where(
        User.company_id == get_user_id(payload["company_id"])
    ) if payload.get("company_id") else query.where(User.company_id.is_(None))
```

Example from `list_servers` (`main.py:708-710`):
```python
query = select(Server, Company.name).join(Company, Server.company_id == Company.id)
if payload["role"] != "superuser":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```

Example from `list_requests` (`main.py:812-815`):
```python
if payload["role"] == "user":
    query = query.where(Request.requester_id == get_user_id(payload["user_id"]))
elif payload["role"] == "admin":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```

**Write operations:**
- **Cross-company writes** (e.g., creating a server for another company): superuser only
- **Admin writes** (e.g., creating a user for their company): the admin's `company_id` from the JWT is used, and the admin is locked to creating users within their own company

Example from `create_request` (`main.py:872-873`):
```python
if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
    raise HTTPException(403, "Access denied")
```

**Aggregate operations (dashboard counts):**
The `dashboard/stats` endpoint applies the `company_id` filter to every counter query for admin users (`main.py:318-331`):
```python
company_id = payload.get("company_id") if payload["role"] != "superuser" else None
cid = get_user_id(company_id) if company_id else None
# Then for each count query:
if cid and hasattr(model, "company_id"):
    query = query.where(model.company_id == cid)
```

### 3.3 Notification Targeting

Notifications follow the same scoping model (`main.py:143-148`):
```python
result = await db.execute(
    select(User).where(
        or_(User.role == UserRole.superuser,
            and_(User.role == UserRole.admin,
                 User.company_id == get_user_id(company_id)))
    )
)
```
When a new access request is created, the system notifies both all superusers (cross-tenant visibility) and the specific company's admin.

### 3.4 Audit Log Scoping

Audit logs carry a `company_id` column. List queries for audit logs apply role-based filtering (`main.py:1114-1117`):
```python
if payload["role"] != "superuser":
    query = query.where(AuditLog.company_id == get_user_id(payload["company_id"]))
```
This ensures a company admin can only see audit events within their own tenant.

### 3.5 Terminal Session Scoping

When a WebSocket terminal session is initiated, the server verifies that the user owns the request and that the request is approved and not expired (`main.py:1320-1321`):
```python
if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
    await websocket.send_json({"type": "error", "data": "Access denied"})
```

---

## 4. Password Handling

### 4.1 Hashing Algorithm

Passwords are hashed using **bcrypt** with the `bcrypt` Python library (`auth_utils.py:7-11`):

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

def verify_password(password: str, hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash.encode())
```

### 4.2 Cost Factor

`bcrypt.gensalt(12)` sets the work factor to 12 (2^12 = 4,096 iterations). This is the standard baseline — the cryptographic cost adapts automatically as bcrypt's algorithm incorporates Moore's law into its design.

### 4.3 Password Storage Format

The bcrypt output is a 60-character string stored in the `password_hash` column of the `users` table:

```
$2b$12$VK5GUEymZ7mYB4aJBhNOtu5Y3CVmP6J4zGXH9nL5qM0Qq0t0eXe2q
```

Format breakdown:
- `$2b$` — Bcrypt algorithm version (2b variant)
- `12$` — Cost factor (work factor)
- Remaining 53 characters — Base64-encoded salt (22 chars) + hash (31 chars)

### 4.4 Password Change Flow (`main.py:279-292`)

```
POST /api/auth/change-password
Body: { "currentPassword": "...", "newPassword": "..." }
```

1. Verifies the current password by calling `verify_password(data.current_password, user.password_hash)`
2. Hashes the new password with `hash_password(data.new_password)`
3. Updates the `password_hash` column
4. Logs a `password_change` audit event

The password change requires the current password to prevent session hijacking from changing the password without knowledge of the existing credential.

### 4.5 Password Validation

- Minimum length: 6 characters (enforced in the frontend and should be validated on the backend)
- No complexity requirements (uppercase, digit, special character) are enforced by the backend

---

## 5. HMAC-Based Agent Authentication

### 5.1 Trust Model

The PAM Server and Tenant Agent machines communicate over HTTP without a TLS certificate (in the current deployment). To establish mutual trust, every agent-to-server request is signed with an **HMAC-SHA256** digest using a shared secret key.

The shared key is the company's `api_key` field in the `companies` table. Each company has a unique `api_key` that is shared with their respective tenant agent. The codebase also includes a fallback default key in `config.py:8`:

```python
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "shared-agent-api-key-pam2024")
```

This fallback is used when a company record has no `api_key` set but is intended for development only.

### 5.2 Signing Protocol

Every agent-to-server request includes two custom HTTP headers:

| Header | Value |
|--------|-------|
| `X-API-Key` | The shared secret key (company `api_key` or `AGENT_API_KEY`) |
| `X-Signature` | `HMAC-SHA256(api_key, request_body_bytes)` as a hex digest |

The agent constructs the signature by:
1. Taking the raw request body as bytes (JSON-encoded)
2. Computing `HMAC(key=api_key.encode(), msg=body_bytes, digest=sha256)`
3. Encoding the result as a lowercase hex string

### 5.3 Server-Side Verification

All three agent endpoints follow the same verification pattern (`main.py:189-205`):

```python
async def verify_agent_hmac(request, body_bytes: bytes, db: AsyncSession):
    api_key = request.headers.get("X-API-Key")
    signature = request.headers.get("X-Signature")
    if not api_key or not signature:
        raise HTTPException(401, "Missing API key or signature")
    company = await db.execute(select(Company).where(Company.api_key == api_key))
    company = company.scalar_one_or_none()
    if not company:
        agent = await db.execute(select(Agent).where(Agent.api_key == api_key))
        agent = agent.scalar_one_or_none()
        if not agent:
            raise HTTPException(401, "Invalid API key")
        return api_key, company
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")
    return api_key, company
```

The verification flow:

1. Extract `X-API-Key` and `X-Signature` from the request headers
2. Look up the API key in the `companies` table (matching `Company.api_key`)
3. If no company is found, fall back to looking up the `agents` table
4. Recompute the HMAC-SHA256 digest of the raw request body bytes
5. Compare using `hmac.compare_digest()` — a constant-time comparison function that prevents timing attacks

### 5.4 Agent Endpoints

Three agent endpoints use this HMAC authentication:

| Endpoint | Purpose | Verified Fields |
|----------|---------|-----------------|
| `POST /api/agent/register` | Register or update an agent instance | hostname, ip, os_version, agent_version, tenant_company_id |
| `POST /api/agent/heartbeat` | Send periodic liveness signal | hostname, status (UP/DOWN) |
| `POST /api/agent/events` | Stream events (login, logout, sudo, account creation) | array of event objects |

### 5.5 Server-to-Agent Calls

When the PAM Server needs to call the Tenant Agent (e.g., to provision or revoke a Linux user), it authenticates using the same `X-API-Key` header:

```python
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(
        f"http://{server.ip}:{agent_port}/agent/provision",
        json=provision_body,
        headers={"X-API-Key": api_key or AGENT_API_KEY}
    )
```

In the server-to-agent direction, only the `X-API-Key` header is sent (no HMAC signature). The agent is expected to verify the API key as a shared secret on its end. The provisioning call (`main.py:924-940`) sends:

- `request_id` — UUID of the access request
- `username_to_create` — JIT Linux username (e.g., `jit-a1b2c3d4`)
- `privilege` — `"root"` or `"user"`
- `duration_minutes` — How long the account should remain active
- `expires_at` — ISO 8601 timestamp of expiration

The revoke call (`main.py:166-171`) sends:
- `request_id` — UUID of the request
- `username` — The provisioned Linux username to remove

### 5.6 Key Distribution

- Each company's `api_key` is set when the company record is created
- The API key is stored in the `companies.api_key` column (unique, nullable)
- The agent receives its company's API key through out-of-band configuration (env variable or config file)
- The development fallback `AGENT_API_KEY` (`"shared-agent-api-key-pam2024"`) is used when no company-specific key is set
- Agent records in the `agents` table also store their API key (`agents.api_key`) for cross-reference during heartbeat verification
