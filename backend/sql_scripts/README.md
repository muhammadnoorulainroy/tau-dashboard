# SQL Scripts Directory

This directory contains SQL migration and utility scripts.

## Files

### Migration Scripts (Historical)
- `add_hierarchy_columns.sql` - Adds pod_lead_email and calibrator_email columns (now handled by db_migrations.py)
- `remove_role_columns.sql` - Removes old role columns (now handled by db_migrations.py)

## Note

⚠️ **These SQL scripts are kept for reference only.**

The application now uses **automatic migrations** via `db_migrations.py`, which runs on backend startup.

### Manual SQL execution is NOT required!

The migration system automatically handles:
- Adding/removing columns
- Creating/dropping indexes
- Schema changes
- Data transformations

## If You Need to Run Manual SQL

```bash
# Connect to PostgreSQL
psql -h localhost -U postgres -d tau_dashboard

# Run a script
\i sql_scripts/add_hierarchy_columns.sql

# Exit
\q
```

## Creating New Scripts

If you need to create a new migration script:

1. Add the migration logic to `backend/db_migrations.py`
2. It will run automatically on next backend startup
3. Optionally save the raw SQL here for reference

