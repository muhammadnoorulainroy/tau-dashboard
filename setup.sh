#!/bin/bash

echo "🚀 TAU Dashboard - Local Setup Script"
echo "======================================"
echo ""

# Colors for output
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# Check if Python is installed
echo "Checking prerequisites..."
if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 is not installed${NC}"
    echo "Please install Python 3.11+ from https://www.python.org/downloads/"
    exit 1
fi
echo -e "${GREEN}✅ Python $(python3 --version)${NC}"

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo -e "${RED}❌ Node.js is not installed${NC}"
    echo "Please install Node.js 18+ from https://nodejs.org/"
    exit 1
fi
echo -e "${GREEN}✅ Node.js $(node --version)${NC}"

# Check if PostgreSQL is installed
if ! command -v psql &> /dev/null; then
    echo -e "${YELLOW}⚠️  PostgreSQL command line tools not found${NC}"
    echo "Make sure PostgreSQL is installed and running"
else
    echo -e "${GREEN}✅ PostgreSQL installed${NC}"
fi

echo ""
echo "Installing dependencies..."
echo ""

# Install backend dependencies
echo "📦 Installing backend dependencies..."
cd backend
if [ ! -d "venv" ]; then
    echo "Creating Python virtual environment..."
    python3 -m venv venv
fi

echo "Activating virtual environment..."
source venv/bin/activate

echo "Installing Python packages..."
pip install -r requirements.txt
cd ..

echo -e "${GREEN}✅ Backend dependencies installed${NC}"
echo ""

# Install frontend dependencies
echo "📦 Installing frontend dependencies..."
cd frontend
npm install
cd ..

echo -e "${GREEN}✅ Frontend dependencies installed${NC}"
echo ""

# Create backend .env files if they don't exist
if [ ! -f "backend/.env.dev" ]; then
    echo "Creating backend/.env.dev file..."
    cat > backend/.env.dev << 'EOF'
# Backend Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000
# GitHub Configuration - REQUIRED
# Get your GitHub token from: https://github.com/settings/tokens
GITHUB_TOKEN=your_github_token_here
GITHUB_REPO=TuringGpt/amazon-tau-bench-tasks

# Database Configuration - REQUIRED
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=tau_dashboard

# Security - REQUIRED
# Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
SECRET_KEY=change-this-secret-key
EOF
    echo -e "${GREEN}✅ Created backend/.env.dev file${NC}"
else
    echo -e "${GREEN}✅ backend/.env.dev file already exists${NC}"
fi

if [ ! -f "backend/.env.production" ]; then
    echo "Creating backend/.env.production file..."
    cat > backend/.env.production << 'EOF'
# Backend Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=8000
FRONTEND_URL=https://your-frontend-domain.com
# GitHub Configuration - REQUIRED
GITHUB_TOKEN=your_production_github_token_here
GITHUB_REPO=TuringGpt/amazon-tau-bench-tasks

# Database Configuration - REQUIRED
DB_HOST=production-host
DB_PORT=5432
DB_USER=your_db_user
DB_PASSWORD=your_db_password
DB_NAME=tau_dashboard

# Security - REQUIRED
# Generate a secure key with: python -c "import secrets; print(secrets.token_urlsafe(32))"
# NEVER use a weak key in production!
SECRET_KEY=GENERATE-A-STRONG-RANDOM-SECRET-KEY-HERE
EOF
    echo -e "${GREEN}✅ Created backend/.env.production file${NC}"
else
    echo -e "${GREEN}✅ backend/.env.production file already exists${NC}"
fi

# Create frontend .env files if they don't exist
if [ ! -f "frontend/.env.dev" ]; then
    echo "Creating frontend/.env.dev file..."
    cat > frontend/.env.dev << 'EOF'
# Frontend Server Configuration
VITE_FRONTEND_PORT=3000
VITE_BACKEND_URL=http://localhost:8000

# API Configuration
VITE_API_BASE_URL=/api
VITE_WS_URL=ws://localhost:8000/ws
EOF
    echo -e "${GREEN}✅ Created frontend/.env.dev file${NC}"
else
    echo -e "${GREEN}✅ frontend/.env.dev file already exists${NC}"
fi

if [ ! -f "frontend/.env.production" ]; then
    echo "Creating frontend/.env.production file..."
    cat > frontend/.env.production << 'EOF'
# Frontend Server Configuration
VITE_FRONTEND_PORT=3000
VITE_BACKEND_URL=https://your-backend-api.com

# API Configuration
VITE_API_BASE_URL=/api
VITE_WS_URL=wss://your-backend-api.com/ws
EOF
    echo -e "${GREEN}✅ Created frontend/.env.production file${NC}"
else
    echo -e "${GREEN}✅ frontend/.env.production file already exists${NC}"
fi

# Create symlinks for .env pointing to .env.dev
if [ ! -f "backend/.env" ]; then
    echo "Creating backend/.env symlink to backend/.env.dev..."
    cd backend && ln -s .env.dev .env && cd ..
    echo -e "${GREEN}✅ Created backend/.env -> backend/.env.dev symlink${NC}"
    echo -e "${YELLOW}⚠️  Please edit backend/.env.dev and add your GITHUB_TOKEN${NC}"
else
    echo -e "${GREEN}✅ backend/.env file already exists${NC}"
fi

if [ ! -f "frontend/.env" ]; then
    echo "Creating frontend/.env symlink to frontend/.env.dev..."
    cd frontend && ln -s .env.dev .env && cd ..
    echo -e "${GREEN}✅ Created frontend/.env -> frontend/.env.dev symlink${NC}"
else
    echo -e "${GREEN}✅ frontend/.env file already exists${NC}"
fi

echo ""
echo "======================================"
echo -e "${GREEN}🎉 Setup Complete!${NC}"
echo "======================================"
echo ""
echo "Next steps:"
echo ""
echo "1. ${YELLOW}Create the database:${NC}"
echo "   createdb tau_dashboard"
echo ""
echo "2. ${YELLOW}Configure environment variables:${NC}"
echo "   Backend:  Edit backend/.env.dev and set your GITHUB_TOKEN"
echo "   Frontend: Edit frontend/.env.dev for custom ports (optional)"
echo "   (Get token from https://github.com/settings/tokens)"
echo "   Default ports: Backend=8000, Frontend=3000"
echo ""
echo "3. ${YELLOW}Initialize the database:${NC}"
echo "   make db-init"
echo ""
echo "4. ${YELLOW}Start the application:${NC}"
echo "   Terminal 1: make start-backend"
echo "   Terminal 2: make start-frontend"
echo ""
echo "5. ${YELLOW}Access the dashboard:${NC}"
echo "   Frontend: http://localhost:3000"
echo "   Backend:  http://localhost:8000"
echo "   API Docs: http://localhost:8000/docs"
echo ""

