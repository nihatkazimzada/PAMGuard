import os

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./pam.db")
JWT_SECRET = os.getenv("JWT_SECRET", "pam-server-jwt-secret-key-2024")
JWT_REFRESH_SECRET = os.getenv("JWT_REFRESH_SECRET", "pam-server-refresh-secret-key-2024")
JWT_ALGORITHM = "HS256"
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:5173")
AGENT_API_KEY = os.getenv("AGENT_API_KEY", "shared-agent-api-key-pam2024")
IS_SQLITE = DATABASE_URL.startswith("sqlite")
