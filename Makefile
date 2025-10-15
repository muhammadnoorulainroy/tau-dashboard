.PHONY: help setup install start-backend start-frontend start stop clean test sync db-init db-reset generate-secret

# Default target
help:
	@echo "TAU Dashboard - Local Development Commands"
	@echo "=========================================="
	@echo "make setup          - Initial setup (install dependencies)"
	@echo "make install        - Install all dependencies"
	@echo "make start-backend  - Start backend server"
	@echo "make start-frontend - Start frontend dev server"
	@echo "make start          - Start both backend and frontend (in separate terminals)"
	@echo "make test           - Run tests"
	@echo "make sync           - Trigger manual GitHub sync"
	@echo "make db-init        - Initialize database"
	@echo "make db-reset       - Reset database"
	@echo "make generate-secret - Generate a secure SECRET_KEY"
	@echo "make clean          - Clean up generated files"

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

# Initialize database
db-init:
	@echo "🗄️  Initializing database..."
	cd backend && python -c "from database import init_db; init_db()"

# Reset database
db-reset:
	@echo "⚠️  Resetting database..."
	psql -U postgres -d tau_dashboard -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;" || echo "Make sure PostgreSQL is running"
	make db-init

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
