"""
Database Migration Script
Creates database (if needed) and all tables from SQLAlchemy models.
"""
import sys
import argparse
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import OperationalError
from database import Base
from config import settings

def get_table_count(engine):
    """Get count of existing tables."""
    inspector = inspect(engine)
    return len(inspector.get_table_names())

def parse_database_url(url):
    """Parse database URL into components."""
    # Example: postgresql://user:pass@host:port/dbname
    parts = url.rsplit('/', 1)
    base_url = parts[0]  # postgresql://user:pass@host:port
    db_name = parts[1] if len(parts) > 1 else 'tau_dashboard'
    return base_url, db_name

def database_exists(database_url):
    """Check if database exists."""
    try:
        engine = create_engine(database_url)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except OperationalError:
        return False
    except Exception as e:
        print(f"Warning: Could not check database existence: {str(e)}")
        return False

def create_database(database_url, db_name, verbose=True):
    """Create the database if it doesn't exist."""
    base_url, _ = parse_database_url(database_url)
    
    # Connect to default 'postgres' database to create new database
    postgres_url = f"{base_url}/postgres"
    
    try:
        if verbose:
            print(f"Creating database '{db_name}'...")
        
        # Create engine with isolation_level for CREATE DATABASE
        engine = create_engine(postgres_url, isolation_level="AUTOCOMMIT")
        
        with engine.connect() as conn:
            # Check if database already exists
            result = conn.execute(
                text(f"SELECT 1 FROM pg_database WHERE datname = :dbname"),
                {"dbname": db_name}
            )
            exists = result.fetchone() is not None
            
            if exists:
                if verbose:
                    print(f"Database '{db_name}' already exists.")
                return True
            
            # Create database
            conn.execute(text(f'CREATE DATABASE "{db_name}"'))
            
            if verbose:
                print(f"Database '{db_name}' created successfully!")
            return True
            
    except Exception as e:
        print(f"ERROR: Could not create database: {str(e)}")
        return False
    finally:
        engine.dispose()

def migrate_database(database_url=None, force=False, verbose=True, create_db=False):
    """
    Create all tables from models.
    
    Args:
        database_url: Database URL (defaults to settings.database_url)
        force: Skip confirmation prompt
        verbose: Print detailed information
        create_db: Create database if it doesn't exist
    """
    # Use provided URL or fall back to settings
    url = database_url or settings.database_url
    base_url, db_name = parse_database_url(url)
    
    if verbose:
        print("=" * 80)
        print("DATABASE MIGRATION SCRIPT")
        print("=" * 80)
        # Mask password in URL for display
        display_url = url
        if '@' in url and ':' in url:
            parts = url.split('@')
            user_pass = parts[0].split('//')[-1]
            if ':' in user_pass:
                user, _ = user_pass.split(':', 1)
                display_url = url.replace(user_pass, f"{user}:****")
        print(f"Target Database: {display_url}")
        print("=" * 80)
        print()
    
    # Check if database exists
    db_exists = database_exists(url)
    
    if not db_exists:
        if verbose:
            print(f"Database '{db_name}' does not exist.")
            print()
        
        if create_db:
            # Attempt to create database
            if not create_database(url, db_name, verbose):
                return False
            print()
        else:
            # Ask user if they want to create it
            if not force:
                response = input(f"Create database '{db_name}'? [y/N]: ")
                if response.lower() not in ['y', 'yes']:
                    print("Migration cancelled. Please create the database manually:")
                    print(f"  psql -U postgres")
                    print(f"  CREATE DATABASE {db_name};")
                    print(f"  \\q")
                    return False
                print()
            
            # Create database
            if not create_database(url, db_name, verbose):
                return False
            print()
    
    # Create engine
    try:
        engine = create_engine(url)
        
        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT 1"))
            result.fetchone()
        
        if verbose:
            print("Database connection: OK")
    except Exception as e:
        print(f"ERROR: Could not connect to database: {str(e)}")
        return False
    
    # Check existing tables
    existing_count = get_table_count(engine)
    
    if verbose:
        print(f"Existing tables: {existing_count}")
        print()
    
    # Confirmation prompt (unless forced)
    if not force and existing_count > 0:
        response = input(f"Database has {existing_count} existing tables. Continue? [y/N]: ")
        if response.lower() not in ['y', 'yes']:
            print("Migration cancelled.")
            return False
    
    if verbose:
        print("Creating tables from models...")
        print()
    
    # Create all tables
    try:
        Base.metadata.create_all(bind=engine)
        
        if verbose:
            print("Tables created successfully!")
            print()
            
            # Show created tables
            inspector = inspect(engine)
            tables = inspector.get_table_names()
            
            print(f"Total tables: {len(tables)}")
            print()
            print("Tables:")
            for table in sorted(tables):
                # Get row count
                try:
                    with engine.connect() as conn:
                        result = conn.execute(text(f'SELECT COUNT(*) FROM "{table}"'))
                        count = result.fetchone()[0]
                    print(f"  - {table:30} ({count} rows)")
                except Exception as e:
                    print(f"  - {table:30} (error counting rows)")
            
            print()
            print("=" * 80)
            print("MIGRATION COMPLETE")
            print("=" * 80)
        
        return True
        
    except Exception as e:
        print(f"ERROR during migration: {str(e)}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        engine.dispose()

def main():
    parser = argparse.ArgumentParser(
        description='Database migration script - creates database (if needed) and all tables from models'
    )
    parser.add_argument(
        '--database-url',
        help='Database URL (default: from .env file)',
        default=None
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Skip confirmation prompts'
    )
    parser.add_argument(
        '--quiet',
        action='store_true',
        help='Minimal output'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Use test database (tau_dashboard_test)'
    )
    parser.add_argument(
        '--create-db',
        action='store_true',
        help='Automatically create database if it does not exist (no prompt)'
    )
    
    args = parser.parse_args()
    
    # Handle test mode
    database_url = args.database_url
    if args.test:
        # Replace database name with test version
        if database_url:
            database_url = database_url.rsplit('/', 1)[0] + '/tau_dashboard_test'
        else:
            db_url = settings.database_url
            database_url = db_url.rsplit('/', 1)[0] + '/tau_dashboard_test'
        print("TEST MODE: Using test database")
        print()
    
    success = migrate_database(
        database_url=database_url,
        force=args.force,
        verbose=not args.quiet,
        create_db=args.create_db or args.force  # Auto-create if --create-db or --force
    )
    
    sys.exit(0 if success else 1)

if __name__ == '__main__':
    main()

