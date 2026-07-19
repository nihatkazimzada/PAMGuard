# Database Schema & ERD Report

> Source: `/home/administrator/pam-server/backend-python/database.py` (199 lines)  
> Config: `/home/administrator/pam-server/backend-python/config.py` (9 lines)

---

## 1. Complete Table Schemas (11 Tables)

### 1.0 Custom Types

Two custom SQLAlchemy `TypeDecorator` classes are used throughout:

**`UUIDType` (lines 10–20)** — stores UUIDs as `String(36)` for SQLite compatibility, converts to/from `uuid.UUID` objects:
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

**`ListType` (lines 22–34)** — stores Python lists as JSON strings (SQLite has no native array type):
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

### 1.1 `companies` — Table: `Company`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `name` | `String` | NO | — | — | — |
| `tenant_id` | `String` | NO | **YES** | — | — |
| `domain` | `String` | YES | — | — | — |
| `industry` | `String` | YES | — | — | — |
| `contact_email` | `String` | NO | — | — | — |
| `contact_phone` | `String` | YES | — | — | — |
| `billing_email` | `String` | YES | — | — | — |
| `api_key` | `String` | YES | **YES** | — | — |
| `created_at` | `DateTime` | YES | — | `datetime.utcnow` | — |

Relationships: `users` (one-to-many), `servers` (one-to-many)

### 1.2 `users` — Table: `User`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `full_name` | `String` | NO | — | — | — |
| `username` | `String` | NO | **YES** | — | — |
| `password_hash` | `String` | NO | — | — | — |
| `role` | `Enum(UserRole)` | NO | — | — | — |
| `company_id` | `UUIDType` (String 36) | YES | — | — | `companies.id` ON DELETE **SET NULL** |
| `status` | `Enum(UserStatus)` | NO | — | `UserStatus.active` | — |
| `last_login` | `DateTime` | YES | — | — | — |

Enum `UserRole`: `superuser`, `admin`, `user`  
Enum `UserStatus`: `active`, `inactive`

### 1.3 `servers` — Table: `Server`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `name` | `String` | NO | — | — | — |
| `ip` | `String` | NO | — | — | — |
| `port` | `Integer` | NO | — | `22` | — |
| `allowed_connection_types` | `ListType` (String JSON) | YES | — | `["ssh"]` | — |
| `os` | `String` | YES | — | — | — |
| `company_id` | `UUIDType` (String 36) | NO | — | — | `companies.id` ON DELETE **CASCADE** |
| `status` | `Enum(ServerStatus)` | NO | — | `ServerStatus.inactive` | — |
| `created_at` | `DateTime` | YES | — | `datetime.utcnow` | — |

Enum `ServerStatus`: `active`, `inactive`

### 1.4 `requests` — Table: `Request`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `requester_id` | `UUIDType` (String 36) | NO | — | — | `users.id` ON DELETE **CASCADE** |
| `server_id` | `UUIDType` (String 36) | NO | — | — | `servers.id` ON DELETE **CASCADE** |
| `access_level` | `Enum(AccessLevel)` | NO | — | — | — |
| `duration_minutes` | `Integer` | NO | — | — | — |
| `description` | `Text` | YES | — | — | — |
| `status` | `Enum(RequestStatus)` | NO | — | `RequestStatus.pending` | — |
| `requested_at` | `DateTime` | YES | — | `datetime.utcnow` | — |
| `approved_at` | `DateTime` | YES | — | — | — |
| `approved_by` | `UUIDType` (String 36) | YES | — | — | `users.id` ON DELETE **SET NULL** |
| `expires_at` | `DateTime` | YES | — | — | — |
| `provisioned_username` | `String` | YES | — | — | — |
| `provisioned_at` | `DateTime` | YES | — | — | — |
| `ssh_private_key` | `Text` | YES | — | — | — |
| `agent_port` | `Integer` | YES | — | `8800` | — |

Enum `AccessLevel`: `root`, `user`  
Enum `RequestStatus`: `pending`, `approved`, `rejected`, `expired`, `cancelled`

### 1.5 `sessions` — Table: `Session`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `request_id` | `UUIDType` (String 36) | YES | — | — | `requests.id` ON DELETE **SET NULL** |
| `user_id` | `UUIDType` (String 36) | NO | — | — | `users.id` ON DELETE **CASCADE** |
| `server_id` | `UUIDType` (String 36) | NO | — | — | `servers.id` ON DELETE **CASCADE** |
| `started_at` | `DateTime` | YES | — | `datetime.utcnow` | — |
| `ended_at` | `DateTime` | YES | — | — | — |
| `recording_data` | `JSON` (native) | YES | — | `[]` (empty list) | — |
| `status` | `String` | NO | — | `"active"` | — |

