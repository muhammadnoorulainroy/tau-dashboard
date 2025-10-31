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

