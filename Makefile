SHELL := /bin/bash

# Environment variables (can be overridden)
BACKEND_HOST ?= 0.0.0.0
BACKEND_PORT ?= 4000
# BACKEND_URL must be explicitly set via environment variable (no default)
BACKEND_URL ?=

.PHONY: help setup install start-backend start-frontend start stop clean test sync sync-full sync-last-3-days db-init db-setup db-migrate db-test db-reset db-status db-fix-timezone db-backfill-weeks db-cleanup-weeks generate-secret

# Default target
help:
	@echo "TAU Dashboard - Local Development Commands"
	@echo "=========================================="
	@echo ""
	@echo "Environment Variables:"
	@echo "  BACKEND_HOST=0.0.0.0    - Backend host (default: 0.0.0.0)"
	@echo "  BACKEND_PORT=4000       - Backend port (default: 4000)"
	@echo "  BACKEND_URL=http://...  - Full backend URL (REQUIRED for sync command, no default)"
	@echo ""
	@echo "Setup & Installation:"
	@echo "  make setup          - Initial setup (install dependencies)"
	@echo "  make install        - Install all dependencies"
	@echo ""
	@echo "Running the Application:"
	@echo "  make start-backend  - Start backend server"
	@echo "  make start-frontend - Start frontend dev server"
	@echo "  make start          - Start both (in separate terminals)"
	@echo ""
	@echo "Database Management:"
	@echo "  make db-setup            - Setup database (create DB + tables, one command)"
	@echo "  make db-migrate          - Run database migration (create tables)"
	@echo "  make db-test             - Test migration on test database"
	@echo "  make db-status           - Show database status"
	@echo "  make db-backfill-weeks   - Backfill week/pod data for existing PRs"
	@echo "  make db-cleanup-weeks    - Clean up duplicate week entries"
	@echo "  make db-reset            - Reset database (DANGER: deletes all data)"
	@echo "  make db-init             - Initialize database (legacy, use db-migrate)"
	@echo ""
	@echo "Sync Commands:"
	@echo "  make sync               - Trigger incremental GitHub sync via API (fast, requires BACKEND_URL)"
	@echo "  make sync-full          - Run FULL re-sync in foreground with visible logs (direct DB access)"
	@echo "  make sync-last-3-days   - Sync PRs from last 3 days only (runs automatically every 24h)"
	@echo ""
	@echo "Other Commands:"
	@echo "  make test           - Run tests"
	@echo "  make generate-secret - Generate a secure SECRET_KEY"
	@echo "  make clean          - Clean up generated files"

# Initial setup
setup: install
	@echo "Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Make sure PostgreSQL is running"
	@echo "2. Create database: createdb tau_dashboard"
	@echo "3. Configure environment:"
	@echo "   - Backend:  Edit backend/.env.dev and add your GITHUB_TOKEN"
	@echo "   - Frontend: Edit frontend/.env.dev if you need custom ports"
	@echo "   - Default: Backend on port 4000, Frontend on port 1000"
	@echo "4. Run 'make start-backend' in one terminal"
	@echo "5. Run 'make start-frontend' in another terminal"

# Install all dependencies
install: install-backend install-frontend
	@echo "All dependencies installed"

# Install backend dependencies
install-backend:
	@echo "Installing backend dependencies..."
	cd backend && source venv/bin/activate && pip install -r requirements.txt

# Install frontend dependencies
install-frontend:
	@echo "Installing frontend dependencies..."
	cd frontend && npm install

# Start backend server
start-backend:
	@echo "Starting backend server..."
	@echo "Creating backend .env symlink if needed..."
	@cd backend && [ -f .env ] || ln -s .env.dev .env
	@echo "Starting backend on $(BACKEND_HOST):$(BACKEND_PORT)..."
	cd backend && source venv/bin/activate && uvicorn main:app --reload --host $(BACKEND_HOST) --port $(BACKEND_PORT)

# Start frontend dev server
start-frontend:
	@echo "Starting frontend dev server..."
	@echo "Creating frontend .env symlink if needed..."
	@cd frontend && ([ -L .env ] || [ ! -e .env ]) && ln -sf .env.dev .env || true
	@echo "Starting frontend (check frontend/.env.dev for port configuration)..."
	cd frontend && npm run dev

