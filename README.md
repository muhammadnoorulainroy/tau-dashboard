# TAU Dashboard

A comprehensive dashboard for tracking Pull Request metrics, developer productivity, and review processes for the Amazon TAU Bench Tasks repository.

![TAU Dashboard](https://img.shields.io/badge/version-1.0.0-success)
![Python](https://img.shields.io/badge/python-3.11-blue)
![React](https://img.shields.io/badge/react-18.2-blue)
![FastAPI](https://img.shields.io/badge/fastapi-0.104-green)

## Features

### Real-time Metrics
- **Developer Metrics**: Track PRs raised per developer, rework count, merge rates
- **Reviewer Metrics**: Monitor review counts, approval rates, and review patterns
- **Domain Analytics**: View task distribution across different domains
- **PR State Tracking**: Monitor PR states using GitHub labels (expert review pending, ready to merge, etc.)

### Modern UI Design
- Clean, professional interface with warm color palette (orange, green, gray)
- Responsive design that works on all devices
- Real-time updates via WebSocket connections
- Interactive charts and visualizations using Recharts

### Advanced Filtering
- Filter PRs by specific naming patterns
- Track only PRs with relevant tags
- Support for both open and merged PRs
- Efficient handling of thousands of PRs

### Smart Synchronization
- Intelligent sync strategy (full vs incremental)
- Non-blocking background operations
- Automatic sync every 5 minutes for new updates
- Manual sync with real-time progress notifications

## Requirements

- Docker & Docker Compose
- Node.js 18+ (for local development)
- Python 3.11+ (for local development)
- PostgreSQL 15+
- Redis (for caching and background tasks)

## Installation

### Using Docker (Recommended)

1. Clone the repository:
```bash
git clone <repository-url>
cd tau-dashboard
```

2. Start the services:
```bash
docker-compose up -d
```

3. Access the dashboard:
- Frontend: http://localhost:3000
- Backend API: http://localhost:8000
- API Documentation: http://localhost:8000/docs

### Local Development Setup

#### Backend Setup

1. Navigate to backend directory:
```bash
cd backend
```

2. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up PostgreSQL:
```bash
# Create database
psql -U postgres -c "CREATE DATABASE tau_dashboard;"
```

5. Run the backend:
```bash
uvicorn main:app --reload
```

#### Frontend Setup

1. Navigate to frontend directory:
```bash
cd frontend
```

2. Install dependencies:
```bash
npm install
```

3. Start the development server:
```bash
npm run dev
```

## Configuration

### Environment Variables Setup

The application uses environment variables for all sensitive configuration. **Never hardcode secrets in the code.**

#### Step 1: Create .env file

```bash
# Copy the example file
cp .env.example .env

# Edit .env with your actual credentials
# nano .env  # or use any text editor
```

#### Step 2: Configure Required Variables

Edit `.env` and set these **required** variables:

```env
# GitHub Configuration - REQUIRED
GITHUB_TOKEN=ghp_your_actual_github_token_here
GITHUB_REPO=your-org/your-repo-name

# Database Configuration
DATABASE_URL=postgresql://postgres:postgres@localhost/tau_dashboard
DB_PASSWORD=postgres

# Redis Configuration
REDIS_URL=redis://localhost:6379

# Security - REQUIRED for production
SECRET_KEY=your-strong-secret-key-here
```

### GitHub Token Setup

1. Go to GitHub Settings > Developer settings > Personal access tokens
2. Generate a new token (classic) with `repo` scope
3. Copy the token and set it as `GITHUB_TOKEN` in your `.env` file
4. **Never commit this token to version control**

### Security Notes

- `.env` files are in `.gitignore` and will not be committed
- Use `.env.example` as a template (safe to commit)
- `backend/config.py` reads from environment variables automatically via pydantic-settings
- Docker Compose reads from `.env` file in the root directory
- Required fields: `GITHUB_TOKEN`, `GITHUB_REPO` (app will fail to start without them)

## Database Schema

The dashboard uses PostgreSQL with the following main tables:

- **pull_requests**: Stores PR data including title, state, labels, and metrics
- **developers**: Aggregated developer metrics
- **reviewers**: Aggregated reviewer metrics
- **reviews**: Individual review records
- **check_runs**: CI/CD check results
- **domain_metrics**: Domain-level aggregated metrics
- **sync_state**: Tracks synchronization history and timestamps

## API Endpoints

### Core Endpoints

- `GET /api/overview` - Dashboard overview metrics
- `GET /api/developers` - Developer metrics
- `GET /api/reviewers` - Reviewer metrics
- `GET /api/domains` - Domain metrics
- `GET /api/prs` - Pull requests with filters
- `GET /api/pr-states` - PR state distribution
- `POST /api/sync` - Trigger manual GitHub sync
- `WS /ws` - WebSocket for real-time updates

### API Documentation

Full API documentation is available at http://localhost:8000/docs (Swagger UI)

## UI Components

### Dashboard Views

1. **Main Dashboard**: Overview metrics, charts, and recent activity
2. **Developers View**: Detailed developer metrics and performance
3. **Reviewers View**: Review statistics and patterns
4. **Domains View**: Domain-specific metrics and task distribution
5. **Pull Requests View**: Detailed PR list with advanced filtering

### Key Metrics Tracked

- **Developer Metrics**:
  - Total PRs raised
  - Open vs Merged PRs
  - Rework count (based on feedback and failed checks)
  - Domain distribution

- **Reviewer Metrics**:
  - Total reviews conducted
  - Approval vs Changes requested ratio
  - Review distribution across domains

- **Domain Metrics**:
  - Task count by state (using PR labels)
  - Difficulty distribution
  - Top contributors

## Data Synchronization

The dashboard uses an intelligent synchronization strategy:

### Sync Types

1. **Initial Sync**: Fetches last 60 days of PR data on first run
2. **Full Sync**: Re-fetches last 60 days when last sync was more than 7 days ago
3. **Incremental Sync**: Fetches only recent changes since last sync (runs every 5 minutes)
4. **Manual Sync**: Trigger via the UI sync button with fire-and-forget mechanism

### Non-blocking Operations

- All sync operations run in background threads to prevent UI blocking
- WebSocket notifications provide real-time progress updates
- Sync history tracked in database for intelligent decision-making

## Performance Considerations

- Efficient database indexing for fast queries
- Pagination for large datasets
- Background tasks for heavy operations
- WebSocket for real-time updates without polling
- Caching with Redis for frequently accessed data
- ThreadPoolExecutor for concurrent processing

## PR Pattern Recognition

The dashboard recognizes PRs with the following naming pattern:
```
username-domain-difficulty-taskid
```

Examples:
- `daniel.kurui-hr_experts-4-expert-1760036183`
- `naincy.c-fund_finance-1-expert-1760024946`

Only PRs matching this pattern and having relevant tags are tracked.

## Supported PR Labels

- `expert review pending`
- `calibrator review pending`
- `expert approved`
- `ready to merge`
- `expert`
- `hard`
- `medium`
- `good task`

## Deployment

### Production Deployment

1. Update environment variables for production
2. Use proper secrets management
3. Set up SSL/TLS certificates
4. Configure reverse proxy (nginx/traefik)
5. Set up monitoring and logging

### Docker Production Build

```bash
docker-compose -f docker-compose.prod.yml up -d
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Commit your changes
4. Push to the branch
5. Create a Pull Request

## License

This project is proprietary and confidential.

## Troubleshooting

### Common Issues

1. **Database Connection Error**
   - Ensure PostgreSQL is running
   - Check database credentials
   - Verify database exists

2. **GitHub API Rate Limiting**
   - Use a valid GitHub token
   - Implement caching strategies
   - Reduce sync frequency if needed

3. **Frontend Build Issues**
   - Clear node_modules and reinstall
   - Check Node.js version compatibility
   - Verify all dependencies are installed

### Logs

- Backend logs: `docker-compose logs backend`
- Frontend logs: `docker-compose logs frontend`
- Database logs: `docker-compose logs postgres`

## Support

For issues or questions, please create an issue in the GitHub repository.

## Technology Stack

### Backend
- **FastAPI**: Modern, fast web framework for building APIs
- **SQLAlchemy**: SQL toolkit and ORM
- **PostgreSQL**: Relational database for data persistence
- **PyGithub**: Python library for GitHub API v3
- **Redis**: In-memory data structure store for caching
- **WebSockets**: Real-time bidirectional communication

### Frontend
- **React**: JavaScript library for building user interfaces
- **Vite**: Next-generation frontend build tool
- **Tailwind CSS**: Utility-first CSS framework
- **Recharts**: Composable charting library built on React components
- **Axios**: Promise-based HTTP client
- **date-fns**: Modern JavaScript date utility library

### DevOps
- **Docker**: Containerization platform
- **Docker Compose**: Multi-container Docker orchestration
- **Nginx**: High-performance HTTP server and reverse proxy

---

Built for efficient PR management and team productivity tracking.