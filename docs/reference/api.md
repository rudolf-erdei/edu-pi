# API Reference

REST API endpoints for Tinko.

## Base URL

```
http://your-pi-ip:8000/
```

## Authentication

Most endpoints require Django session authentication.

Login via:
```bash
curl -X POST http://localhost:8000/admin/login/ \
  -d "username=admin&password=yourpassword&csrfmiddlewaretoken=<token>"
```

## Core Endpoints

### Plugin Management

#### List Plugins

```http
GET /admin/plugins/api/list/
```

**Response:**
```json
{
  "plugins": [
    {
      "id": "edupi.activity_timer",
      "name": "Activity Timer",
      "enabled": true,
      "version": "1.0.0"
    }
  ]
}
```

#### Toggle Plugin

```http
POST /admin/plugins/api/toggle/
Content-Type: application/json

{
  "plugin_id": "edupi.activity_timer",
  "enabled": true
}
```

### Settings

#### Get Settings

```http
GET /settings/api/get/?namespace=edupi.activity_timer
```

**Response:**
```json
{
  "settings": {
    "default_duration": 10,
    "led_brightness": 100
  }
}
```

#### Save Settings

```http
POST /settings/api/save/
Content-Type: application/json

{
  "namespace": "edupi.activity_timer",
  "settings": {
    "default_duration": 15,
    "led_brightness": 80
  }
}
```

### System Updates

#### Check for Updates

```http
GET /updates/check/
```

**Response:**
```json
{
  "available": true,
  "commits": ["abc123 Fix bug", "def456 Add feature"],
  "current_version": "v1.2.3"
}
```

#### Start Update

```http
POST /updates/start/
```

**Response (success):**
```json
{
  "update_id": 1
}
```

**Response (rate limited - 429):**
```json
{
  "error": "Updates can only be run every 5 minutes",
  "next_update_at": "2026-04-15T10:30:00Z"
}
```

**Response (already in progress - 409):**
```json
{
  "error": "Update already in progress"
}
```

#### Get Update Status

```http
GET /updates/status/
```

**Response:**
```json
{
  "status": "in_progress",
  "stage": "migrations",
  "stages_completed": ["check_git", "stop_service", "pull", "dependencies"],
  "logs": [
    {"time": "2026-04-15T10:32:01Z", "message": "Checking git repository..."},
    {"time": "2026-04-15T10:32:02Z", "message": "Git repository OK"}
  ]
}
```

