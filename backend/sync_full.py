#!/usr/bin/env python3
"""
Full sync script that runs in foreground with visible logs.
This script directly invokes the GitHub sync service with detailed logging.
"""
import sys
import logging
from datetime import datetime, timezone
from pathlib import Path
from dotenv import load_dotenv
from sqlalchemy import text

# Load .env file from backend directory
backend_dir = Path(__file__).resolve().parent
env_path = backend_dir / '.env'
if env_path.exists():
    load_dotenv(env_path)

from database import SessionLocal, PullRequest
from github_service import GitHubService
from config import settings

# Configure logging to show on console
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

def run_full_sync():
    """Run a full sync with detailed logging"""
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
        
        # Get oldest PR to determine how far back to sync
        logger.info("="*80)
        logger.info("FULL SYNC - Starting...")
        logger.info("="*80)
        
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
        logger.info(f"FULL SYNC COMPLETED")
        logger.info(f"   Total PRs synced: {synced_count}")
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
    logger.info("TAU Dashboard - Full Sync")
    logger.info("")
    
    synced_count = run_full_sync()
    
    if synced_count > 0:
        logger.info("")
        logger.info("Sync completed successfully")
        logger.info("Check the dashboard to see updated metrics.")
        sys.exit(0)
    else:
        logger.warning("")
        logger.warning("Sync completed with no updates or encountered errors.")
        sys.exit(1)

