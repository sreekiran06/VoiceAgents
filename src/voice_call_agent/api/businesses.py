"""Business CRUD API routes — tenant-scoped business management."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from voice_call_agent.core.auth import get_current_admin, get_optional_admin
from voice_call_agent.core.context_loader import invalidate_cache
from voice_call_agent.core.database import get_db
from voice_call_agent.models.db_models import (
    Admin,
    Business,
    BusinessConfig,
    BusinessHours,
    BusinessPhoneNumber,
    BusinessTool,
    DBClient,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/businesses", tags=["businesses"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class PhoneNumberIn(BaseModel):
    phone_number: str
    provider: str = "exotel"
    label: str | None = None


class BusinessConfigIn(BaseModel):
    agent_name: str = "Kiran"
    greeting_text: str = "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?"
    system_prompt_override: str | None = None
    fallback_message: str = "క్షమించండి, మీ మాట సరిగ్గా వినిపించలేదు."
    after_hours_message: str = "Thank you for calling. We are currently closed."
    languages: str = "te-IN,en-IN,hi-IN"
    voice_te_in: str = "kavitha"
    voice_en_in: str = "ishita"
    voice_hi_in: str = "ritu"
    tts_pace: float = 1.0
    llm_model: str = "gemini-3.5-flash-lite"
    max_output_tokens: int = 80
    temperature: float = 0.7


class BusinessHoursIn(BaseModel):
    day_of_week: int = Field(..., ge=0, le=6)
    open_time: str = "09:00"
    close_time: str = "18:00"
    is_closed: bool = False


class BusinessToolIn(BaseModel):
    tool_name: str
    enabled: bool = True
    config_json: str | None = None


class BusinessCreate(BaseModel):
    client_id: str
    name: str
    industry: str = "Other"
    description: str | None = None
    phone_numbers: list[PhoneNumberIn] = []
    config: BusinessConfigIn = BusinessConfigIn()
    hours: list[BusinessHoursIn] = []
    tools: list[BusinessToolIn] = []


class BusinessUpdate(BaseModel):
    name: str | None = None
    industry: str | None = None
    description: str | None = None
    status: str | None = None


class BusinessOut(BaseModel):
    id: str
    client_id: str
    name: str
    industry: str
    description: str | None
    status: str
    is_active: bool
    phone_numbers: list[dict[str, Any]] = []
    config: dict[str, Any] | None = None

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_businesses(
    client_id: str | None = Query(None),
    industry: str | None = Query(None),
    status: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List businesses. Optionally filter by client_id, industry, status."""
    stmt = (
        select(Business)
        .where(Business.is_active.is_(True))
        .options(selectinload(Business.phone_numbers), selectinload(Business.config))
    )
    if client_id:
        stmt = stmt.where(Business.client_id == client_id)
    if industry:
        stmt = stmt.where(Business.industry == industry)
    if status:
        stmt = stmt.where(Business.status == status)

    result = await db.execute(stmt)
    businesses = result.scalars().all()

    return [_serialize_business(b) for b in businesses]


@router.get("/{business_id}")
async def get_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Get a single business with full details."""
    stmt = (
        select(Business)
        .where(Business.id == business_id)
        .options(
            selectinload(Business.phone_numbers),
            selectinload(Business.config),
            selectinload(Business.hours),
            selectinload(Business.tool_configs),
        )
    )
    result = await db.execute(stmt)
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")
    return _serialize_business_full(business)


@router.post("", status_code=201)
async def create_business(
    payload: BusinessCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Create a new business under a client."""
    # Verify client exists
    client_result = await db.execute(select(DBClient).where(DBClient.id == payload.client_id))
    if not client_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Client not found")

    business = Business(
        client_id=payload.client_id,
        name=payload.name,
        industry=payload.industry,
        description=payload.description,
    )
    db.add(business)
    await db.flush()  # Get business.id

    # Config
    cfg = payload.config
    db_config = BusinessConfig(
        business_id=business.id,
        agent_name=cfg.agent_name,
        greeting_text=cfg.greeting_text,
        system_prompt_override=cfg.system_prompt_override,
        fallback_message=cfg.fallback_message,
        after_hours_message=cfg.after_hours_message,
        languages=cfg.languages,
        voice_te_in=cfg.voice_te_in,
        voice_en_in=cfg.voice_en_in,
        voice_hi_in=cfg.voice_hi_in,
        tts_pace=cfg.tts_pace,
        llm_model=cfg.llm_model,
        max_output_tokens=cfg.max_output_tokens,
        temperature=cfg.temperature,
    )
    db.add(db_config)

    # Phone numbers
    for pn in payload.phone_numbers:
        db.add(BusinessPhoneNumber(
            business_id=business.id,
            phone_number=pn.phone_number.strip().replace(" ", "").replace("-", ""),
            provider=pn.provider,
            label=pn.label,
        ))

    # Hours
    for h in payload.hours:
        db.add(BusinessHours(
            business_id=business.id,
            day_of_week=h.day_of_week,
            open_time=h.open_time,
            close_time=h.close_time,
            is_closed=h.is_closed,
        ))

    # Tools — default tools if none provided
    if payload.tools:
        for t in payload.tools:
            db.add(BusinessTool(
                business_id=business.id,
                tool_name=t.tool_name,
                enabled=t.enabled,
                config_json=t.config_json,
            ))
    else:
        for tool_name in ["qualify_lead", "book_appointment", "transfer_to_human"]:
            db.add(BusinessTool(
                business_id=business.id,
                tool_name=tool_name,
                enabled=True,
            ))

    await db.flush()
    logger.info("Created business %s (%s) for client %s", business.id, business.name, payload.client_id)

    return {"id": business.id, "name": business.name, "status": "created"}


