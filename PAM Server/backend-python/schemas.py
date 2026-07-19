from pydantic import BaseModel
from typing import Optional, List
from datetime import datetime

class LoginRequest(BaseModel):
    username: str
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    user: dict

class UserCreate(BaseModel):
    full_name: str
    username: str
    password: str
    role: str = "user"
    company_id: Optional[str] = None

class UserResponse(BaseModel):
    id: str
    full_name: str
    username: str
    role: str
    company_id: Optional[str]
    company_name: Optional[str]
    status: str
    last_login: Optional[datetime]

class CompanyCreate(BaseModel):
    name: str
    tenant_id: str
    domain: Optional[str] = None
    industry: Optional[str] = None
    contact_email: str
    contact_phone: Optional[str] = None
    billing_email: Optional[str] = None

class AgentRegister(BaseModel):
    hostname: str
    ip: str
    os_version: Optional[str] = None
    tenant_company_id: Optional[str] = None
    agent_version: Optional[str] = None

class AgentHeartbeat(BaseModel):
    hostname: str
    status: str = "UP"
    load: Optional[float] = None
    last_activity: Optional[str] = None
    uptime_seconds: Optional[int] = None

class AgentEvent(BaseModel):
    event_type: str
    source: Optional[str] = "linux-agent"
    hostname: str
    username: Optional[str] = None
    detail: Optional[str] = None
    timestamp: Optional[str] = None

class ServerCreate(BaseModel):
    name: str
    ip: str
    port: int = 22
    allowed_connection_types: List[str] = ["ssh"]
    os: Optional[str] = None
    company_id: str

class RequestCreate(BaseModel):
    server_id: str
    access_level: str
    duration_minutes: int
    description: Optional[str] = None

class PasswordChange(BaseModel):
    current_password: str
    new_password: str

class UsernameChange(BaseModel):
    new_username: str

class AddFundsRequest(BaseModel):
    amount: float
    reason: Optional[str] = None
