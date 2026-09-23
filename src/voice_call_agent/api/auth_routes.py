"""Authentication API routes — login, API key management."""

import secrets
import logging

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voice_call_agent.core.auth import (
    create_jwt,
    hash_api_key,
    hash_password,
    verify_password,
    get_current_admin,
)
from voice_call_agent.core.database import get_db
from voice_call_agent.models.db_models import Admin, DBClient

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class LoginRequest(BaseModel):
    email: str
    password: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "bearer"
    user_type: str
    user_id: str
    name: str


class APIKeyResponse(BaseModel):
    api_key: str
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/login", response_model=LoginResponse)
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_db)) -> LoginResponse:
    """Authenticate admin or client and return a JWT token."""
    # Try admin first
    result = await db.execute(
        select(Admin).where(Admin.email == payload.email, Admin.is_active.is_(True))
    )
    admin = result.scalar_one_or_none()

    if admin and verify_password(payload.password, admin.password_hash):
        token = create_jwt({"sub": admin.id, "type": "admin", "email": admin.email})
        return LoginResponse(
            token=token,
            user_type="admin",
            user_id=admin.id,
            name=admin.full_name,
        )

    # Try client
    result = await db.execute(
        select(DBClient).where(DBClient.email == payload.email, DBClient.is_active.is_(True))
    )
    client = result.scalar_one_or_none()

    if client:
        # For clients, check against a stored password hash
        # If no password hash exists yet, they must use API key
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Client login via password not yet supported. Use API key.",
        )

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )


@router.post("/api-key/{client_id}", response_model=APIKeyResponse)
async def generate_api_key(
    client_id: str,
    admin: Admin = Depends(get_current_admin),
    db: AsyncSession = Depends(get_db),
) -> APIKeyResponse:
    """Generate or rotate an API key for a client. Admin only."""
    result = await db.execute(select(DBClient).where(DBClient.id == client_id))
    client = result.scalar_one_or_none()

    if not client:
        raise HTTPException(status_code=404, detail="Client not found")

    # Generate a secure random API key
    raw_key = f"sk_voice_{secrets.token_urlsafe(32)}"
    client.api_key_hash = hash_api_key(raw_key)
    await db.flush()

    logger.info("API key generated for client %s by admin %s", client_id, admin.email)

    return APIKeyResponse(
        api_key=raw_key,
        message=f"API key generated for {client.name}. Store it securely — it won't be shown again.",
    )


@router.get("/me")
async def get_current_user(admin: Admin = Depends(get_current_admin)) -> dict:
    """Return the currently authenticated admin user profile."""
    return {
        "id": admin.id,
        "email": admin.email,
        "full_name": admin.full_name,
        "role": admin.role,
        "user_type": "admin",
    }
