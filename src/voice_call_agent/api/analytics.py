"""Analytics API — tenant-scoped call metrics, lead stats, usage."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from voice_call_agent.core.database import get_db
from voice_call_agent.models.db_models import (
    Appointment,
    Business,
    DBCallSession,
    DBClient,
    Lead,
)

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/analytics", tags=["analytics"])


@router.get("/overview")
async def platform_overview(
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Platform-wide metrics for admin dashboard."""
    total_clients = (await db.execute(select(func.count(DBClient.id)).where(DBClient.is_active.is_(True)))).scalar() or 0
    total_businesses = (await db.execute(select(func.count(Business.id)).where(Business.is_active.is_(True)))).scalar() or 0
    total_calls = (await db.execute(select(func.count(DBCallSession.id)))).scalar() or 0
    total_leads = (await db.execute(select(func.count(Lead.id)))).scalar() or 0
    total_appointments = (await db.execute(select(func.count(Appointment.id)))).scalar() or 0

    return {
        "total_clients": total_clients,
        "total_businesses": total_businesses,
        "total_calls": total_calls,
        "total_leads": total_leads,
        "total_appointments": total_appointments,
    }


@router.get("/calls")
async def call_analytics(
    business_id: str | None = Query(None),
    client_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Call analytics with optional business/client scoping."""
    stmt = select(DBCallSession)

    if business_id:
        stmt = stmt.where(DBCallSession.business_id == business_id)
    elif client_id:
        # Get all business IDs for this client
        biz_stmt = select(Business.id).where(Business.client_id == client_id)
        biz_result = await db.execute(biz_stmt)
        biz_ids = [row[0] for row in biz_result.all()]
        if biz_ids:
            stmt = stmt.where(DBCallSession.business_id.in_(biz_ids))
        else:
            return {"total_calls": 0, "completed": 0, "avg_duration_seconds": 0}

    result = await db.execute(stmt)
    calls = result.scalars().all()

    total = len(calls)
    completed = sum(1 for c in calls if c.status == "completed")
    durations = [c.duration_seconds for c in calls if c.duration_seconds]
    avg_duration = sum(durations) / len(durations) if durations else 0

    # Language breakdown
    lang_counts: dict[str, int] = {}
    for c in calls:
        lang = c.language_detected or "unknown"
        lang_counts[lang] = lang_counts.get(lang, 0) + 1

    return {
        "total_calls": total,
        "completed": completed,
        "in_progress": sum(1 for c in calls if c.status == "in-progress"),
        "avg_duration_seconds": round(avg_duration, 1),
        "language_breakdown": lang_counts,
    }


@router.get("/leads")
async def lead_analytics(
    business_id: str | None = Query(None),
    client_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Lead analytics with optional scoping."""
    stmt = select(Lead)

    if business_id:
        stmt = stmt.where(Lead.business_id == business_id)
    elif client_id:
        biz_stmt = select(Business.id).where(Business.client_id == client_id)
        biz_result = await db.execute(biz_stmt)
        biz_ids = [row[0] for row in biz_result.all()]
        if biz_ids:
            stmt = stmt.where(Lead.business_id.in_(biz_ids))
        else:
            return {"total_leads": 0, "new": 0, "contacted": 0, "converted": 0}

    result = await db.execute(stmt)
    leads = result.scalars().all()

    status_counts: dict[str, int] = {}
    for lead in leads:
        status_counts[lead.status] = status_counts.get(lead.status, 0) + 1

    return {
        "total_leads": len(leads),
        "status_breakdown": status_counts,
    }


@router.get("/usage")
async def usage_analytics(
    client_id: str | None = Query(None),
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """Usage analytics (minutes used vs limit) per client."""
    stmt = select(DBClient).where(DBClient.is_active.is_(True))
    if client_id:
        stmt = stmt.where(DBClient.id == client_id)

    result = await db.execute(stmt)
    clients = result.scalars().all()

    return [
        {
            "client_id": c.id,
            "client_name": c.name,
            "plan": c.plan,
            "minutes_used": c.minutes_used,
            "monthly_limit": c.monthly_minutes_limit,
            "usage_percent": round((c.minutes_used / c.monthly_minutes_limit) * 100, 1) if c.monthly_minutes_limit else 0,
        }
        for c in clients
    ]
