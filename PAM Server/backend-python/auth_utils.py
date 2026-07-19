import bcrypt
from jose import jwt, JWTError
from datetime import datetime, timedelta
from typing import Optional
from config import JWT_SECRET, JWT_REFRESH_SECRET, JWT_ALGORITHM

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(12)).decode()

def verify_password(password: str, hash: str) -> bool:
    return bcrypt.checkpw(password.encode(), hash.encode())

def create_access_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(minutes=15)
    to_encode["type"] = "access"
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)

def create_refresh_token(data: dict) -> str:
    to_encode = data.copy()
    to_encode["exp"] = datetime.utcnow() + timedelta(days=7)
    to_encode["type"] = "refresh"
    return jwt.encode(to_encode, JWT_REFRESH_SECRET, algorithm=JWT_ALGORITHM)

def verify_token(token: str, secret: str = JWT_SECRET) -> Optional[dict]:
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM])
        return payload
    except JWTError:
        return None
