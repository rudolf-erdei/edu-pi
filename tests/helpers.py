"""Shared helpers for the Django test suite."""

import time

from core.edupi_core.settings_auth import SESSION_KEY


def login_settings(client):
    """Give a test client a live Settings session.

    The gate is tested separately in tests/test_settings_auth.py; the tests
    that exercise Settings or update behavior sign in here instead of
    restating the PIN flow.
    """
    session = client.session
    session[SESSION_KEY] = time.time()
    session.save()
    return client
