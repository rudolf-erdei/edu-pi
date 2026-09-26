"""Settings for the test suite.

Inherits everything from ``config.settings`` and changes exactly one thing:
the static files backend.

Production uses ``whitenoise.storage.CompressedManifestStaticFilesStorage``,
which resolves every ``{% static %}`` tag through ``staticfiles.json``. That
manifest is produced by ``collectstatic`` and only exists on a deployed
install, so under pytest any template that touches ``{% static %}`` raised::

    ValueError: Missing staticfiles manifest entry for 'images/favicon.svg'

That blocked ``home.html`` from rendering at all, which is why the dashboard
view and its JavaScript had no test coverage. The plain ``StaticFilesStorage``
resolves ``{% static %}`` to ``STATIC_URL + path`` and needs no manifest, so
templates render in tests the same way they would before a deploy.

Only the staticfiles backend is overridden. Everything else — middleware,
installed apps, database, languages — stays identical to production, so the
suite still exercises the real configuration.
"""

from config.settings import *  # noqa: F401,F403

STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage",
    },
}
