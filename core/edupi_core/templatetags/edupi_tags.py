"""
Custom template tags for the edu-pi project.
"""

from django import template

register = template.Library()


@register.filter
def get_field(form, field_name):
    """
    Get a form field by name.

    Usage:
        {{ form|get_field:field_name }}
    """
    try:
        return form[field_name]
    except KeyError:
        return None
