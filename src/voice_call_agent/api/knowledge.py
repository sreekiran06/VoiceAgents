"""Knowledge base CRUD API — manage FAQ entries per business."""

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voice_call_agent.core.context_loader import invalidate_cache
from voice_call_agent.core.database import get_db
from voice_call_agent.models.db_models import Business, KnowledgeEntry

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/businesses/{business_id}/knowledge", tags=["knowledge"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class KnowledgeCreate(BaseModel):
    category: str = "general"
    question: str
    answer: str
    priority: int = 0


class KnowledgeUpdate(BaseModel):
    category: str | None = None
    question: str | None = None
    answer: str | None = None
    priority: int | None = None
    is_active: bool | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get("")
async def list_knowledge(
    business_id: str,
    category: str | None = None,
    db: AsyncSession = Depends(get_db),
) -> list[dict[str, Any]]:
    """List knowledge entries for a business."""
    # Verify business exists
    biz_result = await db.execute(select(Business).where(Business.id == business_id))
    if not biz_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Business not found")

    stmt = (
        select(KnowledgeEntry)
        .where(KnowledgeEntry.business_id == business_id)
        .where(KnowledgeEntry.is_active.is_(True))
        .order_by(KnowledgeEntry.priority.desc())
    )
    if category:
        stmt = stmt.where(KnowledgeEntry.category == category)

    result = await db.execute(stmt)
    entries = result.scalars().all()

    return [
        {
            "id": e.id,
            "category": e.category,
            "question": e.question,
            "answer": e.answer,
            "priority": e.priority,
            "is_active": e.is_active,
        }
        for e in entries
    ]


@router.post("", status_code=201)
async def create_knowledge(
    business_id: str,
    payload: KnowledgeCreate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, Any]:
    """Add a knowledge entry to a business."""
    biz_result = await db.execute(select(Business).where(Business.id == business_id))
    if not biz_result.scalar_one_or_none():
        raise HTTPException(status_code=404, detail="Business not found")

    entry = KnowledgeEntry(
        business_id=business_id,
        category=payload.category,
        question=payload.question,
        answer=payload.answer,
        priority=payload.priority,
    )
    db.add(entry)
    await db.flush()
    await invalidate_cache()

    return {"id": entry.id, "status": "created"}


@router.put("/{entry_id}")
async def update_knowledge(
    business_id: str,
    entry_id: str,
    payload: KnowledgeUpdate,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Update a knowledge entry."""
    result = await db.execute(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == entry_id, KnowledgeEntry.business_id == business_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    update_data = payload.model_dump(exclude_unset=True)
    for field, val in update_data.items():
        if val is not None:
            setattr(entry, field, val)

    await db.flush()
    await invalidate_cache()
    return {"status": "updated", "id": entry_id}


@router.delete("/{entry_id}")
async def delete_knowledge(
    business_id: str,
    entry_id: str,
    db: AsyncSession = Depends(get_db),
) -> dict[str, str]:
    """Soft-delete a knowledge entry."""
    result = await db.execute(
        select(KnowledgeEntry)
        .where(KnowledgeEntry.id == entry_id, KnowledgeEntry.business_id == business_id)
    )
    entry = result.scalar_one_or_none()
    if not entry:
        raise HTTPException(status_code=404, detail="Knowledge entry not found")

    entry.is_active = False
    await db.flush()
    await invalidate_cache()
    return {"status": "deleted", "id": entry_id}
