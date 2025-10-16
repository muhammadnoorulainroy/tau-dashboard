from pydantic import BaseModel
from typing import List, Dict, Optional, Any
from datetime import datetime

class DeveloperMetrics(BaseModel):
    id: int
    username: str
    github_login: Optional[str]
    total_prs: int
    open_prs: int
    merged_prs: int
    total_rework: int
    last_updated: datetime
    metrics: Dict[str, Any]
    
    class Config:
        from_attributes = True

class ReviewerMetrics(BaseModel):
    id: int
    username: str
    total_reviews: int
    approved_reviews: int
    changes_requested: int
    last_updated: datetime
    metrics: Dict[str, Any]
    
    class Config:
        from_attributes = True

class DomainMetricsResponse(BaseModel):
    id: int
    domain: str
    total_tasks: int
    expert_review_pending: int
    calibrator_review_pending: int
    expert_approved: int
    ready_to_merge: int
    merged: int
    expert_count: int
    hard_count: int
    medium_count: int
    last_updated: datetime
    detailed_metrics: Dict[str, Any]
    
    class Config:
        from_attributes = True

class PullRequestResponse(BaseModel):
    id: int
    github_id: int
    number: int
    title: str
    state: str
    merged: bool
    developer_username: Optional[str]
    domain: Optional[str]
    difficulty: Optional[str]
    task_id: Optional[str]
    author_login: str
    author_email: Optional[str]
    created_at: datetime
    updated_at: datetime
    closed_at: Optional[datetime]
    merged_at: Optional[datetime]
    labels: List[str]
    review_count: int
    comment_count: int
    rework_count: int
    check_failures: int
    
    class Config:
        from_attributes = True

class DashboardOverview(BaseModel):
    total_prs: int
    open_prs: int
    merged_prs: int
    total_developers: int
    total_reviewers: int
    total_domains: int
    average_rework: float
    recent_activity: List[Dict[str, Any]]
    last_sync_time: Optional[datetime] = None

class PRStateDistribution(BaseModel):
    domain: Optional[str]
    distribution: Dict[str, int]
    total: int

class PaginatedDevelopers(BaseModel):
    data: List[DeveloperMetrics]
    total: int
    limit: int
    offset: int

class PaginatedReviewers(BaseModel):
    data: List[ReviewerMetrics]
    total: int
    limit: int
    offset: int


class AggregationMetrics(BaseModel):
    """Metrics for aggregation views"""
    name: str
    email: Optional[str] = None  # Email address (for trainers)
    total_tasks: int
    completed_tasks: int
    rework_percentage: float
    rejected_count: int
    delivery_ready_tasks: int


