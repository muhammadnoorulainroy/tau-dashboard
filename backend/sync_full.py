#!/usr/bin/env python3
"""
Full sync script that runs in foreground with visible logs.
This script directly invokes the GitHub sync service with detailed logging.

Usage:
    python sync_full.py              # Sync from oldest PR in DB
    python sync_full.py --days 30    # Sync last 30 days only
    python sync_full.py --days 60    # Sync last 60 days only
"""
import sys
import logging
import argparse
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Load .env file from backend directory
backend_dir = Path(__file__).resolve().parent
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)

from database import SessionLocal, PullRequest, ActionEmbedding
from github_service import GitHubService
from config import settings

# Configure logging to show on console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_full_sync(days: int = None):
    """
    Run a full sync with detailed logging.
    
    Args:
        days: Number of days to sync. If None, syncs from oldest PR in DB.
    """
    db = SessionLocal()
    
    try:
        # Acquire PostgreSQL advisory lock to prevent concurrent syncs
        # Lock ID: 123456 (same as last-10-days sync to prevent any overlap)
        logger.info("Acquiring database lock to prevent concurrent syncs...")
        result = db.execute(text("SELECT pg_try_advisory_lock(123456)"))
        lock_acquired = result.scalar()
        
        if not lock_acquired:
            logger.warning("Another sync process is already running. Exiting.")
            logger.info("="*80)
            logger.info("SYNC SKIPPED - Another sync is already in progress")
            logger.info("="*80)
            return 0
        
        logger.info("Lock acquired. Starting sync...")
        
        # Determine how far back to sync
        logger.info("="*80)
        logger.info("FULL SYNC - Starting...")
        logger.info("="*80)
        
        if days is not None:
            # User specified number of days
            days_back = days
            logger.info(f"User specified: Will sync PRs from last {days_back} days")
        else:
            # Auto-calculate from oldest PR in database
            oldest_pr = db.query(PullRequest).order_by(PullRequest.created_at.asc()).first()
            
            if oldest_pr and oldest_pr.created_at:
                created = oldest_pr.created_at
                # Make timezone-aware if needed
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                
                days_back = (datetime.now(timezone.utc) - created).days + 7
                logger.info(f"Oldest PR in database: {oldest_pr.title}")
                logger.info(f"Created at: {created}")
                logger.info(f"Will sync PRs from last {days_back} days")
            else:
                days_back = 365
                logger.warning("No PRs found in database, will sync last 365 days")
        
        logger.info("="*80)
        logger.info("")
        
        # Initialize GitHub service
        logger.info("Initializing GitHub service...")
        github_service = GitHubService()
        
        logger.info("")
        logger.info("Starting FULL sync (this may take several minutes)...")
        logger.info("This will fetch and re-process PRs from the last %d days", days_back)
        logger.info("All metrics (check counts, task results, etc.) will be updated")
        logger.info("")
        
        synced_count = github_service.sync_all_prs(db, since_days=days_back)
        
        logger.info("")
        logger.info("="*80)
        logger.info("Checking for reverted PRs and marking rework submissions...")
        logger.info("="*80)
        logger.info("")
        
        # Mark reverted PRs (folders that no longer exist on main branch)
        logger.info("Verifying folder existence on main branch...")
        reverted_count = github_service.mark_reverted_prs(db)
        logger.info(f"Marked {reverted_count} PRs as reverted")
        
        # Mark initial submissions (first PR per folder, rest are rework)
        logger.info("Identifying initial submissions vs rework PRs...")
        initial_count = github_service.mark_initial_submissions(db)
        logger.info(f"Marked {initial_count} PRs as initial submissions")
        
        # CRITICAL: Recalculate metrics with updated revert flags
        logger.info("")
        logger.info("Recalculating metrics with updated revert flags...")
        github_service.update_developer_metrics(db)
        github_service.update_reviewer_metrics(db)
        github_service.update_domain_metrics(db)
        github_service.update_interface_metrics(db)
        logger.info("Metrics recalculated successfully")
        
        # Generate action embeddings and calculate similarities
        logger.info("")
        logger.info("="*80)
        logger.info("Generating action embeddings and calculating similarities...")
        logger.info("="*80)
        logger.info("")
        
        embeddings_created = 0
        total_similarities = 0
        
        try:
            from action_similarity_service import ActionSimilarityService
            action_service = ActionSimilarityService()
            
            # Get all merged PRs without action embeddings
            logger.info("Finding PRs that need action embeddings...")
            prs_without_embeddings = db.query(PullRequest).outerjoin(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True),
                ActionEmbedding.id == None  # No embedding exists
            ).all()
            
            logger.info(f"Found {len(prs_without_embeddings)} PRs without action embeddings")
            
            # Generate embeddings
            embeddings_created = 0
            for pr in prs_without_embeddings:
                try:
                    embedding = action_service.get_or_create_embedding(pr, db)
                    if embedding:
                        embeddings_created += 1
                        if embeddings_created % 10 == 0:
                            logger.info(f"  Generated {embeddings_created}/{len(prs_without_embeddings)} embeddings...")
                except Exception as e:
                    logger.warning(f"  Failed to generate embedding for PR #{pr.number}: {e}")
            
            logger.info(f"Generated {embeddings_created} action embeddings")
            
            # Calculate similarities for each domain
            logger.info("")
            logger.info("Calculating action similarities by domain...")
            
            # Get distinct domains with action embeddings
            domains = db.query(PullRequest.domain).join(
                ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
            ).filter(
                PullRequest.merged == True,
                PullRequest.is_reverted.isnot(True)
            ).distinct().all()
            
            total_similarities = 0
            for (domain,) in domains:
                if not domain:
                    continue
                logger.info(f"  Processing domain: {domain}")
                similarity_count = action_service.calculate_similarity_for_domain(domain, db)
                total_similarities += similarity_count
                logger.info(f"    Calculated {similarity_count} similarity pairs")
            
            logger.info(f"Total action similarities calculated: {total_similarities}")
            
        except Exception as e:
            logger.error(f"Error generating action similarities: {e}", exc_info=True)
            logger.warning("Action similarity generation failed, but sync completed successfully")
        
        # Get actual database totals for summary
        total_merged = db.query(PullRequest).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True)
        ).count()
        
        total_initial = db.query(PullRequest).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True),
            PullRequest.is_initial_submission == True
        ).count()
        
        total_rework = db.query(PullRequest).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True),
            PullRequest.is_initial_submission == False
        ).count()
        
        total_reverted = db.query(PullRequest).filter(
            PullRequest.is_reverted == True
        ).count()
        
        logger.info("")
        logger.info("="*80)
        logger.info(f"FULL SYNC COMPLETED")
        logger.info(f"   PRs synced this run: {synced_count}")
        logger.info(f"   PRs marked reverted this run: {reverted_count}")
        logger.info(f"   PRs marked initial this run: {initial_count}")
        logger.info("")
        logger.info(f"DATABASE TOTALS:")
        logger.info(f"   Total merged tasks (unique): {total_initial}")
        logger.info(f"   Total rework PRs: {total_rework}")
        logger.info(f"   Total reverted PRs: {total_reverted}")
        logger.info(f"   Total merged (non-reverted): {total_merged}")
        logger.info(f"   Action embeddings generated: {embeddings_created}")
        logger.info(f"   Action similarities calculated: {total_similarities}")
        logger.info("="*80)
        
        return synced_count
        
    except KeyboardInterrupt:
        logger.warning("\n\nSync interrupted by user (Ctrl+C)")
        logger.info("Partial sync may have completed. Run again to continue.")
        return 0
    except Exception as e:
        logger.error(f"Error during full sync: {str(e)}", exc_info=True)
        return 0
    finally:
        # Release the advisory lock
        try:
            db.execute(text("SELECT pg_advisory_unlock(123456)"))
            logger.info("Database lock released")
        except Exception as unlock_error:
            logger.warning(f"Error releasing lock: {str(unlock_error)}")
        
        db.close()

if __name__ == "__main__":
    # Parse command-line arguments
    parser = argparse.ArgumentParser(
        description='Full sync script for TAU Dashboard',
        epilog='''
Examples:
  python sync_full.py              # Sync from oldest PR in database
  python sync_full.py --days 30    # Sync last 30 days only (faster)
  python sync_full.py --days 60    # Sync last 60 days only
        '''
    )
    parser.add_argument(
        '--days',
        type=int,
        help='Number of days to sync (default: auto-detect from oldest PR)'
    )
    
    args = parser.parse_args()
    
    logger.info("TAU Dashboard - Full Sync")
    logger.info("")
    
    synced_count = run_full_sync(days=args.days)
    
    if synced_count > 0:
        logger.info("")
        logger.info("Sync completed successfully")
        logger.info("Check the dashboard to see updated metrics.")
        sys.exit(0)
    else:
        logger.warning("")
        logger.warning("Sync completed with no updates or encountered errors.")
        sys.exit(1)

