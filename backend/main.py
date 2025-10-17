from fastapi import FastAPI, Depends, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
from typing import List, Dict, Optional
from datetime import datetime, timedelta, timezone
import asyncio
import json
import logging
from contextlib import asynccontextmanager
from concurrent.futures import ThreadPoolExecutor

from database import get_db, init_db, PullRequest, Developer, Reviewer, DomainMetrics, SyncState, DeveloperHierarchy
from github_service import GitHubService
from google_sheets_service import GoogleSheetsService
from sync_state import should_do_full_sync, get_last_sync_time, get_sync_description
from db_migrations import run_migrations
from schemas import (
    DeveloperMetrics, ReviewerMetrics, DomainMetricsResponse, 
    PullRequestResponse, DashboardOverview, PRStateDistribution,
    PaginatedDevelopers, PaginatedReviewers, AggregationMetrics
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Thread pool for running blocking sync operations
sync_executor = ThreadPoolExecutor(max_workers=3)

# WebSocket connection manager
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        self.active_connections.append(websocket)
    
    def disconnect(self, websocket: WebSocket):
        self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        for connection in self.active_connections:
            try:
                await connection.send_json(message)
            except:
                pass

manager = ConnectionManager()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    try:
        logger.info("Initializing database...")
        init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize database: {str(e)}")
        # Continue anyway to allow the app to start
    
    # Run database migrations automatically
    try:
        logger.info("Running database migrations...")
        run_migrations()
    except Exception as e:
        logger.error(f"Failed to run migrations: {str(e)}")
        # Continue anyway to allow the app to start
    
    # Sync Google Sheets on startup
    try:
        logger.info("=" * 60)
        logger.info("Syncing developer hierarchy from Google Sheets...")
        logger.info("=" * 60)
        
        from database import SessionLocal
        db = SessionLocal()
        try:
            sheets_service = GoogleSheetsService()
            
            # Clear existing hierarchy data for fresh sync
            db.query(DeveloperHierarchy).delete()
            db.commit()
            logger.info("Cleared existing developer hierarchy data")
            
            # Sync fresh data from Google Sheets
            inserted, updated, errors = sheets_service.sync_to_database(db)
            total_records = db.query(DeveloperHierarchy).count()
            
            logger.info("=" * 60)
            logger.info(f"✅ Google Sheets sync complete:")
            logger.info(f"   - Inserted: {inserted}")
            logger.info(f"   - Updated: {updated}")
            logger.info(f"   - Errors: {errors}")
            logger.info(f"   - Total developers: {total_records}")
            logger.info("=" * 60)
        finally:
            db.close()
            
    except Exception as e:
        logger.error(f"Failed to sync Google Sheets on startup: {str(e)}")
        logger.warning("Application will continue, but hierarchy data may be outdated")
        # Continue anyway to allow the app to start
    
    # Start background sync task
    background_task = None
    try:
        from background_tasks import start_background_sync
        background_task = asyncio.create_task(start_background_sync(manager))
        logger.info("Background sync task started")
    except ImportError as e:
        logger.warning(f"Background sync module not available: {str(e)}")
    except Exception as e:
        logger.error(f"Failed to start background sync: {str(e)}")
    
    # Do initial sync (disabled for faster startup, can be triggered manually)
    # try:
    #     github_service = GitHubService()
    #     from database import SessionLocal
    #     db = SessionLocal()
    #     logger.info("Performing initial GitHub sync...")
    #     github_service.sync_all_prs(db, since_days=30)
    #     db.close()
    # except Exception as e:
    #     logger.error(f"Error during initial sync: {str(e)}")
    
    yield
    
    # Shutdown
    logger.info("Shutting down...")
    if background_task:
        logger.info("Cancelling background task...")
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background task cancelled successfully")
    logger.info("Shutdown complete")

app = FastAPI(
    title="TAU Dashboard API",
    description="Dashboard for tracking PR metrics",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware - import settings at the top of this file
from config import settings

app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.frontend_url, "http://localhost:5173"],  # Allow configured frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "TAU Dashboard API", "status": "running"}

@app.get("/api/overview", response_model=DashboardOverview)
def get_dashboard_overview(db: Session = Depends(get_db)):
    """Get overall dashboard metrics."""
    try:
        total_prs = db.query(PullRequest).count()
        open_prs = db.query(PullRequest).filter_by(state='open').count()
        merged_prs = db.query(PullRequest).filter_by(merged=True).count()
        
        total_developers = db.query(Developer).count()
        total_reviewers = db.query(Reviewer).count()
        total_domains = db.query(DomainMetrics).count()
        
        # Calculate average rework
        avg_rework = db.query(PullRequest).with_entities(
            func.avg(PullRequest.rework_count)
        ).scalar() or 0
        
        # Get recent activity
        recent_prs = db.query(PullRequest).order_by(
            PullRequest.created_at.desc()
        ).limit(10).all()
        
        # Get last sync time
        sync_state = db.query(SyncState).first()
        last_sync_time = sync_state.last_sync_time if sync_state else None
        
        return DashboardOverview(
            total_prs=total_prs,
            open_prs=open_prs,
            merged_prs=merged_prs,
            total_developers=total_developers,
            total_reviewers=total_reviewers,
            total_domains=total_domains,
            average_rework=round(avg_rework, 2),
            recent_activity=[{
                'title': pr.title,
                'state': pr.state,
                'developer': pr.developer_username,
                'created_at': pr.created_at
            } for pr in recent_prs],
            last_sync_time=last_sync_time
        )
    except Exception as e:
        logger.error(f"Error getting overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/developers", response_model=PaginatedDevelopers)
def get_developer_metrics(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "total_prs",
    db: Session = Depends(get_db)
):
    """Get developer metrics with pagination."""
    try:
        query = db.query(Developer)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if sort_by == "total_prs":
            query = query.order_by(Developer.total_prs.desc())
        elif sort_by == "open_prs":
            query = query.order_by(Developer.open_prs.desc())
        elif sort_by == "merged_prs":
            query = query.order_by(Developer.merged_prs.desc())
        elif sort_by == "total_rework":
            query = query.order_by(Developer.total_rework.desc())
        
        # Apply pagination
        developers = query.offset(offset).limit(limit).all()
        
        return PaginatedDevelopers(
            data=[DeveloperMetrics.from_orm(dev) for dev in developers],
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error getting developer metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/developers/{username}", response_model=DeveloperMetrics)
def get_developer_details(username: str, db: Session = Depends(get_db)):
    """Get detailed metrics for a specific developer."""
    developer = db.query(Developer).filter_by(username=username).first()
    if not developer:
        raise HTTPException(status_code=404, detail="Developer not found")
    
    # Get recent PRs
    recent_prs = db.query(PullRequest).filter_by(
        developer_username=username
    ).order_by(PullRequest.created_at.desc()).limit(10).all()
    
    developer.metrics['recent_prs'] = [{
        'title': pr.title,
        'state': pr.state,
        'labels': pr.labels,
        'rework_count': pr.rework_count,
        'created_at': pr.created_at
    } for pr in recent_prs]
    
    return DeveloperMetrics.from_orm(developer)

@app.get("/api/reviewers", response_model=PaginatedReviewers)
def get_reviewer_metrics(
    limit: int = 50,
    offset: int = 0,
    sort_by: str = "total_reviews",
    db: Session = Depends(get_db)
):
    """Get reviewer metrics with pagination."""
    try:
        query = db.query(Reviewer)
        
        # Get total count
        total = query.count()
        
        # Apply sorting
        if sort_by == "total_reviews":
            query = query.order_by(Reviewer.total_reviews.desc())
        elif sort_by == "approved_reviews":
            query = query.order_by(Reviewer.approved_reviews.desc())
        elif sort_by == "changes_requested":
            query = query.order_by(Reviewer.changes_requested.desc())
        
        # Apply pagination
        reviewers = query.offset(offset).limit(limit).all()
        
        return PaginatedReviewers(
            data=[ReviewerMetrics.from_orm(rev) for rev in reviewers],
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error getting reviewer metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/domains/list")
def get_domains_list(db: Session = Depends(get_db)):
    """Get list of all unique domains (recognized domains + Others)"""
    try:
        # Get all unique domains from database
        db_domains = db.query(PullRequest.domain).filter(
            PullRequest.domain.isnot(None)
        ).distinct().all()
        
        # Normalize domains
        normalized = set()
        for (domain,) in db_domains:
            if domain:
                normalized.add(normalize_domain(domain))
        
        # Return sorted list: recognized domains alphabetically, then Others
        result = sorted([d for d in normalized if d in settings.recognized_domains])
        if 'Others' in normalized:
            result.append('Others')
        
        logger.info(f"Returning {len(result)} domains: {result}")
        return result
    except Exception as e:
        logger.error(f"Error getting domains list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/statuses/list")
def get_statuses_list(db: Session = Depends(get_db)):
    """Get list of all unique developer statuses from hierarchy table"""
    try:
        # Get all unique statuses from developer_hierarchy
        statuses = db.query(DeveloperHierarchy.status).filter(
            DeveloperHierarchy.status.isnot(None)
        ).distinct().all()
        
        # Extract and sort
        result = sorted([status for (status,) in statuses if status])
        
        logger.info(f"Returning {len(result)} statuses: {result}")
        return result
    except Exception as e:
        logger.error(f"Error getting statuses list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/domains", response_model=List[DomainMetricsResponse])
def get_domain_metrics(db: Session = Depends(get_db)):
    """Get metrics for all domains."""
    try:
        domains = db.query(DomainMetrics).order_by(DomainMetrics.total_tasks.desc()).all()
        return [DomainMetricsResponse.from_orm(dom) for dom in domains]
    except Exception as e:
        logger.error(f"Error getting domain metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/domains/{domain}", response_model=DomainMetricsResponse)
def get_domain_details(domain: str, db: Session = Depends(get_db)):
    """Get detailed metrics for a specific domain."""
    domain_metrics = db.query(DomainMetrics).filter_by(domain=domain).first()
    if not domain_metrics:
        raise HTTPException(status_code=404, detail="Domain not found")
    
    # Get recent PRs for this domain
    recent_prs = db.query(PullRequest).filter_by(
        domain=domain
    ).order_by(PullRequest.created_at.desc()).limit(20).all()
    
    domain_metrics.detailed_metrics['recent_prs'] = [{
        'title': pr.title,
        'state': pr.state,
        'labels': pr.labels,
        'developer': pr.developer_username,
        'created_at': pr.created_at
    } for pr in recent_prs]
    
    return DomainMetricsResponse.from_orm(domain_metrics)

@app.get("/api/pr-states", response_model=PRStateDistribution)
def get_pr_state_distribution(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get PR state distribution by labels."""
    try:
        query = db.query(PullRequest)
        if domain:
            query = query.filter_by(domain=domain)
        
        prs = query.all()
        
        distribution = {
            'expert_review_pending': 0,
            'calibrator_review_pending': 0,
            'expert_approved': 0,
            'ready_to_merge': 0,
            'merged': 0,
            'other': 0
        }
        
        for pr in prs:
            if pr.merged:
                distribution['merged'] += 1
            elif 'ready to merge' in [l.lower() for l in pr.labels]:
                distribution['ready_to_merge'] += 1
            elif 'expert approved' in [l.lower() for l in pr.labels]:
                distribution['expert_approved'] += 1
            elif 'calibrator review pending' in [l.lower() for l in pr.labels]:
                distribution['calibrator_review_pending'] += 1
            elif 'expert review pending' in [l.lower() for l in pr.labels]:
                distribution['expert_review_pending'] += 1
            else:
                distribution['other'] += 1
        
        return PRStateDistribution(
            domain=domain,
            distribution=distribution,
            total=len(prs)
        )
    except Exception as e:
        logger.error(f"Error getting PR state distribution: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/prs", response_model=List[PullRequestResponse])
def get_pull_requests(
    state: Optional[str] = None,
    domain: Optional[str] = None,
    developer: Optional[str] = None,
    limit: int = 50,
    offset: int = 0,
    db: Session = Depends(get_db)
):
    """Get pull requests with filters."""
    try:
        query = db.query(PullRequest)
        
        if state:
            if state == 'merged':
                query = query.filter_by(merged=True)
            else:
                query = query.filter_by(state=state)
        
        if domain:
            query = query.filter_by(domain=domain)
        
        if developer:
            query = query.filter_by(developer_username=developer)
        
        prs = query.order_by(PullRequest.created_at.desc()).offset(offset).limit(limit).all()
        
        return [PullRequestResponse.from_orm(pr) for pr in prs]
    except Exception as e:
        logger.error(f"Error getting pull requests: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class SyncRequest(BaseModel):
    since_days: int = 60
    force_full: bool = False  # Allow forcing a full sync

def _perform_sync(db_url: str, since_days: int, force_full: bool):
    """
    Perform sync in a separate thread to avoid blocking the event loop.
    This function runs in a thread pool executor.
    """
    from database import SessionLocal
    
    db = SessionLocal()
    try:
        github_service = GitHubService()
        
        # Determine if we should do full or incremental sync
        do_full_sync = force_full or should_do_full_sync(db, since_days)
        sync_desc = get_sync_description(db, since_days)
        
        logger.info(f"Starting {sync_desc} (non-blocking)")
        
        if do_full_sync:
            # Full sync - fetch last N days
            count = github_service.sync_all_prs(db, since_days=since_days)
            sync_type = "full"
        else:
            # Incremental sync - only fetch updates since last sync
            last_sync = get_last_sync_time(db)
            count = github_service.get_incremental_updates(db, last_sync)
            sync_type = "incremental"
        
        logger.info(f"Sync completed successfully - {sync_type} sync processed {count} PRs")
        
        return {
            'count': count,
            'sync_type': sync_type,
            'description': sync_desc
        }
    except Exception as e:
        logger.error(f"Error in sync thread: {str(e)}")
        raise
    finally:
        db.close()

@app.post("/api/sync")
async def trigger_sync(
    request: SyncRequest = SyncRequest(),
    db: Session = Depends(get_db)
):
    """
    Manually trigger GitHub sync (fire-and-forget, truly non-blocking).
    
    Smart sync logic:
    - First sync: Fetches last 60 days (full sync)
    - Subsequent syncs: Only fetches updates since last sync (incremental)
    - If last sync was >7 days ago: Does a full sync again
    - force_full=True: Forces a full sync regardless
    
    Returns immediately. WebSocket will notify when complete.
    """
    try:
        from config import settings
        
        # Get sync info before starting
        sync_desc = get_sync_description(db, request.since_days)
        do_full_sync = request.force_full or should_do_full_sync(db, request.since_days)
        sync_type = "full" if do_full_sync else "incremental"
        
        # Background task to run sync and notify when done
        async def run_sync_and_notify():
            try:
                loop = asyncio.get_event_loop()
                result = await loop.run_in_executor(
                    sync_executor,
                    _perform_sync,
                    settings.database_url,
                    request.since_days,
                    request.force_full
                )
                
                # Notify clients via WebSocket when done
                await manager.broadcast({
                    'type': 'sync_complete',
                    'data': {
                        'synced_count': result['count'],
                        'sync_type': result['sync_type'],
                        'description': result['description']
                    }
                })
                logger.info(f"✅ Sync complete, notified clients: {result['count']} PRs")
            except Exception as e:
                logger.error(f"❌ Error in background sync: {str(e)}")
                await manager.broadcast({
                    'type': 'sync_error',
                    'data': {'error': str(e)}
                })
        
        # Start sync in background (don't await)
        asyncio.create_task(run_sync_and_notify())
        
        # Return immediately
        logger.info(f"🚀 Sync started in background: {sync_desc}")
        return {
            "status": "started", 
            "message": "Sync running in background",
            "sync_type": sync_type,
            "description": sync_desc
        }
    except Exception as e:
        logger.error(f"Error starting sync: {str(e)}")
        import traceback
        logger.error(f"Traceback: {traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=str(e))

def normalize_domain(domain: str) -> str:
    """Normalize domain name - return recognized domain or 'Others'
    
    Compares domain (case-insensitive) against recognized domains list.
    Returns the recognized domain name if found, otherwise returns 'Others'.
    """
    if not domain:
        return 'Others'
    
    domain_lower = domain.lower().strip()
    
    # Check if domain matches any recognized domain (case-insensitive)
    for recognized in settings.recognized_domains:
        if domain_lower == recognized.lower():
            return recognized
    
    return 'Others'


def calculate_metrics_from_prs(prs: List[PullRequest]) -> dict:
    """Calculate aggregation metrics from PR list"""
    total_tasks = len(prs)
    completed_tasks = sum(1 for pr in prs if pr.merged)
    
    # Rework % = (sum of all rework_count / total tasks) * 100
    total_rework = sum(pr.rework_count for pr in prs)
    rework_percentage = (total_rework / total_tasks * 100) if total_tasks > 0 else 0.0
    
    # Rejected = closed but not merged OR has 'rejected' label
    rejected_count = sum(1 for pr in prs 
                        if (pr.state == 'closed' and not pr.merged) or 
                        any(l.lower() == 'rejected' for l in pr.labels))
    
    # Delivery ready = has relevant labels
    delivery_ready_tasks = sum(1 for pr in prs 
                               if any(l.lower() in ['ready to merge', 'delivery ready', 'expert approved'] 
                                     for l in pr.labels))
    
    return {
        'total_tasks': total_tasks,
        'completed_tasks': completed_tasks,
        'rework_percentage': round(rework_percentage, 2),
        'rejected_count': rejected_count,
        'delivery_ready_tasks': delivery_ready_tasks
    }




@app.get("/api/aggregation/domains", response_model=List[AggregationMetrics])
def get_domain_aggregation(db: Session = Depends(get_db)):
    """Domain-wise aggregation from PullRequest table with normalized domains"""
    try:
        # Get all PRs
        all_prs = db.query(PullRequest).filter(PullRequest.domain.isnot(None)).all()
        
        # Group PRs by normalized domain
        domain_prs = {}
        for pr in all_prs:
            normalized = normalize_domain(pr.domain)
            if normalized not in domain_prs:
                domain_prs[normalized] = []
            domain_prs[normalized].append(pr)
        
        # Calculate metrics for each domain
        results = []
        for domain, prs in domain_prs.items():
            metrics = calculate_metrics_from_prs(prs)
            results.append(AggregationMetrics(name=domain, **metrics))
        
        # Sort: recognized domains alphabetically, then Others at the end
        recognized_results = sorted(
            [r for r in results if r.name in settings.recognized_domains],
            key=lambda x: x.name
        )
        others_results = [r for r in results if r.name == 'Others']
        
        return recognized_results + others_results
    except Exception as e:
        logger.error(f"Error in domain aggregation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/aggregation/trainers", response_model=List[AggregationMetrics])
def get_trainer_aggregation(
    domain: Optional[str] = None, 
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Trainer-wise aggregation - shows all developers from PRs with their emails
    
    Args:
        domain: Optional normalized domain filter (e.g., 'enterprise_wiki', 'Others')
        status: Optional developer status filter (e.g., 'Active', 'Onboarding')
    """
    try:
        from sqlalchemy import func
        
        # Get developers to include based on status filter
        if status:
            developers_query = db.query(DeveloperHierarchy.github_user).filter(
                DeveloperHierarchy.status == status,
                DeveloperHierarchy.github_user.isnot(None)
            )
            allowed_github_users = set([user.lower() for (user,) in developers_query.all()])
        else:
            allowed_github_users = None
        
        # Get all PRs
        all_prs = db.query(PullRequest).filter(
            PullRequest.author_login.isnot(None)
        ).all()
        
        # Filter by status if provided
        if allowed_github_users is not None:
            all_prs = [pr for pr in all_prs if pr.author_login.lower() in allowed_github_users]
        
        # Filter by normalized domain if provided
        if domain:
            filtered_prs = []
            for pr in all_prs:
                if normalize_domain(pr.domain) == domain:
                    filtered_prs.append(pr)
            all_prs = filtered_prs
        
        # Group PRs by author_login
        author_prs = {}
        for pr in all_prs:
            if pr.author_login:
                if pr.author_login not in author_prs:
                    author_prs[pr.author_login] = []
                author_prs[pr.author_login].append(pr)
        
        # Calculate metrics for each developer
        results = []
        for author_login, prs in author_prs.items():
            metrics = calculate_metrics_from_prs(prs)
            
            # Get email from the first PR (they should all have the same email)
            author_email = None
            for pr in prs:
                if pr.author_email:
                    author_email = pr.author_email
                    break
            
            results.append(AggregationMetrics(
                name=author_login,
                email=author_email,
                **metrics
            ))
        
        return sorted(results, key=lambda x: x.total_tasks, reverse=True)
    except Exception as e:
        logger.error(f"Error in trainer aggregation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/google-sheets/sync")
def sync_google_sheets(db: Session = Depends(get_db)):
    """
    Sync hierarchy data from Google Sheets to DeveloperHierarchy table
    Clears existing data and performs fresh sync to ensure data is up-to-date
    """
    try:
        logger.info("Manual Google Sheets sync triggered")
        sheets_service = GoogleSheetsService()
        
        # Clear existing hierarchy data for fresh sync
        db.query(DeveloperHierarchy).delete()
        db.commit()
        logger.info("Cleared existing developer hierarchy data")
        
        # Sync fresh data from Google Sheets
        inserted, updated, errors = sheets_service.sync_to_database(db)
        
        # Get total count
        total_records = db.query(DeveloperHierarchy).count()
        
        logger.info(f"Manual sync complete: {inserted} inserted, {updated} updated, {errors} errors, {total_records} total")
        
        return {
            "status": "success",
            "inserted": inserted,
            "updated": updated,
            "errors": errors,
            "total_records": total_records,
            "message": f"✅ Hierarchy refreshed: {total_records} developers synced from Google Sheets ({inserted} new, {errors} skipped)."
        }
    except FileNotFoundError as e:
        logger.error(f"Service account file not found: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error syncing Google Sheets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/developer-hierarchy")
def get_developer_hierarchy(db: Session = Depends(get_db)):
    """Get all developer hierarchy records"""
    try:
        records = db.query(DeveloperHierarchy).all()
        return [
            {
                "id": r.id,
                "github_user": r.github_user,
                "turing_email": r.turing_email,
                "role": r.role,
                "status": r.status,
                "pod_lead_email": r.pod_lead_email,
                "calibrator_email": r.calibrator_email,
                "last_synced": r.last_synced
            }
            for r in records
        ]
    except Exception as e:
        logger.error(f"Error getting developer hierarchy: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/aggregation/pod-leads", response_model=List[AggregationMetrics])
def get_pod_lead_aggregation(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    POD Lead-wise aggregation - counts ALL PRs, groups by POD Lead
    
    Args:
        domain: Optional normalized domain filter (e.g., 'enterprise_wiki', 'Others')
        status: Optional developer status filter (e.g., 'Active', 'Onboarding')
    """
    try:
        from sqlalchemy import func
        
        # Track which PR authors have been assigned to a POD Lead
        assigned_authors = set()
        
        # Get all unique pod leads from hierarchy
        pod_leads = db.query(DeveloperHierarchy.pod_lead_email).filter(
            DeveloperHierarchy.pod_lead_email.isnot(None)
        ).distinct().all()
        
        results = []
        for (pod_lead_email,) in pod_leads:
            if not pod_lead_email:
                continue
            
            # Build query for ALL developers under this POD lead (not just trainers)
            devs_query = db.query(DeveloperHierarchy).filter(
                func.lower(DeveloperHierarchy.pod_lead_email) == pod_lead_email.lower()
            )
            
            # Apply status filter if provided
            if status:
                devs_query = devs_query.filter(DeveloperHierarchy.status == status)
            
            devs = devs_query.all()
            
            if not devs:
                continue
            
            # Get PRs for these developers (case-insensitive match)
            github_users = [d.github_user.lower() for d in devs if d.github_user]
            
            if not github_users:
                continue
            
            # Track assigned authors
            assigned_authors.update(github_users)
            
            # Query PRs with case-insensitive author_login match
            all_prs = db.query(PullRequest).filter(
                func.lower(PullRequest.author_login).in_(github_users)
            ).all()
            
            # Apply domain filter if provided
            if domain:
                filtered_prs = [pr for pr in all_prs if normalize_domain(pr.domain) == domain]
                all_prs = filtered_prs
            
            if all_prs:
                metrics = calculate_metrics_from_prs(all_prs)
                
                # Use email prefix as display name
                display_name = pod_lead_email.split('@')[0] if '@' in pod_lead_email else pod_lead_email
                
                # Count developers under this POD Lead
                dev_count = len(devs)
                
                results.append(AggregationMetrics(
                    name=display_name,
                    email=pod_lead_email,
                    trainer_count=dev_count,
                    **metrics
                ))
        
        # Add "Not Assigned" for PRs from developers without a POD Lead
        # Get all PR authors
        all_pr_authors = db.query(PullRequest.author_login).distinct().all()
        unassigned_authors = [author.lower() for (author,) in all_pr_authors if author.lower() not in assigned_authors]
        
        if unassigned_authors:
            # Query PRs for unassigned authors
            unassigned_prs = db.query(PullRequest).filter(
                func.lower(PullRequest.author_login).in_(unassigned_authors)
            ).all()
            
            # Apply domain filter if provided
            if domain:
                filtered_prs = [pr for pr in unassigned_prs if normalize_domain(pr.domain) == domain]
                unassigned_prs = filtered_prs
            
            if unassigned_prs:
                metrics = calculate_metrics_from_prs(unassigned_prs)
                
                results.append(AggregationMetrics(
                    name="Not Assigned",
                    email=None,
                    trainer_count=len(unassigned_authors),
                    **metrics
                ))
        
        return sorted(results, key=lambda x: x.total_tasks, reverse=True)
    except Exception as e:
        logger.error(f"Error in pod lead aggregation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/aggregation/calibrators", response_model=List[AggregationMetrics])
def get_calibrator_aggregation(
    domain: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Calibrator-wise aggregation - counts ALL PRs, groups by Calibrator
    
    Args:
        domain: Optional normalized domain filter (e.g., 'enterprise_wiki', 'Others')
        status: Optional developer status filter (e.g., 'Active', 'Onboarding')
    """
    try:
        from sqlalchemy import func
        
        # Track which PR authors have been assigned to a Calibrator
        assigned_authors = set()
        
        # Get all unique calibrators from hierarchy
        calibrators = db.query(DeveloperHierarchy.calibrator_email).filter(
            DeveloperHierarchy.calibrator_email.isnot(None)
        ).distinct().all()
        
        results = []
        for (calibrator_email,) in calibrators:
            if not calibrator_email:
                continue
            
            # Count POD Leads under this calibrator
            pod_leads_query = db.query(DeveloperHierarchy).filter(
                func.lower(DeveloperHierarchy.calibrator_email) == calibrator_email.lower(),
                func.lower(DeveloperHierarchy.role) == 'pod lead'
            )
            if status:
                pod_leads_query = pod_leads_query.filter(DeveloperHierarchy.status == status)
            pod_leads_under_calibrator = pod_leads_query.all()
            pod_lead_count = len(pod_leads_under_calibrator)
            
            # Build query for ALL developers under this calibrator (not just trainers)
            devs_query = db.query(DeveloperHierarchy).filter(
                func.lower(DeveloperHierarchy.calibrator_email) == calibrator_email.lower()
            )
            
            # Apply status filter if provided
            if status:
                devs_query = devs_query.filter(DeveloperHierarchy.status == status)
            
            devs = devs_query.all()
            
            if not devs:
                continue
            
            # Get PRs for these developers (case-insensitive match)
            github_users = [d.github_user.lower() for d in devs if d.github_user]
            
            if not github_users:
                continue
            
            # Track assigned authors
            assigned_authors.update(github_users)
            
            # Query PRs with case-insensitive author_login match
            all_prs = db.query(PullRequest).filter(
                func.lower(PullRequest.author_login).in_(github_users)
            ).all()
            
            # Apply domain filter if provided
            if domain:
                filtered_prs = [pr for pr in all_prs if normalize_domain(pr.domain) == domain]
                all_prs = filtered_prs
            
            if all_prs:
                metrics = calculate_metrics_from_prs(all_prs)
                
                # Use email prefix as display name
                display_name = calibrator_email.split('@')[0] if '@' in calibrator_email else calibrator_email
                
                # Count developers under this Calibrator (excluding POD Leads for trainer count)
                all_dev_count = len(devs)
                trainer_count = all_dev_count - pod_lead_count
                
                results.append(AggregationMetrics(
                    name=display_name,
                    email=calibrator_email,
                    trainer_count=trainer_count,
                    pod_lead_count=pod_lead_count,
                    **metrics
                ))
        
        # Add "Not Assigned" for PRs from developers without a Calibrator
        # Get all PR authors
        all_pr_authors = db.query(PullRequest.author_login).distinct().all()
        unassigned_authors = [author.lower() for (author,) in all_pr_authors if author.lower() not in assigned_authors]
        
        if unassigned_authors:
            # Query PRs for unassigned authors
            unassigned_prs = db.query(PullRequest).filter(
                func.lower(PullRequest.author_login).in_(unassigned_authors)
            ).all()
            
            # Apply domain filter if provided
            if domain:
                filtered_prs = [pr for pr in unassigned_prs if normalize_domain(pr.domain) == domain]
                unassigned_prs = filtered_prs
            
            if unassigned_prs:
                metrics = calculate_metrics_from_prs(unassigned_prs)
                
                results.append(AggregationMetrics(
                    name="Not Assigned",
                    email=None,
                    trainer_count=len(unassigned_authors),
                    pod_lead_count=0,
                    **metrics
                ))
        
        return sorted(results, key=lambda x: x.total_tasks, reverse=True)
    except Exception as e:
        logger.error(f"Error in calibrator aggregation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time updates."""
    await manager.connect(websocket)
    try:
        while True:
            # Keep connection alive
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        manager.disconnect(websocket)

@app.get("/api/stats/timeline")
def get_timeline_stats(
    days: int = 30,
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get timeline statistics for charts."""
    try:
        end_date = datetime.now(timezone.utc)
        start_date = end_date - timedelta(days=days)
        
        query = db.query(PullRequest).filter(
            PullRequest.created_at >= start_date
        )
        
        if domain:
            query = query.filter_by(domain=domain)
        
        prs = query.all()
        
        # Group by day
        timeline = {}
        for pr in prs:
            date_key = pr.created_at.strftime('%Y-%m-%d')
            if date_key not in timeline:
                timeline[date_key] = {
                    'created': 0,
                    'merged': 0,
                    'rework': 0
                }
            
            timeline[date_key]['created'] += 1
            if pr.merged:
                timeline[date_key]['merged'] += 1
            timeline[date_key]['rework'] += pr.rework_count
        
        return {
            'dates': sorted(timeline.keys()),
            'data': timeline
        }
    except Exception as e:
        logger.error(f"Error getting timeline stats: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from config import settings
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port, reload=True)

