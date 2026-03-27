"""Template tags for plugin system."""

from django import template

register = template.Library()


@register.filter
def dict_get(d, key):
    """Get a value from a dictionary."""
    return d.get(key)
