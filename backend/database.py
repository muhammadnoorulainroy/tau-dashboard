from sqlalchemy import create_engine, Column, Integer, BigInteger, String, DateTime, Boolean, Text, JSON, ForeignKey, Index
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
    reviewer_login = Column(String, index=True)
    state = Column(String)  # APPROVED, CHANGES_REQUESTED, COMMENTED, DISMISSED
    submitted_at = Column(DateTime)
    body = Column(Text, nullable=True)
    
    pull_request = relationship("PullRequest", back_populates="reviews")
    
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


class SyncState(Base):
    __tablename__ = "sync_state"
    
    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime, nullable=True)
    last_full_sync_time = Column(DateTime, nullable=True)


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

