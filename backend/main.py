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

from database import get_db, init_db, PullRequest, Developer, Reviewer, DomainMetrics, SyncState, DeveloperHierarchy, User, Domain, Interface, Week, Pod, Review, InterfaceMetrics
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

# Track active sync tasks for graceful shutdown
active_sync_tasks = set()

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
    
    # Update allowed domains from GitHub on startup
    try:
        logger.info("=" * 60)
        logger.info("Updating allowed domains from GitHub repo...")
        logger.info("=" * 60)
        
        from config import update_allowed_domains, settings
        success = update_allowed_domains(force=True)
        
        if success:
            logger.info(f"✅ Domains updated: {len(settings.allowed_domains)} domains discovered")
            logger.info(f"   Domains: {', '.join(settings.allowed_domains)}")
        else:
            logger.warning(f"⚠️  Using fallback domain list: {len(settings.allowed_domains)} domains")
        
        logger.info("=" * 60)
    except Exception as e:
        logger.error(f"Failed to update domains from GitHub: {str(e)}")
        logger.warning("Application will continue with fallback domain list")
        # Continue anyway to allow the app to start
    
    # Start background sync task
    background_task = None
    domain_refresh_task = None
    try:
        from background_tasks import start_background_sync, start_domain_refresh
        background_task = asyncio.create_task(start_background_sync(manager))
        domain_refresh_task = asyncio.create_task(start_domain_refresh())
        logger.info("Background sync and domain refresh tasks started")
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
    
    # Cancel background periodic sync task
    if background_task:
        logger.info("Cancelling background periodic sync task...")
        background_task.cancel()
        try:
            await background_task
        except asyncio.CancelledError:
            logger.info("Background periodic sync task cancelled")
    
    # Cancel domain refresh task
    if domain_refresh_task:
        logger.info("Cancelling domain refresh task...")
        domain_refresh_task.cancel()
        try:
            await domain_refresh_task
        except asyncio.CancelledError:
            logger.info("Domain refresh task cancelled")
    
    # Cancel all active manual sync tasks
    if active_sync_tasks:
        logger.info(f"Cancelling {len(active_sync_tasks)} active sync task(s)...")
        for task in list(active_sync_tasks):
            task.cancel()
        
        # Wait briefly for cancellation (don't block forever)
        try:
            await asyncio.wait(active_sync_tasks, timeout=2.0)
        except asyncio.TimeoutError:
            logger.warning("Some sync tasks did not cancel in time")
        
        logger.info("Active sync tasks cancelled")
    
    # Shutdown thread pool without waiting for pending tasks
    logger.info("Shutting down thread pool executor...")
    sync_executor.shutdown(wait=False, cancel_futures=True)
    
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
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "TAU Dashboard API", "status": "running"}

@app.get("/api/overview", response_model=DashboardOverview)
@app.get("/api/dashboard", response_model=DashboardOverview)  # Alias for compatibility
def get_dashboard_overview(db: Session = Depends(get_db)):
    """Get overall dashboard metrics."""
    try:
        from config import settings
        
        total_prs = db.query(PullRequest).count()
        open_prs = db.query(PullRequest).filter_by(state='open').count()
        merged_prs = db.query(PullRequest).filter_by(merged=True).count()
        
        total_developers = db.query(Developer).count()
        total_reviewers = db.query(Reviewer).count()
        # Count all allowed domains from config (not just those with PRs)
        total_domains = len(settings.allowed_domains)
        
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
        
        # Ensure timezone-aware last_sync_time
        if last_sync_time and last_sync_time.tzinfo is None:
            last_sync_time = last_sync_time.replace(tzinfo=timezone.utc)
        
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
                'created_at': pr.created_at.isoformat() if pr.created_at else None
            } for pr in recent_prs],
            last_sync_time=last_sync_time
        )
    except Exception as e:
        logger.error(f"Error getting overview: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/developers", response_model=PaginatedDevelopers)
