"""
Background Tasks for Task Agent V2 data sync and similarity calculation
"""
import asyncio
import logging
from datetime import datetime, timezone, timedelta

logger = logging.getLogger(__name__)

# Sync interval in seconds (10 minutes - no API rate limit)
SYNC_INTERVAL = 600

# Similarity calculation interval in seconds (30 minutes)
SIMILARITY_INTERVAL = 1800

# Jibble sync interval in seconds (15 minutes)
JIBBLE_SYNC_INTERVAL = 900


async def start_task_agent_sync(manager=None):
    """
    Background task that periodically syncs data from Task Agent API
    
    Args:
        manager: Optional WebSocket connection manager for broadcasting updates
    """
    logger.info("Starting Task Agent API background sync task")
    logger.info("Running initial sync immediately on startup...")
    
    first_run = True
    
    while True:
        try:
            # On first run, sync immediately; on subsequent runs, wait for interval
            if not first_run:
                await asyncio.sleep(SYNC_INTERVAL)
            first_run = False
            
            logger.info("=" * 60)
            logger.info("Running scheduled Task Agent API sync")
            logger.info("=" * 60)
            
            # Run sync in thread pool to avoid blocking
            from database_v2 import SessionLocal, init_db_v2
            from task_agent_service import TaskAgentService
            
            def run_sync():
                init_db_v2()
                db = SessionLocal()
                try:
                    service = TaskAgentService()
                    result = service.full_sync(db, fetch_task_details=True)  # Full sync with all details
                    return result
                except Exception as e:
                    logger.error(f"Sync error: {e}")
                    return None
                finally:
                    db.close()
            
            # Run in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_sync)
            
            if result:
                logger.info(f"Scheduled sync complete: {result.get('tasks', 0)} tasks")
                
                # Broadcast update if manager provided
                if manager:
                    await manager.broadcast({
                        "type": "sync_complete",
                        "data": result,
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
            
        except asyncio.CancelledError:
            logger.info("Task Agent sync task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in Task Agent sync task: {e}")
            # Continue running even if there's an error
            await asyncio.sleep(60)  # Wait a minute before retrying


async def start_v2_similarity_calculation():
    """
    Background task that periodically calculates similarity scores for Task Agent data
    """
    logger.info("Starting V2 similarity calculation background task")
    
    # Wait a bit before first run to let initial sync complete
    await asyncio.sleep(300)  # 5 minutes
    
    while True:
        try:
            logger.info("=" * 60)
            logger.info("Running scheduled V2 similarity calculation")
            logger.info("=" * 60)
            
            from database_v2 import SessionLocal
            from similarity_service_v2 import SimilarityServiceV2
            
            def run_similarity():
                db = SessionLocal()
                try:
                    service = SimilarityServiceV2()
                    result = service.calculate_all_similarities(db)
                    return result
                except Exception as e:
                    logger.error(f"Similarity calculation error: {e}")
                    return None
                finally:
                    db.close()
            
            # Run in executor
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_similarity)
            
            if result:
                logger.info(f"Similarity calculation complete: {result.get('domains_processed', 0)} domains")
            
            # Wait for next interval
            await asyncio.sleep(SIMILARITY_INTERVAL)
            
        except asyncio.CancelledError:
            logger.info("V2 similarity calculation task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in V2 similarity calculation task: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying


async def run_initial_sync():
    """
    Run an initial sync on startup if database is empty or stale
    """
    from database_v2 import SessionLocal, SyncStateV2, Task
    
    db = SessionLocal()
    try:
        # Check if we have any tasks
        task_count = db.query(Task).count()
        sync_state = db.query(SyncStateV2).first()
        
        should_sync = False
        
        if task_count == 0:
            logger.info("No tasks in database, triggering initial sync")
            should_sync = True
        elif sync_state and sync_state.last_sync_time:
            # Check if last sync was more than 24 hours ago
            age = datetime.now(timezone.utc) - sync_state.last_sync_time.replace(tzinfo=timezone.utc)
            if age > timedelta(hours=24):
                logger.info(f"Last sync was {age.total_seconds() / 3600:.1f} hours ago, triggering sync")
                should_sync = True
        else:
            logger.info("No sync state found, triggering initial sync")
            should_sync = True
        
        if should_sync:
            from task_agent_service import TaskAgentService
            service = TaskAgentService()
            result = service.full_sync(db, fetch_task_details=True)
            logger.info(f"Initial sync complete: {result}")
        else:
            logger.info(f"Database has {task_count} tasks, skipping initial sync")
            
    except Exception as e:
        logger.error(f"Error checking/running initial sync: {e}")
    finally:
        db.close()


async def start_jibble_sync():
    """
    Background task that periodically syncs Jibble time tracking data.
    Runs every hour to keep time entries up to date.
    Syncs current month data only.
    """
    logger.info("Starting Jibble time tracking background sync task")
    logger.info("Sync strategy: Current month only (hourly refresh)")
    
    # Wait 2 minutes before first run to let other services initialize
    await asyncio.sleep(120)
    
    while True:
        try:
            logger.info("=" * 60)
            logger.info("Running scheduled Jibble time tracking sync (current month)")
            logger.info("=" * 60)
            
            from database_v2 import SessionLocal, init_db_v2
            from jibble_sync_service import JibbleSyncService
            
            def run_jibble_sync():
                init_db_v2()
                db = SessionLocal()
                try:
                    service = JibbleSyncService(db)
                    # Sync current month only
                    result = service.full_sync()
                    return result
                except Exception as e:
                    logger.error(f"Jibble sync error: {e}")
                    return None
                finally:
                    db.close()
            
            # Run in executor to avoid blocking
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, run_jibble_sync)
            
            if result:
                month_info = result.get('month_synced', {})
                logger.info(f"Jibble sync complete: {result.get('time_entries_synced', 0)} entries, "
                           f"{result.get('people_synced', 0)} people, "
                           f"month: {month_info.get('month', 'N/A')}")
            
            # Wait for next interval
            await asyncio.sleep(JIBBLE_SYNC_INTERVAL)
            
        except asyncio.CancelledError:
            logger.info("Jibble sync task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in Jibble sync task: {e}")
            await asyncio.sleep(300)  # Wait 5 minutes before retrying