# Start both (note: requires two terminals)
start:
	@echo "WARNING: You need to run these commands in separate terminals:"
	@echo "Terminal 1: make start-backend"
	@echo "Terminal 2: make start-frontend"

# Run tests
test:
	@echo "Running tests..."
	@cd backend && source venv/bin/activate && python -m pytest || echo "pytest not configured yet"

# Trigger manual sync (incremental)
sync:
ifndef BACKEND_URL
	@echo "ERROR: BACKEND_URL is not set!"
	@echo ""
	@echo "Please set BACKEND_URL environment variable:"
	@echo "  Windows:    set BACKEND_URL=http://localhost:4000"
	@echo "  Linux/Mac:  export BACKEND_URL=http://localhost:4000"
	@echo "  Production: set BACKEND_URL=https://your-api-domain.com"
	@echo ""
	@echo "Or run: BACKEND_URL=http://localhost:4000 make sync"
	@exit 1
else
	@echo "Triggering incremental GitHub sync..."
	@echo "Backend URL: $(BACKEND_URL)"
	@curl -X POST $(BACKEND_URL)/api/sync
endif

# Trigger full re-sync from oldest PR in database (runs in foreground with logs)
sync-full:
	@echo "Starting FULL re-sync..."
	@echo ""
	@echo "This will re-sync ALL PRs to update check counts and other metrics."
	@echo "This may take several minutes and use significant API quota."
	@echo "Safe to run while backend is running (uses database locking)."
	@echo ""
	cd backend && python sync_full.py

# Sync data for last 3 days only (runs automatically every 24h, can also run manually)
sync-last-3-days:
	@echo "Starting sync for last 3 days..."
	@echo ""
	@echo "This will sync all PRs updated in the last 3 days."
	@echo "This runs automatically every 24 hours in the background."
	@echo "Safe to run manually while backend is running (uses database locking)."
	@echo ""
	cd backend && python sync_last_3_days.py

# Setup database (create database + tables in one command)
db-setup:
	@echo "Setting up database (will create if needed)..."
	cd backend && source venv/bin/activate && python migrate_db.py --create-db

# Run database migration (create tables)
db-migrate:
	@echo "Running database migration..."
	cd backend && source venv/bin/activate && python migrate_db.py

# Test migration on test database (safe)
db-test:
	@echo "Testing migration on test database..."
	cd backend && bash test_migration.sh

# Show database status
db-status:
	@echo "Database Status:"
	@echo ""
	@cd backend && source venv/bin/activate && python -c "from database import SessionLocal; from sqlalchemy import inspect; db = SessionLocal(); inspector = inspect(db.bind); tables = inspector.get_table_names(); print(f'Tables: {len(tables)}'); print(''); [print(f'  - {t}') for t in sorted(tables)]; db.close()"

# Initialize database (legacy - use db-migrate instead)
db-init:
	@echo "Initializing database (legacy method)..."
	@echo "WARNING: Consider using 'make db-migrate' instead"
	cd backend && source venv/bin/activate && python -c "from database import init_db; init_db()"

# Reset database (DANGER: deletes all data)
db-reset:
	@echo "WARNING: This will DELETE ALL DATA!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read dummy
	@echo "Resetting database..."
	psql -U postgres -d tau_dashboard -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" || echo "Make sure PostgreSQL is running"
	@echo "Recreating tables..."
	make db-migrate

# Backfill week/pod data for existing PRs
db-backfill-weeks:
	@echo "Backfilling week and pod data for existing PRs..."
	@echo "This will update PRs that have NULL week_id by parsing their file paths."
	@echo ""
	@echo "Options:"
	@echo "  To preview changes: cd backend && source venv/bin/activate && python backfill_week_pod.py --dry-run"
	@echo "  To limit PRs:       cd backend && source venv/bin/activate && python backfill_week_pod.py --limit 10"
	@echo ""
	cd backend && source venv/bin/activate && python backfill_week_pod.py

# Clean up duplicate week entries
db-cleanup-weeks:
	@echo "Cleaning up duplicate week entries..."
	@echo "This will merge duplicate weeks (e.g., 'Week 13' and 'week_13') into one."
	@echo ""
	cd backend && source venv/bin/activate && python cleanup_duplicate_weeks.py

# Generate secure secret key
generate-secret:
	@python3 generate_secret.py

# Clean up
clean:
	@echo "Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"
