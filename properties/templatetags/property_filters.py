from django import template
from django.templatetags.static import static

register = template.Library()

PLACEHOLDER_PATH = 'img/property-placeholder.svg'


def _property_placeholder_url():
    """Return the global property placeholder asset."""
    return static(PLACEHOLDER_PATH)


def _field_file_url_if_exists(file_field):
    """Return a file field URL only when the underlying file exists."""
    if not file_field:
        return None

    storage = getattr(file_field, 'storage', None)
    name = getattr(file_field, 'name', None)

    if not storage or not name:
        return None

    try:
        if storage.exists(name):
            return file_field.url
    except Exception:
        return None

    return None

@register.simple_tag
def url_replace(request, field, value):
    """Replace a GET parameter in the URL while preserving others."""
    dict_ = request.GET.copy()
    dict_[field] = value
    return dict_.urlencode()

@register.filter
def get_list(value, arg):
    """Get a list from request.GET.getlist()."""
    if hasattr(value, 'getlist'):
        return value.getlist(arg)
    return []


@register.simple_tag
def property_placeholder_url():
    """Expose the placeholder asset for templates that need manual control."""
    return _property_placeholder_url()


@register.filter
def property_image_url(image):
    """Return a safe image URL for PropertyImage instances (with placeholder fallback)."""
    if not image:
        return _property_placeholder_url()

    getter = getattr(image, 'get_thumbnail_url', None)
    if callable(getter):
        url = getter()
        if url:
            return url

    file_field = getattr(image, 'image', None)
    url = _field_file_url_if_exists(file_field)
    if url:
        return url

    return _property_placeholder_url()


@register.filter
def property_primary_image_url(property_obj):
    """Return a safe URL for a property's primary image with fallback."""
    if not property_obj:
        return _property_placeholder_url()

    getter = getattr(property_obj, 'get_primary_image_url', None)
    if callable(getter):
        url = getter()
        if url:
            return url

    images_rel = getattr(property_obj, 'images', None)
    if images_rel and hasattr(images_rel, 'first'):
        image = images_rel.first()
        if image:
            return property_image_url(image)

    return _property_placeholder_url()