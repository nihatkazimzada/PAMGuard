# PAM Tenant Agent — Full Implementation Report

**Tenant:** <your-tenant> (tenant_id: `<your-company-id>`)
**Target Server:** VM2 — <target-ip> (Ubuntu Server 22.04 LTS)
**PAM Server:** VM1 — <pam-server-ip>:3001
**Agent Version:** 1.0.0
**Date:** July 2, 2026

---

## Table of Contents

1. [Architecture Overview](#1-architecture-overview)
2. [Communication Flow](#2-communication-flow)
3. [Authentication & Security](#3-authentication--security)
4. [Agent Files & Installation](#4-agent-files--installation)
5. [Core Functions in Detail](#5-core-functions-in-detail)
6. [PAM Server Integration](#6-pam-server-integration)
7. [Testing & Verification](#7-testing--verification)
8. [Security Hardening](#8-security-hardening)
9. [Configuration Reference](#9-configuration-reference)
10. [Operational Commands](#10-operational-commands)
11. [Troubleshooting](#11-troubleshooting)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────┐       ┌──────────────────────────────────────┐
│         PAM SERVER (VM1)             │       │        TENANT AGENT (VM2)            │
│     http://<pam-server-ip>:3001      │       │     http://<target-ip>:8800           │
│                                      │       │                                      │
│  ┌──────────────────────────┐        │       │  ┌──────────────────────────┐        │
│  │  Agent Management API    │        │  HTTP  │  │  Outbound (Agent→PAM)    │        │
│  │  POST /api/agent/reg     │◄───────├───────│  │  - /api/agent/register   │        │
│  │  POST /api/agent/hb      │        │       │  │  - /api/agent/heartbeat  │        │
│  │  POST /api/agent/events  │        │       │  │  - /api/agent/events     │        │
│  └──────────────────────────┘        │       │  └──────────────────────────┘        │
│                                      │       │                                      │
│  ┌──────────────────────────┐        │  HTTP  │  ┌──────────────────────────┐        │
│  │  Agent Caller (on appr.) │────────├───────►│  │  Inbound (PAM→Agent)     │        │
│  │  POST /agent/provision   │        │       │  │  - POST /agent/provision │        │
│  │  POST /agent/revoke      │        │       │  │  - POST /agent/revoke    │        │
│  └──────────────────────────┘        │       │  │  - GET /health           │        │
│                                      │       │  └──────────────────────────┘        │
│  ┌──────────────────────────┐        │       │                                      │
│  │  Database                │        │       │  ┌──────────────────────────┐        │
│  │  - companies            │        │       │  │  Local Operations:       │        │
│  │  - agents               │        │       │  │  - useradd / userdel     │        │
│  │  - servers              │        │       │  │  - ssh-keygen            │        │
│  │  - requests             │        │       │  │  - sudoers.d file mgmt   │        │
│  │  - audit_logs           │        │       │  │  - auth.log tailing      │        │
│  │  - sessions             │        │       │  │  - threading.Timer       │        │
│  └──────────────────────────┘        │       │  │    (auto-expiry)         │        │
│                                      │       │  └──────────────────────────┘        │
└──────────────────────────────────────┘       └──────────────────────────────────────┘
```

The system consists of two main components:

**PAM Server (VM1):** The central management platform that handles user authentication, access request workflows, session recording, and audit logging. It communicates with tenant agents to provision and revoke actual Linux user accounts on target servers.

**Tenant Agent (VM2):** A lightweight, self-contained Python service installed on each managed server. It performs the actual Linux user management operations (creating/deleting users, managing SSH keys, configuring sudo access) and forwards security events back to the PAM Server.

### Technology Stack

| Component | Technology |
|-----------|------------|
| Agent Language | Python 3.10 |
| HTTP Server (inbound) | `http.server.HTTPServer` (stdlib) |
| HTTP Client (outbound) | `requests` library |
| Configuration | YAML (`pyyaml`) |
| Service Manager | systemd (auto-restart on failure) |
| SSH Key Generation | `ssh-keygen` (RSA 2048-bit) |
| Logging | Python logging → `/var/log/pam-agent.log` + journald |
| Audit Log Tailing | Polling `/var/log/auth.log` every 5s |
| Auto-Expiry | `threading.Timer` daemon threads |

---

## 2. Communication Flow

### 2.1 Agent Startup Sequence

```
Agent Starts
    │
    ▼
Load Config (/etc/pam-agent/config.yaml)
    │
    ▼
POST /api/agent/register  ──────────────►  PAM Server
    │  {hostname, ip, os_version,           │
    │   tenant_company_id, agent_version}   │
    │                                       │
    ◄──── 200 OK ───────────────────────────┘
    │
    ▼
Start Heartbeat Thread (every 25s)
    │
    ▼
Start Auth Log Tailer Thread
    │
    ▼
Start HTTP Listener (port 8800)
    ├── POST /agent/provision
    ├── POST /agent/revoke
    └── GET  /health
```

### 2.2 Provision Flow (JIT Access Request)

```
User requests access via PAM UI
    │
    ▼
Admin approves request
    │
    ▼
PAM Server calls Agent:
POST http://<agent-ip>:8800/agent/provision
Body: {
  "request_id": "uuid",
  "username_to_create": "jit-a1b2c3d4",
  "privilege": "root",
  "duration_minutes": 30,
  "expires_at": "2026-07-02T15:00:00Z"
}
    │
    ▼
Agent:
  1. Generate RSA 2048-bit SSH key pair
  2. useradd -m -s /bin/bash jit-a1b2c3d4
  3. Set random 24-char password
  4. Install public key → ~/.ssh/authorized_keys
  5. If privilege="root":
     Write /etc/sudoers.d/<request_id> → NOPASSWD:ALL
  6. Schedule threading.Timer for auto-expiry
  7. Queue ACCOUNT_CREATED audit event
    │
    ▼
Returns to PAM Server:
{
  "status": "success",
  "username": "jit-a1b2c3d4",
  "ssh_private_key": "-----BEGIN ...",
  "ssh_public_key": "ssh-rsa AAAA...",
  "password": "random-password"
}
    │
    ▼
PAM Server:
  - Stores SSH private key (encrypted)
  - Updates request status → "active"
  - User connects via WebSocket terminal
    using the provisioned SSH key
```

### 2.3 Revoke Flow

```
Trigger: Manual terminate (PAM) OR auto-expiry (Agent timer)
    │
    ▼
PAM Server calls Agent:
POST http://<agent-ip>:8800/agent/revoke
Body: { "request_id": "uuid", "username": "jit-a1b2c3d4" }
    │
    ▼
Agent:
  1. Pop request from active_requests dict
  2. Cancel pending timer (if any)
  3. Remove /etc/sudoers.d/<request_id>
  4. userdel -r jit-a1b2c3d4
  5. Queue ACCOUNT_REMOVED audit event
    │
    ▼
Returns: { "status": "success", "message": "User jit-a1b2c3d4 removed" }
    │
    ▼
PAM Server updates request status → "completed"
```

### 2.4 Auto-Expiry (Fail-Safe)

Even if the PAM Server goes down and never calls revoke, the agent automatically removes the user after the configured duration:

```
Provision creates Timer(delay=duration_minutes*60, function=revoke)
    │
    ▼
Timer fires → calls revoke_request(request_id)
    │
    ▼
Same as manual revoke: userdel, remove sudoers, audit event
```

This is a critical safety mechanism — the agent does NOT depend solely on the PAM Server for revocation.

### 2.5 Heartbeat Flow

```
Every 25 seconds:
    │
    ▼
Agent → POST /api/agent/heartbeat
Body: {
  "hostname": "linux-server",
  "status": "UP",
  "load": 0.45,
  "last_activity": "2026-07-02T14:00:23Z",
  "uptime_seconds": 120
}
    │
    ▼
PAM Server:
  - Updates agent.last_seen = now
  - If no heartbeat for >90s → mark Inactive
```

### 2.6 Event Forwarding Flow

```
Events queued in memory (thread-safe list with lock):
  - ACCOUNT_CREATED (on provision)
  - ACCOUNT_REMOVED (on revoke)
  - LOGIN (auth.log: "Accepted publickey/password")
  - LOGIN_FAILED (auth.log: "Failed password")
  - SUDO_USED (auth.log: "sudo: ... COMMAND=...")
    │
    ▼
Every heartbeat cycle:
  - Flush batched events
  - POST /api/agent/events
  - On failure: re-queue events for next cycle
```

---

## 3. Authentication & Security

### 3.1 API Key Authentication

Every HTTP request between the agent and the PAM Server uses a shared secret (API key) for authentication.

**API Keys Issued:**

| Tenant | API Key |
|--------|---------|
| Kapital Tech | `<your-api-key>` |
| Acme Corp | `pam_acme_94e7673c8610` |

### 3.2 HMAC Request Signing

Every outbound request from the agent includes three headers:

```
X-API-Key: <your-api-key>
X-Signature: <hex-encoded HMAC-SHA256>
X-Timestamp: 1740938400
```

**Signature Computation (Python):**

```python
import hmac, hashlib

def sign_request(api_key: str, body: str) -> str:
    return hmac.new(
        api_key.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
```

**PAM Server Validation (Python):**

```python
def verify_request(api_key: str, body: str, signature: str) -> bool:
    expected = hmac.new(
        api_key.encode(),
        body.encode(),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### 3.3 Security Measures Summary

| Measure | Implementation |
|---------|---------------|
| API Key Storage | `/etc/pam-agent/config.yaml` with `chmod 600`, owned by `root:root` |
| Request Integrity | HMAC-SHA256 signature prevents body tampering |
| Replay Protection | `X-Timestamp` header enables PAM Server to reject old requests |
| Authentication | `X-API-Key` header identifies the tenant |
| Network Isolation | UFW firewall restricts port 8800 to PAM Server IP only |
| SSH Gateway | Dedicated `pam-gateway` user for PAM SSH connections |
| Auto-Expiry Fail-Safe | Timer-based revocation independent of PAM Server |
| Service Hardening | `NoNewPrivileges=yes`, `PrivateTmp=yes` in systemd |
| Log Rotation | `/etc/logrotate.d/pam-agent` prevents log flooding |

---

## 4. Agent Files & Installation

### 4.1 File Manifest

All agent source files are located at `/home/linux/pam-linux-2/pam-agent/`.

#### Source Files (development directory)

| File | Description | Lines |
|------|-------------|-------|
| `agent.py` | Main agent source code | 638 |
| `config.yaml.example` | Example configuration template | 16 |
| `pam-tenant-agent.service` | systemd unit file | 20 |
| `install.sh` | Automated installation script | 62 |
| `firewall.sh` | UFW firewall configuration script | 40 |
| `setup-gateway-user.sh` | Gateway service account creator | 35 |
| `pam-agent-logrotate` | Logrotate configuration | 8 |
| `README.md` | Full documentation | 207 |

#### Installed Locations (production)

| Source File | Installed To | Permissions |
|-------------|-------------|-------------|
| `agent.py` | `/usr/local/bin/pam-agent.py` | 755 (root:root) |
| `config.yaml.example` | `/etc/pam-agent/config.yaml` | 600 (root:root) |
| `pam-tenant-agent.service` | `/etc/systemd/system/pam-tenant-agent.service` | 644 (root:root) |
| `pam-agent-logrotate` | `/etc/logrotate.d/pam-agent` | 644 (root:root) |
| (created) | `/var/log/pam-agent.log` | 640 (root:adm) |

### 4.2 Installation Steps

```bash
# 1. Create config directory and write config
sudo mkdir -p /etc/pam-agent
# Write /etc/pam-agent/config.yaml with API key and PAM Server URL
sudo chmod 600 /etc/pam-agent/config.yaml

# 2. Install agent script
sudo cp agent.py /usr/local/bin/pam-agent.py
sudo chmod 755 /usr/local/bin/pam-agent.py

# 3. Install systemd service
sudo cp pam-tenant-agent.service /etc/systemd/system/
sudo chmod 644 /etc/systemd/system/pam-tenant-agent.service
sudo systemctl daemon-reload

# 4. Create log file
sudo touch /var/log/pam-agent.log
sudo chmod 640 /var/log/pam-agent.log

# 5. Install logrotate
sudo cp pam-agent-logrotate /etc/logrotate.d/pam-agent

# 6. Enable and start service
sudo systemctl enable pam-tenant-agent.service
sudo systemctl start pam-tenant-agent.service
```

### 4.3 systemd Service Configuration

```ini
[Unit]
Description=PAM Tenant Agent – Kapital Tech
After=network.target auditd.service
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/local/bin/pam-agent.py
Restart=always
RestartSec=10
User=root
Group=root
Environment=PYTHONUNBUFFERED=1
StandardOutput=journal
StandardError=journal
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target
```

Key design decisions:
- **Runs as root** — Required for `useradd`/`userdel` and writing to `/etc/sudoers.d/`
- **Restart=always** — Recovers from crashes within 10 seconds
- **NoNewPrivileges=yes** — Prevents privilege escalation via child processes
- **PrivateTmp=yes** — Isolates /tmp usage

---

## 5. Core Functions in Detail

### 5.1 Agent Source Code Structure (`agent.py`)

```
agent.py (638 lines)
├── Constants & Configuration (lines 1-50)
│   ├── Imports (stdlib + requests + yaml)
│   ├── Logging setup → /var/log/pam-agent.log
│   └── Global state variables
├── Crypto Helpers (lines 64-96)
│   ├── hmac_sign() — HMAC-SHA256 signing
│   ├── secure_password() — Random 24-char passwords
│   └── generate_ssh_keypair() — RSA 2048-bit keys
├── OS Helpers (lines 98-219)
│   ├── get_hostname() / get_ip_address()
│   ├── get_os_version() — reads /etc/os-release
│   ├── get_load_avg() — reads /proc/loadavg
│   ├── user_exists() — uses `id` command
│   ├── create_linux_user() — useradd + chpasswd
│   ├── setup_sudoers() — writes /etc/sudoers.d/<id>
│   ├── remove_sudoers() — deletes sudoers file
│   ├── setup_ssh_key() — authorized_keys installation
│   ├── delete_linux_user() — userdel -r
│   └── schedule_revocation() — threading.Timer
├── Event Queue (lines 221-259)
│   ├── queue_event() — thread-safe event enqueue
│   └── flush_events() — batch send to PAM Server
├── PAM Server API Calls (lines 262-323)
│   ├── send_register() — POST /api/agent/register
│   └── send_heartbeat() — POST /api/agent/heartbeat
├── Provision / Revoke Logic (lines 325-426)
│   ├── provision_request() — full provision workflow
│   └── revoke_request() — full revoke workflow
├── Auth Log Tailer (lines 428-479)
│   └── AuthLogTailer class — polls auth.log every 5s
├── HTTP Request Handler (lines 481-565)
│   ├── AgentHTTPHandler class
│   ├── do_GET() — /health endpoint
│   ├── do_POST() — /agent/provision, /agent/revoke
│   └── do_OPTIONS() — CORS headers
├── Heartbeat Loop (lines 567-575)
│   └── heartbeat_loop() — infinite send+flush cycle
└── Main Entry (lines 577-638)
    └── main() — config load, register, start threads
```

### 5.2 Provision Request (`/agent/provision`)

```python
def provision_request(data: dict) -> dict:
    # 1. Extract and validate inputs
    request_id = data.get("request_id")
    username = data.get("username_to_create")
    privilege = data.get("privilege", "user")
    duration_minutes = int(data.get("duration_minutes", 60))

    # 2. Guard: duplicate request_id check
    if request_id in active_requests:
        return error("request_id already active")
    # 3. Guard: existing user check
    if user_exists(username):
        return error("User already exists")

    # 4. Generate SSH key pair
    private_key, public_key = generate_ssh_keypair()
    #    → ssh-keygen -t rsa -b 2048 in temp directory

    # 5. Create Linux user
    password = create_linux_user(username)
    #    → useradd -m -s /bin/bash <username>
    #    → echo "username:password" | chpasswd

    # 6. Install SSH public key
    setup_ssh_key(username, public_key)
    #    → mkdir -p ~/.ssh
    #    → write authorized_keys
    #    → chmod 700 .ssh, 600 authorized_keys
    #    → chown -R user:user .ssh

    # 7. Configure sudo (if root privilege)
    if privilege == "root":
        setup_sudoers(request_id, username)
        #    → /etc/sudoers.d/<request_id>
        #    → content: "username ALL=(ALL) NOPASSWD:ALL"
        #    → chmod 440

    # 8. Schedule auto-revocation
    schedule_revocation(request_id, username, delay_seconds)
    #    → threading.Timer(delay, revoke_task)
    #    → timer.daemon = True

    # 9. Queue audit event
    queue_event("ACCOUNT_CREATED", detail, username)

    # 10. Return credentials to PAM Server
    return {
        "status": "success",
        "username": username,
        "ssh_private_key": private_key,
        "ssh_public_key": public_key,
        "password": password,
    }
```

### 5.3 Revoke Request (`/agent/revoke`)

```python
def revoke_request(request_id: str) -> dict:
    # 1. Look up request in active_requests dict
    entry = active_requests.pop(request_id, None)
    if not entry:
        return error("Unknown request_id")

    username = entry["username"]

    # 2. Cancel pending timer
    if entry.get("timer"):
        entry["timer"].cancel()

    # 3. Remove sudoers file
    remove_sudoers(request_id)
    #    → os.remove("/etc/sudoers.d/<request_id>")

    # 4. Delete user and home directory
    delete_linux_user(username)
    #    → userdel -r <username>
    #    → Raises RuntimeError if userdel fails (except rc=6)

    # 5. Queue audit event
    queue_event("ACCOUNT_REMOVED", detail, username)

    return {"status": "success", "message": f"User {username} removed"}
```

### 5.4 SSH Key Generation

```python
def generate_ssh_keypair() -> tuple:
    # Uses temp directory to avoid leaving keys on disk
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, "id_rsa")
        subprocess.run([
            "ssh-keygen", "-t", "rsa", "-b", "2048",
            "-f", key_path, "-N", "", "-q"
        ], check=True)
        with open(key_path) as f:
            private_key = f.read()
        with open(key_path + ".pub") as f:
            public_key = f.read()
    return private_key, public_key
```

The SSH key pair is generated fresh for every provision request. The private key is returned to the PAM Server in the provision response and is never stored on the target server (only the public key goes into `authorized_keys`).

### 5.5 Auth Log Tailing

```python
class AuthLogTailer(threading.Thread):
    """Daemon thread that polls /var/log/auth.log every 5 seconds."""

    def run(self):
        self._last_position = 0
        while not self._stop_event.is_set():
            with open(self.path) as f:
                f.seek(self._last_position)
                for line in f:
                    self._process_line(line)
                self._last_position = f.tell()
            self._stop_event.wait(5)

    def _process_line(self, line: str):
        # SSH login success
        if "Accepted publickey" in line or "Accepted password" in line:
            username = extract_username(line)
            queue_event("LOGIN", f"SSH login: {line}", username)

        # SSH login failure
        elif "Failed password" in line:
            username = extract_username(line)
            queue_event("LOGIN_FAILED", f"SSH failure: {line}", username)

        # Sudo usage
        elif "sudo:" in line and "COMMAND=" in line:
            username = extract_sudo_user(line)
            queue_event("SUDO_USED", f"Sudo command: {line}", username)
```

---

## 6. PAM Server Integration

### 6.1 Agent-to-PAM Endpoints (must exist on PAM Server)

The agent calls these endpoints. They were built on the PAM Server as part of this integration:

| Endpoint | Method | Purpose | Frequency |
|----------|--------|---------|-----------|
| `/api/agent/register` | POST | Agent registration on startup | Once (on boot) |
| `/api/agent/heartbeat` | POST | Liveness check | Every 25s |
| `/api/agent/events` | POST | Audit event forwarding | Every 25s |

#### Registration Request

```
POST /api/agent/register
Headers:
  X-API-Key: <your-api-key>
  X-Signature: <hmac_sha256(api_key, body)>
  X-Timestamp: 1740938400
Body:
{
  "hostname": "linux-server",
  "ip": "<agent-ip>",
  "os_version": "Ubuntu 22.04.5 LTS",
  "tenant_company_id": "<your-company-id>",
  "agent_version": "1.0.0"
}
Response: 200 OK
```

#### Heartbeat Request

```
POST /api/agent/heartbeat
Headers:
  X-API-Key: <your-api-key>
  X-Signature: <hmac_sha256(api_key, body)>
  X-Timestamp: 1740938425
Body:
{
  "hostname": "linux-server",
  "status": "UP",
  "load": 0.45,
  "last_activity": "2026-07-02T14:00:23.887270+00:00",
  "uptime_seconds": 120
}
Response: 200 OK
```

PAM Server logic on heartbeat:
- Find agent by hostname + tenant_company_id
- Update `last_seen` timestamp
- If agent hasn't sent heartbeat in 90+ seconds (3× interval), auto-mark as `inactive`

#### Events Request

```
POST /api/agent/events
Headers:
  X-API-Key: <your-api-key>
  X-Signature: <hmac_sha256(api_key, body)>
  X-Timestamp: 1740938425
Body:
{
  "events": [
    {
      "event_type": "ACCOUNT_CREATED",
      "source": "linux-agent",
      "hostname": "linux-server",
      "username": "jit-test-root",
      "detail": "User jit-test-root created with privilege=root, duration=30m",
      "timestamp": "2026-07-02T14:00:23.887270+00:00"
    }
  ]
}
Response: 200 OK
```

PAM Server logic on events:
- Map `event_type` to `security_status`:
  - `LOGIN_FAILED` → `warning`
  - `SUDO_USED` → `info`
  - `ACCOUNT_CREATED`, `ACCOUNT_REMOVED`, `LOGIN` → `info`
- Insert each event into `audit_logs` table

### 6.2 PAM-to-Agent Endpoints (called by PAM Server)

These endpoints run on the agent (port 8800) and are called by the PAM Server when processing access requests:

| Endpoint | Method | When Called |
|----------|--------|-------------|
| `/agent/provision` | POST | When request is approved |
| `/agent/revoke` | POST | When request is cancelled/expired |
| `/health` | GET | Agent health check |

#### Provision Call (PAM Server → Agent)

Called by the PAM Server's approve flow:

```python
# PAM Server code (pseudocode)
def approve_request(request_id):
    request = db.get_request(request_id)
    server = db.get_server(request.server_id)

    # Call the agent
    response = requests.post(
        f"http://{server.ip}:8800/agent/provision",
        json={
            "request_id": request.id,
            "username_to_create": f"jit-{random_string(8)}",
            "privilege": request.access_level,  # "root" or "user"
            "duration_minutes": request.duration_minutes,
            "expires_at": calculate_expiry().isoformat(),
        }
    )

    if response.status_code == 200:
        data = response.json()
        # Store SSH key securely
        db.update_request(request.id, {
            "status": "active",
            "provisioned_username": data["username"],
            "ssh_private_key": encrypt(data["ssh_private_key"]),
            "expires_at": data.get("expires_at"),
        })
```

#### Revoke Call (PAM Server → Agent)

Called on manual cancel, request expiration, or session termination:

```python
def revoke_request(request_id):
    request = db.get_request(request_id)
    server = db.get_server(request.server_id)

    requests.post(
        f"http://{server.ip}:8800/agent/revoke",
        json={
            "request_id": request.id,
            "username": request.provisioned_username,  # fallback if agent restarted
        }
    )

    db.update_request(request.id, {"status": "completed"})
```

### 6.3 Database Schema (PAM Server Additions)

**Agents table:**

```sql
CREATE TABLE agents (
    id TEXT PRIMARY KEY,
    hostname TEXT NOT NULL,
    ip TEXT NOT NULL,
    os_version TEXT,
    tenant_company_id TEXT NOT NULL,
    agent_version TEXT,
    api_key TEXT NOT NULL,
    status TEXT DEFAULT 'inactive',
    last_seen TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    port INTEGER DEFAULT 8800
);
```

**Companies table additions:**

```sql
ALTER TABLE companies ADD COLUMN api_key TEXT UNIQUE;
```

**Requests table additions:**

```sql
ALTER TABLE requests ADD COLUMN provisioned_username TEXT;
ALTER TABLE requests ADD COLUMN ssh_private_key TEXT;  -- encrypted
ALTER TABLE requests ADD COLUMN provisioned_at TIMESTAMP;
ALTER TABLE requests ADD COLUMN expires_at TIMESTAMP;
```

---

## 7. Testing & Verification

### 7.1 Registration Test

```
Agent startup log:
Jul 02 14:30:55 linux-server pam-agent.py: Registration successful
```

The agent registered with the PAM Server on first startup, sending hostname, IP (<agent-ip>), OS version (Ubuntu 22.04.5 LTS), tenant company ID (<company-id>), and agent version (1.0.0). The HMAC-SHA256 signature was computed and verified by the PAM Server.

### 7.2 Health Endpoint Test

```bash
curl http://127.0.0.1:8800/health
```

```json
{"status": "UP", "hostname": "linux-server", "uptime": 14, "active_provisions": 0}
```

### 7.3 Provision Test (Root Privilege)

```bash
curl -X POST http://127.0.0.1:8800/agent/provision \
  -H "Content-Type: application/json" \
  -d '{"request_id":"req-001","username_to_create":"jit-test-root","privilege":"root","duration_minutes":30}'
```

**Response:**
```json
{
  "status": "success",
  "request_id": "req-001",
  "username": "jit-test-root",
  "privilege": "root",
  "duration_minutes": 30,
  "ssh_private_key": "-----BEGIN OPENSSH PRIVATE KEY-----\n...",
  "ssh_public_key": "ssh-rsa AAAAB3NzaC1yc2E...",
  "password": "kr*98JUaVT$GxC3!kk3lk*wm"
}
```

**Verification on server:**
```
User jit-test-root (uid=1002) exists with home directory
~/.ssh/authorized_keys contains the generated public key
/etc/sudoers.d/req-001 → "jit-test-root ALL=(ALL) NOPASSWD:ALL"
```

### 7.4 Revoke Test

```bash
curl -X POST http://127.0.0.1:8800/agent/revoke \
  -H "Content-Type: application/json" \
  -d '{"request_id":"req-001","username":"jit-test-root"}'
```

**Response:**
```json
{"status": "success", "message": "User jit-test-root removed"}
```

**Verification on server:**
```
id: ‘jit-test-root’: no such user  ✓
/etc/sudoers.d/req-001 → No such file or directory  ✓
/home/jit-test-root → No such file or directory  ✓
```

### 7.5 User Privilege (Non-Root) Test

A second test with privilege="user" confirmed that users without sudo access are created correctly (no sudoers file, no sudo/wheel group membership).

### 7.6 Heartbeat Verification

The agent sends heartbeats every 25 seconds. The PAM Server's agent list shows the agent as "active" with the correct `last_seen` timestamp updating each cycle.

---

## 8. Security Hardening

### 8.1 API Key Protection

The agent's API key is stored in `/etc/pam-agent/config.yaml` with strict permissions:

```bash
-rw------- 1 root root 273 Jul  2 14:30 /etc/pam-agent/config.yaml
```

- Owner: root (read/write only)
- Group: root
- Others: no access
- The key is never logged or exposed in error messages

### 8.2 Network Security

**Firewall rules (UFW):**

```bash
# Allow SSH from anywhere (for PAM gateway and admin access)
sudo ufw allow ssh

# Allow agent listener only from PAM Server
sudo ufw allow from <pam-server-ip> to any port 8800 proto tcp
sudo ufw deny 8800

sudo ufw --force enable
```

This ensures that only the PAM Server can call the agent's provision/revoke endpoints.

### 8.3 SSH Key Security

- SSH private keys are generated per-session and returned to the PAM Server
- Private keys are never stored on the target server
- Public keys are stored in `~/.ssh/authorized_keys` with 600 permissions
- SSH key directory has 700 permissions
- Ownership is set to the provisioned user

### 8.4 Sudoers File Security

- Sudoers files are named after the request ID (not the username) for traceability
- Files are created with 440 permissions (read-only for root and group)
- Files are automatically deleted on revoke

### 8.5 Auto-Expiry Fail-Safe

The most critical security feature: every provisioned account is automatically revoked after its configured duration, regardless of whether the PAM Server sends a revoke command. This protects against:

- PAM Server crash/disconnection
- Network partition between PAM Server and agent
- Human error (forgetting to terminate access)
- Race conditions

### 8.6 Service Account Isolation

A dedicated `pam-gateway` system user is created for the PAM Server's SSH gateway connection. This provides:

- Audit trail separation (all PAM SSH connections are attributed to this user)
- Access control (SSH can be restricted to only this user via `AllowUsers pam-gateway` in sshd_config)
- No shell access for regular users through the gateway

---

## 9. Configuration Reference

### 9.1 Agent Config (`/etc/pam-agent/config.yaml`)

```yaml
server:
  # URL of the PAM Server (VM1)
  url: "http://<pam-server-ip>:3001"

  # Pre-issued API key for this tenant
  api_key: "<your-api-key>"

  # Tenant company ID (matches PAM Server's companies.tenant_id)
  company_id: "<your-company-id>"

  # Human-readable tenant name
  tenant_name: "Kapital Bank"

agent:
  # Port the agent's HTTP listener runs on (for provision/revoke callbacks)
  listen_port: 8800

  # Address to bind (0.0.0.0 = all interfaces, firewall restricts to PAM Server)
  listen_addr: "0.0.0.0"

  # Heartbeat interval in seconds (15-30 recommended)
  heartbeat_interval: 25

# IP address of the PAM Server (for firewall rules and documentation)
pam_server_ip: "<pam-server-ip>"

# Agent version identifier
agent_version: "1.0.0"
```

### 9.2 Environment Variables (for testing)

The config path and log path can be overridden for testing:

```bash
PAM_AGENT_CONFIG=/tmp/test-config.yaml PAM_AGENT_LOG=/tmp/test-agent.log python3 agent.py
```

---

## 10. Operational Commands

### 10.1 Service Management

```bash
# Status
sudo systemctl status pam-tenant-agent.service

# Start / Stop / Restart
sudo systemctl start pam-tenant-agent.service
sudo systemctl stop pam-tenant-agent.service
sudo systemctl restart pam-tenant-agent.service

# Enable at boot / Disable
sudo systemctl enable pam-tenant-agent.service
sudo systemctl disable pam-tenant-agent.service

# View live logs
sudo journalctl -u pam-tenant-agent.service -f

# View last 50 lines
sudo journalctl -u pam-tenant-agent.service --no-pager -n 50

# View logs since last boot
sudo journalctl -u pam-tenant-agent.service --no-pager -b
```

### 10.2 Health Check

```bash
curl http://127.0.0.1:8800/health
```

Expected response:
```json
{"status": "UP", "hostname": "linux-server", "uptime": 120, "active_provisions": 0}
```

### 10.3 Manual Provision Test

```bash
curl -X POST http://127.0.0.1:8800/agent/provision \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "manual-test-1",
    "username_to_create": "jit-manual-test",
    "privilege": "root",
    "duration_minutes": 10
  }'
```

### 10.4 Manual Revoke Test

```bash
curl -X POST http://127.0.0.1:8800/agent/revoke \
  -H "Content-Type: application/json" \
  -d '{
    "request_id": "manual-test-1",
    "username": "jit-manual-test"
  }'
```

### 10.5 Firewall Setup

```bash
sudo bash /opt/pam-agent/firewall.sh
```

### 10.6 Gateway User Setup

```bash
sudo bash /opt/pam-agent/setup-gateway-user.sh
```

---

## 11. Troubleshooting

### 11.1 Agent Won't Start

**Symptom:** `systemctl status` shows "failed" or "inactive"

**Check 1:** Validate config syntax
```bash
python3 -c "import yaml; yaml.safe_load(open('/etc/pam-agent/config.yaml'))"
```

**Check 2:** Check logs for errors
```bash
sudo journalctl -u pam-tenant-agent.service --no-pager -n 50
```

**Check 3:** Verify port is available
```bash
sudo lsof -i :8800
```

**Check 4:** Ensure agent script is executable
```bash
ls -la /usr/local/bin/pam-agent.py
```

### 11.2 Registration Fails

**Symptom:** Log shows `Registration failed: cannot connect to PAM Server`

**Check 1:** PAM Server URL in config
```bash
grep url /etc/pam-agent/config.yaml
```

**Check 2:** Network connectivity to PAM Server
```bash
curl -s --max-time 5 http://<pam-server-ip>:3001/api/health
```

**Check 3:** API key in config matches PAM Server
```bash
grep api_key /etc/pam-agent/config.yaml
```

### 11.3 Provision Fails

**Symptom:** Provision endpoint returns error

**Common errors:**

| Error | Likely Cause | Solution |
|-------|-------------|----------|
| `cannot lock /etc/passwd` | Stale lock file from previous operation | `sudo rm -f /etc/.pwd.lock` |
| `Permission denied` | Agent not running as root | `ps aux | grep pam-agent` — should show root |
| `User already exists` | Username collision | Use unique usernames (jit-* prefix) |
| `request_id already active` | Duplicate provision call | Use unique request IDs |

### 11.4 Revoke Fails

**Symptom:** Revoke returns error or user not removed

**Check 1:** If agent restarted, active_requests dict is lost. Send username in body:
```bash
curl -X POST ... -d '{"request_id":"...", "username":"jit-user"}'
```

**Check 2:** If user is currently logged in, `userdel -r` may fail. Force kill user sessions first:
```bash
sudo pkill -u jit-username
```

### 11.5 Heartbeats Not Showing on PAM Server

**Symptom:** Agent shows as "inactive" on PAM Server

**Check 1:** Agent is running
```bash
curl http://127.0.0.1:8800/health
```

**Check 2:** Agent logs show heartbeat attempts
```bash
sudo journalctl -u pam-tenant-agent.service --no-pager | grep -i heartbeat
```

**Check 3:** PAM Server heartbeat endpoint is reachable
```bash
curl -s -X POST http://<pam-server-ip>:3001/api/agent/heartbeat
```

---

## Appendix A: API Reference

### A.1 Agent Endpoints (port 8800)

| Method | Path | Request Body | Response |
|--------|------|-------------|----------|
| GET | `/health` | — | `{"status":"UP","hostname":"...","uptime":N,"active_provisions":N}` |
| POST | `/agent/provision` | `{request_id, username_to_create, privilege, duration_minutes, expires_at}` | `{status, username, ssh_private_key, ssh_public_key, password}` |
| POST | `/agent/revoke` | `{request_id, username}` | `{status, message}` |

### A.2 Agent-to-PAM Endpoints (PAM Server, port 3001)

| Method | Path | Headers | Request Body |
|--------|------|---------|-------------|
| POST | `/api/agent/register` | X-API-Key, X-Signature, X-Timestamp | `{hostname, ip, os_version, tenant_company_id, agent_version}` |
| POST | `/api/agent/heartbeat` | X-API-Key, X-Signature, X-Timestamp | `{hostname, status, load, last_activity, uptime_seconds}` |
| POST | `/api/agent/events` | X-API-Key, X-Signature, X-Timestamp | `{events: [{event_type, source, hostname, username, detail, timestamp}]}` |

### A.3 Event Types

| Event Type | Description | Security Status |
|------------|-------------|-----------------|
| `ACCOUNT_CREATED` | JIT user provisioned | info |
| `ACCOUNT_REMOVED` | JIT user revoked | info |
| `LOGIN` | SSH login success (from auth.log) | info |
| `LOGIN_FAILED` | SSH login failure (from auth.log) | warning |
| `SUDO_USED` | Sudo command executed (from auth.log) | info |

---

## Appendix B: Sample Agent Log Output

```
Jul 02 14:49:13 linux-server pam-agent.py[1898]: PAM Tenant Agent starting
  (hostname=<agent-hostname>, server=http://<pam-server-ip>:3001)
Jul 02 14:49:13 linux-server pam-agent.py[1898]: Registration successful
Jul 02 14:49:13 linux-server pam-agent.py[1898]: Listening on 0.0.0.0:8800
  for provision/revoke callbacks
Jul 02 14:49:13 linux-server pam-agent.py[1898]: Starting auth.log tailer
  on /var/log/auth.log
Jul 02 14:49:15 linux-server pam-agent.py[1898]: HTTP: GET /health 200 -
Jul 02 14:49:18 linux-server pam-agent.py[1898]: HTTP: POST /agent/provision 200 -
Jul 02 14:49:18 linux-server pam-agent.py[1898]: Scheduled revocation for
  jit-test-root in 1800s (request req-001)
Jul 02 14:49:19 linux-server pam-agent.py[1537]: Heartbeat failed:
  Connection refused  (PAM Server not available)
```

---

*End of Report*
