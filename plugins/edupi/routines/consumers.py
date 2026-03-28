"""WebSocket consumers for Routines plugin real-time sync."""

import json
import logging

from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async

from .services.routine_player import routine_player

logger = logging.getLogger(__name__)


class RoutineConsumer(AsyncWebsocketConsumer):
    """WebSocket consumer for routine playback real-time sync."""

    async def connect(self):
        """Handle WebSocket connection."""
        self.room_group_name = "routines"

        # Join room group
        await self.channel_layer.group_add(
            self.room_group_name,
            self.channel_name,
        )

        await self.accept()
        logger.info(f"Routine WebSocket client connected: {self.channel_name}")

        # Send current status
        await self.send_current_status()

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection."""
        # Leave room group
        await self.channel_layer.group_discard(
            self.room_group_name,
            self.channel_name,
        )
        logger.info(f"Routine WebSocket client disconnected: {self.channel_name}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(text_data)
            message_type = data.get("type")

            if message_type == "get_status":
                await self.send_current_status()
            elif message_type == "command":
                command = data.get("command")
                await self.handle_command(command)
            else:
                logger.warning(f"Unknown message type: {message_type}")

        except json.JSONDecodeError:
            logger.error("Invalid JSON received")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": "Invalid JSON",
                    }
                )
            )
        except Exception as e:
            logger.error(f"Error handling WebSocket message: {e}")
            await self.send(
                text_data=json.dumps(
                    {
                        "type": "error",
                        "message": str(e),
                    }
                )
            )

    async def handle_command(self, command: str):
        """Handle playback commands from WebSocket clients."""
        # Commands are handled through the view API, but we can acknowledge here
        await self.send(
            text_data=json.dumps(
                {
                    "type": "command_acknowledged",
                    "command": command,
                }
            )
        )

    async def send_current_status(self):
        """Send current playback status to client."""
        session = routine_player.get_session()

        if session:
            current_line = routine_player.get_current_line()
            current, total, percent = routine_player.get_progress()

            status_data = {
                "type": "status_update",
                "has_active_session": True,
                "session": {
                    "id": session.id,
                    "routine_id": session.routine.id,
                    "routine_title": session.routine.title,
                    "status": session.status,
                    "current_line_index": current,
                    "total_lines": total,
                    "progress_percent": percent,
                    "current_line": current_line,
                },
            }
        else:
            status_data = {
                "type": "status_update",
                "has_active_session": False,
            }

        await self.send(text_data=json.dumps(status_data))

    async def routine_line_changed(self, event):
        """Handle line change broadcast."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "line_changed",
                    "line_index": event["line_index"],
                    "line_text": event["line_text"],
                    "progress_percent": event["progress_percent"],
                }
            )
        )

    async def routine_status_changed(self, event):
        """Handle status change broadcast."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "status_changed",
                    "status": event["status"],
                    "routine_id": event.get("routine_id"),
                    "routine_title": event.get("routine_title"),
                }
            )
        )

    async def routine_completed(self, event):
        """Handle routine completion broadcast."""
        await self.send(
            text_data=json.dumps(
                {
                    "type": "completed",
                    "routine_id": event["routine_id"],
                    "routine_title": event["routine_title"],
                }
            )
        )
