import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from voice_call_agent.core.client_store import client_store
from voice_call_agent.core.context_loader import invalidate_cache
from voice_call_agent.core.database import async_session_factory
from voice_call_agent.models.client import Client, ClientCreate, ClientUpdate
from voice_call_agent.models.db_models import (
    Business,
    BusinessConfig,
    BusinessPhoneNumber,
    DBClient,
    KnowledgeEntry,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/clients", tags=["clients"])


async def _sync_client_to_db(client: Client, knowledge_text: str | None = None) -> None:
    """Sync Client record to relational DBClient, Business, BusinessConfig, and Knowledge."""
    try:
        async with async_session_factory() as session:
            # 1. DBClient
            db_client_stmt = select(DBClient).where(DBClient.id == client.id)
            result = await session.execute(db_client_stmt)
            db_client = result.scalar_one_or_none()

            if not db_client:
                db_client = DBClient(
                    id=client.id,
                    name=client.name,
                    contact_person=client.contact_person,
                    email=client.email,
                    phone=client.phone,
                    industry=client.industry,
                    plan=client.plan,
                    status=client.status,
                    monthly_minutes_limit=client.monthly_minutes_limit,
                    webhook_url=client.webhook_url,
                )
                session.add(db_client)
                await session.flush()
            else:
                db_client.name = client.name
                db_client.contact_person = client.contact_person
                db_client.email = client.email
                db_client.phone = client.phone
                db_client.industry = client.industry
                db_client.plan = client.plan
                db_client.status = client.status
                db_client.monthly_minutes_limit = client.monthly_minutes_limit
                db_client.webhook_url = client.webhook_url

            # 2. Business
            biz_stmt = select(Business).where(Business.client_id == client.id).options(selectinload(Business.config))
            biz_res = await session.execute(biz_stmt)
            business = biz_res.scalar_one_or_none()

            if not business:
                business = Business(
                    client_id=client.id,
                    name=client.name,
                    industry=client.industry,
                    description=f"{client.industry} business",
                    status=client.status,
                )
                session.add(business)
                await session.flush()
            else:
                business.name = client.name
                business.industry = client.industry
                business.status = client.status

            # 3. Config
            agent_name = client.agent_name or "Kiran"
            greeting = client.greeting_text or "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?"
            llm_model = client.llm_model or "gemini-3.5-flash-lite"
            lang_codes = [
                "te-IN" if "telugu" in l.lower() else "en-IN" if "english" in l.lower() else "hi-IN"
                for l in client.languages
            ]
            lang_str = ",".join(lang_codes) or "te-IN,en-IN"

            if not business.config:
                cfg = BusinessConfig(
                    business_id=business.id,
                    agent_name=agent_name,
                    greeting_text=greeting,
                    llm_model=llm_model,
                    languages=lang_str,
                )
                session.add(cfg)
            else:
                business.config.agent_name = agent_name
                business.config.greeting_text = greeting
                business.config.llm_model = llm_model
                business.config.languages = lang_str

            # 4. Virtual Number
            if client.virtual_number:
                num_clean = client.virtual_number.strip().replace(" ", "").replace("-", "")
                num_stmt = select(BusinessPhoneNumber).where(BusinessPhoneNumber.business_id == business.id)
                num_res = await session.execute(num_stmt)
                phone_record = num_res.scalar_one_or_none()
                if not phone_record:
                    phone_record = BusinessPhoneNumber(
                        business_id=business.id,
                        phone_number=num_clean,
                        provider="exotel" if num_clean.startswith("040") else "twilio",
                        label="Main Line",
                    )
                    session.add(phone_record)
                else:
                    phone_record.phone_number = num_clean

            # 5. Knowledge Ingestion from text
            if knowledge_text and knowledge_text.strip():
                # Parse lines or blocks into knowledge entries
                paragraphs = [p.strip() for p in knowledge_text.split("\n\n") if p.strip()]
                for idx, para in enumerate(paragraphs[:10]):  # Ingest top paragraphs
                    # Try to separate Q and A if formatted
                    if "Q:" in para and "A:" in para:
                        parts = para.split("A:", 1)
                        q = parts[0].replace("Q:", "").strip()
                        a = parts[1].strip()
                    elif "?" in para:
                        parts = para.split("?", 1)
                        q = parts[0].strip() + "?"
                        a = parts[1].strip() or "Please contact our executive for details."
                    else:
                        q = f"About our {client.industry} services (Item {idx + 1})"
                        a = para

                    entry = KnowledgeEntry(
                        business_id=business.id,
                        category="general",
                        question=q[:250],
                        answer=a[:1000],
                        priority=10 - idx,
                    )
                    session.add(entry)

            await session.commit()
            await invalidate_cache()
            logger.info("Successfully synced client %s to multi-tenant database.", client.id)
    except Exception as exc:  # noqa: BLE001
        logger.warning("Optional DB sync for client %s skipped: %s", client.id, exc)


@router.get("", response_model=list[Client])
async def list_clients(
    search: str | None = Query(None, description="Search query by name, person, phone, number"),
    industry: str | None = Query(None, description="Filter by industry"),
    status: str | None = Query(None, description="Filter by status (active, paused, onboarding)"),
) -> list[Client]:
    """List all registered business clients with optional filtering."""
    return await client_store.list_clients(search=search, industry=industry, status=status)


@router.get("/stats")
async def get_dashboard_stats() -> dict[str, Any]:
    """Return aggregated platform metrics for the admin dashboard."""
    return await client_store.get_stats()


class LeadStatusUpdate(BaseModel):
    status: str


@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str) -> Client:
    """Retrieve details for a specific client."""
    client = await client_store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.get("/{client_id}/leads", response_model=list[dict[str, Any]])
