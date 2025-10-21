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
    backend_port: int = 4000
    frontend_url: str = "http://localhost:1000"
    
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

    # Google Service Account Configuration (Optional - for hierarchy/aggregation features)
    google_service_account_type: Optional[str] = "service_account"
    google_project_id: Optional[str] = None
    google_private_key_id: Optional[str] = None
    google_private_key: Optional[str] = None
    google_client_email: Optional[str] = None
    google_client_id: Optional[str] = None
    google_auth_uri: Optional[str] = "https://accounts.google.com/o/oauth2/auth"
    google_token_uri: Optional[str] = "https://oauth2.googleapis.com/token"
    google_auth_provider_cert_url: Optional[str] = "https://www.googleapis.com/oauth2/v1/certs"
    google_client_cert_url: Optional[str] = None
    google_universe_domain: Optional[str] = "googleapis.com"

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

        # Check if required fields are present (password can be empty)
        if db_user is not None and db_host is not None and db_name is not None:
            # Handle empty password (common for local PostgreSQL on macOS)
            password_part = f":{db_password}" if db_password else ""
            return f"postgresql://{db_user}{password_part}@{db_host}:{db_port}/{db_name}"

        # Default to localhost for development
        return "postgresql://postgres:postgres@localhost:5432/tau_dashboard"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        # Allow extra fields for flexibility
        extra = 'allow'

settings = Settings()