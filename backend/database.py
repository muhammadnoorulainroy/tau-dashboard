from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, ForeignKey, Index, UniqueConstraint, Float
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from datetime import datetime
from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class PullRequest(Base):
    __tablename__ = "pull_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, index=True)
    number = Column(Integer, index=True)
    title = Column(String, index=True)
    state = Column(String, index=True)  # open, closed
    merged = Column(Boolean, default=False, index=True)
    
    # Extracted fields from title pattern: username-domain-difficulty-taskid
    developer_username = Column(String, index=True)
    domain = Column(String, index=True)
    difficulty = Column(String, index=True)
    task_id = Column(String, index=True)
    
    # GitHub data
    author_login = Column(String, index=True)  # Links to DeveloperHierarchy.github_user
    author_email = Column(String, nullable=True)  # Fetched from GitHub API
    
    created_at = Column(DateTime)
    updated_at = Column(DateTime)
    closed_at = Column(DateTime, nullable=True)
    merged_at = Column(DateTime, nullable=True)
    
    # Labels/Tags stored as JSON array
    labels = Column(JSON, default=list)
    
    # Review and feedback tracking
    review_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    review_comments_count = Column(Integer, default=0)
    
    # Rework tracking
    rework_count = Column(Integer, default=0)
    check_failures = Column(Integer, default=0)
    check_passes = Column(Integer, default=0)
    
    # Task Execution Results (from bot comment)
    task_trials_total = Column(Integer, default=0)
    task_trials_passed = Column(Integer, default=0)
    task_trials_failed = Column(Integer, default=0)
    task_success_rate = Column(Float, default=0.0)
    
    # Interface/Week tracking (added via migration)
    trainer_id = Column(Integer, nullable=True)
    domain_id = Column(Integer, nullable=True)
    interface_id = Column(Integer, nullable=True)
    week_id = Column(Integer, nullable=True)
    pod_id = Column(Integer, nullable=True)
    trainer_name = Column(String, nullable=True)
    interface_num = Column(Integer, nullable=True, index=True)
    complexity = Column(String, nullable=True)
    timestamp = Column(BigInteger, nullable=True)
    week_num = Column(Integer, nullable=True, index=True)
    week_name = Column(String, nullable=True)
    pod_name = Column(String, nullable=True)
    
    # Timestamps
    last_synced = Column(DateTime, default=func.now())
    
    # Relationships
    reviews = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")
    check_runs = relationship("CheckRun", back_populates="pull_request", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index('idx_pr_domain_state', 'domain', 'state'),
        Index('idx_pr_developer', 'developer_username'),
        Index('idx_pr_created', 'created_at'),
    )


class Review(Base):
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, index=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    reviewer_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewer_login = Column(String, index=True)
    state = Column(String)  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    submitted_at = Column(DateTime)
    body = Column(Text, nullable=True)
    
    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])
    
    __table_args__ = (
        Index('idx_review_reviewer', 'reviewer_login'),
        Index('idx_review_state', 'state'),
    )


class CheckRun(Base):
    __tablename__ = "check_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, index=True)
    pull_request_id = Column(Integer, ForeignKey("pull_requests.id"))
    name = Column(String)
    status = Column(String)  # completed, in_progress, queued
    conclusion = Column(String, nullable=True)  # success, failure, neutral, cancelled
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    
    pull_request = relationship("PullRequest", back_populates="check_runs")


class Developer(Base):
    __tablename__ = "developers"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    github_login = Column(String, index=True)
    total_prs = Column(Integer, default=0)
    open_prs = Column(Integer, default=0)
    merged_prs = Column(Integer, default=0)
    closed_prs = Column(Integer, default=0)
    total_rework = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now())
    
    # Cached metrics as JSON
    metrics = Column(JSON, default=dict)


class Reviewer(Base):
    __tablename__ = "reviewers"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    total_reviews = Column(Integer, default=0)
    approved_reviews = Column(Integer, default=0)
    changes_requested = Column(Integer, default=0)
    commented_reviews = Column(Integer, default=0)  # Reviews with COMMENTED state
    dismissed_reviews = Column(Integer, default=0)  # Reviews with DISMISSED state
    last_updated = Column(DateTime, default=func.now())
    
    # Cached metrics as JSON
    metrics = Column(JSON, default=dict)


