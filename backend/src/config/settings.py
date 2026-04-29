"""
Configuration module for SmartRetail-Sync backend.
Manages both local (.env) and Azure Key Vault configurations.
"""

import os
from typing import Optional
from dotenv import load_dotenv
from pydantic_settings import BaseSettings
import logging

logger = logging.getLogger(__name__)


class Settings(BaseSettings):
    """
    Application settings with support for both .env files and Azure Key Vault.
    
    Priority order:
    1. Environment variables (from Azure Key Vault in production)
    2. .env file (local development)
    3. Default values
    """
    
    # ==========================================
    # APPLICATION SETTINGS
    # ==========================================
    APP_NAME: str = "SmartRetail-Sync"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = False
    ENVIRONMENT: str = "local"  # local | development | staging | production
    LOG_LEVEL: str = "INFO"
    
    # ==========================================
    # DATABASE SETTINGS
    # ==========================================
    DB_HOST: Optional[str] = None
    DB_PORT: int = 5432
    DB_NAME: str = "smartretail_db"
    DB_USER: Optional[str] = None
    DB_PASSWORD: Optional[str] = None
    
    # Connection pool settings
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # ==========================================
    # AZURE KEY VAULT SETTINGS
    # ==========================================
    AZURE_KEYVAULT_URL: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    
    # ==========================================
    # API SETTINGS
    # ==========================================
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_PREFIX: str = "/api/v1"
    CORS_ORIGINS: list = [
        "http://localhost:3000",
        "http://localhost:8000",
        "https://app.powerbi.com",
    ]
    
    # ==========================================
    # SECURITY SETTINGS
    # ==========================================
    SECRET_KEY: Optional[str] = None
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    
    # ==========================================
    # MONITORING & LOGGING
    # ==========================================
    ENABLE_TELEMETRY: bool = True
    APPLICATION_INSIGHTS_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


def load_settings() -> Settings:
    """
    Load settings from .env file if in local environment.
    """
    # Load .env file in local development
    if os.getenv("ENVIRONMENT", "local") == "local":
        env_file_path = os.path.join(os.path.dirname(__file__), "../../.env")
        if os.path.exists(env_file_path):
            load_dotenv(env_file_path)
            logger.info("Loaded .env file from local environment")
    
    return Settings()


def get_database_url(settings: Settings) -> str:
    """
    Construct PostgreSQL database URL.
    
    Format: postgresql://user:password@host:port/database
    """
    if not all([settings.DB_HOST, settings.DB_USER, settings.DB_PASSWORD]):
        raise ValueError(
            "Database credentials not configured. "
            "Set DB_HOST, DB_USER, DB_PASSWORD in .env or Azure Key Vault"
        )
    
    return (
        f"postgresql://{settings.DB_USER}:{settings.DB_PASSWORD}@"
        f"{settings.DB_HOST}:{settings.DB_PORT}/{settings.DB_NAME}"
    )


# Global settings instance
settings = load_settings()