### System Updates WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/updates/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Update status:', data.status, 'Stage:', data.stage);
};
```

**Message Format:**
```json
{
  "status": "in_progress",
  "stage": "pull",
  "stages_completed": ["check_git", "stop_service"],
  "logs": [
    {"time": "2026-04-15T10:32:01Z", "message": "Pulling changes..."}
  ]
}
```

### System

The settings page's **System** tab is rendered by the server; these four routes
are what it calls, plus the ones behind its buttons.

!!! warning "These endpoints require no login"
    Nothing outside `/admin/` authenticates, so any client that can reach the Pi
    can call all four. The two destructive ones are POST-only with Django's CSRF
    check, which stops a *third-party page* from triggering them — the token
    cannot be read cross-origin — but that is not a substitute for a login: a
    client that fetches `/settings/?tab=system` first gets a token, and
    `GET /settings/system/backup/` needs nothing at all and returns the entire
    database. Treat the port as trusted-network only. See
    [`ISSUES.md`](https://github.com/rudolf-erdei/edu-pi/blob/master/ISSUES.md).

#### Connected Clients

```http
GET /settings/system/clients/
```

Browsers that requested a page in the last 120 seconds, most recently seen
first. Kept in process memory: no database row, no session row, no file.

**Response:**
```json
{
  "count": 2,
  "generated_at": "2026-09-27T14:31:07+03:00",
  "clients": [
    {
      "ip": "10.42.0.14",
      "user": "",
      "route": "settings/",
      "idle_seconds": 3,
      "seen_for_seconds": 412
    }
  ]
}
```

`route` is Django's resolved route pattern, never the raw path, so no
client-supplied string is stored or returned. `user` is empty until something
signs in, which today is nobody. The registry is capped at 32 entries and drops
the least recently seen when it is full.

#### Download Backup

```http
GET /settings/system/backup/
```

Returns the archive described in
[Settings → System](../teacher/settings.md#backup) as an attachment:
`db.sqlite3` (a `VACUUM INTO` snapshot, so it includes the rows the write-ahead
log has not checkpointed), `media/` if present, and `manifest.json`.

| Answer | When |
|---|---|
| `200` + `.zip` attachment | The usual case |
| `302` back to `?tab=system` with a message | Refused: the database is larger than `BACKUP_MAX_BYTES`, there is no room in the temp directory, or the database file is missing |

The archive is built in the system temp directory, which is tmpfs on the Pi, and
the directory is removed once the response closes. A download that is cancelled
before it finishes leaves a directory behind — the sweep at the top of the next
request removes it after 15 minutes.

#### Delete Old History

```http
POST /settings/system/clean/
```

Deletes rows older than the retention windows in
[Settings → System](../teacher/settings.md#maintenance), excluding any row in a
live state. `GET` answers `405`. A missing or invalid CSRF token answers `403`.
On success, `302` to `/settings/?tab=system` with a `django.contrib.messages`
message naming the counts.

#### Compact the Database

```http
POST /settings/system/vacuum/
```

Runs SQLite's `VACUUM`, which rewrites the database file and returns the space
that deleted rows left behind. `GET` answers `405`. The statement sets a
30-second busy timeout first, because the noise monitor commits every five
seconds and the default timeout would fail those commits while the file is being
rewritten. Reports the size before and after, or that there was nothing to
reclaim.

## Plugin-Specific Endpoints

### Activity Timer

#### Get Timer Status

```http
GET /plugins/edupi/activity_timer/api/status/
```

**Response:**
```json
{
  "active": true,
  "remaining_seconds": 450,
  "total_seconds": 600,
  "preset": "Break Time"
}
```

#### Start Timer

```http
POST /plugins/edupi/activity_timer/api/start/
Content-Type: application/json

{
  "duration": 600,
  "preset_id": "break_time"
}
```

#### Pause Timer

```http
POST /plugins/edupi/activity_timer/api/pause/
```

#### Stop Timer

```http
POST /plugins/edupi/activity_timer/api/stop/
```

### Noise Monitor

#### Get Current Level

```http
GET /plugins/edupi/noise_monitor/api/level/
```

**Response:**
```json
{
  "instant": 45.2,
  "session_average": 42.8,
  "unit": "dB",
  "timestamp": "2024-01-15T10:30:00Z"
}
```

#### Get Historical Data

```http
GET /plugins/edupi/noise_monitor/api/history/?limit=50
```

**Response:**
```json
{
  "readings": [
    {
      "instant": 45.2,
      "session": 42.8,
      "timestamp": "2024-01-15T10:30:00Z"
    }
  ]
}
```

#### Get the History Chart

```http
GET /plugins/edupi/noise_monitor/chart/
```

**Response:** HTML, not JSON — the `Noise Over Time` card exactly as the
dashboard renders it, including the inline SVG. The dashboard re-fetches this
every 60 seconds and swaps it in by its `history-chart` id, which is how the
graph keeps up without a charting library. Not under `api/` for that reason: it
is a piece of page rather than data. Use `api/history/` above for data.

#### Update Profile

```http
POST /plugins/edupi/noise_monitor/api/profile/
Content-Type: application/json

{
  "profile_id": "custom",
  "yellow_threshold": 40,
  "red_threshold": 70
}
```

### Routines

#### List Routines

```http
GET /plugins/edupi/routines/api/list/
```

**Response:**
```json
{
  "routines": [
    {
      "id": 1,
      "title": "Hand Warming Exercise",
      "category": "Warm-up",
      "duration": 30
    }
  ]
}
```

#### Get Routine Status

```http
GET /plugins/edupi/routines/api/status/
```

**Response:**
```json
{
  "playing": true,
  "routine_id": 1,
  "current_line": 2,
  "total_lines": 5,
  "paused": false
}
```

#### Control Playback

```http
POST /plugins/edupi/routines/api/control/
Content-Type: application/json

