# Backend Deep-Dive: PAM Server (main.py)

> Generated from codebase snapshot at `/home/administrator/pam-server/backend-python/`  
> Total backend LOC: ~1563 lines across `main.py`, `schemas.py` (85 lines), `auth_utils.py` (30 lines), `config.py` (9 lines), `database.py` (199 lines)

---

## 1. Full Endpoint Catalogue

### 1.1 Conventions Used Across All Endpoints

- **Auth mechanism**: JWT passed as `?token=<jwt>` query parameter on every request (except `/api/auth/login`, `/api/auth/refresh`, `/api/health`)
- **Token verification**: `get_current_user_from_token()` returns `None` on invalid/missing token → `401` (unless the endpoint explicitly checks and raises `HTTPException(401, "Not authenticated")`)
- **Role scoping**: `payload["role"]` is checked against `"superuser"`, `"admin"`, `"user"`; `company_id` is extracted from the JWT payload for multi-tenant isolation
- **Database sessions**: Injected via `Depends(get_db)` which yields an `AsyncSession` from `async_session` (SQLAlchemy async)
- **Error uniformity**: All errors are `HTTPException(status_code, detail)` — no custom exception classes, no global handler

---

### 1.2 Auth Routes (`/api/auth/*`)

| # | Method | Path | Auth Required | Role Required | Request Body | Response Shape | Error Codes & Conditions |
|---|---|---|---|---|---|---|---|
| 1 | `POST` | `/api/auth/login` | None | None | `LoginRequest` `{username: str, password: str}` | `{access_token: str, refresh_token: str, user: {...}}` | **400**: missing fields (Pydantic validation). **401**: wrong username/password. **403**: account deactivated |
| 2 | `POST` | `/api/auth/refresh` | None (refresh token in body) | None | `{"refreshToken": str}` | `{access_token: str, refresh_token: str}` | **400**: missing refreshToken. **401**: invalid/expired token or user inactive |
| 3 | `GET` | `/api/auth/me` | Yes | Any | N/A | `{id, fullName, username, role, companyId, companyName, status}` | **401**: not authenticated. **404**: user not found (deleted between token issue and request) |
| 4 | `POST` | `/api/auth/change-password` | Yes (`?token=`) | Any | `PasswordChange` `{current_password: str, new_password: str}` | `{"message": "Password changed successfully"}` | **401**: not authenticated. **400**: current password is incorrect |
| 5 | `POST` | `/api/auth/change-username` | Yes (`?token=`) | Any | `UsernameChange` `{new_username: str}` | `{"message": "Username changed successfully"}` | **401**: not authenticated. **400**: username already taken |

**Detailed error conditions for `POST /api/auth/login` (line 209–243):**
```python
if not user or not verify_password(data.password, user.password_hash):
    await log_audit(db, "login_failed", data.username, security_status="warning")
    raise HTTPException(401, "Invalid username or password")  # ← 401

if user.status == UserStatus.inactive:
    raise HTTPException(403, "Account is deactivated")        # ← 403
```

**`POST /api/auth/refresh` (line 245–259):**
```python
payload = verify_token(token, JWT_REFRESH_SECRET)           # uses separate secret!
if not payload:
    raise HTTPException(401, "Invalid refresh token")         # ← 401 on expired/invalid
```

---

### 1.3 Dashboard Routes (`/api/dashboard/*`)

| # | Method | Path | Auth | Role | Request Body | Response Shape | Error Codes |
|---|---|---|---|---|---|---|---|
| 6 | `GET` | `/api/dashboard/stats` | Yes (`?token=`) | admin, superuser | N/A | `{adminCount, companyCount, userCount, requestCount, serverCount, activeSessionCount, criticalCount, highCount, companies: [...], failedLogins: [...], recentActivities: [...]}` | **403**: user role not allowed (`payload["role"] == "user"` → 403) |
| 7 | `GET` | `/api/dashboard/user-stats` | Yes (`?token=`) | any | N/A | `{pendingCount, approvedCount, activeSessionCount, serverCount, recentRequests: [...], recentActivities: [...]}` | **401**: not authenticated. Never 403 (all roles allowed) |

