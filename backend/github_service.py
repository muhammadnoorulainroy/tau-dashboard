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
        self.github = Github(settings.github_token)
        self.repo = self.github.get_repo(settings.github_repo)
        
        # Known valid domains (for fixing malformed PR titles)
        self.valid_domains = set(settings.allowed_domains)
        
        # Pattern to match PRs: {trainer_name}-{domain}-{interface_num}-{complexity_level}-{timestamp}
        # Example: haseeb-fund_finance-3-expert-1760428727
        # NOTE: Made trainer name non-greedy to avoid consuming domain parts
        self.pr_pattern = re.compile(r'^([a-zA-Z0-9\._-]+?)-([\w_-]+)-(\d+)-(expert|hard|medium)-(\d{10})$')
        # Pattern for task files (same format, but may have .json extension)
        self.task_file_pattern = re.compile(r'^([a-zA-Z0-9\._-]+?)-([\w_-]+)-(\d+)-(expert|hard|medium)-(\d{10})(?:\.json)?$')
        # Pattern to extract week and pod from file paths: week_12/bandreddy_pod/task_name/...
        self.week_pod_pattern = re.compile(r'^week_(\d+)/([^/]+)/')
        
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
        """Check if PR matches our criteria (has proper format and tags)."""
        # Check if title matches our pattern
        if not self.parse_pr_title(pr.title):
            return False
        
        # Check if PR has labels (tags)
        if not pr.labels:
            return False
            
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
        existing = db.query(UserDomainAssignment).filter_by(
            user_id=user.id,
            domain_id=domain.id
        ).first()
        
        if not existing:
            assignment = UserDomainAssignment(
                user_id=user.id,
                domain_id=domain.id
            )
            db.add(assignment)
            db.flush()
            logger.info(f"Assigned user {user.github_username} to domain {domain.domain_name}")
    
    def parse_week_pod_from_pr_files(self, pr) -> Optional[Tuple[int, str]]:
        """
        Parse week number and pod name from PR file changes.
        Expected format: week_12/bandreddy_pod/task_folder/...
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
    
    def sync_pull_request(self, pr, db: Session) -> Optional[PullRequest]:
        """Sync a single pull request to the database."""
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
            
            # Update counts
            db_pr.review_count = pr.review_comments
            db_pr.comment_count = pr.comments
            
            # Calculate rework (changes requested reviews only)
            db_pr.rework_count = self.calculate_rework_count(pr, db)
            
            # Calculate failed automated checks (separate from rework)
            db_pr.check_failures = self.calculate_failed_checks_count(pr)
            
            # ===========================
            # MIGRATION-AWARE: Create entities and set foreign keys
            # ===========================
            
            # 1. Create/get trainer (user)
            trainer = self.get_or_create_user(pr.user.login, 'trainer', db)
            db_pr.trainer_id = trainer.id
            
            # 2. Create/get domain
            domain = self.get_or_create_domain(parsed['domain'], db)
            db_pr.domain_id = domain.id
            
            # 3. Create/get interface (linked to domain)
            interface = self.get_or_create_interface(domain, parsed['interface_num'], db)
            db_pr.interface_id = interface.id
            
            # 4. Parse and create/get week and pod from PR file changes
            week_pod_info = self.parse_week_pod_from_pr_files(pr)
            if week_pod_info:
                week_num, pod_name = week_pod_info
                week = self.get_or_create_week(week_num, db)
                pod = self.get_or_create_pod(pod_name, db)
                db_pr.week_id = week.id
                db_pr.pod_id = pod.id
            
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
            self.sync_reviews(pr, db_pr, db)
            self.sync_check_runs(pr, db_pr, db)
            
            return db_pr
            
        except Exception as e:
            logger.error(f"Error syncing PR {pr.number}: {str(e)}")
            return None
    
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
            
            check_failures = 0
            for check in check_runs:
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
                
                if check.conclusion == 'failure':
                    check_failures += 1
            
            db_pr.check_failures = check_failures
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
        for pr in self.repo.get_pulls(state='open', sort='created', direction='asc'):
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
        """Get incremental updates since last sync."""
        synced_count = 0
        skipped_count = 0
        checked_count = 0
        
        # Ensure last_sync is timezone-aware
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        
        logger.info(f"Starting incremental sync for PRs updated after {last_sync}")
        
        # Get recently updated PRs - explicitly sort by updated date descending
        # GitHub API: sort='updated' returns PRs sorted by most recently updated first
        try:
            for pr in self.repo.get_pulls(state='all', sort='updated', direction='desc'):
                checked_count += 1
                
                # Check if PR was updated after last sync
                if pr.updated_at <= last_sync:
                    # Since PRs are sorted by updated_at desc, once we hit an old PR,
                    # all remaining PRs will be even older, so we can break
                    logger.info(f"Reached PRs older than last sync at PR #{pr.number} (updated: {pr.updated_at})")
                    break
                
                # Try to sync this PR
                if self.sync_pull_request(pr, db):
                    synced_count += 1
                    if synced_count % 10 == 0:
                        db.commit()
                        logger.info(f"Incremental sync progress: synced {synced_count} PRs (checked {checked_count})...")
                else:
                    skipped_count += 1
                
                # Safety limit to prevent runaway syncs
                if checked_count > 500:
                    logger.warning(f"Checked 500 PRs, stopping incremental sync. Consider a full sync.")
                    break
                    
        except Exception as e:
            logger.error(f"Error during incremental sync: {str(e)}")
            db.rollback()
            raise
        
        db.commit()
        
        logger.info(f"Incremental sync complete: synced {synced_count} PRs, skipped {skipped_count}, checked {checked_count} total")
        
        # Update metrics if we synced any PRs
        if synced_count > 0:
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
        
        return synced_count
    
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

