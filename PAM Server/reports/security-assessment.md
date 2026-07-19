# Security Assessment: PAM Server

> Generated from codebase snapshot at `/home/administrator/pam-server/backend-python/`  
> Analyzed through OWASP Top 10 (2021) lens  
> **Assessment type:** Manual code audit — no automated scans or penetration testing were performed

---

## 1. Authentication & Session Management (OWASP A7)

### 1.1 JWT Implementation

**File:** `auth_utils.py`, lines 1-30

```python
JWT_ALGORITHM = "HS256"

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

def verify_token(token: str, secret: str = JWT_SECRET) -> Optional[dict]:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
```

**Positive:** Access tokens expire after 15 minutes (short window). Refresh tokens use a separate secret (`JWT_REFRESH_SECRET`). The `python-jose` library is a well-maintained JWT implementation.

**Critical finding — hardcoded secrets in source (`config.py`, lines 4-5):**

```python
JWT_SECRET = os.getenv("JWT_SECRET", "pam-server-jwt-secret-key-2024")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "pam-server-refresh-secret-key-2024")
```

Both secrets fall back to hardcoded strings if environment variables are not set. Any developer who has access to the source code knows the JWT signing key. Combined with the HS256 algorithm (symmetric), this means anyone with the source can forge valid tokens for any user.

**Finding — no audience/issuer/not-before claims:**

The JWT payload contains only `user_id`, `username`, `role`, `company_id`, `exp`, and `type`. There is no `aud` (audience), `iss` (issuer), `iat` (issued-at), or `nbf` (not-before) claim. This makes token reuse across different services possible and removes the ability to validate the token's origin.

**Finding — no refresh token rotation:**

```python
# main.py lines 245-259
@app.post("/api/auth/refresh")
async def refresh(token_data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    token = token_data.get("refreshToken")
    # ...
    return {"access_token": create_access_token(new_payload), "refresh_token": create_refresh_token(new_payload)}
```

The same refresh token can be used multiple times. There is no one-time-use or rotation mechanism. If a refresh token is exfiltrated, it remains valid for 7 days and can be used to generate unlimited access tokens.

### 1.2 bcrypt Cost Factor

**File:** `auth_utils.py`, line 8

```python
def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()
```

**Positive:** bcrypt with `gensalt(12)` provides a cost factor of 2^12 = 4096 iterations. This is the OWASP-recommended minimum for 2024. The password hash is stored in a dedicated `password_hash` column.

### 1.3 Token Storage — localStorage (XSS Exposure)

**Finding — critical: tokens stored in localStorage, accessible via XSS.**

**File:** `frontend_html.py` (embedded SPA):

```javascript
// Login response handler
const savedToken = localStorage.getItem('pam_token');
const savedUser = localStorage.getItem('pam_user');

// Login handler (line ~280)
localStorage.setItem('pam_token', data.access_token);
localStorage.setItem('pam_user', JSON.stringify(data.user));
```

The access token is persisted to `localStorage` with key `pam_token`. There is no `httpOnly` or `Secure` flag because localStorage is a JavaScript API — any XSS vulnerability (e.g., a malicious SSH command that escapes the terminal div and injects a `<script>` tag) can read `localStorage.getItem('pam_token')` and exfiltrate the token.

**Finding — token leaked via URL query parameter on every request:**

**File:** `frontend_html.py` (API helper):

```javascript
async function api(url, opts = {}) {
  if (token) {
    const sep = url.includes('?') ? '&' : '?';
    url += sep + 'token=' + encodeURIComponent(token);  // ← token in URL
  }
}
```

The JWT is appended as a `?token=` query parameter on every API request. This exposes the token in:
- Server access logs (`GET /api/servers?token=eyJhbGci...` logged as full URL)
- Browser history (if any requests use browser navigation instead of fetch)
- Referer headers (if the page navigates to an external link)
- Network intermediary logs (proxies, load balancers)

The WebSocket connection path also uses the query param:

