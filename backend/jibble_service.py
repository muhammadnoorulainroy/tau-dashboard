"""
Jibble API Service - Handles authentication and API calls to Jibble
"""
import logging
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Any
from config import settings

logger = logging.getLogger(__name__)


class JibbleService:
    """Service for interacting with Jibble API"""
    
    def __init__(self):
        # Support both naming conventions
        self.client_id = settings.jibble_client_id or settings.jibble_api_key
        self.client_secret = settings.jibble_client_secret or settings.jibble_api_secret
        self.base_url = settings.jibble_api_url
        self.time_tracking_url = settings.jibble_time_tracking_url
        self.access_token: Optional[str] = None
        self.token_expires_at: Optional[datetime] = None
    
    def _get_access_token(self) -> str:
        """Get OAuth2 access token using client credentials flow"""
        # Return cached token if still valid
        if self.access_token and self.token_expires_at and datetime.now() < self.token_expires_at:
            return self.access_token
        
        if not self.client_id or not self.client_secret:
            raise ValueError("Jibble client_id and client_secret are required")
        
        token_url = "https://identity.prod.jibble.io/connect/token"
        
        payload = {
            "grant_type": "client_credentials",
            "client_id": self.client_id,
            "client_secret": self.client_secret,
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded",
        }
        
        try:
            response = requests.post(token_url, data=payload, headers=headers, timeout=30)
            response.raise_for_status()
            
            data = response.json()
            self.access_token = data["access_token"]
            expires_in = data.get("expires_in", 3600)
            self.token_expires_at = datetime.now() + timedelta(seconds=expires_in - 60)
            
            logger.info("Successfully obtained Jibble access token")
            return self.access_token
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Failed to get Jibble access token: {e}")
            raise
    
    def _make_request(self, endpoint: str, method: str = "GET", params: Dict = None, 
                      base_url: str = None) -> Dict:
        """Make authenticated request to Jibble API"""
        token = self._get_access_token()
        url = f"{base_url or self.base_url}/{endpoint}"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
        
        try:
            response = requests.request(method, url, headers=headers, params=params, timeout=60)
            
            if response.status_code == 404:
                logger.warning(f"Jibble API 404 for {endpoint}")
                return {"value": []}
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Jibble API error for {endpoint}: {e}")
            raise
    
    def get_people(self, page_size: int = 1000, max_pages: int = 25) -> List[Dict]:
        """
        Fetch all people from Jibble with pagination
        Uses OData $skip and $top parameters
        """
        all_people = []
        skip = 0
        
        for page in range(max_pages):
            params = {
                "$top": page_size,
                "$skip": skip,
            }
            
            try:
                data = self._make_request("People", params=params)
                people = data.get("value", [])
                
                if not people:
                    logger.info(f"No more people at page {page + 1} (skip={skip})")
                    break
                
                all_people.extend(people)
                logger.info(f"Fetched page {page + 1}: {len(people)} people (total: {len(all_people)})")
                
                if len(people) < page_size:
                    break
                
                skip += page_size
                
            except Exception as e:
                logger.error(f"Error fetching people page {page + 1}: {e}")
                break
        
        logger.info(f"Total people fetched: {len(all_people)}")
        return all_people
    
    def get_time_entries(self, start_date: datetime, end_date: datetime, 
                         person_ids: List[str] = None, max_pages: int = 100) -> List[Dict]:
        """
        Fetch time entries (clock in/out events) from Jibble
        Uses the time-tracking.prod.jibble.io endpoint
        
        Based on Jibble API docs:
        - $filter=(belongsToDate ge 2024-06-10 and belongsToDate lt 2024-06-13)
        - Uses 'lt' (less than) not 'le' (less than or equal)
        """
        start_str = start_date.strftime('%Y-%m-%d')
        # Add 1 day for 'lt' (less than) comparison to include end_date
        end_plus_one = (end_date + timedelta(days=1)).strftime('%Y-%m-%d')
        
        # Use parentheses format as per API docs
        filter_expr = f"(belongsToDate ge {start_str} and belongsToDate lt {end_plus_one})"
        
        all_entries = []
        page_size = 100  # Use smaller page size for reliability
        
        for page in range(max_pages):
            params = {
                "$filter": filter_expr,
                "$top": page_size,
                "$skip": page * page_size,
                "$select": "id,type,time,localTime,belongsToDate,personId",
            }
            
            try:
                data = self._make_request("TimeEntries", params=params, 
                                          base_url=self.time_tracking_url)
                entries = data.get("value", [])
                
                if not entries:
                    break
                    
                all_entries.extend(entries)
                logger.info(f"Fetched page {page + 1}: {len(entries)} entries (total: {len(all_entries)})")
                
                if len(entries) < page_size:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching time entries page {page + 1}: {e}")
                break
        
        logger.info(f"Fetched {len(all_entries)} total time entries for {start_date.date()} to {end_date.date()}")
        return all_entries
    
    def calculate_daily_hours(self, time_entries: List[Dict]) -> Dict[str, Dict[str, float]]:
        """
        Calculate daily hours from time entries (clock in/out events)
        
        Returns: {person_id: {date_str: total_hours}}
        """
        from collections import defaultdict
        
        # Group entries by person and date
        person_date_entries = defaultdict(lambda: defaultdict(list))
        
        for entry in time_entries:
            person_id = entry.get("personId")
            entry_datetime_str = entry.get("time")  # Use 'time' field (UTC timestamp)
            entry_type = entry.get("type")  # "In" or "Out"
            belongs_to_date = entry.get("belongsToDate")  # Date the entry belongs to
            
            if not person_id or not entry_datetime_str:
                continue
            
            try:
                entry_datetime = datetime.fromisoformat(entry_datetime_str.replace("Z", "+00:00"))
                # Use belongsToDate if available, otherwise derive from datetime
                date_str = belongs_to_date if belongs_to_date else entry_datetime.date().isoformat()
                
                person_date_entries[person_id][date_str].append({
                    "datetime": entry_datetime,
                    "type": entry_type,
                })
            except Exception as e:
                logger.warning(f"Error parsing time entry: {e}")
                continue
        
        # Calculate hours for each person/date
        daily_hours = {}
        
        for person_id, date_entries in person_date_entries.items():
            daily_hours[person_id] = {}
            
            for date_str, entries in date_entries.items():
                # Sort entries by datetime
                entries.sort(key=lambda x: x["datetime"])
                
                total_seconds = 0
                clock_in_time = None
                
                for entry in entries:
                    if entry["type"] == "In":
                        clock_in_time = entry["datetime"]
                    elif entry["type"] == "Out" and clock_in_time:
                        duration = (entry["datetime"] - clock_in_time).total_seconds()
                        total_seconds += duration
                        clock_in_time = None
                
                # If still clocked in, calculate up to now (or end of day)
                if clock_in_time:
                    now = datetime.now(clock_in_time.tzinfo)
                    duration = (now - clock_in_time).total_seconds()
                    # Cap at 12 hours to avoid unrealistic values
                    total_seconds += min(duration, 12 * 3600)
                
                daily_hours[person_id][date_str] = round(total_seconds / 3600, 2)
        
        return daily_hours
    
    def test_connection(self) -> Dict[str, Any]:
        """Test the Jibble API connection"""
        try:
            token = self._get_access_token()
            
            # Try to fetch first page of people
            params = {"$top": 1}
            data = self._make_request("People", params=params)
            people_count = len(data.get("value", []))
            
            return {
                "success": True,
                "message": "Successfully connected to Jibble API",
                "has_token": bool(token),
                "sample_people": people_count,
            }
        except Exception as e:
            return {
                "success": False,
                "message": f"Failed to connect: {str(e)}",
                "has_token": False,
            }

