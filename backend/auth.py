"""
Google OAuth 2.0 Authentication for TAU Dashboard
Implements secure token-based authentication with Google Sign-In
Only allows users with Turing emails from the database
"""

from fastapi import Depends, HTTPException, status, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from google.oauth2 import id_token
from google.auth.transport import requests
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict
import jwt
import logging

from config import settings

logger = logging.getLogger(__name__)

# Additional allowed emails (admins/special access)
ADDITIONAL_ALLOWED_EMAILS = [
    'noman.s@turing.com',
    'ain.m@turing.com',
    'tushar.a@turing.com',
    'tushar.thote@turing.com',
    'raghav.bala@turing.com',
    'satheesh.palaninathan@turing.com'
]

# Security scheme for Bearer token
security = HTTPBearer()

# JWT Configuration
JWT_SECRET = settings.secret_key
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 24

# In-memory session store (in production, use Redis or database)
active_sessions: Dict[str, dict] = {}


def is_email_allowed(email: str) -> bool:
    """
    Check if email is allowed to access the dashboard
    
    Checks:
    1. If email is in ADDITIONAL_ALLOWED_EMAILS list
    2. If email exists in DeveloperHierarchy table (turing_email)
    3. If email exists in Users table
    
    Args:
        email: Email address to check
        
    Returns:
        True if allowed, False otherwise
    """
    # Check additional allowed emails first
    if email.lower() in [e.lower() for e in ADDITIONAL_ALLOWED_EMAILS]:
        logger.info(f"Email {email} found in additional allowed list")
        return True
    
    # Check against database
    try:
        from database import SessionLocal, DeveloperHierarchy, User
        db = SessionLocal()
        
        try:
            # Check if email exists in DeveloperHierarchy table
            hierarchy_user = db.query(DeveloperHierarchy).filter(
                DeveloperHierarchy.turing_email.ilike(email)
            ).first()
            
            if hierarchy_user:
                logger.info(f"Email {email} found in DeveloperHierarchy table")
                return True
            
            # Check if email exists in Users table
            user = db.query(User).filter(
                User.email.ilike(email)
            ).first()
            
            if user:
                logger.info(f"Email {email} found in Users table")
                return True
            
            logger.warning(f"Email {email} not found in any allowed list")
            return False
            
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Error checking email authorization: {str(e)}")
        # In case of database error, deny access
        return False


def verify_google_token(token: str) -> Optional[dict]:
    """
    Verify Google ID token and extract user information
    Only allows users with authorized Turing emails
    
    Args:
        token: Google ID token from frontend
        
    Returns:
        User info dict if valid and authorized, None otherwise
    """
    # Skip Google OAuth if client ID is not configured
    if not settings.app_google_client_id:
        logger.warning("Google OAuth is not configured (APP_GOOGLE_CLIENT_ID missing)")
        return None
    
    try:
        # Verify the token with Google
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            settings.app_google_client_id
        )
        
        # Verify the issuer
        if idinfo['iss'] not in ['accounts.google.com', 'https://accounts.google.com']:
            logger.warning(f"Invalid token issuer: {idinfo['iss']}")
            return None
        
        # Extract user information
        user_info = {
            'email': idinfo['email'],
            'name': idinfo.get('name', ''),
            'picture': idinfo.get('picture', ''),
            'sub': idinfo['sub'],  # Google user ID
            'email_verified': idinfo.get('email_verified', False)
        }
        
        # Check if email is authorized
        if not is_email_allowed(user_info['email']):
            logger.warning(f"Unauthorized access attempt by: {user_info['email']}")
            return None
        
        logger.info(f"Successfully verified and authorized Google token for user: {user_info['email']}")
        return user_info
        
    except ValueError as e:
        logger.error(f"Invalid Google token: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error verifying Google token: {str(e)}")
        return None


def create_access_token(user_info: dict) -> str:
    """
    Create JWT access token for authenticated user
    
    Args:
        user_info: User information from Google
        
    Returns:
        JWT token string
    """
    expire = datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    
    payload = {
        'sub': user_info['email'],
        'name': user_info['name'],
        'picture': user_info['picture'],
        'google_id': user_info['sub'],
        'exp': expire,
        'iat': datetime.now(timezone.utc)
    }
    
    token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)
    
    # Store in active sessions
    active_sessions[token] = {
        'user_info': user_info,
        'created_at': datetime.now(timezone.utc),
        'expires_at': expire
    }
    
    return token


def verify_access_token(token: str) -> Optional[dict]:
    """
    Verify JWT access token
    
    Args:
        token: JWT token string
        
    Returns:
        User info dict if valid, None otherwise
    """
    try:
        # Check if token exists in active sessions
        if token not in active_sessions:
            logger.warning("Token not found in active sessions")
            return None
        
        # Verify JWT signature and expiration
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        
        # Check if session is still valid
        session = active_sessions[token]
        if datetime.now(timezone.utc) > session['expires_at']:
            # Remove expired session
            del active_sessions[token]
            logger.info("Session expired and removed")
            return None
        
        return {
            'email': payload['sub'],
            'name': payload.get('name', ''),
            'picture': payload.get('picture', ''),
            'google_id': payload.get('google_id', '')
        }
        
    except jwt.ExpiredSignatureError:
        logger.warning("Token has expired")
        # Clean up expired session
        if token in active_sessions:
            del active_sessions[token]
        return None
    except jwt.JWTError as e:
        logger.error(f"JWT error: {str(e)}")
        return None
    except Exception as e:
        logger.error(f"Error verifying token: {str(e)}")
        return None


def revoke_token(token: str) -> bool:
    """
    Revoke/logout a token
    
    Args:
        token: JWT token to revoke
        
    Returns:
        True if revoked successfully
    """
    if token in active_sessions:
        del active_sessions[token]
        logger.info(f"Token revoked successfully")
        return True
    return False


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    """
    Dependency to get current authenticated user
    
    Args:
        credentials: HTTP Bearer token from request
        
    Returns:
        User info dict
        
    Raises:
        HTTPException: If token is invalid or expired
    """
    token = credentials.credentials
    
    user_info = verify_access_token(token)
    
    if user_info is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired authentication token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    return user_info


async def optional_auth(request: Request) -> Optional[dict]:
    """
    Optional authentication - doesn't fail if no token provided
    Used for endpoints that work with or without authentication
    
    Args:
        request: FastAPI request object
        
    Returns:
        User info dict if authenticated, None otherwise
    """
    auth_header = request.headers.get('Authorization')
    
    if not auth_header or not auth_header.startswith('Bearer '):
        return None
    
    token = auth_header.split(' ')[1]
    return verify_access_token(token)


def get_active_sessions_count() -> int:
    """Get count of active sessions"""
    # Clean up expired sessions
    now = datetime.now(timezone.utc)
    expired_tokens = [
        token for token, session in active_sessions.items()
        if now > session['expires_at']
    ]
    for token in expired_tokens:
        del active_sessions[token]
    
    return len(active_sessions)

