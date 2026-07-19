#!/usr/bin/env python3
"""
Start PAM Server and a public tunnel (local-host.run).
Outputs the public URL.
"""
import subprocess
import time
import os
import re
import signal
import sys

def main():
    os.chdir(os.path.join(os.path.dirname(__file__), "backend-python"))
    
    # Kill any existing uvicorn
    subprocess.run(["pkill", "-f", "uvicorn main:app"], capture_output=True)
    time.sleep(1)
    
    # Start backend
    backend = subprocess.Popen(
        ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "3001"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    print(f"Backend started (PID: {backend.pid})")
    
    # Wait for it to start
    time.sleep(4)
    
    # Verify it's running
    import urllib.request
    try:
        r = urllib.request.urlopen("http://localhost:3001/api/health")
        print(f"Backend health: {r.read().decode()}")
    except:
        print("WARNING: Backend may not be running")
    
    # Start tunnel
    tunnel = subprocess.Popen(
        ["ssh", "-o", "StrictHostKeyChecking=no", "-o", "ServerAliveInterval=30",
         "-R", "80:localhost:3001", "nokey@localhost.run"],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    print(f"Tunnel started (PID: {tunnel.pid})")
    
    # Wait for URL
    url = None
    start = time.time()
    while time.time() - start < 15:
        line = tunnel.stdout.readline()
        if line:
            print(line, end='', flush=True)
            # Look for the URL pattern: https://xxxxx.lhr.life
            m = re.search(r'https://[a-zA-Z0-9-]+\.lhr\.life', line)
            if m:
                url = m.group(0)
                break
    
    print("\n" + "=" * 60)
    print(f"  PAM CONSOLE IS LIVE!")
    print(f"  Public URL: {url}")
    print(f"  Login: nihat.kazimzada@example.com / nihat123")
    print("=" * 60)
    
    # Write URL to a file
    if url:
        with open("/tmp/pam_url.txt", "w") as f:
            f.write(url)
    
    # Keep running until interrupted
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\nShutting down...")
        tunnel.terminate()
        backend.terminate()
        sys.exit(0)

if __name__ == "__main__":
    main()
