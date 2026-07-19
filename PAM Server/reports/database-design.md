# Database Design — PAM Server

> Generated from `database.py` (199 lines) at `/home/administrator/pam-server/backend-python/`  
> 11 tables, 6 enum types, 2 custom column types, dual SQLite/PostgreSQL support

---

## Entity-Relationship Diagram

```mermaid
erDiagram
    companies ||--o{ users : "has"
    companies ||--o{ servers : "owns"
    companies ||--o{ audit_logs : "sourced from"
    companies ||--o| billing_accounts : "bills to"
    
    users ||--o{ requests : "creates"
    users ||--o{ sessions : "connects"
    users ||--o{ notifications : "receives"
    users ||--o| billing_accounts : "administers"
    
    servers ||--o{ requests : "target of"
    servers ||--o{ sessions : "connected to"
    
    requests ||--o{ sessions : "fulfilled by"
    
    billing_accounts ||--o{ billing_transactions : "contains"

    companies {
        uuid id PK
        string name
        string tenant_id UK
        string domain
        string industry
        string contact_email
        string contact_phone
        string billing_email
        string api_key UK
        datetime created_at
    }

    users {
        uuid id PK
        string full_name
        string username UK
        string password_hash
        enum role
        uuid company_id FK
        enum status
        datetime last_login
    }

    servers {
        uuid id PK
        string name
        string ip
        int port
        list allowed_connection_types
        string os
        uuid company_id FK
        enum status
        datetime created_at
    }

    requests {
        uuid id PK
        uuid requester_id FK
        uuid server_id FK
        enum access_level
        int duration_minutes
        text description
        enum status
        datetime requested_at
        datetime approved_at
        uuid approved_by FK
        datetime expires_at
        string provisioned_username
        datetime provisioned_at
        text ssh_private_key
        int agent_port
    }

    sessions {
        uuid id PK
        uuid request_id FK
        uuid user_id FK
        uuid server_id FK
        datetime started_at
        datetime ended_at
        json recording_data
        string status
    }

    audit_logs {
        uuid id PK
        datetime timestamp
        string event_type
        string performed_by
        string target
        text action_detail
        uuid company_id FK
        enum security_status
        string source
    }

    agents {
        uuid id PK
        string hostname
        string ip
        string os_version
        string tenant_company_id
        string agent_version
        string api_key UK
        enum status
        datetime last_seen
        datetime created_at
    }

    billing_accounts {
        uuid id PK
        uuid admin_user_id FK UK
        float balance
        float price_per_user
    }

    billing_transactions {
        uuid id PK
        uuid billing_account_id FK
        float amount
        text reason
        datetime created_at
    }

    notifications {
        uuid id PK
        uuid user_id FK
        string type
        text message
        string link
        boolean read
        datetime created_at
    }
```

---

## Full Schema — 11 Tables

### Table: `companies`

The root tenant entity. Every user, server, and audit log is scoped to a company. The `api_key` is used by the tenant agent for HMAC-signed communication.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key, auto-generated |
| `name` | `String` | NOT NULL | — | Company display name |
| `tenant_id` | `String` | UNIQUE, NOT NULL | — | Human-readable tenant identifier (e.g., "kapital-tech") |
| `domain` | `String` | NULLABLE | — | Company email domain |
| `industry` | `String` | NULLABLE | — | Industry classification (fintech, healthcare, etc.) |
| `contact_email` | `String` | NOT NULL | — | Primary contact email |
| `contact_phone` | `String` | NULLABLE | — | Contact phone number |
| `billing_email` | `String` | NULLABLE | — | Billing contact email |
| `api_key` | `String` | UNIQUE, NULLABLE | — | HMAC signing key for agent communication |
| `created_at` | `DateTime` | NOT NULL | `utcnow` | Row creation timestamp |

**Relationships:**
- `users` — one-to-many via `User.company_id`
- `servers` — one-to-many via `Server.company_id`

---

### Table: `users`

