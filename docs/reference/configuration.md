# Configuration Reference

Complete reference for Tinko configuration options.

## Environment Variables

Create a `.env` file in the project root:

```bash
# Development
DEBUG=True
SECRET_KEY=your-dev-secret-key-change-in-production
ALLOWED_HOSTS=localhost,127.0.0.1,0.0.0.0
TIME_ZONE=Europe/Bucharest

# Production
DEBUG=False
SECRET_KEY=complex-random-string-here
ALLOWED_HOSTS=your-domain.com,192.168.1.100
TIME_ZONE=Europe/Bucharest
```

### Required Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `SECRET_KEY` | Django secret key | Random 50+ character string |
| `DEBUG` | Debug mode | `True` or `False` |
| `ALLOWED_HOSTS` | Allowed hostnames | `localhost,127.0.0.1` |

!!! note "`ALLOWED_HOSTS` is a starting list, not the whole list"
    `config/settings.py` merges what you configure with the names the machine
    answers to at that moment: its own hostname, `.local` (Django's subdomain
    wildcard, which covers the mDNS name `tinko.local`) and the address of the
    interface that reaches the network. The installer can only record the
    address it sees at install time, and on DHCP that goes stale — the field Pi
    was installed at `192.168.68.63` and later came up on `.66`, which answered
    `400 Bad Request` until every process started deriving it. Nothing you add
    here is ever removed, so this stays the place to list extra names.

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIME_ZONE` | UTC | Local timezone |
| `DATABASE_URL` | sqlite:///db.sqlite3 | Database connection |
| `STATIC_ROOT` | staticfiles/ | Static files directory |
| `MEDIA_ROOT` | media/ | Uploaded files directory |

### Uploaded Files Are Served in Production Too

`STATIC_ROOT` (the CSS, JS and icons that ship with the code) is served by
WhiteNoise, which indexes it at startup. `MEDIA_ROOT` (the school logo, and the
audio the routines plugin generates) is different: it is written by the running
application, so it is served by the app itself from `MEDIA_URL`, through the
`media` URL pattern in `config/urls.py`. The pattern is built from `MEDIA_URL`,
so changing the setting moves the route with it.

This matters because WhiteNoise can only serve files that existed when the
service started: a logo uploaded through Settings would 404 until the next
restart. The route is not gated on `DEBUG` — a Pi runs with `DEBUG=False`, and
gating it there is what made logo uploads appear to do nothing.

## Django Settings

Key settings in `config/settings.py`:

### Database Configuration

```python
# SQLite (default)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

# PostgreSQL (production)
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'tinko',
        'USER': 'tinko',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
    }
}
```

### Static Files

```python
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
```

### Media Files

```python
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'
```

### Security Settings

```python
# Production only
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_BROWSER_XSS_FILTER = True
X_FRAME_OPTIONS = 'DENY'
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
```

## Plugin Settings

Settings are stored with namespaces:

### Global Settings

- `tinko.global.school_name`
- `tinko.global.school_logo`
- `tinko.global.robot_name`

### Plugin Settings

- `{author}.{plugin}.{setting_key}`
- Example: `edupi.activity_timer.default_duration`

## Systemd Service

Production service configuration (`/etc/systemd/system/tinko.service`). The
install and update scripts write this file — `$USER` is the service user and
`$INSTALL_DIR` the repository checkout — so do not hand-edit it; edit the
heredoc in `install-raspberry-pi.sh`, `update.sh` and `update-web.sh` instead.

```ini
[Unit]
Description=Tinko Educational Platform
After=network.target
# StartLimit* belong in [Unit]; in [Service] systemd ignores them.
StartLimitIntervalSec=60
StartLimitBurst=5

[Service]
Type=simple
User=$USER
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$HOME/.local/bin:/usr/local/bin:/usr/bin:/bin"
Environment="PYTHONPATH=$INSTALL_DIR"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=$UV_PATH run python manage.py collectstatic --noinput
ExecStart=$UV_PATH run daphne -b 0.0.0.0 -p 80 \
  -e ssl:443:privateKey=/etc/tinko-portal/key.pem:certKey=/etc/tinko-portal/cert.pem \
  config.asgi:application
AmbientCapabilities=CAP_NET_BIND_SERVICE
CapabilityBoundingSet=CAP_NET_BIND_SERVICE CAP_SETUID CAP_SETGID CAP_AUDIT_WRITE
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

