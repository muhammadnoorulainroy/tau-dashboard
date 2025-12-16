"""
Database models for Task Agent API integration (v2)
Replaces GitHub-based PullRequest model with Task Agent Task model
"""
from sqlalchemy import (
    create_engine, Column, Integer, String, DateTime, Boolean, 
    Text, JSON, ForeignKey, Index, UniqueConstraint, Float, ARRAY
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from sqlalchemy.sql import func
from datetime import datetime
from config import settings

engine = create_engine(settings.database_url)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


# =============================================================================
# TASK AGENT MODELS (New - replacing GitHub PR models)
# =============================================================================

class Task(Base):
    """
    Task from Task Agent API
    Maps to: GET /api/tasks and GET /api/tasks/{task_id}
    """
    __tablename__ = "tasks"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Task Agent identifiers
    task_agent_id = Column(String, unique=True, nullable=False, index=True)  # "task_20251205_082251_950_a46708ce_290b1b31"
    
    # Core task fields
    description = Column(Text, nullable=True)
    difficulty = Column(String, index=True)  # medium, hard, expert
    status = Column(String, index=True)  # draft, pending_review, in_expert_review, etc.
    
    # Domain and Interface (from tau_metadata)
    domain = Column(String, index=True)  # from tau_metadata.environment
    interface_num = Column(Integer, nullable=True, index=True)  # from tau_metadata.interface
    
    # Trainer (task creator)
    trainer_id = Column(String, index=True)  # UUID from Task Agent
    trainer_name = Column(String, nullable=True)
    trainer_email = Column(String, nullable=True, index=True)
    
    # Reviewer (calibrator)
    reviewer_id = Column(String, nullable=True)
    reviewer_name = Column(String, nullable=True)
    reviewer_email = Column(String, nullable=True)
    
    # Expert Reviewer
    expert_reviewer_id = Column(String, nullable=True)
    expert_reviewer_name = Column(String, nullable=True)
    expert_reviewer_email = Column(String, nullable=True)
    
    # Pod Lead
    pod_lead_id = Column(String, nullable=True)
    pod_lead_name = Column(String, nullable=True)
    pod_lead_email = Column(String, nullable=True)
    
    # Batch info
    batch_id = Column(String, nullable=True, index=True)
    batch_name = Column(String, nullable=True)
    batch_status = Column(String, nullable=True)  # inprogress, delivered
    batch_is_locked = Column(Boolean, default=False)
    
    # Metrics
    rework_count = Column(Integer, default=0)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True), nullable=True)  # When status = approved
    
    # Content for similarity analysis
    instruction_text = Column(Text, nullable=True)  # from scenarios[0].prompts[0].prompt_text
    tool_sequence = Column(JSON, nullable=True)  # Action graph JSON
    tools = Column(JSON, nullable=True)  # Array of tool calls
    
    # Rework attribution (who sent this task to rework - extracted from task_history)
    rework_by_name = Column(String, nullable=True)  # Name of person who sent to rework
    rework_by_email = Column(String, nullable=True)  # Email of person who sent to rework
    rework_by_role = Column(String, nullable=True)  # Role: pod_lead, calibrator, expert_reviewer
    
    # Full metadata storage
    tau_metadata = Column(JSON, nullable=True)  # Full tau_metadata object
    scenarios = Column(JSON, nullable=True)  # Full scenarios array
    task_history = Column(JSON, nullable=True)  # Full task history for audit trail
    
    # Sync tracking
    last_synced = Column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        Index('idx_task_domain_status', 'domain', 'status'),
        Index('idx_task_trainer', 'trainer_email'),
        Index('idx_task_created', 'created_at'),
        Index('idx_task_batch', 'batch_id'),
    )


class TaskAgentUser(Base):
    """
    User from Task Agent API
    Maps to: GET /api/admin/users
    """
    __tablename__ = "task_agent_users"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Task Agent identifier
    user_agent_id = Column(String, unique=True, nullable=False, index=True)  # UUID from Task Agent
    
    # User info
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=True)
    is_active = Column(Boolean, default=True)
    
    # Roles (array of strings: trainer, admin, pod_lead, expert_reviewer, reviewer)
    roles = Column(JSON, default=list)
    
    # Profile
    avatar_url = Column(String, nullable=True)
    auth_method = Column(String, nullable=True)  # google_oauth, both, email_otp
    
    # Stats from Task Agent
    login_count = Column(Integer, default=0)
    last_login_at = Column(DateTime(timezone=True), nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=True)
    last_synced = Column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        Index('idx_user_email', 'email'),
        Index('idx_user_active', 'is_active'),
    )


