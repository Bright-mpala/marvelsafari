from django import template

register = template.Library()


@register.filter(name="add_class")
def add_class(field, css_classes: str):
    """Safely append CSS classes to a form field's widget in templates.

    Usage: {{ field|add_class:"my-css classes" }}
    """
    if not hasattr(field, "field"):
        return field

    existing = field.field.widget.attrs.get("class", "")
    if existing:
        combined = f"{existing} {css_classes}"
    else:
        combined = css_classes

    return field.as_widget(attrs={"class": combined})
