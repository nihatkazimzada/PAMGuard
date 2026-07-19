#!/usr/bin/env python3
"""Unified PAM Server - serves both API and frontend from a single process."""
import uvicorn
import os

if __name__ == "__main__":
    port = int(os.getenv("PORT", "3001"))
    print(f"Starting PAM Server on http://0.0.0.0:{port}")
    uvicorn.run("main:app", host="0.0.0.0", port=port)
