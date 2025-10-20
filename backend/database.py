"""
TAU Dashboard Database Models
New structure with users, domains, interfaces, weeks, pods, and proper relationships.
"""
from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session, relationship
from sqlalchemy.sql import func
from datetime import datetime
from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# ============================================================================
# CORE ENTITIES
# ============================================================================

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
    pull_requests = relationship("PullRequest", back_populates="interface")


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
    
    pull_requests = relationship("PullRequest", back_populates="week")


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
    pull_requests = relationship("PullRequest", back_populates="pod")


# ============================================================================
# PULL REQUESTS AND REVIEWS
# ============================================================================

class PullRequest(Base):
    """Pull requests/tasks with full relationship tracking."""
    __tablename__ = "pull_requests"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, nullable=False, index=True)
    number = Column(Integer, nullable=False, index=True)
    title = Column(String, nullable=False)
    state = Column(String, nullable=False, index=True)  # From GitHub API
    merged = Column(Boolean, default=False, index=True)  # From GitHub API
    
    # Relationships (NEW)
    trainer_id = Column(Integer, ForeignKey('users.id'), index=True)
    domain_id = Column(Integer, ForeignKey('domains.id'), index=True)
    interface_id = Column(Integer, ForeignKey('interfaces.id'), index=True)
    week_id = Column(Integer, ForeignKey('weeks.id'), index=True)
    pod_id = Column(Integer, ForeignKey('pods.id'), index=True)
    
    # Quick access fields (from PR title)
    trainer_name = Column(String, index=True)
    domain = Column(String, index=True)
    interface_num = Column(Integer, index=True)
    complexity = Column(String, nullable=False, index=True)
    timestamp = Column(String)
    
    # Week/Pod info (from PR file changes)
    week_num = Column(Integer, index=True)
    week_name = Column(String, index=True)
    pod_name = Column(String, index=True)
    
    # Legacy compatibility
    developer_username = Column(String, index=True)
    difficulty = Column(String, index=True)
    task_id = Column(String, index=True)
    
    # GitHub data
    author_login = Column(String, index=True)  # Links to DeveloperHierarchy.github_user
    author_email = Column(String, nullable=True)  # Fetched from GitHub API

    created_at = Column(DateTime, index=True)
    updated_at = Column(DateTime)
    closed_at = Column(DateTime)
    merged_at = Column(DateTime)
    
    # Labels from GitHub
    labels = Column(JSON, default=list)
    
    # Metrics
    review_count = Column(Integer, default=0)
    comment_count = Column(Integer, default=0)
    rework_count = Column(Integer, default=0)  # From CHANGES_REQUESTED reviews
    check_failures = Column(Integer, default=0)
    last_synced = Column(DateTime, default=func.now())
    
    # Relationships
    trainer = relationship("User", foreign_keys=[trainer_id])
    domain_obj = relationship("Domain", foreign_keys=[domain_id])
    interface = relationship("Interface", back_populates="pull_requests")
    week = relationship("Week", back_populates="pull_requests")
    pod = relationship("Pod", back_populates="pull_requests")
    reviews = relationship("Review", back_populates="pull_request", cascade="all, delete-orphan")
    check_runs = relationship("CheckRun", back_populates="pull_request", cascade="all, delete-orphan")


class Review(Base):
    """Review records."""
    __tablename__ = "reviews"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, index=True)
    pull_request_id = Column(Integer, ForeignKey('pull_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    reviewer_id = Column(Integer, ForeignKey('users.id'), index=True)
    reviewer_login = Column(String, index=True)
    state = Column(String, nullable=False, index=True)
    submitted_at = Column(DateTime)
    body = Column(Text)
    
    pull_request = relationship("PullRequest", back_populates="reviews")
    reviewer = relationship("User", foreign_keys=[reviewer_id])


class CheckRun(Base):
    """CI/CD check runs."""
    __tablename__ = "check_runs"
    
    id = Column(Integer, primary_key=True, index=True)
    github_id = Column(BigInteger, unique=True, index=True)
    pull_request_id = Column(Integer, ForeignKey('pull_requests.id', ondelete='CASCADE'), nullable=False, index=True)
    name = Column(String)
    status = Column(String)
    conclusion = Column(String, index=True)
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    
    pull_request = relationship("PullRequest", back_populates="check_runs")


# ============================================================================
# JUNCTION/MAPPING TABLES
# ============================================================================

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


class RoleMappingSheet(Base):
    """Role mapping from external sheet to override default roles."""
    __tablename__ = "role_mapping_sheet"
    
    id = Column(Integer, primary_key=True, index=True)
    github_username = Column(String, unique=True, nullable=False, index=True)
    role = Column(String, nullable=False)
    imported_at = Column(DateTime, default=func.now())
    last_updated = Column(DateTime, default=func.now(), onupdate=func.now())


# ============================================================================
# LEGACY COMPATIBILITY (for gradual transition)
# ============================================================================

class Developer(Base):
    """DEPRECATED - For backward compatibility only."""
    __tablename__ = "developers"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    github_login = Column(String, index=True)
    total_prs = Column(Integer, default=0)
    open_prs = Column(Integer, default=0)
    merged_prs = Column(Integer, default=0)
    total_rework = Column(Integer, default=0)
    total_check_failures = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now())
    metrics = Column(JSON, default=dict)


class Reviewer(Base):
    """DEPRECATED - For backward compatibility only."""
    __tablename__ = "reviewers"
    
    id = Column(Integer, primary_key=True, index=True)
    username = Column(String, unique=True, index=True)
    total_reviews = Column(Integer, default=0)
    approved_reviews = Column(Integer, default=0)
    changes_requested = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now())
    metrics = Column(JSON, default=dict)


class DomainMetrics(Base):
    """DEPRECATED - For backward compatibility only."""
    __tablename__ = "domain_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, unique=True, index=True)
    total_tasks = Column(Integer, default=0)
    expert_review_pending = Column(Integer, default=0)
    calibrator_review_pending = Column(Integer, default=0)
    expert_approved = Column(Integer, default=0)
    ready_to_merge = Column(Integer, default=0)
    merged = Column(Integer, default=0)
    expert_count = Column(Integer, default=0)
    hard_count = Column(Integer, default=0)
    medium_count = Column(Integer, default=0)
    last_updated = Column(DateTime, default=func.now())
    detailed_metrics = Column(JSON, default=dict)


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


# ============================================================================
# SYSTEM TABLES
# ============================================================================

class SyncState(Base):
    """Sync history tracking."""
    __tablename__ = "sync_state"
    
    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime(timezone=True))  # Store with timezone
    last_full_sync_time = Column(DateTime(timezone=True))  # Store with timezone
    total_prs_synced = Column(Integer, default=0)
    total_users_created = Column(Integer, default=0)
    total_domains_created = Column(Integer, default=0)
    total_interfaces_created = Column(Integer, default=0)
    last_sync_pr_count = Column(Integer, default=0)
    last_sync_duration = Column(Integer, default=0)
    sync_type = Column(String)
    last_sync_status = Column(String, default='success')
    last_error = Column(Text)
    created_at = Column(DateTime, default=func.now())
    updated_at = Column(DateTime, default=func.now(), onupdate=func.now())


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
