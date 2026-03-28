"""WebSocket routing configuration for Routines plugin."""

from django.urls import re_path

from . import consumers

websocket_urlpatterns = [
    re_path(r"ws/routines/$", consumers.RoutineConsumer.as_asgi()),
]
