# TAU Dashboard

A comprehensive dashboard for tracking Pull Request metrics, developer productivity, and review processes.

![Python](https://img.shields.io/badge/python-3.11-blue)
![React](https://img.shields.io/badge/react-18.2-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.104-green)

## Features

- **Developer Metrics**: Track PRs raised per developer, rework count, merge rates
- **Reviewer Metrics**: Monitor review counts, approval rates, and review patterns
- **Domain Analytics**: View task distribution across different domains
- **PR State Tracking**: Monitor PR states using GitHub labels
- **Real-time Updates**: WebSocket-based live updates
- **Smart Synchronization**: Intelligent sync strategy (full vs incremental)

## Prerequisites

Before you begin, make sure you have the following installed:

- **Python 3.11+** - [Download Python](https://www.python.org/downloads/)
- **Node.js 18+** - [Download Node.js](https://nodejs.org/)
- **PostgreSQL 15+** - [Download PostgreSQL](https://www.postgresql.org/download/)

## Quick Start

### 1. Clone the Repository

```bash
git clone <repository-url>
cd tau-dashboard
```

### 2. Install Dependencies

```bash
make install
```

This will install both backend and frontend dependencies.

### 3. Set Up PostgreSQL Database

**Option A: Automatic (Recommended for new setup)**

The migration script can create the database for you automatically. Skip to Step 5 and use `make db-setup`.

**Option B: Manual**

Create the database manually:

```bash
createdb tau_dashboard
```

Or using psql:

```bash
psql -U postgres
CREATE DATABASE tau_dashboard;
\q
```

### 4. Configure Environment Variables

The project uses separate environment files for backend and frontend:

**Backend Configuration:**
- `backend/.env.dev` - Backend development configuration
- `backend/.env.production` - Backend production configuration
- `backend/.env` - Symlink to active environment

**Frontend Configuration:**
- `frontend/.env.dev` - Frontend development configuration
- `frontend/.env.production` - Frontend production configuration
- `frontend/.env` - Symlink to active environment

**For Development:**

Edit backend configuration:

```bash
# Edit the backend config
nano backend/.env.dev
```

```env
# Backend Server Configuration
BACKEND_HOST=0.0.0.0
BACKEND_PORT=4000
FRONTEND_URL=http://localhost:1000

# GitHub Configuration
GITHUB_TOKEN=ghp_your_github_token_here
GITHUB_REPO=TuringGpt/amazon-tau-bench-tasks

# Database Configuration
DB_HOST=localhost
DB_PORT=5432
DB_USER=postgres
DB_PASSWORD=postgres
DB_NAME=tau_dashboard

# Security
SECRET_KEY=change-this-secret-key
```

Edit frontend configuration (optional - only if you need custom ports):

```bash
nano frontend/.env.dev
```

```env
# Frontend Server Configuration
VITE_FRONTEND_PORT=1000
VITE_BACKEND_URL=http://localhost:4000

# API Configuration
VITE_API_BASE_URL=/api
VITE_WS_URL=ws://localhost:4000/ws
```

**Configuration Options:**

**Backend:**
- `BACKEND_HOST` - Host to bind backend server (default: 0.0.0.0)
- `BACKEND_PORT` - Backend port (default: 4000)
- `FRONTEND_URL` - Frontend URL for CORS (default: http://localhost:1000)
- `DB_HOST` - Database hostname
- `DB_PORT` - Database port (default: 5432)
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_NAME` - Database name
- `SECRET_KEY` - Security key (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)

**Frontend:**
- `VITE_FRONTEND_PORT` - Frontend dev server port (default: 1000)
- `VITE_BACKEND_URL` - Backend API URL (default: http://localhost:4000)

**Get your GitHub token:**
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate a new token (classic) with `repo` scope
3. Copy the token and paste it in `backend/.env.dev`

**For Production:**

Edit production configs and point `.env` symlinks to production files:

```bash
cd backend && ln -sf .env.production .env && cd ..
cd frontend && ln -sf .env.production .env && cd ..
```

### 5. Initialize Database

**Option A: Automatic Setup (Recommended for new installations)**
```bash
# Creates database (if needed) + all tables in one command
make db-setup
```

This will:
- Check if the database exists
- Create it if it doesn't exist (prompts for confirmation)
- Create all tables from the schema

**Option B: Manual Setup (if database already exists)**
```bash
# Run database migration to create tables only
make db-migrate
```

**Option C: Legacy Method**
```bash
# Tables will be created automatically on server startup
make db-init
```

**Testing Migration (Safe)**
```bash
# Test on separate database before applying to production
make db-test
```

### 6. Start the Application

You'll need two terminal windows:

**Terminal 1 - Backend:**
```bash
make start-backend
```

**Terminal 2 - Frontend:**
```bash
make start-frontend
```

### 7. Access the Dashboard

- **Frontend**: http://localhost:1000
- **Backend API**: http://localhost:4000
- **API Docs**: http://localhost:4000/docs

## Development

### Backend Development

The backend is built with FastAPI and uses:
- **FastAPI** - Modern web framework
- **SQLAlchemy** - ORM for database operations
- **PostgreSQL** - Database
- **PyGithub** - GitHub API integration

Backend files are in the `backend/` directory.

To run backend only:
```bash
cd backend
uvicorn main:app --reload
```

### Frontend Development

The frontend is built with React and Vite:
- **React 18** - UI library
- **Vite** - Build tool and dev server
- **Tailwind CSS** - Styling
- **Recharts** - Charts and visualizations
- **Axios** - HTTP client

Frontend files are in the `frontend/` directory.

To run frontend only:
```bash
cd frontend
npm run dev
```

### Project Structure

```
tau-dashboard/
├── backend/
│   ├── main.py              # FastAPI application
│   ├── database.py          # Database models and setup
│   ├── github_service.py    # GitHub API integration
│   ├── background_tasks.py  # Background sync tasks
│   ├── schemas.py           # Pydantic schemas
│   ├── config.py            # Configuration
│   └── requirements.txt     # Python dependencies
├── frontend/
│   ├── src/
│   │   ├── components/      # React components
│   │   ├── services/        # API services
│   │   ├── App.jsx          # Main app component
│   │   └── main.jsx         # Entry point
│   ├── package.json         # Node dependencies
│   └── vite.config.js       # Vite configuration
├── Makefile                 # Development commands
└── README.md
```

## Available Commands

```bash
make help           # Show all available commands
make setup          # Initial setup
make install        # Install all dependencies
make start-backend  # Start backend server
make start-frontend # Start frontend dev server
make test           # Run tests
make sync           # Trigger GitHub sync
make db-setup       # Setup database (create DB + tables)
make db-migrate     # Run database migration
make db-test        # Test migration on test database
make db-status      # Show database status
make db-init        # Initialize database (legacy)
make db-reset       # Reset database
make clean          # Clean up generated files
```

## API Endpoints

- `GET /api/overview` - Dashboard overview metrics
- `GET /api/developers` - Developer metrics
- `GET /api/reviewers` - Reviewer metrics
- `GET /api/domains` - Domain metrics
- `GET /api/prs` - Pull requests with filters
- `GET /api/pr-states` - PR state distribution
- `POST /api/sync` - Trigger manual GitHub sync
- `WS /ws` - WebSocket for real-time updates

Full API documentation: http://localhost:4000/docs

## Database Management

### Setup Database (First Time)
```bash
# Creates database (if needed) and all tables
make db-setup
```

### Run Migration (Existing Database)
```bash
# Creates tables only (database must exist)
make db-migrate
```

### Test Migration (Safe)
```bash
# Test on separate test database
make db-test
```

### Check Database Status
```bash
# Show tables and row counts
make db-status
```

### Initialize Database (Legacy)
```bash
make db-init
```

### Reset Database
```bash
make db-reset
```

### Direct Database Access
```bash
psql -U postgres -d tau_dashboard
```

## Troubleshooting

### Database Connection Error
- Make sure PostgreSQL is running: `pg_ctl status`
- Check if database exists: `psql -l`
- Verify credentials in `.env` file

### Port Already in Use
- Backend (4000): Check if another app is using port 4000
- Frontend (1000): Check if another app is using port 1000
- Use `lsof -i :4000` or `lsof -i :1000` to find the process

### GitHub API Rate Limiting
- Make sure you're using a valid GitHub token
- Token should have `repo` scope
- Check rate limit: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

### Module Not Found Errors
- Backend: Make sure you're in the virtual environment
- Frontend: Try deleting `node_modules` and running `npm install` again

## Production Deployment

### Server Setup (104.198.177.87)

The application runs on ports:
- **Backend**: 4000
- **Frontend**: 1000

#### 1. Install Prerequisites on Server

```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install PostgreSQL
sudo apt install postgresql postgresql-contrib -y

# Install Python and pip
sudo apt install python3 python3-pip python3-venv -y

# Install Node.js 18+
curl -fsSL https://deb.nodesource.com/setup_18.x | sudo -E bash -
sudo apt install -y nodejs

# Install PM2 for process management
sudo npm install -g pm2
```

#### 2. Setup PostgreSQL Database

```bash
# Switch to postgres user
sudo -u postgres psql

# Create database and user
CREATE DATABASE tau_dashboard;
CREATE USER postgres WITH PASSWORD 'postgres';
GRANT ALL PRIVILEGES ON DATABASE tau_dashboard TO postgres;
ALTER USER postgres WITH SUPERUSER;
\q
```

#### 3. Deploy Application

```bash
# Clone repository
cd ~
git clone <your-repo-url> tau-dashboard
cd tau-dashboard

# Backend setup
cd backend
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.production .env
python migrate_db.py --create-db --force

# Frontend setup
cd ../frontend
npm install
cp .env.production .env
npm run build
```

#### 4. Start Services with PM2

```bash
# Start backend on port 4000
cd ~/tau-dashboard/backend
pm2 start "uvicorn main:app --host 0.0.0.0 --port 4000" --name tau-backend

# Install serve for frontend
npm install -g serve

# Start frontend on port 1000
cd ~/tau-dashboard/frontend
pm2 start "serve -s dist -l 1000" --name tau-frontend

# Save PM2 configuration
pm2 save

# Setup PM2 to start on boot
pm2 startup
```

#### 5. Configure Firewall

```bash
sudo ufw allow 1000/tcp
sudo ufw allow 4000/tcp
sudo ufw allow 22/tcp
sudo ufw enable
```

#### 6. Access Application

- Frontend: http://104.198.177.87:1000
- Backend API: http://104.198.177.87:4000
- API Docs: http://104.198.177.87:4000/docs

### PM2 Management Commands

```bash
# View all services
pm2 status

# View logs
pm2 logs

# Restart services
pm2 restart all

# Stop services
pm2 stop all

# Start specific service
pm2 start tau-backend
pm2 start tau-frontend
```

### Update Deployment

```bash
# Pull latest code
cd ~/tau-dashboard
git pull

# Update backend
cd backend
source venv/bin/activate
pip install -r requirements.txt
pm2 restart tau-backend

# Update frontend
cd ../frontend
npm install
npm run build
pm2 restart tau-frontend
```

### Deployment Troubleshooting

```bash
# Check if ports are in use
sudo lsof -i :4000
sudo lsof -i :1000

# Check database connection
psql -U postgres -d tau_dashboard -c "SELECT COUNT(*) FROM pull_requests;"

# View PM2 logs
pm2 logs --lines 100

# Check service status
pm2 status
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary and confidential.

## Support

For issues or questions, please create an issue in the GitHub repository.