### 1.6 `audit_logs` — Table: `AuditLog`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `timestamp` | `DateTime` | YES | — | `datetime.utcnow` | — |
| `event_type` | `String` | NO | — | — | — |
| `performed_by` | `String` | NO | — | — | — |
| `target` | `String` | YES | — | — | — |
| `action_detail` | `Text` | YES | — | — | — |
| `company_id` | `UUIDType` (String 36) | YES | — | — | `companies.id` ON DELETE **SET NULL** |
| `security_status` | `Enum(SecurityStatus)` | NO | — | `SecurityStatus.info` | — |
| `source` | `String` | YES | — | `"pam-server"` | — |

Enum `SecurityStatus`: `info`, `warning`, `critical`

### 1.7 `agents` — Table: `Agent`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `hostname` | `String` | NO | — | — | — |
| `ip` | `String` | NO | — | — | — |
| `os_version` | `String` | YES | — | — | — |
| `tenant_company_id` | `String` | YES | — | — | — |
| `agent_version` | `String` | YES | — | — | — |
| `api_key` | `String` | YES | **YES** | — | — |
| `status` | `Enum(AgentStatus)` | NO | — | `AgentStatus.active` | — |
| `last_seen` | `DateTime` | YES | — | — | — |
| `created_at` | `DateTime` | YES | — | `datetime.utcnow` | — |

Enum `AgentStatus`: `active`, `inactive`

### 1.8 `billing_accounts` — Table: `BillingAccount`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `admin_user_id` | `UUIDType` (String 36) | NO | **YES** (unique) | — | `users.id` ON DELETE **CASCADE** |
| `balance` | `Float` | NO | — | `0` | — |
| `price_per_user` | `Float` | NO | — | `5` | — |

### 1.9 `billing_transactions` — Table: `BillingTransaction`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `billing_account_id` | `UUIDType` (String 36) | NO | — | — | `billing_accounts.id` ON DELETE **CASCADE** |
| `amount` | `Float` | NO | — | — | — |
| `reason` | `Text` | YES | — | — | — |
| `created_at` | `DateTime` | YES | — | `datetime.utcnow` | — |

### 1.10 `notifications` — Table: `Notification`

| Column | Type | Nullable | Unique | Default | FK |
|---|---|---|---|---|---|
| `id` | `UUIDType` (String 36) | NO | PK | `uuid.uuid4()` | — |
| `user_id` | `UUIDType` (String 36) | NO | — | — | `users.id` ON DELETE **CASCADE** |
| `type` | `String` | NO | — | — | — |
| `message` | `Text` | NO | — | — | — |
| `link` | `String` | YES | — | — | — |
| `read` | `Boolean` | NO | — | `False` | — |
| `created_at` | `DateTime` | YES | — | `datetime.utcnow` | — |

---

## 2. Entity Relationship Diagram (Mermaid)

