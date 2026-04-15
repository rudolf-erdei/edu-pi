"""
ASGI config for config project.

It exposes the ASGI callable as a module-level variable named ``application``.

For more information on this file, see
https://docs.djangoproject.com/en/4.2/howto/deployment/asgi/
"""

import os

from django.core.asgi import get_asgi_application
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.auth import AuthMiddlewareStack
from channels.security.websocket import AllowedHostsOriginValidator

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

# Import routing after Django setup
django_asgi_app = get_asgi_application()

# Import websocket routes after Django setup
from plugins.edupi.noise_monitor import routing as noise_routing
from plugins.edupi.routines import routing as routines_routing
from core.update_system import routing as update_routing

# Combine all websocket routes
websocket_urlpatterns = (
    noise_routing.websocket_urlpatterns
    + routines_routing.websocket_urlpatterns
    + update_routing.websocket_urlpatterns
)

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": AllowedHostsOriginValidator(
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
    }
)
