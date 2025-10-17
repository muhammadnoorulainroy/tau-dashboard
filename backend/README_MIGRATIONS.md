# Database Migrations - Quick Reference

## Automatic Migrations ✨

Database schema changes **run automatically** on application startup.

### What Happens on Startup:

```
1. Application starts
   ↓
2. Base tables created (init_db)
   ↓
3. Migrations run automatically (db_migrations.py)
   ├─ Check if pod_lead_email column exists
   ├─ Check if calibrator_email column exists
   ├─ Check if indices exist
   └─ Add missing items
   ↓
4. Application ready ✅
```

### Example Logs:

**First run (columns don't exist):**
```
INFO:db_migrations:Running database migrations...
INFO:db_migrations:Adding pod_lead_email column to pull_requests table...
INFO:db_migrations:✓ Added pod_lead_email column
INFO:db_migrations:Adding calibrator_email column to pull_requests table...
INFO:db_migrations:✓ Added calibrator_email column
INFO:db_migrations:Creating index on pod_lead_email...
INFO:db_migrations:✓ Created idx_pr_pod_lead index
INFO:db_migrations:Creating index on calibrator_email...
INFO:db_migrations:✓ Created idx_pr_calibrator index
INFO:db_migrations:✅ All migrations completed successfully
```

**Subsequent runs (columns already exist):**
```
INFO:db_migrations:Running database migrations...
INFO:db_migrations:✓ pod_lead_email column already exists
INFO:db_migrations:✓ calibrator_email column already exists
INFO:db_migrations:✓ idx_pr_pod_lead index already exists
INFO:db_migrations:✓ idx_pr_calibrator index already exists
INFO:db_migrations:✅ All migrations completed successfully
```

## No Manual Steps Required 🎉

Just start your application:
```bash
uvicorn main:app --reload
```

The migration system:
- ✅ Checks what's missing
- ✅ Adds only what's needed
- ✅ Safe to run multiple times (idempotent)
- ✅ Logs everything clearly
- ✅ Won't break existing data

## Files

- **`db_migrations.py`** - Contains all migration logic
- **`main.py`** - Calls `run_migrations()` on startup
- **`add_hierarchy_columns.sql`** - *(Legacy) Manual SQL, kept for reference*

## For Developers

### Adding a New Migration:

1. Edit `backend/db_migrations.py`
2. Add your migration function
3. Call it in `run_migrations()`

Example:
```python
def add_my_new_feature():
    """Add description"""
    try:
        with engine.connect() as connection:
            if not column_exists('my_table', 'my_column'):
                connection.execute(text(
                    "ALTER TABLE my_table ADD COLUMN my_column VARCHAR"
                ))
                connection.commit()
                logger.info("✓ Added my_column")
        return True
    except Exception as e:
        logger.error(f"Error: {e}")
        return False

def run_migrations():
    add_hierarchy_columns()
    add_my_new_feature()  # Add here
```

## Troubleshooting

### Migration Fails?
Check logs for specific error. Common issues:
- Database connection problem
- Insufficient permissions (need ALTER TABLE)
- Column already exists with different type

### Need to Revert?
Use the manual SQL script:
```bash
psql -f backend/remove_role_columns.sql
```

## More Details

See `AUTOMATIC_MIGRATIONS.md` for comprehensive documentation.

