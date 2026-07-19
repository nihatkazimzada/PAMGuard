# Deployment Guide — PAM Server

> Source files: `docker-compose.yml` (49 lines), `Dockerfile.backend` (11 lines), `Dockerfile.backend-pg` (12 lines), `Dockerfile.frontend` (16 lines), `nginx.conf` (34 lines), `start.sh` (39 lines)

---

## Table of Contents

1. [Docker Compose Setup](#1-docker-compose-setup)
2. [Backend Dockerfile Variants](#2-backend-dockerfile-variants)
3. [Nginx Configuration](#3-nginx-configuration)
4. [VM-to-VM Networking](#4-vm-to-vm-networking)
5. [Start Script](#5-start-script)
6. [Deployment Checklist](#6-deployment-checklist)

---

## 1. Docker Compose Setup

The system can be deployed as a three-service stack defined in `docker-compose.yml`. Each service runs in its own container, with the backend and frontend connecting over an internal Docker bridge network.

### 1.1 Service Overview

```
┌──────────────┐      :5432      ┌──────────────┐      :3001      ┌──────────────┐
│   postgres   │◄───────────────►│   backend    │◄───────────────►│   frontend   │
│  (postgres:  │  DATABASE_URL   │  (backend-   │  proxy_pass     │  (nginx:     │
│   16-alpine) │                 │   pg image)  │                 │   alpine)    │
└──────────────┘                 └──────────────┘                 └──────────────┘
                                        │
                                        │ :3001 (WebSocket /ws)
                                        │
                                 ┌──────┴──────┐
                                 │   External   │
                                 │   Clients    │
                                 └─────────────-┘
```

### 1.2 PostgreSQL Service (lines 4-18)

```yaml
postgres:
  image: postgres:16-alpine
  environment:
    POSTGRES_DB: pamdb
    POSTGRES_USER: pamuser
    POSTGRES_PASSWORD: pampass
  volumes:
    - pgdata:/var/lib/postgresql/data
  healthcheck:
    test: ["CMD-SHELL", "pg_isready -U pamuser -d pamdb"]
    interval: 5s
    retries: 5
```

**What it does:** Runs PostgreSQL 16 on Alpine Linux, the production database backend. On first start it creates the `pamdb` database with user `pamuser`.

**Data persistence:** A named Docker volume `pgdata` is mounted at `/var/lib/postgresql/data`. This survives container restarts and rebuilds.

**Health check:** The container exposes a `pg_isready` health check that the backend waits on before starting. The backend's `depends_on` uses `condition: service_healthy` to ensure the database is accepting connections before the backend attempts to initialize its schema.

**Port mapping:** `5432:5432` — exposed to the host for direct database access if needed (for backups, migrations, etc.). The backend connects internally via the Docker network.

### 1.3 Backend Service (lines 20-37)

```yaml
backend:
  build:
    context: .
    dockerfile: Dockerfile.backend-pg
  environment:
    DATABASE_URL: postgresql+asyncpg://pamuser:pampass@postgres:5432/pamdb
    JWT_SECRET: ${JWT_SECRET:-pam-server-jwt-secret-key-2024}
    JWT_REFRESH_SECRET: ${JWT_REFRESH_SECRET:-pam-server-refresh-secret-key-2024}
    FRONTEND_URL: http://localhost
    AGENT_API_KEY: ${AGENT_API_KEY:-shared-agent-api-key-pam2024}
    SSH_KEY_PATH: /home/administrator/.ssh/id_rsa
  ports:
    - "3001:3001"
  depends_on:
    postgres:
      condition: service_healthy
  volumes:
    - ~/.ssh:/home/administrator/.ssh:ro
```

**What it does:** Runs the FastAPI application (`uvicorn main:app`) on port 3001. It connects to the PostgreSQL service using the `asyncpg` driver via the `DATABASE_URL` environment variable.

**Key configuration via environment:**

| Variable | Default | Purpose |
|----------|---------|---------|
| `DATABASE_URL` | — | PostgreSQL connection string (`postgresql+asyncpg://user:pass@host:5432/db`) |
| `JWT_SECRET` | `pam-server-jwt-secret-key-2024` | HMAC key for access token signing |
| `JWT_REFRESH_SECRET` | `pam-server-refresh-secret-key-2024` | HMAC key for refresh token signing |
| `FRONTEND_URL` | `http://localhost` | CORS allowed origin |
| `AGENT_API_KEY` | `shared-agent-api-key-pam2024` | Fallback key for agent communication |
| `SSH_KEY_PATH` | `~/.ssh/id_rsa` | Path to the SSH private key used for terminal sessions |

**Host volume mount:** The `~/.ssh` directory is mounted read-only into the container so the backend can use the host's SSH key for terminal sessions to target servers.

**Port mapping:** `3001:3001` — the backend API and embedded frontend are exposed on port 3001.

### 1.4 Frontend Service (lines 39-46)

```yaml
frontend:
  build:
    context: .
    dockerfile: Dockerfile.frontend
  ports:
    - "80:80"
  depends_on:
    - backend
```

**What it does:** Serves the React build output via Nginx on port 80. The Nginx configuration acts as a reverse proxy: static files are served directly, while `/api` and `/ws` paths are proxied to the backend.

**Why it depends on backend:** Nginx starts immediately regardless of backend availability — it will return 502 until the backend is ready. The `depends_on` declaration ensures the backend container is created first.

### 1.5 Network Communication

All three services share the default Docker Compose network (a bridge network created automatically). They communicate using service names as hostnames:

- Backend connects to `postgres:5432`
- Nginx proxies to `http://backend:3001`

No `networks` block is declared in the Compose file, so the default bridge network is used. Containers can reach each other by their service name, and the `backend:3001` host:port combination is resolvable from within the frontend container.

---

## 2. Backend Dockerfile Variants

Two Dockerfiles are provided for the backend, differing only in the database driver and system dependencies.

### 2.1 `Dockerfile.backend` — SQLite (Development/Standalone)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy \
    aiosqlite bcrypt python-jose[cryptography] websockets asyncssh \
    python-multipart aiofiles httpx
COPY backend-python/ .
EXPOSE 3001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
```

**When to use:**
- Development and local testing
- Single-VM deployments where PostgreSQL is not available
- Quick demonstrations or prototyping
- Environments with limited memory (SQLite has no separate process)

**How it differs from the PostgreSQL variant:**

| Aspect | SQLite (`Dockerfile.backend`) | PostgreSQL (`Dockerfile.backend-pg`) |
|--------|------------------------------|--------------------------------------|
| Database driver | `aiosqlite` | `asyncpg` |
| System packages | None (pure Python) | `gcc`, `libpq-dev` (for asyncpg C extension) |
| Image size | ~300 MB | ~600 MB |
| `DATABASE_URL` | `sqlite+aiosqlite:///./pam.db` | `postgresql+asyncpg://user:pass@host:5432/pamdb` |
| Multi-process safety | Single-process only | Fully concurrent |
| Data location | Local file in container | External PostgreSQL volume |

**Run command (standalone, no Docker Compose):**
```bash
docker build -t pam-backend-sqlite -f Dockerfile.backend .
docker run -d -p 3001:3001 --name pam-backend pam-backend-sqlite
```

### 2.2 `Dockerfile.backend-pg` — PostgreSQL (Production)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy \
    asyncpg bcrypt python-jose[cryptography] websockets asyncssh \
    python-multipart aiofiles httpx
COPY backend-python/ .
EXPOSE 3001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
```

**When to use:**
- Production deployments
- Multi-process or multi-replica setups
- Environments requiring concurrent connections
- Any deployment where data durability and ACID compliance are priorities

**System dependencies:** `gcc` and `libpq-dev` are required at build time to compile the `asyncpg` C extension. These add approximately 300 MB to the image but are only needed during the pip install step; they could be removed in a multi-stage build for smaller final images.

### 2.3 Common Characteristics

Both Dockerfiles share:
- **Python base image:** `python:3.11-slim` (Debian-based, minimal footprint)
- **Working directory:** `/app`
- **Source copy:** `COPY backend-python/ .` — copies all Python files (main.py, database.py, auth_utils.py, config.py, schemas.py, seed.py, frontend_html.py)
- **Entry point:** Uvicorn with `main:app` on `0.0.0.0:3001`
- **Port:** `3001`

The application code is identical — only the installed packages and system dependencies differ. The SQLite flag in `config.py` (`IS_SQLITE = DATABASE_URL.startswith("sqlite")`) automatically configures the engine for the appropriate backend.

---

## 3. Nginx Configuration

The `nginx.conf` file configures Nginx to serve the React frontend and reverse-proxy API and WebSocket requests to the backend.

```nginx
server {
    listen 80;
    server_name localhost;
    root /usr/share/nginx/html;
    index index.html;

    location / {
        try_files $uri $uri/ /index.html;
    }

    location /api {
        proxy_pass http://backend:3001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }

    location /ws {
        proxy_pass http://backend:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }

    location /socket.io {
        proxy_pass http://backend:3001;
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        proxy_set_header Host $host;
    }
}
```

### 3.1 Static File Serving — `location /`

Serves the React build output from `/usr/share/nginx/html`. The `try_files` directive implements SPA routing: if the request path doesn't match a static file, it falls back to `index.html` so the React router can handle the route client-side.

### 3.2 API Proxy — `location /api`

All requests under `/api` are forwarded to `http://backend:3001`. Standard proxy headers are set to preserve the original client IP and protocol information:

- `Host` — forwarded as-is so the backend sees the original hostname
- `X-Real-IP` — the client's IP address
- `X-Forwarded-For` — chain of proxy IPs
- `X-Forwarded-Proto` — original protocol (`http` or `https`)

### 3.3 WebSocket Proxy — `location /ws` and `location /socket.io`

Both WebSocket paths use the same configuration pattern:

1. **`proxy_http_version 1.1`** — WebSockets require HTTP/1.1 (HTTP/1.0 does not support the Upgrade mechanism)
2. **`proxy_set_header Upgrade $http_upgrade`** — forwards the client's `Upgrade: websocket` request header
3. **`proxy_set_header Connection "upgrade"`** — overrides the default `Connection` header to signal an upgrade request

The `/ws` path is used by the terminal WebSocket (`/ws/terminal`). The `/socket.io` path is reserved for future use with Socket.IO.

### 3.4 How the Frontend Container Serves Both UI and API

The Nginx container listens on port 80 for all three URL spaces:

| Path | Handler | Purpose |
|------|---------|---------|
| `/` (any path not under `/api` or `/ws`) | Static files from React build | Frontend UI |
| `/api/*` | Reverse proxy to backend:3001 | REST API |
| `/ws/*` | Reverse proxy with WebSocket upgrade | Terminal WebSocket |

This means clients only need to connect to a single port (80) to access the complete application.

---

## 4. VM-to-VM Networking

The PAM system spans two virtual machines with distinct roles:

```
┌───────────────────────────────────────┐     ┌───────────────────────────────────────┐
│           VM1: PAM Server             │     │           VM2: Tenant Agent          │
│         (10.0.2.20)                   │     │         (10.0.2.21)                   │
│                                       │     │                                       │
│  ┌─────────────┐   ┌──────────────┐   │     │   ┌──────────────────┐               │
│  │  Backend    │   │  Nginx       │   │     │   │  Agent Process   │               │
│  │  :3001      │◄──│  :80         │   │     │   │  :8800           │               │
│  │  FastAPI    │   │  (optional)  │   │     │   │  FastAPI         │               │
│  └──────┬──────┘   └──────────────┘   │     │   └────────┬─────────┘               │
│         │                             │     │            │                          │
│         │ HTTP POST /api/agent/*      │     │            │                          │
│         └─────────────────────────────┼─────┼────────────┘                          │
│                                       │     │                                       │
│         ┌─────────────────────────┐   │     │   ┌──────────────────┐               │
│         │  SSH Terminal (asyncssh)│   │     │   │  Linux User Mgmt │               │
│         │  → VM2 :22             │   │     │   │  (useradd/del)   │               │
│         └─────────────────────────┘   │     │   └──────────────────┘               │
└───────────────────────────────────────┘     └───────────────────────────────────────┘
```

### 4.1 Network Configuration

Both VMs are on the same local network segment with static IP addresses:

| VM | Hostname | IP Address | Subnet |
|----|----------|------------|--------|
| VM1 (PAM Server) | `pam-server` | `10.0.2.20` | `/24` |
| VM2 (Tenant Agent) | `tenant-agent` | `10.0.2.21` | `/24` |

### 4.2 Communication Flows

**Flow 1: PAM Server → Tenant Agent (HTTP)**

The PAM Server calls the Tenant Agent when an access request is approved or revoked. These are outgoing HTTP requests from the backend to the agent:

| Direction | Source | Target | Port | Protocol | Endpoints |
|-----------|--------|--------|------|----------|-----------|
| Server → Agent | `10.0.2.20` | `10.0.2.21` | `8800` | HTTP | `/agent/provision`, `/agent/revoke` |

The server discovers the agent's IP from the `servers.ip` field in the database and the port from `requests.agent_port` (default `8800`). Each request includes an `X-API-Key` header for authentication.

**Flow 2: Tenant Agent → PAM Server (HTTP)**

The Tenant Agent initiates communication for registration, heartbeats, and event streaming:

| Direction | Source | Target | Port | Protocol | Endpoints |
|-----------|--------|--------|------|----------|-----------|
| Agent → Server | `10.0.2.21` | `10.0.2.20` | `3001` | HTTP | `/api/agent/register`, `/api/agent/heartbeat`, `/api/agent/events` |

Each request includes `X-API-Key` and `X-Signature` headers for HMAC authentication.

**Flow 3: PAM Server → VM2 (SSH)**

When a user opens a terminal session, the backend establishes an SSH connection to VM2:

| Direction | Source | Target | Port | Protocol |
|-----------|--------|--------|------|----------|
| Server → VM2 | `10.0.2.20` | `10.0.2.21` | `22` | SSH (via asyncssh) |

The SSH connection uses the per-request provisioned credentials (JIT username + generated SSH key) to authenticate as the provisioned Linux user.

**Flow 4: Clients → PAM Server**

End users access the web UI by connecting to the PAM Server:

| Direction | Source | Target | Port | Protocol |
|-----------|--------|--------|------|----------|
| Client → Server | Any | `10.0.2.20` | `3001` | HTTP / WebSocket |

The embedded SPA is served at `GET /`, and the WebSocket terminal connects via `ws://10.0.2.20:3001/ws/terminal`.

### 4.3 Network Security Model

- All traffic between VMs is unencrypted HTTP or SSH (no TLS). The HMAC-SHA256 signature on agent-to-server requests provides message integrity and authentication without transport-level encryption.
- The SSH connection uses JIT credentials that expire after the request's `duration_minutes` window.
- No inbound ports need to be open on VM2 beyond `22` (SSH) and `8800` (agent HTTP endpoint).
- VM1 only needs inbound port `3001` (or `80` with the Nginx frontend) for client access, plus outbound access to VM2 on ports `22` and `8800`.

### 4.4 Agent IP Resolution

The PAM Server determines the agent's IP address from the `servers.ip` column. Each server record has an `ip` field that stores the target VM's IP address. The `agent_port` field on the request (default `8800`) determines which port to use for agent communication.

In the approvation flow (`main.py:924-928`):

```python
async with httpx.AsyncClient(timeout=10) as client:
    resp = await client.post(
        f"http://{server.ip}:{agent_port}/agent/provision",
        json=provision_body,
        headers={"X-API-Key": api_key or AGENT_API_KEY}
    )
```

---

## 5. Start Script

The `start.sh` script provides a standalone deployment flow for non-Docker environments. It starts the backend directly with Python and optionally creates a public tunnel.

### 5.1 Script Walkthrough

```bash
#!/bin/bash
# Start PAM Server with public tunnel
export PATH="$HOME/.local/bin:$PATH"

echo "=== Starting PAM Server ==="
```

**Purpose:** The `PATH` export ensures Python user-installed packages (like `uvicorn`) are available even if not installed system-wide.

```bash
# Kill any existing processes
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "localhost.run" 2>/dev/null
sleep 2
```

**Step 1 — Cleanup:** Kills any lingering uvicorn or localhost.run processes from previous runs. The `2>/dev/null` suppresses errors if no matching processes are found. The `sleep 2` gives the OS time to release the port.

```bash
# Start the backend
cd "$(dirname "$0")/backend-python"
python3 -m uvicorn main:app --host 0.0.0.0 --port 3001 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"
```

**Step 2 — Backend Launch:** Changes to the `backend-python` directory and starts Uvicorn in the background on port `3001`, listening on all interfaces. The PID is captured for later `wait`.

```bash
# Wait for backend to be ready
sleep 3

# Test local health
curl -s http://localhost:3001/api/health
echo ""
echo "Backend is healthy"
```

**Step 3 — Health Check:** Waits 3 seconds for the backend to initialize, then verifies it's responding by hitting the `/api/health` endpoint. If the curl fails, the script continues (no error exit), but the message would indicate a problem.

```bash
# Start localhost.run tunnel
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:3001 nokey@localhost.run 2>&1 &
TUNNEL_PID=$!
echo "Tunnel started (PID: $TUNNEL_PID)"
```

**Step 4 — Public Tunnel (optional):** Opens an SSH reverse tunnel to `localhost.run`, a service that provides a public URL (e.g., `https://random-subdomain.lhr.life`) that forwards to the local server on port 3001. The `StrictHostKeyChecking=no` flag accepts the tunnel server's host key automatically. `ServerAliveInterval=30` sends keepalive packets every 30 seconds to prevent the tunnel from dropping.

```bash
echo ""
echo "=== Server is running ==="
echo "Local:  http://localhost:3001"
echo "Public: https://<subdomain>.lhr.life (check tunnel output above)"

# Wait for background processes
wait $BACKEND_PID $TUNNEL_PID
```

**Step 5 — Output:** Prints the local and public URLs. The `wait` command keeps the script running until either process exits, so the script stays attached to the terminal session (or systemd/service manager if run as a service).

### 5.2 Usage

```bash
# Make executable
chmod +x start.sh

# Run (will stay in foreground)
./start.sh

# Run in background
nohup ./start.sh > pam.log 2>&1 &
```

### 5.3 Running Without the Tunnel

To start the server without the public tunnel, remove lines 28-35 or run the backend command directly:

```bash
cd backend-python
python3 -m uvicorn main:app --host 0.0.0.0 --port 3001
```

### 5.4 Running With serve.py

An alternative entry point, `serve.py`, wraps the same uvicorn launch:

```bash
cd backend-python
python3 serve.py
```

This reads the `PORT` environment variable (default `3001`) and starts the server programmatically rather than via the CLI.

---

## 6. Deployment Checklist

### Prerequisites

- [ ] **Two Linux VMs** with network connectivity between them (VM1 for PAM Server, VM2 for Tenant Agent)
- [ ] **Python 3.10+** installed on VM1 (for direct deployment) or **Docker 24+** and **Docker Compose** (for containerized deployment)
- [ ] **SSH access** from VM1 to VM2 (for terminal sessions and agent provisioning)
- [ ] A registered domain or static IP if deploying for production use (the tunnel is for development only)

### Option A: Docker Compose (Recommended for Production)

1. **Clone or copy the project** to VM1:
   ```bash
   mkdir -p /opt/pam-server
   # Copy all files from the project directory to /opt/pam-server
   ```

2. **Set secrets** in environment variables or a `.env` file:
   ```bash
   export JWT_SECRET="<generate-a-random-64-char-string>"
   export JWT_REFRESH_SECRET="<generate-a-different-random-64-char-string>"
   export AGENT_API_KEY="<generate-a-shared-secret-for-agent-communication>"
   ```

3. **Start the stack:**
   ```bash
   cd /opt/pam-server
   docker compose up -d
   ```

4. **Verify all services are running:**
   ```bash
   docker compose ps
   # Expected: postgres (healthy), backend (up), frontend (up)
   ```

5. **Check the health endpoint:**
   ```bash
   curl http://localhost:3001/api/health
   # Expected: {"status": "ok"}
   ```

6. **Access the web UI:**
   - Browse to `http://<vm1-ip>:80` (with frontend container) or `http://<vm1-ip>:3001` (direct to backend)
   - Log in with a seed account or create one via the registration flow

### Option B: Direct Python (Standalone/Development)

1. **Install system dependencies** on VM1:
   ```bash
   sudo apt-get update
   sudo apt-get install -y python3 python3-pip python3-venv
   ```

2. **Set up a virtual environment:**
   ```bash
   cd /path/to/backend-python
   python3 -m venv venv
   source venv/bin/activate
   ```

3. **Install Python packages:**
   ```bash
   pip install fastapi uvicorn[standard] sqlalchemy aiosqlite bcrypt \
       python-jose[cryptography] websockets asyncssh python-multipart aiofiles httpx
   ```

4. **Configure secrets** in environment variables (override defaults in `config.py`):
   ```bash
   export JWT_SECRET="<random-64-char-string>"
   export JWT_REFRESH_SECRET="<random-64-char-string>"
   export AGENT_API_KEY="<shared-secret>"
   ```

5. **Initialize the database and seed data:**
   ```bash
   python3 -c "from database import init_db; import asyncio; asyncio.run(init_db())"
   python3 seed.py
   ```

6. **Start the server:**
   ```bash
   python3 serve.py
   # or: uvicorn main:app --host 0.0.0.0 --port 3001
   ```

### Tenant Agent Setup (VM2)

1. **Deploy the tenant agent** on VM2 (IP: `10.0.2.21`). The agent is a Python FastAPI service that listens on port `8800`.

2. **Configure the agent** with the company's API key (must match the `api_key` set on the company record in the PAM Server database).

3. **Register the target server** in the PAM Server UI:
   - Navigate to Servers → Add Target Server
   - Enter the server name, IP address (`10.0.2.21`), port (`22`), and select the owning company
   - The agent port defaults to `8800`

4. **Verify agent connectivity:**
   - The agent should send a heartbeat to the PAM Server (`POST /api/agent/heartbeat`)
   - Check the Agent Management page in the UI to confirm the agent status is "Active"

### Post-Deployment Verification

- [ ] **Health check:** `GET /api/health` returns `{"status": "ok"}`
- [ ] **Login:** Username/password authentication works and returns JWT tokens
- [ ] **Dashboard stats:** The admin dashboard displays counts of users, servers, requests
- [ ] **Server listing:** Servers appear in the Servers page with correct status
- [ ] **Request flow:** A user can create an access request, an admin can approve it
- [ ] **Terminal session:** After approval, the user can open an SSH terminal via the WebSocket connection
- [ ] **Audit logging:** Login and request events appear in the Audit Logs page
- [ ] **Agent heartbeat:** The agent status shows as "Active" and `last_seen` updates periodically
- [ ] **Notifications:** Unread notification count appears on the bell icon

### Production Considerations

- Replace default JWT secrets and agent API key with cryptographically random values
- Configure a reverse proxy (Nginx/Caddy) with TLS termination for HTTPS access
- Set `DATABASE_URL` to a managed PostgreSQL instance for production data durability
- Adjust the `pool_size` (default: 5) and `max_overflow` (default: 10) in `database.py` based on expected concurrency
- Configure firewall rules to restrict access to port `3001` (or `80`) to authorized IP ranges
- Set up regular backups for the PostgreSQL database (`pg_dump`)
- Consider using a process manager (systemd, supervisord) to keep the backend running
- For multi-replica deployments, ensure the SQLite variant is not used (it does not support concurrent writers)
