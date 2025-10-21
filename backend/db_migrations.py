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

def add_github_created_at_to_domains():
    """
    Add github_created_at column to domains table to track when domain was created on GitHub
    """
    try:
        logger.info("Checking for github_created_at column in domains...")
        
        if not column_exists('domains', 'github_created_at'):
            logger.info("Adding github_created_at column to domains...")
            with engine.connect() as connection:
                connection.execute(text(
                    "ALTER TABLE domains ADD COLUMN github_created_at TIMESTAMPTZ"
                ))
                connection.commit()
                logger.info("✓ Added github_created_at column")
        else:
            logger.info("✓ github_created_at column already exists")
            
        logger.info("✅ domains table updated with GitHub metadata")
        
    except Exception as e:
        logger.error(f"Error adding github_created_at column: {str(e)}")
        raise


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
    
    # Add github_created_at to domains table
    add_github_created_at_to_domains()
    
    # Note: DeveloperHierarchy table is created by init_db() via SQLAlchemy Base.metadata.create_all()
    logger.info("✓ DeveloperHierarchy table managed by SQLAlchemy ORM")
    
    logger.info("=" * 60)
    logger.info("✅ All migrations completed successfully")
    logger.info("=" * 60)
    
    return True

