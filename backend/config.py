from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings - loaded from environment variables or .env file
    
    Pydantic-settings automatically reads from:
    1. Environment variables (case-insensitive)
    2. .env file (specified in Config.env_file)
    
    Required fields (no default): GITHUB_TOKEN, GITHUB_REPO
    """
    
    # Database - override in .env for production
    database_url: str = "postgresql://postgres:postgres@localhost/tau_dashboard"
    
    # GitHub - REQUIRED: Must be set via environment variables or .env file
    github_token: str  # No default = REQUIRED
    github_repo: str   # No default = REQUIRED
    
    # Redis - optional
    redis_url: Optional[str] = "redis://localhost:6379"
    
    # Security - Change in production
    secret_key: str = "dev-secret-key-CHANGE-IN-PRODUCTION"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

