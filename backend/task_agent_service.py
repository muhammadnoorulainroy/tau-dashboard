"""
Task Agent API Service
Handles syncing data from Amazon Task Agent API to local database
"""
import os
import json
import logging
import requests
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy.orm import Session
from sqlalchemy import func

from database_v2 import (
    Task, TaskAgentUser, Batch, Environment, SyncStateV2,
    SessionLocal, init_db_v2, TASK_STATUSES
)

# Load environment variables
env_path = Path(__file__).parent / '.env'
if env_path.exists():
    load_dotenv(env_path)

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class TaskAgentService:
    """Service for interacting with Task Agent API"""
    
    def __init__(self):
        self.base_url = os.getenv("TASK_AGENT_API_URL", "https://amazon-task-agent.turing.com")
        self.token = os.getenv("TASK_AGENT_API_TOKEN")
        
        if not self.token:
            raise ValueError("TASK_AGENT_API_TOKEN not found in environment")
        
        self.headers = {
            "authorization": f"Bearer {self.token}",
            "content-type": "application/json",
            "accept": "application/json"
        }
    
    def _request(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make authenticated request to Task Agent API"""
        url = f"{self.base_url}{endpoint}"
        try:
            response = requests.get(url, headers=self.headers, params=params, timeout=60)
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"API error {response.status_code}: {endpoint} - {response.text[:200]}")
                return None
        except Exception as e:
            logger.error(f"Request failed: {endpoint} - {str(e)}")
            return None
    
    # =========================================================================
    # API FETCH METHODS
    # =========================================================================
    
    def fetch_all_tasks(self, per_page: int = 100) -> List[Dict]:
        """
        Fetch all tasks from API with pagination
        Fetches by status to ensure we get all tasks including approved ones
        """
        all_tasks = []
        seen_ids = set()
        
        # Fetch by each status to ensure we get all tasks
        for status in TASK_STATUSES:
            page = 1
            while True:
                logger.info(f"Fetching {status} tasks page {page}...")
                data = self._request("/api/tasks", {
                    "page": page, 
                    "per_page": per_page,
                    "status": status
                })
                
                if not data or "tasks" not in data:
                    break
                
                tasks = data["tasks"]
                for task in tasks:
                    if task["id"] not in seen_ids:
                        all_tasks.append(task)
                        seen_ids.add(task["id"])
                
                if len(tasks) < per_page:
                    break
                
                page += 1
        
        # Also fetch without status filter to catch any edge cases
        page = 1
        while True:
            data = self._request("/api/tasks", {"page": page, "per_page": per_page})
            
            if not data or "tasks" not in data:
                break
            
            tasks = data["tasks"]
            for task in tasks:
                if task["id"] not in seen_ids:
                    all_tasks.append(task)
                    seen_ids.add(task["id"])
            
            if len(tasks) < per_page:
                break
            
            page += 1
        
        logger.info(f"Fetched {len(all_tasks)} tasks total")
        return all_tasks
    
    def fetch_task_detail(self, task_id: str) -> Optional[Dict]:
        """Fetch single task with full details (tools, scenarios, etc.)"""
        return self._request(f"/api/tasks/{task_id}")
    
    def fetch_all_users(self, per_page: int = 100) -> List[Dict]:
        """Fetch all users from API"""
        all_users = []
        page = 1
        
        while True:
            logger.info(f"Fetching users page {page}...")
            data = self._request("/api/admin/users", {"page": page, "per_page": per_page})
            
            if not data or "users" not in data:
                break
            
            users = data["users"]
            all_users.extend(users)
            
            if len(users) < per_page:
                break
            
            page += 1
        
        logger.info(f"Fetched {len(all_users)} users total")
        return all_users
    
    def fetch_all_batches(self) -> List[Dict]:
        """Fetch all batches from API"""
        data = self._request("/api/batches", {"page": 1, "per_page": 1000})
        if data and "batches" in data:
            logger.info(f"Fetched {len(data['batches'])} batches")
            return data["batches"]
        return []
    
    def fetch_environments(self) -> List[Dict]:
        """Fetch all environments/domains from API"""
        data = self._request("/api/tau-env/environments")
        if data and isinstance(data, list):
            logger.info(f"Fetched {len(data)} environments")
            return data
        return []
    
    def fetch_status_counts(self) -> Dict[str, int]:
        """Fetch task status counts from API"""
        data = self._request("/api/tasks/statuses")
        if data and "statuses" in data:
            return {s["status"]: s["count"] for s in data["statuses"]}
        return {}
    
    # =========================================================================
    # SYNC METHODS
    # =========================================================================
    
    def sync_environments(self, db: Session) -> int:
        """Sync environments/domains to database"""
        environments = self.fetch_environments()
        count = 0
        
        for env_data in environments:
            env = db.query(Environment).filter(
                Environment.name == env_data["name"]
            ).first()
            
            if not env:
                env = Environment(name=env_data["name"])
                db.add(env)
            
            env.description = env_data.get("description")
            env.data_path_exists = env_data.get("data_path_exists", True)
            env.is_active = True
            env.last_synced = datetime.now(timezone.utc)
            count += 1
        
        db.commit()
        logger.info(f"Synced {count} environments")
        return count
    
    def sync_users(self, db: Session) -> int:
        """Sync users to database"""
        users = self.fetch_all_users()
        count = 0
        
        for user_data in users:
            user = db.query(TaskAgentUser).filter(
                TaskAgentUser.user_agent_id == user_data["id"]
            ).first()
            
            if not user:
                user = TaskAgentUser(user_agent_id=user_data["id"])
                db.add(user)
            
            user.email = user_data.get("email")
            user.name = user_data.get("name")
            user.is_active = user_data.get("is_active", True)
            user.roles = user_data.get("roles", [])
            user.avatar_url = user_data.get("avatar_url")
            user.auth_method = user_data.get("auth_method")
            user.login_count = user_data.get("login_count", 0)
            
            if user_data.get("last_login_at"):
                user.last_login_at = datetime.fromisoformat(
                    user_data["last_login_at"].replace("Z", "+00:00")
                )
            if user_data.get("created_at"):
                user.created_at = datetime.fromisoformat(
                    user_data["created_at"].replace("Z", "+00:00")
                )
            if user_data.get("updated_at"):
                user.updated_at = datetime.fromisoformat(
                    user_data["updated_at"].replace("Z", "+00:00")
                )
            
            user.last_synced = datetime.now(timezone.utc)
            count += 1
        
        db.commit()
        logger.info(f"Synced {count} users")
        return count
    
    def build_name_to_email_lookup(self, db: Session) -> Dict[str, str]:
        """
        Build a case-insensitive name-to-email lookup from TaskAgentUser table
        Returns dict mapping lowercase names to emails
        """
        users = db.query(TaskAgentUser).filter(
            TaskAgentUser.email.isnot(None),
            TaskAgentUser.name.isnot(None)
        ).all()
        
        lookup = {}
        for user in users:
            if user.name and user.email:
                # Store with lowercase key for case-insensitive matching
                lookup[user.name.lower().strip()] = user.email
        
        logger.info(f"Built name-to-email lookup with {len(lookup)} entries")
        return lookup
    
    def lookup_email_by_name(self, name: str, lookup: Dict[str, str]) -> Optional[str]:
        """Look up email by name using case-insensitive matching"""
        if not name:
            return None
        
        # Direct lookup (case-insensitive)
        email = lookup.get(name.lower().strip())
        if email:
            return email
        
        # Try normalized name (remove extra spaces, etc.)
        normalized = ' '.join(name.split()).lower()
        email = lookup.get(normalized)
        if email:
            return email
        
        return None
    
    def extract_rework_attribution(self, task_history: List[Dict], name_email_lookup: Dict[str, str]) -> Optional[Dict]:
        """
        Extract who sent the task to rework from task_history
        
        Events that indicate a reviewer sent task to rework:
        - task_sent_to_rework_by_pod_lead
        - task_sent_to_rework_by_calibrator  
        - task_sent_to_rework_by_expert
        
        NOTE: We explicitly EXCLUDE 'task_started_rework' which is when 
        the trainer starts working on fixing the task (not who sent it to rework)
        
        Returns:
            Dict with 'name', 'email', 'role' or None
        """
        if not task_history:
            return None
        
        # Sort by created_at descending to get most recent rework event
        sorted_history = sorted(
            task_history, 
            key=lambda x: x.get('created_at', ''), 
            reverse=True
        )
        
        for event in sorted_history:
            event_type = event.get('event', '').lower()
            initiated_by = event.get('initiated_by')
            
            if not initiated_by:
                continue
            
            # Only match "task_sent_to_rework_by_*" events (not task_started_rework)
            if not event_type.startswith('task_sent_to_rework_by'):
                continue
            
            # Determine role from event type
            role = None
            if 'pod_lead' in event_type:
                role = 'pod_lead'
            elif 'calibrator' in event_type:
                role = 'calibrator'
            elif 'expert' in event_type:
                role = 'expert_reviewer'
            
            # Found a valid rework event
            email = self.lookup_email_by_name(initiated_by, name_email_lookup)
            return {
                'name': initiated_by,
                'email': email,
                'role': role
            }
        
        return None
    
    def sync_batches(self, db: Session) -> int:
        """Sync batches to database"""
        batches = self.fetch_all_batches()
        count = 0
        
        for batch_data in batches:
            batch = db.query(Batch).filter(
                Batch.batch_agent_id == batch_data["id"]
            ).first()
            
            if not batch:
                batch = Batch(batch_agent_id=batch_data["id"])
                db.add(batch)
            
            batch.batch_name = batch_data.get("batch_name")
            batch.environment = batch_data.get("environment")
            batch.description = batch_data.get("description")
            batch.status = batch_data.get("status")
            batch.is_locked = batch_data.get("is_locked", False)
            batch.is_exported = batch_data.get("is_exported", False)
            batch.task_count = batch_data.get("task_count", 0)
            batch.author = batch_data.get("author")
            
            if batch_data.get("date_opened"):
                batch.date_opened = datetime.fromisoformat(
                    batch_data["date_opened"].replace("Z", "+00:00")
                )
            if batch_data.get("date_closed"):
                batch.date_closed = datetime.fromisoformat(
                    batch_data["date_closed"].replace("Z", "+00:00")
                )
            if batch_data.get("created_at"):
                batch.created_at = datetime.fromisoformat(
                    batch_data["created_at"].replace("Z", "+00:00")
                )
            if batch_data.get("updated_at"):
                batch.updated_at = datetime.fromisoformat(
                    batch_data["updated_at"].replace("Z", "+00:00")
                )
            
            batch.last_synced = datetime.now(timezone.utc)
            count += 1
        
        db.commit()
        logger.info(f"Synced {count} batches")
        return count
    
    def sync_tasks(self, db: Session, fetch_details: bool = True, name_email_lookup: Dict[str, str] = None) -> int:
        """
        Sync tasks to database
        
        Args:
            db: Database session
            fetch_details: If True, fetch full task details for instruction_text and tool_sequence
            name_email_lookup: Optional pre-built name-to-email lookup dict
        """
        tasks = self.fetch_all_tasks()
        count = 0
        updated = 0
        details_fetched = 0
        history_refreshed = 0  # Track tasks that got history refresh on status transition
        
        # Build email lookup if not provided
        if name_email_lookup is None:
            name_email_lookup = self.build_name_to_email_lookup(db)
        
        logger.info(f"Processing {len(tasks)} tasks (fetch_details={fetch_details})...")
        
        for i, task_data in enumerate(tasks):
            task_agent_id = task_data["id"]
            
            task = db.query(Task).filter(
                Task.task_agent_id == task_agent_id
            ).first()
            
            is_new = task is None
            if is_new:
                task = Task(task_agent_id=task_agent_id)
                db.add(task)
            
            # Basic fields
            task.description = task_data.get("description")
            task.difficulty = task_data.get("difficulty")
            
            # Track status transition for history refresh
            old_status = task.status
            new_status = task_data.get("status")
            task.status = new_status
            
            # Trainer
            task.trainer_id = task_data.get("trainer_id")
            task.trainer_name = task_data.get("trainer")
            task.trainer_email = task_data.get("trainer_email")
            
            # Reviewers (Calibrators)
            task.reviewer_id = task_data.get("reviewer")
            task.reviewer_name = task_data.get("reviewer_name")
            task.reviewer_email = task_data.get("reviewer_email")
            # Lookup email if not provided
            if not task.reviewer_email and task.reviewer_name:
                task.reviewer_email = self.lookup_email_by_name(task.reviewer_name, name_email_lookup)
            
            # Expert Reviewers
            task.expert_reviewer_id = task_data.get("expert_reviewer_id")
            task.expert_reviewer_name = task_data.get("expert_reviewer_name")
            task.expert_reviewer_email = task_data.get("expert_reviewer_email")
            # Lookup email if not provided
            if not task.expert_reviewer_email and task.expert_reviewer_name:
                task.expert_reviewer_email = self.lookup_email_by_name(task.expert_reviewer_name, name_email_lookup)
            
            # POD Leads
            task.pod_lead_id = task_data.get("pod_lead_id")
            task.pod_lead_name = task_data.get("pod_lead_name")
            task.pod_lead_email = task_data.get("pod_lead_email")
            # Lookup email if not provided
            if not task.pod_lead_email and task.pod_lead_name:
                task.pod_lead_email = self.lookup_email_by_name(task.pod_lead_name, name_email_lookup)
            
            # Batch
            task.batch_id = task_data.get("batch_id")
            task.batch_name = task_data.get("batch_name")
            task.batch_status = task_data.get("batch_status")
            task.batch_is_locked = task_data.get("batch_is_locked", False)
            
            # Metrics
            task.rework_count = task_data.get("rework_count", 0)
            
            # Timestamps
            if task_data.get("created_at"):
                task.created_at = datetime.fromisoformat(
                    task_data["created_at"].replace("Z", "+00:00")
                )
            if task_data.get("updated_at"):
                task.updated_at = datetime.fromisoformat(
                    task_data["updated_at"].replace("Z", "+00:00")
                )
            if task_data.get("completed_at"):
                task.completed_at = datetime.fromisoformat(
                    task_data["completed_at"].replace("Z", "+00:00")
                )
            
            # tau_metadata (contains domain and interface)
            tau_metadata = task_data.get("tau_metadata")
            if tau_metadata:
                task.tau_metadata = tau_metadata
                task.domain = tau_metadata.get("environment")
                interface = tau_metadata.get("interface")
                if interface:
                    try:
                        task.interface_num = int(interface)
                    except (ValueError, TypeError):
                        task.interface_num = None
            
            # Fallback: Extract domain from batch_name if tau_metadata not available
            # e.g., "Batch_confluence_wiki_20251201_185920" -> "confluence_wiki"
            if not task.domain and task.batch_name:
                batch_name = task.batch_name
                if batch_name.startswith("Batch_"):
                    # Format: Batch_{domain}_{YYYYMMDD}_{HHMMSS}
                    # Split and find timestamp parts (8 and 6 digits)
                    import re
                    match = re.match(r'^Batch_(.+)_(\d{8})_(\d{6})$', batch_name)
                    if match:
                        task.domain = match.group(1)
            
            # If task has tools/scenarios in list response, use them
            if task_data.get("tools"):
                task.tools = task_data["tools"]
            if task_data.get("scenarios"):
                task.scenarios = task_data["scenarios"]
                # Extract instruction text
                try:
                    task.instruction_text = task_data["scenarios"][0]["prompts"][0]["prompt_text"]
                except (IndexError, KeyError, TypeError):
                    pass
            if task_data.get("tool_sequence"):
                if isinstance(task_data["tool_sequence"], str):
                    try:
                        task.tool_sequence = json.loads(task_data["tool_sequence"])
                    except json.JSONDecodeError:
                        task.tool_sequence = None
                else:
                    task.tool_sequence = task_data["tool_sequence"]
            
            # Fetch full details if needed (for instruction_text, tool_sequence, and task_history)
            # IMPORTANT: task_history is dynamic and changes as tasks go through reviews
            needs_instruction = not task.instruction_text
            needs_tool_sequence = not task.tool_sequence
            needs_history = not task.task_history
            
            # Refresh task_history for tasks in ACTIVE review states where new events may have occurred
            # These are the only states where review events can be added:
            # - Tasks waiting for or in any review stage
            # - Tasks in rework (may be resubmitted)
            active_review_states = [
                'pending_review',      # Waiting for expert review
                'in_expert_review',    # Being reviewed by expert
                'pending_calibrator_review',  # Waiting for calibrator
                'in_calibrator_review',  # Being reviewed by calibrator
                'in_pod_lead_review',  # Being reviewed by POD lead
                'rework'               # May have review events from rejection
            ]
            
            # Check if task is currently in an active review state
            needs_history_refresh = new_status in active_review_states
            
            # IMPORTANT: Also refresh history when a task TRANSITIONED OUT of active review
            # This captures events that happened before the transition:
            # - approved: captures final approval event
            # - draft: captures rework events when trainer withdrew submission
            if old_status in active_review_states and new_status in ['approved', 'draft']:
                needs_history_refresh = True
                history_refreshed += 1
            
            # Also refresh if the task HAS history but we detect the history might be stale
            # (task was previously reviewed but is now back in draft)
            if new_status == 'draft' and task.task_history:
                # Check if the existing history has any review events
                has_review_events = any(
                    'review' in e.get('event', '').lower() or 
                    'rework' in e.get('event', '').lower() or
                    'approved' in e.get('event', '').lower() or
                    'calibrator' in e.get('event', '').lower()
                    for e in task.task_history
                )
                if has_review_events:
                    needs_history_refresh = True
            
            needs_details = needs_instruction or needs_tool_sequence or needs_history or needs_history_refresh
            if fetch_details and needs_details:
                details_fetched += 1
                if details_fetched % 50 == 0:
                    logger.info(f"Fetching details: {details_fetched} tasks processed (current: {i + 1}/{len(tasks)})...")
                
                detail = self.fetch_task_detail(task_agent_id)
                if detail:
                    # tau_metadata
                    if detail.get("tau_metadata") and not task.tau_metadata:
                        task.tau_metadata = detail["tau_metadata"]
                        task.domain = detail["tau_metadata"].get("environment")
                        interface = detail["tau_metadata"].get("interface")
                        if interface:
                            try:
                                task.interface_num = int(interface)
                            except (ValueError, TypeError):
                                pass
                    
                    # Tools
                    if detail.get("tools"):
                        task.tools = detail["tools"]
                    
                    # Scenarios with instruction text
                    if detail.get("scenarios"):
                        task.scenarios = detail["scenarios"]
                        try:
                            task.instruction_text = detail["scenarios"][0]["prompts"][0]["prompt_text"]
                        except (IndexError, KeyError, TypeError):
                            pass
                    
                    # Tool sequence
                    if detail.get("tool_sequence"):
                        if isinstance(detail["tool_sequence"], str):
                            try:
                                task.tool_sequence = json.loads(detail["tool_sequence"])
                            except json.JSONDecodeError:
                                pass
                        else:
                            task.tool_sequence = detail["tool_sequence"]
                    
                    # Store task_history
                    if detail.get("task_history"):
                        task.task_history = detail["task_history"]
            
            # Always extract rework attribution from task_history (even if already synced before)
            # This ensures the attribution logic is always up-to-date
            if task.task_history:
                rework_info = self.extract_rework_attribution(task.task_history, name_email_lookup)
                if rework_info:
                    task.rework_by_name = rework_info.get('name')
                    task.rework_by_email = rework_info.get('email')
                    task.rework_by_role = rework_info.get('role')
                else:
                    # Clear any previous rework attribution if no rework events found
                    task.rework_by_name = None
                    task.rework_by_email = None
                    task.rework_by_role = None
            
            task.last_synced = datetime.now(timezone.utc)
            
            if is_new:
                count += 1
            else:
                updated += 1
            
            # Commit in batches to avoid memory issues
            if (count + updated) % 50 == 0:
                db.commit()
        
        db.commit()
        logger.info(f"Synced tasks: {count} new, {updated} updated, {details_fetched} details fetched, {history_refreshed} histories refreshed on approval")
        return count + updated
    
    def update_environment_stats(self, db: Session) -> None:
        """Update computed statistics on environments based on synced tasks"""
        environments = db.query(Environment).all()
        
        for env in environments:
            # Get tasks for this domain
            tasks = db.query(Task).filter(Task.domain == env.name).all()
            
            # Reset counts
            env.total_tasks = len(tasks)
            env.draft_count = 0
            env.pending_review_count = 0
            env.in_expert_review_count = 0
            env.pending_calibrator_review_count = 0
            env.in_calibrator_review_count = 0
            env.in_pod_lead_review_count = 0
            env.rework_count = 0
            env.approved_count = 0
            
            env.approved_expert = 0
            env.approved_hard = 0
            env.approved_medium = 0
            env.total_expert = 0
            env.total_hard = 0
            env.total_medium = 0
            
            for task in tasks:
                # Status counts
                if task.status == 'draft':
                    env.draft_count += 1
                elif task.status == 'pending_review':
                    env.pending_review_count += 1
                elif task.status == 'in_expert_review':
                    env.in_expert_review_count += 1
                elif task.status == 'pending_calibrator_review':
                    env.pending_calibrator_review_count += 1
                elif task.status == 'in_calibrator_review':
                    env.in_calibrator_review_count += 1
                elif task.status == 'in_pod_lead_review':
                    env.in_pod_lead_review_count += 1
                elif task.status == 'rework':
                    env.rework_count += 1
                elif task.status == 'approved':
                    env.approved_count += 1
                
                # Total complexity counts
                if task.difficulty == 'expert':
                    env.total_expert += 1
                elif task.difficulty == 'hard':
                    env.total_hard += 1
                elif task.difficulty == 'medium':
                    env.total_medium += 1
                
                # Approved complexity counts
                if task.status == 'approved':
                    if task.difficulty == 'expert':
                        env.approved_expert += 1
                    elif task.difficulty == 'hard':
                        env.approved_hard += 1
                    elif task.difficulty == 'medium':
                        env.approved_medium += 1
            
            env.last_synced = datetime.now(timezone.utc)
        
        db.commit()
        logger.info(f"Updated stats for {len(environments)} environments")
    
    def full_sync(self, db: Session, fetch_task_details: bool = True) -> Dict[str, int]:
        """
        Perform full sync of all data from Task Agent API
        
        Args:
            db: Database session
            fetch_task_details: If True, fetch full details for each task (slower but complete)
        
        Returns:
            Dictionary with sync counts
        """
        logger.info("=" * 60)
        logger.info("Starting full sync from Task Agent API")
        logger.info("=" * 60)
        
        start_time = datetime.now(timezone.utc)
        
        # Sync in order
        env_count = self.sync_environments(db)
        user_count = self.sync_users(db)
        batch_count = self.sync_batches(db)
        task_count = self.sync_tasks(db, fetch_details=fetch_task_details)
        
        # Update computed stats
        self.update_environment_stats(db)
        
        # Update sync state
        sync_state = db.query(SyncStateV2).first()
        if not sync_state:
            sync_state = SyncStateV2()
            db.add(sync_state)
        
        sync_state.last_sync_time = datetime.now(timezone.utc)
        sync_state.last_full_sync_time = datetime.now(timezone.utc)
        sync_state.tasks_synced = task_count
        sync_state.users_synced = user_count
        sync_state.batches_synced = batch_count
        db.commit()
        
        duration = (datetime.now(timezone.utc) - start_time).total_seconds()
        
        logger.info("=" * 60)
        logger.info("Sync completed!")
        logger.info(f"  Environments: {env_count}")
        logger.info(f"  Users: {user_count}")
        logger.info(f"  Batches: {batch_count}")
        logger.info(f"  Tasks: {task_count}")
        logger.info(f"  Duration: {duration:.1f}s")
        logger.info("=" * 60)
        
        return {
            "environments": env_count,
            "users": user_count,
            "batches": batch_count,
            "tasks": task_count,
            "duration_seconds": duration
        }


def run_sync(fetch_details: bool = True):
    """Run a full sync from command line"""
    # Initialize database tables
    init_db_v2()
    
    # Create service and run sync
    service = TaskAgentService()
    db = SessionLocal()
    
    try:
        result = service.full_sync(db, fetch_task_details=fetch_details)
        return result
    finally:
        db.close()


if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description="Sync data from Task Agent API")
    parser.add_argument(
        "--skip-details", 
        action="store_true",
        help="Skip fetching full task details (faster but incomplete)"
    )
    args = parser.parse_args()
    
    run_sync(fetch_details=not args.skip_details)