class Batch(Base):
    """
    Batch from Task Agent API
    Maps to: GET /api/batches
    """
    __tablename__ = "batches"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Task Agent identifier
    batch_agent_id = Column(String, unique=True, nullable=False, index=True)  # UUID from Task Agent
    
    # Batch info
    batch_name = Column(String, nullable=False, index=True)
    environment = Column(String, index=True)  # Domain name (confluence_wiki, etc.)
    description = Column(Text, nullable=True)
    
    # Status
    status = Column(String, index=True)  # inprogress, delivered
    is_locked = Column(Boolean, default=False)
    is_exported = Column(Boolean, default=False)
    
    # Counts
    task_count = Column(Integer, default=0)
    
    # Author
    author = Column(String, nullable=True)
    
    # Timestamps
    date_opened = Column(DateTime(timezone=True))
    date_closed = Column(DateTime(timezone=True), nullable=True)
    exported_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True))
    updated_at = Column(DateTime(timezone=True), nullable=True)
    last_synced = Column(DateTime(timezone=True), default=func.now())


class Environment(Base):
    """
    Environment/Domain from Task Agent API
    Maps to: GET /api/tau-env/environments
    """
    __tablename__ = "environments"
    
    id = Column(Integer, primary_key=True, index=True)
    
    name = Column(String, unique=True, nullable=False, index=True)  # confluence_wiki, etc.
    description = Column(Text, nullable=True)
    data_path_exists = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)
    
    # Computed stats (updated during sync) - All individual statuses
    total_tasks = Column(Integer, default=0)
    
    # Individual status counts (matching Task Agent API statuses)
    draft_count = Column(Integer, default=0)
    pending_review_count = Column(Integer, default=0)
    in_expert_review_count = Column(Integer, default=0)
    pending_calibrator_review_count = Column(Integer, default=0)
    in_calibrator_review_count = Column(Integer, default=0)
    in_pod_lead_review_count = Column(Integer, default=0)
    rework_count = Column(Integer, default=0)
    approved_count = Column(Integer, default=0)
    
    # Complexity breakdown for approved tasks
    approved_expert = Column(Integer, default=0)
    approved_hard = Column(Integer, default=0)
    approved_medium = Column(Integer, default=0)
    
    # Complexity breakdown for all tasks
    total_expert = Column(Integer, default=0)
    total_hard = Column(Integer, default=0)
    total_medium = Column(Integer, default=0)
    
    last_synced = Column(DateTime(timezone=True), default=func.now())


# =============================================================================
# SIMILARITY MODELS (Keep existing, update references)
# =============================================================================

class TaskEmbedding(Base):
    """
    Stores embeddings for task instructions (for similarity calculations)
    Updated to reference Task instead of PullRequest
    """
    __tablename__ = "task_embeddings_v2"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)
    embedding = Column(ARRAY(Float), nullable=False)
    model_name = Column(String, default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=func.now())


class TaskSimilarity(Base):
    """
    Stores pairwise cosine similarity scores between tasks
    Updated to reference Task instead of PullRequest
    """
    __tablename__ = "task_similarities_v2"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True, nullable=False)
    task_id_1 = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    task_id_2 = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    calculated_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_sim_domain_tasks', 'domain', 'task_id_1', 'task_id_2'),
        UniqueConstraint('task_id_1', 'task_id_2', name='uq_task_pair_v2'),
    )


class ActionEmbedding(Base):
    """
    Stores embeddings for task action sequences (tool calls)
    Updated to reference Task instead of PullRequest
    """
    __tablename__ = "action_embeddings_v2"
    
    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("tasks.id"), unique=True, nullable=False, index=True)
    embedding = Column(ARRAY(Float), nullable=False)
    action_sequence = Column(Text, nullable=True)
    tool_count = Column(Integer, default=0)
    unique_tools = Column(JSON, default=list)
    model_name = Column(String, default="all-MiniLM-L6-v2")
    created_at = Column(DateTime, default=func.now())


class ActionSimilarity(Base):
    """
    Stores pairwise cosine similarity scores between task action sequences
    Updated to reference Task instead of PullRequest
    """
    __tablename__ = "action_similarities_v2"
    
    id = Column(Integer, primary_key=True, index=True)
    domain = Column(String, index=True, nullable=False)
    task_id_1 = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    task_id_2 = Column(Integer, ForeignKey("tasks.id"), nullable=False)
    similarity_score = Column(Float, nullable=False)
    calculated_at = Column(DateTime, default=func.now())
    
    __table_args__ = (
        Index('idx_action_sim_domain_tasks', 'domain', 'task_id_1', 'task_id_2'),
        UniqueConstraint('task_id_1', 'task_id_2', name='uq_action_task_pair_v2'),
    )