def get_developer_metrics(
    limit: int = 200,  # Increased default limit
    offset: int = 0,
    sort_by: str = "total_prs",
    search: str = None,
    domain: str = None,
    db: Session = Depends(get_db)
):
    """Get developer metrics with pagination, search, and filters. When domain is specified, shows domain-specific stats only."""
    try:
        # If domain filter is applied, calculate stats from PRs in that domain only
        if domain:
            from sqlalchemy import func, case
            
            # Build base query with domain filter
            pr_query = db.query(
                PullRequest.developer_username.label('username'),
                func.count(PullRequest.id).label('total_prs'),
                func.sum(case((PullRequest.state == 'open', 1), else_=0)).label('open_prs'),
                func.sum(case((PullRequest.merged == True, 1), else_=0)).label('merged_prs'),
                func.sum(case(((PullRequest.state == 'closed') & (PullRequest.merged == False), 1), else_=0)).label('closed_prs'),
                func.sum(PullRequest.rework_count).label('total_rework'),
                func.avg(case((PullRequest.merged == True, PullRequest.rework_count), else_=None)).label('avg_rework')
            ).filter(
                PullRequest.domain == domain
            ).group_by(PullRequest.developer_username)
            
            # Apply search filter
            if search:
                pr_query = pr_query.filter(PullRequest.developer_username.ilike(f"%{search}%"))
            
            # Get all results for sorting and pagination
            results = pr_query.all()
            
            # Sort results
            if sort_by == "total_prs":
                results = sorted(results, key=lambda x: x.total_prs or 0, reverse=True)
            elif sort_by == "open_prs":
                results = sorted(results, key=lambda x: x.open_prs or 0, reverse=True)
            elif sort_by == "merged_prs":
                results = sorted(results, key=lambda x: x.merged_prs or 0, reverse=True)
            elif sort_by == "closed_prs":
                results = sorted(results, key=lambda x: x.closed_prs or 0, reverse=True)
            elif sort_by == "total_rework":
                results = sorted(results, key=lambda x: x.total_rework or 0, reverse=True)
            
            total = len(results)
            
            # Apply pagination
            paginated_results = results[offset:offset + limit]
            
            # Build response with domain-specific stats and domain list
            from datetime import datetime, timezone
            developers_data = []
            for result in paginated_results:
                # Get domains this developer has worked on (for display)
                dev_domains_query = db.query(PullRequest.domain).filter(
                    PullRequest.developer_username == result.username
                ).distinct()
                dev_domains = [d[0] for d in dev_domains_query.all() if d[0] and d[0] in settings.allowed_domains]
                
                # Fetch email from DeveloperHierarchy table
                hierarchy = db.query(DeveloperHierarchy).filter_by(github_user=result.username).first()
                email = hierarchy.turing_email if hierarchy else None
                
                # Calculate merge rate for this domain only
                merge_rate = (result.merged_prs / result.total_prs * 100) if result.total_prs else 0
                
                developers_data.append({
                    'id': 0,  # Placeholder ID for domain-filtered view
                    'username': result.username,
                    'github_login': result.username,
                    'email': email,
                    'total_prs': result.total_prs or 0,
                    'open_prs': result.open_prs or 0,
                    'merged_prs': result.merged_prs or 0,
                    'closed_prs': result.closed_prs or 0,
                    'total_rework': result.total_rework or 0,
                    'last_updated': datetime.now(timezone.utc),
                    'metrics': {
                        'avg_rework': round(result.avg_rework or 0, 2),
                        'merge_rate': round(merge_rate, 2),
                        'domains': dev_domains
                    }
                })
            
            return PaginatedDevelopers(
                data=developers_data,
                total=total,
                limit=limit,
                offset=offset
            )
        
        # No domain filter - return global stats from Developer table with enriched metrics
        query = db.query(Developer)
        
        # Apply search filter (by username)
        if search:
            query = query.filter(Developer.username.ilike(f"%{search}%"))
        
        # Get total count after filters
        total = query.count()
        
        # Apply sorting
        if sort_by == "total_prs":
            query = query.order_by(Developer.total_prs.desc())
        elif sort_by == "open_prs":
            query = query.order_by(Developer.open_prs.desc())
        elif sort_by == "merged_prs":
            query = query.order_by(Developer.merged_prs.desc())
        elif sort_by == "closed_prs":
            query = query.order_by(Developer.closed_prs.desc())
        elif sort_by == "total_rework":
            query = query.order_by(Developer.total_rework.desc())
        
        # Apply pagination
        developers = query.offset(offset).limit(limit).all()
        
        # Enrich developer data with domains
        enriched_developers = []
        for developer in developers:
            # Fetch email from DeveloperHierarchy table
            hierarchy = db.query(DeveloperHierarchy).filter_by(github_user=developer.github_login).first()
            email = hierarchy.turing_email if hierarchy else None
            
            developer_dict = {
                'id': developer.id,
                'username': developer.username,
                'github_login': developer.github_login,
                'email': email,
                'total_prs': developer.total_prs,
                'open_prs': developer.open_prs,
                'merged_prs': developer.merged_prs,
                'closed_prs': developer.closed_prs,
                'total_rework': developer.total_rework,
                'last_updated': developer.last_updated,
                'metrics': developer.metrics or {}
            }
            
            # Add domains this developer has worked on
            dev_domains_query = db.query(PullRequest.domain).filter(
                PullRequest.developer_username == developer.username
            ).distinct()
            developer_dict['metrics']['domains'] = [d[0] for d in dev_domains_query.all() if d[0] and d[0] in settings.allowed_domains]
            
            enriched_developers.append(developer_dict)
        
        return PaginatedDevelopers(
            data=enriched_developers,
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
    limit: int = 200,  # Increased default limit
    offset: int = 0,
    sort_by: str = "total_reviews",
    search: str = None,
    domain: str = None,
    db: Session = Depends(get_db)
):
    """Get reviewer metrics with pagination, search, and filters. When domain is specified, shows domain-specific stats only."""
    try:
        # If domain filter is applied, calculate stats from Reviews in that domain only
        if domain:
            from sqlalchemy import func, case
            
            # Build base query with domain filter (join Review with PullRequest)
            review_query = db.query(
                Review.reviewer_login.label('username'),
                func.count(Review.id).label('total_reviews'),
                func.sum(case((Review.state == 'APPROVED', 1), else_=0)).label('approved_reviews'),
                func.sum(case((Review.state == 'CHANGES_REQUESTED', 1), else_=0)).label('changes_requested'),
                func.sum(case((Review.state == 'COMMENTED', 1), else_=0)).label('commented_reviews'),
                func.sum(case((Review.state == 'DISMISSED', 1), else_=0)).label('dismissed_reviews')
            ).join(
                PullRequest, Review.pull_request_id == PullRequest.id
            ).filter(
                PullRequest.domain == domain
            ).group_by(Review.reviewer_login)
            
            # Apply search filter
            if search:
                review_query = review_query.filter(Review.reviewer_login.ilike(f"%{search}%"))
            
            # Get all results for sorting and pagination
            results = review_query.all()
            
            # Sort results
            if sort_by == "total_reviews":
                results = sorted(results, key=lambda x: x.total_reviews or 0, reverse=True)
            elif sort_by == "approved_reviews":
                results = sorted(results, key=lambda x: x.approved_reviews or 0, reverse=True)
            elif sort_by == "changes_requested":
                results = sorted(results, key=lambda x: x.changes_requested or 0, reverse=True)
            
            total = len(results)
            
            # Apply pagination
            paginated_results = results[offset:offset + limit]
            
            # Build response with domain-specific stats and domain list
            from datetime import datetime, timezone
            reviewers_data = []
            for result in paginated_results:
                # Get domains this reviewer has worked on (for display)
                rev_domains_query = db.query(PullRequest.domain).join(
                    Review, Review.pull_request_id == PullRequest.id
                ).filter(
                    Review.reviewer_login == result.username
                ).distinct()
                rev_domains = [d[0] for d in rev_domains_query.all() if d[0] and d[0] in settings.allowed_domains]
                
                # Fetch email and role from DeveloperHierarchy table
                hierarchy = db.query(DeveloperHierarchy).filter_by(github_user=result.username).first()
                email = hierarchy.turing_email if hierarchy else None
                role = hierarchy.role if hierarchy else None
                
                # Calculate approval rate for this domain only
                approval_rate = (result.approved_reviews / result.total_reviews * 100) if result.total_reviews else 0
                
                # Get recent reviews in this domain
                recent_reviews = db.query(Review).join(
                    PullRequest, Review.pull_request_id == PullRequest.id
                ).filter(
                    Review.reviewer_login == result.username,
                    PullRequest.domain == domain
                ).order_by(Review.submitted_at.desc()).limit(5).all()
                
                recent_reviews_list = [
                    {
                        'pr_title': db.query(PullRequest).filter_by(id=review.pull_request_id).first().title if db.query(PullRequest).filter_by(id=review.pull_request_id).first() else 'N/A',
                        'state': review.state,
                        'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None
                    }
                    for review in recent_reviews
                ]
                
                reviewers_data.append({
                    'id': 0,  # Placeholder ID for domain-filtered view
                    'username': result.username,
                    'email': email,
                    'role': role,
                    'total_reviews': result.total_reviews or 0,
                    'approved_reviews': result.approved_reviews or 0,
                    'changes_requested': result.changes_requested or 0,
                    'commented_reviews': result.commented_reviews or 0,
                    'dismissed_reviews': result.dismissed_reviews or 0,
                    'last_updated': datetime.now(timezone.utc),
                    'metrics': {
                        'approval_rate': round(approval_rate, 2),
                        'domains': rev_domains,
                        'recent_reviews': recent_reviews_list
                    }
                })
            
            return PaginatedReviewers(
                data=reviewers_data,
                total=total,
                limit=limit,
                offset=offset
            )
        
        # No domain filter - return global stats from Reviewer table with enriched metrics
        query = db.query(Reviewer)
        
        # Apply search filter (by username)
        if search:
            query = query.filter(Reviewer.username.ilike(f"%{search}%"))
        
        # Get total count after filters
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
        
        # Enrich reviewer data with domains and recent reviews
        enriched_reviewers = []
        for reviewer in reviewers:
            # Fetch email and role from DeveloperHierarchy table
            hierarchy = db.query(DeveloperHierarchy).filter_by(github_user=reviewer.username).first()
            email = hierarchy.turing_email if hierarchy else None
            role = hierarchy.role if hierarchy else None
            
            reviewer_dict = {
                'id': reviewer.id,
                'username': reviewer.username,
                'email': email,
                'role': role,
                'total_reviews': reviewer.total_reviews,
                'approved_reviews': reviewer.approved_reviews,
                'changes_requested': reviewer.changes_requested,
                'commented_reviews': reviewer.commented_reviews,
                'dismissed_reviews': reviewer.dismissed_reviews,
                'last_updated': reviewer.last_updated,
                'metrics': reviewer.metrics or {}
            }
            
            # Add domains this reviewer has worked on
            rev_domains_query = db.query(PullRequest.domain).join(
                Review, Review.pull_request_id == PullRequest.id
            ).filter(
                Review.reviewer_login == reviewer.username
            ).distinct()
            reviewer_dict['metrics']['domains'] = [d[0] for d in rev_domains_query.all() if d[0] and d[0] in settings.allowed_domains]
            
            # Add recent reviews
            recent_reviews = db.query(Review).join(
                PullRequest, Review.pull_request_id == PullRequest.id
            ).filter(
                Review.reviewer_login == reviewer.username
            ).order_by(Review.submitted_at.desc()).limit(5).all()
            
            reviewer_dict['metrics']['recent_reviews'] = [
                {
                    'pr_title': db.query(PullRequest).filter_by(id=review.pull_request_id).first().title if db.query(PullRequest).filter_by(id=review.pull_request_id).first() else 'N/A',
                    'state': review.state,
                    'submitted_at': review.submitted_at.isoformat() if review.submitted_at else None
                }
                for review in recent_reviews
            ]
            
            enriched_reviewers.append(reviewer_dict)
        
        return PaginatedReviewers(
            data=enriched_reviewers,
            total=total,
            limit=limit,
            offset=offset
        )
    except Exception as e:
        logger.error(f"Error getting reviewer metrics: {str(e)}")
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
    """Get metrics for allowed domains only, sorted by GitHub creation date (newest first)."""
    from database import Domain
    try:
        # Get domains with GitHub creation dates for sorting
        domain_order = db.query(Domain).filter(
            Domain.domain_name.in_(settings.allowed_domains),
            Domain.is_active == True
        ).order_by(Domain.github_created_at.desc().nullslast()).all()
        
        # Create ordering map
        domain_order_map = {d.domain_name: idx for idx, d in enumerate(domain_order)}
        
        # Get domain metrics
        domains = db.query(DomainMetrics).filter(
            DomainMetrics.domain.in_(settings.allowed_domains)
        ).all()
        
        # Sort by GitHub creation date using the order map
        domains.sort(key=lambda x: domain_order_map.get(x.domain, 999))
        
        return [DomainMetricsResponse.from_orm(dom) for dom in domains]
    except Exception as e:
        logger.error(f"Error getting domain metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/domains/list")
