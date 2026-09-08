from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    PROJECT_NAME: str = "AI Sales Automation Platform"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # Security
    SECRET_KEY: str = "supersecret_jwt_key_change_in_production_ai_sales_crm_platform_key"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440  # 24 hours

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./ai_sales_crm.db"
    POSTGRES_DATABASE_URL: Optional[str] = "postgresql+asyncpg://postgres:postgrespassword@localhost:5432/ai_sales_crm"

    # AI Provider (Google Gemini)
    GEMINI_API_KEY: Optional[str] = ""
    GEMINI_MODEL: str = "gemini-2.5-flash"

    # Guardrail Policies
    MAX_DEFAULT_DISCOUNT_PCT: float = 10.0
    HITL_AUTO_ESCALATE_ON_LOW_CONFIDENCE: bool = True
    CONFIDENCE_THRESHOLD: float = 0.75

    # Telephony & Gemini Voice Configuration
    TWILIO_ACCOUNT_SID: Optional[str] = None
    TWILIO_AUTH_TOKEN: Optional[str] = None
    TWILIO_PHONE_NUMBER: Optional[str] = None
    GEMINI_VOICE_NAME: str = "Puck"  # Puck, Charon, Kore, Fenrir, Aoede
    VOICE_SIMULATION_MODE: bool = True

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

settings = Settings()
