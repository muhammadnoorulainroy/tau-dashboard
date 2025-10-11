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

from database import get_db, init_db, PullRequest, Developer, Reviewer, DomainMetrics, SyncState
from github_service import GitHubService
from sync_state import should_do_full_sync, get_last_sync_time, get_sync_description
from schemas import (
    DeveloperMetrics, ReviewerMetrics, DomainMetricsResponse, 
    PullRequestResponse, DashboardOverview, PRStateDistribution,
    PaginatedDevelopers, PaginatedReviewers
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

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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
    uvicorn.run(app, host="0.0.0.0", port=8000, reload=True)

