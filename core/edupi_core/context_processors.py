"""
Context processors for the edu-pi project.
"""

from django.conf import settings as django_settings
from core.plugin_system.settings import SiteSettings


def site_settings(request):
    """
    Add site settings to template context.

    Returns:
        Dict with site settings for use in templates.
    """
    return {
        "ROBOT_NAME": SiteSettings.get("tinko.global.robot_name", "Tinko"),
        "SCHOOL_NAME": SiteSettings.get("tinko.global.school_name", ""),
        "SCHOOL_LOGO": SiteSettings.get("tinko.global.logo_path", ""),
        "MEDIA_URL": django_settings.MEDIA_URL,
    }
