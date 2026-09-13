import asyncio
import json
from pathlib import Path
from channels.generic.websocket import AsyncWebsocketConsumer

# Configuration
STATUS_FILE = Path("/run/tinko-update/status.json")

class SystemUpdateConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        await self.accept()
        # Push live status to this client every second. The daemon is a
        # separate process and cannot broadcast over the channels layer, so
        # we poll the status file the daemon owns.
        self._poll_task = asyncio.ensure_future(self._poll_status())

    async def disconnect(self, code):
        if hasattr(self, "_poll_task"):
            self._poll_task.cancel()

    def get_status(self):
        """Reads the current status from the JSON file."""
        if not STATUS_FILE.exists():
            return {"status": "idle", "stage": None}
        try:
            with open(STATUS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {"status": "idle", "stage": None}

    async def _poll_status(self):
        try:
            while True:
                await self.send(text_data=json.dumps(self.get_status()))
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            pass