```mermaid
erDiagram
    Company {
        string id PK "UUID (String 36)"
        string name "NOT NULL"
        string tenant_id "UNIQUE, NOT NULL"
        string domain "NULLABLE"
        string industry "NULLABLE"
        string contact_email "NOT NULL"
        string contact_phone "NULLABLE"
        string billing_email "NULLABLE"
        string api_key "UNIQUE, NULLABLE"
        datetime created_at "DEFAULT now()"
    }

    User {
        string id PK "UUID (String 36)"
        string full_name "NOT NULL"
        string username "UNIQUE, NOT NULL"
        string password_hash "NOT NULL"
        enum role "UserRole: superuser|admin|user"
        string company_id FK "NULLABLE, SET NULL on delete"
        enum status "UserStatus: active|inactive, DEFAULT active"
        datetime last_login "NULLABLE"
    }

    Server {
        string id PK "UUID (String 36)"
        string name "NOT NULL"
        string ip "NOT NULL"
        int port "DEFAULT 22"
        list allowed_connection_types "JSON, DEFAULT [ssh]"
        string os "NULLABLE"
        string company_id FK "CASCADE on delete"
        enum status "ServerStatus: active|inactive, DEFAULT inactive"
        datetime created_at "DEFAULT now()"
    }

    Request {
        string id PK "UUID (String 36)"
        string requester_id FK "CASCADE on delete"
        string server_id FK "CASCADE on delete"
        enum access_level "AccessLevel: root|user"
        int duration_minutes "NOT NULL"
        text description "NULLABLE"
        enum status "RequestStatus: pending|approved|rejected|expired|cancelled, DEFAULT pending"
        datetime requested_at "DEFAULT now()"
        datetime approved_at "NULLABLE"
        string approved_by FK "SET NULL on delete"
        datetime expires_at "NULLABLE"
        string provisioned_username "NULLABLE"
        datetime provisioned_at "NULLABLE"
        text ssh_private_key "NULLABLE"
        int agent_port "DEFAULT 8800"
    }

    Session {
        string id PK "UUID (String 36)"
        string request_id FK "SET NULL on delete"
        string user_id FK "CASCADE on delete"
        string server_id FK "CASCADE on delete"
        datetime started_at "DEFAULT now()"
        datetime ended_at "NULLABLE"
        json recording_data "DEFAULT []"
        string status "DEFAULT active"
    }

    AuditLog {
        string id PK "UUID (String 36)"
        datetime timestamp "DEFAULT now()"
        string event_type "NOT NULL"
        string performed_by "NOT NULL"
        string target "NULLABLE"
        text action_detail "NULLABLE"
        string company_id FK "SET NULL on delete"
        enum security_status "SecurityStatus: info|warning|critical, DEFAULT info"
        string source "DEFAULT pam-server"
    }

    Agent {
        string id PK "UUID (String 36)"
        string hostname "NOT NULL"
        string ip "NOT NULL"
        string os_version "NULLABLE"
        string tenant_company_id "NULLABLE"
        string agent_version "NULLABLE"
        string api_key "UNIQUE, NULLABLE"
        enum status "AgentStatus: active|inactive, DEFAULT active"
        datetime last_seen "NULLABLE"
        datetime created_at "DEFAULT now()"
    }

    BillingAccount {
        string id PK "UUID (String 36)"
        string admin_user_id FK "UNIQUE, CASCADE on delete"
        float balance "DEFAULT 0"
        float price_per_user "DEFAULT 5"
    }

    BillingTransaction {
        string id PK "UUID (String 36)"
        string billing_account_id FK "CASCADE on delete"
        float amount "NOT NULL"
        text reason "NULLABLE"
        datetime created_at "DEFAULT now()"
    }

    Notification {
        string id PK "UUID (String 36)"
        string user_id FK "CASCADE on delete"
        string type "NOT NULL"
        text message "NOT NULL"
        string link "NULLABLE"
        boolean read "DEFAULT false"
        datetime created_at "DEFAULT now()"
    }

    Company ||--o{ User : "has"
    Company ||--o{ Server : "has"
    Company ||--o{ AuditLog : "scopes"
    User ||--o{ Request : "requests"
    User ||--o{ Session : "connects"
    User ||--o{ Notification : "receives"
    User |o--|| BillingAccount : "admin account"
    Server ||--o{ Request : "target of"
    Server ||--o{ Session : "accessed"
    Request ||--o{ Session : "creates"
    BillingAccount ||--o{ BillingTransaction : "transactions"
```

---

## 3. Index Analysis

### 3.1 Existing Indexes (Implicit via Constraints)

SQLAlchemy automatically creates indexes for:

| Column(s) | Table | Reason | Evidence |
|---|---|---|---|
| `id` (PK) | All 11 tables | Primary key — every table has `id = Column(UUIDType(), primary_key=True, ...)` | Lines 77, 93, 106, 120, 138, 149, 161, 174, 181, 189 |
| `tenant_id` | `companies` | `unique=True` | Line 79 |
| `api_key` | `companies` | `unique=True` | Line 85 |
| `username` | `users` | `unique=True` | Line 95 |
| `admin_user_id` | `billing_accounts` | `unique=True` (also a FK) | Line 175 |
| `api_key` | `agents` | `unique=True` | Line 167 |

### 3.2 Foreign Keys (No Automatic Index in SQLite/MySQL)

SQLAlchemy does **not** automatically create indexes on foreign key columns. The following FK columns lack explicit `index=True`:

| FK Column | Table | Referenced Table | Used In Queries? | Risk |
|---|---|---|---|---|
| `company_id` | `users` | `companies` | **Yes** — every role-based query filters by company | Full scan on user lookup by company |
| `company_id` | `servers` | `companies` | **Yes** — every list_servers call filters by company | Full scan on server listing |
| `company_id` | `audit_logs` | `companies` | **Yes** — every audit_log query filters by company | Full scan on audit log listing |
| `requester_id` | `requests` | `users` | **Yes** — every "my requests" query | Full scan on user's requests |
| `server_id` | `requests` | `servers` | **Yes** — check-active query | Full scan |
| `user_id` | `sessions` | `users` | **Yes** — session scope by user | Full scan |
| `server_id` | `sessions` | `servers` | **Yes** — session scope | Full scan |
| `user_id` | `notifications` | `users` | **Yes** — every notification load | Full scan |

