# Feature Walkthrough — PAM Server

> Source: `main.py` (1563 lines), `frontend_html.py` (1342 lines), `auth_utils.py` (30 lines)  
> Core capability descriptions for the five primary product features

---

## Table of Contents

1. [Just-in-Time Access Request Lifecycle](#1-just-in-time-access-request-lifecycle)
2. [Session Recording and Replay](#2-session-recording-and-replay)
3. [Real-Time Suspicious Activity Detection](#3-real-time-suspicious-activity-detection)
4. [Comprehensive Audit Logging](#4-comprehensive-audit-logging)
5. [Notification System](#5-notification-system)

---

## 1. Just-in-Time Access Request Lifecycle

The core workflow of the PAM system is a five-stage JIT access lifecycle: **Request → Approval → Provisioning → Connection → Expiry**. Each stage is persisted in the database and tracked via audit logs.

### 1.1 Lifecycle Diagram

```mermaid
sequenceDiagram
    actor User
    actor Admin
    participant PAM as PAM Server
    participant Agent as Tenant Agent (VM2)
    participant VM as Target VM

    User->>PAM: POST /api/requests<br/>{server_id, access_level, duration}
    PAM->>PAM: Create Request record (status: pending)
    PAM->>Admin: Notify "new access request"
    PAM->>User: Notify "request submitted"

    Admin->>PAM: POST /api/requests/{id}/approve
    PAM->>PAM: Set status: approved<br/>Set expires_at = now + duration
    PAM->>Agent: POST /agent/provision<br/>{username_to_create, privilege, duration}
    Agent->>Agent: Create JIT Linux user<br/>(useradd / usermod)
    Agent-->>PAM: {username, ssh_private_key}
    PAM->>PAM: Store provisioned_username<br/>& ssh_private_key
    PAM->>Admin: Notify "request approved"

    User->>PAM: WebSocket /ws/terminal<br/>{action: "join_session", requestId, serverId}
    PAM->>PAM: Create Session record (status: active)
    PAM->>VM: SSH connect (JIT credentials)
    VM-->>PAM: Shell ready
    PAM-->>User: Terminal I/O stream

    Note over VM,User: Session active until disconnect or expiry

    PAM->>PAM: Periodic check every 60s<br/>expires_at ≤ now?
    PAM->>PAM: Set status: expired
    PAM->>Agent: POST /agent/revoke<br/>{username}
    Agent->>Agent: Remove JIT Linux user
    PAM->>VM: Terminate SSH session
```

### 1.2 Stage Details

#### Stage 1: Request Creation

A user submits an access request through the Servers page or the My Requests page:

```
POST /api/requests
Body: { server_id, access_level: "user"|"root", duration_minutes, description? }
```

The backend:
1. Validates the server exists, is active, and belongs to the user's company
2. Creates a `Request` record with `status: pending` and `requested_at: now`
3. Logs a `request_created` audit event
4. Notifies all superusers and the company's admin via the notification system
5. Returns the new request ID to the user

#### Stage 2: Approval

An admin or superuser reviews pending requests on the Approvals page:

```
POST /api/requests/{id}/approve
```

The backend:
1. Validates the request is in `pending` status
2. Sets `status: approved`, `approved_at: now`, and `approved_by: <admin_id>`
3. Calculates `expires_at = now + duration_minutes`
4. Logs a `request_approved` audit event
5. Notifies the requester that their request was approved

#### Stage 3: Agent Provisioning

Immediately after approval, the backend calls the Tenant Agent on the target VM:

```
POST http://{server.ip}:8800/agent/provision
Headers: X-API-Key: <company_api_key>
Body: {
  "request_id": "<uuid>",
  "username_to_create": "jit-a1b2c3d4",
  "privilege": "user"|"root",
  "duration_minutes": 30,
  "expires_at": "2026-07-11T17:23:00Z"
}
```

The Tenant Agent:
1. Creates a Linux user with a random JIT username (`jit-<8 hex chars>`)
2. Generates a per-request SSH key pair
3. Configures the user with the requested privilege level (`root` = added to `sudo` / `wheel` group)
4. Returns the JIT username and SSH private key to the PAM Server

The PAM Server stores the `provisioned_username` and `ssh_private_key` on the request record and logs an `agent_provisioned` audit event.

#### Stage 4: SSH Connection

The user opens a terminal session from the browser:

1. The frontend opens a WebSocket to `/ws/terminal?token=<jwt>`
2. The user sends `{action: "join_session", requestId, serverId}`
3. The backend creates a `Session` database record with `status: active`
4. The backend reads the provisioned credentials from the request
5. If a per-request SSH key exists (from agent provisioning), it's written to a temporary file and used for authentication
6. Otherwise, the backend falls back to the default `pam-service` user with the host's SSH key
7. `asyncssh` establishes the SSH connection to `server.ip:server.port`
8. The backend sends `{"type": "ssh_ready"}` and the terminal I/O loop begins

#### Stage 5: Expiry and Cleanup

The system enforces access expiry through two mechanisms:

**Active expiry (during a session):** Every second during an active terminal session, the frontend polls the request's `expires_at`. When remaining time reaches zero, it displays "EXPIRED" and calls `terminateSession()`.

**Background expiry sweep (`expire_old_requests` at line 1515):** A background async task runs every 60 seconds. It queries for approved requests whose `expires_at <= now`, marks them as `expired`, and attempts to revoke the JIT user by calling the Tenant Agent's `/agent/revoke` endpoint.

When a session ends (disconnect, terminate, or expiry), the recording array is written to the database, the session status is set to `ended`, and the JIT credentials remain on the request record for audit purposes.

---

## 2. Session Recording and Replay

Every keystroke and every byte of terminal output during an SSH session is captured, stored, and made available for playback.

### 2.1 Capture Architecture

The recording is accumulated in an in-memory Python list during the WebSocket session:

```python
# Initialized when the session is created
recording = []

# On input from user
recording.append({"timestamp": time.time(), "event": "input", "data": msg["data"]})

# On output from SSH stdout/stderr
recording.append({"timestamp": time.time(), "event": "output", "data": masked_text})
```

Three code paths append to the recording array:

| Path | Location | Trigger | `event` value |
|------|----------|---------|---------------|
| User input | Line 1432 | `websocket.receive_json()` with `type: "terminal_input"` | `"input"` |
| SSH stdout | Line 1381 | `async for data in stdout_r` | `"output"` |
| SSH stderr | Line 1397 | `async for data in stderr_r` | `"output"` |

Each entry captures:
- **`timestamp`**: Unix epoch seconds (float) from `datetime.utcnow().timestamp()`, enabling millisecond-precision timing for replay pacing
- **`event`**: Either `"input"` or `"output"` — distinguishes user commands from server responses
- **`data`**: The raw terminal text. For output, this may include ANSI escape codes, carriage returns, and tab characters. For input, this is the command string including the trailing `\n`

### 2.2 Key Masking

Before any output entry is added to the recording, it passes through `mask_ssh_keys()` (line 68-69):

```python
SSH_KEY_PATTERN = re.compile(
    r'-----BEGIN\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----'
    r'[\s\S]*?-----END\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----',
    re.IGNORECASE
)

def mask_ssh_keys(text: str) -> str:
    return SSH_KEY_PATTERN.sub('[SSH KEY REDACTED]', text)
```

This regex matches any PEM-encoded private key (RSA, OpenSSH, or EC format) that appears in the terminal output. The entire key block is replaced with the literal string `[SSH KEY REDACTED]`. This ensures that if a user or script outputs a private key during a session (e.g., `cat ~/.ssh/id_rsa`), the key content is never stored in the recording database.

The masking is applied before the data enters the recording array and before it's sent to the WebSocket client, so both the stored recording and the live terminal view are sanitized.

Key patterns detected (all formats are matched case-insensitively):
- `-----BEGIN RSA PRIVATE KEY-----`
- `-----BEGIN OPENSSH PRIVATE KEY-----`
- `-----BEGIN EC PRIVATE KEY-----`

### 2.3 Storage

When a session ends (user disconnects, session is terminated, or connection drops), the recording is persisted:

```python
async with async_session() as db:
    sess = await db.execute(select(Session).where(Session.id == session_id))
    sess = sess.scalar_one_or_none()
    if sess:
        sess.recording_data = recording
        sess.status = "ended"
        sess.ended_at = datetime.utcnow()
        await db.commit()
```

The recording is stored in the `sessions.recording_data` column:
- **SQLite**: stored as a JSON text string
- **PostgreSQL**: stored as `JSONB` with support for indexed queries

### 2.4 Replay

The Recordings page lists all ended sessions with user, server, duration, and date. Clicking "Play" fetches the recording:

```
GET /api/sessions/{id}/recording
Response: { "recording": [ { "timestamp": ..., "event": "output", "data": "..." }, ... ] }
```

The frontend opens a replay modal with:
- A black terminal-style display area (monospace font, `#00ff00` green text)
- A "Play" button that iterates through the recording array
- Timed delays between entries computed from the original timestamps (capped at 100ms maximum, 15ms minimum)
- Output entries are appended to the display; input entries (user commands) are skipped during replay visual (they appear as output echo when the remote server echoes them back)

The replay pacing maintains the approximate timing of the original session: commands that were typed quickly appear quickly, while pauses between commands are preserved.

```javascript
function replayRecording(rec) {
  const entry = rec[replayIndex];
  if (entry.event === 'output') {
    wrap.textContent += entry.data;
  }
  replayIndex++;
  const delay = replayIndex < rec.length
    ? Math.min((rec[replayIndex].timestamp - entry.timestamp), 100)
    : 100;
  setTimeout(() => replayRecording(rec), Math.max(delay, 15));
}
```

---

## 3. Real-Time Suspicious Activity Detection

The PAM Server includes a built-in detection engine that scans all terminal I/O in real time for patterns associated with privilege escalation, unauthorized changes, and destructive actions.

### 3.1 Detection Scope

Every byte that passes through the terminal session is inspected — both user input (commands typed) and server output (command results and error messages). The detection runs in the same event loop as the terminal I/O, scanning each chunk of data as it arrives.

```
User input → WebSocket → PAM Server → detect_suspicious_activity() → SSH process
                                          │
                                          ├─ if match → log "suspicious_command"
                                          │
SSH process → stdout/stderr → PAM Server → detect_suspicious_activity() → WebSocket → User
                                          │
                                          ├─ if match → log "suspicious_output"
```

### 3.2 Detection Patterns

Nineteen regular expression patterns are defined at line 41-61, organized into five categories:

**Privilege Escalation (4 patterns):**
| Pattern | Description |
|---------|-------------|
| `sudo <command>` | Attempting to run commands with superuser privileges |
| `su -` or `su <user>` | Switching to another user account |
| `chmod <mode>` with setuid bits (47xx, +s) | Setting the setuid bit on executables |
| `pkexec` / `doas` | Alternative privilege escalation tools |

**Remote Code Execution (3 patterns):**
| Pattern | Description |
|---------|-------------|
| `wget <url> \| bash` or `wget <url> \| sh` | Downloading and executing remote scripts |
| `curl <url> \| bash` or `curl <url> \| sh` | Alternative download-and-execute vector |
| `base64 -d ... \| bash` or `echo ... \| base64 -d \| bash` | Decoding and running obfuscated payloads |

**Unauthorized Package Installation (3 patterns):**
| Pattern | Description |
|---------|-------------|
| `apt-get install`, `apt install`, `yum install`, `dnf install`, `zypper install`, `pacman` | System package manager usage |
| `pip install` | Python package installation |
| `npm install -g` | Global Node.js package installation |

**System Tampering (4 patterns):**
| Pattern | Description |
|---------|-------------|
| `chmod +x <file>` | Making a file executable (potential malware staging) |
| `docker run --privileged` | Running a container with elevated host access |
| Shell fork bomb (`:(){ :|:& };:`) | Fork bomb denial-of-service attempt |
| `dd if=/dev/urandom of=` | Writing random data (potential sabotage) |

**Raw Disk Access (4 patterns):**
| Pattern | Description |
|---------|-------------|
| `cat /dev/sda`, `dd if=/dev/sda`, `fdisk /dev/sda` | Reading raw block devices |
| `> /dev/sda`, `mkfs.*`, `fdisk /dev/` | Disk destruction or formatting |

### 3.3 Alert Severity

Every detected pattern is classified as `critical` severity. When a match is found, the system:

1. Creates an audit log entry with `event_type: "suspicious_command"` (for input) or `"suspicious_output"` (for output)
2. Includes the matched description in the `action_detail` field (e.g., "Privilege escalation: sudo command used")
3. Associates the alert with the session ID as the `target`, enabling administrators to locate the exact session and recording where the event occurred
4. Sets `security_status: "critical"` for all pattern matches

### 3.4 Alert Context in the UI

On the Audit Logs page, suspicious events are displayed with:
- A red badge for `security_status: critical`
- The specific pattern description in the Details column
- The session ID as the target, linking to the recorded session
- A "Terminate" action button that allows an admin to immediately end the session

The terminate action sends a POST to `/api/sessions/{sessionId}/terminate`, which both ends the SSH process and marks the session as `terminated` in the database.

---

## 4. Comprehensive Audit Logging

Every meaningful action in the system is recorded in the `audit_logs` table with a consistent schema, providing a complete, searchable history of all events across all tenants.

### 4.1 Audit Log Schema

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `timestamp` | DateTime | When the event occurred (UTC) |
| `event_type` | String | Event classifier (26 known types) |
| `performed_by` | String | Actor identifier (username or "system") |
| `target` | String | Target entity ID (optional) |
| `action_detail` | Text | Human-readable description of the event |
| `company_id` | UUID | Tenant scoping (nullable) |
| `security_status` | Enum | `info`, `warning`, or `critical` |
| `source` | String | Origin system (default: "pam-server") |

### 4.2 Event Categories

**Authentication Events (4 types):**
- `login` — successful user login (status: info)
- `login_failed` — failed login attempt (status: warning)
- `password_change` — user changed their password (status: info)
- `username_change` — user changed their username (status: info)

**Company Management (2 types):**
- `company_created` — superuser created a new tenant (status: info)
- `company_deleted` — superuser removed a tenant (status: warning)

**User Management (2 types):**
- `user_created` — new user account created (status: info)
- `user_status_change` — user activated/deactivated (status: info/warning)

**Server Management (3 types):**
- `server_created` — new target server registered (status: info)
- `server_deleted` — target server removed (status: warning)
- `server_status_change` — server marked active/inactive (status: info)

**Request Lifecycle (6 types):**
- `request_created` — user submitted a new access request (status: info)
- `request_approved` — admin approved a request (status: info)
- `request_rejected` — admin denied a request (status: info)
- `request_expired` — system flagged an expired request (status: info)
- `request_cancelled` — user cancelled their own request (status: info)
- `request_deleted` — request record removed (status: info)

**Session Events (1 type):**
- `session_terminated` — admin forcibly ended a session (status: warning)

**Security Events (2 types):**
- `suspicious_command` — user typed a monitored pattern (status: critical)
- `suspicious_output` — SSH output contained a monitored pattern (status: critical)

**Agent Events (2 types):**
- `agent_registered` — tenant agent registered on startup (status: info)
- `agent_provisioned` — agent created a JIT Linux user (status: info)

**Billing Events (1 type):**
- `billing_funds_added` — funds deposited to a billing account (status: info)

**System Events (1 type):**
- `system_init` — server started up (status: info)

### 4.3 Audit Log Page Features

The Audit Logs page (accessible to admins and superusers) provides:

**Pagination:** 50 logs per page with Previous/Next navigation and a page counter. The pagination offset is tracked client-side via the `auditPage` variable (resets to 0 on "Clear Filters").

**Column display:** Each row shows Timestamp (formatted with `toLocaleString()`), Event type (blue badge), Performed by (actor), Target (truncated UUID), Details (event description), Security status (red/yellow/blue badge), and an Action column.

**Context-sensitive actions:** When a log entry has `event_type` of `suspicious_command` or `suspicious_output` and a `target` (session ID), a "Terminate" button appears that allows the admin to immediately end the associated SSH session.

**CSV export:** The "Export CSV" button opens `/api/audit-logs/export` in a new tab, downloading the full audit log as a CSV file for offline analysis or external SIEM import.

### 4.4 Tenant Scoping

When an admin views the audit log, only events within their own company are shown. Superusers can view events across all tenants. This is enforced at the query level:

```python
if payload["role"] != "superuser":
    query = query.where(AuditLog.company_id == get_user_id(payload["company_id"]))
```

### 4.5 Audit Event Recording

The `log_audit` helper function (line 122-130) creates audit entries consistently:

```python
async def log_audit(db, event_type, performed_by, target=None,
                    action_detail=None, company_id=None, security_status="info"):
    entry = AuditLog(
        event_type=event_type, performed_by=performed_by, target=target,
        action_detail=action_detail,
        company_id=get_user_id(company_id) if company_id else None,
        security_status=SecurityStatus(security_status)
    )
    db.add(entry)
    await db.commit()
```

This function is called from 28 locations across the codebase, ensuring every significant action produces a structured, timestamped audit record before the response is sent to the client.

---

## 5. Notification System

The notification system keeps users informed about important events in real time, both through in-app notifications and a persistent unread badge.

### 5.1 Notification Model

Notifications are stored in the `notifications` table with:

| Field | Type | Description |
|-------|------|-------------|
| `id` | UUID | Primary key |
| `user_id` | UUID FK | Recipient user |
| `type` | String | Notification category (e.g., `new_request`, `request_approved`) |
| `message` | Text | Human-readable notification body |
| `link` | String | Client-side route path for navigation on click |
| `read` | Boolean | Whether the user has dismissed the notification |
| `created_at` | DateTime | When the notification was generated |

### 5.2 Notification Triggers

Notifications are sent for the following events:

| Event | Recipient | Type | Message | Link |
|-------|-----------|------|---------|------|
| New access request | All superusers + company admin | `new_request` | "New access request from {username} for {server}" | `/approvals` |
| Request approved | Requester | `request_approved` | "Your access request has been approved" | `/my-requests` |
| Request rejected | Requester | `request_rejected` | "Your access request has been rejected" | `/my-requests` |
| User created | All superusers + company admin | `user_created` | "New user {name} has been created" | `/users` |
| Session terminated | Session user | (future use) | — | — |

### 5.3 Delivery Mechanisms

**Persistent storage:** Each notification is written to the database immediately. This ensures notifications survive page refreshes, browser restarts, and server restarts.

**WebSocket push (real-time delivery):** When a notification is created, the system checks if the recipient has an active WebSocket connection (stored in the `active_connections` dictionary at line 38):

```python
ws = active_connections.get(user_id)
if ws:
    try:
        await ws.send_json({"type": "notification", "data": {...}})
    except:
        pass
```

This pushes the notification to the browser immediately without requiring polling.

**Unread count polling:** On page load and when the notification bell is clicked, the frontend fetches the unread count from `/api/notifications/unread-count`. This provides a fallback for notification delivery if the WebSocket push fails.

### 5.4 Frontend Experience

**Bell icon:** The notification bell in the top bar displays the unread count as a red badge (`#notif-badge`). The badge is hidden when the count is zero and shown when there are unread notifications.

**Notification drawer:** Clicking the bell opens a modal showing the 20 most recent notifications. Each notification shows:
- The message text
- The creation timestamp
- A blue left border indicator for unread items
- Reduced opacity (0.6) for read items
- Clicking a notification marks it as read and navigates to the linked page

**Mark all read:** A "Mark All Read" button at the top of the drawer sends `POST /api/notifications/read-all`, which uses a bulk SQL update:

```python
await db.execute(
    text("UPDATE notifications SET read = true WHERE user_id = :uid AND read = false"),
    {"uid": get_user_id(payload["user_id"])}
)
```

### 5.5 Notification to Admins and Superusers

The `notify_admins_and_superusers` helper function (line 143-150) targets both superusers (cross-tenant) and the specific company's admin:

```python
result = await db.execute(
    select(User).where(
        or_(User.role == UserRole.superuser,
            and_(User.role == UserRole.admin,
                 User.company_id == get_user_id(company_id)))
    )
)
```

This ensures that:
- **Superusers** see notifications from all companies (they manage the entire system)
- **Admins** only see notifications relevant to their own company (they manage one tenant)
- **Users** see only their own notifications (request status changes)
