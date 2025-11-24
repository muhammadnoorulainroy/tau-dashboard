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
    """
    Run similarity calculation in a separate thread to avoid blocking the event loop.
    Calculates both instruction-based and action-based similarities.
    """
    try:
        from similarity_service import SimilarityService
        from action_similarity_service import ActionSimilarityService
        from database import PullRequest, TaskEmbedding, ActionEmbedding
        
        db = SessionLocal()
        
        instruction_service = SimilarityService()
        action_service = ActionSimilarityService()
        
        logger.info("="*80)
        logger.info("Starting similarity calculation (instruction + action)")
        logger.info("="*80)
        
        # STEP 1: Instruction Embeddings & Similarities
        logger.info("\n[STEP 1] Processing Instruction Embeddings...")
        
        # Get all merged PRs with instructions but no embeddings
        prs_without_instruction_embeddings = db.query(PullRequest).outerjoin(
            TaskEmbedding, PullRequest.id == TaskEmbedding.pr_id
        ).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True),
            PullRequest.instruction_text != None,
            PullRequest.instruction_text != '',
            TaskEmbedding.id == None
        ).all()
        
        if prs_without_instruction_embeddings:
            logger.info(f"Found {len(prs_without_instruction_embeddings)} PRs without instruction embeddings")
            
            instruction_embeddings_created = 0
            for pr in prs_without_instruction_embeddings:
                try:
                    embedding = instruction_service.get_or_create_embedding(pr.id, pr.instruction_text, db)
                    if embedding is not None:
                        instruction_embeddings_created += 1
                        if instruction_embeddings_created % 50 == 0:
                            logger.info(f"  Generated {instruction_embeddings_created} instruction embeddings...")
                except Exception as e:
                    logger.warning(f"  Failed to generate instruction embedding for PR #{pr.number}: {e}")
            
            logger.info(f"Generated {instruction_embeddings_created} instruction embeddings")
        else:
            logger.info("All PRs already have instruction embeddings")
        
        # Calculate instruction similarities by domain
        logger.info("\nCalculating instruction similarities by domain...")
        instruction_domains = db.query(PullRequest.domain).join(
            TaskEmbedding, PullRequest.id == TaskEmbedding.pr_id
        ).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True)
        ).distinct().all()
        
        instruction_domains_processed = 0
        for (domain,) in instruction_domains:
            if not domain:
                continue
            try:
                logger.info(f"  Processing instruction similarities for domain: {domain}")
                instruction_service.calculate_similarity_for_domain(domain, db)
                instruction_domains_processed += 1
            except Exception as e:
                logger.error(f"  Error calculating instruction similarities for {domain}: {e}")
        
        logger.info(f"Instruction similarity calculation complete for {instruction_domains_processed} domains")
        
        # STEP 2: Action Embeddings & Similarities
        logger.info("\n[STEP 2] Processing Action Embeddings...")
        
        # Get all merged PRs without action embeddings
        prs_without_action_embeddings = db.query(PullRequest).outerjoin(
            ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
        ).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True),
            ActionEmbedding.id == None
        ).all()
        
        if prs_without_action_embeddings:
            logger.info(f"Found {len(prs_without_action_embeddings)} PRs without action embeddings")
            
            action_embeddings_created = 0
            for pr in prs_without_action_embeddings:
                try:
                    embedding = action_service.get_or_create_embedding(pr, db)
                    if embedding:
                        action_embeddings_created += 1
                        if action_embeddings_created % 50 == 0:
                            logger.info(f"  Generated {action_embeddings_created} action embeddings...")
                except Exception as e:
                    logger.warning(f"  Failed to generate action embedding for PR #{pr.number}: {e}")
            
            logger.info(f"Generated {action_embeddings_created} action embeddings")
        else:
            logger.info("All PRs already have action embeddings")
        
        # Calculate action similarities by domain
        logger.info("\nCalculating action similarities by domain...")
        action_domains = db.query(PullRequest.domain).join(
            ActionEmbedding, PullRequest.id == ActionEmbedding.pr_id
        ).filter(
            PullRequest.merged == True,
            PullRequest.is_reverted.isnot(True)
        ).distinct().all()
        
        action_domains_processed = 0
        for (domain,) in action_domains:
            if not domain:
                continue
            try:
                logger.info(f"  Processing action similarities for domain: {domain}")
                action_service.calculate_similarity_for_domain(domain, db)
                action_domains_processed += 1
            except Exception as e:
                logger.error(f"  Error calculating action similarities for {domain}: {e}")
        
        logger.info(f"Action similarity calculation complete for {action_domains_processed} domains")
        
        db.close()
        
        logger.info("="*80)
        logger.info("Similarity calculation complete")
        logger.info(f"  Instruction domains: {instruction_domains_processed}")
        logger.info(f"  Action domains: {action_domains_processed}")
        logger.info("="*80)
        
        return {
            'instruction_domains': instruction_domains_processed,
            'action_domains': action_domains_processed
        }
    except Exception as e:
        logger.error(f"Error in similarity calculation thread: {str(e)}")
        return 0

def _do_revert_verification():
    """Run revert verification in a separate thread to avoid blocking the event loop."""
    try:
        github_service = GitHubService()
        db = SessionLocal()
        
        # Mark reverted PRs (folders that no longer exist on main)
        reverted_count = github_service.mark_reverted_prs(db)
        
        # Mark initial submissions (first PR per folder)
        initial_count = github_service.mark_initial_submissions(db)
        
        db.close()
        logger.info(f"Revert verification complete: {reverted_count} reverted, {initial_count} initial submissions")
        return {'reverted': reverted_count, 'initial': initial_count}
    except Exception as e:
        logger.error(f"Error in revert verification thread: {str(e)}")
        return {'reverted': 0, 'initial': 0}

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
                result = await loop.run_in_executor(executor, _do_similarity_calculation)
                
                if result and isinstance(result, dict):
                    logger.info(f"Similarity calculation complete - instruction domains: {result.get('instruction_domains', 0)}, action domains: {result.get('action_domains', 0)}")
                else:
                    logger.info("Similarity calculation completed")
                
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


async def start_revert_verification():
    """
    Background task to verify reverted PRs and mark initial submissions daily.
    
    Note: This task runs as a safety net. The full_sync and sync_last_3_days scripts
    also perform this verification, so this task provides redundancy and catches any
    PRs that were reverted between sync runs.
    """
    try:
        # Wait 2 hours before starting first verification to allow initial sync to complete
        await asyncio.sleep(7200)  # 2 hours
        
        while True:
            try:
                logger.info("Starting revert verification (background)...")
                
                # Run the blocking revert verification in a thread pool
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(executor, _do_revert_verification)
                
                if result:
                    logger.info(f"Revert verification complete - {result['reverted']} reverted, {result['initial']} initial submissions")
                else:
                    logger.info("Revert verification completed")
                
            except asyncio.CancelledError:
                # Task was cancelled, exit gracefully
                logger.info("Revert verification task cancelled, shutting down...")
                raise
            except Exception as e:
                logger.error(f"Error in revert verification: {str(e)}")
            
            # Wait for 24 hours between verifications (daily check)
            await asyncio.sleep(86400)  # 24 hours
    
    except asyncio.CancelledError:
        # Clean shutdown
        logger.info("Revert verification task stopped")
        raise