Migrations run at update time, not at service start, to keep boot fast.

`AmbientCapabilities` is what lets daphne bind ports 80 and 443 without
`setcap`. The `CAP_SETUID`/`CAP_SETGID` pair is there because a bounding set
also clamps what a *setuid* binary gains, and `sudo` is setuid root: without
them, every `sudo` call the app makes fails with *unable to change to root gid*.
Full explanation, and what these capabilities do not protect against, in
[Update System](update-system.md#services-capabilities-and-root-access).

## Update Service

`/etc/systemd/system/tinko-update.service` is a root-owned, stdlib-only daemon
that runs web updates and owns the status file the dashboard reads. It is
installed by `setup_update_infrastructure()` in `scripts/update_infra.sh`, along
with the sudoers rules and the power helper. See
[Update System](update-system.md).

## Logging Configuration

```python
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': 'tinko.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console', 'file'],
        'level': 'INFO',
    },
}
```

## WebSocket Configuration

```python
# config/asgi.py
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

application = ProtocolTypeRouter({
    'http': get_asgi_application(),
    'websocket': URLRouter(
        # Your WebSocket routes
    ),
})
```

## Cache Configuration

```python
# Local memory (development)
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.locmem.LocMemCache',
    }
}

# Redis (production)
CACHES = {
    'default': {
        'BACKEND': 'django_redis.cache.RedisCache',
        'LOCATION': 'redis://127.0.0.1:6379/1',
    }
}
```

## Internationalization

```python
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'Europe/Bucharest'
USE_I18N = True
USE_L10N = True
USE_TZ = True

LANGUAGES = [
    ('en', 'English'),
    ('ro', 'Romanian'),
]

LOCALE_PATHS = [
    BASE_DIR / 'locale',
]
```

## Security Headers

```python
# config/settings.py

# Content Security Policy
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "'unsafe-inline'")
CSP_SCRIPT_SRC = ("'self'", "'unsafe-inline'")

# CORS (if needed)
CORS_ALLOWED_ORIGINS = [
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]
```

## Email Configuration

```python
# SMTP
EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.gmail.com'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'your-email@gmail.com'
EMAIL_HOST_PASSWORD = 'your-password'
DEFAULT_FROM_EMAIL = 'Tinko <your-email@gmail.com>'

# Console (development)
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

## File Upload Limits

```python
# Maximum upload size (100MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600

# Upload handlers
FILE_UPLOAD_HANDLERS = [
    'django.core.files.uploadhandler.MemoryFileUploadHandler',
    'django.core.files.uploadhandler.TemporaryFileUploadHandler',
]
```

## Session Configuration

```python
SESSION_ENGINE = 'django.contrib.sessions.backends.db'
SESSION_COOKIE_AGE = 1209600  # 2 weeks
SESSION_COOKIE_SECURE = True  # HTTPS only
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
```

## CSRF Protection

```python
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_HTTPONLY = True
CSRF_TRUSTED_ORIGINS = [
    'https://your-domain.com',
]
```

## Performance Tuning

```python
# Database connection pooling
DATABASES = {
    'default': {
        # ...
        'CONN_MAX_AGE': 600,  # 10 minutes
    }
}

# Template caching
TEMPLATES = [{
    # ...
    'OPTIONS': {
        'loaders': [
            ('django.template.loaders.cached.Loader', [
                'django.template.loaders.filesystem.Loader',
                'django.template.loaders.app_directories.Loader',
            ]),
        ],
    },
}]
```

## Development vs Production

### Development Settings

```python
DEBUG = True
ALLOWED_HOSTS = ['*']
SECRET_KEY = 'dev-key-not-for-production'
EMAIL_BACKEND = 'django.core.mail.backends.console.EmailBackend'
```

### Production Settings

```python
DEBUG = False
ALLOWED_HOSTS = ['your-domain.com']
SECRET_KEY = os.environ['SECRET_KEY']
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 3600
```

## Environment-Specific Settings

Create separate settings files:

```
config/
├── settings/
│   ├── __init__.py
│   ├── base.py       # Common settings
│   ├── development.py
│   └── production.py
```

Switch with:
```bash
export DJANGO_SETTINGS_MODULE=config.settings.production
```

## See Also

- [Troubleshooting](troubleshooting.md) - Common issues
- [Installation](../teacher/installation.md) - Setup guide
- [Plugin Development](../developer/plugins/tutorial.md) - Create plugins
