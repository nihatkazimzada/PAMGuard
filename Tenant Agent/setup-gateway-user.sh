#!/usr/bin/env bash
set -euo pipefail

echo "=== PAM Gateway User Setup ==="

if [[ $EUID -ne 0 ]]; then
    echo "ERROR: This script must be run as root (sudo)." >&2
    exit 1
fi

GATEWAY_USER="pam-gateway"

if id "$GATEWAY_USER" &>/dev/null; then
    echo "User $GATEWAY_USER already exists."
else
    useradd -m -s /bin/bash "$GATEWAY_USER"
    echo "Created user: $GATEWAY_USER"
fi

# Create SSH directory for the gateway user
GATEWAY_SSH_DIR="/home/$GATEWAY_USER/.ssh"
mkdir -p "$GATEWAY_SSH_DIR"
chmod 700 "$GATEWAY_SSH_DIR"
touch "$GATEWAY_SSH_DIR/authorized_keys"
chmod 600 "$GATEWAY_SSH_DIR/authorized_keys"
chown -R "$GATEWAY_USER:$GATEWAY_USER" "/home/$GATEWAY_USER"

echo ""
echo "Gateway user $GATEWAY_USER is ready."
echo "The PAM Server's SSH public key must be added to:"
echo "  $GATEWAY_SSH_DIR/authorized_keys"
echo ""
echo "To restrict SSH to only this gateway user, add to /etc/ssh/sshd_config:"
echo "  AllowUsers $GATEWAY_USER"
echo "Then: systemctl restart sshd"
