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
ssh -o StrictHostKeyChecking=no -o ServerAliveInterval=30 -R 80:localhost:3001 nokey@localhost.run 2>&1 &
TUNNEL_PID=$!
echo "Tunnel started (PID: $TUNNEL_PID)"

echo ""
echo "=== Server is running ==="
echo "Local:  http://localhost:3001"
echo "Public: https://<subdomain>.lhr.life (check tunnel output above)"

# Wait for background processes
wait $BACKEND_PID $TUNNEL_PID
