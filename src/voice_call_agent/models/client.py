from datetime import UTC, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


class LeadRecord(BaseModel):
    id: str
    name: str = "Anonymous"
    phone: str = ""
    email: str | None = None
    requirement: str
    budget: str | None = None
    location: str | None = None
    timeline: str | None = None
    status: Literal["new", "contacted", "qualified", "converted", "lost"] = "new"
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    )
    notes: str | None = None
    call_id: str | None = None


class CallRecord(BaseModel):
    call_id: str
    caller_phone: str
    call_time: str
    duration_seconds: int
    language_detected: str = "Telugu"
    status: Literal["completed", "missed", "transferred", "in-progress"] = "completed"
    sentiment: Literal["Positive", "Neutral", "Urgent", "Inquiry", "Follow-up"] = "Positive"
    summary: str
    recording_url: str | None = None
    transcript: list[dict[str, Any]] = Field(default_factory=list)


class ClientBase(BaseModel):
    name: str = Field(..., min_length=2, max_length=120)
    contact_person: str = Field(..., min_length=2, max_length=100)
    email: str = Field(..., max_length=120)
    phone: str = Field(..., max_length=30)
    industry: Literal["Real Estate", "Clinics & Healthcare", "Coaching & EdTech", "Local Services", "Other"]
    languages: list[Literal["Telugu", "Hindi", "English"]] = Field(default_factory=lambda: ["Telugu", "English"])
    virtual_number: str = Field(default="")
    plan: Literal["Starter", "Growth", "Pro"] = "Starter"
    status: Literal["active", "paused", "onboarding"] = "active"
    monthly_minutes_limit: int = Field(default=1000, ge=100)
    webhook_url: str | None = None
    agent_name: str | None = None
    greeting_text: str | None = None
    knowledge_text: str | None = None
    custom_llm_api_key: str | None = None
    llm_model: str | None = None


class ClientCreate(ClientBase):
    pass


class ClientUpdate(BaseModel):
    name: str | None = None
    contact_person: str | None = None
    email: str | None = None
    phone: str | None = None
    industry: Literal["Real Estate", "Clinics & Healthcare", "Coaching & EdTech", "Local Services", "Other"] | None = None
    languages: list[Literal["Telugu", "Hindi", "English"]] | None = None
    virtual_number: str | None = None
    plan: Literal["Starter", "Growth", "Pro"] | None = None
    status: Literal["active", "paused", "onboarding"] | None = None
    monthly_minutes_limit: int | None = None
    webhook_url: str | None = None
    agent_name: str | None = None
    greeting_text: str | None = None
    knowledge_text: str | None = None
    custom_llm_api_key: str | None = None
    llm_model: str | None = None


class Client(ClientBase):
    id: str
    minutes_used: int = 0
    leads_captured: int = 0
    appointments_booked: int = 0
    created_at: str = Field(
        default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%d %H:%M")
    )
    recent_calls: list[CallRecord] = Field(default_factory=list)
    leads: list[LeadRecord] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
