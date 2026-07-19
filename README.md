# PAMGuard

Privileged Access Management system — two components working together to provide just-in-time SSH access with session recording, audit logging, and suspicious activity detection.

# Team members
- Elnur Nuriyev Seyfaddin (https://github.com/elnurnueiyev)
- Aysel Mammadova Vugar ()
- Ali Mursalzada Samir (https://github.com/mursalzadaali-coder)
- Nihat Kazimzada Ibrahim (https://github.com/nihatkazimzada)

## Architecture

```
┌─────────────────────────┐         ┌─────────────────────────┐
│     PAM Server          │         │     Tenant Agent        │
│  (this repo: PAM Server/)│◄───────►│  (this repo: Tenant    │
│                         │  HTTP   │   Agent/)               │
│  - FastAPI backend      │  HMAC   │  - FastAPI agent        │
│  - Embedded SPA         │  signed │  - Linux user mgmt      │
│  - PostgreSQL/SQLite    │         │  - Event streaming      │
│  - JWT auth / RBAC      │         │                         │
│  - WebSocket terminal   │         │                         │
│  - Session recording    │         │                         │
└─────────────────────────┘         └─────────────────────────┘
         │                                        │
         │ SSH :22                                │ useradd/del
         ▼                                        ▼
  ┌─────────────────┐                   ┌─────────────────┐
  │  Managed VM     │                   │  Managed VM     │
  │  (target server)│                   │  (agent host)   │
  └─────────────────┘                   └─────────────────┘
```

## Repository Structure

```
PAMGuard/
├── README.md                 ← This file
├── .gitignore                ← Root-level gitignore
├── PAM Server/               ← PAM Server (FastAPI backend + embedded frontend)
│   ├── README.md
│   ├── .env.example
│   ├── .gitignore
│   ├── backend-python/       ← Python source
│   ├── frontend/             ← React frontend (alternative)
│   ├── reports/               ← Technical documentation
│   ├── docker-compose.yml
│   ├── Dockerfile.*
│   ├── nginx.conf
│   ├── start.sh
│   └── tunnel.py
└── Tenant Agent/             ← Tenant Agent (managed VM agent)
    ├── README.md
    └── agent.py                   ← Main tenant agent
    ├── install.sh                 ← Installation script
    ├── firewall.sh                ← Firewall configuration
    ├── setup-gateway-user.sh      ← Creates gateway SSH user
    ├── config.yaml.example        ← Example configuration
    ├── .env.example               ← Environment variables example
    ├── pam-tenant-agent.service   ← Systemd service
    ├── pam-agent-logrotate        ← Logrotate configuration
    ├── PAM_TENANT_AGENT_REPORT.md ← Technical documentation
    └── .gitignore
```

## Setup Order

1. **PAM Server** first — start the backend so it's ready to receive agent connections
2. **Tenant Agent** second — configure it with the agent API key and point it at the PAM Server

## Configuration

Both components require environment variables. Copy the `.env.example` files:

```bash
# PAM Server
cp PAM\ Server/.env.example PAM\ Server/.env
# Edit PAM Server/.env with your values

# Tenant Agent
cp Tenant\ Agent/.env.example Tenant\ Agent/.env
# Edit Tenant Agent/.env with your values
```

## Requirements

| Component | Runtime | Optional |
|-----------|---------|----------|
| PAM Server | Python 3.11+, SQLite (built-in) | PostgreSQL 16, Docker 24+ |
| Tenant Agent | Python 3.10+ | — |
| Development | Node.js 20+ (for React frontend build) | — |

## Documentation

- [PAM Server README](PAM%20Server/README.md) — full setup, env vars, API docs
- [Tenant Agent README](Tenant%20Agent/README.md) — agent setup and configuration
