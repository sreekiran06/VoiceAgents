from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "Voice Call Agent"
    environment: str = "development"
    public_base_url: str = ""
    render_external_url: str = ""  # Auto-populated by Render if deployed there

    @property
    def base_url(self) -> str:
        """Resolve public base URL from explicit setting, Render environment, or localhost."""
        if self.public_base_url and self.public_base_url != "http://localhost:8000":
            return self.public_base_url.rstrip("/")
        if self.render_external_url:
            return self.render_external_url.rstrip("/")
        return self.public_base_url or "http://localhost:8000"

    # LLM Provider: "gemini" or "explabs"
    llm_provider: str = "gemini"
    explabs_api_key: str = ""
    explabs_base_url: str = "https://api.experientiallabs.ai/v1"
    gemini_api_key: str = ""

    # Telephony configuration
    telephony_provider: str = "twilio"  # "twilio" or "exotel"
    twilio_account_sid: str = ""
    twilio_auth_token: str = ""
    twilio_from_number: str = ""
    validate_telephony_signatures: bool = False

    # Exotel configuration (https://my.exotel.com/apps#installed-apps)
    exotel_account_sid: str = ""
    exotel_api_key: str = ""
    exotel_api_token: str = ""
    exotel_subdomain: str = "api.exotel.com"  # or "api.in.exotel.com" for Mumbai cluster
    exotel_caller_id: str = ""  # Your ExoPhone virtual number (e.g. 0XXXXXXXXX)
    exotel_app_id: str = ""  # Flow / Applet ID from Installed Apps


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
