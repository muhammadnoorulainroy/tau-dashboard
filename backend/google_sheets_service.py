"""
Google Sheets Service - Fetch and merge data from Google Sheets
"""
import logging
import json
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import gspread
from google.oauth2.service_account import Credentials
from sqlalchemy.orm import Session
from database import DeveloperHierarchy
from config import settings

logger = logging.getLogger(__name__)

class GoogleSheetsService:
    def __init__(self):
        """Initialize Google Sheets service with service account credentials from environment"""
        self.client = None
        
        # Google Sheets URLs
        self.sheet1_url = "https://docs.google.com/spreadsheets/d/1V5luny0xnVcvUcfAItjQj4XC56MU1i3UUjCAVwS9bPA/edit?gid=1653135311#gid=1653135311"
        self.sheet2_url = "https://docs.google.com/spreadsheets/d/12WSKMXbzSMa0e5Jy0_xQK_eV5NF4Kn9v-PKQhqhxgQQ/edit?gid=0#gid=0"
    
    def _get_service_account_info(self) -> Dict:
        """Build service account info from environment variables"""
        if not settings.google_private_key:
            raise ValueError("Google Sheets credentials not configured. Set GOOGLE_* environment variables.")
        
        # Replace literal \n in the private key with actual newlines
        private_key = settings.google_private_key.replace('\\n', '\n')
        
        return {
            "type": settings.google_service_account_type,
            "project_id": settings.google_project_id,
            "private_key_id": settings.google_private_key_id,
            "private_key": private_key,
            "client_email": settings.google_client_email,
            "client_id": settings.google_client_id,
            "auth_uri": settings.google_auth_uri,
            "token_uri": settings.google_token_uri,
            "auth_provider_x509_cert_url": settings.google_auth_provider_cert_url,
            "client_x509_cert_url": settings.google_client_cert_url,
            "universe_domain": settings.google_universe_domain
        }
    
    def connect(self):
        """Connect to Google Sheets API using credentials from environment variables"""
        try:
            scopes = [
                'https://www.googleapis.com/auth/spreadsheets.readonly',
                'https://www.googleapis.com/auth/drive.readonly'
            ]
            
            # Get service account info from environment variables
            service_account_info = self._get_service_account_info()
            
            # Create credentials from the dictionary
            credentials = Credentials.from_service_account_info(
                service_account_info,
                scopes=scopes
            )
            
            self.client = gspread.authorize(credentials)
            logger.info("Successfully connected to Google Sheets API using environment credentials")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to Google Sheets: {e}")
            raise
    
    def fetch_sheet1_data(self) -> List[Dict]:
        """
        Fetch data from Sheet 1 (Amazon Agentic List)
        Columns: Turing Email, Role, Pod Lead, Calibrator
        """
        try:
            if not self.client:
                self.connect()
            
            # Open spreadsheet and get the specific tab
            spreadsheet = self.client.open_by_url(self.sheet1_url)
            worksheet = spreadsheet.worksheet("Amazon Agentic List")
            
            # Get all records as list of dictionaries
            records = worksheet.get_all_records()
            
            logger.info(f"Fetched {len(records)} records from Sheet 1")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching Sheet 1 data: {e}")
            raise
    
    def fetch_sheet2_data(self) -> List[Dict]:
        """
        Fetch data from Sheet 2 (GitHub users)
        Columns: Email, Github User
        """
        try:
            if not self.client:
                self.connect()
            
            # Open spreadsheet and get the specific tab
            spreadsheet = self.client.open_by_url(self.sheet2_url)
            worksheet = spreadsheet.worksheet("Sheet1")
            
            # Get all records as list of dictionaries
            records = worksheet.get_all_records()
            
            logger.info(f"Fetched {len(records)} records from Sheet 2")
            return records
            
        except Exception as e:
            logger.error(f"Error fetching Sheet 2 data: {e}")
            raise
    
    def merge_sheets_data(self) -> List[Dict]:
        """
        Merge data from both sheets based on email and calculate hierarchy
        
        Transformation logic:
        - For Trainers: POD Lead = their Lead, Calibrator = Lead's Lead
        - For POD Leads: POD Lead = themselves, Calibrator = their Lead
        - For Calibrators: Calibrator = themselves
        
        Returns list of dicts with:
        - turing_email
        - github_user
        - role
        - pod_lead_email
        - calibrator_email
        """
        try:
            sheet1_data = self.fetch_sheet1_data()
            sheet2_data = self.fetch_sheet2_data()
            
            # Create mapping from email to github username
            email_to_github = {}
            for row in sheet2_data:
                # Handle various possible column names
                email = row.get('Email') or row.get('email') or row.get('       Email', '').strip()
                github_user = row.get('Github User') or row.get('github_user') or row.get('GitHub User', '')
                
                if email and github_user:
                    email_to_github[email.lower().strip()] = github_user.strip()
            
            logger.info(f"Created email-to-github mapping with {len(email_to_github)} entries")
            
            # Create email-to-record lookup for hierarchy resolution
            email_lookup = {}
            for row in sheet1_data:
                turing_email = (row.get('Turing Email') or row.get('turing_email', '')).strip().lower()
                if turing_email:
                    email_lookup[turing_email] = row
            
            logger.info(f"Created email lookup with {len(email_lookup)} entries")
            
            # Define allowed roles (normalize to these)
            allowed_roles = ['Team Leader', 'Trainer', 'Calibrator', 'Pod Lead']
            
            # Merge data and calculate hierarchy
            merged_data = []
            for row in sheet1_data:
                turing_email = (row.get('Turing Email') or row.get('turing_email', '')).strip().lower()
                
                if not turing_email:
                    continue
                
                # Get status from Google Sheets
                status = (row.get('Status') or row.get('status', '')).strip()
                
                # Include ALL developers regardless of status (status is stored in DB)
                # No status filter - sync all trainers
                
                role = (row.get('Role') or row.get('role', '')).strip()
                
                # Normalize role - if not in allowed list, set to 'Others'
                if role not in allowed_roles:
                    role = 'Others'
                
                lead_email = (row.get('Lead') or row.get('lead', '')).strip().lower()
                
                pod_lead_email = None
                calibrator_email = None
                
                if role.lower() == 'trainer':
                    # Trainer's Lead is their POD Lead
                    pod_lead_email = lead_email if lead_email else None
                    
                    # Calibrator is the Lead of the POD Lead
                    if lead_email and lead_email in email_lookup:
                        pod_lead_record = email_lookup[lead_email]
                        pod_lead_lead = (pod_lead_record.get('Lead') or pod_lead_record.get('lead', '')).strip().lower()
                        calibrator_email = pod_lead_lead if pod_lead_lead else None
                
                elif role.lower() == 'pod lead':
                    # POD Lead's own email is their pod_lead_email
                    pod_lead_email = turing_email
                    # Their Lead is their Calibrator
                    calibrator_email = lead_email if lead_email else None
                
                elif role.lower() == 'calibrator':
                    # Calibrator's own email is their calibrator_email
                    calibrator_email = turing_email
                    # Could optionally set pod_lead_email if needed
                
                merged_data.append({
                    'turing_email': turing_email,
                    'github_user': email_to_github.get(turing_email, ''),
                    'role': role,
                    'status': status,
                    'pod_lead_email': pod_lead_email,
                    'calibrator_email': calibrator_email
                })
            
            logger.info(f"Merged {len(merged_data)} active records with calculated hierarchy")
            return merged_data
            
        except Exception as e:
            logger.error(f"Error merging sheets data: {e}")
            raise
    
    def sync_to_database(self, db: Session) -> Tuple[int, int, int]:
        """
        Sync hierarchy data to DeveloperHierarchy table
        
        Returns: (inserted_count, updated_count, error_count)
        """
        try:
            merged_data = self.merge_sheets_data()
            
            inserted_count = 0
            updated_count = 0
            error_count = 0
            
            # Track to handle duplicates (keep first occurrence)
            seen_github_users = set()
            seen_emails = set()
            
            for item in merged_data:
                try:
                    github_user = item.get('github_user', '').strip() or None  # Convert empty string to None
                    turing_email = item.get('turing_email', '').strip()
                    
                    # Skip if missing critical field (turing_email is required, github_user is optional)
                    if not turing_email:
                        logger.warning(f"Skipping record with missing turing_email: {item}")
                        error_count += 1
                        continue
                    
                    # Skip duplicate emails (primary identifier)
                    if turing_email in seen_emails:
                        logger.warning(f"Skipping duplicate email in batch: {turing_email} ({github_user})")
                        error_count += 1
                        continue
                    
                    # Skip duplicate github_user (only if not None)
                    if github_user and github_user in seen_github_users:
                        logger.warning(f"Skipping duplicate GitHub username in batch: {github_user} ({turing_email})")
                        error_count += 1
                        continue
                    
                    seen_emails.add(turing_email)
                    if github_user:
                        seen_github_users.add(github_user)
                    
                    # Check if record exists (by email, which is unique)
                    existing = db.query(DeveloperHierarchy).filter_by(turing_email=turing_email).first()
                    
                    if existing:
                        # Update existing record
                        existing.github_user = github_user  # Update github_user (might be None)
                        existing.role = item.get('role')
                        existing.status = item.get('status')
                        existing.pod_lead_email = item.get('pod_lead_email')
                        existing.calibrator_email = item.get('calibrator_email')
                        updated_count += 1
                    else:
                        # Insert new record
                        new_hierarchy = DeveloperHierarchy(
                            github_user=github_user,  # Can be None
                            turing_email=turing_email,
                            role=item.get('role'),
                            status=item.get('status'),
                            pod_lead_email=item.get('pod_lead_email'),
                            calibrator_email=item.get('calibrator_email')
                        )
                        db.add(new_hierarchy)
                        inserted_count += 1
                    
                except Exception as e:
                    logger.error(f"Error processing record {item}: {e}")
                    error_count += 1
                    continue
            
            db.commit()
            logger.info(f"Sync complete: {inserted_count} inserted, {updated_count} updated, {error_count} errors")
            
            return (inserted_count, updated_count, error_count)
            
        except Exception as e:
            logger.error(f"Error syncing to database: {e}")
            db.rollback()
            raise