```javascript
const wsUrl = 'ws://' + location.host + '/ws/terminal?token=' + token;
```

**Finding — no httpOnly cookie option explored.** The backend accepts the token via query param (`Query(None)`) but never attempts to set an httpOnly cookie. Using httpOnly cookies with `SameSite=Strict` would prevent both XSS and URL-based token leakage.

---

## 2. Authorization & RBAC (OWASP A1)

### 2.1 Who Can Do What

The system defines three roles: `superuser` (cross-company), `admin` (per-company), `user` (end-user). The enforcement pattern is consistent across most endpoints:

```python
# Pattern A: check auth only (any authenticated user)
if not payload:
    raise HTTPException(401, "Not authenticated")

# Pattern B: forbid users
if not payload or payload["role"] == "user":
    raise HTTPException(403, "Forbidden")

# Pattern C: require superuser
if not payload or payload["role"] != "superuser":
    raise HTTPException(403, "Forbidden")
```

### 2.2 Endpoints with Missing or Weak Authorization

**Finding — `GET /api/servers` returns server list to any authenticated user (by design), but admin cannot filter by arbitrary company:**

```python
# main.py lines 703-723
@app.get("/api/servers")
async def list_servers(token: str = Query(None), company_id: str = None, ...):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(Server, Company.name).join(Company, Server.company_id == Company.id)
    if payload["role"] != "superuser":
        query = query.where(Server.company_id == get_user_id(payload["company_id"]))
    elif company_id:
        query = query.where(Server.company_id == get_user_id(company_id))
```

Note: the `elif` on line 711 means only superuser can use the `company_id` query parameter. An admin cannot filter by a different company_id even if they know it — correct enforcement.

**Finding — `GET /api/servers/{server_id}` has no company ownership check:**

```python
# main.py lines 766-782
async def get_server(server_id: str, ...):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Server, Company.name).join(...).where(Server.id == get_user_id(server_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Server not found")
    s, cn = row
    sd = {"id": str(s.id), "name": s.name, "ip": s.ip, ...}
    if payload["role"] != "user":
        sd.update({"port": s.port, "os": s.os, "allowed_connection_types": s.allowed_connection_types})
    return sd
```

**Problem:** A user from Company A can call `GET /api/servers/{server_id_of_company_B}` and get the server details (IP, name, status). The role check on line 780 only hides port/OS/connection_types from "user" role, but the IP address itself is still returned. The server_id is a UUID so it's not guessable, but it is enumerable if a user obtains another company's server ID (e.g., through logs, support tickets, or a compromised admin account).

**Finding — `GET /api/users` leaks the entire company's user list to any authenticated user:**

```python
# main.py lines 589-603
@app.get("/api/users")
async def list_users(token: str = Query(None), ...):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(User, Company.name).outerjoin(...)
    if payload["role"] != "superuser":
        query = query.where(User.company_id == get_user_id(payload["company_id"]))
    # ...
```

A regular `user` role can see all users in their company, including their full names, usernames, roles, and last login times. This is an information disclosure issue. A user has no legitimate need to see the full user registry.

**Finding — `GET /api/sessions/{session_id}` has no company ownership filter:**

```python
# main.py lines 1041-1061
async def get_session(session_id: str, ...):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Session, ...).join(...).outerjoin(...)
        .where(Session.id == get_user_id(session_id))
    )
```

The query has no role-based filter. An admin from Company A can request a session from Company B by its ID and get the full session details (including user_name, server_ip, server_port, access_level, start/end times). The session_id is a UUID but no company boundary is enforced after the query.

**Finding — `GET /api/sessions/{session_id}/recording` has inconsistent multi-tenant check:**

```python
# main.py lines 1063-1078
async def get_session_recording(session_id: str, ...):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(
        select(Session, Server.company_id).join(Server, Session.server_id == Server.id)
        .where(Session.id == get_user_id(session_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Session not found")
    session, company_id = row
    if payload["role"] != "superuser" and str(company_id) != payload.get("company_id"):
        raise HTTPException(403, "Access denied")
    return {"recording": session.recording_data or []}
```