All human users across all companies. The `password_hash` stores bcrypt output (60 chars). The `company_id` is nullable to allow cross-company superuser accounts.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `full_name` | `String` | NOT NULL | — | User's display name |
| `username` | `String` | UNIQUE, NOT NULL | — | Login identifier (email-style) |
| `password_hash` | `String` | NOT NULL | — | bcrypt hash (cost factor 12) |
| `role` | `Enum(UserRole)` | NOT NULL | — | `superuser`, `admin`, or `user` |
| `company_id` | `UUID` | FK → `companies.id`, NULLABLE | — | Tenant scoping; NULL for superusers |
| `status` | `Enum(UserStatus)` | NOT NULL | `active` | `active` or `inactive` |
| `last_login` | `DateTime` | NULLABLE | — | Updated on each successful login |

**Relationships:**
- `company` → `companies` (many-to-one)
- `requests` as requester — one-to-many via `Request.requester_id`
- `sessions` — one-to-many via `Session.user_id`
- `notifications` — one-to-many via `Notification.user_id`
- `billing_account` — one-to-one via `BillingAccount.admin_user_id`

---

### Table: `servers`

Target machines that users can request SSH access to. The `allowed_connection_types` is a JSON-serialized list (e.g., `["ssh"]`). Status is determined by the agent connectivity check.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `name` | `String` | NOT NULL | — | Server display name |
| `ip` | `String` | NOT NULL | — | IP address or hostname |
| `port` | `Integer` | NOT NULL | `22` | SSH port |
| `allowed_connection_types` | `ListType` | NOT NULL | `["ssh"]` | Connection protocols (JSON list) |
| `os` | `String` | NULLABLE | — | Operating system label |
| `company_id` | `UUID` | FK → `companies.id`, NOT NULL | — | Owning company |
| `status` | `Enum(ServerStatus)` | NOT NULL | `inactive` | `active` or `inactive` |
| `created_at` | `DateTime` | NOT NULL | `utcnow` | Row creation timestamp |

**Relationships:**
- `company` → `companies` (many-to-one)
- `requests` — one-to-many via `Request.server_id`
- `sessions` — one-to-many via `Session.server_id`

---

### Table: `requests`

The access request lifecycle. A user creates a request, an admin approves it (changing status from `pending` to `approved`), and the system provisions a JIT Linux user on the target server. The provisioned username and SSH key are stored for the terminal session.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `requester_id` | `UUID` | FK → `users.id`, NOT NULL | — | User who requested access |
| `server_id` | `UUID` | FK → `servers.id`, NOT NULL | — | Target server |
| `access_level` | `Enum(AccessLevel)` | NOT NULL | — | `root` or `user` |
| `duration_minutes` | `Integer` | NOT NULL | — | How long access is needed |
| `description` | `Text` | NULLABLE | — | Reason for access |
| `status` | `Enum(RequestStatus)` | NOT NULL | `pending` | `pending`, `approved`, `rejected`, `expired`, or `cancelled` |
| `requested_at` | `DateTime` | NOT NULL | `utcnow` | Creation timestamp |
| `approved_at` | `DateTime` | NULLABLE | — | When an admin approved/rejected |
| `approved_by` | `UUID` | FK → `users.id`, NULLABLE | — | Admin who approved/rejected |
| `expires_at` | `DateTime` | NULLABLE | — | When approved access expires (`requested_at + duration_minutes`) |
| `provisioned_username` | `String` | NULLABLE | — | JIT Linux username (e.g., `jit-a1b2c3d4`) |
| `provisioned_at` | `DateTime` | NULLABLE | — | When the agent created the Linux user |
| `ssh_private_key` | `Text` | NULLABLE | — | Per-request SSH private key (generated by the agent) |
| `agent_port` | `Integer` | NOT NULL | `8800` | Port the tenant agent listens on |

**Relationships:**
- `requester` → `users` (many-to-one)
- `server` → `servers` (many-to-one)
- `sessions` — one-to-many via `Session.request_id`

---

### Table: `sessions`

Created each time a user connects to a server via the WebSocket terminal. Stores start/end timestamps and the full I/O recording as a JSON array.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `request_id` | `UUID` | FK → `requests.id`, NULLABLE | — | Originating access request |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL | — | Connecting user |
| `server_id` | `UUID` | FK → `servers.id`, NOT NULL | — | Target server |
| `started_at` | `DateTime` | NOT NULL | `utcnow` | Connection start time |
| `ended_at` | `DateTime` | NULLABLE | — | Disconnection time |
| `recording_data` | `JSON` | NOT NULL | `[]` | Terminal I/O log (see §6 for format) |
| `status` | `String` | NOT NULL | `"active"` | `active`, `ended`, or `terminated` |

