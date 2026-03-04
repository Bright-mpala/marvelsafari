from django import template

register = template.Library()


AMENITY_ICON_MAP = {
    "wifi": "fa-wifi",
    "free_wifi": "fa-wifi",
    "internet": "fa-globe",
    "pool": "fa-person-swimming",
    "swimming_pool": "fa-person-swimming",
    "spa": "fa-spa",
    "gym": "fa-dumbbell",
    "fitness_center": "fa-dumbbell",
    "parking": "fa-square-parking",
    "valet_parking": "fa-car",
    "restaurant": "fa-utensils",
    "bar": "fa-martini-glass",
    "breakfast_included": "fa-mug-saucer",
    "breakfast": "fa-mug-hot",
    "air_conditioning": "fa-snowflake",
    "heating": "fa-fire",
    "laundry": "fa-soap",
    "pet_friendly": "fa-paw",
    "pets_allowed": "fa-paw",
    "kids_club": "fa-children",
    "family_rooms": "fa-people-roof",
    "airport_shuttle": "fa-shuttle-plane",
    "car_rental": "fa-car",
    "concierge": "fa-bell-concierge",
    "room_service": "fa-bell",
    "security": "fa-shield-halved",
    "business_center": "fa-briefcase",
    "meeting_room": "fa-handshake",
    "beachfront": "fa-umbrella-beach",
    "balcony": "fa-house-chimney",
    "kitchen": "fa-kitchen-set",
    "smoke_free": "fa-ban-smoking",
}


def _normalize_icon(value: str | None) -> str | None:
    if not value:
        return None
    icon = value.strip()
    if not icon:
        return None
    return icon if icon.startswith("fa-") else f"fa-{icon}"


@register.filter(name="amenity_icon")
def amenity_icon(amenity) -> str:
    """Return a font-awesome class for the given amenity."""
    if amenity is None:
        return "fa-circle-check"

    # Honor explicit icon on the model first
    explicit_icon = _normalize_icon(getattr(amenity, "icon", None))
    if explicit_icon:
        return explicit_icon

    candidates: list[str] = []
    slug = getattr(amenity, "slug", "") or ""
    name = getattr(amenity, "name", "") or ""

    def _variations(val: str) -> list[str]:
        val = val.lower().strip()
        if not val:
            return []
        normalized = [val]
        normalized.append(val.replace(" ", "_"))
        normalized.append(val.replace("-", "_"))
        normalized.append(val.replace(".", "_"))
        return list(dict.fromkeys(normalized))  # preserve order, dedupe

    candidates.extend(_variations(slug))
    candidates.extend(_variations(name))

    for candidate in candidates:
        if candidate in AMENITY_ICON_MAP:
            return AMENITY_ICON_MAP[candidate]

    return "fa-circle-check"