This endpoint correctly enforces multi-tenant access (line 1076). However, note the inconsistency: `get_session()` (line 1041) does NOT have this check, while `get_session_recording()` does. This is a **logical inconsistency** — the metadata endpoint is less protected than the recording endpoint.

**Finding — `POST /api/requests/{request_id}/approve` does not enforce admin company scope:**

```python
# main.py lines 889-941
async def approve_request(request_id: str, ...):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
    req = result.scalar_one_or_none()
    if not req or req.status != RequestStatus.pending:
        raise HTTPException(400, "Request not found or not pending")
```

An admin from Company A could potentially approve a request from Company B — there is no check that the request's server belongs to the admin's company. The request table does not store the company_id directly; it's resolved through the server relationship, but the endpoint never follows that relationship to verify company ownership.

**Finding — `POST /api/users` admin can only create `user` role (correct), but `POST /api/requests` has no admin-company scope check on the target server:**

```python
# main.py lines 861-887
async def create_request(data: RequestCreate, ...):
    payload = get_current_user_from_token(token=token)
    # ...
    server = ...  # fetches server
    if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
        raise HTTPException(403, "Access denied")
```

This check at line 872 **is correct** — a user/admin cannot create a request for a server outside their company. However, the auth check is that a user must always match their company_id. This is correct.

**Finding — `GET /api/requests` admin can see all company requests, but no way to filter out own requests:**

```python
# main.py lines 801-833
async def list_requests(token: str = Query(None), ...):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = ...
    if payload["role"] == "user":
        query = query.where(Request.requester_id == ...)
    elif payload["role"] == "admin":
        query = query.where(Server.company_id == ...)
```

The admin correctly sees all requests for their company's servers, including their own requests. This is by design (admins need to see all pending requests to approve them).

**Finding — `DELETE /api/requests/{request_id}` has role escalation for admin:**

```python
# main.py lines 989-992
if payload["role"] == "admin" and str(req.requester_id) != payload["user_id"]:
    raise HTTPException(403, "Admins can only delete their own requests")
```

An admin can delete any user's request in their company (line 989 only blocks `user` role from deleting others' requests). But line 991-992 blocks admins from deleting others' requests too — so an admin can only delete their own requests, not their users' requests. This may be intentional or an oversight depending on design intent.

**Summary of authorization gaps:**

| Endpoint | Gap | Risk |
|----------|-----|------|
| `GET /api/servers/{id}` | No company ownership check for metadata | Low (UUID not guessable) |
| `GET /api/users` | Users see all company users | Medium (info disclosure) |
| `GET /api/sessions/{id}` | No company ownership filter | Medium (session metadata leak) |
| `POST /api/requests/{id}/approve` | No company scope check | High (cross-company approval) |

---

## 3. Injection (OWASP A3)

### 3.1 SQL Injection

**Positive:** All database queries use SQLAlchemy ORM, which parameterizes queries by default. The generated SQL binds values as parameters rather than interpolating them into the query string.

**Finding — raw SQL with parameterized binding (safe):**

```python
# main.py lines 1283-1286
await db.execute(
    text("UPDATE notifications SET read = true WHERE user_id = :uid AND read = false"),
    {"uid": get_user_id(payload["user_id"])}
)
```

This uses `text()` with named bind parameters (`:uid`) and a separate parameter dictionary. This is safe from SQL injection because SQLAlchemy passes the parameters to the database driver as bind variables.

**Finding — `ilike` with f-string (safe):**

```python
# main.py line 1121
query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
```

The f-string creates the pattern string, but SQLAlchemy's `.ilike()` still binds this as a parameter. The `%` characters are part of the LIKE pattern value, not string interpolation into the SQL. **This is safe.**

**Overall SQL Injection risk: LOW** — SQLAlchemy ORM usage throughout prevents SQL injection.

