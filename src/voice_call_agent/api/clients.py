from typing import Any

from fastapi import APIRouter, HTTPException, Query

from voice_call_agent.core.client_store import client_store
from voice_call_agent.models.client import Client, ClientCreate, ClientUpdate

router = APIRouter(prefix="/api/clients", tags=["clients"])


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


@router.get("/{client_id}", response_model=Client)
async def get_client(client_id: str) -> Client:
    """Retrieve details for a specific client."""
    client = await client_store.get_client(client_id)
    if not client:
        raise HTTPException(status_code=404, detail="Client not found")
    return client


@router.post("", response_model=Client, status_code=201)
async def create_client(payload: ClientCreate) -> Client:
    """Register a new business client on the platform."""
    return await client_store.create_client(payload)


@router.patch("/{client_id}", response_model=Client)
async def update_client(client_id: str, payload: ClientUpdate) -> Client:
    """Update configuration, status, or contact details for a client."""
    updated = await client_store.update_client(client_id, payload)
    if not updated:
        raise HTTPException(status_code=404, detail="Client not found")
    return updated


@router.delete("/{client_id}")
async def delete_client(client_id: str) -> dict[str, str]:
    """Remove a business client."""
    deleted = await client_store.delete_client(client_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Client not found")
    return {"status": "deleted", "client_id": client_id}
