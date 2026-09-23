"""SQLAlchemy ORM models for the multi-tenant voice agent platform.

Hierarchy: Admin → Client → Business → (Config, Hours, Knowledge, Tools, Calls)
"""

import uuid
from datetime import UTC, datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Mapped, mapped_column, relationship

from voice_call_agent.core.database import Base


def _uuid() -> str:
    return uuid.uuid4().hex


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------------------
# Admin (platform-level users)
# ---------------------------------------------------------------------------

class Admin(Base):
    __tablename__ = "admins"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False, default="Admin")
    role: Mapped[str] = mapped_column(String(30), nullable=False, default="superadmin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)


# ---------------------------------------------------------------------------
# Client (tenant organization)
# ---------------------------------------------------------------------------

class DBClient(Base):
    __tablename__ = "clients"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    contact_person: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    industry: Mapped[str] = mapped_column(String(80), nullable=False, default="Other")
    plan: Mapped[str] = mapped_column(String(30), nullable=False, default="Starter")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="onboarding")
    api_key_hash: Mapped[str | None] = mapped_column(String(255), nullable=True)
    monthly_minutes_limit: Mapped[int] = mapped_column(Integer, default=1000)
    minutes_used: Mapped[int] = mapped_column(Integer, default=0)
    webhook_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    businesses: Mapped[list["Business"]] = relationship(back_populates="client", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Business (individual business unit under a client)
# ---------------------------------------------------------------------------

class Business(Base):
    __tablename__ = "businesses"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    client_id: Mapped[str] = mapped_column(String(64), ForeignKey("clients.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    industry: Mapped[str] = mapped_column(String(80), nullable=False, default="Other")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    # Relationships
    client: Mapped["DBClient"] = relationship(back_populates="businesses")
    config: Mapped["BusinessConfig | None"] = relationship(back_populates="business", uselist=False, cascade="all, delete-orphan")
    phone_numbers: Mapped[list["BusinessPhoneNumber"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    hours: Mapped[list["BusinessHours"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    knowledge_entries: Mapped[list["KnowledgeEntry"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    tool_configs: Mapped[list["BusinessTool"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    call_sessions: Mapped[list["DBCallSession"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    leads: Mapped[list["Lead"]] = relationship(back_populates="business", cascade="all, delete-orphan")
    appointments: Mapped[list["Appointment"]] = relationship(back_populates="business", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Business Phone Numbers (for routing incoming calls → business)
# ---------------------------------------------------------------------------

class BusinessPhoneNumber(Base):
    __tablename__ = "business_phone_numbers"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="exotel")  # exotel | twilio
    label: Mapped[str | None] = mapped_column(String(80), nullable=True)  # e.g. "Main Line", "Sales"
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    business: Mapped["Business"] = relationship(back_populates="phone_numbers")


# ---------------------------------------------------------------------------
# Business Configuration (voice agent settings per business)
# ---------------------------------------------------------------------------

class BusinessConfig(Base):
    __tablename__ = "business_configs"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, unique=True, index=True)

    # Agent persona
    agent_name: Mapped[str] = mapped_column(String(60), nullable=False, default="Kiran")
    greeting_text: Mapped[str] = mapped_column(Text, nullable=False, default="నమస్కారం! మీకు ఎలా సహాయం చేయగలను?")
    system_prompt_override: Mapped[str | None] = mapped_column(Text, nullable=True)  # Overrides template
    fallback_message: Mapped[str] = mapped_column(Text, nullable=False, default="క్షమించండి, మీ మాట సరిగ్గా వినిపించలేదు. దయచేసి మళ్ళీ చెప్పగలరా?")
    after_hours_message: Mapped[str] = mapped_column(Text, nullable=False, default="Thank you for calling. We are currently closed. Please call back during business hours.")

    # Language & voice
    languages: Mapped[str] = mapped_column(String(100), nullable=False, default="te-IN,en-IN,hi-IN")  # CSV
    voice_te_in: Mapped[str] = mapped_column(String(30), nullable=False, default="kavitha")
    voice_en_in: Mapped[str] = mapped_column(String(30), nullable=False, default="ishita")
    voice_hi_in: Mapped[str] = mapped_column(String(30), nullable=False, default="ritu")
    tts_pace: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)

    # LLM
    llm_model: Mapped[str] = mapped_column(String(60), nullable=False, default="gemini-3.5-flash-lite")
    max_output_tokens: Mapped[int] = mapped_column(Integer, nullable=False, default=80)
    temperature: Mapped[float] = mapped_column(Float, nullable=False, default=0.7)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now, onupdate=_now)

    business: Mapped["Business"] = relationship(back_populates="config")

    @property
    def language_list(self) -> list[str]:
        return [lang.strip() for lang in self.languages.split(",") if lang.strip()]

    @property
    def voice_map(self) -> dict[str, str]:
        return {
            "te-IN": self.voice_te_in,
            "en-IN": self.voice_en_in,
            "hi-IN": self.voice_hi_in,
        }


# ---------------------------------------------------------------------------
# Business Hours
# ---------------------------------------------------------------------------

class BusinessHours(Base):
    __tablename__ = "business_hours"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    day_of_week: Mapped[int] = mapped_column(Integer, nullable=False)  # 0=Monday, 6=Sunday
    open_time: Mapped[str] = mapped_column(String(10), nullable=False, default="09:00")
    close_time: Mapped[str] = mapped_column(String(10), nullable=False, default="18:00")
    is_closed: Mapped[bool] = mapped_column(Boolean, default=False)

    business: Mapped["Business"] = relationship(back_populates="hours")

    __table_args__ = (
        UniqueConstraint("business_id", "day_of_week", name="uq_business_day"),
    )


# ---------------------------------------------------------------------------
# Knowledge Entries (FAQ per business)
# ---------------------------------------------------------------------------

class KnowledgeEntry(Base):
    __tablename__ = "knowledge_entries"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(80), nullable=False, default="general")
    question: Mapped[str] = mapped_column(Text, nullable=False)
    answer: Mapped[str] = mapped_column(Text, nullable=False)
    priority: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    business: Mapped["Business"] = relationship(back_populates="knowledge_entries")


# ---------------------------------------------------------------------------
# Business Tools (enabled tools per business)
# ---------------------------------------------------------------------------

class BusinessTool(Base):
    __tablename__ = "business_tools"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    tool_name: Mapped[str] = mapped_column(String(80), nullable=False)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    config_json: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON string for tool-specific config
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    business: Mapped["Business"] = relationship(back_populates="tool_configs")

    __table_args__ = (
        UniqueConstraint("business_id", "tool_name", name="uq_business_tool"),
    )


# ---------------------------------------------------------------------------
# Call Sessions (persistent call logs)
# ---------------------------------------------------------------------------

class DBCallSession(Base):
    __tablename__ = "call_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    call_sid: Mapped[str] = mapped_column(String(120), nullable=False, index=True)
    from_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    to_number: Mapped[str | None] = mapped_column(String(30), nullable=True)
    direction: Mapped[str] = mapped_column(String(20), nullable=False, default="inbound")
    provider: Mapped[str] = mapped_column(String(30), nullable=False, default="exotel")
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="initiated")
    language_detected: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    business: Mapped["Business"] = relationship(back_populates="call_sessions")
    messages: Mapped[list["CallMessage"]] = relationship(back_populates="session", cascade="all, delete-orphan")


# ---------------------------------------------------------------------------
# Call Messages (transcript entries)
# ---------------------------------------------------------------------------

class CallMessage(Base):
    __tablename__ = "call_messages"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    session_id: Mapped[str] = mapped_column(String(64), ForeignKey("call_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user | assistant | system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    session: Mapped["DBCallSession"] = relationship(back_populates="messages")


# ---------------------------------------------------------------------------
# Leads
# ---------------------------------------------------------------------------

class Lead(Base):
    __tablename__ = "leads"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("call_sessions.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(30), nullable=True)
    requirement: Mapped[str] = mapped_column(Text, nullable=False)
    budget: Mapped[str | None] = mapped_column(String(100), nullable=True)
    location: Mapped[str | None] = mapped_column(String(120), nullable=True)
    timeline: Mapped[str | None] = mapped_column(String(100), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="new")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    business: Mapped["Business"] = relationship(back_populates="leads")


# ---------------------------------------------------------------------------
# Appointments
# ---------------------------------------------------------------------------

class Appointment(Base):
    __tablename__ = "appointments"

    id: Mapped[str] = mapped_column(String(64), primary_key=True, default=_uuid)
    business_id: Mapped[str] = mapped_column(String(64), ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True)
    session_id: Mapped[str | None] = mapped_column(String(64), ForeignKey("call_sessions.id", ondelete="SET NULL"), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(120), nullable=False)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    appointment_type: Mapped[str] = mapped_column(String(80), nullable=False)
    date: Mapped[str] = mapped_column(String(30), nullable=False)
    time: Mapped[str] = mapped_column(String(30), nullable=False)
    confirmation_code: Mapped[str | None] = mapped_column(String(20), nullable=True)
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="confirmed")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=_now)

    business: Mapped["Business"] = relationship(back_populates="appointments")
