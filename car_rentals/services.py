"""Domain services for car rentals.

Includes AI-based verification for user-submitted car listings.
"""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any, Dict

from ai_assistant.ai_service import AIServiceError, OpenAIAIService, TokenBudgetExceeded

logger = logging.getLogger(__name__)


def _pricing_guardrails(car) -> dict[str, Any]:
    """Detect obviously unrealistic rates to keep marketplace credible."""

    seats = Decimal(getattr(car, 'seats', 0) or 4)
    base_daily = Decimal(car.daily_price or 0)
    upper_daily = Decimal('65.00') + (seats * Decimal('25.00'))
    lower_daily = Decimal('15.00')

    issues: list[str] = []

    if base_daily <= 0:
        issues.append('Daily price must be set before we can list this car.')
    elif base_daily < lower_daily and car.service_type != 'taxi':
        issues.append('Daily price is below our safety floor for insured rentals.')
    elif base_daily > upper_daily:
        issues.append('Daily price exceeds our allowable cap for this class of car.')

    taxi_hour = Decimal(car.taxi_per_hour or 0)
    if car.service_type in ('taxi', 'both') and taxi_hour:
        taxi_cap = Decimal('90.00') + (seats * Decimal('12.00'))
        if taxi_hour > taxi_cap:
            issues.append('Hourly chauffeur rate is above our permitted ceiling for this region.')

    return {
        'approved': not issues,
        'reasons': issues,
        'source': 'pricing_guardrail'
    }


def verify_car_with_ai(car) -> Dict[str, Any]:
    """Run a quick AI authenticity check on a car listing.

    Returns a dict with keys: approved (bool), confidence (float|None), reasons (list[str]), source (str).
    """

    guardrail = _pricing_guardrails(car)
    if not guardrail['approved']:
        return {
            'approved': False,
            'confidence': 0.0,
            'reasons': guardrail['reasons'],
            'source': guardrail['source'],
        }

    try:
        service = OpenAIAIService()
    except (AIServiceError, TokenBudgetExceeded, Exception) as exc:  # pragma: no cover - runtime dependency
        logger.warning("AI verification unavailable: %s", exc)
        return {
            'approved': False,
            'confidence': None,
            'reasons': ['AI service unavailable; manual review required.'],
            'source': 'fallback',
        }

    owner = getattr(car, 'owner', None)
    owner_name = None
    if owner:
        owner_name = owner.get_full_name() or owner.username or owner.email

    car_payload = {
        'make': car.make,
        'model': car.model,
        'year': car.year,
        'license_plate': car.license_plate,
        'service_type': car.service_type,
        'company': getattr(car.company, 'name', None),
        'owner_name': owner_name,
        'owner_email': getattr(car.owner, 'email', None),
        'daily_price': float(car.daily_price or 0),
        'taxi_rate_per_km': float(car.taxi_rate_per_km or 0) if car.taxi_rate_per_km else None,
        'taxi_per_hour': float(car.taxi_per_hour or 0) if car.taxi_per_hour else None,
        'has_ac': car.has_ac,
        'has_gps': car.has_gps,
        'has_bluetooth': car.has_bluetooth,
        'has_dashcam': car.has_dashcam,
    }

    try:
        result = service.verify_car_listing(car_payload=car_payload)
        data = result.data or {}
        approved = bool(data.get('is_real')) and str(data.get('action')).lower() == 'approve'
        return {
            'approved': approved,
            'confidence': float(data.get('confidence') or 0),
            'reasons': data.get('reasons') or [],
            'source': result.provider,
        }
    except (AIServiceError, TokenBudgetExceeded) as exc:
        logger.warning("AI verification failed: %s", exc)
        return {
            'approved': False,
            'confidence': None,
            'reasons': ['AI check failed; requires manual review.'],
            'source': 'fallback',
        }
    except Exception as exc:  # pragma: no cover - unexpected
        logger.exception("Unexpected AI verification error: %s", exc)
        return {
            'approved': False,
            'confidence': None,
            'reasons': ['AI check failed unexpectedly; requires manual review.'],
            'source': 'fallback',
        }