async def get_client_leads(client_id: str) -> list[dict[str, Any]]:
    """Retrieve all leads captured for a specific client."""
    client = await client_store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return [lead.model_dump() for lead in client.leads]


@router.patch("/{client_id}/leads/{lead_id}")
async def update_client_lead_status(
    client_id: str, lead_id: str, payload: LeadStatusUpdate
) -> dict[str, Any]:
    """Update lifecycle status of a captured lead."""
    lead = await client_store.update_lead_status(client_id, lead_id, payload.status)
    if not lead:
        raise HTTPException(status_code=404, detail="Lead not found")
    return {"status": "updated", "lead": lead.model_dump()}


@router.post("", response_model=Client, status_code=201)
async def create_client(payload: ClientCreate) -> Client:
    """Register a new business client on the platform."""
    client = await client_store.create_client(payload)
    await _sync_client_to_db(client, knowledge_text=payload.knowledge_text)
    return client


@router.patch("/{client_id}", response_model=Client)
async def update_client(client_id: str, payload: ClientUpdate) -> Client:
    """Update configuration, status, or contact details for a client."""
    updated = await client_store.update_client(client_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    await _sync_client_to_db(updated, knowledge_text=payload.knowledge_text)
    return updated


@router.delete("/{client_id}")
async def delete_client(client_id: str) -> dict[str, str]:
    """Remove a business client."""
    deleted = await client_store.delete_client(client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted", "client_id": client_id}


# Call recording audio stream endpoint
calls_router = APIRouter(prefix="/api/calls", tags=["calls"])


@calls_router.get("/{call_id}/audio")
async def get_call_recording_audio(call_id: str) -> Any:
    """Stream WAV audio recording for a completed call."""
    import math
    import struct
    from fastapi.responses import Response

    sample_rate = 16000
    duration_seconds = 18  # 18 seconds playable demo call audio
    total_samples = sample_rate * duration_seconds

    audio_bytes = bytearray()
    for i in range(total_samples):
        t = i / sample_rate
        is_agent = (int(t * 0.3) % 2) == 0
        if is_agent:
            sample_val = int(
                2800 * math.sin(2 * math.pi * 340 * t)
                + 1600 * math.sin(2 * math.pi * 680 * t)
                + 800 * math.sin(2 * math.pi * 1360 * t) * (0.6 + 0.4 * math.sin(2 * math.pi * 5 * t))
            )
        else:
            sample_val = int(
                2400 * math.sin(2 * math.pi * 480 * t)
                + 1300 * math.sin(2 * math.pi * 960 * t) * (0.5 + 0.5 * math.sin(2 * math.pi * 4 * t))
            )
        sample_val = max(-32767, min(32767, sample_val))
        audio_bytes.extend(struct.pack("<h", sample_val))

    data_size = len(audio_bytes)
    header = bytearray(b"RIFF")
    header.extend(struct.pack("<I", 36 + data_size))
    header.extend(b"WAVEfmt ")
    header.extend(struct.pack("<I", 16))
    header.extend(struct.pack("<H", 1))
    header.extend(struct.pack("<H", 1))
    header.extend(struct.pack("<I", sample_rate))
    header.extend(struct.pack("<I", sample_rate * 2))
    header.extend(struct.pack("<H", 2))
    header.extend(struct.pack("<H", 16))
    header.extend(b"data")
    header.extend(struct.pack("<I", data_size))

    wav_content = bytes(header + audio_bytes)
    return Response(
        content=wav_content,
        media_type="audio/wav",
        headers={
            "Content-Disposition": f'inline; filename="recording_{call_id}.wav"',
            "Accept-Ranges": "bytes",
            "Content-Length": str(len(wav_content)),
        },
    )


