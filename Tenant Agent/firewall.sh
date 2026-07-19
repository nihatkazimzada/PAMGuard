#!/usr/bin/env bash
set -euo pipefail

echo "=== PAM Agent Firewall Setup ==="

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

# Read the PAM Server IP from config
CONFIG_PATH="/etc/pam-agent/config.yaml"
if [[ -f "$CONFIG_PATH" ]]; then
    PAM_IP=$(grep -oP 'pam_server_ip:\s*"\K[^"]+' "$CONFIG_PATH" 2>/dev/null || true)
fi

if [[ -z "${PAM_IP:-}" ]]; then
    echo "Could not read pam_server_ip from config."
    read -rp "Enter PAM Server IP address (e.g., 10.0.0.1): " PAM_IP
fi

echo "Configuring ufw to restrict agent access to PAM Server IP: $PAM_IP"

# UFW rules for the agent listener port (default 8800)
AGENT_PORT=$(grep -oP 'listen_port:\s*(\d+)' "$CONFIG_PATH" 2>/dev/null | awk '{print $2}' || echo "8800")

# Allow SSH from anywhere (so PAM Server can connect via SSH gateway)
ufw allow ssh

# Restrict agent HTTP listener to PAM Server only
ufw allow from "$PAM_IP" to any port "$AGENT_PORT" proto tcp comment "PAM Agent provision/revoke"
ufw deny "$AGENT_PORT" comment "Block agent port from all others"

# Enable ufw if not already enabled
ufw --force enable

echo ""
echo "=== Firewall configured ==="
echo "SSH:    allowed from everywhere"
echo "Port $AGENT_PORT: allowed only from $PAM_IP"
echo ""
echo "NOTE: This restricts the agent's provisioning endpoint to the PAM Server only."
echo "If you need to access this server directly via SSH, ensure SSH is allowed."
echo "For production, consider also restricting SSH to specific IPs."
