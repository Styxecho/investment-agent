"""
Dashboard Backend Configuration
"""
import os
from pathlib import Path
from pydantic_settings import BaseSettings

# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.resolve()

# Database path (reuse existing database)
DB_PATH = PROJECT_ROOT / "data_external" / "db" / "external_data.db"

class Settings(BaseSettings):
    """Application settings"""
    
    # API
    API_V1_PREFIX: str = "/api/v1"
    
    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3011", "http://127.0.0.1:3011"]
    
    # Database
    DATABASE_URL: str = f"sqlite:///{DB_PATH}"
    
    # Cache
    CACHE_TTL: int = 300  # 5 minutes
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        extra = "ignore"  # Ignore extra env vars from project's .env

settings = Settings()
