from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """
    Application settings - loaded from environment variables or .env file
    
    Pydantic-settings automatically reads from:
    1. Environment variables (case-insensitive)
    2. .env file (specified in Config.env_file)
    
    Required fields (no default): GITHUB_TOKEN, GITHUB_REPO, DB_*
    """
    
    # Server Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    
    # Database Configuration - REQUIRED
    db_host: str
    db_port: int = 5432
    db_user: str
    db_password: str
    db_name: str
    
    # GitHub - REQUIRED: Must be set via environment variables or .env file
    github_token: str
    github_repo: str
    
    # Security - REQUIRED
    secret_key: str
    
    @property
    def database_url(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

