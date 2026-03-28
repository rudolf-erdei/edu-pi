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

### Optional Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TIME_ZONE` | UTC | Local timezone |
| `DATABASE_URL` | sqlite:///db.sqlite3 | Database connection |
| `STATIC_ROOT` | staticfiles/ | Static files directory |
| `MEDIA_ROOT` | media/ | Uploaded files directory |

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

Production service configuration (`/etc/systemd/system/tinko.service`):

```ini
[Unit]
Description=Tinko Educational Platform
After=network.target

[Service]
Type=simple
User=pi
WorkingDirectory=/home/pi/edu-pi
Environment="PATH=/home/pi/.local/bin"
Environment="PYTHONPATH=/home/pi/edu-pi"
Environment="DJANGO_SETTINGS_MODULE=config.settings"
Environment="EDUPI_DEBUG=False"
ExecStartPre=/home/pi/.cargo/bin/uv run python manage.py migrate --noinput
ExecStartPre=/home/pi/.cargo/bin/uv run python manage.py collectstatic --noinput
ExecStart=/home/pi/.cargo/bin/uv run daphne -b 0.0.0.0 -p 8000 config.asgi:application
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

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