def get_domains_list(db: Session = Depends(get_db)):
    """Get list of all allowed domains with IDs (includes domains without PRs)."""
    from database import Domain
    try:
        # Get all domains from DB that are in allowed list
        db_domains = db.query(Domain).filter(
            Domain.domain_name.in_(settings.allowed_domains),
            Domain.is_active == True
        ).order_by(Domain.github_created_at.desc().nullslast(), Domain.domain_name).all()
        
        # Create a map of existing domains
        db_domain_map = {d.domain_name: d for d in db_domains}
        
        # Build result list - include ALL allowed domains (even if not in DB yet)
        result = []
        for domain_name in settings.allowed_domains:
            if domain_name in db_domain_map:
                domain = db_domain_map[domain_name]
                result.append({
                    'id': domain.id,
                    'name': domain.domain_name
                })
            else:
                # Domain exists in config but not in DB yet (no PRs)
                # Create a temporary entry (will be created properly on next domain sync)
                result.append({
                    'id': 0,  # Placeholder ID
                    'name': domain_name
                })
        
        return {'domains': result}
    except Exception as e:
        logger.error(f"Error getting domains list: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/domains/config/current")
def get_current_domains_config():
    """Get current allowed domains configuration."""
    from config import settings
    import time
    
    last_refresh_time = None
    if settings.last_domain_refresh:
        last_refresh_time = datetime.fromtimestamp(settings.last_domain_refresh, tz=timezone.utc).isoformat()
    
    return {
        'allowed_domains': sorted(settings.allowed_domains),
        'count': len(settings.allowed_domains),
        'dynamic_discovery_enabled': settings.enable_dynamic_domains,
        'last_refresh': last_refresh_time,
        'source': 'github_dynamic' if settings.enable_dynamic_domains else 'hardcoded_fallback'
    }

