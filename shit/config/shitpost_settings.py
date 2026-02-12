"""
Configuration settings for Shitpost-Alpha.
Uses Pydantic for environment variable validation and management.
"""

import os
from typing import Optional
from pydantic_settings import BaseSettings
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
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    DEBUG: bool = Field(default=True, env="DEBUG")

    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./shitpost_alpha.db", env="DATABASE_URL"
    )

    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    XAI_API_KEY: Optional[str] = Field(default=None, env="XAI_API_KEY")
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # openai, anthropic, grok
    LLM_MODEL: str = Field(default="gpt-4", env="LLM_MODEL")
    LLM_BASE_URL: Optional[str] = Field(default=None, env="LLM_BASE_URL")  # Custom base URL for OpenAI-compatible APIs

    # Truth Social Shitpost Configuration
    TRUTH_SOCIAL_USERNAME: str = Field(
        default="realDonaldTrump", env="TRUTH_SOCIAL_USERNAME"
    )
    TRUTH_SOCIAL_SHITPOST_INTERVAL: int = Field(
        default=30, env="TRUTH_SOCIAL_SHITPOST_INTERVAL"
    )  # seconds between shitpost harvests

    # Analysis Configuration
    CONFIDENCE_THRESHOLD: float = Field(default=0.7, env="CONFIDENCE_THRESHOLD")
    MAX_SHITPOST_LENGTH: int = Field(default=4000, env="MAX_SHITPOST_LENGTH")

    # System Launch Configuration
    SYSTEM_LAUNCH_DATE: str = Field(
        default="2025-01-01T00:00:00Z", env="SYSTEM_LAUNCH_DATE"
    )

    # SMS/Alerting Configuration (Phase 2)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")

    # Email Configuration (Phase 2 - Alerting)
    EMAIL_PROVIDER: str = Field(
        default="smtp", env="EMAIL_PROVIDER"
    )  # "smtp" or "sendgrid"
    SMTP_HOST: Optional[str] = Field(default=None, env="SMTP_HOST")
    SMTP_PORT: int = Field(default=587, env="SMTP_PORT")
    SMTP_USERNAME: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    SMTP_PASSWORD: Optional[str] = Field(default=None, env="SMTP_PASSWORD")
    SMTP_USE_TLS: bool = Field(default=True, env="SMTP_USE_TLS")
    EMAIL_FROM_ADDRESS: str = Field(
        default="alerts@shitpostalpha.com",
        env="EMAIL_FROM_ADDRESS",
    )
    EMAIL_FROM_NAME: str = Field(
        default="Shitpost Alpha",
        env="EMAIL_FROM_NAME",
    )
    SENDGRID_API_KEY: Optional[str] = Field(default=None, env="SENDGRID_API_KEY")

    # Telegram Bot Configuration (Phase 2 - Alerting)
    TELEGRAM_BOT_TOKEN: Optional[str] = Field(default=None, env="TELEGRAM_BOT_TOKEN")
    TELEGRAM_BOT_USERNAME: Optional[str] = Field(
        default=None, env="TELEGRAM_BOT_USERNAME"
    )  # Without @ prefix
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None, env="TELEGRAM_WEBHOOK_URL"
    )  # For webhook mode (optional)

    # Market Data Resilience Configuration
    ALPHA_VANTAGE_API_KEY: Optional[str] = Field(default=None, env="ALPHA_VANTAGE_API_KEY")
    MARKET_DATA_PRIMARY_PROVIDER: str = Field(default="yfinance", env="MARKET_DATA_PRIMARY_PROVIDER")
    MARKET_DATA_FALLBACK_PROVIDER: str = Field(default="alphavantage", env="MARKET_DATA_FALLBACK_PROVIDER")
    MARKET_DATA_MAX_RETRIES: int = Field(default=3, env="MARKET_DATA_MAX_RETRIES")
    MARKET_DATA_RETRY_DELAY: float = Field(default=1.0, env="MARKET_DATA_RETRY_DELAY")  # seconds
    MARKET_DATA_RETRY_BACKOFF: float = Field(default=2.0, env="MARKET_DATA_RETRY_BACKOFF")  # multiplier
    MARKET_DATA_STALENESS_THRESHOLD_HOURS: int = Field(default=48, env="MARKET_DATA_STALENESS_THRESHOLD_HOURS")
    MARKET_DATA_HEALTH_CHECK_SYMBOLS: str = Field(default="SPY,AAPL", env="MARKET_DATA_HEALTH_CHECK_SYMBOLS")
    MARKET_DATA_FAILURE_ALERT_CHAT_ID: Optional[str] = Field(default=None, env="MARKET_DATA_FAILURE_ALERT_CHAT_ID")

    # ScrapeCreators API Configuration
    SCRAPECREATORS_API_KEY: Optional[str] = Field(
        default=None, env="SCRAPECREATORS_API_KEY"
    )

    # S3 Data Lake Configuration
    S3_BUCKET_NAME: str = Field(default="shitpost-alpha-raw-data", env="S3_BUCKET_NAME")
    S3_PREFIX: str = Field(default="truth-social", env="S3_PREFIX")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(
        default=None, env="AWS_SECRET_ACCESS_KEY"
    )
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")

    # Multi-Source Harvester Configuration
    ENABLED_HARVESTERS: str = Field(
        default="truth_social",
        env="ENABLED_HARVESTERS",
    )  # Comma-separated list of enabled harvester source names

    # Twitter/X Configuration (Future)
    TWITTER_API_KEY: Optional[str] = Field(default=None, env="TWITTER_API_KEY")
    TWITTER_API_SECRET: Optional[str] = Field(default=None, env="TWITTER_API_SECRET")
    TWITTER_BEARER_TOKEN: Optional[str] = Field(default=None, env="TWITTER_BEARER_TOKEN")
    TWITTER_TARGET_USERS: str = Field(
        default="", env="TWITTER_TARGET_USERS"
    )  # Comma-separated Twitter usernames to monitor

    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    FILE_LOGGING: bool = Field(default=False, env="FILE_LOGGING")
    LOG_FILE_PATH: Optional[str] = Field(default=None, env="LOG_FILE_PATH")

    # Neon CLI (used by db-admin tooling, not by application code)
    NEON_PROJECT_ID: Optional[str] = Field(default=None, env="NEON_PROJECT_ID")
    NEON_ORG_ID: Optional[str] = Field(default=None, env="NEON_ORG_ID")

    class Config:
        env_file = ".env"
        case_sensitive = False

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
                raise ValueError(
                    "XAI_API_KEY is required when LLM_PROVIDER is 'grok'"
                )
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
