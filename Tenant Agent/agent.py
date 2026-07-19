#!/usr/bin/env python3
"""
PAM Tenant Agent – <your-tenant> (<your-company-id>)
Manages Linux users and forwards security events to PAM Server.
"""

import os
import sys
import time
import json
import hmac
import hashlib
import subprocess
import threading
import logging
import signal
import socket
import re
import secrets
import string
from datetime import datetime, timezone
from pathlib import Path
from http.server import HTTPServer, BaseHTTPRequestHandler
from urllib.parse import urlparse

import yaml
import requests

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
AGENT_VERSION = "1.0.0"
CONFIG_PATH = os.environ.get("PAM_AGENT_CONFIG", "/etc/pam-agent/config.yaml")
LOG_PATH = os.environ.get("PAM_AGENT_LOG", "/var/log/pam-agent.log")
AUTH_LOG_PATH = "/var/log/auth.log"
LISTEN_DEFAULT_PORT = 8800
HEARTBEAT_DEFAULT = 25

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_PATH),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("pam-agent")

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------
config = {}
pam_server_url = ""
api_key = ""
company_id = ""
agent_uptime_start = time.time()
active_requests = {}  # request_id -> {"username": str, "timer": threading.Timer, "created_at": float}
event_queue = []
event_queue_lock = threading.Lock()

# ---------------------------------------------------------------------------
# Crypto helpers
# ---------------------------------------------------------------------------