### 3.2 Command Injection in Agent Callbacks

**File:** `main.py`, lines 154-173, 909-940, 1525-1538

```python
# main.py lines 166-170 (agent_revoke)
async with httpx.AsyncClient(timeout=5) as client:
    await client.post(
        f"http://{server.ip}:{agent_port}/agent/revoke",
        json={"request_id": str(req.id), "username": req.provisioned_username},
        headers={"X-API-Key": api_key or AGENT_API_KEY}
    )
```

**Finding — the PAM Server sends `username` to the agent, which likely executes `userdel` or `usermod` on the target VM. If the agent has a command injection vulnerability (e.g., `os.system(f"userdel {username}")`), then an attacker who controls the `provisioned_username` could execute arbitrary commands on the tenant VM.**

The `provisioned_username` is set from the agent's response at line 933:

```python
req.provisioned_username = prov.get("username", jit_username)
```

And `jit_username` is generated server-side as `"jit-" + uuid.uuid4().hex[:8]`. This is safe. However, the agent's response is trusted without validation — if the agent were compromised or replaced, it could inject special characters into the username.

**Similarly, line 1535 sends the user's `requester.username` in the expiry revocation:**

```python
await client.post(f"http://{server.ip}:9100/agent/revoke",
    json={"user": requester.username}, ...)
```

The `requester.username` comes from the database, which was set at user creation time. If the user creation input is not sanitized (it isn't — Pydantic only ensures it's a string), a malicious user could register with a username like `"; rm -rf /; "` and the agent might execute it.

**Pydantic schema (`schemas.py`, lines 14-19):**

```python
class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str = "user"
    company_id: Optional[str] = None
```

No regex validation, no character allowlist, no minimum/maximum length on `username`. A username like `admin` would be rejected for duplication, but `"; shutdown -h now; "` would pass validation.

**Risk: MEDIUM** — depends on agent implementation. If the agent uses `subprocess.run()` with shell=True, command injection is trivially exploitable.

---

## 4. HMAC Signing & Replay Protection (OWASP A2)

### 4.1 HMAC Verification

**File:** `main.py`, lines 189-205, 496-585

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
        return api_key, company  # ← Bug: company is None here
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")
    return api_key, company
```

**Positive:** `hmac.compare_digest()` is used throughout for timing-safe comparison:

```python
# main.py lines 510-511, 542-543, 567-568
if not hmac.compare_digest(expected, signature):
    raise HTTPException(401, "Invalid HMAC signature")
```

This is correct. Using `hmac.compare_digest()` prevents timing side-channel attacks that would be possible with `expected == signature`.

**Finding — verification order bug in `verify_agent_hmac` (lines 189-205):**

The function first looks up the `api_key` in the `Company` table (line 194). If not found, it falls through to the `Agent` table (line 197). If the api_key is found in the Agent table but not in the Company table, the function **returns `api_key, company` on line 201 where `company` is None**. The callers of this function expect a valid `company` object.

Worse, the HMAC verification on line 202 only executes if the api_key was found in the Company table (the `if not company:` branch returns early on line 201). This means:
- If an api_key exists in the Agent table but NOT in the Company table, **no HMAC verification is performed** — the function returns with a valid api_key but no signature check.
- If an api_key exists in the Company table, the HMAC verification runs correctly.

**Finding — no replay attack protection:**

The HMAC signature is `SHA256(body + api_key)`. There is no:
- **Timestamp** (`X-Timestamp` header) — cannot enforce request freshness
- **Nonce** (`X-Nonce` header) — cannot detect duplicate requests
- **Request sequence number** — cannot enforce ordering

An attacker who intercepts an agent's signed request can replay it verbatim within an unlimited time window. For example, an intercepted `agent/register` request could be replayed to re-register an agent, or an intercepted `agent/events` request could replay audit events.

```python
# main.py lines 498-532
@app.post("/api/agent/register", response_model=None)
async def agent_register(incoming: FastAPIRequest, ...):
    body_bytes = await incoming.body()
    data = json.loads(body_bytes) if body_bytes else {}
    api_key = incoming.headers.get("X-API-Key")
    signature = incoming.headers.get("X-Signature")
    # ...
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")
```

The body is parsed after HMAC verification, which is correct (verify signature before processing). But without a timestamp, a captured registration request can be replayed.

---

## 5. Secrets Management (OWASP A6)

### 5.1 API Keys in Plaintext

**File:** `database.py`, line 85

```python
class Company(Base):
    __tablename__ = "companies"
    # ...
    api_key = Column(String, unique=True, nullable=True)