# =============================================================================
# JIBBLE TIME TRACKING MODELS
# =============================================================================

class JibblePerson(Base):
    """
    Person/Employee from Jibble API
    Maps to: GET /People
    """
    __tablename__ = "jibble_people"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Jibble identifiers
    jibble_id = Column(String, unique=True, nullable=False, index=True)
    
    # Personal info
    full_name = Column(String, nullable=True)
    first_name = Column(String, nullable=True)
    last_name = Column(String, nullable=True)
    personal_email = Column(String, nullable=True, index=True)  # Jibble personal email
    work_email = Column(String, nullable=True, index=True)
    
    # Status
    status = Column(String, nullable=True)  # Active, etc.
    
    # Latest activity
    latest_time_entry = Column(DateTime(timezone=True), nullable=True)
    
    # Sync tracking
    last_synced = Column(DateTime(timezone=True), default=func.now())


class JibbleTimeEntry(Base):
    """
    Daily time entry summary for a person
    Aggregated from TimeEntries endpoint
    """
    __tablename__ = "jibble_time_entries"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Person reference
    person_id = Column(String, index=True, nullable=False)  # Jibble person ID
    
    # Date
    entry_date = Column(DateTime(timezone=True), nullable=False, index=True)
    
    # Time data
    total_hours = Column(Float, default=0.0)
    clock_in_time = Column(DateTime(timezone=True), nullable=True)
    clock_out_time = Column(DateTime(timezone=True), nullable=True)
    
    # Sync tracking
    last_synced = Column(DateTime(timezone=True), default=func.now())
    
    __table_args__ = (
        UniqueConstraint('person_id', 'entry_date', name='uq_jibble_person_date'),
        Index('idx_jibble_time_person_date', 'person_id', 'entry_date'),
    )


class JibbleEmailMapping(Base):
    """
    Stores the mapping between Turing email and Jibble personal email from Google Sheets.
    """
    __tablename__ = "jibble_email_mappings"
    
    id = Column(Integer, primary_key=True, index=True)
    turing_email = Column(String, unique=True, nullable=False, index=True)
    jibble_email = Column(String, nullable=False, index=True)
    last_synced = Column(DateTime(timezone=True), default=func.now())


# =============================================================================
# SYNC STATE
# =============================================================================

class SyncStateV2(Base):
    """Track sync state for Task Agent API"""
    __tablename__ = "sync_state_v2"
    
    id = Column(Integer, primary_key=True, index=True)
    last_sync_time = Column(DateTime(timezone=True), nullable=True)
    last_full_sync_time = Column(DateTime(timezone=True), nullable=True)
    tasks_synced = Column(Integer, default=0)
    users_synced = Column(Integer, default=0)
    batches_synced = Column(Integer, default=0)


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db_v2():
    """Create all v2 database tables and run migrations."""
    Base.metadata.create_all(bind=engine)
    
    # Run column migrations for existing tables
    _run_migrations()


def _run_migrations():
    """Add any missing columns to existing tables."""
    from sqlalchemy import text
    
    with engine.connect() as conn:
        # Check if rework attribution columns exist
        result = conn.execute(text("""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name = 'tasks' AND column_name = 'rework_by_name'
        """))
        
        if result.fetchone() is None:
            print('Migration: Adding rework attribution columns to tasks table...')
            conn.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS rework_by_name VARCHAR'))
            conn.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS rework_by_email VARCHAR'))
            conn.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS rework_by_role VARCHAR'))
            conn.execute(text('ALTER TABLE tasks ADD COLUMN IF NOT EXISTS task_history JSONB'))
            conn.commit()
            print('Migration: Rework columns added successfully')


# All valid task statuses from Task Agent API
TASK_STATUSES = [
    'draft',                      # Task created, not submitted
    'pending_review',             # Submitted, waiting for first review
    'in_expert_review',           # Being reviewed by expert reviewer
    'pending_calibrator_review',  # Passed expert review, waiting for calibrator
    'in_calibrator_review',       # Being reviewed by calibrator
    'in_pod_lead_review',         # Being reviewed by pod lead (final review)
    'rework',                     # Sent back for revisions
    'approved',                   # Fully approved, ready for delivery
]


def is_in_review(status: str) -> bool:
    """Check if status is any review stage (not draft, rework, or approved)"""
    return status in [
        'pending_review',
        'in_expert_review', 
        'pending_calibrator_review',
        'in_calibrator_review',
        'in_pod_lead_review'
    ]


def is_terminal_status(status: str) -> bool:
    """Check if status is a terminal state (approved or rework)"""
    return status in ['approved', 'rework']

