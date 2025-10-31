from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional, List
from datetime import datetime, timezone
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
        "incident_management_redos",
        "incident_management_technical",
        "it_incident_management",
        "smart_home",
        "smart_home_alexa",
        "wiki_confluence"
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


def fetch_domains_from_github() -> List[dict]:
    """
    Fetch valid domain names from GitHub repo's envs folder with metadata.
    Returns list of dicts with domain name and creation date.
    """
    try:
        from github import Github

        logger.info("Fetching domains from GitHub repo envs folder...")

        # Initialize GitHub client
        g = Github(settings.github_token)
        repo = g.get_repo(settings.github_repo)

        # Get contents of envs folder
        contents = repo.get_contents("envs")

        # Filter for directories and get metadata
        domains_data = []
        for item in contents:
            if item.type == "dir":
                # Normalize domain name (replace hyphens with underscores)
                normalized_name = item.name.replace('-', '_')
                
                # Get the commit that created this folder to find creation date
                try:
                    commits = repo.get_commits(path=f"envs/{item.name}")
                    # Get the oldest commit (first commit that added this path)
                    oldest_commit = list(commits)[-1] if commits.totalCount > 0 else None
                    created_at = oldest_commit.commit.author.date if oldest_commit else None
                except Exception as e:
                    logger.warning(f"Could not get creation date for {item.name}: {str(e)}")
                    created_at = None
                
                domains_data.append({
                    'name': normalized_name,
                    'original_name': item.name,
                    'created_at': created_at
                })
        
        # Sort by creation date descending (newest first)
        domains_data.sort(key=lambda x: x['created_at'] or datetime.min.replace(tzinfo=timezone.utc), reverse=True)
        
        domain_names = [d['name'] for d in domains_data]
        logger.info(f"Discovered {len(domain_names)} domains from GitHub: {', '.join(domain_names)}")

        return domains_data

    except Exception as e:
        logger.error(f"Failed to fetch domains from GitHub: {str(e)}")
        logger.info("Using fallback hardcoded domain list")
        # Return fallback as dict format
        return [{'name': d, 'original_name': d, 'created_at': None} for d in settings.allowed_domains]


def update_allowed_domains(force: bool = False) -> bool:
    """
    Update the allowed_domains list from GitHub and sync to database.

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
        # Fetch domains from GitHub with metadata
        domains_data = fetch_domains_from_github()

        if domains_data:
            # Extract just the names for settings
            domain_names = [d['name'] for d in domains_data]
            
            # Update the settings
            settings.allowed_domains = domain_names
            settings.recognized_domains = domain_names
            settings.last_domain_refresh = time.time()

            # Sync to database
            try:
                from database import SessionLocal, Domain
                db = SessionLocal()
                try:
                    for domain_data in domains_data:
                        domain_name = domain_data['name']
                        created_at = domain_data['created_at']
                        
                        # Check if domain exists
                        existing_domain = db.query(Domain).filter_by(domain_name=domain_name).first()
                        
                        if not existing_domain:
                            # Create new domain entry
                            new_domain = Domain(
                                domain_name=domain_name,
                                display_name=domain_name.replace('_', ' ').title(),
                                description=f"Domain: {domain_data['original_name']}",
                                is_active=True,
                                github_created_at=created_at
                            )
                            db.add(new_domain)
                            logger.debug(f"Added new domain to DB: {domain_name}")
                        else:
                            # Update existing domain to ensure it's active and set creation date if missing
                            existing_domain.is_active = True
                            if not existing_domain.github_created_at and created_at:
                                existing_domain.github_created_at = created_at
                    
                    db.commit()
                    logger.info(f"Synced {len(domains_data)} domains to database")
                finally:
                    db.close()
            except Exception as db_error:
                logger.warning(f"Failed to sync domains to database: {str(db_error)}")
                # Continue anyway - in-memory list is updated

            logger.info(f"Updated allowed domains: {len(domain_names)} domains")
            return True
        else:
            logger.warning("No domains fetched from GitHub, keeping existing list")
            return False

    except Exception as e:
        logger.error(f"Error updating domains: {str(e)}")
        return False