```

Company API keys are stored in plaintext in the `companies.api_key` column. The database is SQLite by default (`pam.db`), which is a single file on disk. Anyone with filesystem access to the server can read `pam.db` and extract all API keys.

**File:** `database.py`, line 133

```python
class Request(Base):
    __tablename__ = "requests"
    # ...
    ssh_private_key = Column(Text, nullable=True)
```

SSH private keys are stored in plaintext in the `requests.ssh_private_key` column. These keys provide SSH access to tenant servers. Anyone who can read the database can SSH into provisioned servers.

**File:** `main.py`, lines 454-461

```python
# Companies list endpoint returns API keys in plaintext
companies.append({
    # ...
    "api_key": c.api_key,  # exposed to superuser in API response
})
```

The API key is returned in the `GET /api/companies` response (line 458). While this endpoint is superuser-only, it means the API key is transmitted over the network in plaintext and visible in the browser's developer tools.

### 5.2 Hardcoded JWT Secrets

**File:** `config.py`, lines 4-5

```python
JWT_SECRET = os.getenv("JWT_SECRET", "pam-server-jwt-secret-key-2024")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "pam-server-refresh-secret-key-2024")
```

Both JWT secrets have hardcoded fallback values. In the live deployment, no `.env` file was found — the secrets are likely using the hardcoded defaults. Anyone who knows these strings can forge valid JWT tokens for any user.

### 5.3 Shared Agent API Key

**File:** `config.py`, line 8

```python
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "shared-agent-api-key-pam2024")
```

There is a single shared API key for all tenant agents. This means:
- Any agent can impersonate any company
- If one agent is compromised, the trust relationship of all agents is broken
- The key cannot be rotated per-company without updating all agents

**File:** `main.py`, line 170

```python
headers={"X-API-Key": api_key or AGENT_API_KEY}
#                                  ^^^^^^^^^^^^^^ fallback to shared key
```

The fallback to `AGENT_API_KEY` means that even if a company has a valid api_key, some calls use the shared key. The inconsistency makes key management confusing and reduces the security benefit of per-company keys.

### 5.4 No `.env` File in Repository

No `.env` file or `.env.example` exists in the repository. The `config.py` uses `os.getenv()` with fallback defaults, so the application runs with production-default secrets unless environment variables are explicitly set. This creates a high risk of deploying with known secrets.

---

## 6. Multi-Tenant Isolation (OWASP A1 — Broken Object Level Authorization)

### 6.1 Where `company_id` Filtering Is Correct

**`GET /api/dashboard/stats` (lines 312-385):**
```python
company_id = payload.get("company_id") if payload["role"] != "superuser" else None
cid = get_user_id(company_id) if company_id else None
# ... all count queries check `if cid and hasattr(model, "company_id")`
```
✓ Correct — superuser sees all, admin sees filtered.

**`GET /api/servers` (lines 703-723):**
```python
if payload["role"] != "superuser":
    query = query.where(Server.company_id == get_user_id(payload["company_id"]))
```
✓ Correct.

**`GET /api/requests` (lines 801-833):**
```python
if payload["role"] == "user":
    query = query.where(Request.requester_id == ...)
elif payload["role"] == "admin":
    query = query.where(Server.company_id == ...)