@app.post("/api/domains/config/refresh")
def refresh_domains_config():
    """Manually trigger domain refresh from GitHub."""
    from config import update_allowed_domains, settings
    
    try:
        logger.info("Manual domain refresh triggered via API")
        success = update_allowed_domains(force=True)
        
        if success:
            return {
                'status': 'success',
                'message': 'Domains refreshed successfully',
                'allowed_domains': sorted(settings.allowed_domains),
                'count': len(settings.allowed_domains)
            }
        else:
            return {
                'status': 'error',
                'message': 'Failed to refresh domains from GitHub',
                'allowed_domains': sorted(settings.allowed_domains),
                'count': len(settings.allowed_domains)
            }
    except Exception as e:
        logger.error(f"Error refreshing domains via API: {str(e)}")
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
            task = asyncio.current_task()
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
            except asyncio.CancelledError:
                logger.info("Sync task cancelled during shutdown")
                raise
            except Exception as e:
                logger.error(f"❌ Error in background sync: {str(e)}")
                await manager.broadcast({
                    'type': 'sync_error',
                    'data': {'error': str(e)}
                })
            finally:
                # Remove task from active set
                if task in active_sync_tasks:
                    active_sync_tasks.discard(task)
        
        # Start sync in background (don't await)
        task = asyncio.create_task(run_sync_and_notify())
        active_sync_tasks.add(task)
        
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