{
  "action": "play|pause|next|previous|stop",
  "routine_id": 1
}
```

### Touch Piano

#### Get Piano Status

```http
GET /plugins/edupi/touch_piano/api/status/
```

**Response:**
```json
{
  "active": true,
  "volume": 80,
  "keys_pressed": [1, 3, 5],
  "session_id": "abc123"
}
```

#### Simulate Key Press (for testing)

```http
POST /plugins/edupi/touch_piano/api/key/
Content-Type: application/json

{
  "key": 1,
  "pressed": true
}
```

## WebSocket Endpoints

WebSocket connections for real-time updates.

### Connection URL

```
ws://your-pi-ip:8000/ws/{endpoint}/
```

### Noise Monitor WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/noise-monitor/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log('Noise level:', data.instant);
};
```

**Message Format:**
```json
{
  "type": "noise_update",
  "instant": 45.2,
  "session": 42.8,
  "timestamp": "2024-01-15T10:30:00Z"
}
```

### Routines WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/routines/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.type === 'line_changed') {
    console.log('Current line:', data.line_number);
  }
};
```

**Message Types:**
- `line_changed`: New line highlighted
- `playback_state`: Play/pause/stop updates
- `sync`: Full state sync

### System Updates WebSocket

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/updates/');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  if (data.status === 'completed') {
    console.log('Update complete!');
  }
};
```

**Message Format:**
```json
{
  "status": "in_progress|completed|failed",
  "stage": "pull",
  "stages_completed": ["check_git", "stop_service"],
  "logs": [
    {"time": "2026-04-15T10:32:01Z", "message": "Pulling changes..."}
  ]
}
```

## Error Responses

### 400 Bad Request

```json
{
  "error": "Invalid parameter",
  "detail": "duration must be positive integer"
}
```

### 401 Unauthorized

```json
{
  "error": "Authentication required"
}
```

### 403 Forbidden

```json
{
  "error": "Permission denied"
}
```

### 404 Not Found

```json
{
  "error": "Resource not found"
}
```

### 500 Internal Server Error

```json
{
  "error": "Internal server error"
}
```

## Rate Limiting

Default rate limits:
- 100 requests per minute per IP
- WebSocket: 10 messages per second

Headers:
```http
X-RateLimit-Limit: 100
X-RateLimit-Remaining: 95
X-RateLimit-Reset: 1640995200
```

## CORS

Cross-Origin requests allowed from:
- Same origin
- Configured in settings

Enable CORS for external access:
```python
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "https://your-app.com",
]
```

## Plugin Development

Create custom API endpoints in your plugin:

```python
# urls.py
from django.urls import path
from . import views

urlpatterns = [
    path('api/data/', views.APIView.as_view()),
]

# views.py
from django.http import JsonResponse
from django.views import View

class APIView(View):
    def get(self, request):
        data = {'message': 'Hello from plugin!'}
        return JsonResponse(data)
```

## Testing API

### Using curl

```bash
# Get status
curl http://localhost:8000/plugins/edupi/activity_timer/api/status/

# Start timer
curl -X POST http://localhost:8000/plugins/edupi/activity_timer/api/start/ \
  -H "Content-Type: application/json" \
  -d '{"duration": 300}'
```

### Using Python requests

```python
import requests

# Get noise level
response = requests.get(
    'http://localhost:8000/plugins/edupi/noise_monitor/api/level/'
)
data = response.json()
print(f"Noise: {data['instant']} dB")
```

## See Also

- [WebSocket](../developer/websocket.md) - WebSocket implementation
- [Plugin Development](../developer/plugins/tutorial.md) - Create endpoints
- [Configuration](configuration.md) - API settings