```
✓ Correct — user sees only own requests, admin sees company's requests.

**`GET /api/sessions` (lines 1018-1038):**
```python
if payload["role"] == "user":
    query = query.where(Session.user_id == ...)
elif payload["role"] == "admin":
    query = query.where(Server.company_id == ...)
```
✓ Correct.

**`GET /api/audit-logs` (lines 1106-1140):**
```python
if payload["role"] != "superuser":
    query = query.where(AuditLog.company_id == ...)
```
✓ Correct.

**`POST /api/requests` (lines 861-887):**
```python
if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
    raise HTTPException(403, "Access denied")
```
✓ Correct — user/admin cannot request access to out-of-company servers.

**`PATCH /api/users/{user_id}/status` (lines 673-699):**
```python
if payload["role"] != "superuser":
    if user.role == UserRole.admin:
        raise HTTPException(403, "Cannot change admin status")
    if str(user.company_id) != payload.get("company_id"):
        raise HTTPException(403, "Access denied")
```
✓ Correct — admin can only change users in their own company.

### 6.2 Where `company_id` Filtering Is Missing

**`GET /api/servers/{server_id}` (lines 766-782):**
```python
# No company_id filter after fetching the server
row = result.first()
if not row:
    raise HTTPException(404, "Server not found")
# ... returns server data regardless of company ownership
```
✗ Missing — any authenticated user can read any server's metadata by UUID.

**`GET /api/sessions/{session_id}` (lines 1041-1061):**
```python
# No role-based filter on the query
result = await db.execute(select(Session, ...).where(Session.id == ...))
```
✗ Missing — any authenticated user (except user role which is handled via a different mechanism) can read any session's metadata.

**`POST /api/requests/{request_id}/approve` (lines 889-941):**
```python
# No check that the request's server belongs to the admin's company
result = await db.execute(select(Request).where(Request.id == ...))
if not req or req.status != RequestStatus.pending:
    raise HTTPException(400, ...)
```
✗ Missing — an admin can approve a request from another company if they know the request_id.

**`POST /api/requests/{request_id}/reject` (lines 943-959):**
```python
# Same issue as approve
if not req or req.status != RequestStatus.pending:
    raise HTTPException(400, ...)
```
✗ Missing — same cross-company rejection issue.

### 6.3 The `agent_revoke` NameError Bug

**File:** `main.py`, lines 179-187

```python
result = await db.execute(
    select(User).where(
        or_(User.role == UserRole.superuser,
            and_(User.role == UserRole.admin, User.company_id == get_user_id(company_id)))
            #                                                            ^^^^^^^^^^
    )
)
users = result.scalars().all()
for u in users:
    await notify_user(db, str(u.id), type, message, link)
    #                       ^^^^  ^^^^^^^  ^^^^^^^^
```

**Critical finding:** The variables `company_id`, `type`, `message`, and `link` are **undefined** in this scope. They are not function parameters, not local variables, and not global. This function is called from `cancel_request` (line 975) and `delete_request` (line 994). Any call to `agent_revoke()` where `req.provisioned_username` is set (meaning the request was previously approved and provisioned) will crash with a `NameError`:

```
NameError: name 'company_id' is not defined
```

This crash prevents the cancel/delete operation from completing. The request remains in its current state in the database, but the HTTP response is a 500 Internal Server Error.

---

## 7. Additional Security Observations

### 7.1 CORS Misconfiguration

**File:** `main.py`, lines 107-113

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "*"],  # FRONTEND_URL = "http://localhost:5173"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Finding — browser behavior:** When `allow_origins=["*"]`, browsers ignore `Access-Control-Allow-Credentials: true` per the CORS specification. The presence of `FRONTEND_URL` first in the list means the middleware may emit that value instead of `*`, but the behavior is implementation-defined. More importantly, the combination signals a misunderstanding of CORS — in a production deployment, origins should be explicitly listed.

### 7.2 Silent Exception Handling

**File:** `main.py` — at least 8 instances of `except: pass`:

```python
# Line 140-141
except:
    pass

