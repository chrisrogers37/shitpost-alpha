"""
Configuration settings for Shitpost-Alpha.
Uses Pydantic for environment variable validation and management.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field

# Load .env file from project root
from dotenv import load_dotenv

current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(
    os.path.dirname(current_dir)
)  # Go up two levels from shit/config/
env_file_path = os.path.join(project_root, ".env")
if os.path.exists(env_file_path):
    load_dotenv(env_file_path)


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Environment
    ENVIRONMENT: str = Field(default="development")
    DEBUG: bool = Field(default=True)

    # Database
    DATABASE_URL: str = Field(default="sqlite:///./shitpost_alpha.db")

    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None)
    XAI_API_KEY: Optional[str] = Field(default=None)
    LLM_PROVIDER: str = Field(default="openai")  # openai, anthropic, grok
    LLM_MODEL: str = Field(default="gpt-4")
    LLM_BASE_URL: Optional[str] = Field(
        default=None
    )  # Custom base URL for OpenAI-compatible APIs

    # Ensemble Configuration
    ENSEMBLE_ENABLED: bool = Field(
        default=False
    )  # Opt-in; set True in Railway to activate
    ENSEMBLE_PROVIDERS: str = Field(default="openai,anthropic,grok")
    ENSEMBLE_MIN_PROVIDERS: int = Field(
        default=2
    )  # Minimum successful providers for valid ensemble

    # Truth Social Shitpost Configuration
    TRUTH_SOCIAL_USERNAME: str = Field(default="realDonaldTrump")
    TRUTH_SOCIAL_SHITPOST_INTERVAL: int = Field(
        default=30
    )  # seconds between shitpost harvests

    # Analysis Configuration
    CONFIDENCE_THRESHOLD: float = Field(default=0.7)
    MAX_SHITPOST_LENGTH: int = Field(default=4000)

    # System Launch Configuration
    SYSTEM_LAUNCH_DATE: str = Field(default="2025-01-01T00:00:00Z")

    # SMS/Alerting Configuration (Phase 2)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None)
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None)
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None)

    # Email Configuration (Phase 2 - Alerting)
    EMAIL_PROVIDER: str = Field(default="smtp")  # "smtp" or "sendgrid"
    SMTP_HOST: Optional[str] = Field(default=None)
    SMTP_PORT: int = Field(default=587)
    SMTP_USERNAME: Optional[str] = Field(default=None)
    SMTP_PASSWORD: Optional[str] = Field(default=None)
    SMTP_USE_TLS: bool = Field(default=True)
    EMAIL_FROM_ADDRESS: str = Field(default="alerts@shitpostalpha.com")
    EMAIL_FROM_NAME: str = Field(default="Shitpost Alpha")
    SENDGRID_API_KEY: Optional[str] = Field(default=None)

    # Telegram Bot Configuration (Phase 2 - Alerting)
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None)
    TELEGRAM_BOT_USERNAME: Optional[str] = Field(default=None)  # Without @ prefix
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None
    )  # For webhook mode (optional)

    # Market Data Resilience Configuration
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(default=None)
    MARKET_DATA_PRIMARY_PROVIDER: str = Field(default="yfinance")
    MARKET_DATA_FALLBACK_PROVIDER: str = Field(default="alphavantage")
    MARKET_DATA_MAX_RETRIES: int = Field(default=3)
    MARKET_DATA_RETRY_DELAY: float = Field(default=1.0)  # seconds
    MARKET_DATA_RETRY_BACKOFF: float = Field(default=2.0)  # multiplier
    MARKET_DATA_STALENESS_THRESHOLD_HOURS: int = Field(default=48)
    MARKET_DATA_HEALTH_CHECK_SYMBOLS: str = Field(default="SPY,AAPL")
    MARKET_DATA_FAILURE_ALERT_CHAT_ID: Optional[str] = Field(default=None)

    # ScrapeCreators API Configuration
    SCRAPECREATORS_API_KEY: Optional[str] = Field(default=None)

    # S3 Data Lake Configuration
    S3_BUCKET_NAME: str = Field(default="shitpost-alpha-raw-data")
    S3_PREFIX: str = Field(default="truth-social")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None)
    AWS_REGION: str = Field(default="us-east-1")

    # Multi-Source Harvester Configuration
    ENABLED_HARVESTERS: str = Field(
        default="truth_social"
    )  # Comma-separated list of enabled harvester source names

    # Twitter/X Configuration (Future)
    TWITTER_API_KEY: Optional[str] = Field(default=None)
    TWITTER_API_SECRET: Optional[str] = Field(default=None)
    TWITTER_BEARER_TOKEN: Optional[str] = Field(default=None)
    TWITTER_TARGET_USERS: str = Field(
        default=""
    )  # Comma-separated Twitter usernames to monitor

    # Logging
    LOG_LEVEL: str = Field(default="INFO")
    FILE_LOGGING: bool = Field(default=False)
    LOG_FILE_PATH: Optional[str] = Field(default=None)

    # Neon CLI (used by db-admin tooling, not by application code)
    NEON_PROJECT_ID: Optional[str] = Field(default=None)
    NEON_ORG_ID: Optional[str] = Field(default=None)

    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,
    )

    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'"
                )
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError(
                    "ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'"
                )
            return self.ANTHROPIC_API_KEY
        elif self.LLM_PROVIDER == "grok":
            if not self.XAI_API_KEY:
                raise ValueError("XAI_API_KEY is required when LLM_PROVIDER is 'grok'")
            return self.XAI_API_KEY
        else:
            raise ValueError(f"Unsupported LLM provider: {self.LLM_PROVIDER}")

    def get_llm_base_url(self) -> Optional[str]:
        """Get the base URL for the LLM provider, if applicable.

        Returns:
            Base URL string for OpenAI-compatible providers, or None for native SDKs.
        """
        if self.LLM_BASE_URL:
            return self.LLM_BASE_URL
        if self.LLM_PROVIDER == "grok":
            return "https://api.x.ai/v1"
        return None

    def get_enabled_harvester_names(self) -> list[str]:
        """Parse ENABLED_HARVESTERS into a list of source names."""
        return [h.strip() for h in self.ENABLED_HARVESTERS.split(",") if h.strip()]

    def is_production(self) -> bool:
        """Check if running in production environment."""
        return self.ENVIRONMENT.lower() == "production"

    def validate_config(self):
        """Validate that all required settings are present."""
        errors = []

        # Validate LLM configuration
        try:
            self.get_llm_api_key()
        except ValueError as e:
            errors.append(str(e))

        # Add more validation as needed

        if errors:
            raise ValueError(f"Configuration errors: {'; '.join(errors)}")


# Global settings instance
settings = Settings()
