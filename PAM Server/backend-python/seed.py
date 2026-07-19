import asyncio
import uuid
from datetime import datetime
from sqlalchemy import select
from database import async_session, init_db, Company, User, Server, Agent, AgentStatus, BillingAccount, Notification, AuditLog
from auth_utils import hash_password

async def seed():
    await init_db()
    async with async_session() as db:
        existing = await db.execute(select(User).where(User.role == 'superuser'))
        if existing.scalar_one_or_none():
            print("Superuser already exists, skipping seed")
            return

        # Superuser
        su = User(
            full_name="Nihat Kazimzada",
            username="nihat.kazimzada@example.com",
            password_hash=hash_password("nihat123"),
            role="superuser",
            company_id=None,
            status="active"
        )
        db.add(su)
        await db.flush()
        print(f"Created superuser: {su.username}")

        # Company 1: Kapital Tech
        kt = Company(
            name="Kapital Tech",
            tenant_id="kapital-tech",
            domain="kapitaltech.com",
            industry="fintech",
            contact_email="info@kapitaltech.com",
            contact_phone="+994-12-555-0100",
            billing_email="billing@kapitaltech.com",
            api_key="pam_kapital_" + uuid.uuid4().hex[:12]
        )
        db.add(kt)
        await db.flush()
        print(f"Created company: {kt.name}")

        # Company 2: Acme Corp
        ac = Company(
            name="Acme Corp",
            tenant_id="acme-corp",
            domain="acmecorp.com",
            industry="enterprise",
            contact_email="info@acmecorp.com",
            contact_phone="+1-555-0100",
            billing_email="billing@acmecorp.com",
            api_key="pam_acme_" + uuid.uuid4().hex[:12]
        )
        db.add(ac)
        await db.flush()
        print(f"Created company: {ac.name}")

        # Admin for Kapital Tech
        aysel = User(
            full_name="Aysel Mammadova",
            username="aysel.mammadova@example.com",
            password_hash=hash_password("aysel123"),
            role="admin",
            company_id=kt.id,
            status="active"
        )
        db.add(aysel)
        await db.flush()
        print(f"Created admin: {aysel.username}")

        # Admin for Acme Corp
        elnur = User(
            full_name="Elnur Nuriyev",
            username="elnur.nuriyev@example.com",
            password_hash=hash_password("elnur123"),
            role="admin",
            company_id=ac.id,
            status="active"
        )
        db.add(elnur)
        await db.flush()
        print(f"Created admin: {elnur.username}")

        # Billing accounts
        db.add(BillingAccount(admin_user_id=aysel.id, balance=100, price_per_user=5))
        db.add(BillingAccount(admin_user_id=elnur.id, balance=100, price_per_user=5))
        print("Created billing accounts ($100 each)")

        # Test users
        user_hash = hash_password("user123")
        for u in [
            ("Rashad Guliyev", "rashad.guliyev@example.com", kt.id),
            ("Leyla Hasanli", "leyla.hasanli@example.com", ac.id),
            ("Tural Aliyev", "tural.aliyev@example.com", kt.id),
            ("Gunay Ibrahimova", "gunay.ibrahimova@example.com", ac.id),
        ]:
            db.add(User(full_name=u[0], username=u[1], password_hash=user_hash, role="user", company_id=u[2], status="active"))
        print("Created test users")

        # Servers
        db.add(Server(name="linux-tenant-kapital", ip="10.0.2.21", port=22,
                      allowed_connection_types=["ssh"], os="Ubuntu Server 22.04 LTS",
                      company_id=kt.id, status="active"))
        db.add(Server(name="windows-tenant-acme", ip="VM3_IP_PLACEHOLDER", port=22,
                      allowed_connection_types=["ssh"], os="Windows Server 2022",
                      company_id=ac.id, status="active"))
        print("Created servers")

        # Agent for Kapital Tech server
        agent = Agent(
            hostname="linux-tenant-kapital", ip="10.0.2.21",
            os_version="Ubuntu 22.04.5 LTS",
            tenant_company_id="kapital-tech",
            agent_version="1.0.0",
            api_key=kt.api_key,
            status=AgentStatus.active,
            last_seen=datetime.utcnow()
        )
        db.add(agent)
        print("Created agent for Kapital Tech")

        # Welcome notifications
        db.add(Notification(user_id=su.id, type="system", message="PAM Server has been deployed successfully. Welcome!"))
        db.add(Notification(user_id=aysel.id, type="system", message="Welcome to PAM Console, Aysel. Your billing account has been credited with $100."))
        db.add(Notification(user_id=elnur.id, type="system", message="Welcome to PAM Console, Elnur. Your billing account has been credited with $100."))

        # Audit log
        db.add(AuditLog(event_type="system_init", performed_by="system", target="pam-server",
                        action_detail="PAM Server initialized with seed data"))

        await db.commit()

    print("\nSeed completed successfully!")
    print("\nDefault logins:")
    print("  Superuser: nihat.kazimzada@example.com / nihat123")
    print("  Admin (Kapital Tech): aysel.mammadova@example.com / aysel123")
    print("  Admin (Acme Corp): elnur.nuriyev@example.com / elnur123")
    print("  Users: rashad.guliyev@example.com / user123")
    print("         leyla.hasanli@example.com / user123")
    print("         tural.aliyev@example.com / user123")
    print("         gunay.ibrahimova@example.com / user123")

if __name__ == "__main__":
    asyncio.run(seed())
