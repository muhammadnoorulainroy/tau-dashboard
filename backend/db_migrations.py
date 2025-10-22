"""
Database Migrations - Automatically run on startup
"""
import logging
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session
from database import engine

logger = logging.getLogger(__name__)

def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table"""
    inspector = inspect(engine)
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    return column_name in columns

def index_exists(table_name: str, index_name: str) -> bool:
    """Check if an index exists for a table"""
    inspector = inspect(engine)
    indexes = [idx['name'] for idx in inspector.get_indexes(table_name)]
    return index_name in indexes

def remove_old_hierarchy_columns():
    """
    Remove old pod_lead_email and calibrator_email columns from pull_requests table
    These were replaced by the DeveloperHierarchy table (proper normalization)
    """
    try:
        logger.info("Checking for old hierarchy columns in pull_requests...")
        
        with engine.connect() as connection:
            # Remove pod_lead_email column if it exists
            if column_exists('pull_requests', 'pod_lead_email'):
                logger.info("Removing old pod_lead_email column from pull_requests...")
                connection.execute(text(
                    "ALTER TABLE pull_requests DROP COLUMN IF EXISTS pod_lead_email"
                ))
                connection.commit()
                logger.info("✓ Removed old pod_lead_email column")
            
            # Remove calibrator_email column if it exists
            if column_exists('pull_requests', 'calibrator_email'):
                logger.info("Removing old calibrator_email column from pull_requests...")
                connection.execute(text(
                    "ALTER TABLE pull_requests DROP COLUMN IF EXISTS calibrator_email"
                ))
                connection.commit()
                logger.info("✓ Removed old calibrator_email column")
            
            # Drop old indices if they exist
            connection.execute(text("DROP INDEX IF EXISTS idx_pr_pod_lead"))
            connection.execute(text("DROP INDEX IF EXISTS idx_pr_calibrator"))
            connection.commit()
            logger.info("✓ Cleaned up old indices")
        
        logger.info("✅ Old hierarchy columns cleaned up")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️  Could not remove old columns (may not exist): {e}")
        return True  # Not a critical error

def add_status_column():
    """
    Add status column to developer_hierarchy table
    """
    try:
        logger.info("Checking for status column in developer_hierarchy...")
        
        if not column_exists('developer_hierarchy', 'status'):
            logger.info("Adding status column to developer_hierarchy...")
            with engine.connect() as connection:
                connection.execute(text(
                    "ALTER TABLE developer_hierarchy ADD COLUMN status VARCHAR"
                ))
                connection.commit()
                
                # Create index on status for faster filtering
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_developer_hierarchy_status ON developer_hierarchy(status)"
                ))
                connection.commit()
                
            logger.info("✓ Added status column to developer_hierarchy")
            return True
        else:
            logger.info("✓ Status column already exists")
            return False
            
    except Exception as e:
        logger.warning(f"⚠️  Could not add status column: {e}")
        return False

def allow_null_github_user():
    """
    Make github_user column nullable and remove unique constraint
    This allows including developers who don't have GitHub accounts yet
    """
    try:
        logger.info("Updating github_user column to allow NULL values...")
        
        with engine.connect() as connection:
            # Drop unique constraint on github_user if it exists
            try:
                connection.execute(text(
                    "ALTER TABLE developer_hierarchy DROP CONSTRAINT IF EXISTS ix_developer_hierarchy_github_user"
                ))
                connection.commit()
                logger.info("✓ Dropped unique constraint on github_user")
            except Exception as e:
                logger.info(f"  Unique constraint may not exist: {e}")
            
            # Make github_user nullable
            try:
                connection.execute(text(
                    "ALTER TABLE developer_hierarchy ALTER COLUMN github_user DROP NOT NULL"
                ))
                connection.commit()
                logger.info("✓ Made github_user nullable")
            except Exception as e:
                logger.info(f"  Column may already be nullable: {e}")
            
            # Recreate index as non-unique (allows duplicates/nulls)
            connection.execute(text(
                "DROP INDEX IF EXISTS idx_hierarchy_github_user"
            ))
            connection.execute(text(
                "CREATE INDEX IF NOT EXISTS idx_hierarchy_github_user ON developer_hierarchy(github_user) WHERE github_user IS NOT NULL"
            ))
            connection.commit()
            logger.info("✓ Recreated github_user index (non-unique, partial)")
        
        logger.info("✅ github_user column now allows NULL values")
        return True
        
    except Exception as e:
        logger.warning(f"⚠️  Could not update github_user column: {e}")
        return False

def add_users_table_columns():
    """
    Add missing columns to users table
    """
    try:
        logger.info("Checking for missing users table columns...")
        
        with engine.connect() as connection:
            if not column_exists('users', 'name'):
                logger.info("Adding name column to users...")
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN name VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added name column")
            
            if not column_exists('users', 'is_active'):
                logger.info("Adding is_active column to users...")
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT TRUE"
                ))
                connection.commit()
                logger.info("✓ Added is_active column")
            
            if not column_exists('users', 'password_hash'):
                logger.info("Adding password_hash column to users...")
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN password_hash VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added password_hash column")
            
            if not column_exists('users', 'auth_token'):
                logger.info("Adding auth_token column to users...")
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN auth_token VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added auth_token column")
            
            if not column_exists('users', 'last_login'):
                logger.info("Adding last_login column to users...")
                connection.execute(text(
                    "ALTER TABLE users ADD COLUMN last_login TIMESTAMP"
                ))
                connection.commit()
                logger.info("✓ Added last_login column")
        
        logger.info("✅ users table columns updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding users table columns: {e}")
        return False

def add_reviews_reviewer_id():
    """
    Add reviewer_id column to reviews table
    """
    try:
        logger.info("Checking for reviewer_id column in reviews table...")
        
        with engine.connect() as connection:
            if not column_exists('reviews', 'reviewer_id'):
                logger.info("Adding reviewer_id column to reviews...")
                connection.execute(text(
                    "ALTER TABLE reviews ADD COLUMN reviewer_id INTEGER"
                ))
                
                # Add index for performance
                connection.execute(text(
                    "CREATE INDEX IF NOT EXISTS idx_reviews_reviewer_id ON reviews(reviewer_id)"
                ))
                
                connection.commit()
                logger.info("✓ Added reviewer_id column and index")
            else:
                logger.info("✓ Column reviews.reviewer_id already exists")
        
        logger.info("✅ reviews table updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding reviewer_id to reviews: {e}")
        return False

def add_developer_closed_prs():
    """
    Add closed_prs column to developers table
    """
    try:
        logger.info("Checking for closed_prs column in developers table...")
        
        with engine.connect() as connection:
            if not column_exists('developers', 'closed_prs'):
                logger.info("Adding closed_prs column to developers...")
                connection.execute(text(
                    "ALTER TABLE developers ADD COLUMN closed_prs INTEGER DEFAULT 0"
                ))
                
                connection.commit()
                logger.info("✓ Added closed_prs column")
            else:
                logger.info("✓ Column developers.closed_prs already exists")
        
        logger.info("✅ developers table updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding closed_prs to developers: {e}")
        return False

def add_sync_state_columns():
    """
    Add new tracking columns to sync_state table
    """
    try:
        logger.info("Checking for new sync_state columns...")
        
        with engine.connect() as connection:
            if not column_exists('sync_state', 'total_prs_synced'):
                logger.info("Adding total_prs_synced column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN total_prs_synced INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added total_prs_synced column")
            
            if not column_exists('sync_state', 'total_users_created'):
                logger.info("Adding total_users_created column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN total_users_created INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added total_users_created column")
            
            if not column_exists('sync_state', 'total_domains_created'):
                logger.info("Adding total_domains_created column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN total_domains_created INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added total_domains_created column")
            
            if not column_exists('sync_state', 'total_interfaces_created'):
                logger.info("Adding total_interfaces_created column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN total_interfaces_created INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added total_interfaces_created column")
            
            if not column_exists('sync_state', 'last_sync_pr_count'):
                logger.info("Adding last_sync_pr_count column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN last_sync_pr_count INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added last_sync_pr_count column")
            
            if not column_exists('sync_state', 'last_sync_duration'):
                logger.info("Adding last_sync_duration column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN last_sync_duration INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added last_sync_duration column")
            
            if not column_exists('sync_state', 'sync_type'):
                logger.info("Adding sync_type column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN sync_type VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added sync_type column")
            
            if not column_exists('sync_state', 'last_sync_status'):
                logger.info("Adding last_sync_status column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN last_sync_status VARCHAR DEFAULT 'success'"
                ))
                connection.commit()
                logger.info("✓ Added last_sync_status column")
            
            if not column_exists('sync_state', 'last_error'):
                logger.info("Adding last_error column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN last_error TEXT"
                ))
                connection.commit()
                logger.info("✓ Added last_error column")
            
            if not column_exists('sync_state', 'created_at'):
                logger.info("Adding created_at column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ))
                connection.commit()
                logger.info("✓ Added created_at column")
            
            if not column_exists('sync_state', 'updated_at'):
                logger.info("Adding updated_at column...")
                connection.execute(text(
                    "ALTER TABLE sync_state ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP"
                ))
                connection.commit()
                logger.info("✓ Added updated_at column")
        
        logger.info("✅ sync_state columns updated successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding sync_state columns: {e}")
        return False

def add_developer_check_failures():
    """
    Add total_check_failures column to developers table
    """
    try:
        logger.info("Checking for total_check_failures column in developers table...")
        
        if not column_exists('developers', 'total_check_failures'):
            logger.info("Adding total_check_failures column to developers...")
            with engine.connect() as connection:
                connection.execute(text(
                    "ALTER TABLE developers ADD COLUMN total_check_failures INTEGER DEFAULT 0"
                ))
                connection.commit()
                logger.info("✓ Added total_check_failures column")
        else:
            logger.info("✓ total_check_failures column already exists")
        
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding total_check_failures column: {e}")
        return False

def add_new_pr_columns():
    """
    Add new relationship and metadata columns to pull_requests table
    These support the new normalized schema with proper relationships
    """
    try:
        logger.info("Checking for new pull_requests columns...")
        
        with engine.connect() as connection:
            # Add relationship columns
            if not column_exists('pull_requests', 'trainer_id'):
                logger.info("Adding trainer_id column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN trainer_id INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added trainer_id column")
            
            if not column_exists('pull_requests', 'domain_id'):
                logger.info("Adding domain_id column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN domain_id INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added domain_id column")
            
            if not column_exists('pull_requests', 'interface_id'):
                logger.info("Adding interface_id column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN interface_id INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added interface_id column")
            
            if not column_exists('pull_requests', 'week_id'):
                logger.info("Adding week_id column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN week_id INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added week_id column")
            
            if not column_exists('pull_requests', 'pod_id'):
                logger.info("Adding pod_id column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN pod_id INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added pod_id column")
            
            # Add quick access fields
            if not column_exists('pull_requests', 'trainer_name'):
                logger.info("Adding trainer_name column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN trainer_name VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added trainer_name column")
            
            if not column_exists('pull_requests', 'interface_num'):
                logger.info("Adding interface_num column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN interface_num INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added interface_num column")
            
            if not column_exists('pull_requests', 'complexity'):
                logger.info("Adding complexity column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN complexity VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added complexity column")
            
            if not column_exists('pull_requests', 'timestamp'):
                logger.info("Adding timestamp column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN timestamp VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added timestamp column")
            
            # Add week/pod info fields
            if not column_exists('pull_requests', 'week_num'):
                logger.info("Adding week_num column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN week_num INTEGER"
                ))
                connection.commit()
                logger.info("✓ Added week_num column")
            
            if not column_exists('pull_requests', 'week_name'):
                logger.info("Adding week_name column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN week_name VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added week_name column")
            
            if not column_exists('pull_requests', 'pod_name'):
                logger.info("Adding pod_name column...")
                connection.execute(text(
                    "ALTER TABLE pull_requests ADD COLUMN pod_name VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added pod_name column")
            
            # Create indices for performance (skip if they already exist)
            logger.info("Creating indices on new columns...")
            
            # Just log that we're skipping index creation for now to speed up startup
            logger.info("✓ Skipping index creation (will be created on first use or manually)")
            
            # Indices will be created automatically by SQLAlchemy on table access
            # Or can be created manually later with:
            # CREATE INDEX IF NOT EXISTS idx_pr_trainer_id ON pull_requests(trainer_id);
            # etc.
            
            connection.commit()
        
        logger.info("✅ New pull_requests columns added successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error adding new columns: {e}")
        return False

def add_reviewer_comment_columns():
    """Add commented_reviews and dismissed_reviews columns to reviewers table."""
    logger.info("Checking for commented_reviews and dismissed_reviews columns in reviewers table...")
    
    try:
        # Get db connection using engine directly
        from database import engine
        with engine.connect() as conn:
            # Check if columns exist
            result = conn.execute(text("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name = 'reviewers' 
                AND column_name IN ('commented_reviews', 'dismissed_reviews')
            """))
            existing_columns = {row[0] for row in result.fetchall()}
            
            if 'commented_reviews' not in existing_columns:
                conn.execute(text("ALTER TABLE reviewers ADD COLUMN commented_reviews INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("✓ Added commented_reviews column")
            else:
                logger.info("✓ commented_reviews column already exists")
                
            if 'dismissed_reviews' not in existing_columns:
                conn.execute(text("ALTER TABLE reviewers ADD COLUMN dismissed_reviews INTEGER DEFAULT 0"))
                conn.commit()
                logger.info("✓ Added dismissed_reviews column")
            else:
                logger.info("✓ dismissed_reviews column already exists")
        
        logger.info("✅ reviewers table updated successfully")
    except Exception as e:
        logger.error(f"Error adding reviewer columns: {e}")

def run_migrations():
    """
    Run all database migrations
    This is called automatically on application startup
    """
    logger.info("=" * 60)
    logger.info("Running database migrations...")
    logger.info("=" * 60)
    
    # Clean up old schema (hierarchy columns in pull_requests)
    # These are now in the DeveloperHierarchy table
    remove_old_hierarchy_columns()
    
    # Add status column to developer_hierarchy
    add_status_column()
    
    # Allow NULL values in github_user column
    allow_null_github_user()
    
    # Add new pull_requests columns for normalized schema
    add_new_pr_columns()
    
    # Add total_check_failures to developers table
    add_developer_check_failures()
    
    # Add new sync_state tracking columns
    add_sync_state_columns()
    
    # Add missing users table columns
    add_users_table_columns()
    
    # Add reviewer_id to reviews table
    add_reviews_reviewer_id()
    
    # Add closed_prs to developers table
    add_developer_closed_prs()
    
    # Add commented_reviews and dismissed_reviews to reviewers table
    add_reviewer_comment_columns()
    
    # Note: DeveloperHierarchy table is created by init_db() via SQLAlchemy Base.metadata.create_all()
    logger.info("✓ DeveloperHierarchy table managed by SQLAlchemy ORM")
    
    logger.info("=" * 60)
    logger.info("✅ All migrations completed successfully")
    logger.info("=" * 60)
    
    return True

