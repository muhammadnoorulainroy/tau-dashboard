import asyncio
import logging
from datetime import datetime, timedelta, timezone
from concurrent.futures import ThreadPoolExecutor
from database import SessionLocal
from github_service import GitHubService

logger = logging.getLogger(__name__)

# Thread pool for running blocking operations
executor = ThreadPoolExecutor(max_workers=2)

def _do_sync(last_sync):
    """Run sync in a separate thread to avoid blocking the event loop."""
    try:
        github_service = GitHubService()
        db = SessionLocal()
        
        # Get incremental updates from last hour
        count = github_service.get_incremental_updates(db, last_sync)
        
        db.close()
        return count
    except Exception as e:
        logger.error(f"Error in sync thread: {str(e)}")
        return 0

def _do_3_day_sync():
    """Run 3-day sync in a separate thread to avoid blocking the event loop."""
    try:
        from sync_last_3_days import sync_last_3_days
        return sync_last_3_days()
    except Exception as e:
        logger.error(f"Error in 3-day sync thread: {str(e)}")
        return 0

def _do_similarity_calculation():
    """Run similarity calculation in a separate thread to avoid blocking the event loop."""
    try:
        from similarity_service import SimilarityService
        db = SessionLocal()
        
        similarity_service = SimilarityService()
        
        # Get all domains with merged PRs that have instructions
        from database import PullRequest
        domains = db.query(PullRequest.domain).filter(
            PullRequest.merged == True,
            PullRequest.instruction_text != None,
            PullRequest.instruction_text != ''
        ).distinct().all()
        
        total_domains = len(domains)
        processed = 0
        
        logger.info(f"Starting similarity calculation for {total_domains} domains")
        
        for (domain,) in domains:
            try:
                logger.info(f"Calculating similarities for domain: {domain}")
                similarity_service.calculate_similarity_for_domain(domain, db)
                processed += 1
            except Exception as e:
                logger.error(f"Error calculating similarities for {domain}: {e}")
        
        db.close()
        logger.info(f"Similarity calculation complete for {processed}/{total_domains} domains")
        return processed
    except Exception as e:
        logger.error(f"Error in similarity calculation thread: {str(e)}")
        return 0

async def start_background_sync(connection_manager):
    """Background task to periodically sync with GitHub."""
    try:
        # Wait a bit before starting to ensure the app is fully initialized
        await asyncio.sleep(60)  # Wait 1 minute before first sync
        
        while True:
            try:
                logger.info("Starting background sync (non-blocking)...")
                
                # Run the blocking sync operation in a thread pool
                last_sync = datetime.now(timezone.utc) - timedelta(hours=1)
                loop = asyncio.get_event_loop()
                count = await loop.run_in_executor(executor, _do_sync, last_sync)
                
                if count > 0:
                    logger.info(f"Background sync complete - synced {count} PRs")
                    # Notify WebSocket clients
                    await connection_manager.broadcast({
                        'type': 'data_updated',
                        'data': {
                            'synced_count': count,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    })
                else:
                    logger.debug("Background sync found no updates")
                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.info("Background sync task cancelled, shutting down...")
                raise
            except Exception as e:
                logger.error(f"Error in background sync: {str(e)}")
            
            # Wait for 1 hour between syncs
            await asyncio.sleep(3600)
    
    except asyncio.CancelledError:
        # Clean shutdown
        logger.info("Background sync task stopped")
        executor.shutdown(wait=False)
        raise


async def start_domain_refresh():
    """Background task to periodically refresh allowed domains from GitHub."""
    try:
        # Wait a bit before starting to ensure the app is fully initialized
        await asyncio.sleep(3600)  # Wait 1 hour before first refresh
        
        while True:
            try:
                logger.info("Refreshing allowed domains from GitHub...")
                
                from config import update_allowed_domains, settings
                
                # Update domains from GitHub
                success = update_allowed_domains(force=True)
                
                if success:
                    logger.info(f"Domains refreshed: {len(settings.allowed_domains)} domains")
                    logger.debug(f"   Domains: {', '.join(settings.allowed_domains)}")
                else:
                    logger.warning(f"Domain refresh failed, using cached list: {len(settings.allowed_domains)} domains")
                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.info("Domain refresh task cancelled, shutting down...")
                raise
            except Exception as e:
                logger.error(f"Error refreshing domains: {str(e)}")
            
            # Wait for 1 hour between refreshes
            await asyncio.sleep(3600)
    
    except asyncio.CancelledError:
        # Clean shutdown
        logger.info("Domain refresh task stopped")
        raise


async def start_3_day_sync(connection_manager):
    """Background task to run 3-day sync every 24 hours."""
    try:
        # Wait 1 hour and 15 mins before starting first sync to avoid startup congestion
        await asyncio.sleep(4500)  # 1 hour 15 minutes

        while True:
            try:
                logger.info("Starting 3-day full sync (background)...")
                
                # Run the blocking 3-day sync operation in a thread pool
                loop = asyncio.get_event_loop()
                count = await loop.run_in_executor(executor, _do_3_day_sync)
                
                if count and count > 0:
                    logger.info(f"3-day sync complete - synced {count} PRs")
                    # Notify WebSocket clients
                    await connection_manager.broadcast({
                        'type': 'data_updated',
                        'data': {
                            'sync_type': '3_day_full_sync',
                            'synced_count': count,
                            'timestamp': datetime.now(timezone.utc).isoformat()
                        }
                    })
                else:
                    logger.info("3-day sync completed (no new PRs or error occurred)")
                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.info("3-day sync task cancelled, shutting down...")
                raise
            except Exception as e:
                logger.error(f"Error in 3-day sync: {str(e)}")
            
            # Wait for 24 hours between syncs
            await asyncio.sleep(86400)  # 24 hours
    
    except asyncio.CancelledError:
        # Clean shutdown
        logger.info("3-day sync task stopped")
        raise


async def start_similarity_calculation():
    """Background task to calculate task similarities hourly."""
    try:
        # Wait 1 hour 30 mins before starting first calculation to allow initial sync to complete
        await asyncio.sleep(5400)  # 1 hour 30 minutes
        
        while True:
            try:
                logger.info("Starting similarity calculation (background)...")
                
                # Run the blocking similarity calculation in a thread pool
                loop = asyncio.get_event_loop()
                domains_processed = await loop.run_in_executor(executor, _do_similarity_calculation)
                
                if domains_processed and domains_processed > 0:
                    logger.info(f"Similarity calculation complete - processed {domains_processed} domains")
                else:
                    logger.info("Similarity calculation completed (no domains processed)")
                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.info("Similarity calculation task cancelled, shutting down...")
                raise
            except Exception as e:
                logger.error(f"Error in similarity calculation: {str(e)}")
            
            # Wait for 1 hour between calculations
            await asyncio.sleep(3600)  # 1 hour
    
    except asyncio.CancelledError:
        # Clean shutdown
        logger.info("Similarity calculation task stopped")
        raise

