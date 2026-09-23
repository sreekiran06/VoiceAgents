"""BusinessContext — the core multi-tenant data object loaded once per call.

Carries everything the voice agent needs for a specific business,
eliminating per-frame database queries during active calls.
"""

from dataclasses import dataclass, field


@dataclass(frozen=True)
class BusinessContext:
    """Immutable context loaded at call start, injected into the orchestrator."""

    business_id: str
    business_name: str
    client_id: str
    industry: str

    # Agent persona
    agent_name: str = "Kiran"
    system_prompt: str = ""
    greeting_text: str = "నమస్కారం! మీకు ఎలా సహాయం చేయగలను?"
    fallback_message: str = "క్షమించండి, మీ మాట సరిగ్గా వినిపించలేదు. దయచేసి మళ్ళీ చెప్పగలరా?"
    after_hours_message: str = "Thank you for calling. We are currently closed."

    # Language & voice
    languages: tuple[str, ...] = ("te-IN", "en-IN", "hi-IN")
    voice_map: dict[str, str] = field(default_factory=lambda: {
        "te-IN": "kavitha", "en-IN": "ishita", "hi-IN": "ritu",
    })
    tts_pace: float = 1.0

    # LLM settings
    llm_model: str = "gemini-3.5-flash-lite"
    max_output_tokens: int = 80
    temperature: float = 0.7

    # Knowledge base (FAQ entries)
    knowledge: tuple[dict[str, str], ...] = ()

    # Enabled tools
    enabled_tools: tuple[str, ...] = ("qualify_lead", "book_appointment", "transfer_to_human")

    # Business hours (list of dicts with day_of_week, open_time, close_time, is_closed)
    business_hours: tuple[dict, ...] = ()

    # Webhook for CRM integration
    webhook_url: str | None = None


# Default context used when no business is resolved (backward compatibility)
DEFAULT_CONTEXT = BusinessContext(
    business_id="default",
    business_name="SK Voice Agents",
    client_id="default",
    industry="Technology",
    agent_name="Kiran",
    system_prompt="",  # Will fall back to global SYSTEM_PROMPT
    greeting_text="నమస్కారం! SK Voice Agents కి స్వాగతం. మీకు ఎలా సహాయం చేయగలను?",
)
