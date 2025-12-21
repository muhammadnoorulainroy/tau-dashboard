"""
API v2 Router for Task Agent data
Replaces GitHub-based endpoints with Task Agent API-backed endpoints
"""
from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func, desc, distinct
from typing import Optional, List
from datetime import datetime, timezone
import logging

from database_v2 import (
    get_db, Task, TaskAgentUser, Batch, Environment, 
    SyncStateV2, TaskEmbedding, TaskSimilarity, ActionEmbedding, ActionSimilarity,
    JibblePerson, JibbleTimeEntry, JibbleEmailMapping,
    TASK_STATUSES, is_in_review
)
from schemas_v2 import (
    TaskResponse, PaginatedTasks, EnvironmentResponse,
    TrainerMetrics, PaginatedTrainers, BatchResponse,
    DashboardOverviewV2, StatusBreakdown, SyncStatusResponse,
    TaskSimilarityResponse, ActionSimilarityResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v2", tags=["v2"])


# =============================================================================
# DASHBOARD OVERVIEW
# =============================================================================

@router.get("/overview", response_model=DashboardOverviewV2)
def get_overview(db: Session = Depends(get_db)):
    """Get dashboard overview with task statistics"""
    
    # Get total counts
    total_tasks = db.query(Task).count()
    total_trainers = db.query(distinct(Task.trainer_email)).filter(
        Task.trainer_email.isnot(None)
    ).count()
    total_domains = db.query(Environment).filter(Environment.is_active == True).count()
    total_batches = db.query(Batch).count()
    
    # Status counts
    status_counts = {}
    for status in TASK_STATUSES:
        status_counts[status] = db.query(Task).filter(Task.status == status).count()
    
    # Calculate in_review (all review stages)
    in_review_count = sum(
        status_counts.get(s, 0) for s in [
            'pending_review', 'in_expert_review', 'pending_calibrator_review',
            'in_calibrator_review', 'in_pod_lead_review'
        ]
    )
    
    # Average rework
    avg_rework = db.query(func.avg(Task.rework_count)).scalar() or 0
    
    # Approval rate (approved / (approved + rework))
    approved = status_counts.get('approved', 0)
    rework = status_counts.get('rework', 0)
    approval_rate = approved / (approved + rework) if (approved + rework) > 0 else 0
    
    # Sync info
    sync_state = db.query(SyncStateV2).first()
    last_sync_time = sync_state.last_sync_time if sync_state else None
    
    return DashboardOverviewV2(
        total_tasks=total_tasks,
        total_trainers=total_trainers,
        total_domains=total_domains,
        total_batches=total_batches,
        draft_count=status_counts.get('draft', 0),
        pending_review_count=status_counts.get('pending_review', 0),
        in_expert_review_count=status_counts.get('in_expert_review', 0),
        pending_calibrator_review_count=status_counts.get('pending_calibrator_review', 0),
        in_calibrator_review_count=status_counts.get('in_calibrator_review', 0),
        in_pod_lead_review_count=status_counts.get('in_pod_lead_review', 0),
        rework_count=status_counts.get('rework', 0),
        approved_count=status_counts.get('approved', 0),
        in_review_count=in_review_count,
        average_rework=float(avg_rework),
        approval_rate=approval_rate,
        last_sync_time=last_sync_time
    )


# =============================================================================
# TASKS
# =============================================================================

@router.get("/tasks", response_model=PaginatedTasks)
def get_tasks(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    domain: Optional[str] = None,
    status: Optional[str] = None,
    difficulty: Optional[str] = None,
    trainer_email: Optional[str] = None,
    batch_id: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("created_at", regex="^(created_at|updated_at|status|difficulty|rework_count)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get paginated list of tasks with filters"""
    
    query = db.query(Task)
    
    # Apply filters
    if domain:
        query = query.filter(Task.domain == domain)
    if status:
        if status == "in_review":
            # Special handling: all review stages
            query = query.filter(Task.status.in_([
                'pending_review', 'in_expert_review', 'pending_calibrator_review',
                'in_calibrator_review', 'in_pod_lead_review'
            ]))
        else:
            query = query.filter(Task.status == status)
    if difficulty:
        query = query.filter(Task.difficulty == difficulty)
    if trainer_email:
        query = query.filter(Task.trainer_email == trainer_email)
    if batch_id:
        query = query.filter(Task.batch_id == batch_id)
    if search:
        query = query.filter(
            Task.instruction_text.ilike(f"%{search}%") | 
            Task.task_agent_id.ilike(f"%{search}%") |
            Task.trainer_name.ilike(f"%{search}%")
        )
    
    # Get total
    total = query.count()
    
    # Apply sorting
    sort_column = getattr(Task, sort_by)
    if sort_order == "desc":
        query = query.order_by(desc(sort_column))
    else:
        query = query.order_by(sort_column)
    
    # Apply pagination
    offset = (page - 1) * per_page
    tasks = query.offset(offset).limit(per_page).all()
    
    total_pages = (total + per_page - 1) // per_page
    
    return PaginatedTasks(
        data=[TaskResponse.model_validate(t) for t in tasks],
        total=total,
        page=page,
        per_page=per_page,
        total_pages=total_pages
    )


@router.get("/tasks/{task_id}", response_model=TaskResponse)
def get_task(task_id: int, db: Session = Depends(get_db)):
    """Get a single task by ID"""
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


@router.get("/tasks/by-agent-id/{task_agent_id}", response_model=TaskResponse)
def get_task_by_agent_id(task_agent_id: str, db: Session = Depends(get_db)):
    """Get a single task by Task Agent ID"""
    task = db.query(Task).filter(Task.task_agent_id == task_agent_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return TaskResponse.model_validate(task)


# =============================================================================
# ENVIRONMENTS / DOMAINS
# =============================================================================

@router.get("/environments", response_model=List[EnvironmentResponse])
def get_environments(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Get all environments/domains"""
    query = db.query(Environment)
    if active_only:
        query = query.filter(Environment.is_active == True)
    
    environments = query.order_by(Environment.name).all()
    return [EnvironmentResponse.model_validate(e) for e in environments]


@router.get("/environments/{name}", response_model=EnvironmentResponse)
def get_environment(name: str, db: Session = Depends(get_db)):
    """Get a single environment by name"""
    env = db.query(Environment).filter(Environment.name == name).first()
    if not env:
        raise HTTPException(status_code=404, detail="Environment not found")
    return EnvironmentResponse.model_validate(env)


@router.get("/domains", response_model=List[EnvironmentResponse])
def get_domains(
    active_only: bool = True,
    db: Session = Depends(get_db)
):
    """Alias for environments - Get all domains"""
    return get_environments(active_only=active_only, db=db)


# =============================================================================
# TRAINERS
# =============================================================================

@router.get("/trainers", response_model=PaginatedTrainers)
def get_trainers(
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
    domain: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = Query("total_tasks", regex="^(total_tasks|approved_count|rework_count|approval_rate|in_review_count|trainer_name)$"),
    sort_order: str = Query("desc", regex="^(asc|desc)$"),
    db: Session = Depends(get_db)
):
    """Get trainers with their metrics"""
    
    # Base query to get unique trainers
    query = db.query(Task.trainer_email, Task.trainer_name).filter(
        Task.trainer_email.isnot(None)
    )
    
    if domain:
        query = query.filter(Task.domain == domain)
    
    trainer_query = query.distinct()
    
    if search:
        trainer_query = trainer_query.filter(
            Task.trainer_email.ilike(f"%{search}%") |
            Task.trainer_name.ilike(f"%{search}%")
        )
    
    # Get all trainers
    trainers_raw = trainer_query.all()
    
    # Calculate metrics for each trainer
    trainers = []
    for trainer_email, trainer_name in trainers_raw:
        task_query = db.query(Task).filter(Task.trainer_email == trainer_email)
        if domain:
            task_query = task_query.filter(Task.domain == domain)
        
        tasks = task_query.all()
        total = len(tasks)
        
        if total == 0:
            continue
        
        # Count by status
        status_counts = {}
        difficulty_counts = {"expert": 0, "hard": 0, "medium": 0}
        
        for task in tasks:
            status = task.status
            status_counts[status] = status_counts.get(status, 0) + 1
            if task.difficulty in difficulty_counts:
                difficulty_counts[task.difficulty] += 1
        
        approved = status_counts.get('approved', 0)
        rework = status_counts.get('rework', 0)
        
        in_review = sum(
            status_counts.get(s, 0) for s in [
                'pending_review', 'in_expert_review', 'pending_calibrator_review',
                'in_calibrator_review', 'in_pod_lead_review'
            ]
        )
        
        trainers.append(TrainerMetrics(
            trainer_email=trainer_email,
            trainer_name=trainer_name,
            total_tasks=total,
            draft_count=status_counts.get('draft', 0),
            pending_review_count=status_counts.get('pending_review', 0),
            in_expert_review_count=status_counts.get('in_expert_review', 0),
            pending_calibrator_review_count=status_counts.get('pending_calibrator_review', 0),
            in_calibrator_review_count=status_counts.get('in_calibrator_review', 0),
            in_pod_lead_review_count=status_counts.get('in_pod_lead_review', 0),
            rework_count=rework,
            approved_count=approved,
            approval_rate=approved / total if total > 0 else 0,
            rework_rate=rework / total if total > 0 else 0,
            in_review_count=in_review,
            expert_count=difficulty_counts['expert'],
            hard_count=difficulty_counts['hard'],
            medium_count=difficulty_counts['medium']
        ))
    
    # Sort
    reverse = sort_order == "desc"
    if sort_by == "total_tasks":
        trainers.sort(key=lambda t: t.total_tasks, reverse=reverse)
    elif sort_by == "approved_count":
        trainers.sort(key=lambda t: t.approved_count, reverse=reverse)
    elif sort_by == "rework_count":
        trainers.sort(key=lambda t: t.rework_count, reverse=reverse)
    elif sort_by == "approval_rate":
        trainers.sort(key=lambda t: t.approval_rate, reverse=reverse)
    elif sort_by == "in_review_count":
        trainers.sort(key=lambda t: t.in_review_count, reverse=reverse)
    elif sort_by == "trainer_name":
        trainers.sort(key=lambda t: (t.trainer_name or '').lower(), reverse=reverse)
    
    # Paginate
    total = len(trainers)
    offset = (page - 1) * per_page
    trainers = trainers[offset:offset + per_page]
    
    return PaginatedTrainers(
        data=trainers,
        total=total,
        page=page,
        per_page=per_page
    )


# =============================================================================
# BATCHES
# =============================================================================

@router.get("/batches", response_model=List[BatchResponse])
def get_batches(
    environment: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get all batches with optional filters"""
    query = db.query(Batch)
    
    if environment:
        query = query.filter(Batch.environment == environment)
    if status:
        query = query.filter(Batch.status == status)
    
    batches = query.order_by(desc(Batch.date_opened)).all()
    return [BatchResponse.model_validate(b) for b in batches]


# =============================================================================
# STATUS BREAKDOWN
# =============================================================================

@router.get("/status-breakdown", response_model=List[StatusBreakdown])
def get_status_breakdown(
    by_domain: bool = False,
    db: Session = Depends(get_db)
):
    """Get status breakdown, optionally by domain"""
    
    if by_domain:
        # Get breakdown per domain
        domains = db.query(distinct(Task.domain)).filter(Task.domain.isnot(None)).all()
        
        result = []
        for (domain,) in domains:
            tasks = db.query(Task).filter(Task.domain == domain).all()
            breakdown = {}
            for task in tasks:
                breakdown[task.status] = breakdown.get(task.status, 0) + 1
            
            result.append(StatusBreakdown(
                domain=domain,
                total=len(tasks),
                breakdown=breakdown
            ))
        
        return result
    else:
        # Overall breakdown
        tasks = db.query(Task).all()
        breakdown = {}
        for task in tasks:
            breakdown[task.status] = breakdown.get(task.status, 0) + 1
        
        return [StatusBreakdown(
            domain=None,
            total=len(tasks),
            breakdown=breakdown
        )]


# =============================================================================
# SYNC
# =============================================================================

@router.get("/sync/status", response_model=SyncStatusResponse)
def get_sync_status(db: Session = Depends(get_db)):
    """Get current sync status"""
    sync_state = db.query(SyncStateV2).first()
    
    if not sync_state:
        return SyncStatusResponse()
    
    return SyncStatusResponse(
        last_sync_time=sync_state.last_sync_time,
        last_full_sync_time=sync_state.last_full_sync_time,
        tasks_synced=sync_state.tasks_synced,
        users_synced=sync_state.users_synced,
        batches_synced=sync_state.batches_synced
    )


@router.post("/sync/trigger")
async def trigger_sync(
    background_tasks: BackgroundTasks,
    fetch_details: bool = True,
    db: Session = Depends(get_db)
):
    """Trigger a background sync from Task Agent API"""
    from task_agent_service import TaskAgentService
    
    def run_sync():
        from database_v2 import SessionLocal
        db = SessionLocal()
        try:
            service = TaskAgentService()
            service.full_sync(db, fetch_task_details=fetch_details)
        except Exception as e:
            logger.error(f"Sync failed: {e}")
        finally:
            db.close()
    
    background_tasks.add_task(run_sync)
    
    return {"message": "Sync triggered", "status": "running"}


# =============================================================================
# SIMILARITY (Updated for Task Agent)
# =============================================================================

@router.get("/similarity/tasks/{task_id}", response_model=TaskSimilarityResponse)
def get_task_similarity(
    task_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get similar tasks based on instruction text"""
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get similarities from database
    similarities = db.query(TaskSimilarity).filter(
        (TaskSimilarity.task_id_1 == task_id) | (TaskSimilarity.task_id_2 == task_id)
    ).order_by(desc(TaskSimilarity.similarity_score)).limit(limit * 2).all()
    
    similar_tasks = []
    seen_ids = {task_id}
    
    for sim in similarities:
        other_id = sim.task_id_2 if sim.task_id_1 == task_id else sim.task_id_1
        if other_id in seen_ids:
            continue
        seen_ids.add(other_id)
        
        other_task = db.query(Task).filter(Task.id == other_id).first()
        if other_task:
            similar_tasks.append({
                "task_id": other_task.id,
                "task_agent_id": other_task.task_agent_id,
                "instruction_text": other_task.instruction_text,
                "domain": other_task.domain,
                "similarity_score": sim.similarity_score
            })
        
        if len(similar_tasks) >= limit:
            break
    
    return TaskSimilarityResponse(
        task_id=task.id,
        task_agent_id=task.task_agent_id,
        instruction_text=task.instruction_text,
        domain=task.domain,
        similar_tasks=similar_tasks
    )


@router.get("/similarity/actions/{task_id}", response_model=ActionSimilarityResponse)
def get_action_similarity(
    task_id: int,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """Get similar tasks based on action/tool sequence"""
    
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    
    # Get similarities from database
    similarities = db.query(ActionSimilarity).filter(
        (ActionSimilarity.task_id_1 == task_id) | (ActionSimilarity.task_id_2 == task_id)
    ).order_by(desc(ActionSimilarity.similarity_score)).limit(limit * 2).all()
    
    similar_tasks = []
    seen_ids = {task_id}
    
    for sim in similarities:
        other_id = sim.task_id_2 if sim.task_id_1 == task_id else sim.task_id_1
        if other_id in seen_ids:
            continue
        seen_ids.add(other_id)
        
        other_task = db.query(Task).filter(Task.id == other_id).first()
        if other_task:
            similar_tasks.append({
                "task_id": other_task.id,
                "task_agent_id": other_task.task_agent_id,
                "instruction_text": other_task.instruction_text,
                "description": other_task.description,
                "tool_sequence": other_task.tool_sequence,
                "domain": other_task.domain,
                "difficulty": other_task.difficulty,
                "trainer_name": other_task.trainer_name,
                "similarity_score": sim.similarity_score
            })
        
        if len(similar_tasks) >= limit:
            break
    
    return ActionSimilarityResponse(
        task_id=task.id,
        task_agent_id=task.task_agent_id,
        tool_sequence=task.tool_sequence,
        domain=task.domain,
        similar_tasks=similar_tasks
    )


# =============================================================================
# CUSTOM SIMILARITY SEARCH
# =============================================================================

from pydantic import BaseModel

class CustomSimilaritySearchRequest(BaseModel):
    query_text: str
    domain: Optional[str] = None
    search_type: str = "instruction"  # "instruction" or "action"
    limit: int = 10
    min_similarity: float = 0.3

@router.post("/similarity/search")
def search_similar_tasks(
    request: CustomSimilaritySearchRequest,
    db: Session = Depends(get_db)
):
    """
    Search for tasks similar to custom input text.
    
    - **query_text**: The text to search for similar tasks
    - **domain**: Optional domain to filter results
    - **search_type**: "instruction" for instruction similarity, "action" for action sequence similarity
    - **limit**: Maximum number of results (default 10)
    - **min_similarity**: Minimum similarity score threshold (default 0.3)
    """
    from similarity_service_v2 import SimilarityServiceV2
    
    if not request.query_text or not request.query_text.strip():
        raise HTTPException(status_code=400, detail="Query text is required")
    
    service = SimilarityServiceV2()
    
    if request.search_type == "action":
        results = service.search_similar_by_action_sequence(
            query_text=request.query_text,
            db=db,
            domain=request.domain,
            limit=request.limit,
            min_similarity=request.min_similarity
        )
    else:
        results = service.search_similar_by_text(
            query_text=request.query_text,
            db=db,
            domain=request.domain,
            limit=request.limit,
            min_similarity=request.min_similarity
        )
    
    return {
        "query_text": request.query_text[:200] + "..." if len(request.query_text) > 200 else request.query_text,
        "search_type": request.search_type,
        "domain": request.domain,
        "total_results": len(results),
        "results": results
    }


# =============================================================================
# STATISTICS
# =============================================================================

@router.get("/stats/by-difficulty")
def get_stats_by_difficulty(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics grouped by difficulty"""
    query = db.query(Task)
    if domain:
        query = query.filter(Task.domain == domain)
    
    tasks = query.all()
    
    stats = {}
    for task in tasks:
        diff = task.difficulty or "unknown"
        if diff not in stats:
            stats[diff] = {
                "total": 0,
                "approved": 0,
                "rework": 0,
                "in_review": 0,
                "draft": 0
            }
        
        stats[diff]["total"] += 1
        if task.status == "approved":
            stats[diff]["approved"] += 1
        elif task.status == "rework":
            stats[diff]["rework"] += 1
        elif task.status == "draft":
            stats[diff]["draft"] += 1
        elif is_in_review(task.status):
            stats[diff]["in_review"] += 1
    
    return stats


@router.get("/stats/by-batch")
def get_stats_by_batch(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics grouped by batch"""
    query = db.query(Task).filter(Task.batch_id.isnot(None))
    if domain:
        query = query.filter(Task.domain == domain)
    
    tasks = query.all()
    
    stats = {}
    for task in tasks:
        batch = task.batch_name or task.batch_id
        if batch not in stats:
            stats[batch] = {
                "batch_id": task.batch_id,
                "batch_status": task.batch_status,
                "total": 0,
                "approved": 0,
                "rework": 0,
                "in_review": 0
            }
        
        stats[batch]["total"] += 1
        if task.status == "approved":
            stats[batch]["approved"] += 1
        elif task.status == "rework":
            stats[batch]["rework"] += 1
        elif is_in_review(task.status):
            stats[batch]["in_review"] += 1
    
    return stats


@router.get("/stats/timeline")
def get_timeline_stats(
    domain: Optional[str] = None,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get task creation timeline statistics"""
    from datetime import timedelta
    
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    
    query = db.query(Task).filter(Task.created_at >= cutoff)
    if domain:
        query = query.filter(Task.domain == domain)
    
    tasks = query.all()
    
    # Group by date
    timeline = {}
    for task in tasks:
        if task.created_at:
            date_str = task.created_at.strftime("%Y-%m-%d")
            if date_str not in timeline:
                timeline[date_str] = {"created": 0, "approved": 0, "rework": 0}
            timeline[date_str]["created"] += 1
            if task.status == "approved":
                timeline[date_str]["approved"] += 1
            elif task.status == "rework":
                timeline[date_str]["rework"] += 1
    
    # Sort by date
    sorted_timeline = [
        {"date": date, **counts}
        for date, counts in sorted(timeline.items())
    ]
    
    return sorted_timeline


# =============================================================================
# AGGREGATION - POD LEADS
# =============================================================================

@router.get("/aggregation/pod-leads")
def get_pod_lead_aggregation(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics aggregated by POD Lead - counts review events from task_history"""
    from sqlalchemy import or_
    
    # Build name-to-email lookup for POD leads
    users = db.query(TaskAgentUser).filter(
        TaskAgentUser.email.isnot(None),
        TaskAgentUser.name.isnot(None)
    ).all()
    name_to_email = {u.name.lower().strip(): u.email.lower() for u in users if u.name and u.email}
    email_to_name = {u.email.lower(): u.name for u in users if u.name and u.email}
    
    # Get tasks where POD lead is assigned
    query = db.query(Task).filter(
        or_(Task.pod_lead_email.isnot(None), Task.pod_lead_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_pod_lead = query.all()
    
    # Group by POD Lead - track tasks and status
    pod_leads = {}
    
    # Process tasks for total counts and current status
    for task in tasks_with_pod_lead:
        key = (task.pod_lead_email or "").lower() or task.pod_lead_name
        if not key:
            continue
            
        if key not in pod_leads:
            pod_leads[key] = {
                "pod_lead_email": task.pod_lead_email,
                "pod_lead_name": task.pod_lead_name or email_to_name.get(key, key),
                "total_tasks": 0,
                "draft_count": 0,
                "pending_review_count": 0,
                "in_expert_review_count": 0,
                "pending_calibrator_review_count": 0,
                "in_calibrator_review_count": 0,
                "in_pod_lead_review_count": 0,
                "rework_count": 0,  # From task_history events
                "approved_count": 0,  # From task_history events
                "trainers": set(),
                "domains": set()
            }
        
        pod_leads[key]["total_tasks"] += 1
        if task.trainer_email:
            pod_leads[key]["trainers"].add(task.trainer_email)
        if task.domain:
            pod_leads[key]["domains"].add(task.domain)
        
        # Current status counts
        if task.status == 'draft':
            pod_leads[key]["draft_count"] += 1
        elif task.status == 'pending_review':
            pod_leads[key]["pending_review_count"] += 1
        elif task.status == 'in_expert_review':
            pod_leads[key]["in_expert_review_count"] += 1
        elif task.status == 'pending_calibrator_review':
            pod_leads[key]["pending_calibrator_review_count"] += 1
        elif task.status == 'in_calibrator_review':
            pod_leads[key]["in_calibrator_review_count"] += 1
        elif task.status == 'in_pod_lead_review':
            pod_leads[key]["in_pod_lead_review_count"] += 1
        elif task.status == 'rework':
            pass  # Don't count in any review stage
    
    # Now count review events from task_history (ALL TIME)
    # POD Lead events: pod_lead_review_completed (approved), task_sent_to_rework_by_pod_lead (rework)
    # IMPORTANT: Also handle both_reviews_completed with two-pass logic to prevent double counting
    tasks_with_history = db.query(Task).filter(Task.task_history.isnot(None))
    if domain:
        tasks_with_history = tasks_with_history.filter(Task.domain == domain)
    tasks_with_history = tasks_with_history.all()
    
    for task in tasks_with_history:
        if not task.task_history:
            continue
        
        # Two-pass logic for both_reviews_completed handling
        # Track which POD leads have APPROVAL events on this task (not rework - those are separate actions)
        task_pod_lead_has_approval = set()  # emails that have pod_lead_review_completed
        both_reviews_events = []  # (reviewer_email, initiated_by) tuples to process in pass 2
        
        # PASS 1: Count individual POD Lead events
        for event in task.task_history:
            event_type = event.get('event', '').lower()
            initiated_by = event.get('initiated_by', '')
            
            # Get reviewer email from initiated_by name
            reviewer_email = name_to_email.get(initiated_by.lower().strip()) if initiated_by else None
            
            if not reviewer_email:
                continue
            
            key = reviewer_email.lower()
            
            # Handle individual POD Lead events
            if event_type in ['pod_lead_review_completed', 'task_sent_to_rework_by_pod_lead']:
                # Only track approvals for deduplication (rework is a separate action)
                if event_type == 'pod_lead_review_completed':
                    task_pod_lead_has_approval.add(key)
                
                # Initialize if not exists
                if key not in pod_leads:
                    pod_leads[key] = {
                        "pod_lead_email": reviewer_email,
                        "pod_lead_name": email_to_name.get(key, initiated_by or key),
                        "total_tasks": 0,
                        "draft_count": 0,
                        "pending_review_count": 0,
                        "in_expert_review_count": 0,
                        "pending_calibrator_review_count": 0,
                        "in_calibrator_review_count": 0,
                        "in_pod_lead_review_count": 0,
                        "rework_count": 0,
                        "approved_count": 0,
                        "trainers": set(),
                        "domains": set()
                    }
                
                # Count the review event
                if event_type == 'pod_lead_review_completed':
                    pod_leads[key]["approved_count"] += 1
                elif event_type == 'task_sent_to_rework_by_pod_lead':
                    pod_leads[key]["rework_count"] += 1
            
            # Collect both_reviews_completed for pass 2
            elif event_type == 'both_reviews_completed':
                both_reviews_events.append((reviewer_email, initiated_by))
        
        # PASS 2: Handle both_reviews_completed - only count if initiator is POD Lead and has no APPROVAL event
        # (Rework events don't count - a reviewer can send to rework, then later approve via both_reviews_completed)
        for reviewer_email, initiated_by in both_reviews_events:
            key = reviewer_email.lower()
            
            # Check if this person is the POD Lead for this task
            task_pod_lead = (task.pod_lead_email or "").lower()
            if key != task_pod_lead:
                continue  # Not the POD Lead, skip
            
            # Only count if no approval event exists (rework is a separate action)
            if key in task_pod_lead_has_approval:
                continue  # Already has approval event, skip
            
            # Initialize if not exists
            if key not in pod_leads:
                pod_leads[key] = {
                    "pod_lead_email": reviewer_email,
                    "pod_lead_name": email_to_name.get(key, initiated_by or key),
                    "total_tasks": 0,
                    "draft_count": 0,
                    "pending_review_count": 0,
                    "in_expert_review_count": 0,
                    "pending_calibrator_review_count": 0,
                    "in_calibrator_review_count": 0,
                    "in_pod_lead_review_count": 0,
                    "rework_count": 0,
                    "approved_count": 0,
                    "trainers": set(),
                    "domains": set()
                }
            
            # Count as POD Lead approval (both_reviews_completed = approval)
            pod_leads[key]["approved_count"] += 1
    
    # Convert to result list
    result = []
    for key, data in pod_leads.items():
        approved = data["approved_count"]
        rework = data["rework_count"]
        reviewed = approved + rework  # Total review actions
        in_review = (
            data["pending_review_count"] + data["in_expert_review_count"] +
            data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
            data["in_pod_lead_review_count"]
        )
        total = approved + rework + in_review  # Total = Approved + Rework + In Review
        
        result.append({
            "pod_lead_email": data["pod_lead_email"],
            "pod_lead_name": data["pod_lead_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,
            "draft_count": data["draft_count"],
            "pending_review_count": data["pending_review_count"],
            "in_expert_review_count": data["in_expert_review_count"],
            "pending_calibrator_review_count": data["pending_calibrator_review_count"],
            "in_calibrator_review_count": data["in_calibrator_review_count"],
            "in_pod_lead_review_count": data["in_pod_lead_review_count"],
            "rework_count": rework,
            "approved_count": approved,
            "in_review_count": (
                data["pending_review_count"] + data["in_expert_review_count"] +
                data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
                data["in_pod_lead_review_count"]
            ),
            "approval_rate": approved / reviewed if reviewed > 0 else 0,
            "rework_rate": rework / reviewed if reviewed > 0 else 0,
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })
    
    # Sort by reviewed count descending (most active reviewers first)
    result.sort(key=lambda x: x["reviewed_count"], reverse=True)
    
    return result


# =============================================================================
# AGGREGATION - CALIBRATORS (REVIEWERS)
# =============================================================================

@router.get("/aggregation/calibrators")
def get_calibrator_aggregation(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics aggregated by Calibrator - counts review events from task_history"""
    from sqlalchemy import or_
    
    # Build name-to-email lookup
    users = db.query(TaskAgentUser).filter(
        TaskAgentUser.email.isnot(None),
        TaskAgentUser.name.isnot(None)
    ).all()
    name_to_email = {u.name.lower().strip(): u.email.lower() for u in users if u.name and u.email}
    email_to_name = {u.email.lower(): u.name for u in users if u.name and u.email}
    
    # Get tasks where calibrator is assigned
    query = db.query(Task).filter(
        or_(Task.reviewer_email.isnot(None), Task.reviewer_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_calibrator = query.all()
    
    # Group by Calibrator
    calibrators = {}
    
    # Process tasks for total counts and current status
    for task in tasks_with_calibrator:
        key = (task.reviewer_email or "").lower() or task.reviewer_name
        if not key:
            continue
            
        if key not in calibrators:
            calibrators[key] = {
                "calibrator_email": task.reviewer_email,
                "calibrator_name": task.reviewer_name or email_to_name.get(key, key),
                "total_tasks": 0,
                "draft_count": 0,
                "pending_review_count": 0,
                "in_expert_review_count": 0,
                "pending_calibrator_review_count": 0,
                "in_calibrator_review_count": 0,
                "in_pod_lead_review_count": 0,
                "rework_count": 0,
                "approved_count": 0,
                "trainers": set(),
                "domains": set()
            }
        
        calibrators[key]["total_tasks"] += 1
        if task.trainer_email:
            calibrators[key]["trainers"].add(task.trainer_email)
        if task.domain:
            calibrators[key]["domains"].add(task.domain)
        
        # Current status counts
        if task.status == 'draft':
            calibrators[key]["draft_count"] += 1
        elif task.status == 'pending_review':
            calibrators[key]["pending_review_count"] += 1
        elif task.status == 'in_expert_review':
            calibrators[key]["in_expert_review_count"] += 1
        elif task.status == 'pending_calibrator_review':
            calibrators[key]["pending_calibrator_review_count"] += 1
        elif task.status == 'in_calibrator_review':
            calibrators[key]["in_calibrator_review_count"] += 1
        elif task.status == 'in_pod_lead_review':
            calibrators[key]["in_pod_lead_review_count"] += 1
        elif task.status == 'rework':
            pass  # Don't count in any review stage
    
    # Now count review events from task_history (ALL TIME)
    # Calibrator events: task_approved_by_calibrator (approved), task_sent_to_rework_by_calibrator (rework)
    tasks_with_history = db.query(Task).filter(Task.task_history.isnot(None))
    if domain:
        tasks_with_history = tasks_with_history.filter(Task.domain == domain)
    tasks_with_history = tasks_with_history.all()
    
    for task in tasks_with_history:
        if not task.task_history:
            continue
        
        for event in task.task_history:
            event_type = event.get('event', '').lower()
            initiated_by = event.get('initiated_by', '')
            
            # Only Calibrator events
            if event_type not in ['task_approved_by_calibrator', 'task_sent_to_rework_by_calibrator']:
                continue
            
            # Get reviewer email from initiated_by name or task field
            reviewer_email = name_to_email.get(initiated_by.lower().strip()) if initiated_by else None
            if not reviewer_email and task.reviewer_email:
                reviewer_email = task.reviewer_email.lower()
            
            if not reviewer_email:
                continue
            
            key = reviewer_email.lower()
            
            # Initialize if not exists
            if key not in calibrators:
                calibrators[key] = {
                    "calibrator_email": reviewer_email,
                    "calibrator_name": email_to_name.get(key, initiated_by or key),
                    "total_tasks": 0,
                    "draft_count": 0,
                    "pending_review_count": 0,
                    "in_expert_review_count": 0,
                    "pending_calibrator_review_count": 0,
                    "in_calibrator_review_count": 0,
                    "in_pod_lead_review_count": 0,
                    "rework_count": 0,
                    "approved_count": 0,
                    "trainers": set(),
                    "domains": set()
                }
            
            # Count the review event
            if event_type == 'task_approved_by_calibrator':
                calibrators[key]["approved_count"] += 1
            elif event_type == 'task_sent_to_rework_by_calibrator':
                calibrators[key]["rework_count"] += 1
    
    # Convert to result list
    result = []
    for key, data in calibrators.items():
        approved = data["approved_count"]
        rework = data["rework_count"]
        reviewed = approved + rework  # Total review actions
        in_review = (
            data["pending_review_count"] + data["in_expert_review_count"] +
            data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
            data["in_pod_lead_review_count"]
        )
        total = approved + rework + in_review  # Total = Approved + Rework + In Review
        
        result.append({
            "calibrator_email": data["calibrator_email"],
            "calibrator_name": data["calibrator_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,
            "draft_count": data["draft_count"],
            "pending_review_count": data["pending_review_count"],
            "in_expert_review_count": data["in_expert_review_count"],
            "pending_calibrator_review_count": data["pending_calibrator_review_count"],
            "in_calibrator_review_count": data["in_calibrator_review_count"],
            "in_pod_lead_review_count": data["in_pod_lead_review_count"],
            "rework_count": rework,
            "approved_count": approved,
            "in_review_count": (
                data["pending_review_count"] + data["in_expert_review_count"] +
                data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
                data["in_pod_lead_review_count"]
            ),
            "approval_rate": approved / reviewed if reviewed > 0 else 0,
            "rework_rate": rework / reviewed if reviewed > 0 else 0,
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })

    result.sort(key=lambda x: x["reviewed_count"], reverse=True)
    
    return result


# =============================================================================
# AGGREGATION - EXPERT REVIEWERS
# =============================================================================

@router.get("/aggregation/expert-reviewers")
def get_expert_reviewer_aggregation(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics aggregated by Expert Reviewer - counts review events from task_history"""
    from sqlalchemy import or_
    
    # Build name-to-email lookup
    users = db.query(TaskAgentUser).filter(
        TaskAgentUser.email.isnot(None),
        TaskAgentUser.name.isnot(None)
    ).all()
    name_to_email = {u.name.lower().strip(): u.email.lower() for u in users if u.name and u.email}
    email_to_name = {u.email.lower(): u.name for u in users if u.name and u.email}
    
    # Get tasks where expert reviewer is assigned
    query = db.query(Task).filter(
        or_(Task.expert_reviewer_email.isnot(None), Task.expert_reviewer_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_expert = query.all()
    
    # Group by Expert Reviewer
    expert_reviewers = {}
    
    # Process tasks for total counts and current status
    for task in tasks_with_expert:
        key = (task.expert_reviewer_email or "").lower() or task.expert_reviewer_name
        if not key:
            continue
            
        if key not in expert_reviewers:
            expert_reviewers[key] = {
                "expert_reviewer_email": task.expert_reviewer_email,
                "expert_reviewer_name": task.expert_reviewer_name or email_to_name.get(key, key),
                "total_tasks": 0,
                "draft_count": 0,
                "pending_review_count": 0,
                "in_expert_review_count": 0,
                "pending_calibrator_review_count": 0,
                "in_calibrator_review_count": 0,
                "in_pod_lead_review_count": 0,
                "rework_count": 0,
                "approved_count": 0,
                "trainers": set(),
                "domains": set()
            }
        
        expert_reviewers[key]["total_tasks"] += 1
        if task.trainer_email:
            expert_reviewers[key]["trainers"].add(task.trainer_email)
        if task.domain:
            expert_reviewers[key]["domains"].add(task.domain)
        
        # Current status counts
        if task.status == 'draft':
            expert_reviewers[key]["draft_count"] += 1
        elif task.status == 'pending_review':
            expert_reviewers[key]["pending_review_count"] += 1
        elif task.status == 'in_expert_review':
            expert_reviewers[key]["in_expert_review_count"] += 1
        elif task.status == 'pending_calibrator_review':
            expert_reviewers[key]["pending_calibrator_review_count"] += 1
        elif task.status == 'in_calibrator_review':
            expert_reviewers[key]["in_calibrator_review_count"] += 1
        elif task.status == 'in_pod_lead_review':
            expert_reviewers[key]["in_pod_lead_review_count"] += 1
        elif task.status == 'rework':
            pass  # Don't count in any review stage
    
    # Now count review events from task_history (ALL TIME)
    # Expert Reviewer events: expert_review_completed (approved), task_sent_to_rework_by_expert (rework)
    # IMPORTANT: Also handle both_reviews_completed with two-pass logic to prevent double counting
    tasks_with_history = db.query(Task).filter(Task.task_history.isnot(None))
    if domain:
        tasks_with_history = tasks_with_history.filter(Task.domain == domain)
    tasks_with_history = tasks_with_history.all()
    
    for task in tasks_with_history:
        if not task.task_history:
            continue
        
        # Two-pass logic for both_reviews_completed handling
        # Track which experts have APPROVAL events on this task (not rework - those are separate actions)
        task_expert_has_approval = set()  # emails that have expert_review_completed
        both_reviews_events = []  # (reviewer_email, initiated_by) tuples to process in pass 2
        
        # PASS 1: Count individual Expert Reviewer events
        for event in task.task_history:
            event_type = event.get('event', '').lower()
            initiated_by = event.get('initiated_by', '')
            
            # Get reviewer email from initiated_by name
            reviewer_email = name_to_email.get(initiated_by.lower().strip()) if initiated_by else None
            
            if not reviewer_email:
                continue
            
            key = reviewer_email.lower()
            
            # Handle individual Expert Reviewer events
            if event_type in ['expert_review_completed', 'task_sent_to_rework_by_expert']:
                # Only track approvals for deduplication (rework is a separate action)
                if event_type == 'expert_review_completed':
                    task_expert_has_approval.add(key)
                
                # Initialize if not exists
                if key not in expert_reviewers:
                    expert_reviewers[key] = {
                        "expert_reviewer_email": reviewer_email,
                        "expert_reviewer_name": email_to_name.get(key, initiated_by or key),
                        "total_tasks": 0,
                        "draft_count": 0,
                        "pending_review_count": 0,
                        "in_expert_review_count": 0,
                        "pending_calibrator_review_count": 0,
                        "in_calibrator_review_count": 0,
                        "in_pod_lead_review_count": 0,
                        "rework_count": 0,
                        "approved_count": 0,
                        "trainers": set(),
                        "domains": set()
                    }
                
                # Count the review event
                if event_type == 'expert_review_completed':
                    expert_reviewers[key]["approved_count"] += 1
                elif event_type == 'task_sent_to_rework_by_expert':
                    expert_reviewers[key]["rework_count"] += 1
            
            # Collect both_reviews_completed for pass 2
            elif event_type == 'both_reviews_completed':
                both_reviews_events.append((reviewer_email, initiated_by))
        
        # PASS 2: Handle both_reviews_completed - only count if initiator is Expert and has no APPROVAL event
        # (Rework events don't count - a reviewer can send to rework, then later approve via both_reviews_completed)
        for reviewer_email, initiated_by in both_reviews_events:
            key = reviewer_email.lower()
            
            # Check if this person is the Expert Reviewer for this task
            task_expert = (task.expert_reviewer_email or "").lower()
            if key != task_expert:
                continue  # Not the Expert, skip
            
            # Only count if no approval event exists (rework is a separate action)
            if key in task_expert_has_approval:
                continue  # Already has approval event, skip
            
            # Initialize if not exists
            if key not in expert_reviewers:
                expert_reviewers[key] = {
                    "expert_reviewer_email": reviewer_email,
                    "expert_reviewer_name": email_to_name.get(key, initiated_by or key),
                    "total_tasks": 0,
                    "draft_count": 0,
                    "pending_review_count": 0,
                    "in_expert_review_count": 0,
                    "pending_calibrator_review_count": 0,
                    "in_calibrator_review_count": 0,
                    "in_pod_lead_review_count": 0,
                    "rework_count": 0,
                    "approved_count": 0,
                    "trainers": set(),
                    "domains": set()
                }
            
            # Count as Expert approval (both_reviews_completed = approval)
            expert_reviewers[key]["approved_count"] += 1
    
    # Convert to result list
    result = []
    for key, data in expert_reviewers.items():
        approved = data["approved_count"]
        rework = data["rework_count"]
        reviewed = approved + rework  # Total review actions
        in_review = (
            data["pending_review_count"] + data["in_expert_review_count"] +
            data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
            data["in_pod_lead_review_count"]
        )
        total = approved + rework + in_review  # Total = Approved + Rework + In Review
        
        result.append({
            "expert_reviewer_email": data["expert_reviewer_email"],
            "expert_reviewer_name": data["expert_reviewer_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,
            "draft_count": data["draft_count"],
            "pending_review_count": data["pending_review_count"],
            "in_expert_review_count": data["in_expert_review_count"],
            "pending_calibrator_review_count": data["pending_calibrator_review_count"],
            "in_calibrator_review_count": data["in_calibrator_review_count"],
            "in_pod_lead_review_count": data["in_pod_lead_review_count"],
            "rework_count": rework,
            "approved_count": approved,
            "in_review_count": (
                data["pending_review_count"] + data["in_expert_review_count"] +
                data["pending_calibrator_review_count"] + data["in_calibrator_review_count"] +
                data["in_pod_lead_review_count"]
            ),
            "approval_rate": approved / reviewed if reviewed > 0 else 0,
            "rework_rate": rework / reviewed if reviewed > 0 else 0,
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })
    
    # Sort by reviewed count descending (most active reviewers first)
    result.sort(key=lambda x: x["reviewed_count"], reverse=True)
    
    return result


# =============================================================================
# TIME TRACKING (JIBBLE)
# =============================================================================

@router.get("/time-tracking/weekly")
def get_weekly_time_tracking(
    week_offset: int = Query(0, ge=-52, le=0, description="Week offset (0=current, -1=last week)"),
    trainer_email: Optional[str] = Query(None, description="Filter by trainer email or name"),
    page: int = Query(1, ge=1),
    per_page: int = Query(25, ge=10, le=100),
    db: Session = Depends(get_db)
):
    """
    Get weekly time tracking data for trainers
    Includes Jibble hours + task metrics (created, rework, reviewed)
    """
    from datetime import timedelta
    from collections import defaultdict
    
    # Calculate week boundaries (Monday to Sunday)
    # First get to start of current week, then apply week_offset
    today = datetime.now()
    start_of_current_week = today - timedelta(days=today.weekday())
    start_of_current_week = start_of_current_week.replace(hour=0, minute=0, second=0, microsecond=0)
    # week_offset is 0 or negative, so adding it goes back in time
    start_of_week = start_of_current_week + timedelta(weeks=week_offset)
    end_of_week = start_of_week + timedelta(days=6, hours=23, minutes=59, seconds=59)
    
    # ISO week string
    iso_year, iso_week, _ = start_of_week.isocalendar()
    iso_week_str = f"{iso_year}-W{iso_week:02d}"
    
    # Get all email mappings (defines who should be shown)
    # Maps: jibble_email (lowercase) -> turing_email, and turing_email (lowercase) -> jibble_email
    email_mappings = db.query(JibbleEmailMapping).all()
    allowed_emails = {m.jibble_email.lower(): m.turing_email for m in email_mappings}
    turing_emails = {m.turing_email.lower(): m.jibble_email for m in email_mappings}
    
    # Initialize people data from email mappings
    people_data = {}
    for mapping in email_mappings:
        people_data[mapping.turing_email] = {
            "turing_email": mapping.turing_email,
            "jibble_email": mapping.jibble_email,
            "person_name": None,
            "daily_hours": {(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0.0 for i in range(7)},
            "daily_tasks_created": {(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7)},
            "daily_rework_completed": {(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7)},
            "daily_tasks_reviewed": {(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7)},
            "daily_tasks_approved": {(start_of_week + timedelta(days=i)).strftime("%Y-%m-%d"): 0 for i in range(7)},
            "total_hours": 0.0,
            "total_tasks_created": 0,
            "total_rework_completed": 0,
            "total_tasks_reviewed": 0,
            "total_tasks_approved": 0,
        }
    
    # Get Jibble time entries for this week - aggregate by person and DATE to avoid timezone duplicates
    from sqlalchemy import func as sqlfunc, cast, Date
    
    # Use aggregation to get one row per person+date, taking MAX hours (in case of duplicates)
    time_entries_agg = db.query(
        JibblePerson.personal_email,
        JibblePerson.work_email,
        JibblePerson.full_name,
        cast(JibbleTimeEntry.entry_date, Date).label('entry_day'),
        sqlfunc.max(JibbleTimeEntry.total_hours).label('total_hours')  # MAX to handle duplicates
    ).join(
        JibblePerson, JibbleTimeEntry.person_id == JibblePerson.jibble_id
    ).filter(
        JibbleTimeEntry.entry_date >= start_of_week,
        JibbleTimeEntry.entry_date <= end_of_week
    ).group_by(
        JibblePerson.jibble_id,
        JibblePerson.personal_email,
        JibblePerson.work_email,
        JibblePerson.full_name,
        cast(JibbleTimeEntry.entry_date, Date)
    ).all()
    
    # Process time entries
    for row in time_entries_agg:
        personal_email, work_email, full_name, entry_day, hours = row
        jibble_email = personal_email or work_email
        if not jibble_email or jibble_email.lower() not in allowed_emails:
            continue
        
        turing_email = allowed_emails[jibble_email.lower()]
        if turing_email not in people_data:
            continue
        
        date_str = entry_day.strftime("%Y-%m-%d")
        hours = hours or 0.0
        
        if date_str in people_data[turing_email]["daily_hours"]:
            people_data[turing_email]["daily_hours"][date_str] = hours
            people_data[turing_email]["total_hours"] += hours
        
        # Set person name
        if not people_data[turing_email]["person_name"]:
            people_data[turing_email]["person_name"] = full_name
    
    # Get task metrics using SQL aggregation (much faster than loading all tasks)
    # Build a lookup from lowercase turing email to original turing email in people_data
    turing_email_lookup = {email.lower(): email for email in people_data.keys()}
    turing_email_set = set(turing_email_lookup.keys())
    
    # Tasks created - aggregate by trainer_email and date using SQL
    from sqlalchemy import func as sqlfunc, cast, Date
    
    tasks_created_agg = db.query(
        sqlfunc.lower(Task.trainer_email).label('email'),
        cast(Task.created_at, Date).label('date'),
        sqlfunc.count().label('count'),
        sqlfunc.max(Task.trainer_name).label('trainer_name')
    ).filter(
        Task.trainer_email.isnot(None),
        Task.created_at >= start_of_week,
        Task.created_at <= end_of_week,
        sqlfunc.lower(Task.trainer_email).in_(turing_email_set)
    ).group_by(
        sqlfunc.lower(Task.trainer_email),
        cast(Task.created_at, Date)
    ).all()
    
    for row in tasks_created_agg:
        trainer_key = row.email
        if trainer_key in turing_email_lookup:
            turing_email = turing_email_lookup[trainer_key]
            date_str = row.date.strftime("%Y-%m-%d")
            if date_str in people_data[turing_email]["daily_tasks_created"]:
                people_data[turing_email]["daily_tasks_created"][date_str] = row.count
                people_data[turing_email]["total_tasks_created"] += row.count
            if not people_data[turing_email]["person_name"] and row.trainer_name:
                people_data[turing_email]["person_name"] = row.trainer_name
    
    # Rework completed and Approved tasks - use task_history for accuracy
    # A rework is "completed" when a trainer submits a task after starting rework
    # A task is "approved" when both_reviews_completed or task_approved_by_calibrator event occurs
    
    # Build name-to-email lookup for trainer attribution
    from database_v2 import TaskAgentUser
    users = db.query(TaskAgentUser).filter(
        TaskAgentUser.email.isnot(None),
        TaskAgentUser.name.isnot(None)
    ).all()
    name_to_email_trainer = {u.name.lower().strip(): u.email.lower() for u in users if u.name and u.email}
    
    # Fetch all tasks with task_history
    tasks_with_history = db.query(Task).filter(
        Task.task_history.isnot(None)
    ).all()
    
    # Track rework completions and approvals
    rework_by_email_date = {}  # {email: {date_str: count}}
    approved_by_email_date = {}  # {email: {date_str: count}}
    
    # Track which tasks have been counted to avoid double-counting
    approved_tasks_counted = set()  # {(task_id, date_str)}
    
    # Make week boundaries timezone-aware for comparison with task_history timestamps
    from datetime import timezone as tz
    start_of_week_utc = start_of_week.replace(tzinfo=tz.utc)
    end_of_week_utc = end_of_week.replace(tzinfo=tz.utc)
    
    for task in tasks_with_history:
        if not task.task_history:
            continue
        
        task_trainer_email = (task.trainer_email or "").lower()
        if not task_trainer_email or task_trainer_email not in turing_email_lookup:
            continue
        
        # Sort events by time
        events = sorted(task.task_history, key=lambda x: x.get('created_at', ''))
        
        in_rework = False
        
        for event in events:
            event_type = event.get('event', '').lower()
            created_at = event.get('created_at', '')
            
            # Track rework state
            if event_type == 'task_started_rework':
                in_rework = True
            
            # Rework completed = task_submitted while in rework state
            if event_type == 'task_submitted' and in_rework:
                try:
                    event_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if start_of_week_utc <= event_date <= end_of_week_utc:
                        date_str = event_date.strftime("%Y-%m-%d")
                        if task_trainer_email not in rework_by_email_date:
                            rework_by_email_date[task_trainer_email] = {}
                        if date_str not in rework_by_email_date[task_trainer_email]:
                            rework_by_email_date[task_trainer_email][date_str] = 0
                        rework_by_email_date[task_trainer_email][date_str] += 1
                except Exception as e:
                    logger.debug(f"Error parsing rework event date: {e}")
                in_rework = False
            
            # Approved = both_reviews_completed or task_approved_by_calibrator
            # Only count ONCE per task per day (avoid double-counting multiple approval events)
            if event_type in ['both_reviews_completed', 'task_approved_by_calibrator']:
                try:
                    event_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                    if start_of_week_utc <= event_date <= end_of_week_utc:
                        date_str = event_date.strftime("%Y-%m-%d")
                        
                        # Check if this task was already counted as approved this week
                        task_key = (task.task_agent_id, task_trainer_email)
                        if task_key in approved_tasks_counted:
                            continue  # Skip - already counted
                        approved_tasks_counted.add(task_key)
                        
                        if task_trainer_email not in approved_by_email_date:
                            approved_by_email_date[task_trainer_email] = {}
                        if date_str not in approved_by_email_date[task_trainer_email]:
                            approved_by_email_date[task_trainer_email][date_str] = 0
                        approved_by_email_date[task_trainer_email][date_str] += 1
                except Exception as e:
                    logger.debug(f"Error parsing approval event date: {e}")
    
    # Apply rework counts to people_data
    for email, daily_counts in rework_by_email_date.items():
        if email in turing_email_lookup:
            turing_email = turing_email_lookup[email]
            for date_str, count in daily_counts.items():
                if date_str in people_data[turing_email]["daily_rework_completed"]:
                    people_data[turing_email]["daily_rework_completed"][date_str] = count
                    people_data[turing_email]["total_rework_completed"] += count
    
    # Apply approved counts to people_data
    for email, daily_counts in approved_by_email_date.items():
        if email in turing_email_lookup:
            turing_email = turing_email_lookup[email]
            for date_str, count in daily_counts.items():
                if date_str in people_data[turing_email]["daily_tasks_approved"]:
                    people_data[turing_email]["daily_tasks_approved"][date_str] = count
                    people_data[turing_email]["total_tasks_approved"] += count
    
    # Tasks reviewed - count from task_history events
    # Review events that count as "+1 review":
    # - Expert Reviewer: expert_review_completed (approved), task_sent_to_rework_by_expert (rejected)
    # - POD Lead: pod_lead_review_completed (approved), task_sent_to_rework_by_pod_lead (rejected)
    # - Calibrator: task_approved_by_calibrator (approved), task_sent_to_rework_by_calibrator (rejected)
    # IMPORTANT: both_reviews_completed is counted using two-pass logic to prevent double counting
    #            It's only counted if the initiator doesn't have an individual event for that task
    
    REVIEW_EVENTS = {
        'expert_review_completed': 'expert_reviewer',
        'task_sent_to_rework_by_expert': 'expert_reviewer',
        'pod_lead_review_completed': 'pod_lead',
        'task_sent_to_rework_by_pod_lead': 'pod_lead',
        'task_approved_by_calibrator': 'calibrator',
        'task_sent_to_rework_by_calibrator': 'calibrator',
    }
    
    # Reuse name_to_email_trainer from rework/approved section above
    name_to_email = name_to_email_trainer
    
    # Parse task_history to count reviews (reuse tasks_with_history from above)
    reviews_by_email_date = {}  # {email: {date_str: count}}
    
    for task in tasks_with_history:
        if not task.task_history:
            continue
        
        # Two-pass logic: track which reviewers have APPROVAL events for this task
        # (not rework - those are separate actions, and we should count both_reviews_completed after rework)
        task_reviewers_with_approval = set()  # emails that have individual approval events
        both_reviews_events_for_task = []  # (initiated_by, created_at) tuples
        
        # Approval events (for deduplication with both_reviews_completed)
        APPROVAL_EVENTS = {'expert_review_completed', 'pod_lead_review_completed', 'task_approved_by_calibrator'}
        
        # PASS 1: Count individual review events
        for event in task.task_history:
            event_type = event.get('event', '').lower()
            initiated_by = event.get('initiated_by', '')
            created_at = event.get('created_at', '')
            
            # Collect both_reviews_completed for pass 2
            if event_type == 'both_reviews_completed':
                both_reviews_events_for_task.append((initiated_by, created_at))
                continue
            
            # Check if this is an individual review event
            if event_type not in REVIEW_EVENTS:
                continue
            
            # Parse event date
            if not created_at:
                continue
            try:
                event_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                # Check if event is within our week range (using UTC-aware comparison)
                if event_date < start_of_week_utc or event_date > end_of_week_utc:
                    continue
                event_date_str = event_date.strftime("%Y-%m-%d")
            except Exception as e:
                logger.debug(f"Error parsing review event date: {e}")
                continue
            
            # Get reviewer email from name
            reviewer_email = None
            if initiated_by:
                reviewer_email = name_to_email.get(initiated_by.lower().strip())
            
            if not reviewer_email:
                continue
            
            # Check if this reviewer is in our allowed list
            if reviewer_email not in turing_email_lookup:
                continue
            
            # Track only APPROVAL events for deduplication (rework is a separate action)
            if event_type in APPROVAL_EVENTS:
                task_reviewers_with_approval.add(reviewer_email.lower())
            
            # Count the review
            if reviewer_email not in reviews_by_email_date:
                reviews_by_email_date[reviewer_email] = {}
            if event_date_str not in reviews_by_email_date[reviewer_email]:
                reviews_by_email_date[reviewer_email][event_date_str] = 0
            reviews_by_email_date[reviewer_email][event_date_str] += 1
        
        # PASS 2: Handle both_reviews_completed - only count if initiator has no individual event
        for initiated_by, created_at in both_reviews_events_for_task:
            if not created_at or not initiated_by:
                continue
            
            try:
                event_date = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                if event_date < start_of_week_utc or event_date > end_of_week_utc:
                    continue
                event_date_str = event_date.strftime("%Y-%m-%d")
            except Exception:
                continue
            
            # Get reviewer email from name
            reviewer_email = name_to_email.get(initiated_by.lower().strip())
            if not reviewer_email:
                continue
            
            reviewer_email_lower = reviewer_email.lower()
            
            # Check if this reviewer is in our allowed list
            if reviewer_email not in turing_email_lookup:
                continue
            
            # Determine the role of this person on this task
            task_pod_lead = (task.pod_lead_email or "").lower()
            task_expert = (task.expert_reviewer_email or "").lower()
            
            is_pod_lead = reviewer_email_lower == task_pod_lead
            is_expert = reviewer_email_lower == task_expert
            
            # Only count if they don't already have an APPROVAL event for this task
            # (Rework events don't count - a reviewer can send to rework, then later approve via both_reviews_completed)
            if reviewer_email_lower in task_reviewers_with_approval:
                continue  # Already has approval event, skip
            
            # Check role and count
            if is_pod_lead or is_expert:
                if reviewer_email not in reviews_by_email_date:
                    reviews_by_email_date[reviewer_email] = {}
                if event_date_str not in reviews_by_email_date[reviewer_email]:
                    reviews_by_email_date[reviewer_email][event_date_str] = 0
                reviews_by_email_date[reviewer_email][event_date_str] += 1
    
    # Apply review counts to people_data
    for reviewer_email, daily_counts in reviews_by_email_date.items():
        if reviewer_email in turing_email_lookup:
            turing_email = turing_email_lookup[reviewer_email]
            for date_str, count in daily_counts.items():
                if date_str in people_data[turing_email]["daily_tasks_reviewed"]:
                    people_data[turing_email]["daily_tasks_reviewed"][date_str] = count
                    people_data[turing_email]["total_tasks_reviewed"] += count
    
    # Fill in person names from email where missing
    for email, data in people_data.items():
        if not data["person_name"]:
            # Try to derive from email
            name_part = email.split("@")[0]
            data["person_name"] = name_part.replace(".", " ").title()
    
    # Convert to list and apply filtering
    trainers = list(people_data.values())
    
    # Filter by trainer_email/name if provided
    if trainer_email:
        search_lower = trainer_email.lower()
        trainers = [
            t for t in trainers 
            if search_lower in (t["turing_email"] or "").lower() 
            or search_lower in (t["jibble_email"] or "").lower()
            or search_lower in (t["person_name"] or "").lower()
        ]
    
    # Sort by total hours descending
    trainers.sort(key=lambda t: t["total_hours"], reverse=True)
    
    # Pagination
    total = len(trainers)
    total_pages = (total + per_page - 1) // per_page
    offset = (page - 1) * per_page
    trainers_page = trainers[offset:offset + per_page]
    
    # Calculate totals
    total_hours = sum(t["total_hours"] for t in trainers)
    total_created = sum(t["total_tasks_created"] for t in trainers)
    total_rework = sum(t["total_rework_completed"] for t in trainers)
    total_reviewed = sum(t["total_tasks_reviewed"] for t in trainers)
    total_approved = sum(t["total_tasks_approved"] for t in trainers)
    
    return {
        "week": iso_week_str,
        "start_date": start_of_week.date().isoformat(),
        "end_date": end_of_week.date().isoformat(),
        "trainers": trainers_page,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "summary": {
            "total_hours": round(total_hours, 2),
            "total_tasks_created": total_created,
            "total_rework_completed": total_rework,
            "total_tasks_reviewed": total_reviewed,
            "total_tasks_approved": total_approved,
            "active_trainers": len([t for t in trainers if t["total_hours"] > 0]),
        }
    }


@router.post("/time-tracking/sync")
def sync_time_tracking(
    db: Session = Depends(get_db)
):
    """Sync Jibble time tracking data for current month"""
    from jibble_sync_service import JibbleSyncService
    
    try:
        sync_service = JibbleSyncService(db)
        result = sync_service.full_sync()
        return result
    except Exception as e:
        logger.error(f"Time tracking sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/time-tracking/test")
def test_jibble_connection():
    """Test Jibble API connection"""
    from jibble_service import JibbleService
    
    try:
        service = JibbleService()
        return service.test_connection()
    except Exception as e:
        return {
            "success": False,
            "message": f"Connection test failed: {str(e)}",
            "has_token": False,
        }