# Lines 172-173
except:
    pass

# Lines 756-757
except:
    pass

# Lines 939-940
except:
    pass

# Lines 1469-1470
except:
    pass

# Lines 1489-1491 (nested try)
except:
    pass

# Lines 1537-1538
except:
    pass

# Lines 1540-1541
except:
    pass
```

Every `except: pass` swallows the exception completely — no logging, no error tracking, no fallback. The most dangerous one is at lines 939-940:

```python
except:
    pass
```

This wraps the tenant agent provisioning call. If the agent returns an error or is unreachable, the request is approved but the user is never provisioned. The admin sees "Request approved," the user clicks "Connect" and gets "SSH connection failed," and there is no audit trail of the provisioning failure.

### 7.3 No Rate Limiting

**OPSEC finding — no rate limiting on any endpoint.** A malicious authenticated user can:

1. Hit `POST /api/auth/login` repeatedly with different passwords (no brute-force protection)
2. Create 1000 requests in seconds via `POST /api/requests`
3. Trigger the agent provisioning callback 1000 times, potentially DDoS-ing the tenant agent
4. Read the audit log via `GET /api/audit-logs?limit=50&offset=N` to paginate through all logs (can exfiltrate the entire audit history)

### 7.4 Session Recording Data Exposure

**File:** `database.py`, line 144

```python
recording_data = Column(JSON, default=list)
```

Session recordings (full terminal I/O) are stored as JSON blobs in the database. There is no size limit, no compression, and no encryption. A long SSH session with heavy output could grow the database to gigabytes. Additionally, sensitive data (passwords typed in the terminal) is captured unless it matches the SSH key pattern.

**The SSH key masking (lines 63-69) only masks SSH private keys:**
```python
SSH_KEY_PATTERN = re.compile(
    r'-----BEGIN\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----',
)
def mask_ssh_keys(text: str) -> str:
    return SSH_KEY_PATTERN.sub('[SSH KEY REDACTED]', text)
```

Passwords for database logins, API keys typed in terminal, or other secrets are not masked.

### 7.5 No HTTPS

All communication uses plain HTTP/WS. The Nginx config (`nginx.conf`) only listens on port 80 with no SSL configuration. The WebSocket URL uses `ws://` not `wss://`. The localhost.run tunnel provides TLS at the tunnel endpoint, but traffic between the tunnel and the server is unencrypted.

### 7.6 Password Policy

There is no password policy enforcement. The `UserCreate` schema has no minimum length, no complexity requirements, no common-password check:

```python
class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str  # ← No min_length, no regex
    role: str = "user"
```

The seed data uses passwords like "nihat123", "aysel123", "user123" — all predictable.

---

## 8. Conclusion — Findings by Risk Severity

### Critical

| # | Finding | File/Line | Impact |
|---|---------|-----------|--------|
| C1 | Hardcoded JWT secrets in source code | `config.py:4-5` | Anyone with source can forge tokens for any user |
| C2 | API keys stored in plaintext DB column | `database.py:85` | DB compromise = all API keys leaked |
| C3 | SSH private keys stored in plaintext DB column | `database.py:133` | DB compromise = SSH access to all tenant servers |
| C4 | `agent_revoke()` crashes with NameError — undefined variables `company_id`, `type`, `message`, `link` | `main.py:179-187` | Cancel/delete on provisioned requests returns 500, operation fails silently |
| C5 | Shared agent API key with hardcoded fallback — single key for all companies | `config.py:8`, `main.py:170` | Compromise of one agent breaks trust for all |
| C6 | HMAC bypass when api_key found in Agent table but not Company table — no signature verification | `main.py:196-201` | Agent can register without proving possession of secret |

### High

