# Simple Aggregation Feature

## Overview
The dashboard now includes a simple aggregation view that displays task metrics across two dimensions:
1. **Domain wise** - Groups PRs by domain
2. **Trainer wise** - Groups PRs by developer (author_login)

The other tabs (Pod Leads, Calibrators, Experts) are placeholders that return empty data for now.

## Metrics Displayed
Each aggregation shows:
- **Total Tasks** - Number of pull requests
- **Completed Tasks** - Merged PRs (with percentage)
- **Rework %** - (Total rework count / Total tasks) × 100
- **Rejected** - Closed but not merged, or has 'rejected' label
- **Delivery Ready** - PRs with labels: 'ready to merge', 'delivery ready', or 'expert approved'

## Usage

### Access the Feature
1. Open the dashboard
2. Click on "Aggregation" in the sidebar
3. Switch between tabs to view different aggregations

### Available Views

#### Domain wise
- Groups all PRs by their `domain` field
- Shows metrics for each domain (hr_payroll, backend, frontend, etc.)
- Sorted by total tasks (descending)

#### Trainer wise  
- Shows all developers who have created PRs
- Groups by `author_login` (GitHub username)
- Shows individual developer metrics
- Sorted by total tasks (descending)

#### Pod Leads wise / Calibrators wise / Experts wise
- Currently return empty data
- Placeholders for future functionality

## Data Source
All data is pulled directly from the `pull_requests` table:
- No external files required
- No sync operations needed
- Data updates automatically when PRs are synced from GitHub

## API Endpoints

```
GET /api/aggregation/domains       - Domain aggregation
GET /api/aggregation/trainers      - Developer aggregation
GET /api/aggregation/pod-leads     - Empty (placeholder)
GET /api/aggregation/calibrators   - Empty (placeholder)
GET /api/aggregation/experts       - Empty (placeholder)
```

## Response Format

```json
[
  {
    "name": "hr_payroll",
    "total_tasks": 45,
    "completed_tasks": 38,
    "rework_percentage": 12.5,
    "rejected_count": 2,
    "delivery_ready_tasks": 35
  }
]
```

## Implementation Details

### Metric Calculations

**Total Tasks**
```python
total_tasks = len(prs)
```

**Completed Tasks**
```python
completed_tasks = sum(1 for pr in prs if pr.merged)
```

**Rework %**
```python
total_rework = sum(pr.rework_count for pr in prs)
rework_percentage = (total_rework / total_tasks * 100) if total_tasks > 0 else 0.0
```

**Rejected Count**
```python
rejected_count = sum(1 for pr in prs 
    if (pr.state == 'closed' and not pr.merged) or 
    any(l.lower() == 'rejected' for l in pr.labels))
```

**Delivery Ready Tasks**
```python
delivery_ready_tasks = sum(1 for pr in prs 
    if any(l.lower() in ['ready to merge', 'delivery ready', 'expert approved'] 
           for l in pr.labels))
```

## Files Modified

### Backend
- `backend/main.py` - Added 5 aggregation endpoints
- `backend/schemas.py` - Added `AggregationMetrics` schema

### Frontend
- `frontend/src/components/AggregationView.jsx` - Created aggregation UI
- `frontend/src/components/Sidebar.jsx` - Added "Aggregation" nav item
- `frontend/src/App.jsx` - Added routing for AggregationView

## Summary Cards
Below the table, summary cards display totals across all entries:
- Sum of total tasks
- Sum of completed tasks
- Average rework percentage
- Sum of rejected tasks
- Sum of delivery ready tasks

## Color Coding
- **Rework %**: Green (<15%), Yellow (15-30%), Red (>30%)
- **Completed**: Green text
- **Rejected**: Red text
- **Delivery Ready**: Blue text

That's it! Simple, straightforward aggregations without any external dependencies.

