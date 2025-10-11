import re
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Tuple
from github import Github, GithubException
from sqlalchemy.orm import Session
from database import PullRequest, Review, CheckRun, Developer, Reviewer, DomainMetrics
from config import settings
from sync_state import update_last_sync_time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class GitHubService:
    def __init__(self):
        self.github = Github(settings.github_token)
        self.repo = self.github.get_repo(settings.github_repo)
        # Pattern to match PRs we're interested in: username-domain-difficulty-taskid
        self.pr_pattern = re.compile(r'^([a-zA-Z0-9\._-]+)-([\w_]+)-([\d\w]+)-(expert|hard|medium)-(\d+)$')
        
    def parse_pr_title(self, title: str) -> Optional[Dict]:
        """Parse PR title to extract developer, domain, difficulty, and task ID."""
        match = self.pr_pattern.match(title)
        if match:
            return {
                'developer_username': match.group(1),
                'domain': match.group(2),
                'difficulty': match.group(4),
                'task_id': match.group(5)
            }
        
        # Try alternative pattern without difficulty in specific position
        alt_pattern = re.compile(r'^([a-zA-Z0-9\._-]+)-([\w_]+)-.*-(\d{10,})$')
        match = alt_pattern.match(title)
        if match:
            # Try to extract difficulty from the title
            difficulty = 'unknown'
            if 'expert' in title.lower():
                difficulty = 'expert'
            elif 'hard' in title.lower():
                difficulty = 'hard'
            elif 'medium' in title.lower():
                difficulty = 'medium'
                
            return {
                'developer_username': match.group(1),
                'domain': match.group(2),
                'difficulty': difficulty,
                'task_id': match.group(3)
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
        """Calculate rework count based on feedback and check failures."""
        rework_count = 0
        
        # Count reviews requesting changes
        for review in pr.get_reviews():
            if review.state == 'CHANGES_REQUESTED':
                rework_count += 1
        
        # Count failed checks
        if hasattr(pr, 'get_check_runs'):
            for check in pr.get_check_runs():
                if check.conclusion == 'failure':
                    rework_count += 1
        
        return rework_count
    
    def sync_pull_request(self, pr, db: Session) -> Optional[PullRequest]:
        """Sync a single pull request to the database."""
        try:
            # Check if we should process this PR
            if not self.should_process_pr(pr):
                return None
            
            # Parse PR title
            parsed = self.parse_pr_title(pr.title)
            if not parsed:
                return None
            
            # Check if PR already exists
            db_pr = db.query(PullRequest).filter_by(github_id=pr.id).first()
            if not db_pr:
                db_pr = PullRequest(github_id=pr.id)
            
            # Update PR fields
            db_pr.number = pr.number
            db_pr.title = pr.title
            db_pr.state = pr.state
            db_pr.merged = pr.merged
            db_pr.developer_username = parsed['developer_username']
            db_pr.domain = parsed['domain']
            db_pr.difficulty = parsed['difficulty']
            db_pr.task_id = parsed['task_id']
            db_pr.author_login = pr.user.login
            db_pr.created_at = pr.created_at
            db_pr.updated_at = pr.updated_at
            db_pr.closed_at = pr.closed_at
            db_pr.merged_at = pr.merged_at
            
            # Update labels
            db_pr.labels = [label.name for label in pr.labels]
            
            # Update counts
            db_pr.review_count = pr.review_comments
            db_pr.comment_count = pr.comments
            
            # Calculate rework
            db_pr.rework_count = self.calculate_rework_count(pr, db)
            
            # Sync reviews
            self.sync_reviews(pr, db_pr, db)
            
            # Sync check runs
            self.sync_check_runs(pr, db_pr, db)
            
            db_pr.last_synced = datetime.now(timezone.utc)
            
            db.add(db_pr)
            return db_pr
            
        except Exception as e:
            logger.error(f"Error syncing PR {pr.number}: {str(e)}")
            return None
    
    def sync_reviews(self, pr, db_pr: PullRequest, db: Session):
        """Sync reviews for a pull request."""
        try:
            for review in pr.get_reviews():
                db_review = db.query(Review).filter_by(github_id=review.id).first()
                if not db_review:
                    db_review = Review(
                        github_id=review.id,
                        pull_request_id=db_pr.id,
                        reviewer_login=review.user.login,
                        state=review.state,
                        submitted_at=review.submitted_at,
                        body=review.body
                    )
                    db.add(db_review)
                else:
                    db_review.state = review.state
                    db_review.body = review.body
        except Exception as e:
            logger.error(f"Error syncing reviews for PR {pr.number}: {str(e)}")
    
    def sync_check_runs(self, pr, db_pr: PullRequest, db: Session):
        """Sync check runs for a pull request."""
        try:
            if hasattr(pr, 'get_check_runs'):
                check_failures = 0
                for check in pr.get_check_runs():
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
                    
                    if check.conclusion == 'failure':
                        check_failures += 1
                
                db_pr.check_failures = check_failures
        except Exception as e:
            logger.error(f"Error syncing check runs for PR {pr.number}: {str(e)}")
    
    def sync_all_prs(self, db: Session, since_days: int = 60):
        """Sync all PRs from the last N days."""
        # Use timezone-aware datetime for comparison with GitHub API datetimes
        since = datetime.now(timezone.utc) - timedelta(days=since_days)
        synced_count = 0
        
        logger.info(f"Starting sync for PRs since {since}")
        
        # Sync open PRs
        for pr in self.repo.get_pulls(state='open'):
            if pr.created_at < since:
                break
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 10 == 0:
                    db.commit()
                    logger.info(f"Synced {synced_count} PRs...")
        
        # Sync recently closed PRs
        for pr in self.repo.get_pulls(state='closed'):
            if pr.updated_at < since:
                break
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 10 == 0:
                    db.commit()
                    logger.info(f"Synced {synced_count} PRs...")
        
        db.commit()
        logger.info(f"Sync completed. Total PRs synced: {synced_count}")
        
        # Update aggregated metrics
        self.update_developer_metrics(db)
        self.update_reviewer_metrics(db)
        self.update_domain_metrics(db)
        
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
            dev.total_rework = sum(pr.rework_count for pr in prs)
            
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
        
        db.commit()
    
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
        
        db.commit()
    
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
        
        db.commit()
    
    def get_incremental_updates(self, db: Session, last_sync: datetime) -> int:
        """Get incremental updates since last sync."""
        synced_count = 0
        
        # Ensure last_sync is timezone-aware
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        
        # Get recently updated PRs
        for pr in self.repo.get_pulls(state='all'):
            if pr.updated_at <= last_sync:
                break
            if self.sync_pull_request(pr, db):
                synced_count += 1
                if synced_count % 10 == 0:
                    db.commit()
        
        db.commit()
        
        # Update metrics if we synced any PRs
        if synced_count > 0:
            self.update_developer_metrics(db)
            self.update_reviewer_metrics(db)
            self.update_domain_metrics(db)
        
        # ALWAYS update last sync time, even if no updates found
        # This prevents repeatedly checking the same time period
        update_last_sync_time(db)
        
        return synced_count

