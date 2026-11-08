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
        # `or` rather than the get() default: the settings form can save an
        # empty string, and get() only falls back when the row is missing.
        # Taken literally, a blank robot name erases the brand from the
        # navbar and the dashboard hero.
        "ROBOT_NAME": SiteSettings.get("tinko.global.robot_name") or "Tinko",
        "SCHOOL_NAME": SiteSettings.get("tinko.global.school_name", ""),
        "SCHOOL_LOGO": SiteSettings.get("tinko.global.logo_path", ""),
        "MEDIA_URL": django_settings.MEDIA_URL,
    }
