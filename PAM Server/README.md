# PAM Server

Privileged Access Management backend — FastAPI application that brokers SSH access to managed servers through a just-in-time (JIT) access request workflow.

## What It Does

- Multi-tenant RBAC (superuser / admin / user) with JWT authentication
- JIT access request lifecycle: request → approval → agent provisioning → SSH terminal → expiry
- Real-time WebSocket terminal with session recording and replay
- Suspicious activity detection (19 patterns — privilege escalation, RCE, disk tampering)
- HMAC-signed agent communication for tenant VM provisioning
- Full audit logging with CSV export
- Billing account tracking per tenant
- In-app notification system
- Dark/light theme embedded SPA frontend

## Requirements

- Python 3.11+
- pip packages (see `backend-python/requirements.txt` or install individually):
  `fastapi uvicorn[standard] sqlalchemy aiosqlite bcrypt python-jose[cryptography] websockets asyncssh python-multipart aiofiles httpx`
- For PostgreSQL: `asyncpg` + `gcc` and `libpq-dev` system packages
- For Docker: Docker 24+ and Docker Compose

## Setup

### Quick Start (SQLite / Development)

```bash
cd PAM\ Server/backend-python
pip install fastapi uvicorn[standard] sqlalchemy aiosqlite bcrypt python-jose[cryptography] websockets asyncssh python-multipart aiofiles httpx
python3 -m uvicorn main:app --host 0.0.0.0 --port 3001
```

### Docker Compose (PostgreSQL / Production)

```bash
cd PAM\ Server
docker compose up -d
```

### Seed Data

```bash
cd PAM\ Server/backend-python
python3 seed.py
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `DATABASE_URL` | No | `sqlite+aiosqlite:///./pam.db` | Database connection string |
| `JWT_SECRET` | No | `&lt;jwt_secret&gt;` | HMAC key for access token signing |
| `JWT_REFRESH_SECRET` | No | `&lt;jwt_refresh_secret&gt;` | HMAC key for refresh token signing |
| `AGENT_API_KEY` | No | `&lt;agent_api_key&gt;` | Shared secret for agent communication |
| `FRONTEND_URL` | No | `http://localhost:5173` | CORS allowed origin |
| `SSH_KEY_PATH` | No | `~/.ssh/id_rsa` | Default SSH key for terminal sessions |
| `PORT` | No | `3001` | Server listen port |

Copy `.env.example` to `.env` and override values for your environment:

```bash
cp .env.example .env
```

## Run

```bash
cd PAM\ Server/backend-python
python3 serve.py
# or
uvicorn main:app --host 0.0.0.0 --port 3001
```

## Ports

| Port | Service | Description |
|------|---------|-------------|
| 3001 | PAM Server | API + embedded SPA + WebSocket terminal |
| 5432 | PostgreSQL | Database (Docker only) |
| 80 | Nginx | Frontend reverse proxy (Docker frontend only) |

## Dependent Services

- **Tenant Agent** (separate component, see `../Tenant Agent/README.md`): runs on each managed VM, handles JIT Linux user provisioning via HTTP callbacks
- **PostgreSQL** (optional, for production): database backend
- **Nginx** (optional, for production frontend): reverse proxy for API + WebSocket