| # | Finding | File/Line | Impact |
|---|---------|-----------|--------|
| H1 | JWT leaked in URL query parameter on every API request | `frontend_html.py` (api helper) | Token exposed in server logs, browser history, referer headers |
| H2 | Token stored in localStorage — XSS accessible | `frontend_html.py` (init) | Any XSS vulnerability leads to full account takeover |
| H3 | No timestamp/nonce in HMAC — replay attacks possible | `main.py:496-585` | Captured agent requests can be replayed indefinitely |
| H4 | Admin can approve/reject requests across companies — no company scope check | `main.py:889-959` | Cross-tenant access escalation |
| H5 | No company ownership check on `GET /api/servers/{id}` and `GET /api/sessions/{id}` | `main.py:766-782, 1041-1061` | Information disclosure across tenants |
| H6 | No rate limiting on any endpoint — brute-force and DoS possible | All endpoints | Unrestricted login attempts, request creation, API abuse |

### Medium

| # | Finding | File/Line | Impact |
|---|---------|-----------|--------|
| M1 | `GET /api/users` exposes full company user list to regular users | `main.py:589-603` | Information disclosure (names, roles, last login) |
| M2 | Pydantic models have no input validation — no min_length, no regex | `schemas.py:14-19` | Potentially malicious usernames stored in DB, passed to agents |
| M3 | Username sent to agent in expiry revocation without sanitization | `main.py:1535` | Potential command injection in agent (agent-dependent) |
| M4 | `except: pass` in 8+ locations silently swallows errors, especially provisioning failure | `main.py:939-940` | Request approved but user not provisioned — no error feedback |
| M5 | No refresh token rotation — same token valid for 7 days | `main.py:245-259` | Stolen refresh token = persistent access |

### Low

| # | Finding | File/Line | Impact |
|---|---------|-----------|--------|
| L1 | JWT missing `aud`, `iss`, `iat`, `nbf` claims | `auth_utils.py:13-28` | Token reuse possible across services, no origin validation |
| L2 | No HTTPS, no SSL in Nginx | `nginx.conf` | Traffic in plaintext (mitigated by tunnel TLS) |
| L3 | CORS misconfiguration — `*` combined with `allow_credentials=True` | `main.py:107-113` | Browsers ignore credential headers with wildcard origin |
| L4 | No password policy — no length or complexity requirements | `schemas.py:14-19` | Weak passwords in seed data ("user123") |
| L5 | Companies endpoint returns api_key in API response | `main.py:458` | API key transmitted over network in plaintext |
| L6 | Session recordings stored as unbounded JSON — no size limit, no encryption | `database.py:144` | Database bloat, sensitive terminal data persisted indefinitely |
| L7 | `verify_agent_hmac` checks agent lookup after company lookup — inconsistent key validation | `main.py:189-205` | Dual-purpose function has confusing control flow |

### Summary Count

| Severity | Count |
|----------|-------|
| Critical | 6 |
| High | 6 |
| Medium | 5 |
| Low | 7 |
| **Total** | **24** |

### Recommended Immediate Actions

1. **Remove hardcoded secrets from `config.py`** — require `JWT_SECRET`, `JWT_REFRESH_SECRET`, and `AGENT_API_KEY` to be set via environment variables with no fallback. Document `.env.example` without real values.
2. **Fix the `agent_revoke()` NameError** — either remove the notification block (lines 179-187) or complete it with proper variables. Currently it crashes on cancel/delete of provisioned requests.
3. **Fix the HMAC bypass** — ensure `verify_agent_hmac` always performs signature verification before returning, regardless of which table the api_key was found in.
4. **Add company scope checks to approve/reject endpoints** — verify that the request's server belongs to the admin's company before allowing approval/rejection.
5. **Encrypt secrets at rest** — hash API keys with bcrypt (or at minimum encrypt them at the application level), and store SSH private keys encrypted in the database.
6. **Add rate limiting** — especially on login (`POST /api/auth/login`) and request creation (`POST /api/requests`).
7. **Move JWT from URL to httpOnly cookies** — eliminate the `?token=` query parameter and switch to `Set-Cookie` with `httpOnly`, `Secure`, `SameSite=Strict`.
