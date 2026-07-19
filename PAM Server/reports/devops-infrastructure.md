# DevOps Infrastructure: PAM Server Deployment & VM Networking

> Generated from codebase snapshot at `/home/administrator/pam-server/`  
> Covers Docker Compose, Dockerfiles, Nginx, VM networking, start script, and deployment issues

---

## 1. Docker Compose Structure

**File:** `/home/administrator/pam-server/docker-compose.yml`

```yaml
version: '3.8'

services:
  postgres:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: pamdb
      POSTGRES_USER: pamuser
      POSTGRES_PASSWORD: pampass
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U pamuser -d pamdb"]
      interval: 5s
      timeout: 5s
      retries: 5

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

  frontend:
    build:
      context: .
      dockerfile: Dockerfile.frontend
    ports:
      - "80:80"
    depends_on:
      - backend

volumes:
  pgdata:
```

### 1.1 Service Breakdown

**`postgres`** (PostgreSQL 16 Alpine)
- Data persisted via named volume `pgdata`
- Exposes port 5432
- Health check runs `pg_isready` every 5 seconds — backend waits for this before starting
- Uses hardcoded credentials (`pamuser`/`pampass`)

**`backend`** (Python FastAPI)
- Builds from `Dockerfile.backend-pg` (includes `asyncpg` + `libpq-dev`)
- 6 environment variables configured:
  - `DATABASE_URL` points to the `postgres` service via Docker DNS (`postgresql+asyncpg://pamuser:pampass@postgres:5432/pamdb`)
  - `JWT_SECRET` / `JWT_REFRESH_SECRET` — use env var or fallback to hardcoded defaults
  - `FRONTEND_URL` — set to `http://localhost` (used by CORS middleware)
  - `AGENT_API_KEY` — shared key for agent-to-server HMAC
  - `SSH_KEY_PATH` — path to the SSH deploy key
- Mounts `~/.ssh` read-only from host into container at `/home/administrator/.ssh:ro`
- Waits for `postgres` health check before starting
- Exposes port 3001

**`frontend`** (Nginx)
- Builds from `Dockerfile.frontend` — multi-stage: Node 20 builds the React app, then Nginx Alpine serves it
- Exposes port 80
- Depends on backend (no health check — backend may not be ready when Nginx starts)
- Ships `nginx.conf` with reverse proxy rules

### 1.2 Networks

No custom networks are defined. Docker Compose creates a default bridge network (`pam-server_default`) that links all three services. The `backend` resolves the `postgres` hostname via Docker DNS. The `frontend` resolves `backend` via Docker DNS in its Nginx config.

### 1.3 Volumes

Single named volume `pgdata` — PostgreSQL data directory. No bind mounts for application code (the images are self-contained).

---

## 2. Dockerfile Comparison

### 2.1 `Dockerfile.backend` (SQLite variant)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy aiosqlite \
    bcrypt python-jose[cryptography] websockets asyncssh python-multipart aiofiles httpx
