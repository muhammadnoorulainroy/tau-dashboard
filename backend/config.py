from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List

class Settings(BaseSettings):
    """
    Application settings - loaded from environment variables or .env file
    
    Pydantic-settings automatically reads from:
    1. Environment variables (case-insensitive)
    2. .env file (specified in Config.env_file)
    
    Supports both:
    - database_url as single string
    - Individual DB components (db_host, db_user, etc.)
    """
    
    # Server Configuration
    backend_host: str = "0.0.0.0"
    backend_port: int = 8000
    frontend_url: str = "http://localhost:3000"
    
    # Database Configuration - Can be provided as single URL or individual components
    database_url: Optional[str] = None
    
    # Individual DB components (optional if database_url is provided)
    db_host: Optional[str] = None
    db_port: int = 5432
    db_user: Optional[str] = None
    db_password: Optional[str] = None
    db_name: Optional[str] = None
    
    # GitHub - REQUIRED
    github_token: str
    github_repo: str
    
    # Redis (optional)
    redis_url: str = "redis://localhost:6379"
    
    # Security
    secret_key: str = "your-secret-key-here"

    # Google Service Account Configuration
    google_service_account_type: str = "service_account"
    google_project_id: str
    google_private_key_id: str
    google_private_key: str
    google_client_email: str
    google_client_id: str
    google_auth_uri: str = "https://accounts.google.com/o/oauth2/auth"
    google_token_uri: str = "https://oauth2.googleapis.com/token"
    google_auth_provider_cert_url: str = "https://www.googleapis.com/oauth2/v1/certs"
    google_client_cert_url: str
    google_universe_domain: str = "googleapis.com"

    # Allowed/Recognized domains (as in both branches)
    # These domains will be shown or recognized; others may be grouped as "Others"
    allowed_domains: List[str] = [
        "enterprise_wiki",
        "finance",
        "fund_finance",
        "hr_experts",
        "hr_management",
        "hr_payroll",
        "incident_management",
        "it_incident_management",
        "smart_home"
    ]
    recognized_domains: List[str] = allowed_domains

    @validator('database_url', always=True, pre=False)
    def construct_database_url(cls, v, values):
        """Construct database URL from components if not provided directly."""
        if v:
            return v

        db_user = values.get('db_user')
        db_password = values.get('db_password')
        db_host = values.get('db_host')
        db_port = values.get('db_port', 5432)
        db_name = values.get('db_name')

        if all([db_user, db_password, db_host, db_name]):
            return f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

        # Default to localhost for development
        return "postgresql://postgres:postgres@localhost:5432/tau_dashboard"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Allow extra fields for flexibility
        extra = 'allow'

settings = Settings()