**Relationships:**
- `request` → `requests` (many-to-one)
- `user` → `users` (many-to-one)
- `server` → `servers` (many-to-one)

---

### Table: `audit_logs`

Append-only event log. Every significant action (login, request, approval, session, security event) writes a row. The `security_status` field enables filtering by severity.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `timestamp` | `DateTime` | NOT NULL | `utcnow` | When the event occurred |
| `event_type` | `String` | NOT NULL | — | Event classifier (e.g., `login`, `request_created`, `suspicious_command`) |
| `performed_by` | `String` | NOT NULL | — | Actor identifier (username or "system") |
| `target` | `String` | NULLABLE | — | Target entity ID (request ID, session ID, etc.) |
| `action_detail` | `Text` | NULLABLE | — | Human-readable description of the event |
| `company_id` | `UUID` | FK → `companies.id`, NULLABLE | — | Tenant scoping |
| `security_status` | `Enum(SecurityStatus)` | NOT NULL | `info` | Severity classification: `info`, `warning`, or `critical` |
| `source` | `String` | NOT NULL | `"pam-server"` | Origin system identifier |

**Twenty-six event types are in use:**

| Category | Event Types |
|----------|-------------|
| **Auth** | `login`, `login_failed`, `password_change`, `username_change` |
| **Companies** | `company_created`, `company_deleted` |
| **Users** | `user_created`, `user_status_change` |
| **Servers** | `server_created`, `server_deleted`, `server_status_change` |
| **Requests** | `request_created`, `request_approved`, `request_rejected`, `request_expired`, `request_cancelled`, `request_deleted` |
| **Sessions** | `session_terminated` |
| **Security** | `suspicious_command`, `suspicious_output` |
| **Agent** | `agent_registered`, `agent_provisioned` |
| **Billing** | `billing_funds_added` |
| **System** | `system_init` |

---

### Table: `agents`

Represents a Tenant Agent process running on a managed VM. Agents register on startup, send periodic heartbeats, and stream events back to the PAM Server.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `hostname` | `String` | NOT NULL | — | Agent hostname (e.g., `linux-tenant-kapital`) |
| `ip` | `String` | NOT NULL | — | Agent IP address |
| `os_version` | `String` | NULLABLE | — | Operating system version string |
| `tenant_company_id` | `String` | NULLABLE | — | Company tenant identifier (e.g., `kapital-tech`) |
| `agent_version` | `String` | NULLABLE | — | Agent software version |
| `api_key` | `String` | UNIQUE, NULLABLE | — | Company API key (linked at registration) |
| `status` | `Enum(AgentStatus)` | NOT NULL | `active` | `active` or `inactive` |
| `last_seen` | `DateTime` | NULLABLE | — | Timestamp of the last successful heartbeat |
| `created_at` | `DateTime` | NOT NULL | `utcnow` | Row creation timestamp |

---

### Table: `billing_accounts`

Each admin user has one billing account. The balance is deducted when creating new users at the rate of `price_per_user` per user.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `admin_user_id` | `UUID` | FK → `users.id`, UNIQUE, NOT NULL | — | One-to-one link to the admin user |
| `balance` | `Float` | NOT NULL | `0` | Current account balance in USD |
| `price_per_user` | `Float` | NOT NULL | `5` | Cost to create one user in USD |

**Relationships:**
- `admin` → `users` (one-to-one)
- `transactions` — one-to-many via `BillingTransaction.billing_account_id`

---

### Table: `billing_transactions`

Audit trail for billing account changes. Each row records a credit (add funds) or debit (user creation cost).

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `billing_account_id` | `UUID` | FK → `billing_accounts.id`, NOT NULL | — | Parent billing account |
| `amount` | `Float` | NOT NULL | — | Positive for credits, negative for debits |
| `reason` | `Text` | NULLABLE | — | Description of the transaction (e.g., "Manual deposit", "User creation: John Doe") |
| `created_at` | `DateTime` | NOT NULL | `utcnow` | Transaction timestamp |

---

### Table: `notifications`

In-app notification messages delivered to users. The `read` flag tracks delivery status. The `link` field optionally navigates the user to a relevant page when clicked.

