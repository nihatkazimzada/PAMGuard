import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Float, Text, DateTime, Boolean, ForeignKey, Enum, JSON, TypeDecorator
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import DeclarativeBase, relationship
import enum

from config import DATABASE_URL, IS_SQLITE

class UUIDType(TypeDecorator):
    impl = String(36)
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        return str(value) if isinstance(value, uuid.UUID) else value
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        return uuid.UUID(value) if isinstance(value, str) else value

class ListType(TypeDecorator):
    impl = String
    cache_ok = True
    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        import json
        return json.dumps(value)
    def process_result_value(self, value, dialect):
        if value is None:
            return None
        import json
        return json.loads(value) if isinstance(value, str) else value

engine = create_async_engine(DATABASE_URL, connect_args={"check_same_thread": False} if IS_SQLITE else {}, pool_size=5, max_overflow=10)
async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

class Base(DeclarativeBase):
    pass

class UserRole(str, enum.Enum):
    superuser = "superuser"
    admin = "admin"
    user = "user"

class UserStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"

class RequestStatus(str, enum.Enum):
    pending = "pending"
    approved = "approved"
    rejected = "rejected"
    expired = "expired"
    cancelled = "cancelled"

class AccessLevel(str, enum.Enum):
    root = "root"
    user = "user"

class ServerStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"

class SecurityStatus(str, enum.Enum):
    info = "info"
    warning = "warning"
    critical = "critical"

class AgentStatus(str, enum.Enum):
    active = "active"
    inactive = "inactive"

class Company(Base):
    __tablename__ = "companies"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    tenant_id = Column(String, unique=True, nullable=False)
    domain = Column(String, nullable=True)
    industry = Column(String, nullable=True)
    contact_email = Column(String, nullable=False)
    contact_phone = Column(String, nullable=True)
    billing_email = Column(String, nullable=True)
    api_key = Column(String, unique=True, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    users = relationship("User", back_populates="company")
    servers = relationship("Server", back_populates="company")

class User(Base):
    __tablename__ = "users"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    full_name = Column(String, nullable=False)
    username = Column(String, unique=True, nullable=False)
    password_hash = Column(String, nullable=False)
    role = Column(Enum(UserRole), nullable=False)
    company_id = Column(UUIDType(), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    status = Column(Enum(UserStatus), nullable=False, default=UserStatus.active)
    last_login = Column(DateTime, nullable=True)

    company = relationship("Company", back_populates="users")

class Server(Base):
    __tablename__ = "servers"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    name = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    port = Column(Integer, nullable=False, default=22)
    allowed_connection_types = Column(ListType(), default=lambda: ["ssh"])
    os = Column(String, nullable=True)
    company_id = Column(UUIDType(), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False)
    status = Column(Enum(ServerStatus), nullable=False, default=ServerStatus.inactive)
    created_at = Column(DateTime, default=datetime.utcnow)

    company = relationship("Company", back_populates="servers")

class Request(Base):
    __tablename__ = "requests"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id = Column(UUIDType(), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    access_level = Column(Enum(AccessLevel), nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(Enum(RequestStatus), nullable=False, default=RequestStatus.pending)
    requested_at = Column(DateTime, default=datetime.utcnow)
    approved_at = Column(DateTime, nullable=True)
    approved_by = Column(UUIDType(), ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    expires_at = Column(DateTime, nullable=True)
    provisioned_username = Column(String, nullable=True)
    provisioned_at = Column(DateTime, nullable=True)
    ssh_private_key = Column(Text, nullable=True)
    agent_port = Column(Integer, default=8800)

class Session(Base):
    __tablename__ = "sessions"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(UUIDType(), ForeignKey("requests.id", ondelete="SET NULL"), nullable=True)
    user_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    server_id = Column(UUIDType(), ForeignKey("servers.id", ondelete="CASCADE"), nullable=False)
    started_at = Column(DateTime, default=datetime.utcnow)
    ended_at = Column(DateTime, nullable=True)
    recording_data = Column(JSON, default=list)
    status = Column(String, nullable=False, default="active")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    timestamp = Column(DateTime, default=datetime.utcnow)
    event_type = Column(String, nullable=False)
    performed_by = Column(String, nullable=False)
    target = Column(String, nullable=True)
    action_detail = Column(Text, nullable=True)
    company_id = Column(UUIDType(), ForeignKey("companies.id", ondelete="SET NULL"), nullable=True)
    security_status = Column(Enum(SecurityStatus), nullable=False, default=SecurityStatus.info)
    source = Column(String, default="pam-server")

class Agent(Base):
    __tablename__ = "agents"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    hostname = Column(String, nullable=False)
    ip = Column(String, nullable=False)
    os_version = Column(String, nullable=True)
    tenant_company_id = Column(String, nullable=True)
    agent_version = Column(String, nullable=True)
    api_key = Column(String, unique=True, nullable=True)
    status = Column(Enum(AgentStatus), nullable=False, default=AgentStatus.active)
    last_seen = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class BillingAccount(Base):
    __tablename__ = "billing_accounts"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    admin_user_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False)
    balance = Column(Float, nullable=False, default=0)
    price_per_user = Column(Float, nullable=False, default=5)

class BillingTransaction(Base):
    __tablename__ = "billing_transactions"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    billing_account_id = Column(UUIDType(), ForeignKey("billing_accounts.id", ondelete="CASCADE"), nullable=False)
    amount = Column(Float, nullable=False)
    reason = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

class Notification(Base):
    __tablename__ = "notifications"
    id = Column(UUIDType(), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(UUIDType(), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    type = Column(String, nullable=False)
    message = Column(Text, nullable=False)
    link = Column(String, nullable=True)
    read = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