class DomainMetrics(Base):
    __tablename__ = "domain_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True)
    total_tasks = Column(Integer, default=0)
    
    # Task state counts based on labels
    expert_review_pending = Column(Integer, default=0)
    calibrator_review_pending = Column(Integer, default=0)
    expert_approved = Column(Integer, default=0)
    ready_to_merge = Column(Integer, default=0)
    merged = Column(Integer, default=0)
    
    # Difficulty distribution
    expert_count = Column(Integer, default=0)
    hard_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    
    last_updated = Column(DateTime, default=func.now())
    
    # Cached detailed metrics as JSON
    detailed_metrics = Column(JSON, default=dict)

class User(Base):
    """
    All users: trainers, pod leads, calibrators, admins.
    Auto-created from PRs (trainers) and reviews (reviewers).
    Roles can be overridden via role mapping sheet.
    """
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True, index=True)
    github_username = Column(String, unique=True, nullable=False, index=True)
    name = Column(String)
    email = Column(String, unique=True, index=True)
    role = Column(String, index=True)  # 'admin', 'pod_lead', 'calibrator', 'trainer', NULL
    is_active = Column(Boolean, default=True)
    
    # Authentication (for future)
    password_hash = Column(String)
    auth_token = Column(String)
    last_login = Column(DateTime)
    
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())

class Domain(Base):
    """Work domains (finance, hr_payroll, smart_home, etc.)."""
    __tablename__ = "domains"
    
    id = Column(Integer, primary_key=True, index=True)
    domain_name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String)
    description = Column(Text)
    is_active = Column(Boolean, default=True, index=True)
    github_created_at = Column(DateTime(timezone=True), nullable=True)  # When domain was created on GitHub
    
    # Statistics
    total_tasks = Column(Integer, default=0)
    merged = Column(Integer, default=0)
    
    # Status counts (from labels)
    discarded = Column(Integer, default=0)
    expert_review_pending = Column(Integer, default=0)
    pending_review = Column(Integer, default=0)
    calibrator_review_pending = Column(Integer, default=0)
    needs_changes = Column(Integer, default=0)
    expert_approved = Column(Integer, default=0)
    good_task = Column(Integer, default=0)
    pod_lead_approved = Column(Integer, default=0)
    ready_to_merge = Column(Integer, default=0)
    resubmitted = Column(Integer, default=0)
    
    # Complexity
    expert_count = Column(Integer, default=0)
    hard_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    
    # Rework (from review events)
    total_rework = Column(Integer, default=0)
    
    detailed_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    interfaces = relationship("Interface", back_populates="domain", cascade="all, delete-orphan")


class Interface(Base):
    """Interfaces within domains (typically 1-5 per domain)."""
    __tablename__ = "interfaces"
    
    id = Column(Integer, primary_key=True, index=True)
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    interface_num = Column(Integer, nullable=False, index=True)
    name = Column(String)
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    
    # Statistics
    total_tasks = Column(Integer, default=0)
    merged = Column(Integer, default=0)
    
    # Status counts
    discarded = Column(Integer, default=0)
    expert_review_pending = Column(Integer, default=0)
    pending_review = Column(Integer, default=0)
    calibrator_review_pending = Column(Integer, default=0)
    needs_changes = Column(Integer, default=0)
    expert_approved = Column(Integer, default=0)
    good_task = Column(Integer, default=0)
    pod_lead_approved = Column(Integer, default=0)
    ready_to_merge = Column(Integer, default=0)
    resubmitted = Column(Integer, default=0)
    
    # Rework
    rework = Column(Integer, default=0)
    
    # Complexity - Merged
    merged_expert_count = Column(Integer, default=0)
    merged_hard_count = Column(Integer, default=0)
    merged_medium_count = Column(Integer, default=0)
    
    # Complexity - All statuses (non-merged)
    all_expert_count = Column(Integer, default=0)
    all_hard_count = Column(Integer, default=0)
    all_medium_count = Column(Integer, default=0)
    
    weekly_stats = Column(JSON, default=dict)
    detailed_metrics = Column(JSON, default=dict)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        UniqueConstraint('domain_id', 'interface_num', name='_domain_interface_uc'),
    )
    
    domain = relationship("Domain", back_populates="interfaces")
    # pull_requests = relationship("PullRequest", back_populates="interface")  # Commented out - PullRequest doesn't have this relationship

