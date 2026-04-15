# WebSocket Integration

WebSocket support for real-time communication in Tinko.

## Overview

Tinko uses Django Channels for WebSocket support, enabling real-time updates for plugins like Noise Monitor and Routines.

## WebSocket Endpoints

### Existing Endpoints

| Endpoint | URL | Purpose |
|----------|-----|---------|
| Noise Monitor | `ws://host:8000/ws/noise-monitor/` | Real-time noise levels |
| Routines | `ws://host:8000/ws/routines/` | Routine playback sync |
| System Updates | `ws://host:8000/ws/updates/` | Real-time update progress |

## Creating WebSocket Consumers

### Step 1: Create Consumer

**File:** `plugins/acme/myplugin/consumers.py`

```python
import json
from channels.generic.websocket import AsyncWebsocketConsumer

class MyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        """Client connected."""
        await self.accept()
        await self.send(json.dumps({
            'type': 'connected',
            'message': 'WebSocket connected'
        }))
    
    async def disconnect(self, close_code):
        """Client disconnected."""
        pass
    
    async def receive(self, text_data):
        """Receive message from client."""
        data = json.loads(text_data)
        message = data.get('message', '')
        
        # Process message
        response = {
            'type': 'response',
            'message': f'Received: {message}'
        }
        
        await self.send(json.dumps(response))
```

### Step 2: Create Routing

**File:** `plugins/acme/myplugin/routing.py`

```python
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'ws/myplugin/$', consumers.MyConsumer.as_asgi()),
]
```

### Step 3: Register in ASGI

**File:** `config/asgi.py`

```python
import os
from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

# Import routing
from plugins.acme.myplugin import routing as myplugin_routing

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': AuthMiddlewareStack(
        URLRouter(
            myplugin_routing.websocket_urlpatterns
        )
    ),
})
```

### Step 4: Register in Plugin

**File:** `plugins/acme/myplugin/plugin.py`

```python
def register(self):
    # Register WebSocket routing
    from . import routing
    self.register_websocket_routing(routing.websocket_urlpatterns)
```

## Broadcasting Messages

### Send to Group

```python
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()

# Send to group
async_to_sync(channel_layer.group_send)(
    'myplugin_updates',
    {
        'type': 'update_data',
        'data': {'value': 42}
    }
)
```

### Consumer Group Methods

```python
class MyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        # Join group
        await self.channel_layer.group_add(
            'myplugin_updates',
            self.channel_name
        )
    
    async def disconnect(self, close_code):
        # Leave group
        await self.channel_layer.group_discard(
            'myplugin_updates',
            self.channel_name
        )
    
    async def update_data(self, event):
        """Handle group message."""
        data = event['data']
        await self.send(json.dumps({
            'type': 'update',
            'data': data
        }))
```

## JavaScript Client

### Connecting

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/myplugin/');

ws.onopen = function() {
    console.log('WebSocket connected');
};

ws.onmessage = function(event) {
    const data = JSON.parse(event.data);
    console.log('Received:', data);
    
    if (data.type === 'update') {
        updateUI(data.data);
    }
};

ws.onclose = function() {
    console.log('WebSocket closed');
    // Reconnect logic
    setTimeout(connect, 3000);
};

ws.onerror = function(error) {
    console.error('WebSocket error:', error);
};
```

### Sending Messages

```javascript
// Send data to server
ws.send(JSON.stringify({
    message: 'Hello server'
}));
```

### Auto-Reconnect

```javascript
let ws;
let reconnectInterval = 3000;

function connect() {
    ws = new WebSocket('ws://localhost:8000/ws/myplugin/');
    
    ws.onclose = function() {
        setTimeout(connect, reconnectInterval);
    };
}

connect();
```

## Best Practices

### Error Handling

```python
class MyConsumer(AsyncWebsocketConsumer):
    async def receive(self, text_data):
        try:
            data = json.loads(text_data)
            # Process data
        except json.JSONDecodeError:
            await self.send(json.dumps({
                'error': 'Invalid JSON'
            }))
        except Exception as e:
            await self.send(json.dumps({
                'error': str(e)
            }))
```

### Rate Limiting

```python
import time

class MyConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.last_message_time = time.time()
        await self.accept()
    
    async def receive(self, text_data):
        # Rate limit: max 10 messages/second
        now = time.time()
        if now - self.last_message_time < 0.1:
            await self.send(json.dumps({
                'error': 'Rate limit exceeded'
            }))
            return
        
        self.last_message_time = now
        # Process message
```

### Authentication

```python
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

class AuthConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope["user"]
        if self.user.is_anonymous:
            await self.close()
        else:
            await self.accept()
```

## Configuration

### Channel Layer

**File:** `config/settings.py`

```python
# In-memory channel layer (development)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels.layers.InMemoryChannelLayer'
    }
}

# Redis channel layer (production)
CHANNEL_LAYERS = {
    'default': {
        'BACKEND': 'channels_redis.core.RedisChannelLayer',
        'CONFIG': {
            'hosts': [('127.0.0.1', 6379)],
        },
    },
}
```

### Install Redis

```bash
# Ubuntu/Debian
sudo apt-get install redis-server

# Start Redis
sudo systemctl start redis
```

## Testing WebSocket

### Using Python

```python
import pytest
from channels.testing import WebsocketCommunicator
from myproject.asgi import application

@pytest.mark.asyncio
async def test_my_consumer():
    communicator = WebsocketCommunicator(
        application, 
        '/ws/myplugin/'
    )
    connected, subprotocol = await communicator.connect()
    assert connected
    
    # Send message
    await communicator.send_json_to({
        'message': 'Hello'
    })
    
    # Receive response
    response = await communicator.receive_json_from()
    assert response['type'] == 'response'
    
    await communicator.disconnect()
```

## Troubleshooting

### Connection Refused

- Check ASGI server is running (Daphne)
- Verify URL path is correct
- Check firewall settings

### Messages Not Received

- Verify consumer is registered
- Check group names match
- Look for channel layer errors

### Performance Issues

- Use Redis channel layer for production
- Implement rate limiting
- Close unused connections

## See Also

- [Django Channels Documentation](https://channels.readthedocs.io/)
- [Plugin Tutorial](plugins/tutorial.md) - Create plugins
- [Testing](testing.md) - Test WebSocket consumers