**Evidence — no `index=True` anywhere in database.py:**
```python
# All FK columns use plain Column() without index=True:
company_id = Column(UUIDType(), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)        # line 98
company_id = Column(UUIDType(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)       # line 112
requester_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)          # line 121
server_id = Column(UUIDType(), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)           # line 122
user_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)               # line 140
# ... etc
```

### 3.3 Columns That Should Be Indexed (But Aren't)

| Column | Table | Why |
|---|---|---|
| `event_type` | `audit_logs` | Filtered in **every** audit log query; also used in dashboard stats aggregation |
| `security_status` | `audit_logs` | Dashboard counts critical/warning events (lines 342–350) |
| `status` | `requests` | The `expire_old_requests` task queries `WHERE status = 'approved' AND expires_at <= now` (line 1521) |
| `expires_at` | `requests` | Used in expiry check query above |
| `status` | `sessions` | Dashboard counts active sessions (`WHERE status = 'active'`) |
| `performed_by` | `audit_logs` | User dashboard filters by `performed_by == payload["username"]` (line 422) |
| `hostname` | `agents` | Agent heartbeat lookup (`WHERE hostname = ...`) — lines 545, 513 |

**Evidence from main.py — dashboard query on `security_status` (lines 342–344):**
```python
audit_query = select(func.count(AuditLog.id)).where(AuditLog.security_status == SecurityStatus.critical)
if cid:
    audit_query = audit_query.where(AuditLog.company_id == cid)
```

**Evidence — expiry check (lines 1521–1523):**
```python
result = await db.execute(
    select(Request).where(Request.status == RequestStatus.approved, Request.expires_at <= now)
)
```

### 3.4 Index Cost vs Benefit

With SQLite (dev), the database is local and single-user — missing indexes are unnoticeable. With PostgreSQL (prod) and thousands of rows per table, every unindexed FK query becomes a sequential scan. The most critical missing indexes are:

1. `audit_logs(company_id)` — most-queried table by company scope
2. `requests(requester_id)` — every user dashboard load
3. `sessions(user_id, status)` — active session counting and filtering
4. `requests(status, expires_at)` — background expiry job

---

## 4. SQLite (Dev) → PostgreSQL (Production) Transition

### 4.1 The Connection String

**`config.py` (lines 1–9):**
```python
import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./pam.db")
JWT_SECRET = os.getenv("JWT_SECRET", "&lt;jwt_secret&gt;")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "&lt;jwt_refresh_secret&gt;")
JWT_ALGORITHM = "HS256"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "&lt;agent_api_key&gt;")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
```

The default is `sqlite+aiosqlite:///./pam.db`. To switch to PostgreSQL, set the environment variable:
```bash
export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/pamdb"
```

### 4.2 Engine Configuration

**`database.py` line 36:**
```python
engine = create_async_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if IS_SQLITE else {},
    pool_size=5,
    max_overflow=10
)
```

The `IS_SQLITE` flag controls:
- **SQLite**: passes `connect_args={"check_same_thread": False}` (required for async SQLite access)
- **PostgreSQL**: passes `{}` (no special args needed for asyncpg)

### 4.3 Custom Type Compatibility

The `UUIDType` stores UUIDs as `String(36)` for SQLite. With PostgreSQL, `asyncpg` natively supports `UUID` columns — but the custom type always converts to `String(36)` regardless of dialect. This works but loses the native UUID column type on PostgreSQL. A proper production setup would:

```python
class UUIDType(TypeDecorator):
    impl = String(36) if IS_SQLITE else Uuid  # Would need dialect-aware logic
```

Currently it always uses `String(36)` (line 11):
```python
impl = String(36)
```

The `ListType` stores lists as JSON strings for SQLite. PostgreSQL has native `JSONB` — but the custom type always uses `String` (line 23):
```python
impl = String
```

On PostgreSQL, `Session.recording_data` uses SQLAlchemy's native `JSON` type (line 144), which maps to `JSONB` on PostgreSQL automatically:
```python
recording_data = Column(JSON, default=list)
```

### 4.4 Migration Tooling

**No migration tool is used.** There is no `alembic.ini`, no `versions/` directory, and no migration script anywhere in the project.

**Evidence — no Alembic import or setup in any file:**
```python
# grep -r "alembic" .  → 0 results
```

**Instead, schema is applied via `Base.metadata.create_all` (line 197–199):**
```python
async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
```

