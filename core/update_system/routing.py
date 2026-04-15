from django.urls import re_path
from .consumers import SystemUpdateConsumer

websocket_urlpatterns = [
    re_path(r"ws/updates/$", SystemUpdateConsumer.as_asgi()),
]