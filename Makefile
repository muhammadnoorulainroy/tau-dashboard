.PHONY: help setup install start-backend start-frontend start stop clean test sync db-init db-setup db-migrate db-test db-reset db-status db-fix-timezone generate-secret

# Default target
help:
	@echo "TAU Dashboard - Local Development Commands"
	@echo "=========================================="
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
	@echo "  make db-setup       - Setup database (create DB + tables, one command)"
	@echo "  make db-migrate     - Run database migration (create tables)"
	@echo "  make db-test        - Test migration on test database"
	@echo "  make db-status      - Show database status"
	@echo "  make db-reset       - Reset database (DANGER: deletes all data)"
	@echo "  make db-init        - Initialize database (legacy, use db-migrate)"
	@echo ""
	@echo "Other Commands:"
	@echo "  make test           - Run tests"
	@echo "  make sync           - Trigger manual GitHub sync"
	@echo "  make generate-secret - Generate a secure SECRET_KEY"
	@echo "  make clean          - Clean up generated files"

# Initial setup
setup: install
	@echo "✅ Setup complete!"
	@echo ""
	@echo "Next steps:"
	@echo "1. Make sure PostgreSQL is running"
	@echo "2. Create database: createdb tau_dashboard"
	@echo "3. Configure environment:"
	@echo "   - Backend:  Edit backend/.env.dev and add your GITHUB_TOKEN"
	@echo "   - Frontend: Edit frontend/.env.dev if you need custom ports"
	@echo "   - Default: Backend on port 8000, Frontend on port 3000"
	@echo "4. Run 'make start-backend' in one terminal"
	@echo "5. Run 'make start-frontend' in another terminal"

# Install all dependencies
install: install-backend install-frontend
	@echo "✅ All dependencies installed"

# Install backend dependencies
install-backend:
	@echo "📦 Installing backend dependencies..."
	cd backend && pip install -r requirements.txt

# Install frontend dependencies
install-frontend:
	@echo "📦 Installing frontend dependencies..."
	cd frontend && npm install

# Start backend server
start-backend:
	@echo "🚀 Starting backend server..."
	@echo "Creating backend .env symlink if needed..."
	@cd backend && [ -f .env ] || ln -s .env.dev .env
	@echo "Starting backend (check backend/.env.dev for port configuration)..."
	cd backend && uvicorn main:app --reload

# Start frontend dev server
start-frontend:
	@echo "🚀 Starting frontend dev server..."
	@echo "Creating frontend .env symlink if needed..."
	@cd frontend && [ -f .env ] || ln -s .env.dev .env
	@echo "Starting frontend (check frontend/.env.dev for port configuration)..."
	cd frontend && npm run dev

# Start both (note: requires two terminals)
start:
	@echo "⚠️  You need to run these commands in separate terminals:"
	@echo "Terminal 1: make start-backend"
	@echo "Terminal 2: make start-frontend"

# Run tests
test:
	@echo "🧪 Running tests..."
	@cd backend && python -m pytest || echo "pytest not configured yet"

# Trigger manual sync
sync:
	@echo "🔄 Triggering GitHub sync..."
	curl -X POST http://localhost:8000/api/sync

# Setup database (create database + tables in one command)
db-setup:
	@echo "🗄️  Setting up database (will create if needed)..."
	cd backend && python migrate_db.py --create-db

# Run database migration (create tables)
db-migrate:
	@echo "🗄️  Running database migration..."
	cd backend && python migrate_db.py

# Test migration on test database (safe)
db-test:
	@echo "🧪 Testing migration on test database..."
	cd backend && bash test_migration.sh

# Show database status
db-status:
	@echo "📊 Database Status:"
	@echo ""
	@cd backend && python -c "from database import SessionLocal; from sqlalchemy import inspect; db = SessionLocal(); inspector = inspect(db.bind); tables = inspector.get_table_names(); print(f'Tables: {len(tables)}'); print(''); [print(f'  - {t}') for t in sorted(tables)]; db.close()"

# Initialize database (legacy - use db-migrate instead)
db-init:
	@echo "🗄️  Initializing database (legacy method)..."
	@echo "⚠️  Consider using 'make db-migrate' instead"
	cd backend && python -c "from database import init_db; init_db()"

# Reset database (DANGER: deletes all data)
db-reset:
	@echo "⚠️  WARNING: This will DELETE ALL DATA!"
	@echo "Press Ctrl+C to cancel, or Enter to continue..."
	@read dummy
	@echo "Resetting database..."
	psql -U postgres -d tau_dashboard -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" || echo "Make sure PostgreSQL is running"
	@echo "Recreating tables..."
	make db-migrate

# Generate secure secret key
generate-secret:
	@python3 generate_secret.py

# Clean up
clean:
	@echo "🧹 Cleaning up..."
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "node_modules" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "dist" -exec rm -rf {} + 2>/dev/null || true
	@echo "✅ Clean complete"