This is called once at startup in the FastAPI `lifespan` handler (main.py lines 98–103):
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(expire_old_requests())
    yield
    task.cancel()
```

**Implications of no Alembic:**
- Schema changes require manual DDL scripts for production
- No rollback capability
- No version history of schema changes
- `create_all` is **additive only** — it creates tables that don't exist but does NOT alter existing tables
- Renaming or dropping columns requires manual SQL intervention
- No seed data separation — `seed.py` must be run separately after deployment

### 4.5 Docker/Production Configuration

The production Docker setup (`Dockerfile.backend-pg`, `docker-compose.yml`) expects PostgreSQL:

**`Dockerfile.backend-pg` (from project root):**
```dockerfile
# Sets DATABASE_URL to PostgreSQL connection
ENV DATABASE_URL=postgresql+asyncpg://postgres:postgres@db:5432/pamdb
```

**`docker-compose.yml`** defines a `db` service (PostgreSQL) and sets `DATABASE_URL` accordingly, but the app code itself has **no migration step** — on container startup, `init_db()` creates tables via `create_all` if they don't exist.

---

## 5. JSON Field Structure: `session.recording_data`

### 5.1 Schema

The `recording_data` column is defined as `Column(JSON, default=list)` (line 144). It stores an array of event objects.

### 5.2 Sample Payload

The recording is built in `main.py` during the WebSocket SSH session (lines 1342, 1381, 1397, 1432):

```json
[
    {
        "timestamp": 1719876543.21,
        "event": "input",
        "data": "ls -la\n"
    },
    {
        "timestamp": 1719876543.45,
        "event": "output",
        "data": "total 24\ndrwxr-xr-x 2 jit-fe3af591 jit-fe3af591 4096 Jul  2 12:34 .\ndrwxr-xr-x 3 root root 4096 Jul  2 12:34 ..\n-rw-r--r-- 1 jit-fe3af591 jit-fe3af591  220 Jul  2 12:34 .bash_logout\n"
    },
    {
        "timestamp": 1719876545.10,
        "event": "input",
        "data": "whoami\n"
    },
    {
        "timestamp": 1719876545.30,
        "event": "output",
        "data": "jit-fe3af591\n"
    },
    {
        "timestamp": 1719876548.00,
        "event": "input",
        "data": "sudo apt install nginx\n"
    },
    {
        "timestamp": 1719876548.01,
        "event": "output",
        "data": "[SSH KEY REDACTED]\n"
    }
]
```

### 5.3 Field Meanings

| Field | Type | Description |
|---|---|---|
| `timestamp` | `float` (Unix epoch) | `datetime.utcnow().timestamp()` — when the event occurred |
| `event` | `string` | `"input"` (keystroke from user) or `"output"` (terminal output from SSH) |
| `data` | `string` | The actual terminal text. Output data is **masked** — SSH private keys are replaced with `[SSH KEY REDACTED]` via `mask_ssh_keys()` before storage (main.py lines 1380, 1396) |

### 5.4 How It's Populated

**Input recording (main.py lines 1432):**
```python
recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "input", "data": msg["data"]})
```

**Output recording (main.py lines 1380–1381):**
```python
masked = mask_ssh_keys(text)
recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "output", "data": masked})
```

### 5.5 How It's Consumed

**Playback via API (main.py lines 1063–1078):**
```python
@app.get("/api/sessions/{session_id}/recording")
async def get_session_recording(...):
    ...
    return {"recording": session.recording_data or []}
```

**Playback in frontend** — the `replayRecording()` function iterates the array with timing delays:
```javascript
function replayRecording(rec) {
    const entry = rec[replayIndex];
    if (entry.event === 'output') {
        wrap.textContent += entry.data;
    }
    replayIndex++;
    const delay = Math.min((rec[replayIndex].timestamp - entry.timestamp), 100);
    setTimeout(() => replayRecording(rec), Math.max(delay, 15));
}
```

### 5.6 Security: SSH Key Masking

Before any output data enters the recording, the `mask_ssh_keys()` function (main.py lines 63–69) runs:

```python
SSH_KEY_PATTERN = re.compile(
    r'-----BEGIN\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----',
    re.IGNORECASE
)
def mask_ssh_keys(text: str) -> str:
    return SSH_KEY_PATTERN.sub('[SSH KEY REDACTED]', text)
```

This ensures that if anyone types `cat ~/.ssh/id_rsa` or similar, the private key material is never persisted in the database recording. The scrub runs on every `output` event before appending to the `recording` list (lines 1380, 1396).
