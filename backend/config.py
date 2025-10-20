from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
import logging

logger = logging.getLogger(__name__)

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

    # Allowed/Recognized domains (fallback list - will be dynamically updated from GitHub)
    # These domains will be shown or recognized; others may be grouped as "Others"
    allowed_domains: List[str] = [
        "enterprise_wiki",
        "finance",
        "fund_finance",
        "hr_experts",
        "hr_management",
        "hr_payroll",
        "hr_talent_management",
        "incident_management",
        "it_incident_management",
        "smart_home"
    ]
    recognized_domains: List[str] = allowed_domains
    
    # Dynamic domain discovery settings
    enable_dynamic_domains: bool = True  # Set to False to use hardcoded list only
    last_domain_refresh: Optional[float] = None  # Timestamp of last refresh

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


def fetch_domains_from_github() -> List[str]:
    """
    Fetch valid domain names from GitHub repo's envs folder.
    Returns list of domain names (folder names in envs/).
    """
    try:
        from github import Github
        
        logger.info("Fetching domains from GitHub repo envs folder...")
        
        # Initialize GitHub client
        g = Github(settings.github_token)
        repo = g.get_repo(settings.github_repo)
        
        # Get contents of envs folder
        contents = repo.get_contents("envs")
        
        # Filter for directories only
        domains = [
            item.name for item in contents 
            if item.type == "dir"
        ]
        
        # Normalize domain names (replace hyphens with underscores)
        normalized_domains = [domain.replace('-', '_') for domain in domains]
        
        logger.info(f"Discovered {len(normalized_domains)} domains from GitHub: {', '.join(normalized_domains)}")
        
        return normalized_domains
        
    except Exception as e:
        logger.error(f"Failed to fetch domains from GitHub: {str(e)}")
        logger.info("Using fallback hardcoded domain list")
        return settings.allowed_domains


def update_allowed_domains(force: bool = False) -> bool:
    """
    Update the allowed_domains list from GitHub.
    
    Args:
        force: If True, update even if dynamic domains are disabled
        
    Returns:
        True if update was successful, False otherwise
    """
    import time
    
    if not settings.enable_dynamic_domains and not force:
        logger.debug("Dynamic domain discovery is disabled")
        return False
    
    try:
        # Fetch domains from GitHub
        new_domains = fetch_domains_from_github()
        
        if new_domains:
            # Update the settings
            settings.allowed_domains = new_domains
            settings.recognized_domains = new_domains
            settings.last_domain_refresh = time.time()
            
            logger.info(f"Updated allowed domains: {len(new_domains)} domains")
            return True
        else:
            logger.warning("No domains fetched from GitHub, keeping existing list")
            return False
            
    except Exception as e:
        logger.error(f"Error updating domains: {str(e)}")
        return False