class InterfaceMetrics(Base):
    """DEPRECATED - For backward compatibility only."""
    __tablename__ = "interface_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    interface_num = Column(Integer, unique=True, index=True)
    total_tasks = Column(Integer, default=0)
    merged = Column(Integer, default=0)
    discarded = Column(Integer, default=0)
    expert_approved = Column(Integer, default=0)
    expert_review_pending = Column(Integer, default=0)
    pending_review = Column(Integer, default=0)
    pod_lead_approved = Column(Integer, default=0)
    ready_to_merge = Column(Integer, default=0)
    resubmitted = Column(Integer, default=0)
    good_task = Column(Integer, default=0)
    rework = Column(Integer, default=0)
    merged_expert_count = Column(Integer, default=0)
    merged_hard_count = Column(Integer, default=0)
    merged_medium_count = Column(Integer, default=0)
    all_expert_count = Column(Integer, default=0)
    all_hard_count = Column(Integer, default=0)
    all_medium_count = Column(Integer, default=0)
    weekly_stats = Column(JSON, default=dict)
    detailed_metrics = Column(JSON, default=dict)
    last_updated = Column(DateTime, default=func.now())


class Week(Base):
    """Weeks extracted from PR file changes."""
    __tablename__ = "weeks"
    
    id = Column(Integer, primary_key=True, index=True)
    week_name = Column(String, unique=True, nullable=False, index=True)
    week_num = Column(Integer, index=True)
    display_name = Column(String)
    start_date = Column(DateTime)
    end_date = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    # pull_requests = relationship("PullRequest", back_populates="week")  # Commented out - PullRequest doesn't have this relationship


class Pod(Base):
    """Pod entities extracted from PR file changes."""
    __tablename__ = "pods"
    
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    display_name = Column(String)
    pod_lead_id = Column(Integer, ForeignKey('users.id'))
    description = Column(Text)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())
    
    pod_lead = relationship("User", foreign_keys=[pod_lead_id])
    # pull_requests = relationship("PullRequest", back_populates="pod")  # Commented out - PullRequest doesn't have this relationship


class UserDomainAssignment(Base):
    """Users assigned to domains (auto or manual)."""
    __tablename__ = "user_domain_assignments"
    
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey('users.id', ondelete='CASCADE'), nullable=False, index=True)
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    assignment_type = Column(String, default='auto')
    assigned_by = Column(Integer, ForeignKey('users.id'))
    assigned_at = Column(DateTime, default=func.now())
    is_active = Column(Boolean, default=True)
    
    __table_args__ = (
        UniqueConstraint('user_id', 'domain_id', name='_user_domain_uc'),
    )


class SyncState(Base):
    __tablename__ = "sync_state"
    
    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime(timezone=True), nullable=True)
    last_full_sync_time = Column(DateTime(timezone=True), nullable=True)


class DeveloperHierarchy(Base):
    """
    Developer Hierarchy Table - Stores POD Lead and Calibrator mapping
    Data source: Google Sheets (merged from two sheets)
    Links to PullRequest via github_user <-> author_login
    """
    __tablename__ = "developer_hierarchy"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Identity fields
    github_user = Column(String, index=True, nullable=True)  # Links to PR.author_login (nullable for developers without GitHub)
    turing_email = Column(String, unique=True, index=True, nullable=False)  # Primary identifier
    
    # Role information
    role = Column(String, index=True)  # Trainer, POD Lead, Calibrator, etc.
    status = Column(String, index=True)  # Active, Inactive, etc. (from Google Sheets)
    
    # Hierarchy fields (transformed from Google Sheets)
    pod_lead_email = Column(String, index=True, nullable=True)
    calibrator_email = Column(String, index=True, nullable=True)
    
    # Metadata
    last_synced = Column(DateTime, default=func.now(), onupdate=func.now())
    created_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_hierarchy_github_user', 'github_user'),
        Index('idx_hierarchy_pod_lead', 'pod_lead_email'),
        Index('idx_hierarchy_calibrator', 'calibrator_email'),
    )



def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db():
    """
    Create all database tables.
    Note: This creates base tables. Additional migrations (like hierarchy columns)
    are handled by db_migrations.py which runs automatically on startup.
    """
    Base.metadata.create_all(bind=engine)

