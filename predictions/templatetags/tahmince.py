from datetime import timezone as dt_timezone

from django import template

register = template.Library()


@register.filter
def iso_utc(value):
    """Tarayıcının (JS Date) her yerde aynı okuduğu UTC ISO 8601 biçimi: 2026-11-05T15:30:00Z."""
    if not value:
        return ""
    return value.astimezone(dt_timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
