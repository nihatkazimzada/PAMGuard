import json
import uuid
import csv
import io
import os
import hmac
import hashlib
import tempfile
from datetime import datetime, timedelta
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query, Body, Request as FastAPIRequest
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select, func, or_, and_, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import (
    async_session, init_db, Company, User, Server, Request, Session,
    AuditLog, BillingAccount, BillingTransaction, Notification,
    UserRole, UserStatus, RequestStatus, ServerStatus, SecurityStatus, AccessLevel,
    Agent, AgentStatus
)
from schemas import (
    LoginRequest, UserCreate, CompanyCreate, ServerCreate,
    RequestCreate, PasswordChange, UsernameChange, AddFundsRequest
)
from auth_utils import hash_password, verify_password, create_access_token, create_refresh_token, verify_token
from config import FRONTEND_URL, AGENT_API_KEY

import asyncio
import httpx
import re

active_connections: dict[str, WebSocket] = {}
active_ssh_sessions: dict[str, dict] = {}

SUSPICIOUS_PATTERNS = [
    (re.compile(r'\bsudo\s+', re.IGNORECASE), 'critical', 'Privilege escalation: sudo command used'),
    (re.compile(r'^su\s+-|^su\b', re.IGNORECASE), 'critical', 'Privilege escalation: su command used'),
    (re.compile(r'chmod\s+\+?4?7{2}7', re.IGNORECASE), 'critical', 'Setuid bit set via chmod'),
    (re.compile(r'chmod\s+\+?s', re.IGNORECASE), 'critical', 'Setuid bit set via chmod +s'),
    (re.compile(r'pkexec\s+', re.IGNORECASE), 'critical', 'Privilege escalation via pkexec'),
    (re.compile(r'doas\s+', re.IGNORECASE), 'critical', 'Privilege escalation via doas'),
    (re.compile(r'wget\s+.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Remote code execution: wget pipe to shell'),
    (re.compile(r'curl\s+.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Remote code execution: curl pipe to shell'),
    (re.compile(r'base64\s+-d.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Obfuscated command execution via base64'),
    (re.compile(r'\becho\s+.*\|.*base64\s+-d.*\|.*\b(bash|sh)\b', re.IGNORECASE), 'critical', 'Obfuscated command execution via echo+base64'),
    (re.compile(r'\b(apt-get|apt|yum|dnf|zypper|pacman)\s+install\b', re.IGNORECASE), 'critical', 'Unauthorized package installation'),
    (re.compile(r'\bpip\s+install\b', re.IGNORECASE), 'critical', 'Unauthorized Python package install'),
    (re.compile(r'\bnpm\s+install\s+-g\b', re.IGNORECASE), 'critical', 'Unauthorized global npm install'),
    (re.compile(r'chmod\s+\+x\s+', re.IGNORECASE), 'critical', 'Making file executable'),
    (re.compile(r'docker\s+run\s+.*--privileged', re.IGNORECASE), 'critical', 'Docker container with privileged flag'),
    (re.compile(r':\(\)\s*\{.*:\|:&\s*\;.*\};?\s*:', re.IGNORECASE), 'critical', 'Fork bomb detected'),
    (re.compile(r'dd\s+if=/dev/urandom\s+of=', re.IGNORECASE), 'critical', 'Destructive dd command'),
    (re.compile(r'cat\s+/dev/sda|dd\s+if=/dev/sda|fdisk\s+/dev/sda', re.IGNORECASE), 'critical', 'Raw disk access detected'),
    (re.compile(r'>\s*/dev/sda|mkfs\.|fdisk\s+/dev/', re.IGNORECASE), 'critical', 'Disk destruction command detected'),
]

SSH_KEY_PATTERN = re.compile(
    r'-----BEGIN\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----[\s\S]*?-----END\s+(RSA\s+)?(OPENSSH\s+)?(EC\s+)?PRIVATE\s+KEY-----',
    re.IGNORECASE
)

def mask_ssh_keys(text: str) -> str:
    return SSH_KEY_PATTERN.sub('[SSH KEY REDACTED]', text)

def detect_suspicious_activity(text: str) -> list[dict]:
    findings = []
    for pattern, severity, description in SUSPICIOUS_PATTERNS:
        if pattern.search(text):
            findings.append({"severity": severity, "description": description})
    return findings

async def get_db():
    async with async_session() as session:
        yield session

def get_user_id(user_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(user_id)
    except:
        raise HTTPException(400, "Invalid user ID")

def get_current_user_from_token(token: str = None, websocket: WebSocket = None):
    if websocket:
        token = websocket.cookies.get("access_token") or websocket.query_params.get("token")
    if not token:
        return None
    payload = verify_token(token)
    if not payload:
        return None
    return payload

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    task = asyncio.create_task(expire_old_requests())
    yield
    task.cancel()

app = FastAPI(title="PAM Server", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[FRONTEND_URL, "*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ─── Helper ───────────────────────────────────────────────────────────────────

async def get_company_id_for_user(user_id: str, db: AsyncSession) -> Optional[str]:
    result = await db.execute(select(User).where(User.id == get_user_id(user_id)))
    user = result.scalar_one_or_none()
    return str(user.company_id) if user and user.company_id else None

async def log_audit(db: AsyncSession, event_type: str, performed_by: str, target: str = None,
                    action_detail: str = None, company_id: str = None, security_status: str = "info"):
    entry = AuditLog(
        event_type=event_type, performed_by=performed_by, target=target,
        action_detail=action_detail, company_id=get_user_id(company_id) if company_id else None,
        security_status=SecurityStatus(security_status)
    )
    db.add(entry)
    await db.commit()

async def notify_user(db: AsyncSession, user_id: str, type: str, message: str, link: str = None):
    notif = Notification(user_id=get_user_id(user_id), type=type, message=message, link=link)
    db.add(notif)
    await db.commit()
    ws = active_connections.get(user_id)
    if ws:
        try:
            await ws.send_json({"type": "notification", "data": {"id": str(notif.id), "type": type, "message": message, "link": link, "read": False}})
        except:
            pass

async def notify_admins_and_superusers(db: AsyncSession, company_id: str, type: str, message: str, link: str = None):
    result = await db.execute(
        select(User).where(
            or_(User.role == UserRole.superuser,
                and_(User.role == UserRole.admin, User.company_id == get_user_id(company_id)))
        )
    )
    users = result.scalars().all()
    for u in users:
        await notify_user(db, str(u.id), type, message, link)

async def agent_revoke(db: AsyncSession, req, delete_req=False):
    if not req.provisioned_username:
        return
    server = await db.execute(select(Server).where(Server.id == req.server_id))
    server = server.scalar_one_or_none()
    if not server:
        return
    company = await db.execute(select(Company).where(Company.id == server.company_id))
    company = company.scalar_one_or_none()
    api_key = company.api_key if company else None
    agent_port = req.agent_port or 8800
    try:
        async with httpx.AsyncClient(timeout=5) as client:
            await client.post(
                f"http://{server.ip}:{agent_port}/agent/revoke",
                json={"request_id": str(req.id), "username": req.provisioned_username},
                headers={"X-API-Key": api_key or AGENT_API_KEY}
            )
    except:
        pass
    if not delete_req:
        req.provisioned_username = None
        req.ssh_private_key = None
        req.provisioned_at = None
        await db.commit()
    result = await db.execute(
        select(User).where(
            or_(User.role == UserRole.superuser,
                and_(User.role == UserRole.admin, User.company_id == get_user_id(company_id)))
        )
    )
    users = result.scalars().all()
    for u in users:
        await notify_user(db, str(u.id), type, message, link)

async def verify_agent_hmac(request, body_bytes: bytes, db: AsyncSession):
    api_key = request.headers.get("X-API-Key")
    signature = request.headers.get("X-Signature")
    if not api_key or not signature:
        raise HTTPException(401, "Missing API key or signature")
    company = await db.execute(select(Company).where(Company.api_key == api_key))
    company = company.scalar_one_or_none()
    if not company:
        agent = await db.execute(select(Agent).where(Agent.api_key == api_key))
        agent = agent.scalar_one_or_none()
        if not agent:
            raise HTTPException(401, "Invalid API key")
        return api_key, company
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")
    return api_key, company

# ─── Auth Routes ──────────────────────────────────────────────────────────────

@app.post("/api/auth/login")
async def login(data: LoginRequest, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(User).where(User.username == data.username))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.password, user.password_hash):
        await log_audit(db, "login_failed", data.username, security_status="warning")
        raise HTTPException(401, "Invalid username or password")
    if user.status == UserStatus.inactive:
        raise HTTPException(403, "Account is deactivated")
    
    user.last_login = datetime.utcnow()
    await db.commit()

    payload = {"user_id": str(user.id), "username": user.username, "role": user.role.value,
               "company_id": str(user.company_id) if user.company_id else None}
    access_token = create_access_token(payload)
    refresh_token = create_refresh_token(payload)

    company_name = None
    if user.company_id:
        c_result = await db.execute(select(Company).where(Company.id == user.company_id))
        company = c_result.scalar_one_or_none()
        company_name = company.name if company else None

    await log_audit(db, "login", user.username, str(user.id), "User logged in successfully",
                    str(user.company_id) if user.company_id else None)

    return {
        "access_token": access_token, "refresh_token": refresh_token,
        "user": {
            "id": str(user.id), "fullName": user.full_name, "username": user.username,
            "role": user.role.value, "companyId": str(user.company_id) if user.company_id else None,
            "companyName": company_name, "status": user.status.value
        }
    }

@app.post("/api/auth/refresh")
async def refresh(token_data: dict = Body(...), db: AsyncSession = Depends(get_db)):
    token = token_data.get("refreshToken")
    if not token:
        raise HTTPException(400, "Refresh token required")
    payload = verify_token(token, JWT_REFRESH_SECRET)
    if not payload:
        raise HTTPException(401, "Invalid refresh token")
    result = await db.execute(select(User).where(User.id == get_user_id(payload["user_id"])))
    user = result.scalar_one_or_none()
    if not user or user.status == UserStatus.inactive:
        raise HTTPException(401, "Invalid refresh token")
    new_payload = {"user_id": str(user.id), "username": user.username, "role": user.role.value,
                   "company_id": str(user.company_id) if user.company_id else None}
    return {"access_token": create_access_token(new_payload), "refresh_token": create_refresh_token(new_payload)}

@app.get("/api/auth/me")
async def get_me(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(User, Company.name).outerjoin(Company, User.company_id == Company.id).where(User.id == get_user_id(payload["user_id"]))
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "User not found")
    user, company_name = row
    return {
        "id": str(user.id), "fullName": user.full_name, "username": user.username,
        "role": user.role.value, "companyId": str(user.company_id) if user.company_id else None,
        "companyName": company_name, "status": user.status.value
    }

@app.post("/api/auth/change-password")
async def change_password(data: PasswordChange, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(User).where(User.id == get_user_id(payload["user_id"])))
    user = result.scalar_one_or_none()
    if not user or not verify_password(data.current_password, user.password_hash):
        raise HTTPException(400, "Current password is incorrect")
    user.password_hash = hash_password(data.new_password)
    await db.commit()
    await log_audit(db, "password_change", user.username, str(user.id), "Password changed",
                    str(user.company_id) if user.company_id else None)
    return {"message": "Password changed successfully"}

@app.post("/api/auth/change-username")
async def change_username(data: UsernameChange, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    existing = await db.execute(select(User).where(User.username == data.new_username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Username already taken")
    result = await db.execute(select(User).where(User.id == get_user_id(payload["user_id"])))
    user = result.scalar_one_or_none()
    user.username = data.new_username
    await db.commit()
    await log_audit(db, "username_change", payload["username"], str(user.id), f"Username changed to {data.new_username}",
                    str(user.company_id) if user.company_id else None)
    return {"message": "Username changed successfully"}

# ─── Dashboard ────────────────────────────────────────────────────────────────

@app.get("/api/dashboard/stats")
async def dashboard_stats(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")

    company_id = payload.get("company_id") if payload["role"] != "superuser" else None
    cid = get_user_id(company_id) if company_id else None

    async def count_with_filter(model, column, value):
        query = select(func.count(model.id)).where(column == value)
        if cid and hasattr(model, "company_id"):
            query = query.where(model.company_id == cid)
        result = await db.execute(query)
        return result.scalar()

    async def count_all(model):
        query = select(func.count(model.id))
        if cid and hasattr(model, "company_id"):
            query = query.where(model.company_id == cid)
        result = await db.execute(query)
        return result.scalar()

    admin_count = await count_with_filter(User, User.role, UserRole.admin)
    company_count = await count_all(Company)
    user_count = await count_with_filter(User, User.role, UserRole.user)
    request_count = await count_all(Request)
    server_count = await count_all(Server)
    active_session_count = await count_with_filter(Session, Session.status, "active")

    audit_query = select(func.count(AuditLog.id)).where(AuditLog.security_status == SecurityStatus.critical)
    if cid:
        audit_query = audit_query.where(AuditLog.company_id == cid)
    critical_count = (await db.execute(audit_query)).scalar()

    audit_query2 = select(func.count(AuditLog.id)).where(AuditLog.security_status == SecurityStatus.warning)
    if cid:
        audit_query2 = audit_query2.where(AuditLog.company_id == cid)
    high_count = (await db.execute(audit_query2)).scalar()

    companies_data = []
    companies_result = await db.execute(select(Company))
    for c in companies_result.scalars():
        uc = await db.execute(select(func.count(User.id)).where(User.company_id == c.id))
        companies_data.append({"id": str(c.id), "name": c.name, "user_count": uc.scalar()})

    recent = await db.execute(
        select(AuditLog).order_by(AuditLog.timestamp.desc()).limit(10)
    )
    recent_activities = [
        {"timestamp": r.timestamp.isoformat() + 'Z', "event_type": r.event_type, "performed_by": r.performed_by,
         "action_detail": r.action_detail, "security_status": r.security_status.value}
        for r in recent.scalars()
    ]

    failed_query = select(AuditLog.timestamp).where(
        AuditLog.event_type == 'login_failed',
        AuditLog.timestamp >= datetime.utcnow() - timedelta(hours=24)
    )
    if cid:
        failed_query = failed_query.where(AuditLog.company_id == cid)
    failed_logins_raw = await db.execute(failed_query)
    hours_count = {}
    for row in failed_logins_raw:
        hour_key = str(row.timestamp).split(':')[0] + ':00:00'
        hours_count[hour_key] = hours_count.get(hour_key, 0) + 1
    failed_logins = [{"hour": h, "count": c} for h, c in sorted(hours_count.items())]

    return {
        "adminCount": admin_count, "companyCount": company_count, "companies": companies_data,
        "userCount": user_count, "requestCount": request_count, "serverCount": server_count, "activeSessionCount": active_session_count,
        "criticalCount": critical_count, "highCount": high_count, "failedLogins": failed_logins,
        "recentActivities": recent_activities
    }

@app.get("/api/dashboard/user-stats")
async def user_dashboard_stats(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] not in ("user", "admin", "superuser"):
        raise HTTPException(401, "Not authenticated")
    
    user_id = get_user_id(payload["user_id"])
    company_id = get_user_id(payload["company_id"]) if payload.get("company_id") else None

    pending_count = (await db.execute(
        select(func.count(Request.id)).where(Request.requester_id == user_id, Request.status == RequestStatus.pending)
    )).scalar()
    approved_count = (await db.execute(
        select(func.count(Request.id)).where(Request.requester_id == user_id, Request.status == RequestStatus.approved)
    )).scalar()
    active_sessions = (await db.execute(
        select(func.count(Session.id)).where(Session.user_id == user_id, Session.status == "active")
    )).scalar()

    recent_reqs = await db.execute(
        select(Request, Server.name.label("server_name"), Server.ip.label("server_ip"))
        .join(Server, Request.server_id == Server.id)
        .where(Request.requester_id == user_id)
        .order_by(Request.requested_at.desc())
        .limit(5)
    )
    recent_requests = [
        {"id": str(r.Request.id), "server_name": r.server_name, "server_ip": r.server_ip,
         "access_level": r.Request.access_level.value, "status": r.Request.status.value,
         "duration_minutes": r.Request.duration_minutes, "description": r.Request.description,
         "requested_at": r.Request.requested_at.isoformat() + 'Z'}
        for r in recent_reqs
    ]

    recent_activities = []
    audit_logs = await db.execute(
        select(AuditLog).where(AuditLog.performed_by == payload["username"])
        .order_by(AuditLog.timestamp.desc()).limit(8)
    )
    recent_activities = [
        {"timestamp": r.timestamp.isoformat() + 'Z', "event_type": r.event_type,
         "action_detail": r.action_detail, "security_status": r.security_status.value}
        for r in audit_logs.scalars()
    ]

    server_count = 0
    if company_id:
        sc = await db.execute(select(func.count(Server.id)).where(Server.company_id == company_id))
        server_count = sc.scalar()

    return {
        "pendingCount": pending_count, "approvedCount": approved_count,
        "activeSessionCount": active_sessions, "recentRequests": recent_requests,
        "recentActivities": recent_activities, "serverCount": server_count
    }

# ─── Companies ────────────────────────────────────────────────────────────────

@app.get("/api/companies")
async def list_companies(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Company).order_by(Company.created_at.desc()))
    companies = []
    for c in result.scalars():
        sc = await db.execute(select(func.count(Server.id)).where(Server.company_id == c.id))
        uc = await db.execute(select(func.count(User.id)).where(User.company_id == c.id))
        companies.append({
            "id": str(c.id), "name": c.name, "tenant_id": c.tenant_id, "domain": c.domain,
            "industry": c.industry, "contact_email": c.contact_email, "contact_phone": c.contact_phone,
            "billing_email": c.billing_email, "api_key": c.api_key, "created_at": str(c.created_at),
            "server_count": sc.scalar(), "user_count": uc.scalar()
        })
    return companies

@app.post("/api/companies")
async def create_company(data: CompanyCreate, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    existing = await db.execute(select(Company).where(Company.tenant_id == data.tenant_id))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Tenant ID already exists")
    api_key = "pam_" + data.tenant_id.replace("-", "_")[:8] + "_" + uuid.uuid4().hex[:12]
    company = Company(name=data.name, tenant_id=data.tenant_id, domain=data.domain, industry=data.industry,
                      contact_email=data.contact_email, contact_phone=data.contact_phone,
                      billing_email=data.billing_email, api_key=api_key)
    db.add(company)
    await db.commit()
    await log_audit(db, "company_created", payload["username"], str(company.id),
                    f"Created company: {company.name} ({company.tenant_id})")
    return {"id": str(company.id), "name": company.name, "tenant_id": company.tenant_id, "api_key": api_key}

@app.delete("/api/companies/{company_id}")
async def delete_company(company_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Company).where(Company.id == get_user_id(company_id)))
    company = result.scalar_one_or_none()
    if not company:
        raise HTTPException(404, "Company not found")
    await db.delete(company)
    await db.commit()
    await log_audit(db, "company_deleted", payload["username"], company_id, f"Deleted company: {company.name}",
                    security_status="warning")
    return {"message": "Company deleted"}

# ─── Agent Management ─────────────────────────────────────────────────────────

@app.post("/api/agent/register", response_model=None)
async def agent_register(incoming: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    body_bytes = await incoming.body()
    data = json.loads(body_bytes) if body_bytes else {}
    api_key = incoming.headers.get("X-API-Key")
    signature = incoming.headers.get("X-Signature")
    if not api_key or not signature:
        raise HTTPException(401, "Missing API key or signature")
    company = await db.execute(select(Company).where(Company.api_key == api_key))
    company = company.scalar_one_or_none()
    if not company:
        raise HTTPException(401, "Invalid API key")
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")

    hostname = data.get("hostname", "unknown")

    # Find existing agent by API key first (unique), then by hostname
    agent = await db.execute(select(Agent).where(Agent.api_key == api_key))
    agent = agent.scalar_one_or_none()
    if not agent:
        agent = await db.execute(select(Agent).where(Agent.hostname == hostname))
        agent = agent.scalar_one_or_none()

    if agent:
        agent.hostname = hostname
        agent.ip = data.get("ip", agent.ip)
        agent.os_version = data.get("os_version", agent.os_version)
        agent.agent_version = data.get("agent_version", agent.agent_version)
        agent.tenant_company_id = data.get("tenant_company_id", agent.tenant_company_id)
        agent.last_seen = datetime.utcnow()
        agent.status = AgentStatus.active
    else:
        agent = Agent(
            hostname=hostname, ip=data.get("ip"),
            os_version=data.get("os_version"), tenant_company_id=data.get("tenant_company_id"),
            agent_version=data.get("agent_version"), api_key=api_key, last_seen=datetime.utcnow()
        )
        db.add(agent)
        await db.flush()
        await log_audit(db, "agent_registered", hostname, data.get("ip"),
                        f"Agent registered: {hostname}")

    await db.commit()

    # Update the associated server record to active
    server = await db.execute(
        select(Server).where(Server.company_id == company.id)
    )
    server = server.scalar_one_or_none()
    if server:
        server.status = ServerStatus.active
        await db.commit()

    return {"message": "Agent registered", "hostname": hostname}

@app.post("/api/agent/heartbeat", response_model=None)
async def agent_heartbeat(incoming: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    body_bytes = await incoming.body()
    data = json.loads(body_bytes) if body_bytes else {}
    api_key = incoming.headers.get("X-API-Key")
    signature = incoming.headers.get("X-Signature")
    if not api_key or not signature:
        raise HTTPException(401, "Missing API key or signature")
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")

    hostname = data.get("hostname")

    # Find agent by API key first, then by hostname
    agent = await db.execute(select(Agent).where(Agent.api_key == api_key))
    agent = agent.scalar_one_or_none()
    if not agent and hostname:
        agent = await db.execute(select(Agent).where(Agent.hostname == hostname))
        agent = agent.scalar_one_or_none()
    if not agent:
        raise HTTPException(404, "Agent not found")

    agent.last_seen = datetime.utcnow()
    agent.status = AgentStatus.active if data.get("status") in ("UP", None) else AgentStatus.inactive
    if hostname:
        agent.hostname = hostname
    await db.commit()

    # Update the associated server record
    company = await db.execute(select(Company).where(Company.api_key == api_key))
    company = company.scalar_one_or_none()
    if company:
        server = await db.execute(
            select(Server).where(Server.company_id == company.id)
        )
        server = server.scalar_one_or_none()
        if server:
            server.status = ServerStatus.active
            await db.commit()

    return {"message": "Heartbeat received"}

@app.post("/api/agent/events", response_model=None)
async def agent_events(incoming: FastAPIRequest, db: AsyncSession = Depends(get_db)):
    body_bytes = await incoming.body()
    data = json.loads(body_bytes) if body_bytes else {}
    events = data.get("events", data)
    if isinstance(events, dict):
        events = [events]
    api_key = incoming.headers.get("X-API-Key")
    signature = incoming.headers.get("X-Signature")
    if not api_key or not signature:
        raise HTTPException(401, "Missing API key or signature")
    expected = hmac.new(api_key.encode(), body_bytes, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        raise HTTPException(401, "Invalid HMAC signature")
    company = await db.execute(select(Company).where(Company.api_key == api_key))
    company = company.scalar_one_or_none()
    if not company:
        raise HTTPException(401, "Invalid API key")
    company_id = str(company.id)
    for ev in events:
        event_type = ev.get("event_type", "unknown")
        ss = SecurityStatus.info
        et = event_type.upper()
        if et in ("ACCOUNT_CREATED", "ACCOUNT_REMOVED"):
            ss = SecurityStatus.warning
        elif et in ("LOGIN_FAILED",):
            ss = SecurityStatus.warning
        elif et in ("SUDO_USED",):
            ss = SecurityStatus.info
        await log_audit(db, event_type, ev.get("username", "agent"),
                        ev.get("hostname"), ev.get("detail"), company_id, ss.value)
    return {"message": f"{len(events)} events recorded"}

# ─── Users ────────────────────────────────────────────────────────────────────

@app.get("/api/users")
async def list_users(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(User, Company.name).outerjoin(Company, User.company_id == Company.id)
    if payload["role"] != "superuser":
        query = query.where(User.company_id == get_user_id(payload["company_id"])) if payload.get("company_id") else query.where(User.company_id.is_(None))
    result = await db.execute(query.order_by(User.role, User.full_name))
    return [
        {"id": str(u.id), "full_name": u.full_name, "username": u.username, "role": u.role.value,
         "company_id": str(u.company_id) if u.company_id else None, "company_name": cn,
         "status": u.status.value, "last_login": str(u.last_login) if u.last_login else None}
        for u, cn in result
    ]

@app.get("/api/users/all")
async def list_all_users(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(
        select(User, Company.name).outerjoin(Company, User.company_id == Company.id).order_by(User.role, User.full_name)
    )
    return [
        {"id": str(u.id), "full_name": u.full_name, "username": u.username, "role": u.role.value,
         "company_id": str(u.company_id) if u.company_id else None, "company_name": cn,
         "status": u.status.value, "last_login": str(u.last_login) if u.last_login else None}
        for u, cn in result
    ]

@app.post("/api/users")
async def create_user(data: UserCreate, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    
    existing = await db.execute(select(User).where(User.username == data.username))
    if existing.scalar_one_or_none():
        raise HTTPException(400, "Username already exists")

    if payload["role"] == "admin" and data.role == "admin":
        raise HTTPException(403, "Admin cannot create another admin")

    company_id = data.company_id or payload.get("company_id")
    if not company_id:
        raise HTTPException(400, "Company is required")
    
    if data.role == "admin":
        existing_admin = await db.execute(
            select(User).where(User.company_id == get_user_id(company_id), User.role == UserRole.admin)
        )
        if existing_admin.scalar_one_or_none():
            raise HTTPException(400, "This company already has an admin")

    # Billing check for admin/user creation
    if data.role in ("admin", "user"):
        billing_result = await db.execute(
            select(BillingAccount).where(BillingAccount.admin_user_id == get_user_id(payload["user_id"]))
        )
        billing = billing_result.scalar_one_or_none()
        if billing and billing.balance < billing.price_per_user:
            raise HTTPException(400, "Insufficient billing balance")
        if billing:
            billing.balance -= billing.price_per_user
            txn = BillingTransaction(billing_account_id=billing.id, amount=-billing.price_per_user,
                                     reason=f"User creation: {data.full_name}")
            db.add(txn)

    user = User(full_name=data.full_name, username=data.username,
                password_hash=hash_password(data.password), role=UserRole(data.role),
                company_id=get_user_id(company_id))
    db.add(user)
    await db.commit()

    await log_audit(db, "user_created", payload["username"], str(user.id),
                    f"Created {data.role} user: {data.full_name} ({data.username})", company_id)

    await notify_admins_and_superusers(db, company_id, "user_created",
                                       f"New user {data.full_name} has been created", "/users")

    return {"id": str(user.id), "full_name": user.full_name, "username": user.username,
            "role": user.role.value, "company_id": str(user.company_id) if user.company_id else None}

@app.patch("/api/users/{user_id}/status")
async def change_user_status(user_id: str, body: dict = Body(...), token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(User).where(User.id == get_user_id(user_id)))
    user = result.scalar_one_or_none()
    if not user:
        raise HTTPException(404, "User not found")
    
    new_status = body.get("status")
    if new_status not in ("active", "inactive"):
        raise HTTPException(400, "Invalid status")

    if payload["role"] != "superuser":
        if user.role == UserRole.admin:
            raise HTTPException(403, "Cannot change admin status")
        if str(user.company_id) != payload.get("company_id"):
            raise HTTPException(403, "Access denied")

    user.status = UserStatus(new_status)
    await db.commit()
    await log_audit(db, "user_status_change", payload["username"], user_id,
                    f"User {user.full_name} status changed to {new_status}",
                    str(user.company_id) if user.company_id else None,
                    "info" if new_status == "active" else "warning")
    return {"message": f"User {'activated' if new_status == 'active' else 'deactivated'} successfully"}

# ─── Servers ──────────────────────────────────────────────────────────────────

@app.get("/api/servers")
async def list_servers(token: str = Query(None), company_id: str = None, status: str = None, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(Server, Company.name).join(Company, Server.company_id == Company.id)
    if payload["role"] != "superuser":
        query = query.where(Server.company_id == get_user_id(payload["company_id"]))
    elif company_id:
        query = query.where(Server.company_id == get_user_id(company_id))
    if status:
        query = query.where(Server.status == ServerStatus(status))
    result = await db.execute(query.order_by(Server.created_at.desc()))
    servers = []
    for s, cn in result:
        sd = {"id": str(s.id), "name": s.name, "ip": s.ip, "company_id": str(s.company_id),
              "company_name": cn, "status": s.status.value, "created_at": str(s.created_at)}
        if payload["role"] != "user":
            sd.update({"port": s.port, "os": s.os, "allowed_connection_types": s.allowed_connection_types})
        servers.append(sd)
    return servers

@app.post("/api/servers")
async def create_server(data: ServerCreate, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    server = Server(name=data.name, ip=data.ip, port=data.port,
                    allowed_connection_types=data.allowed_connection_types, os=data.os,
                    company_id=get_user_id(data.company_id))
    db.add(server)
    await db.commit()
    await log_audit(db, "server_created", payload["username"], str(server.id),
                    f"Created server: {server.name} ({server.ip})", data.company_id)
    # Check connectivity asynchronously
    asyncio.create_task(check_server_connectivity(str(server.id), data.ip))
    return {"id": str(server.id), "name": server.name, "ip": server.ip, "status": server.status.value}

async def check_server_connectivity(server_id: str, ip: str):
    is_real = ip in ("VM2_IP_PLACEHOLDER", "VM3_IP_PLACEHOLDER")
    async with async_session() as db:
        result = await db.execute(select(Server).where(Server.id == get_user_id(server_id)))
        server = result.scalar_one_or_none()
        if not server:
            return
        new_status = ServerStatus.inactive
        if is_real:
            try:
                async with httpx.AsyncClient(timeout=5) as client:
                    r = await client.get(f"http://{ip}:9100/agent/heartbeat",
                                         headers={"X-API-Key": AGENT_API_KEY})
                    if r.is_success:
                        new_status = ServerStatus.active
            except:
                pass
        if server.status != new_status:
            server.status = new_status
            await db.commit()
            await log_audit(db, "server_status_change", "system", server_id,
                            f"Server {server.name} status changed to {new_status.value}",
                            str(server.company_id) if server.company_id else None,
                            "info" if new_status == ServerStatus.active else "warning")

@app.get("/api/servers/{server_id}")
async def get_server(server_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Server, Company.name).join(Company, Server.company_id == Company.id).where(Server.id == get_user_id(server_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Server not found")
    s, cn = row
    sd = {"id": str(s.id), "name": s.name, "ip": s.ip, "company_id": str(s.company_id),
          "company_name": cn, "status": s.status.value, "created_at": str(s.created_at)}
    if payload["role"] != "user":
        sd.update({"port": s.port, "os": s.os, "allowed_connection_types": s.allowed_connection_types})
    return sd

@app.delete("/api/servers/{server_id}")
async def delete_server(server_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Server).where(Server.id == get_user_id(server_id)))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(404, "Server not found")
    await db.delete(server)
    await db.commit()
    await log_audit(db, "server_deleted", payload["username"], server_id, f"Deleted server: {server.name}",
                    str(server.company_id) if server.company_id else None, "warning")
    return {"message": "Server deleted"}

# ─── Requests ─────────────────────────────────────────────────────────────────

@app.get("/api/requests")
async def list_requests(token: str = Query(None), status: str = None, requester_id: str = None, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(
        Request, User.full_name.label("requester_name"), User.username.label("requester_username"),
        Server.name.label("server_name"), Server.ip.label("server_ip"), Company.name.label("company_name"),
        Company.id.label("company_id")
    ).join(User, Request.requester_id == User.id).join(Server, Request.server_id == Server.id).join(Company, Server.company_id == Company.id)
    
    if payload["role"] == "user":
        query = query.where(Request.requester_id == get_user_id(payload["user_id"]))
    elif payload["role"] == "admin":
        query = query.where(Server.company_id == get_user_id(payload["company_id"]))
    
    if requester_id:
        query = query.where(Request.requester_id == get_user_id(requester_id))
    if status:
        query = query.where(Request.status == RequestStatus(status))
    
    result = await db.execute(query.order_by(Request.requested_at.desc()))
    return [
        {"id": str(r.Request.id), "requester_id": str(r.Request.requester_id),
         "requester_name": r.requester_name, "requester_username": r.requester_username,
         "server_id": str(r.Request.server_id), "server_name": r.server_name, "server_ip": r.server_ip,
         "company_name": r.company_name, "company_id": str(r.company_id),
         "access_level": r.Request.access_level.value, "duration_minutes": r.Request.duration_minutes,
         "description": r.Request.description, "status": r.Request.status.value,
          "requested_at": r.Request.requested_at.isoformat() + 'Z', "approved_at": r.Request.approved_at.isoformat() + 'Z' if r.Request.approved_at else None,
         "approved_by": str(r.Request.approved_by) if r.Request.approved_by else None, "expires_at": r.Request.expires_at.isoformat() + 'Z' if r.Request.expires_at else None}
        for r in result
    ]

@app.get("/api/requests/my")
async def list_my_requests(token: str = Query(None), status: str = None, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(
        Request, User.full_name.label("requester_name"), User.username.label("requester_username"),
        Server.name.label("server_name"), Server.ip.label("server_ip"), Company.name.label("company_name"),
        Company.id.label("company_id")
    ).join(User, Request.requester_id == User.id).join(Server, Request.server_id == Server.id).join(Company, Server.company_id == Company.id)
    query = query.where(Request.requester_id == get_user_id(payload["user_id"]))
    if status:
        query = query.where(Request.status == RequestStatus(status))
    result = await db.execute(query.order_by(Request.requested_at.desc()))
    return [
        {"id": str(r.Request.id), "requester_id": str(r.Request.requester_id),
         "requester_name": r.requester_name, "requester_username": r.requester_username,
         "server_id": str(r.Request.server_id), "server_name": r.server_name, "server_ip": r.server_ip,
         "company_name": r.company_name, "company_id": str(r.company_id),
         "access_level": r.Request.access_level.value, "duration_minutes": r.Request.duration_minutes,
         "description": r.Request.description, "status": r.Request.status.value,
         "requested_at": r.Request.requested_at.isoformat() + 'Z', "approved_at": r.Request.approved_at.isoformat() + 'Z' if r.Request.approved_at else None,
         "approved_by": str(r.Request.approved_by) if r.Request.approved_by else None, "expires_at": r.Request.expires_at.isoformat() + 'Z' if r.Request.expires_at else None}
        for r in result
    ]

@app.post("/api/requests")
async def create_request(data: RequestCreate, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(Server).where(Server.id == get_user_id(data.server_id)))
    server = result.scalar_one_or_none()
    if not server:
        raise HTTPException(404, "Server not found")
    if server.status == ServerStatus.inactive:
        raise HTTPException(400, "Server is inactive")
    if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
        raise HTTPException(403, "Access denied")
    
    req = Request(requester_id=get_user_id(payload["user_id"]), server_id=get_user_id(data.server_id),
                  access_level=AccessLevel(data.access_level), duration_minutes=data.duration_minutes,
                  description=data.description)
    db.add(req)
    await db.commit()
    await log_audit(db, "request_created", payload["username"], str(req.id),
                    f"Requested {data.access_level} access to {server.name} for {data.duration_minutes}min",
                    str(server.company_id) if server.company_id else None)
    await notify_admins_and_superusers(db, str(server.company_id) if server.company_id else "",
                                       "new_request",
                                       f"New access request from {payload['username']} for {server.name}",
                                       "/approvals")
    return {"id": str(req.id), "status": req.status.value}

@app.post("/api/requests/{request_id}/approve")
async def approve_request(request_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
    req = result.scalar_one_or_none()
    if not req or req.status != RequestStatus.pending:
        raise HTTPException(400, "Request not found or not pending")
    req.status = RequestStatus.approved
    req.approved_at = datetime.utcnow()
    req.approved_by = get_user_id(payload["user_id"])
    req.expires_at = datetime.utcnow() + timedelta(minutes=req.duration_minutes)
    await db.commit()
    await log_audit(db, "request_approved", payload["username"], request_id,
                    f"Approved access request for {req.duration_minutes}min")
    # Notify requester
    await notify_user(db, str(req.requester_id), "request_approved",
                      "Your access request has been approved", "/my-requests")
    # Try agent provision - call VM2's tenant agent
    server = await db.execute(select(Server).where(Server.id == req.server_id))
    server = server.scalar_one_or_none()
    if server:
        company = await db.execute(select(Company).where(Company.id == server.company_id))
        company = company.scalar_one_or_none()
        api_key = company.api_key if company else None
        agent_port = req.agent_port or 8800
        jit_username = "jit-" + uuid.uuid4().hex[:8]
        provision_body = {
            "request_id": str(req.id),
            "username_to_create": jit_username,
            "privilege": req.access_level.value,
            "duration_minutes": req.duration_minutes,
            "expires_at": req.expires_at.isoformat() if req.expires_at else (datetime.utcnow() + timedelta(minutes=req.duration_minutes)).isoformat() + 'Z'
        }
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(
                    f"http://{server.ip}:{agent_port}/agent/provision",
                    json=provision_body,
                    headers={"X-API-Key": api_key or AGENT_API_KEY}
                )
                if resp.status_code == 200:
                    prov = resp.json()
                    req.provisioned_username = prov.get("username", jit_username)
                    req.provisioned_at = datetime.utcnow()
                    req.ssh_private_key = prov.get("ssh_private_key")
                    await db.commit()
                    await log_audit(db, "agent_provisioned", payload["username"], str(req.id),
                                    f"Provisioned {jit_username} on {server.name}")
        except:
            pass
    return {"message": "Request approved"}

@app.post("/api/requests/{request_id}/reject")
async def reject_request(request_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
    req = result.scalar_one_or_none()
    if not req or req.status != RequestStatus.pending:
        raise HTTPException(400, "Request not found or not pending")
    req.status = RequestStatus.rejected
    req.approved_at = datetime.utcnow()
    req.approved_by = get_user_id(payload["user_id"])
    await db.commit()
    await log_audit(db, "request_rejected", payload["username"], request_id, "Rejected access request")
    await notify_user(db, str(req.requester_id), "request_rejected",
                      "Your access request has been rejected", "/my-requests")
    return {"message": "Request rejected"}

@app.post("/api/requests/{request_id}/cancel")
async def cancel_request(request_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    if req.status not in (RequestStatus.pending, RequestStatus.approved):
        raise HTTPException(400, "Request cannot be cancelled")
    if str(req.requester_id) != payload["user_id"]:
        raise HTTPException(403, "Not your request")
    if req.provisioned_username:
        await agent_revoke(db, req)
    req.status = RequestStatus.cancelled
    await db.commit()
    return {"message": "Request cancelled"}

@app.delete("/api/requests/{request_id}")
async def delete_request(request_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
    req = result.scalar_one_or_none()
    if not req:
        raise HTTPException(404, "Request not found")
    if payload["role"] == "user" and str(req.requester_id) != payload["user_id"]:
        raise HTTPException(403, "Forbidden")
    if payload["role"] == "admin" and str(req.requester_id) != payload["user_id"]:
        raise HTTPException(403, "Admins can only delete their own requests")
    if req.provisioned_username:
        await agent_revoke(db, req, delete_req=True)
    await db.delete(req)
    await db.commit()
    await log_audit(db, "request_deleted", payload["username"], request_id, "Deleted access request")
    return {"message": "Request deleted"}

@app.get("/api/requests/check-active/{server_id}")
async def check_active_request(server_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Request).where(
            Request.requester_id == get_user_id(payload["user_id"]),
            Request.server_id == get_user_id(server_id),
            Request.status == RequestStatus.approved,
            Request.expires_at > datetime.utcnow()
        ).order_by(Request.requested_at.desc())
    )
    req = result.scalar_one_or_none()
    return {"hasActive": req is not None, "request": {"id": str(req.id)} if req else None}

# ─── Sessions ─────────────────────────────────────────────────────────────────

@app.get("/api/sessions")
async def list_sessions(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    query = select(
        Session, User.full_name, User.username, Server.name, Server.ip, Company.name
    ).join(User, Session.user_id == User.id).join(Server, Session.server_id == Server.id).join(Company, Server.company_id == Company.id)
    if payload["role"] == "user":
        query = query.where(Session.user_id == get_user_id(payload["user_id"]))
    elif payload["role"] == "admin":
        query = query.where(Server.company_id == get_user_id(payload["company_id"]))
    result = await db.execute(query.order_by(Session.started_at.desc()))
    return [
        {"id": str(s.Session.id), "request_id": str(s.Session.request_id) if s.Session.request_id else None,
         "user_id": str(s.Session.user_id), "user_name": s.full_name, "user_username": s.username,
         "server_id": str(s.Session.server_id), "server_name": s.name, "server_ip": s.ip,
          "company_name": s[4], "started_at": s.Session.started_at.isoformat() + 'Z',
         "ended_at": s.Session.ended_at.isoformat() + 'Z' if s.Session.ended_at else None,
         "status": s.Session.status}
        for s in result
    ]

@app.get("/api/sessions/{session_id}")
async def get_session(session_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Session, User.full_name, User.username, Server.name, Server.ip, Server.port, Company.name, Request.access_level)
        .join(User, Session.user_id == User.id).join(Server, Session.server_id == Server.id)
        .join(Company, Server.company_id == Company.id)
        .outerjoin(Request, Session.request_id == Request.id)
        .where(Session.id == get_user_id(session_id))
    )
    s = result.first()
    if not s:
        raise HTTPException(404, "Session not found")
    return {"id": str(s.Session.id), "request_id": str(s.Session.request_id) if s.Session.request_id else None,
            "user_id": str(s.Session.user_id), "user_name": s.full_name, "user_username": s.username,
            "server_id": str(s.Session.server_id), "server_name": s.name, "server_ip": s.ip, "server_port": s.port,
            "company_name": s[6], "access_level": s.access_level.value if s.access_level else None,
            "started_at": str(s.Session.started_at), "ended_at": str(s.Session.ended_at) if s.Session.ended_at else None,
            "status": s.Session.status}

@app.get("/api/sessions/{session_id}/recording")
async def get_session_recording(session_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(
        select(Session, Server.company_id).join(Server, Session.server_id == Server.id)
        .where(Session.id == get_user_id(session_id))
    )
    row = result.first()
    if not row:
        raise HTTPException(404, "Session not found")
    session, company_id = row
    if payload["role"] != "superuser" and str(company_id) != payload.get("company_id"):
        raise HTTPException(403, "Access denied")
    return {"recording": session.recording_data or []}

@app.post("/api/sessions/{session_id}/terminate")
async def terminate_session(session_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(Session).where(Session.id == get_user_id(session_id)))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(404, "Session not found")
    if payload["role"] == "user" and str(session.user_id) != payload["user_id"]:
        raise HTTPException(403, "Access denied")
    session.status = "terminated"
    session.ended_at = datetime.utcnow()
    await db.commit()
    if session.request_id:
        req = await db.execute(select(Request).where(Request.id == session.request_id))
        req = req.scalar_one_or_none()
        if req:
            req.status = RequestStatus.expired
            await db.commit()
    await log_audit(db, "session_terminated", payload["username"], session_id,
                    "Session terminated", security_status="warning")
    return {"message": "Session terminated"}

# ─── Audit Logs ───────────────────────────────────────────────────────────────

@app.get("/api/audit-logs")
async def list_audit_logs(token: str = Query(None), event_type: str = None, performed_by: str = None,
                          security_status: str = None, date_from: str = None, date_to: str = None,
                          company_id: str = None, limit: int = 50, offset: int = 0, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    query = select(AuditLog)
    if payload["role"] != "superuser":
        query = query.where(AuditLog.company_id == get_user_id(payload["company_id"]))
    elif company_id:
        query = query.where(AuditLog.company_id == get_user_id(company_id))
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if performed_by:
        query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
    if security_status:
        query = query.where(AuditLog.security_status == SecurityStatus(security_status))
    if date_from:
        query = query.where(AuditLog.timestamp >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(AuditLog.timestamp <= datetime.fromisoformat(date_to))
    
    count_query = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_query)).scalar()
    
    result = await db.execute(query.order_by(AuditLog.timestamp.desc()).offset(offset).limit(limit))
    logs = [
        {"id": str(l.id), "timestamp": str(l.timestamp), "event_type": l.event_type,
         "performed_by": l.performed_by, "target": l.target, "action_detail": l.action_detail,
         "company_id": str(l.company_id) if l.company_id else None,
         "security_status": l.security_status.value, "source": l.source}
        for l in result.scalars()
    ]
    return {"rows": logs, "total": total}

@app.get("/api/audit-logs/export")
async def export_audit_logs(token: str = Query(None), event_type: str = None, performed_by: str = None,
                            security_status: str = None, date_from: str = None, date_to: str = None,
                            company_id: str = None, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    query = select(AuditLog)
    if payload["role"] != "superuser":
        query = query.where(AuditLog.company_id == get_user_id(payload["company_id"]))
    elif company_id:
        query = query.where(AuditLog.company_id == get_user_id(company_id))
    if event_type:
        query = query.where(AuditLog.event_type == event_type)
    if performed_by:
        query = query.where(AuditLog.performed_by.ilike(f"%{performed_by}%"))
    if security_status:
        query = query.where(AuditLog.security_status == SecurityStatus(security_status))
    if date_from:
        query = query.where(AuditLog.timestamp >= datetime.fromisoformat(date_from))
    if date_to:
        query = query.where(AuditLog.timestamp <= datetime.fromisoformat(date_to))
    result = await db.execute(query.order_by(AuditLog.timestamp.desc()).limit(10000))
    
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Timestamp", "Event Type", "Performed By", "Target", "Action Detail", "Security Status"])
    for l in result.scalars():
        writer.writerow([str(l.timestamp), l.event_type, l.performed_by, l.target or "",
                        (l.action_detail or "").replace('"', '""'), l.security_status.value])
    output.seek(0)
    return StreamingResponse(iter([output.getvalue()]), media_type="text/csv",
                             headers={"Content-Disposition": f"attachment; filename=audit-log-{int(datetime.utcnow().timestamp())}.csv"})

# ─── Billing ──────────────────────────────────────────────────────────────────

@app.get("/api/billing/my")
async def get_my_billing(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(BillingAccount).where(BillingAccount.admin_user_id == get_user_id(payload["user_id"])))
    acc = result.scalar_one_or_none()
    if not acc:
        acc = BillingAccount(admin_user_id=get_user_id(payload["user_id"]), balance=100, price_per_user=5)
        db.add(acc)
        await db.commit()
    return {"id": str(acc.id), "admin_user_id": str(acc.admin_user_id), "balance": acc.balance, "price_per_user": acc.price_per_user}

@app.get("/api/billing/transactions")
async def get_billing_transactions(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(select(BillingAccount).where(BillingAccount.admin_user_id == get_user_id(payload["user_id"])))
    acc = result.scalar_one_or_none()
    if not acc:
        return []
    txns = await db.execute(
        select(BillingTransaction).where(BillingTransaction.billing_account_id == acc.id)
        .order_by(BillingTransaction.created_at.desc())
    )
    return [{"id": str(t.id), "amount": t.amount, "reason": t.reason, "created_at": str(t.created_at)} for t in txns.scalars()]

@app.post("/api/billing/add-funds")
async def add_funds(data: AddFundsRequest, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] == "user":
        raise HTTPException(403, "Forbidden")
    if data.amount <= 0:
        raise HTTPException(400, "Invalid amount")
    result = await db.execute(select(BillingAccount).where(BillingAccount.admin_user_id == get_user_id(payload["user_id"])))
    acc = result.scalar_one_or_none()
    if not acc:
        acc = BillingAccount(admin_user_id=get_user_id(payload["user_id"]), balance=100, price_per_user=5)
        db.add(acc)
    acc.balance += data.amount
    txn = BillingTransaction(billing_account_id=acc.id, amount=data.amount, reason=data.reason or "Manual deposit")
    db.add(txn)
    await db.commit()
    await log_audit(db, "billing_funds_added", payload["username"], str(acc.id),
                    f"Added ${data.amount} to billing account")
    return {"id": str(acc.id), "balance": acc.balance, "price_per_user": acc.price_per_user}

@app.get("/api/billing/all")
async def get_all_billing(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload or payload["role"] != "superuser":
        raise HTTPException(403, "Forbidden")
    result = await db.execute(
        select(BillingAccount, User.full_name, User.username, Company.name)
        .join(User, BillingAccount.admin_user_id == User.id)
        .outerjoin(Company, User.company_id == Company.id)
    )
    return [{"id": str(acc.id), "admin_name": fn, "admin_username": un, "company_name": cn,
             "balance": acc.balance, "price_per_user": acc.price_per_user}
            for acc, fn, un, cn in result]

# ─── Notifications ────────────────────────────────────────────────────────────

@app.get("/api/notifications")
async def list_notifications(token: str = Query(None), limit: int = 50, db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(Notification).where(Notification.user_id == get_user_id(payload["user_id"]))
        .order_by(Notification.created_at.desc()).limit(limit)
    )
    return [{"id": str(n.id), "type": n.type, "message": n.message, "link": n.link,
             "read": n.read, "created_at": str(n.created_at)} for n in result.scalars()]

@app.get("/api/notifications/unread-count")
async def unread_count(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(
        select(func.count(Notification.id)).where(
            Notification.user_id == get_user_id(payload["user_id"]), Notification.read == False
        )
    )
    return {"count": result.scalar()}

@app.patch("/api/notifications/{notification_id}/read")
async def mark_read(notification_id: str, token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    result = await db.execute(select(Notification).where(Notification.id == get_user_id(notification_id)))
    n = result.scalar_one_or_none()
    if n:
        n.read = True
        await db.commit()
    return {"message": "Marked as read"}

@app.post("/api/notifications/read-all")
async def mark_all_read(token: str = Query(None), db: AsyncSession = Depends(get_db)):
    payload = get_current_user_from_token(token=token)
    if not payload:
        raise HTTPException(401, "Not authenticated")
    await db.execute(
        text("UPDATE notifications SET read = true WHERE user_id = :uid AND read = false"),
        {"uid": get_user_id(payload["user_id"])}
    )
    await db.commit()
    return {"message": "All marked as read"}

# ─── WebSocket (Terminal Session) ─────────────────────────────────────────────

@app.websocket("/ws/terminal")
async def terminal_websocket(websocket: WebSocket):
    await websocket.accept()
    token = websocket.query_params.get("token")
    payload = verify_token(token) if token else None
    if not payload:
        await websocket.send_json({"type": "error", "data": "Not authenticated"})
        await websocket.close()
        return

    user_id = payload["user_id"]
    active_connections[user_id] = websocket

    try:
        data = await websocket.receive_json()
        action = data.get("action")

        if action == "join_session":
            request_id = data.get("requestId")
            server_id = data.get("serverId")
            
            async with async_session() as db:
                server_result = await db.execute(select(Server).where(Server.id == get_user_id(server_id)))
                server = server_result.scalar_one_or_none()
                if not server:
                    await websocket.send_json({"type": "error", "data": "Server not found"})
                    return

                if payload["role"] != "superuser" and str(server.company_id) != payload.get("company_id"):
                    await websocket.send_json({"type": "error", "data": "Access denied"})
                    return

                ssh_username = "pam-service"
                ssh_key = "/home/administrator/.ssh/id_rsa"
                if request_id:
                    req_result = await db.execute(select(Request).where(Request.id == get_user_id(request_id)))
                    req = req_result.scalar_one_or_none()
                    if req and req.provisioned_username and req.ssh_private_key:
                        ssh_username = req.provisioned_username
                        ssh_key = req.ssh_private_key

                db_sess = Session(request_id=get_user_id(request_id) if request_id else None,
                                  user_id=get_user_id(user_id), server_id=get_user_id(server_id),
                                  recording_data=[], status="active")
                db.add(db_sess)
                await db.commit()
                session_id = str(db_sess.id)

                await websocket.send_json({"type": "session_created", "data": {"sessionId": session_id}})

            recording = []

            try:
                import asyncssh
                key_path = None
                tmp_key = None
                if ssh_key and ssh_key.startswith("-----"):
                    tmp_key = tempfile.NamedTemporaryFile(mode="w", suffix=".key", delete=False)
                    tmp_key.write(ssh_key)
                    tmp_key.close()
                    os.chmod(tmp_key.name, 0o600)
                    key_path = tmp_key.name
                elif ssh_key and os.path.exists(ssh_key):
                    key_path = ssh_key
                if key_path:
                    conn = await asyncio.wait_for(
                        asyncssh.connect(server.ip, port=server.port, username=ssh_username,
                                         client_keys=[key_path], known_hosts=None), timeout=10
                    )
                else:
                    conn = await asyncio.wait_for(
                        asyncssh.connect(server.ip, port=server.port, username=ssh_username,
                                         known_hosts=None), timeout=10
                    )

                await websocket.send_json({"type": "ssh_ready"})

                async def shell_handler():
                    nonlocal conn
                    async with conn:
                        process = await conn.create_process()
                        stdin_w = process.stdin
                        stdout_r = process.stdout
                        stderr_r = process.stderr
                        
                        async def read_stdout():
                            async for data in stdout_r:
                                text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
                                masked = mask_ssh_keys(text)
                                recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "output", "data": masked})
                                findings = detect_suspicious_activity(text)
                                for f in findings:
                                    async with async_session() as db3:
                                        await log_audit(db3, "suspicious_output", payload["username"],
                                                        session_id,
                                                        f"Suspicious terminal output: {f['description']}",
                                                        str(server.company_id) if server.company_id else None,
                                                        f['severity'])
                                await websocket.send_json({"type": "terminal_output", "data": masked})

                        async def read_stderr():
                            async for data in stderr_r:
                                if data:
                                    text = data.decode("utf-8", errors="replace") if isinstance(data, bytes) else data
                                    masked = mask_ssh_keys(text)
                                    recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "output", "data": masked})
                                    findings = detect_suspicious_activity(text)
                                    for f in findings:
                                        async with async_session() as db3:
                                            await log_audit(db3, "suspicious_output", payload["username"],
                                                            session_id,
                                                            f"Suspicious terminal output (stderr): {f['description']}",
                                                            str(server.company_id) if server.company_id else None,
                                                            f['severity'])
                                    await websocket.send_json({"type": "terminal_output", "data": masked})

                        task_stdout = asyncio.create_task(read_stdout())
                        task_stderr = asyncio.create_task(read_stderr())

                        while True:
                            try:
                                msg = await asyncio.wait_for(websocket.receive_json(), timeout=1)
                            except asyncio.TimeoutError:
                                if request_id:
                                    async with async_session() as db2:
                                        req_result = await db2.execute(
                                            select(Request).where(Request.id == get_user_id(request_id))
                                        )
                                        req = req_result.scalar_one_or_none()
                                        if req and req.expires_at and req.expires_at <= datetime.utcnow():
                                            stdin_w.write("\n*** Session expired ***\n")
                                            await stdin_w.drain()
                                            break
                                continue
                            except Exception:
                                break

                            if msg.get("type") == "terminal_input":
                                stdin_w.write(msg["data"])
                                await stdin_w.drain()
                                recording.append({"timestamp": datetime.utcnow().timestamp(), "event": "input", "data": msg["data"]})
                                findings = detect_suspicious_activity(msg["data"])
                                for f in findings:
                                    async with async_session() as db3:
                                        await log_audit(db3, "suspicious_command", payload["username"],
                                                        session_id,
                                                        f"Suspicious command: {f['description']}",
                                                        str(server.company_id) if server.company_id else None,
                                                        f['severity'])
                            elif msg.get("type") == "terminate_session":
                                break
                            elif msg.get("type") == "close_session":
                                break

                        task_stdout.cancel()
                        task_stderr.cancel()

                await shell_handler()

                # Save recording
                async with async_session() as db:
                    sess_result = await db.execute(select(Session).where(Session.id == get_user_id(session_id)))
                    sess = sess_result.scalar_one_or_none()
                    if sess:
                        sess.recording_data = recording
                        sess.status = "ended"
                        sess.ended_at = datetime.utcnow()
                        await db.commit()

                await websocket.send_json({"type": "session_ended", "data": {"reason": "disconnected"}})

            except Exception as e:
                await websocket.send_json({"type": "error", "data": f"SSH connection failed: {str(e)}"})
            finally:
                if tmp_key:
                    try:
                        os.unlink(tmp_key.name)
                    except:
                        pass

        elif action == "reconnect_session":
            session_id = data.get("sessionId")
            async with async_session() as db:
                sess_result = await db.execute(select(Session).where(Session.id == get_user_id(session_id)))
                sess = sess_result.scalar_one_or_none()
                if sess and sess.status == "active":
                    await websocket.send_json({"type": "session_reconnected", "data": {"sessionId": session_id}})
                    for entry in (sess.recording_data or []):
                        if entry.get("event") == "output":
                            await websocket.send_json({"type": "terminal_output", "data": entry["data"]})
                else:
                    await websocket.send_json({"type": "error", "data": "No active session found"})

    except WebSocketDisconnect:
        pass
    except Exception as e:
        try:
            await websocket.send_json({"type": "error", "data": str(e)})
        except:
            pass
    finally:
        active_connections.pop(user_id, None)

# ─── Frontend (embedded SPA) ─────────────────────────────────────────────────

from frontend_html import FRONTEND_HTML

@app.get("/")
async def serve_frontend():
    return HTMLResponse(FRONTEND_HTML)

@app.get("/index.html")
async def serve_frontend_index():
    return HTMLResponse(FRONTEND_HTML)

# ─── Health ───────────────────────────────────────────────────────────────────

@app.get("/api/health")
async def health():
    return {"status": "ok", "timestamp": datetime.utcnow().isoformat() + 'Z'}

# ─── Periodic expiry check ────────────────────────────────────────────────────

async def expire_old_requests():
    while True:
        await asyncio.sleep(60)
        try:
            async with async_session() as db:
                now = datetime.utcnow()
                result = await db.execute(
                    select(Request).where(Request.status == RequestStatus.approved, Request.expires_at <= now)
                )
                for req in result.scalars():
                    req.status = RequestStatus.expired
                    await log_audit(db, "request_expired", "system", str(req.id), "Access request expired")
                    server = await db.execute(select(Server).where(Server.id == req.server_id))
                    server = server.scalar_one_or_none()
                    if server:
                        try:
                            async with httpx.AsyncClient(timeout=5) as client:
                                requester = await db.execute(select(User).where(User.id == req.requester_id))
                                requester = requester.scalar_one_or_none()
                                if requester:
                                    await client.post(f"http://{server.ip}:9100/agent/revoke", json={"user": requester.username},
                                                      headers={"X-API-Key": AGENT_API_KEY})
                        except:
                            pass
                await db.commit()
        except:
            pass

# The expire_old_requests task is started in lifespan

from fastapi.responses import FileResponse

@app.get("/api/download-project")
async def download_project():
    zip_path = os.path.join(os.path.dirname(__file__), "LAST_PAM_PROJECT.zip")
    if os.path.exists(zip_path):
        return FileResponse(zip_path, filename="LAST_PAM_PROJECT.zip", media_type="application/zip")
    return {"error": "File not found"}

@app.get("/api/download-report")
async def download_report():
    report_path = "/home/administrator/LAST_PAM_PROJECT/report.md"
    if os.path.exists(report_path):
        return FileResponse(report_path, filename="report.md", media_type="text/markdown")
    return {"error": "File not found"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=3001)
