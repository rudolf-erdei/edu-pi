import json
import os
from pathlib import Path
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.shared import six

# Configuration
STATUS_FILE = Path("/run/tinko-update/status.json")

class SystemUpdateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        # Simple auth check (assumed handled by AuthMiddlewareStack)
        self.group_name = "system_updates"
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial status
        status = self.get_status()
        await self.send(text_data=json.dumps(status))

    async def disconnect(self):
        await self.channel_layer.group_discard(self.group_name, self.channel_name)

    def get_status(self):
        """Reads the current status from the JSON file."""
        if not STATUS_FILE.exists():
            return {"status": "idle", "stage": None}
        try:
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"status": "idle", "stage": None}

    async def update_message(self, event):
        """Handle status updates broadcast from the daemon."""
        # In this implementation, the daemon doesn't use channel_layer.group_send
        # since it's a separate process.
        # Instead, the consumer will poll the file.
        pass

    async def stream_logs(self):
        """
        The daemon writes to status.json.
        We can use a simple loop to poll the file and send updates.
        This is more efficient than a full-blown watchdog in a consumer.
        """
        # This logic is actually triggered by a separate loop or
        # the consumer simply polls.
        pass