COPY backend-python/ .
EXPOSE 3001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
```

- **11 lines, minimal**
- Uses `aiosqlite` — no system dependencies needed
- **No `gcc` or `libpq-dev`** — pure Python wheel installations
- Total pip-installed packages: 9 Python packages + `uvicorn[standard]`
- Image size: ~300MB

### 2.2 `Dockerfile.backend-pg` (PostgreSQL variant)

```dockerfile
FROM python:3.11-slim
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev \
    && rm -rf /var/lib/apt/lists/*
RUN pip install --no-cache-dir fastapi uvicorn[standard] sqlalchemy asyncpg \
    bcrypt python-jose[cryptography] websockets asyncssh python-multipart aiofiles httpx
COPY backend-python/ .
EXPOSE 3001
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"]
```

- **12 lines** — one extra `RUN` compared to SQLite variant
- Installs `gcc` and `libpq-dev` via apt — required to compile `asyncpg`'s C extension (PostgreSQL adapter)
- Replaces `aiosqlite` with `asyncpg` in the pip install line
- Image size: ~600MB (due to `gcc` + `libpq-dev`)

### 2.3 Key Differences

| Aspect | Dockerfile.backend | Dockerfile.backend-pg |
|--------|-------------------|----------------------|
| **Database driver** | `aiosqlite` | `asyncpg` |
| **System deps** | None | `gcc`, `libpq-dev` |
| **Build time** | ~30s | ~120s (compiles C extensions) |
| **Image size** | ~300MB | ~600MB |
| **Use case** | Local dev / demo | Production with PostgreSQL |
| **Config** | `DATABASE_URL=sqlite+aiosqlite:///./pam.db` | `DATABASE_URL=postgresql+asyncpg://...` |

The docker-compose.yml references `Dockerfile.backend-pg` because it defines a `postgres` service. The SQLite Dockerfile exists as a lighter option for standalone demo deployments without a separate database container.

### 2.4 `Dockerfile.frontend` (multi-stage build)

```dockerfile
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json ./
RUN npm install
COPY frontend/ .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
```

**Stage 1 — Build (Node 20 Alpine):**
- Installs all npm dependencies from `package.json`
- Copies all frontend source
- Runs `npm run build` which executes `tsc && vite build`
- Output goes to `/app/dist`

**Stage 2 — Serve (Nginx Alpine):**
- Copies built artifacts from stage 1 to `/usr/share/nginx/html`
- Copies custom `nginx.conf` as the default server block
- Exposes port 80
- Nginx runs in foreground

**Known limitation:** The `npm install` step will fail on production machines behind restrictive firewalls or with slow filesystems, as experienced on this VM (npm timed out after 25+ minutes). The embedded SPA (`frontend_html.py`) serves as the live fallback.

---

## 3. Nginx Configuration

**File:** `/home/administrator/pam-server/nginx.conf`

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

### 3.1 Static File Serving (`location /`)

```nginx
try_files $uri $uri/ /index.html;
```

This is the standard single-page application (SPA) fallback pattern. Nginx first tries:
1. Exact file match (`$uri`) — e.g. `/assets/index-abc123.js`
2. Directory index (`$uri/`) — e.g. `/dashboard/` → `/dashboard/index.html`
3. Fallback to `/index.html` — React Router handles the route client-side

### 3.2 API Proxy (`location /api`)

All requests starting with `/api` are forwarded to `http://backend:3001` (the `backend` Docker service). Standard proxy headers are forwarded:
- `Host` — preserves original hostname
- `X-Real-IP` — client IP for backend logging
- `X-Forwarded-For` — chain of proxies
- `X-Forwarded-Proto` — original scheme (http/https)

No websocket-specific headers here — `/api` endpoints use plain HTTP.

### 3.3 WebSocket Proxy (`location /ws` and `location /socket.io`)

These two blocks are identical and handle WebSocket upgrades:

```nginx
proxy_http_version 1.1;
proxy_set_header Upgrade $http_upgrade;
proxy_set_header Connection "upgrade";
```

**Why this matters:**

1. **`proxy_http_version 1.1`** — HTTP/1.0 does not support WebSocket upgrades. Nginx defaults to HTTP/1.0 for proxied requests, so this is mandatory.

2. **`Upgrade` header** — `$http_upgrade` captures the client's `Upgrade` header value (typically `websocket`). Nginx forwards it verbatim, telling the backend that this connection should be upgraded.

3. **`Connection "upgrade"`** — Nginx normally strips `Connection` headers when proxying. Setting it to a static `"upgrade"` tells the backend the connection upgrade is requested.

4. **`Host` header** — included for backend routing accuracy.

**Without these WebSocket headers**, the backend's `WebSocket` endpoint (`/ws/terminal`) would receive a plain HTTP GET request instead of an upgrade request, causing a 400 "WebSocket handshake failed" error.

The duplicate `/socket.io` block exists for Socket.IO compatibility (if the project had used Socket.IO as a WebSocket transport instead of raw WebSockets). Currently, the backend uses raw WebSockets at path `/ws/terminal`, so only the `/ws` block is actively used.

### 3.4 Missing Production Features

The current nginx.conf lacks:
- **HTTPS/SSL** — no `listen 443 ssl;` block, no certbot references
- **Rate limiting** — no `limit_req_zone` for API endpoints
- **Gzip compression** — no `gzip on;` for static assets
- **Security headers** — no `X-Frame-Options`, `X-Content-Type-Options`, `Strict-Transport-Security`
- **Client max body size** — no `client_max_body_size` (defaults to 1MB, which might be low for file uploads)
- **Access/error logging** — uses Nginx defaults

---

## 4. VM-to-VM Networking Setup

### 4.1 VirtualBox Network Topology

```
Host Machine (your laptop / dev machine)
  │
  ├── VirtualBox Host-Only Network (192.168.56.x / 192.168.0.x)
  │
  ├── VM1: PAM Server (pam-server)
  │     ├── Adapter 1: NAT (internet access)
  │     │   └── IP: 10.0.2.15 (DHCP from VirtualBox NAT gateway)
  │     ├── Adapter 2: Host-Only Adapter
  │     │   └── IP: 192.168.0.105 → migrated to 10.0.2.20
  │     ├── OS: Ubuntu 22.04 LTS
  │     ├── Hostname: pamserver
  │     ├── Gateway: 10.0.2.1
  │     └── Services: FastAPI (port 3001), SSH (port 22)
  │
  └── VM2: Tenant Agent (linux-tenant-kapital)
        ├── Adapter 1: NAT (internet access)
        │   └── IP: 10.0.2.x (DHCP from VirtualBox NAT gateway)
        ├── OS: Ubuntu 22.04 LTS
        ├── Hostname: linux-tenant-kapital
        ├── IP: 10.0.2.21 (static)
        ├── Gateway: 10.0.2.1
        └── Services: Agent listener (port 8800), SSH (port 22)
```

### 4.2 Network Adapter Configuration

Both VMs use **NAT** as their primary adapter (Adapter 1). This gives them internet access through the host's connection, with IP addresses in the `10.0.2.0/24` range assigned by VirtualBox's built-in DHCP.

The VirtualBox NAT gateway runs at `10.0.2.1` — all VM traffic to the internet is routed through this address, which performs NAT to the host's physical network.

### 4.3 IP Assignment

| Component | IP Address | Adapter Mode | Purpose |
|-----------|-----------|-------------|---------|
| VM1 (PAM Server) | `10.0.2.20` | NAT | Default gateway `10.0.2.1`, dynamic DHCP |
| VM2 (Tenant Agent) | `10.0.2.21` | NAT | Static IP, agent listener on port 8800 |
| NAT Gateway | `10.0.2.1` | — | VirtualBox built-in, routes host's network |
| DHCP Server | `10.0.2.2` | — | VirtualBox built-in, assigns IPs on `10.0.2.0/24` |

**IP migration history:** Both VMs were originally on a Host-Only network (`192.168.0.x` range). After a host network reconfiguration, the Host-Only adapter was replaced with NAT networking, and the VMs were reassigned to `10.0.2.x`. The tenant agent IP was specifically pinned to `10.0.2.21` to maintain consistent connectivity.

### 4.4 Connectivity Between VMs

The VMs communicate over the `10.0.2.0/24` NAT network. Since VirtualBox's NAT mode routes between all VMs on the same NAT network, VM1 (`10.0.2.20`) can reach VM2 (`10.0.2.21`) directly:

```
VM1 → VM2: TCP port 8800 (agent HTTP listener)
  From: PAM Server backend (main.py)
  Purpose: Provision/revoke Linux users, send events
  URL: http://10.0.2.21:8800/agent/provision
       http://10.0.2.21:8800/agent/revoke

VM1 ← VM2: TCP port 3001 (PAM Server API)
  From: Tenant Agent HTTP client
  Purpose: Agent registration, heartbeat, event reporting
  URL: http://10.0.2.20:3001/api/agent/register
       http://10.0.2.20:3001/api/agent/heartbeat
       http://10.0.2.20:3001/api/agent/events
```

**Agent configuration on VM2** (expected config, found in code comments and seed data):

```yaml
pam_server_url: http://10.0.2.20:3001
api_key: pam_kapital_627649a1049d   # or pam_acme_94e7673c8610
listener_port: 8800
heartbeat_interval: 25  # seconds
```

### 4.5 Firewall / Port Rules

**UFW:** Not active on either VM (`ufw not active`). There are no iptables rules configured. This means:

- Port 3001 (PAM API) is open to all interfaces on VM1
- Port 8800 (Agent listener) is open to all interfaces on VM2
- Port 22 (SSH) is open on both VMs

**This is a known security gap for production.** In a hardened deployment:
- VM1 should only accept agent connections from `10.0.2.21` on port 3001
- VM2 should only accept provisioning requests from `10.0.2.20` on port 8800
- SSH should be restricted to a management subnet

### 4.6 DNS and Hostname Resolution

The `/etc/hosts` file on VM1 is minimal:

```
127.0.0.1 localhost
127.0.1.1 pamserver
```

There is no host entry for VM2 (`10.0.2.21`). The backend uses raw IP strings throughout — server IPs are stored as plain text in the database and passed directly to `httpx.AsyncClient` for agent communication.

---

## 5. Start Script Walkthrough

**File:** `/home/administrator/pam-server/start.sh`

```bash
#!/bin/bash
# Start PAM Server with public tunnel
export PATH="$HOME/.local/bin:$PATH"

echo "=== Starting PAM Server ==="

# Kill any existing processes
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "localhost.run" 2>/dev/null

# Wait for port to be free
sleep 2

# Start the backend
cd "$(dirname "$0")/backend-python"
python3 -m uvicorn main:app --host 0.0.0.0 --port 3001 &
BACKEND_PID=$!
echo "Backend started (PID: $BACKEND_PID)"

# Wait for backend to be ready
sleep 3

# Test local health
curl -s http://localhost:3001/api/health
echo ""
echo "Backend is healthy"

# Start localhost.run tunnel
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:3001 nokey@localhost.run 2>&1 &
TUNNEL_PID=$!
echo "Tunnel started (PID: $TUNNEL_PID)"

echo ""
echo "=== Server is running ==="
echo "Local:  http://localhost:3001"
echo "Public: https://<subdomain>.lhr.life (check tunnel output above)"

# Wait for background processes
wait $BACKEND_PID $TUNNEL_PID
```

### 5.1 Step-by-Step Execution

**Step 1 — PATH augmentation (line 3):**
```bash
export PATH="$HOME/.local/bin:$PATH"
```
Ensures `pip install --user` binaries (like `uvicorn`) are in PATH. This is necessary on systems where `~/.local/bin` is not included in the default PATH.

**Step 2 — Cleanup stale processes (lines 7-9):**
```bash
pkill -f "uvicorn main:app" 2>/dev/null
pkill -f "localhost.run" 2>/dev/null
```
Terminates any previously running instances. The `-f` flag matches against the full command line. `2>/dev/null` suppresses "no process found" errors on first run.

**Step 3 — Port release wait (line 12):**
```bash
sleep 2
```
Gives the OS time to release TCP port 3001 after `pkill`. This avoids `Address already in use` errors.

**Step 4 — Backend startup (lines 15-18):**
```bash
cd "$(dirname "$0")/backend-python"
python3 -m uvicorn main:app --host 0.0.0.0 --port 3001 &
BACKEND_PID=$!
```
- Changes to the script's directory (`$(dirname "$0")` resolves to wherever `start.sh` lives, e.g. `/home/administrator/pam-server/`)
- Navigates into `backend-python/` subdirectory
- Starts uvicorn in the background (`&`) on all interfaces (`0.0.0.0`) on port 3001
- Captures PID for `wait` at the end

**Step 5 — Health check (lines 21-26):**
```bash
sleep 3
curl -s http://localhost:3001/api/health
```
- Waits 3 seconds for uvicorn to initialize (loads async SQLAlchemy, connects to DB, etc.)
- Hits the `/api/health` endpoint
- If the endpoint returns `{"status": "ok"}`, the backend is ready
- **No exit-on-failure** — if the health check fails, the script continues anyway

**Step 6 — Public tunnel (lines 29-32):**
```bash
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 \
    -R 80:localhost:3001 nokey@localhost.run 2>&1 &
TUNNEL_PID=$!
```
- Uses SSH reverse port forwarding (`-R`) to expose local port 3001 as a public URL
- **`localhost.run`** is a free SSH-based tunneling service (alternative to ngrok)
  - `nokey@localhost.run` — public anonymous login
  - `-R 80:localhost:3001` — forwards remote port 80 to local port 3001
  - `StrictHostKeyChecking=no` — accepts unknown host key automatically
  - `ServerAliveInterval=30` — sends keepalive every 30 seconds to prevent the SSH tunnel from being dropped by NAT
- The tunnel output (visible via `2>&1`) prints the public URL, e.g. `https://random-subdomain.lhr.life`

### 5.2 Limitations of the Script

1. **No health check abort** — If the backend fails to start, the script still prints "Backend is healthy" and starts the tunnel
2. **No error handling** — No `set -e`, no `trap` for cleanup, no PID file management
3. **Hardcoded port** — Port 3001 is hardcoded in 4 places; no `$PORT` variable
4. **Static sleep waits** — Uses `sleep 3` instead of polling the health endpoint in a loop
5. **Tunnel dependency** — The script relies on `localhost.run` being operational. If the SSH tunnel fails, the public URL is never printed and the script gives no error
6. **Background process management** — Uses `wait` at the end, which means the script runs forever. No graceful shutdown on SIGTERM
7. **No `.local/bin` fallback** — If uvicorn is installed globally, the PATH augmentation might not be needed, but it also won't cause harm

---

## 6. Deployment Issues Encountered

### 6.1 Issue: npm Install Timeouts on VM

**Symptom:** `npm install` in the frontend directory runs for 25+ minutes and eventually fails with `ERR_CONNECTION_TIMED_OUT`.

**Root Cause:** The VirtualBox NAT network introduces latency and potential packet loss. The frontend's `package.json` depends on ~5000 packages (including xterm.js, xterm-addon-fit, recharts, lucide-react, and their transitive dependencies). Each package requires multiple HTTP requests to the npm registry. On a VM with limited I/O and NAT networking, this is slow enough to trigger npm's timeout.

**Resolution:** The entire React frontend was abandoned for the running deployment. An embedded SPA was created as `frontend_html.py` — a 1342-line string served directly by FastAPI with no build step, no dependencies, and zero cold-start time. The React source remains in `frontend/` for future reference.

**Current workaround:** A pre-populated `node_modules/` directory was copied from a separate build environment (`son_pam_project_file/`), but it only contains a subset of packages (clsx, csstype, xterm, xterm-addon-fit, postcss-value-parser, lucide-react, @babel-plugin-transform-react-jsx-source). The missing critical dependencies (react, react-dom, react-router-dom, recharts, tailwindcss, vite, typescript, etc.) prevent any build from succeeding.

### 6.2 Issue: IP Network Migration

**Symptom:** The PAM Server and Tenant Agent VMs were originally on a Host-Only VirtualBox network (`192.168.0.105` and `192.168.0.106`). After a host machine reconfiguration, the Host-Only adapter was removed and replaced with NAT networking. Both VMs received new IPs in the `10.0.2.0/24` range, breaking all inter-VM communication.

**Resolution:**
1. New IPs discovered: PAM Server = `10.0.2.20`, Tenant Agent = `10.0.2.21`
2. The Tenant Agent IP was pinned to `10.0.2.21` (likely via manual `netplan` config on VM2)
3. All hardcoded IPs in `seed.py` were updated:
   ```python
   # Before (Host-Only):
   ip="192.168.0.106"
   # After (NAT):
   ip="10.0.2.21"
   ```
4. The database was deleted and reseeded fresh with the new IP
5. The SSH deploy key was regenerated and copied to the new IP:
   ```bash
   ssh-copy-id linux@10.0.2.21
   ```

**Remaining issue:** The Tenant Agent process on VM2 was still configured with the old `192.168.0.106` IP. Even after the migration, the agent continued sending heartbeats to the old address, resulting in 404 errors when the agent tried `POST http://10.0.2.20:3001/api/agent/heartbeat`. This is a configuration drift issue — the agent on VM2 needs its YAML config updated to `pam_server_url: http://10.0.2.20:3001`.

### 6.3 Issue: SSH Key Permissions

**Symptom:** SSH connections from the PAM Server to the tenant VMs failed with `Bad Owner or Permissions` errors.

**Root Cause:** SSH private keys must have strict permissions (`600` or `400`). The key was originally generated with default permissions (`644`) or was read from a mounted volume with incorrect ownership.

**Resolution:**
```bash
chmod 600 /home/administrator/.ssh/id_rsa
```

In the backend code (`main.py`), the SSH private key is written to a tempfile with explicit `chmod 600` before each connection:

```python
# Pseudocode from the SSH connection handler:
with tempfile.NamedTemporaryFile(mode='w', delete=False) as f:
    f.write(request.ssh_private_key)
    key_path = f.name
os.chmod(key_path, 0o600)  # ← explicit permission fix
```

### 6.4 Issue: asyncssh API Compatibility

**Symptom:** The WebSocket SSH terminal crashed with `TypeError: cannot unpack non-iterable ... object` on `create_process()`.

**Root Cause:** The backend was written for an older version of `asyncssh` where `create_process()` returned a 2-tuple `(chan, session)`. In `asyncssh` v2.23.1 (installed on this VM), `create_process()` returns a **3-tuple** `(stdin: SSHWriter[str], stdout: SSHReader[str], stderr: SSHReader[str])`.

**Resolution:**
```python
# Before (old API):
chan, session = await ssh.create_process()
chan.write(cmd.encode())

# After (v2.23.1 API):
stdin_w, stdout_r, stderr_r = await ssh.create_process()
stdin_w.write(cmd)  # SSHWriter[str] — no .encode()
await stdin_w.drain()
```

Additionally, `SSHWriter[str]` expects `str` not `bytes`, so all `.encode()` calls on the stdin stream were removed. A `drain()` call was added after each write to ensure the data is flushed to the SSH channel.

### 6.5 Issue: Port Conflict on Startup

**Symptom:** Restarting the server errors with `socket.error: [Errno 98] Address already in use`.

**Root Cause:** The previous uvicorn process was not fully terminated, and the OS holds the TCP port in `TIME_WAIT` state for 60 seconds after process exit. Additionally, `pkill -f "uvicorn main:app"` may not catch all processes if the command line differs (e.g., run with absolute path vs. relative path).

**Resolution in `start.sh`:**
```bash
pkill -f "uvicorn main:app" 2>/dev/null
sleep 2  # Wait for port to be released
```

For the Docker deployment, this is handled by Docker's container lifecycle — each `docker compose down` / `docker compose up` cycle provides a clean port.

### 6.6 Issue: localhost.run Tunnel Flakiness

**Symptom:** The public tunnel URL (`*.lhr.life`) becomes unreachable after 5-10 minutes. The SSH tunnel process exits silently.

**Root Cause:** Free `localhost.run` tunnels are rate-limited and can be terminated by the service if idle or after a certain number of connections. The `ServerAliveInterval=30` helps but doesn't guarantee persistence.

**Resolution (workaround):** The tunnel is restarted by killing and re-running `start.sh`. For production, a proper domain (e.g., `pam.example.com`) with Nginx + Let's Encrypt would replace the SSH tunnel entirely.

### 6.7 Issue: Agent Provisioning Callback Failures

**Symptom:** When a request is approved, the backend calls the Tenant Agent at `http://10.0.2.21:8800/agent/provision` but gets a `Connection refused` error.

**Root Cause:** The Tenant Agent process was not running on VM2 at port 8800. This is a startup-order issue — the tenant agent must be started before its first provisioning callback.

**Resolution:** The backend's provisioning code has a `try/except` that silently swallows connection errors:

```python
try:
    async with httpx.AsyncClient(timeout=5) as client:
        await client.post(...)
except:
    pass  # ← Silent failure
```

This prevents the request approval from failing, but the Linux user is never actually provisioned. The admin sees "Request approved" but the user cannot connect. The only indication of failure is the absent `provisioned_username` field on the request record.

### 6.8 Issue: socker.listen() after fork (uvicorn + asyncssh)

**Symptom:** Under certain uvicorn configurations (multiple workers), asyncssh connections fail with `RuntimeError: socker.listen() must not be called after forking`.

**Root Cause:** uvicorn with `--workers > 1` uses `fork()` to create worker processes. asyncssh's internal event loop operations do not work correctly across forked processes because file descriptors are shared but the event loop state is not properly reinitialized.

**Resolution:** Uvicorn is started with a single worker (the default): `--host 0.0.0.0 --port 3001`. No `--workers` flag is used, so no forking occurs.

---

## 7. Summary

| Component | Tech | Status |
|-----------|------|--------|
| **Docker Compose** | 3 services (postgres, backend, frontend) | Defined but not running — Docker daemon not active on VM |
| **Backend Dockerfile** | Two variants (SQLite + PostgreSQL) | Both present, `-pg` variant in compose |
| **Frontend Dockerfile** | Multi-stage Node→Nginx | Unbuildable — npm install times out |
| **Nginx** | Reverse proxy with WebSocket upgrade headers | Configured, not deployed (no Docker) |
| **VM networking** | NAT mode (`10.0.2.0/24`), no firewall | Functional but unhardened |
| **Start script** | Backend + localhost.run tunnel | Functional workaround |
| **Startup order** | pkill → sleep → uvicorn → sleep → curl → tunnel | No error handling on health check failure |
| **Agent communication** | HMAC-signed HTTP between VMs | Agent on VM2 hitting 404 (stale config) |
| **SSH deploy key** | `id_rsa` at ~/.ssh with chmod 600 | Working for SSH connections |
| **Frontend build** | npm install fails, embedded SPA fallback | Active workaround |
| **Tunnel** | localhost.run SSH reverse tunnel | Functional but flaky for production |

**Key architectural insight:** The deployment is in a transitional state. The Docker compose infrastructure is defined and ready for production but not currently running (Docker daemon is not available on this VM). The live deployment runs uvicorn directly on the host, served through an SSH tunnel. The embedded SPA (`frontend_html.py`) replaced the unbuildable React frontend. The Tenant Agent on VM2 is provisioned as a seed record but its process either died or was never started with the correct `10.0.2.20` server URL.
