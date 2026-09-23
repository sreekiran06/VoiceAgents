"""Resolve an incoming call's destination number to a BusinessContext.

Uses an async LRU cache (TTL: 5 min) to avoid database queries on every call.
Context is loaded once at call start and reused for the entire call duration.
"""

import asyncio
import logging
import time
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from voice_call_agent.core.context import DEFAULT_CONTEXT, BusinessContext
from voice_call_agent.core.database import async_session_factory
from voice_call_agent.models.db_models import (
    Business,
    BusinessConfig,
    BusinessHours,
    BusinessPhoneNumber,
    BusinessTool,
    KnowledgeEntry,
)

logger = logging.getLogger(__name__)

# Simple TTL cache: {phone_number: (BusinessContext, timestamp)}
_CACHE: dict[str, tuple[BusinessContext, float]] = {}
_CACHE_TTL_SEC = 300  # 5 minutes
_cache_lock = asyncio.Lock()


async def resolve_business_context(destination_number: str) -> BusinessContext:
    """Resolve a destination phone number to a full BusinessContext.

    1. Check in-memory cache (TTL: 5 min)
    2. Query DB: phone_number → business → config + knowledge + tools + hours
    3. Build and cache BusinessContext
    4. Return DEFAULT_CONTEXT if no match found
    """
    # Normalize phone number (strip spaces, leading +)
    normalized = destination_number.strip().replace(" ", "").replace("-", "")

    # 1. Cache check
    async with _cache_lock:
        cached = _CACHE.get(normalized)
        if cached:
            ctx, ts = cached
            if time.time() - ts < _CACHE_TTL_SEC:
                logger.debug("BusinessContext cache hit for %s → %s", normalized, ctx.business_id)
                return ctx
            else:
                del _CACHE[normalized]

    # 2. Database lookup
    try:
        async with async_session_factory() as session:
            # Find phone number → business
            stmt = (
                select(BusinessPhoneNumber)
                .where(BusinessPhoneNumber.phone_number == normalized)
                .where(BusinessPhoneNumber.is_active.is_(True))
            )
            result = await session.execute(stmt)
            phone_record = result.scalar_one_or_none()

            if not phone_record:
                # Try matching without country code prefix variations
                for prefix in ["", "+91", "91", "0"]:
                    stripped = normalized.lstrip("+").lstrip("0")
                    if stripped.startswith("91") and len(stripped) > 10:
                        stripped = stripped[2:]
                    possible = prefix + stripped

                    stmt = (
                        select(BusinessPhoneNumber)
                        .where(BusinessPhoneNumber.phone_number.contains(stripped[-10:]))
                        .where(BusinessPhoneNumber.is_active.is_(True))
                    )
                    result = await session.execute(stmt)
                    phone_record = result.scalar_one_or_none()
                    if phone_record:
                        break

            if not phone_record:
                logger.info("No business found for phone %s, using default context", normalized)
                return DEFAULT_CONTEXT

            business_id = phone_record.business_id

            # Load business with all related data
            stmt = (
                select(Business)
                .where(Business.id == business_id)
                .where(Business.is_active.is_(True))
                .options(
                    selectinload(Business.client),
                    selectinload(Business.config),
                    selectinload(Business.hours),
                    selectinload(Business.knowledge_entries),
                    selectinload(Business.tool_configs),
                )
            )
            result = await session.execute(stmt)
            business = result.scalar_one_or_none()

            if not business:
                logger.warning("Business %s is inactive or deleted", business_id)
                return DEFAULT_CONTEXT

            # Build context from DB records
            config = business.config
            ctx = _build_context(business, config, business.hours, business.knowledge_entries, business.tool_configs)

            # 3. Cache it
            async with _cache_lock:
                _CACHE[normalized] = (ctx, time.time())

            logger.info(
                "Resolved business context: phone=%s → business=%s (%s)",
                normalized, ctx.business_id, ctx.business_name,
            )
            return ctx

    except Exception as exc:
        logger.error("Error resolving business context for %s: %s", normalized, exc)
        return DEFAULT_CONTEXT


def _build_context(
    business: Business,
    config: BusinessConfig | None,
    hours: list[BusinessHours],
    knowledge: list[KnowledgeEntry],
    tools: list[BusinessTool],
) -> BusinessContext:
    """Build a BusinessContext from ORM objects."""
    if config:
        languages = tuple(config.language_list)
        voice_map = config.voice_map
        greeting = config.greeting_text
        fallback = config.fallback_message
        after_hours = config.after_hours_message
        agent_name = config.agent_name
        system_prompt = config.system_prompt_override or ""
        llm_model = config.llm_model
        max_tokens = config.max_output_tokens
        temp = config.temperature
        pace = config.tts_pace
    else:
        languages = ("te-IN", "en-IN", "hi-IN")
        voice_map = {"te-IN": "kavitha", "en-IN": "ishita", "hi-IN": "ritu"}
        greeting = "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?"
        fallback = "క్షమించండి, మీ మాట సరిగ్గా వినిపించలేదు."
        after_hours = "Thank you for calling. We are currently closed."
        agent_name = "Kiran"
        system_prompt = ""
        llm_model = "gemini-3.5-flash-lite"
        max_tokens = 80
        temp = 0.7
        pace = 1.0

    knowledge_entries = tuple(
        {"category": k.category, "question": k.question, "answer": k.answer}
        for k in knowledge
        if k.is_active
    )

    enabled_tools = tuple(
        t.tool_name for t in tools if t.enabled
    ) or ("qualify_lead", "book_appointment", "transfer_to_human")

    business_hours_data = tuple(
        {
            "day_of_week": h.day_of_week,
            "open_time": h.open_time,
            "close_time": h.close_time,
            "is_closed": h.is_closed,
        }
        for h in hours
    )

    return BusinessContext(
        business_id=business.id,
        business_name=business.name,
        client_id=business.client_id,
        industry=business.industry,
        agent_name=agent_name,
        system_prompt=system_prompt,
        greeting_text=greeting,
        fallback_message=fallback,
        after_hours_message=after_hours,
        languages=languages,
        voice_map=voice_map,
        tts_pace=pace,
        llm_model=llm_model,
        max_output_tokens=max_tokens,
        temperature=temp,
        knowledge=knowledge_entries,
        enabled_tools=enabled_tools,
        business_hours=business_hours_data,
        webhook_url=business.client.webhook_url if business.client else None,
    )


async def invalidate_cache(phone_number: str | None = None) -> None:
    """Invalidate cached context. If phone_number is None, clear entire cache."""
    async with _cache_lock:
        if phone_number:
            normalized = phone_number.strip().replace(" ", "").replace("-", "")
            _CACHE.pop(normalized, None)
        else:
            _CACHE.clear()
    logger.info("Cache invalidated: %s", phone_number or "ALL")
