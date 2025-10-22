"""
Sync state management to track when we last synced
"""
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from sqlalchemy import func
from database import PullRequest, SyncState

def update_last_sync_time(db: Session):
    """
    Update the last sync time in the database.
    """
    sync_state = db.query(SyncState).first()
    if not sync_state:
        sync_state = SyncState(last_sync_time=datetime.now(timezone.utc))
        db.add(sync_state)
    else:
        sync_state.last_sync_time = datetime.now(timezone.utc)
    db.commit()

def get_last_sync_time(db: Session) -> datetime:
    """
    Get the last sync time from the SyncState table.
    If no sync state exists, return default time (60 days ago).
    Always returns timezone-aware datetime.
    """
    try:
        sync_state = db.query(SyncState).first()
        if sync_state and sync_state.last_sync_time:
            last_sync = sync_state.last_sync_time
            # Ensure timezone-aware
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            return last_sync
        
        # Fallback: check most recent PR in database
        last_pr = db.query(PullRequest).order_by(
            PullRequest.last_synced.desc()
        ).first()
        
        if last_pr and last_pr.last_synced:
            last_synced = last_pr.last_synced
            if last_synced.tzinfo is None:
                last_synced = last_synced.replace(tzinfo=timezone.utc)
            return last_synced
        
        if last_pr and last_pr.updated_at:
            updated_at = last_pr.updated_at
            if updated_at.tzinfo is None:
                updated_at = updated_at.replace(tzinfo=timezone.utc)
            return updated_at
            
        # Default: 60 days ago for first sync
        return datetime.now(timezone.utc) - timedelta(days=60)
    except Exception:
        return datetime.now(timezone.utc) - timedelta(days=60)

def should_do_full_sync(db: Session, full_sync_days: int = 60) -> bool:
    """
    Determine if we should do a full sync or incremental update.
    
    Returns True if:
    - No sync state exists (first sync)
    - Last sync was more than 7 days ago
    """
    try:
        sync_state = db.query(SyncState).first()
        
        # No sync state = first sync
        if not sync_state or not sync_state.last_sync_time:
            return True
        
        # Handle timezone-naive datetime from database
        last_sync = sync_state.last_sync_time
        if last_sync.tzinfo is None:
            last_sync = last_sync.replace(tzinfo=timezone.utc)
        
        # If last sync was more than 7 days ago, do full sync
        time_since_sync = datetime.now(timezone.utc) - last_sync
        days_since_sync = time_since_sync.days
        
        if days_since_sync > 7:
            return True
        
        return False  # Do incremental sync
        
    except Exception:
        return True  # On error, do full sync to be safe

def get_sync_description(db: Session, full_sync_days: int = 60) -> str:
    """Get a human-readable description of what kind of sync will happen."""
    sync_state = db.query(SyncState).first()
    
    if should_do_full_sync(db, full_sync_days):
        # Check if we have existing PRs to determine if truly initial or just full
        pr_count = db.query(func.count(PullRequest.id)).scalar()
        
        if not sync_state or not sync_state.last_sync_time:
            if pr_count == 0:
                return f"Initial sync - fetching last {full_sync_days} days"
            else:
                return f"Full sync - fetching last {full_sync_days} days (no sync tracking yet)"
        else:
            return f"Full sync - fetching last {full_sync_days} days (last sync was over 7 days ago)"
    else:
        if sync_state and sync_state.last_sync_time:
            # Handle timezone-naive datetime from database
            last_sync = sync_state.last_sync_time
            if last_sync.tzinfo is None:
                last_sync = last_sync.replace(tzinfo=timezone.utc)
            
            hours_ago = (datetime.now(timezone.utc) - last_sync).total_seconds() / 3600
            if hours_ago < 1:
                minutes = int(hours_ago * 60)
                return f"Incremental sync - fetching updates from last {minutes} minute{'s' if minutes != 1 else ''}"
            elif hours_ago < 24:
                hours = int(hours_ago)
                return f"Incremental sync - fetching updates from last {hours} hour{'s' if hours != 1 else ''}"
            else:
                days = int(hours_ago / 24)
                return f"Incremental sync - fetching updates from last {days} day{'s' if days != 1 else ''}"
        return "Incremental sync - fetching recent updates"
