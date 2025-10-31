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
project_root = os.path.dirname(os.path.dirname(current_dir))  # Go up two levels from shit/config/
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
        default="sqlite:///./shitpost_alpha.db",
        env="DATABASE_URL"
    )
    
    # LLM Configuration
    OPENAI_API_KEY: Optional[str] = Field(default=None, env="OPENAI_API_KEY")
    ANTHROPIC_API_KEY: Optional[str] = Field(default=None, env="ANTHROPIC_API_KEY")
    LLM_PROVIDER: str = Field(default="openai", env="LLM_PROVIDER")  # openai, anthropic
    LLM_MODEL: str = Field(default="gpt-4", env="LLM_MODEL")
    
    # Truth Social Shitpost Configuration
    TRUTH_SOCIAL_USERNAME: str = Field(
        default="realDonaldTrump",
        env="TRUTH_SOCIAL_USERNAME"
    )
    TRUTH_SOCIAL_SHITPOST_INTERVAL: int = Field(
        default=30,
        env="TRUTH_SOCIAL_SHITPOST_INTERVAL"
    )  # seconds between shitpost harvests
    
    # Analysis Configuration
    CONFIDENCE_THRESHOLD: float = Field(
        default=0.7,
        env="CONFIDENCE_THRESHOLD"
    )
    MAX_SHITPOST_LENGTH: int = Field(
        default=4000,
        env="MAX_SHITPOST_LENGTH"
    )
    
    # System Launch Configuration
    SYSTEM_LAUNCH_DATE: str = Field(
        default="2025-01-01T00:00:00Z",
        env="SYSTEM_LAUNCH_DATE"
    )
    
    # SMS/Alerting Configuration (Phase 2)
    TWILIO_ACCOUNT_SID: Optional[str] = Field(default=None, env="TWILIO_ACCOUNT_SID")
    TWILIO_AUTH_TOKEN: Optional[str] = Field(default=None, env="TWILIO_AUTH_TOKEN")
    TWILIO_PHONE_NUMBER: Optional[str] = Field(default=None, env="TWILIO_PHONE_NUMBER")
    
    # ScrapeCreators API Configuration
    SCRAPECREATORS_API_KEY: Optional[str] = Field(default=None, env="SCRAPECREATORS_API_KEY")
    
    # S3 Data Lake Configuration
    S3_BUCKET_NAME: str = Field(default="shitpost-alpha-raw-data", env="S3_BUCKET_NAME")
    S3_PREFIX: str = Field(default="truth-social", env="S3_PREFIX")
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None, env="AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None, env="AWS_SECRET_ACCESS_KEY")
    AWS_REGION: str = Field(default="us-east-1", env="AWS_REGION")
    
    # Logging
    LOG_LEVEL: str = Field(default="INFO", env="LOG_LEVEL")
    FILE_LOGGING: bool = Field(default=False, env="FILE_LOGGING")
    LOG_FILE_PATH: Optional[str] = Field(default=None, env="LOG_FILE_PATH")
    
    class Config:
        env_file = ".env"
        case_sensitive = False
    
    def get_llm_api_key(self) -> str:
        """Get the appropriate LLM API key based on provider."""
        if self.LLM_PROVIDER == "openai":
            if not self.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY is required when LLM_PROVIDER is 'openai'")
            return self.OPENAI_API_KEY
        elif self.LLM_PROVIDER == "anthropic":
            if not self.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY is required when LLM_PROVIDER is 'anthropic'")
            return self.ANTHROPIC_API_KEY
        else:
            raise ValueError(f"Unsupported LLM provider: {self.LLM_PROVIDER}")
    
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
