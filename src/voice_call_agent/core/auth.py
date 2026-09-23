"""Authentication utilities for the multi-tenant platform.

Provides:
- API key hashing/verification (for client API access)
- JWT creation/decoding (for admin dashboard sessions)
- FastAPI dependencies: get_current_admin(), get_current_client()
"""

import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voice_call_agent.core.config import settings
from voice_call_agent.core.database import get_db
from voice_call_agent.models.db_models import Admin, DBClient

logger = logging.getLogger(__name__)

# Password / API-key hashing
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# Security schemes
bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


# ---------------------------------------------------------------------------
# Password & API Key utilities
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    return pwd_context.hash(password)


def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)


def hash_api_key(api_key: str) -> str:
    return pwd_context.hash(api_key)


def verify_api_key(api_key: str, hashed: str) -> bool:
    return pwd_context.verify(api_key, hashed)


# ---------------------------------------------------------------------------
# JWT utilities
# ---------------------------------------------------------------------------

def create_jwt(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a signed JWT token."""
    to_encode = data.copy()
    expire = datetime.now(UTC) + (expires_delta or timedelta(minutes=settings.jwt_expiry_minutes))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def decode_jwt(token: str) -> dict[str, Any]:
    """Decode and verify a JWT token. Raises JWTError on failure."""
    return jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------

async def get_current_admin(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin:
    """Extract and verify admin from Bearer JWT token."""
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing authorization header",
        )
    try:
        payload = decode_jwt(credentials.credentials)
        admin_id = payload.get("sub")
        token_type = payload.get("type")
        if not admin_id or token_type != "admin":
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

    result = await db.execute(select(Admin).where(Admin.id == admin_id, Admin.is_active.is_(True)))
    admin = result.scalar_one_or_none()
    if not admin:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Admin not found")
    return admin


async def get_current_client(
    api_key: str | None = Security(api_key_header),
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> DBClient:
    """Authenticate a client via API key header or JWT token."""
    # Try API key first
    if api_key:
        result = await db.execute(select(DBClient).where(DBClient.is_active.is_(True)))
        clients = result.scalars().all()
        for client in clients:
            if client.api_key_hash and verify_api_key(api_key, client.api_key_hash):
                return client
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    # Try JWT token
    if credentials:
        try:
            payload = decode_jwt(credentials.credentials)
            client_id = payload.get("sub")
            token_type = payload.get("type")
            if not client_id or token_type != "client":
                raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid token")
        except JWTError:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")

        result = await db.execute(
            select(DBClient).where(DBClient.id == client_id, DBClient.is_active.is_(True))
        )
        client = result.scalar_one_or_none()
        if not client:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Client not found")
        return client

    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Provide X-API-Key header or Bearer token",
    )


async def get_optional_admin(
    credentials: HTTPAuthorizationCredentials | None = Security(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> Admin | None:
    """Like get_current_admin but returns None instead of raising if unauthenticated."""
    if not credentials:
        return None
    try:
        payload = decode_jwt(credentials.credentials)
        admin_id = payload.get("sub")
        if not admin_id or payload.get("type") != "admin":
            return None
    except JWTError:
        return None

    result = await db.execute(select(Admin).where(Admin.id == admin_id, Admin.is_active.is_(True)))
    return result.scalar_one_or_none()
