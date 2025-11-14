import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from github import Github, GithubException
from sqlalchemy.orm import Session
from database import PullRequest, Review, CheckRun, User, Domain, Interface, Week, Pod, Developer, Reviewer, DomainMetrics, InterfaceMetrics, UserDomainAssignment
from config import settings
from sync_state import update_last_sync_time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self):
        # Set per_page=100 to fetch 100 items per page (max allowed by GitHub API)
        self.github = Github(settings.github_token, per_page=100)
        self.repo = self.github.get_repo(settings.github_repo)
        
        # Known valid domains (for fixing malformed PR titles)
        self.valid_domains = set(settings.allowed_domains)
        
        # Pattern to match PRs: {trainer_name}-{domain}-{interface_num}-{complexity_level}-{timestamp}
        # Example: haseeb-fund_finance-3-expert-1760428727
        # NOTE: Made trainer name non-greedy to avoid consuming domain parts
        self.pr_pattern = re.compile(r'^([a-zA-Z0-9\._-]+?)-([\w_-]+)-(\d+)-(expert|hard|medium)-(\d{10})$')
        # Pattern for task files (same format, but may have .json extension)
        self.task_file_pattern = re.compile(r'^([a-zA-Z0-9\._-]+?)-([\w_-]+)-(\d+)-(expert|hard|medium)-(\d{10})(?:\.json)?$')
        # Pattern to extract week and pod from file paths
        # Supports both formats:
        # 1. Old: week_12/bandreddy_pod/task_name/...
        # 2. New: week_13_hr_talent/mansoor_pod/task_name/...
        self.week_pod_pattern = re.compile(r'^week_(\d+)(?:_[\w_-]+)?/([^/]+)/')
        
    def parse_pr_title(self, title: str) -> Optional[Dict]:
        """Parse PR title to extract trainer, domain, interface number, complexity, and timestamp.
        
        Handles both correct format (hr_experts) and malformed format (hr-experts).
        """
        match = self.pr_pattern.match(title)
        if match:
            trainer_name = match.group(1)
            domain = match.group(2)
            interface_num = int(match.group(3))
            complexity = match.group(4)
            timestamp = match.group(5)
            
            # Fix malformed domains: convert hyphens to underscores and check against valid domains
            domain_normalized = domain.replace('-', '_')
            
            # If the normalized domain is in our valid list, use it
            if domain_normalized in self.valid_domains:
                domain = domain_normalized
            # If the original domain is too short or suspicious, try to fix it
            elif domain in ['expert', 'experts', 'hard', 'medium', 'management', 'payroll', 'finance', 'wiki', 'home', 'incident']:
                # This might be part of a compound domain name that got split
                # Try to reconstruct by looking at the trainer name ending
                parts = trainer_name.split('-')
                if len(parts) > 1:
                    # Last part of trainer might actually be first part of domain
                    potential_prefix = parts[-1]
                    potential_domain = f"{potential_prefix}_{domain}"
                    if potential_domain in self.valid_domains:
                        # Fix the split
                        trainer_name = '-'.join(parts[:-1])
                        domain = potential_domain
            
            return {
                'trainer_name': trainer_name,
                'domain': domain,
                'interface_num': interface_num,
                'complexity': complexity,
                'timestamp': timestamp
            }
        
        # Try alternative pattern for backward compatibility
        alt_pattern = re.compile(r'^([a-zA-Z0-9\._-]+?)-([\w_-]+)-(\d+)?-?(expert|hard|medium)?-?(\d{10,})$')
        match = alt_pattern.match(title)
        if match:
            return {
                'trainer_name': match.group(1),
                'domain': match.group(2),
                'interface_num': int(match.group(3)) if match.group(3) else 0,
                'complexity': match.group(4) if match.group(4) else 'unknown',
                'timestamp': match.group(5)
            }
        
        return None
    
    def should_process_pr(self, pr) -> bool:
        """Check if PR matches our criteria (has proper format)."""
        # Check if title matches our pattern
        if not self.parse_pr_title(pr.title):
            return False
        
        # Labels are optional but recommended for accurate metrics
        # We process PRs regardless of labels
        return True
    
    def calculate_rework_count(self, pr, db: Session) -> int:
        """Calculate rework count based on review feedback only."""
        rework_count = 0
        
        # Count reviews requesting changes
        for review in pr.get_reviews():
            if review.state == 'CHANGES_REQUESTED':
                rework_count += 1
        
        return rework_count
    
    def calculate_failed_checks_count(self, pr) -> int:
        """
        Calculate failed automated checks count.
        Counts each check run that concluded with 'failure'.
        """
        failed_checks = 0
        
        # Count failed checks
        try:
            if hasattr(pr, 'get_check_runs'):
                for check in pr.get_check_runs():
                    if check.conclusion == 'failure':
                        failed_checks += 1
        except Exception as e:
            logger.debug(f"Could not fetch check runs for PR {pr.number}: {str(e)}")
        
        return failed_checks
    
    # ===========================
    # Entity Creation Helpers (Migration-Aware)
    # ===========================
    
    def get_or_create_user(self, github_username: str, role: str, db: Session) -> User:
        """Get or create a user by GitHub username."""
        from sqlalchemy.exc import IntegrityError
        
        user = db.query(User).filter_by(github_username=github_username).first()
        if not user:
            try:
                user = User(
                    github_username=github_username,
                    role=role,
                    email=f"{github_username}@github.local"  # Placeholder email
                )
                db.add(user)
                db.flush()
                logger.info(f"Created new user: {github_username} (role: {role})")
            except IntegrityError:
                # User was created by another process/transaction, rollback and fetch
                db.rollback()
                user = db.query(User).filter_by(github_username=github_username).first()
                if not user:
                    # Try alternative query by email (edge case)
                    user = db.query(User).filter_by(email=f"{github_username}@github.local").first()
        return user
    
    def get_or_create_domain(self, domain_name: str, db: Session) -> Domain:
        """Get or create a domain by name."""
        from sqlalchemy.exc import IntegrityError
        
        domain = db.query(Domain).filter_by(domain_name=domain_name).first()
        if not domain:
            try:
                domain = Domain(domain_name=domain_name)
                db.add(domain)
                db.flush()
                logger.info(f"Created new domain: {domain_name}")
            except IntegrityError:
                db.rollback()
                domain = db.query(Domain).filter_by(domain_name=domain_name).first()
        return domain
    
    def get_or_create_interface(self, domain: Domain, interface_num: int, db: Session) -> Interface:
        """Get or create an interface for a domain."""
        from sqlalchemy.exc import IntegrityError
        
        interface = db.query(Interface).filter_by(
            domain_id=domain.id,
            interface_num=interface_num
        ).first()
        if not interface:
            try:
                interface = Interface(
                    domain_id=domain.id,
                    interface_num=interface_num
                )
                db.add(interface)
                db.flush()
                logger.info(f"Created new interface: {domain.domain_name} - Interface {interface_num}")
            except IntegrityError:
                db.rollback()
                interface = db.query(Interface).filter_by(
                    domain_id=domain.id,
                    interface_num=interface_num
                ).first()
        return interface
    
    def get_or_create_week(self, week_num: int, db: Session) -> Week:
        """Get or create a week by number."""
        from sqlalchemy.exc import IntegrityError
        
        week = db.query(Week).filter_by(week_num=week_num).first()
        if not week:
            try:
                week = Week(
                    week_name=f"week_{week_num}",
                    week_num=week_num
                )
                db.add(week)
                db.flush()
                logger.info(f"Created new week: week_{week_num}")
            except IntegrityError:
                db.rollback()
                week = db.query(Week).filter_by(week_num=week_num).first()
        return week
    
    def get_or_create_pod(self, pod_name: str, db: Session) -> Pod:
        """Get or create a pod by name."""
        from sqlalchemy.exc import IntegrityError
        
        pod = db.query(Pod).filter_by(name=pod_name).first()
        if not pod:
            try:
                pod = Pod(name=pod_name)
                db.add(pod)
                db.flush()
                logger.info(f"Created new pod: {pod_name}")
            except IntegrityError:
                db.rollback()
                pod = db.query(Pod).filter_by(name=pod_name).first()
        return pod
    
    def assign_user_to_domain(self, user: User, domain: Domain, db: Session):
        """Create user-domain assignment if it doesn't exist."""
        from sqlalchemy.exc import IntegrityError
        
        # Validate inputs
        if not user or not domain:
            logger.warning(f"Cannot assign user/domain: user={user}, domain={domain}")
            return
        
        # Refresh user and domain to ensure they're in the current session
        try:
            db.refresh(user)
            db.refresh(domain)
        except Exception as e:
            logger.warning(f"Could not refresh user/domain objects: {str(e)}")
            # Try to re-fetch from DB
            user = db.query(User).filter_by(id=user.id).first()
            domain = db.query(Domain).filter_by(id=domain.id).first()
            if not user or not domain:
                logger.error(f"Could not re-fetch user/domain after refresh failure")
                return
        
        existing = db.query(UserDomainAssignment).filter_by(
            user_id=user.id,
            domain_id=domain.id
        ).first()
        
        if not existing:
            try:
                assignment = UserDomainAssignment(
                    user_id=user.id,
                    domain_id=domain.id
                )
                db.add(assignment)
                db.flush()
                logger.info(f"Assigned user {user.github_username} to domain {domain.domain_name}")
            except IntegrityError as e:
                # Assignment might already exist or foreign key constraint failed
                db.rollback()
                logger.warning(f"Could not assign user {user.github_username} to domain {domain.domain_name}: {str(e)}")
                # Try to re-fetch the assignment (might have been created by another transaction)
                existing = db.query(UserDomainAssignment).filter_by(
                    user_id=user.id,
                    domain_id=domain.id
                ).first()
    
    def parse_week_pod_from_pr_files(self, pr) -> Optional[Tuple[int, str]]:
        """
        Parse week number and pod name from PR file changes.
        Supports both formats:
        1. Old: week_12/bandreddy_pod/task_folder/...
        2. New: week_13_hr_talent/mansoor_pod/task_folder/...
        Returns: (week_num, pod_name) or None if not found
        """
        try:
            files = pr.get_files()
            for file in files:
                match = self.week_pod_pattern.match(file.filename)
                if match:
                    week_num = int(match.group(1))
                    pod_name = match.group(2)
                    return (week_num, pod_name)
        except Exception as e:
            logger.debug(f"Could not parse week/pod from PR {pr.number} files: {str(e)}")
        
        return None
    
    def get_task_file_paths(self, db_pr: PullRequest, filename: str) -> List[str]:
        """
        Returns possible paths for task.json or result.json
        
        Old convention (Week ≤12): week_{num}/{pod_name}/{pr_title}/filename
        Example: week_11/fabio_pod/matheus.c-fund_finance-3-hard-1758726938/result.json
        
        New convention (Week ≥13): week_{num}_{domain}/{pod_name}/{pr_title}/filename
        Example: week_14_incident_management_technical/neeraj_pod/toheeb.adedokun-hr_talent-2-expert-1762764502/task.json
        """
        paths = []
        
        # Use PR title as task folder name
        task_folder = db_pr.task_folder or db_pr.title
        pod_name = db_pr.pod_name
        week_num = db_pr.week_num
        domain = db_pr.domain
        
        if not week_num or not pod_name:
            # No week/pod info - try flat structure as fallback
            paths.append(f"{task_folder}/{filename}")
            return paths
        
        # New convention (Week 13+): week_{num}_{domain}/{pod_name}/{task_folder}/filename
        if week_num >= 13:
            paths.append(f"week_{week_num}_{domain}/{pod_name}/{task_folder}/{filename}")
        
        # Old convention (Week 12-): week_{num}/{pod_name}/{task_folder}/filename
        if week_num <= 12:
            paths.append(f"week_{week_num}/{pod_name}/{task_folder}/{filename}")
        
        # Fallback: try both formats if we're not sure about the cutoff
        # This handles edge cases where the convention might have changed mid-week
        if week_num == 12 or week_num == 13:
            # Try the alternate format as well
            paths.append(f"week_{week_num}/{pod_name}/{task_folder}/{filename}")
            paths.append(f"week_{week_num}_{domain}/{pod_name}/{task_folder}/{filename}")
        
        return paths
    
    def extract_instruction_from_task_json(self, task_json: dict) -> Optional[str]:
        """Extract instruction from task.json"""
        try:
            return task_json.get("task", {}).get("instruction")
        except Exception as e:
            logger.error(f"Error extracting instruction: {e}")
            return None
    
    def calculate_pass_fail_counts(self, result_json: list) -> dict:
        """
        Count passes and fails from result.json
        Returns: {pass_count, fail_count, total_trials}
        """
        if not isinstance(result_json, list):
            logger.error("result.json is not an array")
            return {"pass_count": 0, "fail_count": 0, "total_trials": 0}
        
        pass_count = sum(1 for trial in result_json if trial.get("reward") == 1.0)
        fail_count = sum(1 for trial in result_json if trial.get("reward") == 0.0)
        total_trials = len(result_json)
        
        return {
            "pass_count": pass_count,
            "fail_count": fail_count,
            "total_trials": total_trials
        }
    
    def calculate_actual_difficulty(self, pass_count: int, total_trials: int) -> str:
        """
        Calculate difficulty based on pass rate (percentage)
        
        Based on standard of 16 trials:
        - Medium: 10-12 passes (62.5% - 75%)
        - Hard: 6-9 passes (37.5% - 56.25%)
        - Expert: 3-5 passes (18.75% - 31.25%)
        - Not enough trials: < 3 trials (insufficient data)
        - Unclassified: Pass rate outside defined ranges
        """
        # Check if we have enough trials for meaningful classification
        if total_trials < 3:
            return "not_enough_trials"
        
        if total_trials == 0:
            return "unclassified"
        
        pass_rate = pass_count / total_trials
        
        # Medium: 62.5% to 75%
        if 0.625 <= pass_rate <= 0.75:
            return "medium"
        # Hard: 37.5% to 56.25%
        elif 0.375 <= pass_rate <= 0.5625:
            return "hard"
        # Expert: 18.75% to 31.25%
        elif 0.1875 <= pass_rate <= 0.3125:
            return "expert"
        else:
            return "unclassified"
    
    def fetch_and_store_task_data(self, db_pr: PullRequest):
        """Fetch task.json and result.json for merged PRs by looking at PR file changes"""
        import json
        from github import GithubException
        
        # First, check if PR matches the required naming pattern
        # Pattern: {trainer_name}-{domain}-{interface_num}-{complexity_level}-{timestamp}
        parsed = self.parse_pr_title(db_pr.title)
        if not parsed:
            logger.debug(f"PR #{db_pr.number}: Skipping - title doesn't match naming pattern")
            db_pr.task_data_missing = True
            db_pr.result_data_missing = True
            return
        
        try:
            # Get the PR object from GitHub
            pr = self.repo.get_pull(db_pr.number)
            
            # Get files changed in this PR
            files = pr.get_files()
            
            task_json_path = None
            result_json_path = None
            
            # Extract timestamp from PR title (last part after final dash)
            # e.g., "harish_kumar-fund_finance-3-expert-1758705844" -> "1758705844"
            pr_title = db_pr.title
            timestamp = str(db_pr.timestamp or pr_title.split('-')[-1])
            
            # Debug: Show files in PR
            all_files = [f.filename for f in files]
            logger.info(f"PR #{db_pr.number}: Looking for timestamp '{timestamp}' in {len(all_files)} files")
            logger.debug(f"PR #{db_pr.number}: Files: {all_files[:5]}")  # Show first 5 files
            
            # Find task.json and result.json in the file changes
            # Look for files that:
            # 1. End with /task.json or /result.json
            # 2. Contain the PR's timestamp in the path (unique identifier)
            # This handles both old and new conventions without hardcoding folder structure
            for file in files:
                filename = file.filename
                
                # Check if this file belongs to this PR (contains timestamp)
                if timestamp in filename:
                    if filename.endswith('/task.json'):
                        task_json_path = filename
                        logger.info(f"PR #{db_pr.number}: Found task.json at {filename}")
                    # Check for both 'result.json' and 'results.json' (some PRs use plural)
                    elif filename.endswith('/result.json') or filename.endswith('/results.json'):
                        result_json_path = filename
                        logger.info(f"PR #{db_pr.number}: Found result file at {filename}")
                
                # Break early if we found both
                if task_json_path and result_json_path:
                    break
            
            if not task_json_path and not result_json_path:
                logger.warning(f"PR #{db_pr.number}: No task.json or result.json found in file changes!")
            
            # Fetch task.json
            if task_json_path:
                try:
                    # Try fetching from main branch first
                    try:
                        content = self.repo.get_contents(task_json_path, ref="main")
                    except Exception as main_error:
                        # If not on main, fetch from the merge commit
                        logger.info(f"PR #{db_pr.number}: task.json not on main ({str(main_error)[:50]}), fetching from merge commit")
                        content = self.repo.get_contents(task_json_path, ref=pr.merge_commit_sha)
                    
                    # Handle different content types - try multiple decoding methods
                    task_json = None
                    last_error = None
                    
                    # Method 1: Try decoded_content
                    try:
                        if isinstance(content.decoded_content, bytes):
                            task_json = json.loads(content.decoded_content.decode('utf-8'))
                        elif isinstance(content.decoded_content, str):
                            task_json = json.loads(content.decoded_content)
                    except (AssertionError, AttributeError, ValueError, json.JSONDecodeError) as e:
                        last_error = e
                    
                    # Method 2: Try base64 decoding from content
                    if task_json is None and hasattr(content, 'content') and content.content:
                        try:
                            import base64
                            decoded = base64.b64decode(content.content).decode('utf-8')
                            task_json = json.loads(decoded)
                        except Exception as e:
                            last_error = e
                    
                    # Method 3: Try downloading the file directly
                    if task_json is None:
                        try:
                            # Re-fetch as a blob
                            blob = self.repo.get_git_blob(content.sha)
                            import base64
                            decoded = base64.b64decode(blob.content).decode('utf-8')
                            task_json = json.loads(decoded)
                        except Exception as e:
                            last_error = e
                    
                    if task_json is None:
                        raise Exception(f"All decoding methods failed. Last error: {last_error}")
                    
                    db_pr.instruction_text = self.extract_instruction_from_task_json(task_json)
                    db_pr.task_data_missing = False
                    logger.info(f"PR #{db_pr.number}: Successfully read task.json")
                except Exception as e:
                    db_pr.task_data_missing = True
                    logger.error(f"PR #{db_pr.number}: Error reading task.json: {type(e).__name__}: {e}")
            else:
                db_pr.task_data_missing = True
                logger.debug(f"PR #{db_pr.number}: task.json not in file changes")
            
            # Fetch result.json
            if result_json_path:
                try:
                    # Try fetching from main branch first
                    try:
                        content = self.repo.get_contents(result_json_path, ref="main")
                    except Exception as main_error:
                        # If not on main, fetch from the merge commit
                        logger.info(f"PR #{db_pr.number}: result.json not on main ({str(main_error)[:50]}), fetching from merge commit")
                        content = self.repo.get_contents(result_json_path, ref=pr.merge_commit_sha)
                    
                    # Handle different content types - try multiple decoding methods
                    result_json = None
                    last_error = None
                    
                    # Method 1: Try decoded_content
                    try:
                        if isinstance(content.decoded_content, bytes):
                            result_json = json.loads(content.decoded_content.decode('utf-8'))
                        elif isinstance(content.decoded_content, str):
                            result_json = json.loads(content.decoded_content)
                    except (AssertionError, AttributeError, ValueError, json.JSONDecodeError) as e:
                        last_error = e
                    
                    # Method 2: Try base64 decoding from content
                    if result_json is None and hasattr(content, 'content') and content.content:
                        try:
                            import base64
                            decoded = base64.b64decode(content.content).decode('utf-8')
                            result_json = json.loads(decoded)
                        except Exception as e:
                            last_error = e
                    
                    # Method 3: Try downloading the file directly
                    if result_json is None:
                        try:
                            # Re-fetch as a blob
                            blob = self.repo.get_git_blob(content.sha)
                            import base64
                            decoded = base64.b64decode(blob.content).decode('utf-8')
                            result_json = json.loads(decoded)
                        except Exception as e:
                            last_error = e
                    
                    if result_json is None:
                        raise Exception(f"All decoding methods failed. Last error: {last_error}")
                    
                    counts = self.calculate_pass_fail_counts(result_json)
                    db_pr.pass_count = counts["pass_count"]
                    db_pr.fail_count = counts["fail_count"]
                    db_pr.total_trials = counts["total_trials"]
                    db_pr.actual_difficulty = self.calculate_actual_difficulty(db_pr.pass_count, db_pr.total_trials)
                    db_pr.result_data_missing = False
                    pass_rate = (db_pr.pass_count / db_pr.total_trials * 100) if db_pr.total_trials > 0 else 0
                    logger.info(f"PR #{db_pr.number}: Successfully read result.json - {db_pr.pass_count}/{db_pr.total_trials} passed ({pass_rate:.1f}%), difficulty={db_pr.actual_difficulty}")
                except Exception as e:
                    db_pr.result_data_missing = True
                    logger.error(f"PR #{db_pr.number}: Error reading result.json: {type(e).__name__}: {e}")
            else:
                db_pr.result_data_missing = True
                logger.debug(f"PR #{db_pr.number}: result.json not in file changes")
                
        except GithubException as e:
            logger.error(f"PR #{db_pr.number}: GitHub API error: {e}")
            db_pr.task_data_missing = True
            db_pr.result_data_missing = True
        except Exception as e:
            logger.error(f"PR #{db_pr.number}: Error fetching task data: {e}")
            db_pr.task_data_missing = True
            db_pr.result_data_missing = True
    
    def sync_pull_request(self, pr, db: Session, skip_nested_data: bool = False) -> Optional[PullRequest]:
        """
        Sync a single pull request to the database.
        
        Args:
            pr: GitHub PR object
            db: Database session
            skip_nested_data: If True, skip fetching files/reviews/checks (for closed PRs with complete data)
        """
        try:
            # Handle GitHub 404 errors (deleted PRs)
            try:
                pr_number = pr.number
                pr_title = pr.title
            except Exception as e:
                if '404' in str(e):
                    logger.debug(f"Skipping PR (404 - deleted or inaccessible)")
                    return None
                raise
            
            # Check if we should process this PR
            if not self.should_process_pr(pr):
                return None
            
            # Parse PR title
            parsed = self.parse_pr_title(pr.title)
            if not parsed:
                return None
            
            # Check if PR already exists
            db_pr = db.query(PullRequest).filter_by(github_id=pr.id).first()
            is_new_pr = False
            if not db_pr:
                db_pr = PullRequest(github_id=pr.id)
                is_new_pr = True
            
            # Quick update for closed PRs that already have complete data
            if skip_nested_data and pr.state == 'closed' and db_pr and db_pr.week_id:
                logger.debug(f"PR #{pr.number}: Closed PR with complete data, quick update only")
                db_pr.state = pr.state
                db_pr.merged = pr.merged
                db_pr.updated_at = pr.updated_at
                db_pr.closed_at = pr.closed_at
                db_pr.merged_at = pr.merged_at
                db_pr.last_synced = datetime.now(timezone.utc)
                return db_pr
            
            # Update PR fields
            db_pr.number = pr.number
            db_pr.title = pr.title
            db_pr.state = pr.state
            db_pr.merged = pr.merged
            
            # New field mappings
            db_pr.trainer_name = parsed['trainer_name']
            db_pr.domain = parsed['domain']
            db_pr.interface_num = parsed['interface_num']
            db_pr.complexity = parsed['complexity']
            db_pr.timestamp = parsed['timestamp']
            
            # Backward compatibility aliases
            # FIXED: Use actual GitHub username instead of parsed trainer_name
            db_pr.developer_username = pr.user.login
            db_pr.difficulty = parsed['complexity']
            db_pr.task_id = parsed['timestamp']
            
            db_pr.author_login = pr.user.login
            
            # Try to get author email from GitHub (might be None if private)
            try:
                author_email = pr.user.email
                if author_email:
                    db_pr.author_email = author_email
                    logger.info(f"Fetched email for {pr.user.login}: {author_email}")
            except Exception as e:
                logger.debug(f"Could not fetch email for {pr.user.login}: {e}")
            
            db_pr.created_at = pr.created_at
            db_pr.updated_at = pr.updated_at
            db_pr.closed_at = pr.closed_at
            db_pr.merged_at = pr.merged_at
            
            # Update labels
            db_pr.labels = [label.name for label in pr.labels]
            
            # Fetch and store requested reviewers (only GitHub usernames)
            try:
                requested_reviewers = []
                if hasattr(pr, 'requested_reviewers') and pr.requested_reviewers:
                    requested_reviewers = [reviewer.login for reviewer in pr.requested_reviewers]
                db_pr.requested_reviewers = requested_reviewers
            except Exception as e:
                logger.debug(f"Could not fetch requested reviewers for PR #{pr.number}: {e}")
                db_pr.requested_reviewers = []
            
            # Update counts
            db_pr.review_count = pr.review_comments
            db_pr.comment_count = pr.comments
            
            # Parse task execution results from bot comment
            self.parse_task_execution_results(pr, db_pr)
            
            # Calculate rework (changes requested reviews only)
            db_pr.rework_count = self.calculate_rework_count(pr, db)
            
            # Calculate failed automated checks (separate from rework)
            db_pr.check_failures = self.calculate_failed_checks_count(pr)
            
            # ===========================
            # MIGRATION-AWARE: Create entities and set foreign keys
            # ===========================
            
            # 1. Create/get trainer (user)
            trainer = self.get_or_create_user(pr.user.login, 'trainer', db)
            if not trainer:
                logger.error(f"PR {pr.number}: Failed to create/get trainer {pr.user.login}")
                return None
            db_pr.trainer_id = trainer.id
            
            # 2. Create/get domain
            domain = self.get_or_create_domain(parsed['domain'], db)
            if not domain:
                logger.error(f"PR {pr.number}: Failed to create/get domain {parsed['domain']}")
                return None
            db_pr.domain_id = domain.id
            
            # 3. Create/get interface (linked to domain)
            interface = self.get_or_create_interface(domain, parsed['interface_num'], db)
            if not interface:
                logger.error(f"PR {pr.number}: Failed to create/get interface {parsed['interface_num']} for domain {parsed['domain']}")
                return None
            db_pr.interface_id = interface.id
            
            # 4. Parse and create/get week and pod from PR file changes
            # Optimization: Only fetch files if we don't already have week/pod data
            # Skip if: (1) we're doing a quick update (skip_nested_data=True) OR
            #          (2) we already have week_id AND pod_id
            should_skip_files = skip_nested_data or (db_pr.week_id and db_pr.pod_id)
            
            if not should_skip_files:
                # Fetch files when:
                # 1. Not skipping nested data (full sync needed)
                # 2. AND (PR doesn't have week_id OR doesn't have pod_id)
                week_pod_info = self.parse_week_pod_from_pr_files(pr)
                if week_pod_info:
                    week_num, pod_name = week_pod_info
                    week = self.get_or_create_week(week_num, db)
                    pod = self.get_or_create_pod(pod_name, db)
                    
                    if week and pod:
                        db_pr.week_id = week.id
                        db_pr.pod_id = pod.id
                        # Set denormalized fields for faster queries
                        db_pr.week_num = week.week_num
                        db_pr.week_name = week.week_name
                        db_pr.pod_name = pod.name
                        logger.debug(f"PR #{pr.number}: Parsed week/pod from files (week {week.week_num}, pod {pod.name})")
                    else:
                        if not week:
                            logger.warning(f"PR {pr.number}: Failed to create/get week {week_num}")
                        if not pod:
                            logger.warning(f"PR {pr.number}: Failed to create/get pod {pod_name}")
                else:
                    logger.debug(f"PR #{pr.number}: No week/pod found in file paths")
            else:
                if skip_nested_data:
                    logger.debug(f"PR #{pr.number}: Skipping file fetch (nested data skipped)")
                else:
                    logger.debug(f"PR #{pr.number}: Week/pod already set (week_id={db_pr.week_id}, pod_id={db_pr.pod_id}), skipping file fetch")
            
            # 5. Assign trainer to domain (for access control)
            self.assign_user_to_domain(trainer, domain, db)
            
            db_pr.last_synced = datetime.now(timezone.utc)
            
            # Add and flush the PR first to get its ID for foreign key relationships
            try:
                if is_new_pr:
                    db.add(db_pr)
                db.flush()
            except Exception as flush_error:
                # Handle IntegrityError (race condition where PR was created by another process)
                from sqlalchemy.exc import IntegrityError
                if isinstance(flush_error, IntegrityError):
                    db.rollback()
                    # Re-fetch the PR that was created by another process
                    db_pr = db.query(PullRequest).filter_by(github_id=pr.id).first()
                    if not db_pr:
                        logger.error(f"PR {pr.number} still not found after IntegrityError")
                        return None
                    # Update fields on the re-fetched PR
                    db_pr.number = pr.number
                    db_pr.title = pr.title
                    db_pr.state = pr.state
                    db_pr.merged = pr.merged
                    db_pr.last_synced = datetime.now(timezone.utc)
                    db.flush()
                else:
                    raise
            
            # Now sync reviews and check runs (they need db_pr.id to be set)
            # Optimization: Skip if we're doing a quick update (skip_nested_data=True)
            if not skip_nested_data:
                self.sync_reviews(pr, db_pr, db)
                self.sync_check_runs(pr, db_pr, db)
                
                # Fetch task.json and result.json for merged PRs
                if db_pr.merged and db_pr.merged_at:
                    try:
                        self.fetch_and_store_task_data(db_pr)
                        logger.debug(f"PR #{pr.number}: Task data fetched successfully")
                    except Exception as e:
                        logger.warning(f"PR #{pr.number}: Could not fetch task data: {e}")
            else:
                logger.debug(f"PR #{pr.number}: Skipping reviews/check runs fetch (nested data skipped)")
            
            return db_pr
            
        except Exception as e:
            logger.error(f"Error syncing PR {pr.number}: {str(e)}")
            return None
    
    def parse_task_execution_results(self, pr, db_pr: PullRequest):
        """
        Parse task execution results from github-actions bot comment.
        Extracts: Total Trials, Passed, Failed, Success Rate from the comment body.
        """
        try:
            # Fetch PR comments
            comments = pr.get_issue_comments()
            
            # Find the bot comment with "Task Execution Results Analysis"
            for comment in comments:
                if comment.user.login == 'github-actions[bot]' and 'Task Execution Results Analysis' in comment.body:
                    # Parse the comment body
                    body = comment.body
                    
                    # Extract metrics using regex
                    import re
                    
                    # Look for patterns like: | **Total Trials** | 1 |
                    total_match = re.search(r'\|\s*\*\*Total Trials\*\*\s*\|\s*(\d+)\s*\|', body)
                    passed_match = re.search(r'\|\s*\*\*Passed\*\*\s*\|\s*(\d+)\s*\|', body)
                    failed_match = re.search(r'\|\s*\*\*Failed\*\*\s*\|\s*(\d+)\s*\|', body)
                    success_rate_match = re.search(r'\|\s*\*\*Success Rate\*\*\s*\|\s*(\d+(?:\.\d+)?)%?\s*\|', body)
                    
                    if total_match:
                        db_pr.task_trials_total = int(total_match.group(1))
                    if passed_match:
                        db_pr.task_trials_passed = int(passed_match.group(1))
                    if failed_match:
                        db_pr.task_trials_failed = int(failed_match.group(1))
                    if success_rate_match:
                        db_pr.task_success_rate = float(success_rate_match.group(1))
                    
                    logger.debug(f"PR {pr.number}: Parsed task execution - {db_pr.task_trials_passed}/{db_pr.task_trials_total} passed ({db_pr.task_success_rate}%)")
                    break  # Found the comment, no need to continue
                    
        except Exception as e:
            logger.debug(f"No task execution results found for PR {pr.number}: {str(e)}")
            # Not an error - some PRs may not have this comment yet
    
    def sync_reviews(self, pr, db_pr: PullRequest, db: Session):
        """Sync reviews for a pull request."""
        try:
            for review in pr.get_reviews():
                # Create/get reviewer user (default role: pod_lead, can be updated later)
                reviewer = self.get_or_create_user(review.user.login, 'pod_lead', db)
                
                # Assign reviewer to the PR's domain (for access control)
                if db_pr.domain_id:
                    domain = db.query(Domain).filter_by(id=db_pr.domain_id).first()
                    if domain:
                        self.assign_user_to_domain(reviewer, domain, db)
                
                db_review = db.query(Review).filter_by(github_id=review.id).first()
                if not db_review:
                    db_review = Review(
                        github_id=review.id,
                        pull_request_id=db_pr.id,
                        reviewer_id=reviewer.id,  # Set foreign key
                        reviewer_login=review.user.login,
                        state=review.state,
                        submitted_at=review.submitted_at,
                        body=review.body
                    )
                    db.add(db_review)
                else:
                    db_review.reviewer_id = reviewer.id  # Update foreign key
                    db_review.state = review.state
                    db_review.body = review.body
        except Exception as e:
            logger.error(f"Error syncing reviews for PR {pr.number}: {str(e)}")
    
    def sync_check_runs(self, pr, db_pr: PullRequest, db: Session):
        """Sync check runs for a pull request."""
        try:
            # Get check runs from the head commit (not from PR directly)
            commit = self.repo.get_commit(pr.head.sha)
            check_runs = commit.get_check_runs()
            
            # Group check runs by name and keep only the latest run of each
            # This avoids counting reruns multiple times
            latest_checks = {}
            for check in check_runs:
                check_name = check.name
                # Store all checks (for database)
                db_check = db.query(CheckRun).filter_by(github_id=check.id).first()
                if not db_check:
                    db_check = CheckRun(
                        github_id=check.id,
                        pull_request_id=db_pr.id,
                        name=check.name,
                        status=check.status,
                        conclusion=check.conclusion,
                        started_at=check.started_at,
                        completed_at=check.completed_at
                    )
                    db.add(db_check)
                else:
                    db_check.status = check.status
                    db_check.conclusion = check.conclusion
                    db_check.completed_at = check.completed_at
                
                # Track only the latest run of each check name for counting
                if check_name not in latest_checks:
                    latest_checks[check_name] = check
                else:
                    # Keep the one with the latest started time (GitHub's definition of "latest")
                    # If started times are equal, use GitHub ID (higher ID = later run)
                    existing = latest_checks[check_name]
                    existing_started = existing.started_at or existing.completed_at
                    new_started = check.started_at or check.completed_at
                    
                    if new_started and existing_started:
                        if new_started > existing_started:
                            latest_checks[check_name] = check
                        elif new_started == existing_started and check.id > existing.id:
                            latest_checks[check_name] = check
                    elif new_started:  # existing has no time
                        latest_checks[check_name] = check
            
            # Count only the latest run of each check
            check_failures = 0
            check_passes = 0
            for check in latest_checks.values():
                if check.conclusion == 'failure':
                    check_failures += 1
                elif check.conclusion == 'success':
                    check_passes += 1
            
            db_pr.check_failures = check_failures
            db_pr.check_passes = check_passes
        except Exception as e:
            logger.error(f"Error syncing check runs for PR {pr.number}: {str(e)}")
    
    def sync_all_prs_full_history(self, db: Session):
        """
        Sync ALL PRs that match the naming pattern, regardless of date.
        This is for initial setup or complete re-sync.
        Fetches all PRs (open, closed, merged) from the beginning.
        """
        synced_count = 0
        skipped_count = 0
        total_checked = 0
        
        logger.info("Starting FULL HISTORICAL sync - fetching ALL matching PRs...")
        
        # Sync ALL open PRs
        logger.info("Syncing all OPEN PRs...")
        pull_requests = self.repo.get_pulls(state='open', sort='created', direction='asc')
        for pr in pull_requests:
            total_checked += 1
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 50 == 0:
                    db.commit()   
                    logger.info(f"Synced {synced_count} PRs (checked {total_checked}, skipped {skipped_count})...")
                else:
                    skipped_count += 1
        
        # Sync ALL closed PRs (including merged)
        logger.info("Syncing all CLOSED PRs...")
        for pr in self.repo.get_pulls(state='closed', sort='created', direction='asc'):
            total_checked += 1
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 50 == 0:
                    db.commit()
                    logger.info(f"Synced {synced_count} PRs (checked {total_checked}, skipped {skipped_count})...")
            else:
                skipped_count += 1
        
        # Sync ALL merged PRs (double-check to ensure we got everything)
        logger.info("Syncing all MERGED PRs...")
        try:
            for pr in self.repo.get_pulls(state='all', sort='created', direction='asc'):
                try:
                    if not pr.merged:
                        continue
                    total_checked += 1
                    if self.sync_pull_request(pr, db):
                        synced_count += 1
                        if synced_count % 50 == 0:
                            db.commit()
                            logger.info(f"Synced {synced_count} PRs (checked {total_checked}, skipped {skipped_count})...")
                    else:
                        skipped_count += 1
                except Exception as pr_error:
                    # Skip individual PR errors (404, permission issues, etc.)
                    if '404' in str(pr_error):
                        logger.debug(f"Skipping PR (404 - deleted or inaccessible)")
                    else:
                        logger.warning(f"Error fetching PR: {str(pr_error)}")
                    skipped_count += 1
                    continue
        except Exception as e:
            logger.warning(f"Error in merged PR sync loop: {str(e)}")
            logger.info("Continuing with what we have...")
        
        db.commit()
        logger.info(f"FULL SYNC completed!")
        logger.info(f"  Total PRs checked: {total_checked}")
        logger.info(f"  PRs matching pattern: {synced_count}")
        logger.info(f"  PRs skipped (no match): {skipped_count}")
        
        # Update aggregated metrics
        logger.info("Updating aggregated metrics...")
        self.update_developer_metrics(db)
        self.update_reviewer_metrics(db)
        self.update_domain_metrics(db)
        self.update_interface_metrics(db)
        logger.info("Metrics updated successfully")
        
        # Update last sync time
        update_last_sync_time(db)
        
        return synced_count
    
    def sync_all_prs(self, db: Session, since_days: int = 60):
        """Sync all PRs from the last N days."""
        # Use timezone-aware datetime for comparison with GitHub API datetimes
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        synced_count = 0
        skipped_count = 0
        
        logger.info(f"Starting full sync for PRs since {since} ({since_days} days)")
        
        # Sync open PRs (sorted by created date descending by default)
        logger.info("Syncing open PRs...")
        for pr in self.repo.get_pulls(state='open', sort='created', direction='desc'):
            if pr.created_at < since:
                # Open PRs sorted by created, so break when we hit old ones
                break
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 10 == 0:
                    db.commit()
                    logger.info(f"Synced {synced_count} PRs...")
            else:
                skipped_count += 1
        
        # Sync recently closed/merged PRs (sorted by updated date to catch recent activity)
        logger.info("Syncing closed/merged PRs...")
        for pr in self.repo.get_pulls(state='closed', sort='updated', direction='desc'):
            # Check updated_at since we want recently active closed PRs
            if pr.updated_at < since:
                # PRs sorted by updated_at desc, so break when we hit old ones
                break
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 10 == 0:
                    db.commit()
                    logger.info(f"Synced {synced_count} PRs...")
            else:
                skipped_count += 1
        
        db.commit()
        logger.info(f"Full sync completed: synced {synced_count} PRs, skipped {skipped_count}")
        
        # Update aggregated metrics
        logger.info("Updating aggregated metrics...")
        self.update_developer_metrics(db)
        self.update_reviewer_metrics(db)
        self.update_domain_metrics(db)
        self.update_interface_metrics(db)
        logger.info("Metrics updated successfully")
        
        # Update last sync time
        update_last_sync_time(db)
        
        return synced_count
    
    def update_developer_metrics(self, db: Session):
        """Update aggregated developer metrics."""
        developers = db.query(
            PullRequest.developer_username,
            PullRequest.author_login
        ).distinct().all()
        
        for dev_username, github_login in developers:
            if not dev_username:
                continue
                
            dev = db.query(Developer).filter_by(username=dev_username).first()
            is_new = False
            if not dev:
                dev = Developer(username=dev_username, github_login=github_login)
                is_new = True
            
            # Calculate metrics
            prs = db.query(PullRequest).filter_by(developer_username=dev_username).all()
            dev.total_prs = len(prs)
            dev.open_prs = sum(1 for pr in prs if pr.state == 'open')
            dev.merged_prs = sum(1 for pr in prs if pr.merged)
            dev.closed_prs = sum(1 for pr in prs if pr.state == 'closed' and not pr.merged)
            dev.total_rework = sum(pr.rework_count for pr in prs)
            dev.total_check_failures = sum(pr.check_failures for pr in prs)
            
            # Calculate detailed metrics
            metrics = {
                'domains': {},
                'difficulties': {'expert': 0, 'hard': 0, 'medium': 0},
                'recent_prs': []
            }
            
            for pr in prs:
                # Count by domain
                if pr.domain:
                    metrics['domains'][pr.domain] = metrics['domains'].get(pr.domain, 0) + 1
                
                # Count by difficulty
                if pr.difficulty in metrics['difficulties']:
                    metrics['difficulties'][pr.difficulty] += 1
                
                # Add recent PRs
                if len(metrics['recent_prs']) < 5:
                    metrics['recent_prs'].append({
                        'title': pr.title,
                        'state': pr.state,
                        'created_at': pr.created_at.isoformat() if pr.created_at else None
                    })
            
            dev.metrics = metrics
            dev.last_updated = datetime.now(timezone.utc)
            
            # Only add to session if it's a new developer
            if is_new:
                db.add(dev)
            
            # Commit after each developer to avoid bulk insert conflicts
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Error updating developer {dev_username}: {str(e)}")
                continue
    
    def update_reviewer_metrics(self, db: Session):
        """Update aggregated reviewer metrics."""
        reviewers = db.query(Review.reviewer_login).distinct().all()
        
        for (reviewer_login,) in reviewers:
            if not reviewer_login:
                continue
                
            reviewer = db.query(Reviewer).filter_by(username=reviewer_login).first()
            is_new = False
            if not reviewer:
                reviewer = Reviewer(username=reviewer_login)
                is_new = True
            
            # Calculate metrics
            reviews = db.query(Review).filter_by(reviewer_login=reviewer_login).all()
            reviewer.total_reviews = len(reviews)
            reviewer.approved_reviews = sum(1 for r in reviews if r.state == 'APPROVED')
            reviewer.changes_requested = sum(1 for r in reviews if r.state == 'CHANGES_REQUESTED')
            reviewer.commented_reviews = sum(1 for r in reviews if r.state == 'COMMENTED')
            reviewer.dismissed_reviews = sum(1 for r in reviews if r.state == 'DISMISSED')
            
            # Calculate detailed metrics
            metrics = {
                'domains': {},
                'recent_reviews': []
            }
            
            for review in reviews[:20]:  # Last 20 reviews
                pr = review.pull_request
                if pr and pr.domain:
                    metrics['domains'][pr.domain] = metrics['domains'].get(pr.domain, 0) + 1
                
                if len(metrics['recent_reviews']) < 5:
                    metrics['recent_reviews'].append({
                        'pr_title': pr.title if pr else 'Unknown',
                        'state': review.state,
                        'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None
                    })
            
            reviewer.metrics = metrics
            reviewer.last_updated = datetime.now(timezone.utc)
            
            # Only add to session if it's a new reviewer
            if is_new:
                db.add(reviewer)
            
            # Commit after each reviewer to avoid bulk insert conflicts
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Error updating reviewer {reviewer_login}: {str(e)}")
                continue
    
    def update_domain_metrics(self, db: Session):
        """Update domain-level metrics."""
        domains = db.query(PullRequest.domain).distinct().all()
        
        for (domain,) in domains:
            if not domain:
                continue
                
            domain_metric = db.query(DomainMetrics).filter_by(domain=domain).first()
            is_new = False
            if not domain_metric:
                domain_metric = DomainMetrics(domain=domain)
                is_new = True
            
            # Get all PRs for this domain
            prs = db.query(PullRequest).filter_by(domain=domain).all()
            domain_metric.total_tasks = len(prs)
            
            # Reset counts
            domain_metric.expert_review_pending = 0
            domain_metric.calibrator_review_pending = 0
            domain_metric.expert_approved = 0
            domain_metric.ready_to_merge = 0
            domain_metric.merged = 0
            domain_metric.expert_count = 0
            domain_metric.hard_count = 0
            domain_metric.medium_count = 0
            
            # Count by state and labels
            for pr in prs:
                if pr.merged:
                    domain_metric.merged += 1
                elif 'ready to merge' in [l.lower() for l in pr.labels]:
                    domain_metric.ready_to_merge += 1
                elif 'expert approved' in [l.lower() for l in pr.labels]:
                    domain_metric.expert_approved += 1
                elif 'calibrator review pending' in [l.lower() for l in pr.labels]:
                    domain_metric.calibrator_review_pending += 1
                elif 'expert review pending' in [l.lower() for l in pr.labels]:
                    domain_metric.expert_review_pending += 1
                
                # Count by difficulty
                if pr.difficulty == 'expert':
                    domain_metric.expert_count += 1
                elif pr.difficulty == 'hard':
                    domain_metric.hard_count += 1
                elif pr.difficulty == 'medium':
                    domain_metric.medium_count += 1
            
            # Calculate detailed metrics
            detailed = {
                'developers': {},
                'reviewers': {},
                'weekly_trend': []
            }
            
            # Count by developer
            for pr in prs:
                if pr.developer_username:
                    detailed['developers'][pr.developer_username] = \
                        detailed['developers'].get(pr.developer_username, 0) + 1
            
            # Count by reviewer
            reviews = db.query(Review).join(PullRequest).filter(PullRequest.domain == domain).all()
            for review in reviews:
                if review.reviewer_login:
                    detailed['reviewers'][review.reviewer_login] = \
                        detailed['reviewers'].get(review.reviewer_login, 0) + 1
            
            domain_metric.detailed_metrics = detailed
            domain_metric.last_updated = datetime.now(timezone.utc)
            
            # Only add to session if it's a new domain metric
            if is_new:
                db.add(domain_metric)
            
            # Commit after each domain to avoid bulk insert conflicts
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Error updating domain {domain}: {str(e)}")
                continue
    
    def update_interface_metrics(self, db: Session):
        """Update interface-level metrics with weekly breakdown."""
        from datetime import datetime, timedelta
        from collections import defaultdict
        
        interfaces = db.query(PullRequest.interface_num).distinct().all()
        
        for (interface_num,) in interfaces:
            if interface_num is None:
                continue
                
            interface_metric = db.query(InterfaceMetrics).filter_by(interface_num=interface_num).first()
            is_new = False
            if not interface_metric:
                interface_metric = InterfaceMetrics(interface_num=interface_num)
                is_new = True
            
            # Get all PRs for this interface
            prs = db.query(PullRequest).filter_by(interface_num=interface_num).all()
            interface_metric.total_tasks = len(prs)
            
            # Reset counts
            interface_metric.discarded = 0
            interface_metric.expert_approved = 0
            interface_metric.expert_review_pending = 0
            interface_metric.good_task = 0
            interface_metric.merged = 0
            interface_metric.pending_review = 0
            interface_metric.pod_lead_approved = 0
            interface_metric.ready_to_merge = 0
            interface_metric.resubmitted = 0
            interface_metric.rework = 0
            
            # Reset complexity counts
            interface_metric.all_expert_count = 0
            interface_metric.all_hard_count = 0
            interface_metric.all_medium_count = 0
            interface_metric.merged_expert_count = 0
            interface_metric.merged_hard_count = 0
            interface_metric.merged_medium_count = 0
            
            # Weekly stats structure
            weekly_stats = defaultdict(lambda: {
                'total': 0,
                'merged': 0,
                'statuses': defaultdict(int),
                'complexity': defaultdict(int)
            })
            
            # Process each PR
            for pr in prs:
                # Get week key (start of week)
                week_start = pr.created_at - timedelta(days=pr.created_at.weekday())
                week_key = week_start.strftime('%Y-%m-%d')
                
                # Update weekly stats
                weekly_stats[week_key]['total'] += 1
                if pr.complexity:
                    weekly_stats[week_key]['complexity'][pr.complexity] += 1
                
                # Count PR statuses based on labels
                pr_labels_lower = [l.lower() for l in pr.labels] if pr.labels else []
                
                if pr.merged:
                    interface_metric.merged += 1
                    weekly_stats[week_key]['merged'] += 1
                    weekly_stats[week_key]['statuses']['merged'] += 1
                    
                    # Complexity distribution for merged
                    if pr.complexity == 'expert':
                        interface_metric.merged_expert_count += 1
                    elif pr.complexity == 'hard':
                        interface_metric.merged_hard_count += 1
                    elif pr.complexity == 'medium':
                        interface_metric.merged_medium_count += 1
                else:
                    # Complexity distribution for all non-merged
                    if pr.complexity == 'expert':
                        interface_metric.all_expert_count += 1
                    elif pr.complexity == 'hard':
                        interface_metric.all_hard_count += 1
                    elif pr.complexity == 'medium':
                        interface_metric.all_medium_count += 1
                    
                    # Count by label status
                    if 'discarded' in pr_labels_lower:
                        interface_metric.discarded += 1
                        weekly_stats[week_key]['statuses']['discarded'] += 1
                    elif 'ready to merge' in pr_labels_lower:
                        interface_metric.ready_to_merge += 1
                        weekly_stats[week_key]['statuses']['ready_to_merge'] += 1
                    elif 'pod lead approved' in pr_labels_lower:
                        interface_metric.pod_lead_approved += 1
                        weekly_stats[week_key]['statuses']['pod_lead_approved'] += 1
                    elif 'expert approved' in pr_labels_lower:
                        interface_metric.expert_approved += 1
                        weekly_stats[week_key]['statuses']['expert_approved'] += 1
                    elif 'good task' in pr_labels_lower:
                        interface_metric.good_task += 1
                        weekly_stats[week_key]['statuses']['good_task'] += 1
                    elif 'expert review pending' in pr_labels_lower:
                        interface_metric.expert_review_pending += 1
                        weekly_stats[week_key]['statuses']['expert_review_pending'] += 1
                    elif 'pending review' in pr_labels_lower:
                        interface_metric.pending_review += 1
                        weekly_stats[week_key]['statuses']['pending_review'] += 1
                    elif 'resubmitted' in pr_labels_lower:
                        interface_metric.resubmitted += 1
                        weekly_stats[week_key]['statuses']['resubmitted'] += 1
                
                # Count rework (requested changes)
                interface_metric.rework += pr.rework_count
            
            # Convert weekly_stats to regular dict for JSON storage
            interface_metric.weekly_stats = dict(weekly_stats)
            
            # Calculate detailed metrics
            detailed = {
                'trainers': {},
                'reviewers': {},
                'domains': {},
                'complexity_percentages': {
                    'merged': {
                        'expert': round((interface_metric.merged_expert_count / interface_metric.merged * 100) if interface_metric.merged > 0 else 0, 2),
                        'hard': round((interface_metric.merged_hard_count / interface_metric.merged * 100) if interface_metric.merged > 0 else 0, 2),
                        'medium': round((interface_metric.merged_medium_count / interface_metric.merged * 100) if interface_metric.merged > 0 else 0, 2)
                    },
                    'all_statuses': {
                        'expert': round((interface_metric.all_expert_count / (interface_metric.total_tasks - interface_metric.merged) * 100) if (interface_metric.total_tasks - interface_metric.merged) > 0 else 0, 2),
                        'hard': round((interface_metric.all_hard_count / (interface_metric.total_tasks - interface_metric.merged) * 100) if (interface_metric.total_tasks - interface_metric.merged) > 0 else 0, 2),
                        'medium': round((interface_metric.all_medium_count / (interface_metric.total_tasks - interface_metric.merged) * 100) if (interface_metric.total_tasks - interface_metric.merged) > 0 else 0, 2)
                    }
                }
            }
            
            # Count by trainer and domain
            for pr in prs:
                if pr.trainer_name:
                    detailed['trainers'][pr.trainer_name] = \
                        detailed['trainers'].get(pr.trainer_name, 0) + 1
                if pr.domain:
                    detailed['domains'][pr.domain] = \
                        detailed['domains'].get(pr.domain, 0) + 1
            
            # Count by reviewer
            reviews = db.query(Review).join(PullRequest).filter(PullRequest.interface_num == interface_num).all()
            for review in reviews:
                if review.reviewer_login:
                    detailed['reviewers'][review.reviewer_login] = \
                        detailed['reviewers'].get(review.reviewer_login, 0) + 1
            
            interface_metric.detailed_metrics = detailed
            interface_metric.last_updated = datetime.now(timezone.utc)
            
            # Only add to session if it's a new interface metric
            if is_new:
                db.add(interface_metric)
            
            # Commit after each interface to avoid bulk insert conflicts
            try:
                db.commit()
            except Exception as e:
                db.rollback()
                logger.warning(f"Error updating interface {interface_num}: {str(e)}")
                continue
    
    def get_incremental_updates(self, db: Session, last_sync: datetime) -> int:
        """
        Get incremental updates since last sync.
        
        Optimizations:
        - Smart sync: checks what actually changed before doing expensive API calls
        - Skips nested data (files/reviews/checks) for closed PRs with complete data
        - Early break when reaching PRs older than last sync
        """
        synced_count = 0
        skipped_count = 0
        checked_count = 0
        quick_updates = 0
        
        # Ensure last_sync is timezone-aware
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        
        logger.info(f"Starting incremental sync for PRs updated after {last_sync}")
        
        # Get recently updated PRs - explicitly sort by updated date descending
        # Note: PyGithub handles pagination automatically (100 PRs per page - set in __init__)
        try:
            for pr in self.repo.get_pulls(
                state='all', 
                sort='updated', 
                direction='desc'
            ):
                checked_count += 1
                
                # Check if PR was updated after last sync
                if pr.updated_at <= last_sync:
                    # Since PRs are sorted by updated_at desc, once we hit an old PR,
                    # all remaining PRs will be even older, so we can break
                    logger.info(f"Reached PRs older than last sync at PR #{pr.number} (updated: {pr.updated_at})")
                    break
                
                # Smart sync: Check what actually changed to avoid unnecessary API calls
                db_pr = db.query(PullRequest).filter_by(github_id=pr.id).first()
                
                if db_pr:
                    # PR exists - determine if we need full sync or just metadata update
                    needs_full_sync = False
                    skip_nested = False
                    
                    # Check if significant changes happened (these are FREE - no API calls)
                    metadata_changed = (
                        db_pr.state != pr.state or
                        db_pr.merged != pr.merged or
                        db_pr.title != pr.title
                    )
                    
                    if metadata_changed:
                        logger.debug(f"PR #{pr.number}: Metadata changed")
                        needs_full_sync = True
                    
                    # Open PRs might have new commits/reviews - need to check
                    if pr.state == 'open':
                        logger.debug(f"PR #{pr.number}: Open PR, syncing updates")
                        needs_full_sync = True
                    
                    # PR just closed/merged - do final sync with all data
                    elif pr.state == 'closed' and db_pr.state == 'open':
                        logger.info(f"PR #{pr.number}: Just closed/merged, doing final sync")
                        needs_full_sync = True
                    
                    # Closed PR that was already closed - skip expensive nested data fetching
                    elif pr.state == 'closed' and db_pr.state == 'closed' and db_pr.week_id:
                        logger.debug(f"PR #{pr.number}: Closed PR with complete data, quick update")
                        skip_nested = True
                        needs_full_sync = True
                    
                    if not needs_full_sync:
                        # No significant changes - just update timestamp and skip
                        db_pr.last_synced = datetime.now(timezone.utc)
                        skipped_count += 1
                        logger.debug(f"PR #{pr.number}: No significant changes, skipping")
                        continue
                    
                    # Sync with appropriate flags
                    if self.sync_pull_request(pr, db, skip_nested_data=skip_nested):
                        if skip_nested:
                            quick_updates += 1
                        else:
                            synced_count += 1
                        
                        if (synced_count + quick_updates) % 10 == 0:
                            db.commit()
                            logger.info(f"Incremental sync progress: {synced_count} full, {quick_updates} quick, {skipped_count} skipped (checked {checked_count})")
                    else:
                        skipped_count += 1
                else:
                    # New PR - do full sync
                    if self.sync_pull_request(pr, db):
                        synced_count += 1
                        if synced_count % 10 == 0:
                            db.commit()
                            logger.info(f"Incremental sync progress: {synced_count} new PRs synced")
                    else:
                        skipped_count += 1
                
                # Safety limit to prevent runaway syncs (reduced from 500)
                if checked_count > 200:
                    logger.warning(f"Checked 200 PRs, stopping incremental sync. Consider less frequent syncs or full sync.")
                    break
                    
        except Exception as e:
            logger.error(f"Error during incremental sync: {str(e)}")
            db.rollback()
            raise
        
        db.commit()
        
        logger.info(f"Incremental sync complete: {synced_count} full syncs, {quick_updates} quick updates, {skipped_count} skipped, {checked_count} checked total")
        
        # Update metrics if we synced any PRs
        if synced_count > 0 or quick_updates > 0:
            logger.info("Updating aggregated metrics...")
            self.update_developer_metrics(db)
            self.update_reviewer_metrics(db)
            self.update_domain_metrics(db)
            self.update_interface_metrics(db)
            logger.info("Metrics updated successfully")
        
        # ALWAYS update last sync time, even if no updates found
        # This prevents repeatedly checking the same time period
        update_last_sync_time(db)
        logger.info("Sync state updated")
        
        return synced_count + quick_updates  # Total number of PRs updated
    
    def parse_task_filename(self, filename: str) -> Optional[Dict]:
        """Parse task filename to extract trainer, domain, interface, complexity, and timestamp."""
        # Remove .json extension if present
        name = filename.replace('.json', '')
        match = self.task_file_pattern.match(name)
        if match:
            trainer_name = match.group(1)
            domain = match.group(2)
            interface_num = int(match.group(3))
            complexity = match.group(4)
            timestamp = match.group(5)
            
            # Fix malformed domains (same logic as parse_pr_title)
            domain_normalized = domain.replace('-', '_')
            
            if domain_normalized in self.valid_domains:
                domain = domain_normalized
            elif domain in ['expert', 'experts', 'hard', 'medium', 'management', 'payroll', 'finance', 'wiki', 'home', 'incident']:
                parts = trainer_name.split('-')
                if len(parts) > 1:
                    potential_prefix = parts[-1]
                    potential_domain = f"{potential_prefix}_{domain}"
                    if potential_domain in self.valid_domains:
                        trainer_name = '-'.join(parts[:-1])
                        domain = potential_domain
            
            return {
                'trainer_name': trainer_name,
                'domain': domain,
                'interface_num': interface_num,
                'complexity': complexity,
                'timestamp': timestamp,
                'filename': filename
            }
        return None