@app.get("/api/interfaces")
def get_interface_metrics(
    db: Session = Depends(get_db)
):
    """Get interface metrics with complexity breakdown and weekly stats (interfaces 1-5 only)."""
    try:
        # Filter to show only interfaces 1-5
        interfaces = db.query(InterfaceMetrics).filter(
            InterfaceMetrics.interface_num >= 1,
            InterfaceMetrics.interface_num <= 5
        ).order_by(InterfaceMetrics.interface_num).all()
        
        result = []
        for interface in interfaces:
            # Format the interface data with all metrics
            interface_data = {
                'interface_num': interface.interface_num,
                'total_tasks': interface.total_tasks,
                'statuses': {
                    'discarded': interface.discarded,
                    'expert_approved': interface.expert_approved,
                    'expert_review_pending': interface.expert_review_pending,
                    'good_task': interface.good_task,
                    'merged': interface.merged,
                    'pending_review': interface.pending_review,
                    'pod_lead_approved': interface.pod_lead_approved,
                    'ready_to_merge': interface.ready_to_merge,
                    'resubmitted': interface.resubmitted
                },
                'rework': interface.rework,
                'complexity_breakdown': {
                    'merged': {
                        'expert': interface.merged_expert_count,
                        'hard': interface.merged_hard_count,
                        'medium': interface.merged_medium_count,
                        'total': interface.merged
                    },
                    'all_statuses': {  # All non-merged PRs
                        'expert': interface.all_expert_count,
                        'hard': interface.all_hard_count,
                        'medium': interface.all_medium_count,
                        'total': interface.total_tasks - interface.merged
                    }
                },
                'percentages': interface.detailed_metrics.get('complexity_percentages', {}) if interface.detailed_metrics else {},
                'weekly_stats': interface.weekly_stats,
                'trainers': interface.detailed_metrics.get('trainers', {}) if interface.detailed_metrics else {},
                'domains': interface.detailed_metrics.get('domains', {}) if interface.detailed_metrics else {},
                'last_updated': interface.last_updated
            }
            result.append(interface_data)
        
        return {
            'interfaces': result,
            'total_interfaces': len(result)
        }
    except Exception as e:
        logger.error(f"Error getting interface metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

# NOTE: Specific routes must come BEFORE parameterized routes to avoid conflicts

@app.get("/api/interfaces/filtered")
def get_filtered_interface_metrics(
    week_id: int = None,
    domain_id: int = None,
    trainer_id: int = None,
    status: str = None,
    db: Session = Depends(get_db)
):
    """Get filtered interface metrics by week, domain, trainer, and status."""
    from database import Domain
    try:
        # Build query
        query = db.query(PullRequest)
        
        # Apply filters
        if week_id:
            query = query.filter(PullRequest.week_id == week_id)
        if domain_id:
            query = query.filter(PullRequest.domain_id == domain_id)
        if trainer_id:
            query = query.filter(PullRequest.trainer_id == trainer_id)
        if status:
            if status == 'merged':
                query = query.filter(PullRequest.merged == True)
            elif status == 'open':
                query = query.filter(PullRequest.state == 'open')
        
        # Get all matching PRs
        prs = query.all()
        
        # Track overall status counts
        status_counts = {
            'merged': 0,
            'open': 0,
            'closed': 0,
            'expert_approved': 0,
            'pending_review': 0,
            'discarded': 0,
            'other': 0
        }
        
        # Group by interface
        interface_stats = {}
        for pr in prs:
            if not pr.interface_id:
                continue
            
            interface_num = pr.interface_num
            if interface_num not in range(1, 6):  # Only interfaces 1-5
                continue
            
            if interface_num not in interface_stats:
                interface_stats[interface_num] = {
                    'interface_num': interface_num,
                    'total_tasks': 0,
                    'merged': 0,
                    'open': 0,
                    'rework': 0,
                    'complexity': {
                        'merged': {'expert': 0, 'hard': 0, 'medium': 0},
                        'all': {'expert': 0, 'hard': 0, 'medium': 0}
                    }
                }
            
            stats = interface_stats[interface_num]
            stats['total_tasks'] += 1
            
            # Track status
            if pr.merged:
                stats['merged'] += 1
                status_counts['merged'] += 1
                if pr.complexity == 'expert':
                    stats['complexity']['merged']['expert'] += 1
                elif pr.complexity == 'hard':
                    stats['complexity']['merged']['hard'] += 1
                elif pr.complexity == 'medium':
                    stats['complexity']['merged']['medium'] += 1
            elif pr.state == 'open':
                stats['open'] += 1
                status_counts['open'] += 1
            elif pr.state == 'closed':
                status_counts['closed'] += 1
            
            # Check labels for more specific status
            if pr.labels:
                labels_lower = [l.lower() for l in pr.labels]
                if 'expert approved' in labels_lower:
                    status_counts['expert_approved'] += 1
                elif 'pending review' in labels_lower:
                    status_counts['pending_review'] += 1
                elif 'discarded' in labels_lower:
                    status_counts['discarded'] += 1
            
            if pr.rework_count and pr.rework_count > 0:
                stats['rework'] += pr.rework_count
            
            # All statuses complexity
            if pr.complexity == 'expert':
                stats['complexity']['all']['expert'] += 1
            elif pr.complexity == 'hard':
                stats['complexity']['all']['hard'] += 1
            elif pr.complexity == 'medium':
                stats['complexity']['all']['medium'] += 1
        
        # Convert to list and calculate percentages
        interfaces = []
        for interface_num in sorted(interface_stats.keys()):
            stats = interface_stats[interface_num]
            
            # Calculate merged percentages
            merged_total = stats['complexity']['merged']['expert'] + stats['complexity']['merged']['hard'] + stats['complexity']['merged']['medium']
            merged_pct = {}
            if merged_total > 0:
                merged_pct = {
                    'expert': round((stats['complexity']['merged']['expert'] / merged_total) * 100, 2),
                    'hard': round((stats['complexity']['merged']['hard'] / merged_total) * 100, 2),
                    'medium': round((stats['complexity']['merged']['medium'] / merged_total) * 100, 2)
                }
            
            # Calculate all statuses percentages
            all_total = stats['complexity']['all']['expert'] + stats['complexity']['all']['hard'] + stats['complexity']['all']['medium']
            all_pct = {}
            if all_total > 0:
                all_pct = {
                    'expert': round((stats['complexity']['all']['expert'] / all_total) * 100, 2),
                    'hard': round((stats['complexity']['all']['hard'] / all_total) * 100, 2),
                    'medium': round((stats['complexity']['all']['medium'] / all_total) * 100, 2)
                }
            
            interfaces.append({
                'interface_num': interface_num,
                'total_tasks': stats['total_tasks'],
                'merged': stats['merged'],
                'open': stats['open'],
                'rework': stats['rework'],
                'complexity_breakdown': {
                    'merged': {
                        'expert': stats['complexity']['merged']['expert'],
                        'hard': stats['complexity']['merged']['hard'],
                        'medium': stats['complexity']['merged']['medium'],
                        'total': merged_total,
                        'percentages': merged_pct
                    },
                    'all_statuses': {
                        'expert': stats['complexity']['all']['expert'],
                        'hard': stats['complexity']['all']['hard'],
                        'medium': stats['complexity']['all']['medium'],
                        'total': all_total,
                        'percentages': all_pct
                    }
                }
            })
        
        # Calculate summary
        total_tasks = sum(i['total_tasks'] for i in interfaces)
        total_merged = sum(i['merged'] for i in interfaces)
        total_open = sum(i['open'] for i in interfaces)
        total_rework = sum(i['rework'] for i in interfaces)
        
        summary_merged_complexity = {
            'expert': sum(i['complexity_breakdown']['merged']['expert'] for i in interfaces),
            'hard': sum(i['complexity_breakdown']['merged']['hard'] for i in interfaces),
            'medium': sum(i['complexity_breakdown']['merged']['medium'] for i in interfaces)
        }
        summary_all_complexity = {
            'expert': sum(i['complexity_breakdown']['all_statuses']['expert'] for i in interfaces),
            'hard': sum(i['complexity_breakdown']['all_statuses']['hard'] for i in interfaces),
            'medium': sum(i['complexity_breakdown']['all_statuses']['medium'] for i in interfaces)
        }
        
        return {
            'interfaces': interfaces,
            'summary': {
                'total_tasks': total_tasks,
                'total_merged': total_merged,
                'total_open': total_open,
                'total_rework': total_rework,
                'statuses': status_counts,
                'complexity_breakdown': {
                    'merged': summary_merged_complexity,
                    'all_statuses': summary_all_complexity
                }
            },
            'filters': {
                'week_id': week_id,
                'domain_id': domain_id,
                'trainer_id': trainer_id,
                'status': status
            }
        }
    except Exception as e:
        logger.error(f"Error getting filtered interface metrics: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/interfaces/{interface_num}")
def get_interface_details(
    interface_num: int,
    db: Session = Depends(get_db)
):
    """Get detailed metrics for a specific interface."""
    try:
        interface = db.query(InterfaceMetrics).filter_by(interface_num=interface_num).first()
        
        if not interface:
            raise HTTPException(status_code=404, detail=f"Interface {interface_num} not found")
        
        # Get all PRs for this interface
        prs = db.query(PullRequest).filter_by(interface_num=interface_num).all()
        
        # Group PRs by status
        pr_list = []
        for pr in prs:
            pr_status = 'other'
            if pr.merged:
                pr_status = 'merged'
            elif pr.labels:
                labels_lower = [l.lower() for l in pr.labels]
                if 'discarded' in labels_lower:
                    pr_status = 'discarded'
                elif 'ready to merge' in labels_lower:
                    pr_status = 'ready_to_merge'
                elif 'pod lead approved' in labels_lower:
                    pr_status = 'pod_lead_approved'
                elif 'expert approved' in labels_lower:
                    pr_status = 'expert_approved'
                elif 'good task' in labels_lower:
                    pr_status = 'good_task'
                elif 'expert review pending' in labels_lower:
                    pr_status = 'expert_review_pending'
                elif 'pending review' in labels_lower:
                    pr_status = 'pending_review'
                elif 'resubmitted' in labels_lower:
                    pr_status = 'resubmitted'
            
            pr_list.append({
                'number': pr.number,
                'title': pr.title,
                'trainer': pr.trainer_name,
                'domain': pr.domain,
                'complexity': pr.complexity,
                'status': pr_status,
                'merged': pr.merged,
                'created_at': pr.created_at,
                'rework_count': pr.rework_count,
                'labels': pr.labels
            })
        
        return {
            'interface_num': interface.interface_num,
            'total_tasks': interface.total_tasks,
            'statuses': {
                'discarded': interface.discarded,
                'expert_approved': interface.expert_approved,
                'expert_review_pending': interface.expert_review_pending,
                'good_task': interface.good_task,
                'merged': interface.merged,
                'pending_review': interface.pending_review,
                'pod_lead_approved': interface.pod_lead_approved,
                'ready_to_merge': interface.ready_to_merge,
                'resubmitted': interface.resubmitted
            },
            'rework': interface.rework,
            'complexity_breakdown': {
                'merged': {
                    'expert': interface.merged_expert_count,
                    'hard': interface.merged_hard_count,
                    'medium': interface.merged_medium_count,
                    'total': interface.merged,
                    'percentages': interface.detailed_metrics.get('complexity_percentages', {}).get('merged', {}) if interface.detailed_metrics else {}
                },
                'all_statuses': {
                    'expert': interface.all_expert_count,
                    'hard': interface.all_hard_count,
                    'medium': interface.all_medium_count,
                    'total': interface.total_tasks - interface.merged,
                    'percentages': interface.detailed_metrics.get('complexity_percentages', {}).get('all_statuses', {}) if interface.detailed_metrics else {}
                }
            },
            'weekly_stats': interface.weekly_stats,
            'pull_requests': pr_list,
            'trainers': interface.detailed_metrics.get('trainers', {}) if interface.detailed_metrics else {},
            'domains': interface.detailed_metrics.get('domains', {}) if interface.detailed_metrics else {},
            'last_updated': interface.last_updated
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting interface details: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/weeks")
def get_weeks(db: Session = Depends(get_db)):
    """Get all available weeks."""
    from database import Week
    try:
        weeks = db.query(Week).order_by(Week.week_num.desc()).all()
        return {
            'weeks': [
                {
                    'id': week.id,
                    'week_name': week.week_name,
                    'week_num': week.week_num
                }
                for week in weeks
            ]
        }
    except Exception as e:
        logger.error(f"Error getting weeks: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/trainers")
def get_trainers(db: Session = Depends(get_db)):
    """Get list of all trainers with their Turing emails from Google Sheets."""
    try:
        # Join User with DeveloperHierarchy to get Turing emails
        trainers_query = db.query(
            User.id,
            User.github_username,
            DeveloperHierarchy.turing_email
        ).outerjoin(
            DeveloperHierarchy,
            User.github_username == DeveloperHierarchy.github_user
        ).filter(
            User.role == 'trainer'
        ).order_by(User.github_username).all()
        
        return {
            'trainers': [
                {
                    'id': trainer.id,
                    'username': trainer.github_username,
                    'email': trainer.turing_email  # Real Turing email from Google Sheets
                }
                for trainer in trainers_query
            ]
        }
    except Exception as e:
        logger.error(f"Error getting trainers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/pr-status-breakdown")
def get_pr_status_breakdown(
    week_id: int = None,
    domain_id: int = None,
    db: Session = Depends(get_db)
):
    """Get PR status breakdown by week and domain with complexity distribution."""
    try:
        # Build query
        query = db.query(PullRequest)
        
        if week_id:
            query = query.filter(PullRequest.week_id == week_id)
        if domain_id:
            query = query.filter(PullRequest.domain_id == domain_id)
        
        # Get all PRs
        prs = query.all()
        
        # Status mapping based on labels
        status_map = {
            'discarded': 'Discarded',
            'expert approved': 'Expert Approved',
            'expert review pending': 'Expert Review Pending',
            'good task': 'Good Task',
            'pending review': 'Pending Review',
            'pod lead approved': 'Pod Lead Approved',
            'ready to merge': 'Ready To Merge',
            'resubmitted': 'Resubmitted',
            'rework': 'Rework',
            'merged': 'Merged'
        }
        
        # Initialize status breakdown
        status_breakdown = {}
        for status in status_map.values():
            status_breakdown[status] = {
                'count': 0,
                'complexity': {
                    'expert': 0,
                    'hard': 0,
                    'medium': 0
                }
            }
        
        # Process each PR
        total_prs = len(prs)
        for pr in prs:
            status = None
            
            # Determine status from labels or merged state
            if pr.merged:
                status = 'Merged'
            elif pr.labels:
                labels_lower = [l.lower() for l in pr.labels]
                for label, status_name in status_map.items():
                    if label in labels_lower:
                        status = status_name
                        break
            
            # If no status found, skip
            if not status or status not in status_breakdown:
                continue
            
            # Count the PR
            status_breakdown[status]['count'] += 1
            
            # Count complexity
            if pr.complexity in ['expert', 'hard', 'medium']:
                status_breakdown[status]['complexity'][pr.complexity] += 1
        
        # Calculate percentages and format response
        result = []
        for status, data in status_breakdown.items():
            count = data['count']
            if count == 0:
                continue  # Skip statuses with no PRs
            
            # Calculate overall percentage
            percent = (count / total_prs * 100) if total_prs > 0 else 0
            
            # Calculate complexity percentages
            complexity_data = {}
            for level in ['expert', 'hard', 'medium']:
                level_count = data['complexity'][level]
                level_percent = (level_count / count * 100) if count > 0 else 0
                complexity_data[level] = {
                    'count': level_count,
                    'percent': round(level_percent, 2)
                }
            
            result.append({
                'status': status,
                'count': count,
                'percent': round(percent, 2),
                'complexity': complexity_data
            })
        
        # Sort by count descending
        result.sort(key=lambda x: x['count'], reverse=True)
        
        return {
            'total_prs': total_prs,
            'breakdown': result
        }
    except Exception as e:
        logger.error(f"Error getting PR status breakdown: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/interfaces/summary/all")
def get_all_interfaces_summary(
    db: Session = Depends(get_db)
):
    """Get summary statistics across all interfaces (interfaces 1-5 only)."""
    try:
        # Filter to show only interfaces 1-5
        interfaces = db.query(InterfaceMetrics).filter(
            InterfaceMetrics.interface_num >= 1,
            InterfaceMetrics.interface_num <= 5
        ).all()
        
        total_tasks = sum(i.total_tasks for i in interfaces)
        total_merged = sum(i.merged for i in interfaces)
        total_rework = sum(i.rework for i in interfaces)
        
        # Aggregate status counts
        statuses = {
            'discarded': sum(i.discarded for i in interfaces),
            'expert_approved': sum(i.expert_approved for i in interfaces),
            'expert_review_pending': sum(i.expert_review_pending for i in interfaces),
            'good_task': sum(i.good_task for i in interfaces),
            'merged': total_merged,
            'pending_review': sum(i.pending_review for i in interfaces),
            'pod_lead_approved': sum(i.pod_lead_approved for i in interfaces),
            'ready_to_merge': sum(i.ready_to_merge for i in interfaces),
            'resubmitted': sum(i.resubmitted for i in interfaces)
        }
        
        # Aggregate complexity counts
        complexity_merged = {
            'expert': sum(i.merged_expert_count for i in interfaces),
            'hard': sum(i.merged_hard_count for i in interfaces),
            'medium': sum(i.merged_medium_count for i in interfaces)
        }
        
        complexity_all_statuses = {
            'expert': sum(i.all_expert_count for i in interfaces),
            'hard': sum(i.all_hard_count for i in interfaces),
            'medium': sum(i.all_medium_count for i in interfaces)
        }
        
        # Calculate percentages
        merged_total = sum(complexity_merged.values())
        all_statuses_total = sum(complexity_all_statuses.values())
        
        return {
            'total_interfaces': len(interfaces),
            'total_tasks': total_tasks,
            'total_merged': total_merged,
            'total_rework': total_rework,
            'statuses': statuses,
            'complexity_breakdown': {
                'merged': {
                    **complexity_merged,
                    'total': merged_total,
                    'percentages': {
                        'expert': round((complexity_merged['expert'] / merged_total * 100) if merged_total > 0 else 0, 2),
                        'hard': round((complexity_merged['hard'] / merged_total * 100) if merged_total > 0 else 0, 2),
                        'medium': round((complexity_merged['medium'] / merged_total * 100) if merged_total > 0 else 0, 2)
                    }
                },
                'all_statuses': {
                    **complexity_all_statuses,
                    'total': all_statuses_total,
                    'percentages': {
                        'expert': round((complexity_all_statuses['expert'] / all_statuses_total * 100) if all_statuses_total > 0 else 0, 2),
                        'hard': round((complexity_all_statuses['hard'] / all_statuses_total * 100) if all_statuses_total > 0 else 0, 2),
                        'medium': round((complexity_all_statuses['medium'] / all_statuses_total * 100) if all_statuses_total > 0 else 0, 2)
                    }
                }
            }
        }
    except Exception as e:
        logger.error(f"Error getting interfaces summary: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    from config import settings
    uvicorn.run(app, host=settings.backend_host, port=settings.backend_port, reload=True)