**Line 315–316 — forbidden for regular users:**
```python
if not payload or payload["role"] == "user":
    raise HTTPException(403, "Forbidden")
```

**Company scoping pattern (line 318–319):**
```python
company_id = payload.get("company_id") if payload["role"] != "superuser" else None
cid = get_user_id(company_id) if company_id else None
```

---

### 1.4 Company Routes (`/api/companies/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 8 | `GET` | `/api/companies` | Yes | superuser | N/A | `[{id, name, tenant_id, domain, industry, contact_email, contact_phone, billing_email, api_key, created_at, server_count, user_count}]` | **403**: non-superuser |
| 9 | `POST` | `/api/companies` | Yes | superuser | `CompanyCreate` `{name, tenant_id, domain?, industry?, contact_email, contact_phone?, billing_email?}` | `{id, name, tenant_id, api_key}` | **403**: non-superuser. **400**: tenant_id already exists |
| 10 | `DELETE` | `/api/companies/{company_id}` | Yes | superuser | N/A | `{"message": "Company deleted"}` | **403**: non-superuser. **404**: company not found |

**Company creation auto-generates API key (line 471):**
```python
api_key = "pam_" + data.tenant_id.replace("-", "_")[:8] + "_" + uuid.uuid4().hex[:12]
```

---

### 1.5 Agent Routes (`/api/agent/*`)