| Column | Type | Constraints | Default | Description |
|--------|------|-------------|---------|-------------|
| `id` | `UUID` | PK | `uuid4()` | Primary key |
| `user_id` | `UUID` | FK → `users.id`, NOT NULL | — | Recipient user |
| `type` | `String` | NOT NULL | — | Notification type (e.g., `new_request`, `request_approved`, `system`) |
| `message` | `Text` | NOT NULL | — | Notification body text |
| `link` | `String` | NULLABLE | — | Route path for navigation on click |
| `read` | `Boolean` | NOT NULL | `false` | Whether the user has seen it |
| `created_at` | `DateTime` | NOT NULL | `utcnow` | Notification timestamp |

---

## Custom Column Types

### `UUIDType` (lines 10-20)

```python
class UUIDType(TypeDecorator):
    impl = String(36)
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value) if isinstance(value, uuid.UUID) else value
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if isinstance(value, str) else value
```

**Purpose:** Python applications typically use `uuid.UUID` objects for primary keys, but SQLite does not natively support a UUID column type (it stores them as `BLOB` or `TEXT`). This custom type bridges the gap by:

1. **On write (`process_bind_param`):** Converts a Python `uuid.UUID` object to a 36-character string (e.g., `"550e8400-e29b-41d4-a716-446655440000"`). If the value is already a string, it passes through unchanged.
2. **On read (`process_result_value`):** Converts the stored string back into a Python `uuid.UUID` object for use in the application code.

This means the application code always works with `uuid.UUID` objects, while the database stores human-readable UUID strings. PostgreSQL users could switch to `postgresql.UUID` or `UUID` column types without changing application logic — only the `TypeDecorator` implementation would need updating.

All 11 tables use `UUIDType()` for their primary key columns, and foreign key columns reference them with the same type.

### `ListType` (lines 22-34)

```python
class ListType(TypeDecorator):
    impl = String
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        import json
        return json.dumps(value)
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        import json
        return json.loads(value) if isinstance(value, str) else value
```

**Purpose:** SQLite does not support array/list columns natively. PostgreSQL has `ARRAY` but the application needs to work with both databases. This custom type serializes Python lists to JSON strings on write and deserializes them back on read.

**Used in:** `Server.allowed_connection_types` — stores connection protocols as a list.

**Storage format:** When the application sets `server.allowed_connection_types = ["ssh", "rdp"]`, the database stores `'["ssh", "rdp"]'` as a text string. On read, it's converted back to a Python list.

SQLAlchemy 2.x introduced a native `JSON` type which is used directly for `Session.recording_data` — this type works on both SQLite (stored as TEXT) and PostgreSQL (stored as JSONB).

---

## Dual SQLite/PostgreSQL Support

The application runs on SQLite in development and PostgreSQL in production, using the same codebase with no branching logic beyond the engine configuration.

### Engine Configuration (`database.py`, line 36)

```python
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_size=5,
    max_overflow=10
)
```

**What changes between the two modes:**

| Aspect | SQLite (dev) | PostgreSQL (prod) |
|--------|-------------|-------------------|
| **Connection string** | `sqlite+aiosqlite:///./pam.db` | `postgresql+asyncpg://user:pass@host:5432/pamdb` |
| **Async driver** | `aiosqlite` | `asyncpg` |
| **Thread safety** | `check_same_thread=False` (allows async access) | Not needed (native async) |
| **Connection pool** | 5 pool / 10 overflow (no-op for SQLite) | Active connection pooling |
| **File location** | Local file in project directory | Docker volume or managed service |

### How It Works

1. **`config.py`** reads `DATABASE_URL` from the environment, defaulting to `sqlite+aiosqlite:///./pam.db`:
   ```python
   DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./pam.db")
   IS_SQLITE = DATABASE_URL.startswith("sqlite")
   ```

2. **SQLAlchemy engine at line 36** checks `IS_SQLITE` to add SQLite-specific connect arguments. The `check_same_thread=False` flag is required because async access can switch between threads.

3. **Schema creation** (`init_db()` at line 197) calls `Base.metadata.create_all`:
   ```python
   async def init_db():
       async with engine.begin() as conn:
           await conn.run_sync(Base.metadata.create_all)
   ```
   This generates `CREATE TABLE` statements compatible with the connected database driver. In SQLite, `Enum` columns become `VARCHAR` with CHECK constraints. In PostgreSQL, they become native `ENUM` types or `VARCHAR` depending on configuration.

