from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Voice Call Agent"
    environment: str = "development"
    public_base_url: str = "http://localhost:8000"
    explabs_api_key: str = ""
    explabs_base_url: str = "https://api.experientiallabs.ai/v1"

    # Telephony configuration
    telephony_provider: str = "twilio"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    validate_telephony_signatures: bool = False

    # Vapi.ai configuration
    vapi_api_key: str = ""
    vapi_assistant_id: str = ""  # Set after creating assistant via /vapi/setup
    vapi_phone_number_id: str = ""  # Set after buying a Vapi phone number

    # Sarvam AI configuration  https://dashboard.sarvam.ai
    sarvam_api_key: str = ""
    # Comma-separated BCP-47 codes — first entry is the primary/fallback language.
    # Example: "en-IN,te-IN,hi-IN"
    sarvam_default_languages: str = "en-IN,te-IN,hi-IN"
    sarvam_pace: float = 1.0        # TTS speed: 0.5–2.0

    # Per-language voice overrides (Bulbul speaker names)
    sarvam_voice_en_in: str = "ishita"   # Indian English
    sarvam_voice_te_in: str = "kavitha"  # Telugu
    sarvam_voice_hi_in: str = "ritu"     # Hindi

    @property
    def sarvam_language_list(self) -> list[str]:
        """Ordered list of default languages; first entry is the primary."""
        return [lang.strip() for lang in self.sarvam_default_languages.split(",") if lang.strip()]

    @property
    def sarvam_voice_map(self) -> dict[str, str]:
        """Maps BCP-47 language codes to their configured speaker voices."""
        return {
            "en-IN": self.sarvam_voice_en_in,
            "te-IN": self.sarvam_voice_te_in,
            "hi-IN": self.sarvam_voice_hi_in,
        }


settings = Settings()
