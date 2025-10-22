from pydantic_settings import BaseSettings
from typing import Optional, List

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
    backend_port: int = 4000
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
    
    # Allowed Domains - domains not in this list will be grouped as "Others"
    allowed_domains: List[str] = [
        'enterprise_wiki',
        'finance',
        'fund_finance',
        'hr_experts',
        'hr_management',
        'hr_payroll',
        'incident_management',
        'it_incident_management',
        'smart_home'
    ]
    
    # Dynamic domain configuration
    enable_dynamic_domains: bool = False
    last_domain_refresh: Optional[float] = None
    
    @property
    def database_url(self) -> str:
        """Construct database URL from individual components."""
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()

