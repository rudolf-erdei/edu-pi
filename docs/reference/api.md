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
