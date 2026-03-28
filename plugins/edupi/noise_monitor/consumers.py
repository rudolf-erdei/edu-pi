"""WebSocket consumer for Noise Monitor plugin."""

import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async

from .noise_service import noise_service

logger = logging.getLogger(__name__)


class NoiseMonitorConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for real-time noise monitoring updates."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.group_name = "noise_monitor"

        # Join the noise monitor group
        await self.channel_layer.group_add(self.group_name, self.channel_name)
        await self.accept()

        # Send initial status
        levels = noise_service.get_current_levels()
        await self.send(text_data=json.dumps(levels))

        logger.info(f"WebSocket connected: {self.channel_name}")

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave the noise monitor group
        await self.channel_layer.group_discard(self.group_name, self.channel_name)
        logger.info(f"WebSocket disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            action = data.get("action")

            if action == "get_status":
                levels = noise_service.get_current_levels()
                await self.send(text_data=json.dumps(levels))
            elif action == "start_monitoring":
                # This would be handled by the view
                await self.send(text_data=json.dumps({"status": "use_http_endpoint"}))
            elif action == "stop_monitoring":
                # This would be handled by the view
                await self.send(text_data=json.dumps({"status": "use_http_endpoint"}))

        except json.JSONDecodeError:
            await self.send(text_data=json.dumps({"error": "Invalid JSON"}))
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send(text_data=json.dumps({"error": str(e)}))

    async def noise_update(self, event):
        """Handle noise level updates broadcast from the service."""
        # Send the update to the WebSocket
        await self.send(text_data=json.dumps(event["data"]))

    async def monitoring_status(self, event):
        """Handle monitoring status updates."""
        await self.send(text_data=json.dumps(event["data"]))
