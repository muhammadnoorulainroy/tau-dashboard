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

Create the database:

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
BACKEND_PORT=8000
FRONTEND_URL=http://localhost:3000

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
VITE_FRONTEND_PORT=3000
VITE_BACKEND_URL=http://localhost:8000

# API Configuration
VITE_API_BASE_URL=/api
VITE_WS_URL=ws://localhost:8000/ws
```

**Configuration Options:**

**Backend:**
- `BACKEND_HOST` - Host to bind backend server (default: 0.0.0.0)
- `BACKEND_PORT` - Backend port (default: 8000)
- `FRONTEND_URL` - Frontend URL for CORS (default: http://localhost:3000)
- `DB_HOST` - Database hostname
- `DB_PORT` - Database port (default: 5432)
- `DB_USER` - Database username
- `DB_PASSWORD` - Database password
- `DB_NAME` - Database name
- `SECRET_KEY` - Security key (generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`)

**Frontend:**
- `VITE_FRONTEND_PORT` - Frontend dev server port (default: 3000)
- `VITE_BACKEND_URL` - Backend API URL (default: http://localhost:8000)

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

**Option A: Using Migration Script (Recommended)**
```bash
# Run database migration to create all tables
make db-migrate
```

**Option B: Legacy Method**
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

- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

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
make db-init        # Initialize database
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

Full API documentation: http://localhost:8000/docs

## Database Management

### Initialize Database
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
- Backend (8000): Check if another app is using port 8000
- Frontend (3000): Check if another app is using port 3000
- Use `lsof -i :8000` or `lsof -i :3000` to find the process

### GitHub API Rate Limiting
- Make sure you're using a valid GitHub token
- Token should have `repo` scope
- Check rate limit: `curl -H "Authorization: token YOUR_TOKEN" https://api.github.com/rate_limit`

### Module Not Found Errors
- Backend: Make sure you're in the virtual environment
- Frontend: Try deleting `node_modules` and running `npm install` again

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
