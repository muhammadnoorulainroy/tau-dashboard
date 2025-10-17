# Domain Normalization Feature

## Overview
Domains are now normalized across the application. Recognized domains are shown by their standard name, while all unrecognized domains are grouped under "Others".

## Recognized Domains
The following domains are recognized (defined in `backend/config.py`):

1. `enterprise_wiki`
2. `finance`
3. `fund_finance`
4. `hr_experts`
5. `hr_management`
6. `hr_payroll`
7. `incident_management`
8. `it_incident_management`
9. `smart_home`

## How It Works

### Normalization Logic
- **Case-insensitive matching**: `HR_PAYROLL`, `hr_payroll`, `Hr_Payroll` all map to `hr_payroll`
- **Exact match required**: `payroll` does NOT match `hr_payroll` → goes to "Others"
- **Typos go to Others**: `hr_managment` (typo) → "Others"

### Examples

| Database Value | Normalized To |
|----------------|---------------|
| `hr_payroll` | `hr_payroll` |
| `HR_PAYROLL` | `hr_payroll` |
| `payroll` | `Others` |
| `smart_home` | `smart_home` |
| `hr_managment` (typo) | `Others` |
| `it_management` | `Others` |
| `unknown_domain` | `Others` |
| `5` | `Others` |

## API Endpoints

### 1. Get Domains List
**Endpoint:** `GET /api/domains/list`

**Returns:** Array of normalized domain names
```json
[
  "enterprise_wiki",
  "finance",
  "fund_finance",
  "hr_experts",
  "hr_management",
  "hr_payroll",
  "incident_management",
  "it_incident_management",
  "smart_home",
  "Others"
]
```

### 2. Domain Aggregation
**Endpoint:** `GET /api/aggregation/domains`

**Returns:** Metrics grouped by normalized domain
```json
[
  {
    "name": "enterprise_wiki",
    "email": null,
    "total_tasks": 45,
    "completed_tasks": 38,
    "rework_percentage": 12.5,
    "rejected_count": 2,
    "delivery_ready_tasks": 35
  },
  ...
  {
    "name": "Others",
    "total_tasks": 23,
    "completed_tasks": 18,
    ...
  }
]
```

### 3. Trainer Aggregation with Domain Filter
**Endpoint:** `GET /api/aggregation/trainers?domain=hr_payroll`

**Query Parameters:**
- `domain` (optional): Normalized domain name (e.g., "hr_payroll", "Others")

**Example:**
```bash
# All trainers
GET /api/aggregation/trainers

# Only trainers in hr_payroll domain
GET /api/aggregation/trainers?domain=hr_payroll

# Only trainers in "Others" domains
GET /api/aggregation/trainers?domain=Others
```

## Frontend Integration

### Dropdown Behavior
1. Fetches domains from `/api/domains/list`
2. Shows dropdown only in "Trainer wise" tab
3. Dropdown options:
   - "All Domains" (default)
   - All recognized domains (alphabetically)
   - "Others" (at the end)

### Filtering
- Selecting a domain filters trainers to show only those who worked in that domain
- Metrics are recalculated for the filtered domain only
- Badge shows "Filtered: {domain}" when active

## Database Schema

### No Schema Changes
The `pull_requests` table stores original domain values as-is. Normalization happens at query time, not in storage.

**Column:** `pull_requests.domain` (VARCHAR)
- Stores: Original domain from PR title
- Examples: "hr_payroll", "payroll", "HR_PAYROLL", etc.

## Implementation Details

### Backend Files Modified

1. **`config.py`**
   - Added `recognized_domains: List[str]` field
   - Contains the authoritative list of recognized domains

2. **`main.py`**
   - Added `normalize_domain(domain: str) -> str` function
   - Updated `/api/domains/list` endpoint
   - Updated `/api/aggregation/domains` endpoint
   - Updated `/api/aggregation/trainers` endpoint with domain filter

### Frontend Files Modified

1. **`AggregationView.jsx`**
   - Added domain dropdown for Trainer wise tab
   - Added domain filtering logic
   - Added "Clear Filter" button
   - Added filtered domain badge

## Configuration

To modify recognized domains, edit `backend/config.py`:

```python
recognized_domains: List[str] = [
    'enterprise_wiki',
    'finance',
    'fund_finance',
    'hr_experts',
    'hr_management',
    'hr_payroll',
    'incident_management',
    'it_incident_management',
    'smart_home'
]
```

After modifying, restart the backend server.

## Testing

### Manual Testing Steps

1. **Check domains list:**
   ```bash
   curl http://localhost:8000/api/domains/list
   ```

2. **Check domain aggregation:**
   ```bash
   curl http://localhost:8000/api/aggregation/domains
   ```

3. **Test trainer filtering:**
   ```bash
   # All trainers
   curl http://localhost:8000/api/aggregation/trainers
   
   # Filtered by domain
   curl http://localhost:8000/api/aggregation/trainers?domain=hr_payroll
   
   # Others domain
   curl http://localhost:8000/api/aggregation/trainers?domain=Others
   ```

4. **Test in UI:**
   - Navigate to Aggregation → Trainer wise
   - Select different domains from dropdown
   - Verify data updates correctly

## Performance Considerations

### Current Implementation
- Normalization happens at query time for each request
- All PRs are fetched and then filtered in memory
- Suitable for moderate dataset sizes (< 100k PRs)

### Future Optimizations (if needed)
1. Add computed column `normalized_domain` to database
2. Create database index on `normalized_domain`
3. Use SQL WHERE clause instead of Python filtering
4. Add caching layer for domain lists

## Error Handling

- Empty/null domains → normalized to "Others"
- Invalid domain values → normalized to "Others"
- Case variations → handled automatically
- Whitespace → trimmed automatically

## Sorting

### Domain List
1. Recognized domains (alphabetically)
2. "Others" (always last)

### Aggregation Results
1. Recognized domains (alphabetically)
2. "Others" (always last)

## Migration Notes

### No Database Migration Required
This feature doesn't change the database schema. It only changes how data is queried and displayed.

### Existing Data
All existing domain values in the database remain unchanged. They are normalized only when displayed.

### Backward Compatibility
The feature is fully backward compatible. No changes to existing PRs or data required.

