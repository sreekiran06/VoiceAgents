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


settings = Settings()
