"""
Jibble Sync Service - Syncs Jibble data to the local database
"""
import os
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Tuple, Optional
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError

from jibble_service import JibbleService
from database_v2 import JibblePerson, JibbleTimeEntry, JibbleEmailMapping
from google_sheets_service import GoogleSheetsService

# Load environment variables (same pattern as task_agent_service.py)
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Default Jibble email sheet URL
JIBBLE_EMAIL_SHEET_URL = os.getenv(
    "JIBBLE_EMAIL_SHEET_URL", 
    "https://docs.google.com/spreadsheets/d/12WSKMXbzSMa0e5Jy0_xQK_eV5NF4Kn9v-PKQhqhxgQQ/edit"
)

logger = logging.getLogger(__name__)


class JibbleSyncService:
    """Service for syncing Jibble data to the database"""
    
    def __init__(self, db: Session):
        self.db = db
        self.jibble = JibbleService()
    
    def sync_email_mappings(self) -> int:
        """
        Sync Jibble email mappings from Google Sheet to database
        Column A = Turing Email, Column E = Jibble Email
        
        Returns: number of mappings synced
        """
        try:
            sheets_service = GoogleSheetsService()
            sheets_service.connect()
            
            # Open the spreadsheet (sheet with Email and Jibble Emails columns)
            spreadsheet = sheets_service.client.open_by_url(JIBBLE_EMAIL_SHEET_URL)
            worksheet = spreadsheet.worksheet("Sheet1")
            
            # Get all values
            values = worksheet.get_all_values()
            
            if not values or len(values) < 2:
                logger.warning("No data found in Google Sheet for email mapping")
                return 0
            
            # Column 0 = Email (Turing), Column 4 = Jibble Emails
            synced_count = 0
            
            for row in values[1:]:  # Skip header row
                if len(row) < 5:
                    continue
                
                turing_email = row[0].strip().lower() if row[0] else ""
                jibble_email = row[4].strip().lower() if row[4] else ""
                
                if not turing_email or not jibble_email:
                    continue
                
                # Upsert the mapping
                existing = self.db.query(JibbleEmailMapping).filter_by(
                    turing_email=turing_email
                ).first()
                
                if existing:
                    existing.jibble_email = jibble_email
                    existing.last_synced = func.now()
                else:
                    mapping = JibbleEmailMapping(
                        turing_email=turing_email,
                        jibble_email=jibble_email,
                    )
                    self.db.add(mapping)
                
                synced_count += 1
            
            self.db.commit()
            logger.info(f"Synced {synced_count} email mappings from Google Sheet")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing email mappings: {e}")
            self.db.rollback()
            return 0
    
    def get_allowed_jibble_emails(self) -> Dict[str, str]:
        """
        Get mapping of jibble_email -> turing_email from database
        """
        mappings = self.db.query(JibbleEmailMapping).all()
        return {m.jibble_email: m.turing_email for m in mappings}
    
    def sync_people(self) -> int:
        """
        Sync all people from Jibble to the database
        
        Returns: number of people synced
        """
        try:
            people = self.jibble.get_people()
            synced_count = 0
            
            for person in people:
                jibble_id = person.get("id")
                if not jibble_id:
                    continue
                
                # Extract email - Jibble uses 'email' field for the person's Jibble email
                # This is the personal Gmail/email they use to log in to Jibble
                personal_email = person.get("email", "").lower() if person.get("email") else None
                work_email = person.get("workEmail", "").lower() if person.get("workEmail") else None
                
                # Get latest time entry timestamp
                latest_entry = person.get("latestTimeEntryTime")
                latest_time = None
                if latest_entry:
                    try:
                        latest_time = datetime.fromisoformat(latest_entry.replace("Z", "+00:00"))
                    except:
                        pass
                
                # Upsert person
                existing = self.db.query(JibblePerson).filter_by(jibble_id=jibble_id).first()
                
                if existing:
                    existing.full_name = person.get("fullName")
                    existing.first_name = person.get("firstName")
                    existing.last_name = person.get("lastName")
                    existing.personal_email = personal_email
                    existing.work_email = work_email
                    existing.status = person.get("status")
                    existing.latest_time_entry = latest_time
                    existing.last_synced = func.now()
                else:
                    new_person = JibblePerson(
                        jibble_id=jibble_id,
                        full_name=person.get("fullName"),
                        first_name=person.get("firstName"),
                        last_name=person.get("lastName"),
                        personal_email=personal_email,
                        work_email=work_email,
                        status=person.get("status"),
                        latest_time_entry=latest_time,
                    )
                    self.db.add(new_person)
                
                synced_count += 1
                
                # Commit in batches
                if synced_count % 500 == 0:
                    self.db.commit()
                    logger.info(f"Synced {synced_count} people so far...")
            
            self.db.commit()
            logger.info(f"Synced {synced_count} people from Jibble")
            return synced_count
            
        except Exception as e:
            logger.error(f"Error syncing people: {e}")
            self.db.rollback()
            raise
    
    def sync_time_entries(self, weeks: int = 2) -> Tuple[int, List[Dict]]:
        """
        Sync time entries from Jibble for the specified number of weeks
        Uses the TimesheetsSummary endpoint for pre-calculated daily hours
        
        Returns: (total_entries_synced, weeks_synced_details)
        """
        try:
            total_synced = 0
            weeks_details = []
            
            # Get allowed emails for filtering
            allowed_mapping = self.get_allowed_jibble_emails()
            allowed_emails = set(allowed_mapping.keys())
            
            # Create person_id -> email lookup from JibblePerson table
            people = self.db.query(JibblePerson).all()
            person_id_to_email = {}
            for p in people:
                email = p.personal_email or p.work_email
                if email:
                    person_id_to_email[p.jibble_id] = email.lower()
            
            # Sync each week
            for week_offset in range(weeks + 1):
                # Calculate week boundaries (Monday to Sunday)
                today = datetime.now()
                start_of_week = today - timedelta(days=today.weekday() + week_offset * 7)
                start_of_week = start_of_week.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
                
                # Calculate ISO week
                iso_year, iso_week, _ = start_of_week.isocalendar()
                iso_week_str = f"{iso_year}-W{iso_week:02d}"
                
                logger.info(f"Syncing time entries for {iso_week_str} ({start_of_week.date()} to {end_of_week.date()})")
                
                # Fetch pre-calculated daily hours from TimesheetsSummary
                daily_hours = self.jibble.get_timesheets_summary(start_of_week, end_of_week)
                
                week_entries = 0
                
                for person_id, data in daily_hours.items():
                    # Check if person's email is in allowed list
                    person_email = person_id_to_email.get(person_id)
                    if not person_email or person_email not in allowed_emails:
                        continue
                    
                    for date_str, hours in data.items():
                        # Skip metadata keys
                        if date_str.startswith("_"):
                            continue
                        
                        # Skip zero hours entries (optional - keeps db smaller)
                        if hours == 0:
                            continue
                        
                        try:
                            entry_date = datetime.fromisoformat(date_str)
                            
                            # Try to find existing entry
                            existing = self.db.query(JibbleTimeEntry).filter_by(
                                person_id=person_id,
                                entry_date=entry_date
                            ).first()
                            
                            if existing:
                                existing.total_hours = hours
                                existing.last_synced = func.now()
                            else:
                                new_entry = JibbleTimeEntry(
                                    person_id=person_id,
                                    entry_date=entry_date,
                                    total_hours=hours,
                                )
                                self.db.add(new_entry)
                            
                            week_entries += 1
                            
                        except IntegrityError:
                            self.db.rollback()
                            # Update existing
                            existing = self.db.query(JibbleTimeEntry).filter_by(
                                person_id=person_id,
                                entry_date=entry_date
                            ).first()
                            if existing:
                                existing.total_hours = hours
                                existing.last_synced = func.now()
                        except Exception as e:
                            logger.warning(f"Error saving entry for {person_id}/{date_str}: {e}")
                            continue
                
                self.db.commit()
                total_synced += week_entries
                
                weeks_details.append({
                    "iso_week": iso_week_str,
                    "start": start_of_week.date().isoformat(),
                    "end": end_of_week.date().isoformat(),
                    "entries": week_entries,
                })
            
            logger.info(f"Synced {total_synced} time entries across {len(weeks_details)} weeks")
            return total_synced, weeks_details
            
        except Exception as e:
            logger.error(f"Error syncing time entries: {e}")
            self.db.rollback()
            raise
    
    def full_sync(self, weeks: int = 2) -> Dict:
        """
        Perform a full sync of all Jibble data
        
        Returns: sync results summary
        """
        try:
            # First sync email mappings from Google Sheet
            logger.info("Step 1: Syncing email mappings from Google Sheet...")
            email_mappings = self.sync_email_mappings()
            
            # Then sync all people from Jibble
            logger.info("Step 2: Syncing people from Jibble...")
            people_count = self.sync_people()
            
            # Finally sync time entries
            logger.info(f"Step 3: Syncing time entries for {weeks} weeks...")
            entries_count, weeks_details = self.sync_time_entries(weeks)
            
            return {
                "success": True,
                "email_mappings_synced": email_mappings,
                "people_synced": people_count,
                "time_entries_synced": entries_count,
                "weeks_synced": weeks_details,
                "error": None,
            }
            
        except Exception as e:
            logger.error(f"Full sync failed: {e}")
            return {
                "success": False,
                "email_mappings_synced": 0,
                "people_synced": 0,
                "time_entries_synced": 0,
                "weeks_synced": [],
                "error": str(e),
            }

