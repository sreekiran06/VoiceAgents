"""Async SQLAlchemy engine, session factory, and declarative base.

Supports both SQLite (dev) and PostgreSQL (production) via DATABASE_URL.
"""

import logging
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from voice_call_agent.core.config import settings

logger = logging.getLogger(__name__)


class Base(DeclarativeBase):
    """Declarative base class for all ORM models."""
    pass


# Build engine — echo SQL in development mode
_echo = settings.environment == "development"
engine = create_async_engine(
    settings.database_url,
    echo=_echo,
    pool_pre_ping=True,
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields an async database session."""
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db() -> None:
    """Create all tables. Called once at app startup."""
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.info("Database tables created/verified.")


async def close_db() -> None:
    """Dispose engine connections. Called at app shutdown."""
    await engine.dispose()
    logger.info("Database connections closed.")
