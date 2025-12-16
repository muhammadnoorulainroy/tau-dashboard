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
    """Get task statistics aggregated by POD Lead"""
    from sqlalchemy import or_
    
    # Get tasks where POD lead is assigned (for non-rework tasks)
    query = db.query(Task).filter(
        or_(Task.pod_lead_email.isnot(None), Task.pod_lead_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_pod_lead = query.all()
    
    # Get ALL tasks that were ever sent to rework BY a POD lead
    # (regardless of current status - task may have been fixed and approved)
    rework_query = db.query(Task).filter(
        Task.rework_by_role == 'pod_lead',
        or_(Task.rework_by_email.isnot(None), Task.rework_by_name.isnot(None))
    )
    if domain:
        rework_query = rework_query.filter(Task.domain == domain)
    rework_tasks = rework_query.all()
    
    # Group by POD Lead
    pod_leads = {}
    
    # Process tasks with POD lead assigned (approved, in_review, etc.)
    for task in tasks_with_pod_lead:
        key = task.pod_lead_email or task.pod_lead_name
        if not key:
            continue
            
        if key not in pod_leads:
            pod_leads[key] = {
                "pod_lead_email": task.pod_lead_email,
                "pod_lead_name": task.pod_lead_name,
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
        
        pod_leads[key]["total_tasks"] += 1
        if task.trainer_email:
            pod_leads[key]["trainers"].add(task.trainer_email)
        if task.domain:
            pod_leads[key]["domains"].add(task.domain)
        
        # Status counts (exclude rework here - we'll add from rework_tasks)
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
        elif task.status == 'approved':
            pod_leads[key]["approved_count"] += 1
    
    # Add rework tasks sent by each POD lead
    for task in rework_tasks:
        key = task.rework_by_email or task.rework_by_name
        if not key:
            continue
        
        if key not in pod_leads:
            pod_leads[key] = {
                "pod_lead_email": task.rework_by_email,
                "pod_lead_name": task.rework_by_name,
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
        
        pod_leads[key]["rework_count"] += 1
        pod_leads[key]["total_tasks"] += 1
        if task.trainer_email:
            pod_leads[key]["trainers"].add(task.trainer_email)
        if task.domain:
            pod_leads[key]["domains"].add(task.domain)
    
    # Convert sets to counts and calculate metrics
    result = []
    for key, data in pod_leads.items():
        total = data["total_tasks"]
        approved = data["approved_count"]
        rework = data["rework_count"]
        
        reviewed = approved + rework  # Tasks that have been reviewed (decision made)
        result.append({
            "pod_lead_email": data["pod_lead_email"],
            "pod_lead_name": data["pod_lead_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,  # NEW: Approved + Rework = tasks reviewed
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
            "approval_rate": approved / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "rework_rate": rework / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })
    
    # Sort by total tasks descending
    result.sort(key=lambda x: x["total_tasks"], reverse=True)
    
    return result


# =============================================================================
# AGGREGATION - CALIBRATORS (REVIEWERS)
# =============================================================================

@router.get("/aggregation/calibrators")
def get_calibrator_aggregation(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics aggregated by Calibrator (Reviewer)"""
    from sqlalchemy import or_
    
    # Get tasks where calibrator is assigned (for non-rework tasks)
    query = db.query(Task).filter(
        or_(Task.reviewer_email.isnot(None), Task.reviewer_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_calibrator = query.all()
    
    # Get ALL tasks that were ever sent to rework BY a calibrator
    # (regardless of current status - task may have been fixed and approved)
    rework_query = db.query(Task).filter(
        Task.rework_by_role == 'calibrator',
        or_(Task.rework_by_email.isnot(None), Task.rework_by_name.isnot(None))
    )
    if domain:
        rework_query = rework_query.filter(Task.domain == domain)
    rework_tasks = rework_query.all()
    
    # Group by Calibrator
    calibrators = {}
    
    # Process tasks with calibrator assigned
    for task in tasks_with_calibrator:
        key = task.reviewer_email or task.reviewer_name
        if not key:
            continue
            
        if key not in calibrators:
            calibrators[key] = {
                "calibrator_email": task.reviewer_email,
                "calibrator_name": task.reviewer_name,
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
        
        # Status counts (exclude rework - we'll add from rework_tasks)
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
        elif task.status == 'approved':
            calibrators[key]["approved_count"] += 1
    
    # Add rework tasks sent by each calibrator
    for task in rework_tasks:
        key = task.rework_by_email or task.rework_by_name
        if not key:
            continue
        
        if key not in calibrators:
            calibrators[key] = {
                "calibrator_email": task.rework_by_email,
                "calibrator_name": task.rework_by_name,
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
        
        calibrators[key]["rework_count"] += 1
        calibrators[key]["total_tasks"] += 1
        if task.trainer_email:
            calibrators[key]["trainers"].add(task.trainer_email)
        if task.domain:
            calibrators[key]["domains"].add(task.domain)
    
    # Convert sets to counts and calculate metrics
    result = []
    for key, data in calibrators.items():
        total = data["total_tasks"]
        approved = data["approved_count"]
        rework = data["rework_count"]
        
        reviewed = approved + rework  # Tasks that have been reviewed (decision made)
        result.append({
            "calibrator_email": data["calibrator_email"],
            "calibrator_name": data["calibrator_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,  # NEW: Approved + Rework = tasks reviewed
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
            "approval_rate": approved / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "rework_rate": rework / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })
    
    # Sort by total tasks descending
    result.sort(key=lambda x: x["total_tasks"], reverse=True)
    
    return result


# =============================================================================
# AGGREGATION - EXPERT REVIEWERS
# =============================================================================

@router.get("/aggregation/expert-reviewers")
def get_expert_reviewer_aggregation(
    domain: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Get task statistics aggregated by Expert Reviewer"""
    from sqlalchemy import or_
    
    # Get tasks where expert reviewer is assigned (for non-rework tasks)
    query = db.query(Task).filter(
        or_(Task.expert_reviewer_email.isnot(None), Task.expert_reviewer_name.isnot(None))
    )
    if domain:
        query = query.filter(Task.domain == domain)
    tasks_with_expert = query.all()
    
    # Get ALL tasks that were ever sent to rework BY an expert reviewer
    # (regardless of current status - task may have been fixed and approved)
    rework_query = db.query(Task).filter(
        Task.rework_by_role == 'expert_reviewer',
        or_(Task.rework_by_email.isnot(None), Task.rework_by_name.isnot(None))
    )
    if domain:
        rework_query = rework_query.filter(Task.domain == domain)
    rework_tasks = rework_query.all()
    
    # Group by Expert Reviewer
    expert_reviewers = {}
    
    # Process tasks with expert reviewer assigned
    for task in tasks_with_expert:
        key = task.expert_reviewer_email or task.expert_reviewer_name
        if not key:
            continue
            
        if key not in expert_reviewers:
            expert_reviewers[key] = {
                "expert_reviewer_email": task.expert_reviewer_email,
                "expert_reviewer_name": task.expert_reviewer_name,
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
        
        # Status counts (exclude rework - we'll add from rework_tasks)
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
        elif task.status == 'approved':
            expert_reviewers[key]["approved_count"] += 1
    
    # Add rework tasks sent by each expert reviewer
    for task in rework_tasks:
        key = task.rework_by_email or task.rework_by_name
        if not key:
            continue
        
        if key not in expert_reviewers:
            expert_reviewers[key] = {
                "expert_reviewer_email": task.rework_by_email,
                "expert_reviewer_name": task.rework_by_name,
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
        
        expert_reviewers[key]["rework_count"] += 1
        expert_reviewers[key]["total_tasks"] += 1
        if task.trainer_email:
            expert_reviewers[key]["trainers"].add(task.trainer_email)
        if task.domain:
            expert_reviewers[key]["domains"].add(task.domain)
    
    # Convert sets to counts and calculate metrics
    result = []
    for key, data in expert_reviewers.items():
        total = data["total_tasks"]
        approved = data["approved_count"]
        rework = data["rework_count"]
        
        reviewed = approved + rework  # Tasks that have been reviewed (decision made)
        result.append({
            "expert_reviewer_email": data["expert_reviewer_email"],
            "expert_reviewer_name": data["expert_reviewer_name"],
            "total_tasks": total,
            "reviewed_count": reviewed,  # NEW: Approved + Rework = tasks reviewed
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
            "approval_rate": approved / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "rework_rate": rework / reviewed if reviewed > 0 else 0,  # Changed: based on reviewed tasks
            "trainer_count": len(data["trainers"]),
            "domain_count": len(data["domains"])
        })
    
    # Sort by total tasks descending
    result.sort(key=lambda x: x["total_tasks"], reverse=True)
    
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
            "total_hours": 0.0,
            "total_tasks_created": 0,
            "total_rework_completed": 0,
            "total_tasks_reviewed": 0,
        }
    
    # Get Jibble time entries for this week
    time_entries = db.query(JibbleTimeEntry, JibblePerson).join(
        JibblePerson, JibbleTimeEntry.person_id == JibblePerson.jibble_id
    ).filter(
        JibbleTimeEntry.entry_date >= start_of_week,
        JibbleTimeEntry.entry_date <= end_of_week
    ).all()
    
    # Process time entries
    for entry, person in time_entries:
        jibble_email = person.personal_email or person.work_email
        if not jibble_email or jibble_email.lower() not in allowed_emails:
            continue
        
        turing_email = allowed_emails[jibble_email.lower()]
        if turing_email not in people_data:
            continue
        
        date_str = entry.entry_date.strftime("%Y-%m-%d")
        hours = entry.total_hours or 0.0
        
        if date_str in people_data[turing_email]["daily_hours"]:
            people_data[turing_email]["daily_hours"][date_str] = hours
            people_data[turing_email]["total_hours"] += hours
        
        # Set person name
        if not people_data[turing_email]["person_name"]:
            people_data[turing_email]["person_name"] = person.full_name
    
    # Get task metrics for each trainer
    # Build a lookup from lowercase turing email to original turing email in people_data
    turing_email_lookup = {email.lower(): email for email in people_data.keys()}
    
    # Tasks created - query all tasks in the date range, then filter by email
    tasks_created = db.query(Task).filter(
        Task.trainer_email.isnot(None),
        Task.created_at >= start_of_week,
        Task.created_at <= end_of_week
    ).all()
    
    for task in tasks_created:
        trainer_key = task.trainer_email.lower() if task.trainer_email else None
        if trainer_key and trainer_key in turing_email_lookup:
            turing_email = turing_email_lookup[trainer_key]
            date_str = task.created_at.strftime("%Y-%m-%d")
            if date_str in people_data[turing_email]["daily_tasks_created"]:
                people_data[turing_email]["daily_tasks_created"][date_str] += 1
                people_data[turing_email]["total_tasks_created"] += 1
            # Set person name from task if not set
            if not people_data[turing_email]["person_name"] and task.trainer_name:
                people_data[turing_email]["person_name"] = task.trainer_name
    
    # Rework completed (trainer fixed their rework - task no longer in rework status)
    rework_completed = db.query(Task).filter(
        Task.trainer_email.isnot(None),
        Task.status != 'rework',  # No longer in rework
        Task.rework_by_email.isnot(None),  # Was in rework at some point
        Task.updated_at >= start_of_week,
        Task.updated_at <= end_of_week
    ).all()
    
    for task in rework_completed:
        trainer_key = task.trainer_email.lower() if task.trainer_email else None
        if trainer_key and trainer_key in turing_email_lookup:
            turing_email = turing_email_lookup[trainer_key]
            date_str = task.updated_at.strftime("%Y-%m-%d")
            if date_str in people_data[turing_email]["daily_rework_completed"]:
                people_data[turing_email]["daily_rework_completed"][date_str] += 1
                people_data[turing_email]["total_rework_completed"] += 1
    
    # Tasks reviewed (by pod leads, calibrators, expert reviewers)
    # Only count 'approved' tasks as successfully reviewed
    # This credits the pod_lead who gave final approval
    approved_tasks = db.query(Task).filter(
        Task.updated_at >= start_of_week,
        Task.updated_at <= end_of_week,
        Task.status == 'approved'
    ).all()
    
    for task in approved_tasks:
        date_str = task.updated_at.strftime("%Y-%m-%d")
        
        # Credit the pod lead who approved the task
        if task.pod_lead_email:
            reviewer_key = task.pod_lead_email.lower()
            if reviewer_key in turing_email_lookup:
                turing_email = turing_email_lookup[reviewer_key]
                if date_str in people_data[turing_email]["daily_tasks_reviewed"]:
                    people_data[turing_email]["daily_tasks_reviewed"][date_str] += 1
                    people_data[turing_email]["total_tasks_reviewed"] += 1
    
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
            "active_trainers": len([t for t in trainers if t["total_hours"] > 0]),
        }
    }


@router.post("/time-tracking/sync")
def sync_time_tracking(
    weeks: int = Query(2, ge=1, le=8, description="Number of weeks to sync"),
    db: Session = Depends(get_db)
):
    """Sync Jibble time tracking data"""
    from jibble_sync_service import JibbleSyncService
    
    try:
        sync_service = JibbleSyncService(db)
        result = sync_service.full_sync(weeks=weeks)
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
