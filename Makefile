.PHONY: help setup start stop restart logs clean build dev prod test

# Default target
help:
	@echo "TAU Dashboard - Available Commands"
	@echo "=================================="
	@echo "make setup    - Initial setup and configuration"
	@echo "make start    - Start all services"
	@echo "make stop     - Stop all services"
	@echo "make restart  - Restart all services"
	@echo "make logs     - View logs from all services"
	@echo "make clean    - Clean up containers and volumes"
	@echo "make build    - Build Docker images"
	@echo "make dev      - Start in development mode"
	@echo "make prod     - Start in production mode"
	@echo "make test     - Run tests"
	@echo "make sync     - Trigger manual GitHub sync"

# Setup environment
setup:
	@echo "Setting up TAU Dashboard..."
	@chmod +x setup.sh
	@./setup.sh

# Start services
start:
	docker-compose up -d
	@echo "Services started. Access the dashboard at http://localhost:3000"

# Stop services
stop:
	docker-compose down

# Restart services
restart: stop start

# View logs
logs:
	docker-compose logs -f

# Clean up
clean:
	docker-compose down -v
	@echo "Containers and volumes cleaned up"

# Build images
build:
	docker-compose build

# Development mode
dev:
	docker-compose up

# Production mode
prod:
	docker-compose -f docker-compose.prod.yml up -d

# Run tests
test:
	@echo "Running backend tests..."
	cd backend && python -m pytest
	@echo "Running frontend tests..."
	cd frontend && npm test

# Trigger manual sync
sync:
	curl -X POST http://localhost:8000/api/sync

# Install dependencies locally
install-backend:
	cd backend && pip install -r requirements.txt

install-frontend:
	cd frontend && npm install

install: install-backend install-frontend

# Database operations
db-init:
	docker-compose exec backend python -c "from database import init_db; init_db()"

db-reset:
	docker-compose exec postgres psql -U postgres -d tau_dashboard -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"
	make db-init

# Development helpers
backend-shell:
	docker-compose exec backend /bin/bash

frontend-shell:
	docker-compose exec frontend /bin/sh

db-shell:
	docker-compose exec postgres psql -U postgres -d tau_dashboard


