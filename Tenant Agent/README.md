# PAM Tenant Agent

A lightweight, self-contained agent for Linux user/privilege management,
built for the PAM (Privileged Access Management) system.

> Part of the [PAMGuard](https://github.com/nihatkazimzada/PAMGuard) monorepo.

## Architecture

```
┌──────────────────────┐       HTTP (port 8800)       ┌──────────────────────┐
│   PAM Server (VM1)   │ ◄─────────────────────────►  │  Tenant Agent (VM2)  │
│   - Provision/Revoke │     /agent/provision          │  - useradd/userdel   │
│   - Receives events  │     /agent/revoke              │  - sudoers.d files   │
│   - Heartbeat checks │                               │  - auth.log tailer   │
└──────────────────────┘                               └──────────────────────┘
                              POST /api/agent/*
                              (register, heartbeat, events)
```

The agent runs as a systemd service (`pam-tenant-agent.service`) and
performs four main functions:

1. **Register** — calls the PAM Server on startup with host identity info
2. **Heartbeat** — reports status every 25s so the PAM Server knows the server is alive
3. **Provision** — creates real Linux users with JIT (just-in-time) access on demand
4. **Revoke** — removes users when their access expires or is manually terminated
5. **Event Forwarding** — tails auth.log and forwards SSH/sudo events to the PAM Server

## Prerequisites

- **Ubuntu 20.04+** (tested on 22.04)
- Python 3.8+ with `python3-requests` and `python3-yaml` (included in install)
- `openssh-client` (for `ssh-keygen` — usually pre-installed)
- `ufw` (for firewall rules — optional but recommended)

## Installation

### 1. Copy files to the target server

```bash
# On the target server (VM2), as root or with sudo:
mkdir -p /opt/pam-agent
# Copy all files from this directory to /opt/pam-agent/
```

### 2. Run the installer

```bash
cd /opt/pam-agent
sudo ./install.sh
```

The installer will:
- Copy `agent.py` to `/usr/local/bin/pam-agent.py`
- Create `/etc/pam-agent/` with example config
- Install and enable the systemd service

### 3. Configure

Copy `.env.example` to `.env` or use the config file approach:

```bash
sudo vi /etc/pam-agent/config.yaml
```

Set:
- `server.url` — the PAM Server's address (e.g., `http://<pam-server-ip>:3001`)
- `server.api_key` — the API key issued by the PAM Server administrator
- `server.company_id` — your tenant company ID (e.g., `<your-company-id>`)
- `pam_server_ip` — the PAM Server IP (for request validation and firewall)

Config permissions are automatically set to `600` (owner read/write only).

### 4. Restart the service

```bash
sudo systemctl restart pam-tenant-agent.service
```

### 5. Verify

```bash
sudo systemctl status pam-tenant-agent.service
sudo journalctl -u pam-tenant-agent.service -f
```

You should see registration messages. The agent will appear in the PAM
Server's agent list within seconds.

### 6. (Optional) Configure firewall

```bash
sudo ./firewall.sh
```

This restricts the agent's HTTP listener (port 8800) to accept connections
only from the PAM Server's IP address. SSH access remains open.

## Obtaining an API Key

1. Ask the PAM Server administrator to issue an API key for your tenant.
2. The administrator creates it via the PAM Server dashboard or API.
3. Copy the key into `/etc/pam-agent/config.yaml` under `server.api_key`.

## How It Works

### Registration (on startup)
```
POST /api/agent/register
Headers: X-API-Key, X-Signature (HMAC-SHA256), X-Timestamp
Body: { hostname, ip, os_version, tenant_company_id, agent_version }
```

### Heartbeat (every 25s)
```
POST /api/agent/heartbeat
Headers: X-API-Key, X-Signature, X-Timestamp
Body: { hostname, status, load, last_activity, uptime_seconds }
```

### Provision (called by PAM Server)
```
POST /agent/provision
Body: { request_id, username_to_create, privilege, duration_minutes, expires_at }

Response:
{
  "status": "success",
  "request_id": "...",
  "username": "...",
  "privilege": "root|user",
  "ssh_private_key": "-----BEGIN OPENSSH PRIVATE KEY-----...",
  "ssh_public_key": "ssh-rsa AAAA...",
  "password": "..."
}
```

What happens on the server:
1. Agent generates an SSH keypair
2. Creates the Linux user with `useradd -m`
3. Installs the public key in `~/.ssh/authorized_keys`
4. If `privilege=root`, creates `/etc/sudoers.d/<request_id>` with NOPASSWD
5. Schedules automatic revocation after `duration_minutes`
6. Returns the SSH private key (and password) to the PAM Server
7. Sends `ACCOUNT_CREATED` audit event

### Revoke (called by PAM Server or auto-expiry)
```
POST /agent/revoke
Body: { request_id, username }

Response:
{ "status": "success", "message": "User <username> removed" }
```

What happens on the server:
1. Cancels any pending auto-expiry timer
2. Removes `/etc/sudoers.d/<request_id>`
3. Deletes the user with `userdel -r`
4. Sends `ACCOUNT_REMOVED` audit event

### Event Forwarding
The agent tails `/var/log/auth.log` and forwards:
- **LOGIN** — SSH public key or password login success
- **LOGIN_FAILED** — SSH authentication failure
- **SUDO_USED** — sudo command execution

Events are batched and sent to `POST /api/agent/events` every heartbeat cycle.

## Security Notes

- The agent's HTTP listener (port 8800) should be firewalled to the PAM
  Server's IP only (run `firewall.sh`).
- The API key is stored in `/etc/pam-agent/config.yaml` with `chmod 600`.
- All outbound requests to the PAM Server are signed with HMAC-SHA256 using
  the API key as the secret.
- For production, create a dedicated `pam-gateway` service account for the
  PAM Server's SSH gateway connection (see the PAM Server documentation).
- The agent runs as root to manage users and sudoers files. The systemd
  service includes security hardening (NoNewPrivileges, PrivateTmp, etc.).

## Troubleshooting

**Agent won't start** — check config syntax:
```bash
python3 -c "import yaml; yaml.safe_load(open('/etc/pam-agent/config.yaml'))"
```

**Registration fails** — verify the PAM Server URL and API key:
```bash
curl -v http://<pam-server>:3001/api/agent/register
```

**Provision fails with permission error** — ensure the agent runs as root:
```bash
ps aux | grep pam-agent
```

## Files

| File | Purpose |
|------|---------|
| `agent.py` | Main agent code |
| `config.yaml.example` | Example configuration |
| `pam-tenant-agent.service` | Systemd service unit |
| `install.sh` | Installation script |
| `firewall.sh` | UFW firewall configuration |
| `README.md` | This file |
| `.env.example` | Environment variable template |
| `.gitignore` | Local gitignore for generated/secret files |
