#!/usr/bin/env bash
set -euo pipefail

echo "=== PAM Tenant Agent Installer ==="

# Must be root
if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

AGENT_DIR="$(cd "$(dirname "$0")" && pwd)"
echo "Agent files at: $AGENT_DIR"

# 1. Install the agent script
echo "[1/5] Installing agent script to /usr/local/bin/pam-agent.py..."
cp "$AGENT_DIR/agent.py" /usr/local/bin/pam-agent.py
chmod 755 /usr/local/bin/pam-agent.py

# 2. Install config if not present
CONFIG_PATH="/etc/pam-agent/config.yaml"
if [[ ! -f "$CONFIG_PATH" ]]; then
    echo "[2/5] Creating config directory and installing default config..."
    mkdir -p /etc/pam-agent
    cp "$AGENT_DIR/config.yaml.example" "$CONFIG_PATH"
    chmod 600 "$CONFIG_PATH"
    echo ">>> IMPORTANT: Edit $CONFIG_PATH with your PAM Server details and API key!"
else
    echo "[2/5] Config already exists at $CONFIG_PATH, skipping."
fi

# 3. Install systemd service
echo "[3/5] Installing systemd service..."
cp "$AGENT_DIR/pam-tenant-agent.service" /etc/systemd/system/pam-tenant-agent.service
chmod 644 /etc/systemd/system/pam-tenant-agent.service
systemctl daemon-reload

# 4a. Create log file
echo "[4/5] Creating log file..."
touch /var/log/pam-agent.log
chmod 640 /var/log/pam-agent.log

# 4b. Install logrotate config
echo "[4/5] Installing logrotate configuration..."
cp "$AGENT_DIR/pam-agent-logrotate" /etc/logrotate.d/pam-agent
chmod 644 /etc/logrotate.d/pam-agent

# 5. Enable and start service
echo "[5/5] Enabling and starting service..."
systemctl enable pam-tenant-agent.service
systemctl start pam-tenant-agent.service

echo ""
echo "=== Installation Complete ==="
echo ""
echo "Check status:  systemctl status pam-tenant-agent.service"
echo "View logs:     journalctl -u pam-tenant-agent.service -f"
echo "Config file:   $CONFIG_PATH"
echo ""
echo "Don't forget to:"
echo "  1. Edit $CONFIG_PATH with your PAM Server URL and API key"
echo "  2. Run './firewall.sh' to restrict access to PAM Server IP"
echo "  3. Restart the service: systemctl restart pam-tenant-agent.service"