def hmac_sign(body: str, key: str) -> str:
    return hmac.new(
        key.encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def secure_password(length=24) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


def generate_ssh_keypair() -> tuple:
    """Generate an RSA SSH key pair. Returns (private_key, public_key)."""
    import tempfile
    with tempfile.TemporaryDirectory() as tmpdir:
        key_path = os.path.join(tmpdir, "id_rsa")
        result = subprocess.run(
            ["ssh-keygen", "-t", "rsa", "-b", "2048", "-f", key_path, "-N", "", "-q"],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            raise RuntimeError(f"ssh-keygen failed: {result.stderr}")
        with open(key_path) as f:
            priv = f.read()
        with open(key_path + ".pub") as f:
            pub = f.read()
    return priv, pub

# ---------------------------------------------------------------------------
# OS helpers
# ---------------------------------------------------------------------------

def get_hostname() -> str:
    return socket.gethostname()


def get_ip_address() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.settimeout(1)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "0.0.0.0"


def get_os_version() -> str:
    try:
        with open("/etc/os-release") as f:
            for line in f:
                if line.startswith("PRETTY_NAME="):
                    return line.split("=", 1)[1].strip().strip('"')
    except Exception:
        pass
    return "Unknown"


def get_load_avg() -> float:
    try:
        with open("/proc/loadavg") as f:
            return float(f.read().split()[0])
    except Exception:
        return 0.0


def get_last_activity() -> str:
    now = datetime.now(timezone.utc).isoformat()
    return now


def user_exists(username: str) -> bool:
    result = subprocess.run(["id", username], capture_output=True, text=True)
    return result.returncode == 0


def create_linux_user(username: str) -> str:
    """Create a Linux user with home directory. Returns generated password."""
    password = secure_password()
    result = subprocess.run(
        ["useradd", "-m", "-s", "/bin/bash", username],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"useradd failed: {result.stderr}")
    result = subprocess.run(
        ["chpasswd"],
        input=f"{username}:{password}",
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(f"chpasswd failed: {result.stderr}")
    return password


def setup_sudoers(request_id: str, username: str) -> str:
    """Create /etc/sudoers.d/<request_id> for passwordless sudo."""
    sudoers_path = f"/etc/sudoers.d/{request_id}"
    content = f"{username} ALL=(ALL) NOPASSWD:ALL\n"
    try:
        with open(sudoers_path, "w") as f:
            f.write(content)
        os.chmod(sudoers_path, 0o440)
    except PermissionError:
        raise RuntimeError("Permission denied writing sudoers file (need root)")
    return sudoers_path


def remove_sudoers(request_id: str):
    sudoers_path = f"/etc/sudoers.d/{request_id}"
    if os.path.exists(sudoers_path):
        os.remove(sudoers_path)


def setup_ssh_key(username: str, public_key: str):
    """Install public SSH key into user's authorized_keys."""
    home = f"/home/{username}"
    ssh_dir = os.path.join(home, ".ssh")
    os.makedirs(ssh_dir, exist_ok=True)
    auth_keys = os.path.join(ssh_dir, "authorized_keys")
    with open(auth_keys, "w") as f:
        f.write(public_key.strip() + "\n")
    os.chmod(ssh_dir, 0o700)
    os.chmod(auth_keys, 0o600)
    subprocess.run(["chown", "-R", f"{username}:{username}", ssh_dir])


def delete_linux_user(username: str):
    result = subprocess.run(["userdel", "-r", username], capture_output=True, text=True)
    if result.returncode != 0 and result.returncode != 6:
        # rc=6 means "user does not exist" — consider that a success
        raise RuntimeError(f"userdel failed: {result.stderr}")


def schedule_revocation(request_id: str, username: str, delay_seconds: int):
    """Schedule automatic revocation using a threading.Timer."""
    def revoke_task():
        log.info(f"Auto-expiry: revoking {username} (request {request_id})")
        try:
            revoke_request(request_id)
        except Exception as e:
            log.error(f"Auto-revoke failed for {request_id}: {e}")

    timer = threading.Timer(delay_seconds, revoke_task)
    timer.daemon = True
    timer.start()
    active_requests[request_id] = {
        "username": username,
        "timer": timer,
        "created_at": time.time(),
    }
    log.info(f"Scheduled revocation for {username} in {delay_seconds}s (request {request_id})")

# ---------------------------------------------------------------------------
# Event queue / forwarding
# ---------------------------------------------------------------------------

def queue_event(event_type: str, detail: str, username: str = ""):
    event = {
        "event_type": event_type,
        "source": "linux-agent",
        "hostname": get_hostname(),
        "username": username,
        "detail": detail,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    with event_queue_lock:
        event_queue.append(event)


def flush_events():
    with event_queue_lock:
        events = list(event_queue)
        event_queue.clear()
    if not events:
        return
    url = f"{pam_server_url}/api/agent/events"
    body = json.dumps({"events": events})
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Signature": hmac_sign(body, api_key),
        "X-Timestamp": str(int(time.time())),
    }
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
        if resp.status_code not in (200, 201):
            log.warning(f"Event forward returned {resp.status_code}: {resp.text[:200]}")
    except Exception as e:
        log.warning(f"Event forward failed: {e}")
        with event_queue_lock:
            event_queue[:0] = events  # re-queue on failure


# ---------------------------------------------------------------------------
# PAM Server API calls
# ---------------------------------------------------------------------------

def send_register() -> bool:
    url = f"{pam_server_url}/api/agent/register"
    payload = {
        "hostname": get_hostname(),
        "ip": get_ip_address(),
        "os_version": get_os_version(),
        "tenant_company_id": company_id,
        "agent_version": AGENT_VERSION,
    }
    body = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Signature": hmac_sign(body, api_key),
        "X-Timestamp": str(int(time.time())),
    }
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=15)
        if resp.status_code in (200, 201):
            log.info("Registration successful")
            return True
        else:
            log.warning(f"Registration failed: {resp.status_code} {resp.text[:200]}")
            return False
    except requests.exceptions.ConnectionError:
        log.warning("Registration failed: cannot connect to PAM Server")
        return False
    except Exception as e:
        log.warning(f"Registration failed: {e}")
        return False


def send_heartbeat() -> bool:
    url = f"{pam_server_url}/api/agent/heartbeat"
    payload = {
        "hostname": get_hostname(),
        "status": "UP",
        "load": get_load_avg(),
        "last_activity": get_last_activity(),
        "uptime_seconds": int(time.time() - agent_uptime_start),
    }
    body = json.dumps(payload)
    headers = {
        "Content-Type": "application/json",
        "X-API-Key": api_key,
        "X-Signature": hmac_sign(body, api_key),
        "X-Timestamp": str(int(time.time())),
    }
    try:
        resp = requests.post(url, data=body, headers=headers, timeout=10)
        if resp.status_code not in (200, 201):
            log.warning(f"Heartbeat returned {resp.status_code}")
            return False
        return True
    except Exception as e:
        log.warning(f"Heartbeat failed: {e}")
        return False


# ---------------------------------------------------------------------------
# Provision / Revoke logic
# ---------------------------------------------------------------------------

def provision_request(data: dict) -> dict:
    request_id = data.get("request_id", "")
    username = data.get("username_to_create", "")
    privilege = data.get("privilege", "user")
    duration_minutes = int(data.get("duration_minutes", 60))
    expires_at = data.get("expires_at", "")

    if not request_id or not username:
        return {"status": "error", "message": "request_id and username_to_create are required"}

    if request_id in active_requests:
        return {"status": "error", "message": f"request_id {request_id} already active"}

    if user_exists(username):
        return {"status": "error", "message": f"User {username} already exists"}

    # Generate SSH key pair
    try:
        private_key, public_key = generate_ssh_keypair()
    except Exception as e:
        return {"status": "error", "message": f"Key generation failed: {e}"}

    # Create user
    try:
        password = create_linux_user(username)
    except Exception as e:
        return {"status": "error", "message": f"useradd failed: {e}"}

    # Set up SSH key
    try:
        setup_ssh_key(username, public_key)
    except Exception as e:
        delete_linux_user(username)
        return {"status": "error", "message": f"SSH setup failed: {e}"}

    # Set up sudo if privileged
    if privilege == "root":
        try:
            setup_sudoers(request_id, username)
        except Exception as e:
            delete_linux_user(username)
            return {"status": "error", "message": f"Sudoers setup failed: {e}"}

    # Schedule automatic revocation
    delay_seconds = int(duration_minutes * 60)
    schedule_revocation(request_id, username, delay_seconds)

    # Queue audit event
    queue_event(
        "ACCOUNT_CREATED",
        f"User {username} created with privilege={privilege}, duration={duration_minutes}m",
        username,
    )

    # Return credentials (private key for PAM Server to use)
    return {
        "status": "success",
        "request_id": request_id,
        "username": username,
        "privilege": privilege,
        "duration_minutes": duration_minutes,
        "expires_at": expires_at,
        "ssh_private_key": private_key,
        "ssh_public_key": public_key.strip(),
        "password": password,
    }


def revoke_request(request_id: str) -> dict:
    entry = active_requests.pop(request_id, None)
    username = entry["username"] if entry else None

    # If we don't have it in state, try to find it from config or args
    # For direct revoke calls where we lost state, we need the username
    # Let's handle this via the JSON body instead

    if not username:
        return {"status": "error", "message": f"Unknown request_id: {request_id}"}

    # Cancel pending timer if any
    if entry and entry.get("timer"):
        entry["timer"].cancel()

    # Remove sudoers file
    try:
        remove_sudoers(request_id)
    except Exception as e:
        log.warning(f"Could not remove sudoers for {request_id}: {e}")

    # Delete user
    try:
        delete_linux_user(username)
    except Exception as e:
        return {"status": "error", "message": f"userdel failed: {e}"}

    queue_event(
        "ACCOUNT_REMOVED",
        f"User {username} removed (request {request_id})",
        username,
    )
    return {"status": "success", "message": f"User {username} removed"}


# ---------------------------------------------------------------------------
# Auth log tailer
# ---------------------------------------------------------------------------

class AuthLogTailer(threading.Thread):
    def __init__(self, path=AUTH_LOG_PATH):
        super().__init__(daemon=True)
        self.path = path
        self._stop_event = threading.Event()
        self._last_position = 0

    def run(self):
        if not os.path.exists(self.path):
            log.info(f"auth.log not found at {self.path}, tailer disabled")
            return
        log.info(f"Starting auth.log tailer on {self.path}")
        while not self._stop_event.is_set():
            try:
                with open(self.path) as f:
                    if self._last_position > 0:
                        f.seek(self._last_position)
                    for line in f:
                        line = line.strip()
                        self._process_line(line)
                    self._last_position = f.tell()
            except Exception as e:
                log.debug(f"auth.log read error: {e}")
            self._stop_event.wait(5)

    def _process_line(self, line: str):
        # SSH login success
        if "Accepted publickey" in line or "Accepted password" in line:
            m = re.search(r"for\s+(\S+)", line)
            username = m.group(1) if m else "unknown"
            queue_event("LOGIN", f"SSH login: {line}", username)

        # SSH login failure
        elif "Failed password" in line:
            m = re.search(r"for\s+(\S+)", line)
            username = m.group(1) if m else "unknown"
            queue_event("LOGIN_FAILED", f"SSH failure: {line}", username)

        # Sudo usage
        elif "sudo:" in line and "COMMAND=" in line:
            m = re.search(r"(\w+)\s*:\s*sudo:", line)
            username = m.group(1) if m else "unknown"
            queue_event("SUDO_USED", f"Sudo command: {line}", username)

    def stop(self):
        self._stop_event.set()


# ---------------------------------------------------------------------------
# HTTP Request Handler (for provision/revoke callbacks from PAM Server)
# ---------------------------------------------------------------------------

class AgentHTTPHandler(BaseHTTPRequestHandler):
    def log_message(self, format, *args):
        log.info(f"HTTP: {args[0]} {args[1]} {args[2]}")

    def _send_json(self, status_code: int, data: dict):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == "/health":
            self._send_json(200, {
                "status": "UP",
                "hostname": get_hostname(),
                "uptime": int(time.time() - agent_uptime_start),
                "active_provisions": len(active_requests),
            })
        else:
            self._send_json(404, {"error": "Not found"})

    def do_POST(self):
        parsed = urlparse(self.path)
        content_length = int(self.headers.get("Content-Length", 0))
        body_str = self.rfile.read(content_length).decode("utf-8") if content_length else "{}"

        # Parse JSON
        try:
            data = json.loads(body_str)
        except json.JSONDecodeError:
            self._send_json(400, {"status": "error", "message": "Invalid JSON"})
            return

        # Route
        if parsed.path == "/agent/provision":
            result = provision_request(data)
            status = 200 if result.get("status") == "success" else 400
            self._send_json(status, result)

        elif parsed.path == "/agent/revoke":
            request_id = data.get("request_id", "")
            # We need to accept username from the body too for cases where
            # the agent has restarted and lost state
            username = data.get("username", "")

            entry = active_requests.pop(request_id, None)
            if entry:
                username = entry["username"]
                if entry.get("timer"):
                    entry["timer"].cancel()

            if username:
                try:
                    remove_sudoers(request_id)
                    delete_linux_user(username)
                    queue_event("ACCOUNT_REMOVED", f"User {username} removed (request {request_id})", username)
                    self._send_json(200, {"status": "success", "message": f"User {username} removed"})
                except Exception as e:
                    self._send_json(500, {"status": "error", "message": str(e)})
            else:
                self._send_json(400, {"status": "error", "message": "Request ID not found and username not provided"})

        else:
            self._send_json(404, {"error": "Not found"})

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, X-API-Key, X-Signature, X-Timestamp")
        self.end_headers()


# ---------------------------------------------------------------------------
# Heartbeat loop
# ---------------------------------------------------------------------------

def heartbeat_loop(interval: int):
    while True:
        send_heartbeat()
        flush_events()
        time.sleep(interval)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def main():
    global config, pam_server_url, api_key, company_id

    # Load config
    if not os.path.exists(CONFIG_PATH):
        log.error(f"Config not found at {CONFIG_PATH}")
        sys.exit(1)

    config = load_config(CONFIG_PATH)
    pam_server_url = config["server"]["url"].rstrip("/")
    api_key = config["server"]["api_key"]
    company_id = config["server"]["company_id"]
    listen_port = config.get("agent", {}).get("listen_port", LISTEN_DEFAULT_PORT)
    listen_addr = config.get("agent", {}).get("listen_addr", "0.0.0.0")
    heartbeat_interval = config.get("agent", {}).get("heartbeat_interval", HEARTBEAT_DEFAULT)

    log.info(f"PAM Tenant Agent starting (hostname={get_hostname()}, server={pam_server_url})")

    # Register with PAM Server
    registered = send_register()
    if not registered:
        log.warning("Initial registration failed, will retry in heartbeat loop")

    # Start heartbeat + event flush thread
    hb_thread = threading.Thread(target=heartbeat_loop, args=(heartbeat_interval,), daemon=True)
    hb_thread.start()

    # Start auth log tailer
    tailer = AuthLogTailer()
    tailer.start()

    # Start HTTP server for provision/revoke callbacks
    server = HTTPServer((listen_addr, listen_port), AgentHTTPHandler)
    log.info(f"Listening on {listen_addr}:{listen_port} for provision/revoke callbacks")

    # Handle shutdown gracefully
    def shutdown(signum, frame):
        log.info("Shutting down...")
        server.shutdown()
        sys.exit(0)

    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