@router.patch("/{business_id}")
async def update_business(
    business_id: str,
    payload: BusinessUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Update a business's basic info."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(business, field, val)

    await db.flush()
    await invalidate_cache()  # Clear context cache
    return {"id": business.id, "name": business.name, "status": business.status}


@router.patch("/{business_id}/config")
async def update_business_config(
    business_id: str,
    payload: BusinessConfigIn,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update a business's voice agent configuration."""
    result = await db.execute(
        select(BusinessConfig).where(BusinessConfig.business_id == business_id)
    )
    config = result.scalar_one_or_none()
    if not config:
        raise HTTPException(status_code=404, detail="Business config not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(config, field, val)

    await db.flush()
    await invalidate_cache()  # Clear context cache
    return {"status": "updated", "business_id": business_id}


@router.delete("/{business_id}")
async def delete_business(
    business_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Soft-delete a business (set is_active=False)."""
    result = await db.execute(select(Business).where(Business.id == business_id))
    business = result.scalar_one_or_none()
    if not business:
        raise HTTPException(status_code=404, detail="Business not found")

    business.is_active = False
    business.status = "deactivated"
    await db.flush()
    await invalidate_cache()
    return {"status": "deleted", "business_id": business_id}


# ---------------------------------------------------------------------------
# Serializers
# ---------------------------------------------------------------------------

def _serialize_business(b: Business) -> dict[str, Any]:
    return {
        "id": b.id,
        "client_id": b.client_id,
        "name": b.name,
        "industry": b.industry,
        "description": b.description,
        "status": b.status,
        "is_active": b.is_active,
        "phone_numbers": [
            {"phone_number": pn.phone_number, "provider": pn.provider, "label": pn.label}
            for pn in (b.phone_numbers or [])
        ],
        "config": {
            "agent_name": b.config.agent_name,
            "greeting_text": b.config.greeting_text,
            "languages": b.config.languages,
        } if b.config else None,
    }


def _serialize_business_full(b: Business) -> dict[str, Any]:
    data = _serialize_business(b)
    if b.config:
        data["config"] = {
            "agent_name": b.config.agent_name,
            "greeting_text": b.config.greeting_text,
            "system_prompt_override": b.config.system_prompt_override,
            "fallback_message": b.config.fallback_message,
            "after_hours_message": b.config.after_hours_message,
            "languages": b.config.languages,
            "voice_te_in": b.config.voice_te_in,
            "voice_en_in": b.config.voice_en_in,
            "voice_hi_in": b.config.voice_hi_in,
            "tts_pace": b.config.tts_pace,
            "llm_model": b.config.llm_model,
            "max_output_tokens": b.config.max_output_tokens,
            "temperature": b.config.temperature,
        }
    data["hours"] = [
        {
            "day_of_week": h.day_of_week,
            "open_time": h.open_time,
            "close_time": h.close_time,
            "is_closed": h.is_closed,
        }
        for h in (b.hours or [])
    ]
    data["tools"] = [
        {"tool_name": t.tool_name, "enabled": t.enabled}
        for t in (b.tool_configs or [])
    ]
    return data
