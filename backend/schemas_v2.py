"""
Pydantic schemas for Task Agent API endpoints (v2)
"""
from pydantic import BaseModel, ConfigDict, field_serializer
from typing import List, Dict, Optional, Any
from datetime import datetime, timezone


class TaskResponse(BaseModel):
    """Response model for a single task"""
    id: int
    task_agent_id: str
    description: Optional[str] = None
    difficulty: Optional[str] = None
    status: str
    domain: Optional[str] = None
    interface_num: Optional[int] = None
    
    # Trainer
    trainer_id: Optional[str] = None
    trainer_name: Optional[str] = None
    trainer_email: Optional[str] = None
    
    # Reviewers
    reviewer_name: Optional[str] = None
    reviewer_email: Optional[str] = None
    expert_reviewer_name: Optional[str] = None
    expert_reviewer_email: Optional[str] = None
    pod_lead_name: Optional[str] = None
    pod_lead_email: Optional[str] = None
    
    # Batch
    batch_id: Optional[str] = None
    batch_name: Optional[str] = None
    batch_status: Optional[str] = None
    
    # Metrics
    rework_count: int = 0
    
    # Content
    instruction_text: Optional[str] = None
    tool_sequence: Optional[dict] = None
    
    # Timestamps
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer('created_at', 'updated_at', 'completed_at')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class PaginatedTasks(BaseModel):
    """Paginated list of tasks"""
    data: List[TaskResponse]
    total: int
    page: int
    per_page: int
    total_pages: int


class EnvironmentResponse(BaseModel):
    """Response model for an environment/domain"""
    id: int
    name: str
    description: Optional[str] = None
    is_active: bool = True
    
    # Total counts
    total_tasks: int = 0
    
    # Individual status counts
    draft_count: int = 0
    pending_review_count: int = 0
    in_expert_review_count: int = 0
    pending_calibrator_review_count: int = 0
    in_calibrator_review_count: int = 0
    in_pod_lead_review_count: int = 0
    rework_count: int = 0
    approved_count: int = 0
    
    # Complexity breakdown
    approved_expert: int = 0
    approved_hard: int = 0
    approved_medium: int = 0
    total_expert: int = 0
    total_hard: int = 0
    total_medium: int = 0
    
    last_synced: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer('last_synced')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class TrainerMetrics(BaseModel):
    """Metrics for a trainer"""
    trainer_email: str
    trainer_name: Optional[str] = None
    total_tasks: int = 0
    
    # Status counts
    draft_count: int = 0
    pending_review_count: int = 0
    in_expert_review_count: int = 0
    pending_calibrator_review_count: int = 0
    in_calibrator_review_count: int = 0
    in_pod_lead_review_count: int = 0
    rework_count: int = 0
    approved_count: int = 0
    
    # Computed metrics
    approval_rate: float = 0.0  # approved / total
    rework_rate: float = 0.0  # rework / total
    in_review_count: int = 0  # all review stages combined
    
    # Complexity
    expert_count: int = 0
    hard_count: int = 0
    medium_count: int = 0


class PaginatedTrainers(BaseModel):
    """Paginated list of trainers with metrics"""
    data: List[TrainerMetrics]
    total: int
    page: int
    per_page: int


class BatchResponse(BaseModel):
    """Response model for a batch"""
    id: int
    batch_agent_id: str
    batch_name: str
    environment: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    is_locked: bool = False
    is_exported: bool = False
    task_count: int = 0
    author: Optional[str] = None
    
    date_opened: Optional[datetime] = None
    date_closed: Optional[datetime] = None
    
    model_config = ConfigDict(from_attributes=True)
    
    @field_serializer('date_opened', 'date_closed')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class DashboardOverviewV2(BaseModel):
    """Dashboard overview for Task Agent data"""
    total_tasks: int = 0
    total_trainers: int = 0
    total_domains: int = 0
    total_batches: int = 0
    
    # Status breakdown
    draft_count: int = 0
    pending_review_count: int = 0
    in_expert_review_count: int = 0
    pending_calibrator_review_count: int = 0
    in_calibrator_review_count: int = 0
    in_pod_lead_review_count: int = 0
    rework_count: int = 0
    approved_count: int = 0
    
    # Computed
    in_review_count: int = 0  # all review stages combined
    average_rework: float = 0.0
    approval_rate: float = 0.0
    
    # Sync info
    last_sync_time: Optional[datetime] = None
    
    @field_serializer('last_sync_time')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class StatusBreakdown(BaseModel):
    """Status breakdown for a domain or overall"""
    domain: Optional[str] = None
    total: int = 0
    breakdown: Dict[str, int] = {}


class SyncStatusResponse(BaseModel):
    """Response for sync status"""
    last_sync_time: Optional[datetime] = None
    last_full_sync_time: Optional[datetime] = None
    tasks_synced: int = 0
    users_synced: int = 0
    batches_synced: int = 0
    
    @field_serializer('last_sync_time', 'last_full_sync_time')
    def serialize_datetime(self, dt: Optional[datetime]) -> Optional[str]:
        if dt is None:
            return None
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc)
        else:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat()


class TaskSimilarityResponse(BaseModel):
    """Response for task similarity"""
    task_id: int
    task_agent_id: str
    instruction_text: Optional[str] = None
    domain: Optional[str] = None
    similar_tasks: List[Dict[str, Any]] = []


class ActionSimilarityResponse(BaseModel):
    """Response for action similarity"""
    task_id: int
    task_agent_id: str
    tool_sequence: Optional[Dict] = None
    domain: Optional[str] = None
    similar_tasks: List[Dict[str, Any]] = []


