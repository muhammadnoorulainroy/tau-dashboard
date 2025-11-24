#!/usr/bin/env python3
"""
Sync complete data for the last 3 days only.
This is like a full sync but limited to PRs updated in the last 3 days.

Runs automatically every 24 hours as a background task.
Safe to run concurrently with hourly incremental sync (uses database locking).
"""

import sys
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from dotenv import load_dotenv

backend_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_dir))

# Load .env file from backend directory
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)
    print(f"Loaded environment from: {env_path}")
else:
    print(f"Warning: .env file not found at {env_path}")

from database import SessionLocal, PullRequest, ActionEmbedding
from github_service import GitHubService
from config import settings
from sqlalchemy import text
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def sync_last_3_days():
    """
    Perform a full sync for PRs updated in the last 3 days.
    This includes:
    - Open PRs updated in last 3 days
    - Merged PRs updated in last 3 days
    - All reviews for those PRs
    - All check runs for those PRs
    - Task execution results
    - Developer/Reviewer metrics updates
    - Domain metrics updates
    
    Note: Closed (non-merged) PRs are excluded
    """
    
    print("\n" + "="*80)
    print("SYNCING LAST 3 DAYS DATA")
    print("="*80)
    print(f"\nRepository: {settings.github_repo}")
    print(f"Time Range: Last 3 days")
    print("\nThis will:")
    print("  - Fetch open and merged PRs updated in the last 3 days")
    print("  - NOTE: Closed (non-merged) PRs are excluded")
    print("  - Update reviews, check runs, and task results")
    print("  - Recalculate all metrics (developers, reviewers, domains)")
    print("\n" + "="*80 + "\n")
    
    db = SessionLocal()
    github_service = GitHubService()
    
    try:
        # Acquire PostgreSQL advisory lock to prevent concurrent syncs
        # Lock ID: 123456 (arbitrary number for "last 3 days sync")
        logger.info("Acquiring database lock to prevent concurrent syncs...")
        result = db.execute(text("SELECT pg_try_advisory_lock(123456)"))
        lock_acquired = result.scalar()
        
        if not lock_acquired:
            logger.warning("Another sync process is already running. Exiting.")
            print("\n" + "="*80)
            print("SYNC SKIPPED - Another sync is already in progress")
            print("="*80)
            return
        
        logger.info("Lock acquired. Starting sync...")
        
    except Exception as e:
        logger.error(f"Error acquiring lock: {str(e)}")
        return
    
    try:
        # Calculate date range
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=3)
        
        logger.info(f"Fetching PRs from {start_date.isoformat()} to {end_date.isoformat()}")
        
        # Fetch PRs from the last 3 days
        repo = github_service.repo
        
        # Get PRs updated in last 3 days
        all_prs = []
        
        # Fetch closed/merged PRs
        # Note: GitHub returns both merged and closed (non-merged) PRs with state='closed'
        # Fetch closed PRs (includes merged PRs since merged PRs have state='closed')
        logger.info("Fetching closed/merged PRs from last 3 days...")
        closed_prs = repo.get_pulls(
            state='closed',
            sort='updated',
            direction='desc'
        )
        
        closed_count = 0
        for pr in closed_prs:
            # Stop when we reach PRs older than 3 days
            if pr.updated_at < start_date:
                break
            all_prs.append(pr)
            closed_count += 1
            if closed_count % 50 == 0:
                logger.info(f"  Fetched {closed_count} closed/merged PRs...")
        
        logger.info(f"Found {closed_count} closed/merged PRs (includes both merged and closed non-merged)")
        
        # Fetch open PRs
        logger.info("Fetching open PRs from last 3 days...")
        open_prs = repo.get_pulls(
            state='open',
            sort='updated',
            direction='desc'
        )
        
        open_count = 0
        for pr in open_prs:
            # Stop when we reach PRs older than 3 days
            if pr.updated_at < start_date:
                break
            all_prs.append(pr)
            open_count += 1
            if open_count % 50 == 0:
                logger.info(f"  Fetched {open_count} open PRs...")
        
        logger.info(f"Found {open_count} open PRs")
        
        total_prs = len(all_prs)
        logger.info(f"\nTotal PRs to sync: {total_prs}")
        
        if total_prs == 0:
            logger.warning("No PRs found in the last 3 days!")
            return
        
        # Sync each PR with all its data
        logger.info("\nSyncing PRs with complete data...")
        synced_count = 0
        skipped_count = 0
        
        for i, pr in enumerate(all_prs, 1):
            try:
                # Skip closed (non-merged) PRs - we only want open and merged PRs
                if pr.state == 'closed' and not pr.merged:
                    skipped_count += 1
                    continue
                
                # Sync PR with all nested data (reviews, check runs, task results)
                db_pr = github_service.sync_pull_request(pr, db, skip_nested_data=False)
                
                if db_pr:
                    synced_count += 1
                else:
                    skipped_count += 1
                
                # Commit every 50 PRs to reduce lock duration and prevent deadlocks
                if i % 50 == 0:
                    try:
                        db.commit()
                        logger.info(f"  Progress: {i}/{total_prs} PRs processed (Synced: {synced_count}, Skipped: {skipped_count}) - Committed")
                    except Exception as commit_error:
                        logger.error(f"Error committing batch: {str(commit_error)}")
                        db.rollback()
                elif i % 10 == 0:
                    # Progress update every 10 PRs (without commit)
                    logger.info(f"  Progress: {i}/{total_prs} PRs processed (Synced: {synced_count}, Skipped: {skipped_count})")
                
            except Exception as e:
                logger.error(f"Error syncing PR #{pr.number}: {str(e)}")
                skipped_count += 1
                # Rollback the failed PR transaction
                db.rollback()
                continue
        
        logger.info(f"\nPR sync complete: {synced_count} synced, {skipped_count} skipped")
        
        # Check for reverted PRs and mark rework submissions
        logger.info("\n" + "="*80)
        logger.info("Checking for reverted PRs and marking rework submissions...")
        logger.info("="*80)
        
        # Mark reverted PRs (folders that no longer exist on main branch)
        logger.info("Verifying folder existence on main branch...")
        reverted_count = github_service.mark_reverted_prs(db)
        logger.info(f"Marked {reverted_count} PRs as reverted")
        
        # Mark initial submissions (first PR per folder, rest are rework)
        logger.info("Identifying initial submissions vs rework PRs...")
        initial_count = github_service.mark_initial_submissions(db)
        logger.info(f"Marked {initial_count} PRs as initial submissions")
        
        # CRITICAL: Recalculate metrics with updated revert flags
        logger.info("\nRecalculating metrics with updated revert flags...")
        github_service.update_developer_metrics(db)
        logger.info("Developer metrics updated")
        
        github_service.update_reviewer_metrics(db)
        logger.info("Reviewer metrics updated")
        
        github_service.update_domain_metrics(db)
        logger.info("Domain metrics updated")
        
        github_service.update_interface_metrics(db)
        logger.info("Interface metrics updated")
        
        # Generate action embeddings and calculate similarities
        logger.info("\n" + "="*80)
        logger.info("Generating action embeddings and calculating similarities...")
        logger.info("="*80)
        
        embeddings_created = 0
        total_similarities = 0
        
        try:
            from action_similarity_service import ActionSimilarityService
            action_service = ActionSimilarityService()
            
            # Get all merged PRs without action embeddings (from last 3 days)
            logger.info("Finding PRs that need action embeddings...")
            prs_without_embeddings = db.query(PullRequest).outerjoin(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True),
                PullRequest.updated_at >= start_date,
                ActionEmbedding.id == None
            ).all()
            
            logger.info(f"Found {len(prs_without_embeddings)} PRs without action embeddings")
            
            # Generate embeddings
            new_pr_ids = []
            for pr in prs_without_embeddings:
                try:
                    embedding = action_service.get_or_create_embedding(pr, db)
                    if embedding:
                        embeddings_created += 1
                        new_pr_ids.append(pr.id)
                        if embeddings_created % 10 == 0:
                            logger.info(f"  Generated {embeddings_created}/{len(prs_without_embeddings)} embeddings...")
                except Exception as e:
                    logger.warning(f"  Failed to generate embedding for PR #{pr.number}: {e}")
            
            logger.info(f"Generated {embeddings_created} action embeddings")
            
            # Calculate similarities for new PRs against existing ones
            if new_pr_ids:
                logger.info("")
                logger.info("Calculating action similarities for new PRs...")
                
                # Get distinct domains from new PRs
                domains = db.query(PullRequest.domain).filter(
                    PullRequest.id.in_(new_pr_ids)
                ).distinct().all()
                
                for (domain,) in domains:
                    if not domain:
                        continue
                    logger.info(f"  Processing domain: {domain}")
                    domain_new_prs = [pr_id for pr_id in new_pr_ids if db.query(PullRequest).filter(
                        PullRequest.id == pr_id, PullRequest.domain == domain
                    ).first()]
                    similarity_count = action_service.calculate_similarity_for_new_prs(domain, domain_new_prs, db)
                    total_similarities += similarity_count
                    logger.info(f"    Calculated {similarity_count} similarity pairs")
                
                logger.info(f"Total action similarities calculated: {total_similarities}")
            
        except Exception as e:
            logger.error(f"Error generating action similarities: {e}", exc_info=True)
            logger.warning("Action similarity generation failed, but sync completed successfully")
        
        # Final commit for any remaining changes
        db.commit()
        
        print("\n" + "="*80)
        print("SYNC COMPLETE")
        print("="*80)
        print(f"\nSummary:")
        print(f"  Total PRs found: {total_prs}")
        print(f"  Successfully synced: {synced_count} (open + merged)")
        print(f"  Skipped: {skipped_count} (includes closed non-merged PRs)")
        print(f"  Reverted PRs: {reverted_count}")
        print(f"  Initial submissions: {initial_count}")
        print(f"  Rework PRs: {synced_count - initial_count - reverted_count}")
        print(f"  Action embeddings: {embeddings_created}")
        print(f"  Action similarities: {total_similarities}")
        print(f"  Time range: {start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')}")
        print("\n" + "="*80 + "\n")
        
    except Exception as e:
        logger.error(f"Error during sync: {str(e)}")
        db.rollback()
        raise
    finally:
        # Release the advisory lock
        try:
            db.execute(text("SELECT pg_advisory_unlock(123456)"))
            logger.info("Database lock released")
        except Exception as unlock_error:
            logger.warning(f"Error releasing lock: {str(unlock_error)}")
        
        db.close()


if __name__ == "__main__":
    try:
        sync_last_3_days()
    except KeyboardInterrupt:
        print("\n\nSync interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Sync failed: {str(e)}")
        sys.exit(1)