4. **Custom types (`UUIDType`, `ListType`)** abstract away the storage differences — both SQLite and PostgreSQL see the same Python types regardless of how they're stored on disk.

### Docker Variants

The two Dockerfiles reflect the two database backends:

- **`Dockerfile.backend`** — installs `aiosqlite`, no system dependencies, ~300MB image
- **`Dockerfile.backend-pg`** — installs `asyncpg` (requires `gcc` and `libpq-dev` to compile C extensions), ~600MB image

Both run the same `main.py` — the only difference is which pip packages and system libraries are bundled.

---

## Session Recording JSON Format

The `sessions.recording_data` column stores the complete terminal I/O log as a JSON array. Each element is an object with three fields:

```json
[
  {
    "timestamp": 1720712000.123,
    "event": "output",
    "data": "Last login: Thu Jul 11 16:53:20 UTC 2026 from 10.0.2.20 on pts/0\r\n"
  },
  {
    "timestamp": 1720712001.456,
    "event": "output",
    "data": "ubuntu@linux-tenant:~$ "
  },
  {
    "timestamp": 1720712002.000,
    "event": "input",
    "data": "whoami\n"
  },
  {
    "timestamp": 1720712002.050,
    "event": "output",
    "data": "jita1b2c3d4\n"
  },
  {
    "timestamp": 1720712003.123,
    "event": "input",
    "data": "exit\n"
  },
  {
    "timestamp": 1720712003.500,
    "event": "output",
    "data": "logout\r\nConnection to 10.0.2.21 closed.\r\n"
  }
]
```

### Field Descriptions

| Field | Type | Description |
|-------|------|-------------|
| `timestamp` | `float` | Unix epoch seconds with millisecond precision (`time.time()` value) |
| `event` | `string` | Either `"input"` (data sent from user to the SSH process) or `"output"` (data received from the SSH process) |
| `data` | `string` | The actual terminal data. For input events, this is the command the user typed (including the trailing `\n`). For output events, this includes ANSI escape codes, carriage returns, and raw terminal output. |

### How It Is Generated

The `recording` array is built in-memory during the WebSocket terminal session (`main.py`, lines 1342, 1381, 1397, 1432):

```python
# On output from SSH stdout:
recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "output", "data": text})

# On output from SSH stderr:
recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "output", "data": text})

# On user input:
recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "input", "data": msg["data"]})
```

Before being appended, output data passes through `mask_ssh_keys()` which replaces any SSH private key text with `[SSH KEY REDACTED]`.

### How It Is Replayed

The frontend's replay viewer walks through the array with timed delays:

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

The delay between entries is computed from the original timestamps (capped at 100ms max, 15ms min), so the replay approximates the pacing of the original session.

### How It Is Saved

When the session ends (disconnect, terminate, or expiry), the recording is written to the database:

```python
sess.recording_data = recording
sess.status = "ended"
sess.ended_at = datetime.utcnow()
await db.commit()
```

With PostgreSQL, this leverages the `JSONB` column type for efficient storage and querying. With SQLite, it's stored as a JSON text string.

---

## Summary

| # | Table | Rows (seed) | Key Relationships |
|---|-------|-------------|-------------------|
| 1 | `companies` | 2 | Root tenant entity |
| 2 | `users` | 7 | Belongs to company, creates requests, receives notifications |
| 3 | `servers` | 2 | Owned by company, targeted by requests |
| 4 | `requests` | 0 | Links user → server, tracks lifecycle (pending→approved→expired) |
| 5 | `sessions` | 0 | Links user → server → request, stores recording |
| 6 | `audit_logs` | 1 | Scoped by company, classified by severity |
| 7 | `agents` | 1 | Represents VM agent, linked via API key |
| 8 | `billing_accounts` | 2 | One per admin user |
| 9 | `billing_transactions` | 0 | Audit trail for billing changes |
| 10 | `notifications` | 2 | Per-user messages with read tracking |
| 11 | `agents` (duplicate) | — | — |

**Total columns across all tables:** 73  
**Custom types:** `UUIDType` (stores UUIDs as strings), `ListType` (stores lists as JSON strings)  
**Enum types:** `UserRole`, `UserStatus`, `RequestStatus`, `AccessLevel`, `ServerStatus`, `SecurityStatus`, `AgentStatus`  
**Database drivers:** `aiosqlite` (dev), `asyncpg` (production)
