#!/usr/bin/env python3
"""
Backfill script to update existing PRs with NULL week_ids.

This script:
1. Queries all PRs with NULL week_id from the database
2. Fetches their file paths from GitHub
3. Parses week and pod information using the updated regex
4. Updates the week_id and pod_id in the database

Usage:
    python backfill_week_pod.py [--dry-run] [--limit N]

Options:
    --dry-run    Show what would be updated without making changes
    --limit N    Process only N PRs (useful for testing)
"""

import argparse
import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session
from github import Github

from database import SessionLocal, PullRequest, Week, Pod
from config import settings

logger = logging.getLogger(__name__)


class WeekPodBackfiller:
    """Backfills week and pod information for existing PRs."""
    
    def __init__(self, dry_run: bool = False):
        self.dry_run = dry_run
        self.github = Github(settings.github_token)
        self.repo = self.github.get_repo(settings.github_repo)
        
        # Updated pattern to support both formats:
        # 1. Old: week_12/bandreddy_pod/task_name/...
        # 2. New: week_13_hr_talent/mansoor_pod/task_name/...
        self.week_pod_pattern = re.compile(r'^week_(\d+)(?:_[\w_-]+)?/([^/]+)/')
        
        self.stats = {
            'total_checked': 0,
            'found_week_pod': 0,
            'updated': 0,
            'failed': 0,
            'already_has_week': 0
        }
    
    def get_or_create_week(self, week_num: int, db: Session) -> Optional[Week]:
        """Get or create a Week entity."""
        # Use same format as github_service.py to avoid duplicates
        week_name = f"week_{week_num}"  # Lowercase with underscore
        week = db.query(Week).filter_by(week_name=week_name).first()
        
        if not week:
            week = Week(
                week_name=week_name,
                week_num=week_num,
                display_name=f"Week {week_num}",  # Human-readable format for display
                start_date=None,  # Can be updated later if needed
                end_date=None
            )
            db.add(week)
            db.flush()
            logger.info(f"Created new week: {week_name}")
        
        return week
    
    def get_or_create_pod(self, pod_name: str, db: Session) -> Optional[Pod]:
        """Get or create a Pod entity."""
        pod = db.query(Pod).filter_by(name=pod_name).first()
        
        if not pod:
            pod = Pod(
                name=pod_name,
                display_name=pod_name.replace('_', ' ').title(),
                description=f"Pod: {pod_name}"
            )
            db.add(pod)
            db.flush()
            logger.info(f"Created new pod: {pod_name}")
        
        return pod
    
    def parse_week_pod_from_pr(self, pr_github_id: int) -> Optional[Tuple[int, str]]:
        """
        Fetch PR from GitHub and parse week/pod from file paths.
        Returns: (week_num, pod_name) or None if not found
        """
        try:
            pr = self.repo.get_pull(pr_github_id)
            files = pr.get_files()
            
            for file in files:
                match = self.week_pod_pattern.match(file.filename)
                if match:
                    week_num = int(match.group(1))
                    pod_name = match.group(2)
                    return (week_num, pod_name)
        except Exception as e:
            logger.debug(f"Could not parse week/pod for PR #{pr_github_id}: {str(e)}")
        
        return None
    
    def backfill_pr(self, db_pr: PullRequest, db: Session) -> bool:
        """
        Backfill week and pod for a single PR.
        Returns True if updated, False otherwise.
        """
        try:
            # Parse week and pod from GitHub files
            result = self.parse_week_pod_from_pr(db_pr.number)
            
            if not result:
                logger.debug(f"PR #{db_pr.number}: No week/pod found in file paths")
                return False
            
            week_num, pod_name = result
            logger.info(f"PR #{db_pr.number}: Found week={week_num}, pod={pod_name}")
            self.stats['found_week_pod'] += 1
            
            if self.dry_run:
                logger.info(f"[DRY RUN] Would update PR #{db_pr.number} with week={week_num}, pod={pod_name}")
                return True
            
            # Get or create Week and Pod
            week = self.get_or_create_week(week_num, db)
            pod = self.get_or_create_pod(pod_name, db)
            
            # Update the PR
            db_pr.week_id = week.id
            db_pr.pod_id = pod.id
            db_pr.last_synced = datetime.now(timezone.utc)
            
            db.commit()
            logger.info(f"✅ Updated PR #{db_pr.number} with week_id={week.id}, pod_id={pod.id}")
            self.stats['updated'] += 1
            return True
            
        except Exception as e:
            logger.error(f"❌ Error backfilling PR #{db_pr.number}: {str(e)}")
            db.rollback()
            self.stats['failed'] += 1
            return False
    
    def run(self, limit: Optional[int] = None):
        """Run the backfill process."""
        db = SessionLocal()
        try:
            logger.info("=" * 60)
            logger.info("Starting Week/Pod Backfill Process")
            logger.info("=" * 60)
            
            if self.dry_run:
                logger.warning("🔍 DRY RUN MODE - No changes will be made")
            
            # Query PRs with NULL week_id
            query = db.query(PullRequest).filter(PullRequest.week_id == None)
            
            if limit:
                query = query.limit(limit)
                logger.info(f"Processing up to {limit} PRs")
            
            prs_to_update = query.all()
            total = len(prs_to_update)
            
            logger.info(f"Found {total} PRs with NULL week_id")
            
            if total == 0:
                logger.info("✅ No PRs need backfilling!")
                return
            
            # Process each PR
            for i, db_pr in enumerate(prs_to_update, 1):
                logger.info(f"\n[{i}/{total}] Processing PR #{db_pr.number} ({db_pr.title[:50]}...)")
                self.stats['total_checked'] += 1
                
                self.backfill_pr(db_pr, db)
            
            # Print summary
            self.print_summary()
            
        finally:
            db.close()
    
    def print_summary(self):
        """Print backfill summary statistics."""
        logger.info("\n" + "=" * 60)
        logger.info("Backfill Summary")
        logger.info("=" * 60)
        logger.info(f"Total PRs Checked:       {self.stats['total_checked']}")
        logger.info(f"Week/Pod Found:          {self.stats['found_week_pod']}")
        logger.info(f"Successfully Updated:    {self.stats['updated']}")
        logger.info(f"Failed:                  {self.stats['failed']}")
        
        if self.dry_run:
            logger.info("\n🔍 This was a DRY RUN - no changes were made")
        else:
            logger.info(f"\n✅ Backfill complete! Updated {self.stats['updated']} PRs")


def main():
    # Setup logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    parser = argparse.ArgumentParser(
        description="Backfill week and pod information for existing PRs"
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be updated without making changes'
    )
    parser.add_argument(
        '--limit',
        type=int,
        default=None,
        help='Process only N PRs (useful for testing)'
    )
    
    args = parser.parse_args()
    
    backfiller = WeekPodBackfiller(dry_run=args.dry_run)
    backfiller.run(limit=args.limit)


if __name__ == '__main__':
    main()

