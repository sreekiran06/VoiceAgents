"""Database seeding script — creates default admin and migrates seed client data.

Run at app startup or manually: python -m voice_call_agent.core.seed
"""

import asyncio
import logging

from sqlalchemy import select

from voice_call_agent.core.auth import hash_password
from voice_call_agent.core.config import settings
from voice_call_agent.core.database import async_session_factory, init_db
from voice_call_agent.models.db_models import (
    Admin,
    Business,
    BusinessConfig,
    BusinessHours,
    BusinessPhoneNumber,
    BusinessTool,
    DBClient,
    KnowledgeEntry,
)

logger = logging.getLogger(__name__)


async def seed_database() -> None:
    """Seed the database with default admin and sample data if empty."""
    await init_db()

    async with async_session_factory() as session:
        # Check if admin already exists
        result = await session.execute(select(Admin).limit(1))
        if result.scalar_one_or_none():
            logger.info("Database already seeded, skipping.")
            return

        logger.info("Seeding database with default data...")

        # 1. Create default admin
        admin = Admin(
            email=settings.admin_email,
            password_hash=hash_password(settings.admin_password),
            full_name="SK Admin",
            role="superadmin",
        )
        session.add(admin)

        # 2. Create sample clients
        client_infra = DBClient(
            id="cli-hyd-001",
            name="Sri Krishna Infra & Developers",
            contact_person="Ramesh Reddy",
            email="ramesh@srikrishnainfra.in",
            phone="+91 98490 12345",
            industry="Real Estate",
            plan="Growth",
            status="active",
            monthly_minutes_limit=2500,
            minutes_used=742,
        )
        session.add(client_infra)

        client_apollo = DBClient(
            id="cli-vja-002",
            name="Apollo Multispeciality Clinic",
            contact_person="Dr. Sunita Rao",
            email="appointments@apolloclinicvja.com",
            phone="+91 94401 55667",
            industry="Clinics & Healthcare",
            plan="Growth",
            status="active",
            monthly_minutes_limit=1500,
            minutes_used=520,
        )
        session.add(client_apollo)

        client_narayana = DBClient(
            id="cli-vzg-003",
            name="Narayana IIT & NEET Academy",
            contact_person="P. Venkatesh",
            email="admissions@narayanavzg.edu.in",
            phone="+91 98850 77889",
            industry="Coaching & EdTech",
            plan="Starter",
            status="active",
            monthly_minutes_limit=1000,
            minutes_used=310,
        )
        session.add(client_narayana)

        client_urbanfix = DBClient(
            id="cli-blr-004",
            name="UrbanFix Premium Home Services",
            contact_person="Arvind Sharma",
            email="ops@urbanfix.in",
            phone="+91 99800 22334",
            industry="Local Services",
            plan="Pro",
            status="active",
            monthly_minutes_limit=5000,
            minutes_used=1840,
            webhook_url="https://urbanfix.in/api/v1/voice-leads",
        )
        session.add(client_urbanfix)

        await session.flush()

        # 3. Create sample businesses with configs
        # --- Sri Krishna Infra: Gachibowli Office ---
        biz_gachi = Business(
            client_id="cli-hyd-001",
            name="Sri Krishna Infra - Gachibowli",
            industry="Real Estate",
            description="Premium 3BHK apartments in Gachibowli, Hyderabad",
        )
        session.add(biz_gachi)
        await session.flush()

        session.add(BusinessConfig(
            business_id=biz_gachi.id,
            agent_name="Kiran",
            greeting_text="నమస్కారం! శ్రీ కృష్ణ ఇన్ఫ్రా కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?",
            languages="te-IN,en-IN,hi-IN",
        ))
        session.add(BusinessPhoneNumber(
            business_id=biz_gachi.id,
            phone_number="04041892488",
            provider="exotel",
            label="Main Line",
        ))

        # Knowledge entries for Sri Krishna Infra
        for q, a in [
            ("What projects are available?", "We have luxury 3BHK apartments in Gachibowli starting from 1.2 Cr and premium plots in Kokapet from 80 lakhs."),
            ("What is the price range?", "3BHK apartments: 1.2 Cr to 1.8 Cr. Plots: 80 lakhs to 2 Cr depending on size and location."),
            ("Is there a site visit available?", "Yes! We offer free site visits every day from 10 AM to 6 PM. We can also arrange a personal tour at your convenience."),
            ("What amenities are included?", "Swimming pool, gymnasium, children's play area, 24/7 security, power backup, landscaped gardens, and club house."),
        ]:
            session.add(KnowledgeEntry(
                business_id=biz_gachi.id,
                category="real_estate",
                question=q,
                answer=a,
            ))

        for tool_name in ["qualify_lead", "book_appointment", "transfer_to_human"]:
            session.add(BusinessTool(business_id=biz_gachi.id, tool_name=tool_name, enabled=True))

        # --- Apollo Clinic ---
        biz_apollo = Business(
            client_id="cli-vja-002",
            name="Apollo Clinic - Vijayawada",
            industry="Clinics & Healthcare",
            description="Multi-speciality clinic in Vijayawada",
        )
        session.add(biz_apollo)
        await session.flush()

        session.add(BusinessConfig(
            business_id=biz_apollo.id,
            agent_name="Priya",
            greeting_text="నమస్కారం! Apollo Clinic కి కాల్ చేసినందుకు ధన్యవాదాలు. మీకు ఎలా సహాయం చేయగలను?",
            languages="te-IN,en-IN,hi-IN",
        ))
        session.add(BusinessPhoneNumber(
            business_id=biz_apollo.id,
            phone_number="08662549988",
            provider="exotel",
            label="Clinic Line",
        ))

        for q, a in [
            ("What specialists are available?", "We have cardiologists, dermatologists, orthopedists, pediatricians, and general physicians."),
            ("What are the clinic timings?", "Monday to Saturday: 9 AM to 8 PM. Sunday: 10 AM to 2 PM for emergencies."),
            ("Do you accept insurance?", "Yes, we accept most major health insurance providers including Star Health, ICICI Lombard, and HDFC Ergo."),
        ]:
            session.add(KnowledgeEntry(
                business_id=biz_apollo.id,
                category="healthcare",
                question=q,
                answer=a,
            ))

        for tool_name in ["book_appointment", "transfer_to_human"]:
            session.add(BusinessTool(business_id=biz_apollo.id, tool_name=tool_name, enabled=True))

        # --- Narayana Academy ---
        biz_narayana = Business(
            client_id="cli-vzg-003",
            name="Narayana Academy - Vizag",
            industry="Coaching & EdTech",
            description="IIT/NEET coaching center in Visakhapatnam",
        )
        session.add(biz_narayana)
        await session.flush()

        session.add(BusinessConfig(
            business_id=biz_narayana.id,
            agent_name="Ravi",
            greeting_text="Hello! Welcome to Narayana Academy. How can I help you with admissions?",
            languages="en-IN,te-IN,hi-IN",
        ))
        session.add(BusinessPhoneNumber(
            business_id=biz_narayana.id,
            phone_number="08912783344",
            provider="exotel",
            label="Admissions",
        ))

        for tool_name in ["qualify_lead", "book_appointment", "transfer_to_human"]:
            session.add(BusinessTool(business_id=biz_narayana.id, tool_name=tool_name, enabled=True))

        # --- UrbanFix ---
        biz_urbanfix = Business(
            client_id="cli-blr-004",
            name="UrbanFix - Bangalore",
            industry="Local Services",
            description="Premium home services in Bangalore",
        )
        session.add(biz_urbanfix)
        await session.flush()

        session.add(BusinessConfig(
            business_id=biz_urbanfix.id,
            agent_name="Arvind",
            greeting_text="Hello! UrbanFix Premium Services here. How can I help you today?",
            languages="en-IN,hi-IN",
            voice_te_in="kavitha",
            voice_en_in="ishita",
            voice_hi_in="ritu",
        ))
        session.add(BusinessPhoneNumber(
            business_id=biz_urbanfix.id,
            phone_number="08049127700",
            provider="exotel",
            label="Service Line",
        ))

        for tool_name in ["qualify_lead", "book_appointment", "transfer_to_human"]:
            session.add(BusinessTool(business_id=biz_urbanfix.id, tool_name=tool_name, enabled=True))

        await session.commit()
        logger.info("Database seeded successfully with %d clients and %d businesses.", 4, 4)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(seed_database())