All agent endpoints use `response_model=None` to avoid FastAPI type coercion on `Request` (name collision with Starlette's `Request`).

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 11 | `POST` | `/api/agent/register` | HMAC (X-API-Key, X-Signature) | agent (no JWT) | `{"hostname", "ip", "os_version"?, "tenant_company_id"?, "agent_version"?}` + raw body bytes for HMAC | `{"message": "Agent registered/updated", "hostname": ...}` | **401**: missing/invalid API key or bad HMAC signature |
| 12 | `POST` | `/api/agent/heartbeat` | HMAC | agent | `{"hostname", "status": "UP", "load"?, "last_activity"?, "uptime_seconds"?}` | `{"message": "Heartbeat received"}` | **401**: missing/invalid API key or bad HMAC. **404**: agent hostname not found |
| 13 | `POST` | `/api/agent/events` | HMAC | agent | `{"events": [{event_type, source?, hostname, username?, detail?, timestamp?}]}` or single event object | `{"message": "{n} events recorded"}` | **401**: missing/invalid API key or bad HMAC |

**HMAC verification logic (lines 189–205, also duplicated inline at each agent endpoint):**
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

**Security classification in `POST /api/agent/events` (lines 573–584):**
```python
et = event_type.upper()
if et in ("ACCOUNT_CREATED", "ACCOUNT_REMOVED"):
    ss = SecurityStatus.warning
elif et in ("LOGIN_FAILED",):
    ss = SecurityStatus.warning
elif et in ("SUDO_USED",):
    ss = SecurityStatus.info
# Everything else → info
```

---

### 1.6 User Routes (`/api/users/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 14 | `GET` | `/api/users` | Yes | any | N/A | `[{id, full_name, username, role, company_id, company_name, status, last_login}]` | **401**: not authenticated. Company-scoped for non-superuser |
| 15 | `GET` | `/api/users/all` | Yes | superuser | N/A | Same shape as above but all users across all companies | **403**: non-superuser |
| 16 | `POST` | `/api/users` | Yes | admin, superuser | `UserCreate` `{full_name, username, password, role="user", company_id?}` | `{id, full_name, username, role, company_id}` | **401**: not authenticated. **400**: username exists, missing company, company already has admin, insufficient billing. **403**: admin trying to create another admin |
| 17 | `PATCH` | `/api/users/{user_id}/status` | Yes | admin, superuser | `{"status": "active"|"inactive"}` | `{"message": "User activated/deactivated successfully"}` | **403**: user role, or non-superuser trying to change admin status. **404**: user not found. **400**: invalid status value |

**Admin creation guard (line 630–631):**
```python
if payload["role"] == "admin" and data.role == "admin":
    raise HTTPException(403, "Admin cannot create another admin")
```

**Billing deduction on user creation (lines 645–656):**
```python
if billing and billing.balance < billing.price_per_user:
    raise HTTPException(400, "Insufficient billing balance")
if billing:
    billing.balance -= billing.price_per_user
```

---

### 1.7 Server Routes (`/api/servers/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 18 | `GET` | `/api/servers` | Yes | any | N/A (query: `company_id?`, `status?`) | `[{id, name, ip, company_id, company_name, status, created_at}]` + `port, os, allowed_connection_types` only for non-user roles | **401**: not authenticated |
| 19 | `POST` | `/api/servers` | Yes | superuser | `ServerCreate` `{name, ip, port=22, allowed_connection_types=["ssh"], os?, company_id}` | `{id, name, ip, status}` | **403**: non-superuser |
| 20 | `GET` | `/api/servers/{server_id}` | Yes | any | N/A | Same shape as list item | **401**: not authenticated. **404**: server not found |
| 21 | `DELETE` | `/api/servers/{server_id}` | Yes | superuser | N/A | `{"message": "Server deleted"}` | **403**: non-superuser. **404**: server not found |

**Data hiding for regular users (line 720–721):**
```python
if payload["role"] != "user":
    sd.update({"port": s.port, "os": s.os, "allowed_connection_types": s.allowed_connection_types})
```

---

### 1.8 Request Routes (`/api/requests/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 22 | `GET` | `/api/requests` | Yes | any | N/A (query: `status?`, `requester_id?`) | `[{id, requester_id, requester_name, requester_username, server_id, server_name, server_ip, company_name, company_id, access_level, duration_minutes, description, status, requested_at, approved_at, approved_by, expires_at}]` | **401**: not authenticated. User sees only own; admin sees company; superuser sees all |
| 23 | `GET` | `/api/requests/my` | Yes | any | N/A (query: `status?`) | Same shape as above but filtered to current user only | **401**: not authenticated |
| 24 | `POST` | `/api/requests` | Yes | any | `RequestCreate` `{server_id, access_level, duration_minutes, description?}` | `{id, status}` | **401**: not authenticated. **404**: server not found. **400**: server inactive. **403**: cross-company request |
| 25 | `POST` | `/api/requests/{request_id}/approve` | Yes | admin, superuser | N/A | `{"message": "Request approved"}` | **403**: user role. **400**: request not found or not pending |
| 26 | `POST` | `/api/requests/{request_id}/reject` | Yes | admin, superuser | N/A | `{"message": "Request rejected"}` | **403**: user role. **400**: request not found or not pending |
| 27 | `POST` | `/api/requests/{request_id}/cancel` | Yes | any (owner only) | N/A | `{"message": "Request cancelled"}` | **401**: not authenticated. **404**: request not found. **400**: request cannot be cancelled (not pending/approved). **403**: not your request |
| 28 | `DELETE` | `/api/requests/{request_id}` | Yes | any (scoped) | N/A | `{"message": "Request deleted"}` | **401**: not authenticated. **404**: request not found. **403**: user deleting another's request; admin deleting another's |
| 29 | `GET` | `/api/requests/check-active/{server_id}` | Yes | any | N/A | `{"hasActive": bool, "request": {id} | null}` | **401**: not authenticated |

**Approve flow — agent provisioning (lines 889–941):**
```python
@app.post("/api/requests/{request_id}/approve")
async def approve_request(request_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")                          # ← 403
    req = (await db.execute(select(Request).where(Request.id == get_user_id(request_id)))).scalar_one_or_none()
    if not req or req.status != RequestStatus.pending:
        raise HTTPException(400, "Request not found or not pending")   # ← 400
    # ... updates status, calls agent provision, returns
```

**Cancel permission check (lines 972–973):**
```python
if str(req.requester_id) != payload["user_id"]:
    raise HTTPException(403, "Not your request")
```

---

### 1.9 Session Routes (`/api/sessions/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 30 | `GET` | `/api/sessions` | Yes | any | N/A | `[{id, request_id, user_id, user_name, user_username, server_id, server_name, server_ip, company_name, started_at, ended_at, status}]` | **401**: not authenticated. User sees own; admin sees company; superuser sees all |
| 31 | `GET` | `/api/sessions/{session_id}` | Yes | any | N/A | `{id, request_id, user_id, user_name, user_username, server_id, server_name, server_ip, server_port, company_name, access_level, started_at, ended_at, status}` | **401**: not authenticated. **404**: session not found |
| 32 | `GET` | `/api/sessions/{session_id}/recording` | Yes | admin, superuser | N/A | `{"recording": [{timestamp, event, data}, ...]}` | **403**: user role or cross-company access. **404**: session not found |
| 33 | `POST` | `/api/sessions/{session_id}/terminate` | Yes | any (scoped) | N/A | `{"message": "Session terminated"}` | **401**: not authenticated. **404**: session not found. **403**: user terminating another's session |

**Terminate — also expires the request (lines 1094–1099):**
```python
if session.request_id:
    req = await db.execute(select(Request).where(Request.id == session.request_id))
    req = req.scalar_one_or_none()
    if req:
        req.status = RequestStatus.expired
        await db.commit()
```

---

### 1.10 Audit Log Routes (`/api/audit-logs/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 34 | `GET` | `/api/audit-logs` | Yes | admin, superuser | N/A (query: `event_type?`, `performed_by?`, `security_status?`, `date_from?`, `date_to?`, `company_id?`, `limit=50`, `offset=0`) | `{"rows": [{id, timestamp, event_type, performed_by, target, action_detail, company_id, security_status, source}], "total": int}` | **403**: user role |
| 35 | `GET` | `/api/audit-logs/export` | Yes | admin, superuser | Same filter query params | CSV file download (Content-Disposition attachment, max 10K rows) | **403**: user role |

**Filter application (lines 1118–1127):**
```python
if event_type:
    query = query.where(AuditLog.event_type == event_type)
if performed_by:
    query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
if security_status:
    query = query.where(AuditLog.security_status == SecurityStatus(security_status))
```

---

### 1.11 Billing Routes (`/api/billing/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 36 | `GET` | `/api/billing/my` | Yes | admin, superuser | N/A | `{id, admin_user_id, balance, price_per_user}` | **403**: user role |
| 37 | `GET` | `/api/billing/transactions` | Yes | admin, superuser | N/A | `[{id, amount, reason, created_at}]` | **403**: user role |
| 38 | `POST` | `/api/billing/add-funds` | Yes | admin, superuser | `AddFundsRequest` `{amount: float, reason?}` | `{id, balance, price_per_user}` | **403**: user role. **400**: amount <= 0 |
| 39 | `GET` | `/api/billing/all` | Yes | superuser | N/A | `[{id, admin_name, admin_username, company_name, balance, price_per_user}]` | **403**: non-superuser |

---

### 1.12 Notification Routes (`/api/notifications/*`)

| # | Method | Path | Auth | Role | Request Body | Response | Error Codes |
|---|---|---|---|---|---|---|---|
| 40 | `GET` | `/api/notifications` | Yes | any | N/A (query: `limit=50`) | `[{id, type, message, link, read, created_at}]` | **401**: not authenticated |
| 41 | `GET` | `/api/notifications/unread-count` | Yes | any | N/A | `{"count": int}` | **401**: not authenticated |
| 42 | `PATCH` | `/api/notifications/{notification_id}/read` | Yes | any | N/A | `{"message": "Marked as read"}` | **401**: not authenticated. (No error if not found) |
| 43 | `POST` | `/api/notifications/read-all` | Yes | any | N/A | `{"message": "All marked as read"}` | **401**: not authenticated |

**Mark-as-read silently ignores missing ID (lines 1271–1276):**
```python
if n:
    n.read = True
    await db.commit()
return {"message": "Marked as read"}   # Returns success even if not found
```

---

### 1.13 WebSocket Endpoint

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| 44 | `WebSocket` | `/ws/terminal` | JWT in query param `?token=` | Bidirectional SSH terminal proxy |

**Actions supported inside the WebSocket:**
- `join_session` — starts an SSH session, streams I/O
- `reconnect_session` — replays recording of an existing active session
- `terminate_session` / `close_session` — sent by frontend

**Error messages sent as JSON over the socket (not HTTP):**
```json
{"type": "error", "data": "Not authenticated"}
{"type": "error", "data": "Server not found"}
{"type": "error", "data": "Access denied"}
{"type": "error", "data": "SSH connection failed: <details>"}
```

---

### 1.14 Frontend & Health Routes

| # | Method | Path | Auth | Purpose |
|---|---|---|---|---|
| 45 | `GET` | `/` | None | Serves embedded SPA (`FRONTEND_HTML`) |
| 46 | `GET` | `/index.html` | None | Same as above |
| 47 | `GET` | `/api/health` | None | `{"status": "ok", "timestamp": "..."}` |
| 48 | `GET` | `/api/download-project` | None | Downloads `LAST_PAM_PROJECT.zip` if exists |
| 49 | `GET` | `/api/download-report` | None | Downloads `report.md` if exists |

---

## 2. Error Handling Strategy

### 2.1 Exception Raising Pattern

The entire codebase uses **`HTTPException`** from Starlette/FastAPI with explicit status codes and string `detail` messages. There are no custom exception classes, no `@app.exception_handler` registrations, and no global catch-all middleware.

**Example from login (lines 213–217):**
```python
if not user or not verify_password(data.password, user.password_hash):
    raise HTTPException(401, "Invalid username or password")
if user.status == UserStatus.inactive:
    raise HTTPException(403, "Account is deactivated")
```

### 2.2 Global Exception Handling

**No custom exception handlers exist.** The code does not register any `@app.exception_handler`. FastAPI's default handlers apply:
- `HTTPException` → returns JSON `{"detail": "<message>"}` with the specified status code
- `ValidationError` (Pydantic) → returns `422` with field-level error details
- `RequestValidationError` → returns `422`
- Unhandled `Exception` → returns `500 Internal Server Error` (Starlette default)

**Proof — no exception handlers in the entire file:**
```python
app = FastAPI(title="PAM Server", lifespan=lifespan)   # line 105
# ... 1550+ lines of endpoints and helpers ...
# No @app.exception_handler anywhere
```

### 2.3 WebSocket Error Handling (lines 1485–1493)

WebSocket errors are handled inline:
```python
except WebSocketDisconnect:
    pass
except Exception as e:
    try:
        await websocket.send_json({"type": "error", "data": str(e)})
    except:
        pass
finally:
    active_connections.pop(user_id, None)
```

### 2.4 Background Task Error Handling (lines 1515–1541)

The periodic `expire_old_requests()` coroutine wraps its entire body in `try/except pass`:
```python
async def expire_old_requests():
    while True:
        await asyncio.sleep(60)
        try:
            # ... all logic ...
        except:
            pass
```

### 2.5 Silent Exception Suppression (Antipattern)

Several places silently catch and ignore exceptions with bare `except: pass`:
```python
# Line 901–902 (approve agent provision failure)
except:
    pass

# Line 939–940 (same pattern repeated)
except:
    pass

# Line 756–757 (server connectivity check)
except:
    pass

# Line 1536–1538 (expire_old_requests agent revocation)
except:
    pass
```

This means provisioning failures, connectivity check failures, and revocation failures are **completely invisible** — no logs, no audit trail, no alerts.

---

## 3. Input Validation Analysis

### 3.1 Pydantic Schema Definitions

**`schemas.py` (85 lines total)** defines 12 request models. None of them use Pydantic validators (`@field_validator`, `@model_validator`, `Field(..., min_length=...)`, etc.).

**`LoginRequest` (line 5–7):**
```python
class LoginRequest(BaseModel):
    username: str
    password: str
```
`username` and `password` are **unvalidated** — no minimum/maximum length, no format check. Empty strings are accepted.

**`UserCreate` (line 14–19):**
```python
class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str = "user"
    company_id: Optional[str] = None
```
No length constraints on `full_name`, `username`, or `password`. `role` is unvalidated as a free string — only validated when converted to `UserRole(data.role)` at line 659, which will raise a `422` if it doesn't match the enum.

**`CompanyCreate` (line 31–38):**
```python
class CompanyCreate(BaseModel):
    name: str
    tenant_id: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None
```
`contact_email` is a plain `str` — **no email format validation** using Pydantic's `EmailStr` or regex pattern. Invalid emails like `"notanemail"` would be accepted.

**`ServerCreate` (line 62–68):**
```python
class ServerCreate(BaseModel):
    name: str
    ip: str
    port: int = 22
    allowed_connection_types: List[str] = ["ssh"]
    os: Optional[str] = None
    company_id: str
```
`ip` is a plain `str` — **no IP address format validation**. Any string would pass.

**`RequestCreate` (line 70–74):**
```python
class RequestCreate(BaseModel):
    server_id: str
    access_level: str
    duration_minutes: int
    description: Optional[str] = None
```
`access_level` is a free string — validated only at `AccessLevel(data.access_level)` line 876.

**`PasswordChange` (line 76–78):**
```python
class PasswordChange(BaseModel):
    current_password: str
    new_password: str
```
`new_password` has **no minimum length requirement** — an empty string would be accepted.

**`AddFundsRequest` (line 83–85):**
```python
class AddFundsRequest(BaseModel):
    amount: float
    reason: Optional[str] = None
```
No validation that `amount` is a reasonable positive number (checked only in the endpoint at line 1211).

### 3.2 Where Validation Happens (Endpoint Level)

| Validation | Where | Mechanism |
|---|---|---|
| UUID format for IDs | `get_user_id()` | `uuid.UUID(user_id)` → raises 400 on failure |
| Enum membership | Endpoint code | `UserRole(data.role)` → Pydantic raises 422 |
| IP not empty | None | No check |
| Password minimum length | None | No check |
| Email format | None | No check |
| `duration_minutes` > 0 | None | No check |
| `amount` > 0 | Line 1211 | `if data.amount <= 0: raise HTTPException(400, "Invalid amount")` |

### 3.3 Missing Validations Summary

| Missing Validation | Risk | File/Line |
|---|---|---|
| Password min length on change | Empty password can be set | `schemas.py:77` |
| Email format on company create | Invalid emails stored | `schemas.py:36` |
| IP address format on server create | `"abc"` accepted as IP | `schemas.py:64` |
| `duration_minutes` lower bound | 0 or negative accepted | `schemas.py:73` |
| Cross-field check (e.g., current_password != new_password) | Same password allowed | `schemas.py:76-78` |
| String max lengths | No truncation protection | All schemas |
| XSS/SQL injection on free-text fields | `action_detail` has no sanitization | `main.py:1135` |

---

## 4. Rate Limiting / Throttling Analysis

### 4.1 Does Rate Limiting Exist?

**No.** There is zero rate limiting, throttling, or request bucketing anywhere in the codebase.

**Proof from imports (lines 1–32):**
```python
from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Body, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
```
No `SlowAPI`, `fastapi-limiter`, `slowapi`, or any middleware related to rate limiting is imported.

**Proof from middleware (lines 107–113):**
```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```
Only CORS middleware is registered. No `RateLimitMiddleware`, no `TrustedHostMiddleware`, no security middleware at all.

**Proof from configuration (`config.py`, 9 lines):**
```python
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./pam.db")
JWT_SECRET = os.getenv("JWT_SECRET", "pam-server-jwt-secret-key-2024")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "pam-server-refresh-secret-key-2024")
JWT_ALGORITHM = "HS256"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "shared-agent-api-key-pam2024")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
```
No rate-limit related configuration variables.

### 4.2 Why Rate Limiting Is Missing

The project uses **SQLite** in development (`sqlite+aiosqlite:///./pam.db`), which has no built-in connection pooling for concurrent rate-limit counters. Adding rate limiting would require either:

1. An in-process data structure (simple but lost on restart)
2. A Redis/ValKey dependency (adds infrastructure complexity)

The project also uses **SQLAlchemy async** with a minimal pool (`pool_size=5`), which provides implicit concurrency limiting at the database level but is not equivalent to request-level rate limiting.

### 4.3 Impact of Missing Rate Limiting

Without rate limiting, an attacker could:

- **Brute force login** — `POST /api/auth/login` with unlimited attempts (only audit-logged, not blocked)
- **Flood audit logs** — `POST /api/agent/events` accepts arbitrary numbers of events per request
- **Exhaust database connections** — any endpoint that opens a session could be hammered
- **Spam notifications** — `POST /api/requests` creates notifications for every admin

---

## 5. Notable Code Snippets & Patterns

### 5.1 JWT Token Handling (`auth_utils.py`)

```python
def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=15)   # 15 min expiry
    to_encode["type"] = "access"
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=7)       # 7 day expiry
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str, secret: str = JWT_SECRET) -> Optional[dict]:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
```

Note: Access tokens have only **15 minutes** expiry — the frontend must refresh frequently via `POST /api/auth/refresh`. Refresh tokens last 7 days.

### 5.2 Multi-Tenant Company Scoping

The `company_id` from the JWT payload is used to filter all database queries. The pattern varies slightly per endpoint:

**For superuser (no filter):**
```python
if payload["role"] != "superuser":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```

**For admin (own company):**
```python
elif payload["role"] == "admin":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```

**For user (own records only):**
```python
if payload["role"] == "user":
    query = query.where(Request.requester_id == get_user_id(payload["user_id"]))
```

### 5.3 Agent Provisioning on Approve (lines 908–940)

```python
server = await db.execute(select(Server).where(Server.id == req.server_id))
server = server.scalar_one_or_none()
if server:
    company = await db.execute(select(Company).where(Company.id == server.company_id))
    company = company.scalar_one_or_none()
    api_key = company.api_key if company else None
    agent_port = req.agent_port or 8800
    jit_username = "jit-" + uuid.uuid4().hex[:8]
    provision_body = {
        "request_id": str(req.id),
        "username_to_create": jit_username,
        "privilege": req.access_level.value,
        "duration_minutes": req.duration_minutes,
        "expires_at": req.expires_at.isoformat() if req.expires_at else ...
    }
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                f"http://{server.ip}:{agent_port}/agent/provision",
                json=provision_body,
                headers={"X-API-Key": api_key or AGENT_API_KEY}
            )
            if resp.status_code == 200:
                prov = resp.json()
                req.provisioned_username = prov.get("username", jit_username)
                req.ssh_private_key = prov.get("ssh_private_key")
    except:
        pass  # Silent failure — provisioning error is invisible
```

### 5.4 WebSocket SSH Terminal (lines 1292–1493)

The SSH connection is established with `asyncssh.connect()` to the target server IP, using either:
- The **JIT provisioned SSH key** stored in `Request.ssh_private_key` (if available)
- The **pam-service user's SSH key** at `/home/administrator/.ssh/id_rsa` (fallback for direct connections without a request)

```python
ssh_username = "pam-service"
ssh_key = "/home/administrator/.ssh/id_rsa"
if request_id:
    req = (await db.execute(select(Request).where(Request.id == get_user_id(request_id)))).scalar_one_or_none()
    if req and req.provisioned_username and req.ssh_private_key:
        ssh_username = req.provisioned_username
        ssh_key = req.ssh_private_key
```

The SSH private key is written to a temporary file with `chmod 600` before being passed to asyncssh:

```python
if ssh_key and ssh_key.startswith("-----"):
    tmp_key = tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False)
    tmp_key.write(ssh_key)
    tmp_key.close()
    os.chmod(tmp_key.name, 0o600)
```

### 5.5 Suspicious Activity Detection (lines 41–76)

Regex-based detection runs on every keystroke and every output line from the SSH session:

```python
SUSPICIOUS_PATTERNS = [
    (re.compile(r'\bsudo\s+', re.IGNORECASE), 'critical', 'Privilege escalation: sudo command used'),
    (re.compile(r'wget\s+.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Remote code execution: wget pipe to shell'),
    (re.compile(r'base64\s+-d.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Obfuscated command execution via base64'),
    # ... 19 patterns total
]

def detect_suspicious_activity(text: str) -> list[dict]:
    findings = []
    for pattern, severity, description in SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            findings.append({"severity": severity, "description": description})
    return findings
```

All 19 patterns are classified as `"critical"` severity. When matched, an `AuditLog` entry is created with `event_type` either `"suspicious_command"` (for input) or `"suspicious_output"` (for stdout/stderr). The session is **not** terminated — only logged.

### 5.6 SSH Key Masking in Recordings (lines 63–69)

```python
SSH_KEY_PATTERN = re.compile(
    r'-----BEGIN\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----',
    re.IGNORECASE
)
def mask_ssh_keys(text: str) -> str:
    return SSH_KEY_PATTERN.sub('[SSH KEY REDACTED]', text)
```

Applied in `read_stdout()` (line 1380) and `read_stderr()` (line 1396) before recording or forwarding to the frontend. The raw (unmasked) output is still sent to `detect_suspicious_activity()` for pattern matching.

### 5.7 Known Bug: Broken Notification in `agent_revoke` (lines 179–187)

```python
result = await db.execute(
    select(User).where(
        or_(User.role == UserRole.superuser,
            and_(User.role == UserRole.admin, User.company_id == get_user_id(company_id)))
    )
)
users = result.scalars().all()
for u in users:
    await notify_user(db, str(u.id), type, message, link)
```

**Three undefined variables:** `company_id`, `type`, `message`, `link` — these are not passed into the function and are not declared in scope. This code block is dead/unreachable? Actually it IS reachable — every call to `agent_revoke()` will crash at this point with a `NameError`.

**Wait** — looking at the original code flow: `agent_revoke` is called from `cancel_request` (line 975) and `delete_request` (line 994). But looking at the error log from earlier:

```
NameError: name 'company_id' is not defined. Did you mean: 'company'?
```

This confirms the bug — it was crashing. However, looking at the current code more carefully, this block runs even when `delete_req=True` (from delete_request). But wait, line 174 has `if not delete_req:` which prevents clearing provision fields, but the notification block at lines 179-187 runs regardless. This would cause a crash on every cancel/delete where `req.provisioned_username` is set.

---

## 6. Middleware & App Configuration

```python
app = FastAPI(title="PAM Server", lifespan=lifespan)   # line 105

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "*"],      # Wildcard allows all origins!
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Security note:** `allow_origins=[FRONTEND_URL, "*"]` — the wildcard `"*"` combined with `allow_credentials=True` creates a CORS configuration that is partially invalid (browsers ignore credentials when `*` is used, but `FRONTEND_URL` comes first so it may take precedence depending on middleware internal ordering).

**No other middleware is registered** — no `TrustedHostMiddleware`, no `HTTPSRedirectMiddleware`, no `GZipMiddleware`, no session middleware.

---

## 7. Security Audit Summary

| Area | Status | Details |
|---|---|---|
| **Auth** | Functional | JWT-based, bcrypt password hashing (12 rounds), separate secrets for access/refresh tokens |
| **Multi-tenancy** | Implemented | company_id filtering on all queries, role-based data hiding |
| **API key generation** | Weak | Simple pattern `pam_{tenant}_{12 hex chars}` — deterministic prefix |
| **HMAC verification** | Strong | Uses `hmac.compare_digest()` for timing-safe comparison |
| **Rate limiting** | Missing | No protection against brute-force or DoS |
| **Input validation** | Minimal | No email, IP, or password format validation in Pydantic schemas |
| **Error handling** | Bare minimum | No global exception handler, silent `except: pass` in multiple places |
| **CORS** | Overly permissive | `allow_origins=["*"]` combined with credentials enabled |
| **Password policy** | None | No length/complexity requirements enforced |
| **Session management** | Basic | No refresh token rotation, no invalidation on password change |
| **Audit logging** | Comprehensive | 26 event types logged with security classification |
| **SSH key storage** | Insecure | Private keys stored in plaintext in `Request.ssh_private_key` column |
