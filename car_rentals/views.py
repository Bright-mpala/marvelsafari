# views.py - Updated

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.mail import send_mail
from django.core.paginator import Paginator
from django.db.models import Q, Prefetch, Min, Count, Avg, Sum, Case, When, IntegerField
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_GET
from datetime import timedelta
from decimal import Decimal
from typing import Any
from types import SimpleNamespace

from .models import (
    Car,
    CarCategory,
    CarDriver,
    CarImage,
    CarLocationTracker,
    CarRentalBooking,
    CarRentalCompany,
    CarDriverReview,
    CarStatus,
    OperationalStatus,
    RentalLocation,
    RentalRate,
    TaxiBooking,
)
from .forms import (
    CarDriverReviewForm,
    CarEditForm,
    CarRentalBookingForm,
    CarReviewForm,
    CarSubmissionForm,
    TaxiBookingForm,
)
from .services import verify_car_with_ai

logger = logging.getLogger(__name__)

CAR_LISTING_TEMPLATES: dict[str, dict[str, Any]] = {
    'prado_tx_l': {
        'label': 'Toyota Land Cruiser Prado TX-L',
        'summary': '7-seater safari SUV with fridge, snorkel, and chauffeur option.',
        'initial': {
            'make': 'Toyota',
            'model': 'Land Cruiser Prado TX-L',
            'year': 2022,
            'color': 'Pearl White',
            'service_type': 'both',
            'daily_price': Decimal('185.00'),
            'seats': 7,
            'transmission': 'automatic',
            'fuel_type': 'diesel',
            'has_driver': True,
        },
    },
    'defender_110_xd': {
        'label': 'Land Rover Defender 110 X-Dynamic',
        'summary': 'Overlanding build with snorkel, dual roof racks, and recovery kit.',
        'initial': {
            'make': 'Land Rover',
            'model': 'Defender 110 X-Dynamic',
            'year': 2023,
            'color': 'Gunmetal Grey',
            'service_type': 'rental',
            'daily_price': Decimal('260.00'),
            'seats': 5,
            'transmission': 'automatic',
            'fuel_type': 'diesel',
            'has_driver': False,
        },
    },
    'hiace_safari': {
        'label': 'Toyota Hiace High-Roof Safari Van',
        'summary': '9-passenger pop-up roof van optimized for Nairobi National Park runs.',
        'initial': {
            'make': 'Toyota',
            'model': 'Hiace Safari',
            'year': 2021,
            'color': 'Safari Beige',
            'service_type': 'both',
            'daily_price': Decimal('140.00'),
            'seats': 9,
            'transmission': 'manual',
            'fuel_type': 'diesel',
            'has_driver': True,
        },
    },
}

CAR_FEATURE_GROUPS: list[dict[str, Any]] = [
    {
        'label': 'Comfort & Safety',
        'items': [
            {'field': 'has_ac', 'label': 'Air conditioning'},
            {'field': 'has_child_seat', 'label': 'Child seat available'},
        ],
    },
    {
        'label': 'Navigation & Visibility',
        'items': [
            {'field': 'has_gps', 'label': 'GPS tracking'},
            {'field': 'has_dashcam', 'label': 'Dashcam installed'},
        ],
    },
    {
        'label': 'Connectivity & Power',
        'items': [
            {'field': 'has_bluetooth', 'label': 'Bluetooth audio'},
            {'field': 'has_usb', 'label': 'USB charging'},
            {'field': 'has_wifi', 'label': 'Onboard WiFi'},
        ],
    },
]

FALLBACK_CAR_CATEGORY_DATA: list[dict[str, Any]] = [
    {
        'name': 'Executive Sedan',
        'fuel_type': 'Petrol',
        'transmission': 'Automatic',
        'description': 'Leather-trimmed saloon ideal for airport and embassy transfers.',
        'passenger_capacity': 4,
        'luggage_capacity': 3,
        'active_cars': 18,
    },
    {
        'name': 'Safari SUV',
        'fuel_type': 'Diesel',
        'transmission': 'Automatic',
        'description': 'Raised suspension with dual fuel tanks, fridge, and roof rails.',
        'passenger_capacity': 7,
        'luggage_capacity': 5,
        'active_cars': 42,
    },
    {
        'name': 'High-Roof Van',
        'fuel_type': 'Diesel',
        'transmission': 'Manual',
        'description': 'Pop-up roof Hiace with inverter sockets and 360° swivels.',
        'passenger_capacity': 9,
        'luggage_capacity': 8,
        'active_cars': 25,
    },
    {
        'name': 'Luxury Minibus',
        'fuel_type': 'Diesel',
        'transmission': 'Automatic',
        'description': 'Full-height coaster with onboard WiFi and fridge for expedition crews.',
        'passenger_capacity': 22,
        'luggage_capacity': 15,
        'active_cars': 11,
    },
]

FALLBACK_LOCATION_DATA: list[dict[str, Any]] = [
    {
        'name': 'JKIA Terminal 1E Meet & Greet',
        'city': 'Nairobi',
        'country': 'Kenya',
        'address': 'Jomo Kenyatta International Airport, Terminal 1E arrivals lane',
        'location_type': 'Airport Counter',
    },
    {
        'name': 'Wilson Airport Safari Centre',
        'city': 'Nairobi',
        'country': 'Kenya',
        'address': 'Langata Rd, gate B next to Hangar 7',
        'location_type': 'Airport Counter',
    },
    {
        'name': 'Arusha Clock Tower Pickup',
        'city': 'Arusha',
        'country': 'Tanzania',
        'address': 'Clock Tower Roundabout, Boma Rd',
        'location_type': 'Downtown Hub',
    },
    {
        'name': 'Serengeti Naabi Hill Gate',
        'city': 'Serengeti',
        'country': 'Tanzania',
        'address': 'Naabi Hill Main Gate, Serengeti National Park',
        'location_type': 'Park Gate',
    },
    {
        'name': 'Entebbe Victoria Mall Forecourt',
        'city': 'Entebbe',
        'country': 'Uganda',
        'address': 'Berkeley Rd, outside Victoria Mall main gate',
        'location_type': 'Downtown Hub',
    },
    {
        'name': 'Kigali Serena Hotel Portico',
        'city': 'Kigali',
        'country': 'Rwanda',
        'address': 'Boulevard de la Revolution, Serena main portico',
        'location_type': 'Hotel Lobby',
    },
]

FALLBACK_AMENITY_COUNTS: dict[str, int] = {
    'has_ac': 64,
    'has_child_seat': 18,
    'has_gps': 37,
    'has_dashcam': 29,
    'has_bluetooth': 58,
    'has_usb': 61,
    'has_wifi': 33,
}

# views.py - Update the car_list function

# views.py - Update the car_list function

def _safe_send_mail(subject, message, recipients):
    """Best-effort email helper that fails silently in prod."""
    if not recipients:
        return
    try:
        send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, recipients)
    except Exception as exc:  # pragma: no cover - logging only
        logger.warning("Email send failed: %s", exc)


def _get_or_create_user_company(user):
    """Ensure the submitting user has a company record to attach listings to."""
    code = f"USR{user.id}"
    defaults = {
        'name': user.get_full_name() or user.email or f"User {user.id}",
        'offers_rental': True,
        'offers_taxi': True,
        'is_active': True,
    }
    company, _ = CarRentalCompany.objects.get_or_create(code=code, defaults=defaults)
    return company


def _category_snapshot(data: dict[str, Any]) -> SimpleNamespace:
    """Provide an object with the same template-facing API as a real CarCategory."""
    return SimpleNamespace(
        name=data['name'],
        description=data['description'],
        passenger_capacity=data['passenger_capacity'],
        luggage_capacity=data['luggage_capacity'],
        active_cars=data['active_cars'],
        get_fuel_type_display=lambda value=data['fuel_type']: value,
        get_transmission_display=lambda value=data['transmission']: value,
    )


def _location_snapshot(data: dict[str, Any]) -> SimpleNamespace:
    """Mirror the attributes provided by RentalLocation for the template layer."""
    return SimpleNamespace(
        name=data['name'],
        city=data['city'],
        address=data['address'],
        get_country_display=lambda value=data['country']: value,
        get_location_type_display=lambda value=data['location_type']: value,
    )


def _build_amenity_groups() -> list[dict[str, Any]]:
    """Summarize amenity availability across the fleet for display."""
    amenity_fields = [item['field'] for group in CAR_FEATURE_GROUPS for item in group['items']]
    if not amenity_fields:
        return []

    aggregate_kwargs = {
        f"{field}_count": Sum(
            Case(When(**{field: True}, then=1), default=0, output_field=IntegerField())
        )
        for field in amenity_fields
    }
    feature_counts = {
        key: value or 0
        for key, value in Car.objects.filter(is_deleted=False).aggregate(**aggregate_kwargs).items()
    }

    if not any(feature_counts.values()):
        for field in amenity_fields:
            feature_counts[f"{field}_count"] = FALLBACK_AMENITY_COUNTS.get(field, 0)

    amenity_groups = []
    for group in CAR_FEATURE_GROUPS:
        amenity_groups.append(
            {
                'label': group['label'],
                'items': [
                    {
                        **item,
                        'count': feature_counts.get(f"{item['field']}_count") or 0,
                    }
                    for item in group['items']
                ],
            }
        )
    return amenity_groups


def car_list(request):
    """Main landing page — rental cars + taxi tab."""
    service = request.GET.get('service', 'rental')  # 'rental' or 'taxi'
    pickup = (request.GET.get('pickup_location') or '').strip()
    car_type = (request.GET.get('car_type') or '').strip()
    transmission = (request.GET.get('transmission') or '').strip()
    fuel_type = (request.GET.get('fuel_type') or '').strip()
    min_seats = request.GET.get('min_seats')
    sort_by = request.GET.get('sort', 'recommended')

    # Build queryset based on service type - REMOVE moderation_status filter for testing
    rental_services = ['rental', 'both', '']
    taxi_services = ['taxi', 'both']

    if service == 'taxi':
        service_filter = taxi_services
    elif service == 'rental':
        service_filter = rental_services
    else:  # show all service types
        service_filter = rental_services + taxi_services

    base_qs = Car.objects.select_related(
        'company', 'category', 'current_location'
    ).prefetch_related(
        'images', 'assigned_drivers'
    ).filter(
        service_type__in=service_filter,
        is_deleted=False,
        status=OperationalStatus.AVAILABLE,  # Only show available cars
    )

    # Only show approved cars to public, owners can see their own pending cars
    if request.user.is_authenticated:
        qs = base_qs.filter(
            Q(moderation_status=CarStatus.APPROVED) | Q(owner=request.user)
        )
    else:
        qs = base_qs.filter(moderation_status=CarStatus.APPROVED)


    # Rest of the function remains the same...
    

    # Filters
    if pickup:
        qs = qs.filter(
            Q(company__name__icontains=pickup) |
            Q(current_location__city__icontains=pickup) |
            Q(current_location__name__icontains=pickup) |
            Q(current_location__address__icontains=pickup)
        )

    if car_type:
        qs = qs.filter(
            Q(category__code__iexact=car_type) |
            Q(category__name__icontains=car_type)
        )

    if transmission:
        qs = qs.filter(category__transmission=transmission)

    if fuel_type:
        qs = qs.filter(category__fuel_type=fuel_type)

    if min_seats:
        try:
            qs = qs.filter(seats__gte=int(min_seats))
        except (ValueError, TypeError):
            pass

    # Sorting
    if sort_by == 'price_low':
        qs = qs.order_by('daily_price', 'make')
    elif sort_by == 'price_high':
        qs = qs.order_by('-daily_price', 'make')
    elif sort_by == 'newest':
        qs = qs.order_by('-year', 'make')
    elif sort_by == 'rating':
        qs = qs.order_by('-average_rating', '-review_count', '-company__customer_rating', 'make')
    else:
        qs = qs.order_by('-is_featured', '-company__customer_rating', 'make')

    qs = qs.distinct()

    paginator = Paginator(qs, 12)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    cars = list(page_obj.object_list)

    # Attach rate info
    for car in cars:
        if service == 'taxi':
            car.display_daily_rate = car.taxi_per_hour or car.taxi_rate_per_km
            car.display_currency = 'USD'
            car.rate_label = '/hr' if car.taxi_per_hour else '/km'
        else:
            car.display_daily_rate = car.daily_price
            car.display_currency = 'USD'
            car.rate_label = '/day'
        car.function_label = car.get_usage_function_display()

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    active_filters = []
    if pickup:
        active_filters.append({'label': 'Location', 'value': pickup})
    if car_type:
        active_filters.append({'label': 'Category', 'value': car_type.title()})
    if transmission:
        active_filters.append({'label': 'Transmission', 'value': transmission.title()})
    if fuel_type:
        active_filters.append({'label': 'Fuel', 'value': fuel_type.title()})
    if min_seats:
        active_filters.append({'label': 'Min Seats', 'value': min_seats})

    categories = CarCategory.objects.filter(is_active=True).order_by('display_order')

    # Top rated drivers for taxi tab
    top_drivers = []
    if service == 'taxi':
        top_drivers = CarDriver.objects.filter(
            is_active=True,
            is_available=True
        ).order_by('-average_rating', '-review_count')[:6]

    context = {
        'cars': cars,
        'page_obj': page_obj,
        'total_cars': paginator.count,
        'query_string': query_string,
        'active_filters': active_filters,
        'service': service,
        'categories': categories,
        'sort_by': sort_by,
        'top_drivers': top_drivers,
    }
    return render(request, 'car_rentals/car_list.html', context)


@login_required
def car_submission(request):
    """Allow authenticated users to submit a car listing for review."""
    company = _get_or_create_user_company(request.user)
    template_key = request.GET.get('template') or None
    template_meta = CAR_LISTING_TEMPLATES.get(template_key)
    template_initial = template_meta['initial'] if template_meta else {}

    # Enforce a per-owner cap to prevent spammy uploads
    existing_count = Car.objects.filter(owner=request.user, is_deleted=False).count()
    if existing_count >= 10:
        messages.error(
            request,
            'You have reached your limit of 10 car listings. Remove or archive one before adding another.'
        )
        return redirect('car_rentals:my_listings')

    if request.method == 'POST':
        form = CarSubmissionForm(request.POST, request.FILES, company=company)
        if form.is_valid():
            car = form.save(commit=False)
            car.owner = request.user
            car.company = company
            car.moderation_status = CarStatus.PENDING
            car.status = OperationalStatus.AVAILABLE

            if car.service_type == 'rental':
                car.taxi_base_fare = None
                car.taxi_rate_per_km = None
                car.taxi_per_hour = None

            company.offers_rental = car.service_type in ('rental', 'both') or company.offers_rental
            company.offers_taxi = car.service_type in ('taxi', 'both') or company.offers_taxi
            company.save(update_fields=['offers_rental', 'offers_taxi'])

            car.save()

            gallery_files = form.cleaned_data.get('gallery_images') or []
            for order, image_file in enumerate(gallery_files[:5], start=1):
                CarImage.objects.create(
                    car=car,
                    image=image_file,
                    is_primary=False,
                    display_order=order,
                )

            # AI-driven authenticity check with safe fallback to manual review
            ai_outcome = verify_car_with_ai(car)
            if ai_outcome.get('approved'):
                car.moderation_status = CarStatus.APPROVED
                car.save(update_fields=['moderation_status'])
                messages.success(
                    request,
                    'Your car cleared compliance instantly and is now live for travelers.'
                )
                owner_recipients = [request.user.email] if request.user.email else []
                approved_msg = (
                    "Great news! Our compliance desk has activated your listing.\n\n"
                    f"Vehicle: {car.make} {car.model} ({car.license_plate})\n"
                    f"Service type: {car.get_service_type_display()}\n"
                    "MarvelSafari connects you with renters but does not cover damages. Please keep insurance active.\n"
                )
                _safe_send_mail(
                    f"Car approved: {car.make} {car.model}",
                    approved_msg,
                    owner_recipients,
                )
            else:
                # If AI is unsure/low confidence, keep it pending and guide the user to correct
                car.moderation_status = CarStatus.PENDING
                car.save(update_fields=['moderation_status'])
                reason_text = '; '.join(ai_outcome.get('reasons') or []) or 'We could not verify the listing details.'
                fix_url = request.build_absolute_uri(reverse('car_rentals:car_submission'))
                messages.warning(
                    request,
                    "We need a quick clarification before publishing your car. Please review the note we emailed."
                )
                owner_recipients = [request.user.email] if request.user.email else []
                rejected_msg = (
                    "Our compliance team needs a quick update before we can publish your car.\n\n"
                    f"Vehicle: {car.make} {car.model} ({car.license_plate})\n"
                    f"Reason: {reason_text}\n"
                    f"Update and resubmit here: {fix_url}\n"
                    "Tips: keep pricing within regional expectations and upload clear photos — MarvelSafari enforces these guardrails as a marketplace policy."
                )
                _safe_send_mail(
                    f"Car needs changes: {car.make} {car.model}",
                    rejected_msg,
                    owner_recipients,
                )

            # Always notify the site admin when a car is submitted
            admin_email = getattr(settings, 'CONTACT_NOTIFY_EMAIL', None) or 'marvelsafari@gmail.com'
            admin_recipients = [admin_email] if admin_email else []
            admin_subject = f"New car listing request: {car.make} {car.model}"
            admin_message = (
                "A new car listing request was submitted.\n\n"
                f"Owner: {request.user.get_full_name() or request.user.email}\n"
                f"Vehicle: {car.make} {car.model} ({car.license_plate})\n"
                f"Service type: {car.get_service_type_display()}\n"
                f"Moderation status: {car.moderation_status}\n"
            )
            _safe_send_mail(admin_subject, admin_message, admin_recipients)

            return redirect('car_rentals:car_submission_success')
    else:
        form = CarSubmissionForm(initial=template_initial or None, company=company)

    car_categories_qs = list(
        CarCategory.objects.filter(is_active=True)
        .annotate(active_cars=Count('cars', filter=Q(cars__is_deleted=False)))
        .order_by('display_order', 'name')
    )
    if car_categories_qs:
        car_categories = car_categories_qs
    else:
        car_categories = [_category_snapshot(item) for item in FALLBACK_CAR_CATEGORY_DATA]
    existing_car_count = Car.objects.filter(owner=request.user, is_deleted=False).count()
    amenity_groups = _build_amenity_groups()

    available_locations = list(
        RentalLocation.objects.filter(company=company, is_active=True)
        .order_by('city', 'name')[:6]
    )
    if not available_locations:
        available_locations = list(
            RentalLocation.objects.filter(is_active=True).order_by('city', 'name')[:6]
        )
    if not available_locations:
        available_locations = [_location_snapshot(item) for item in FALLBACK_LOCATION_DATA[:6]]

    total_location_count = RentalLocation.objects.filter(is_active=True).count()
    if not total_location_count:
        total_location_count = len(FALLBACK_LOCATION_DATA)
    location_city_sample = sorted({loc.city for loc in available_locations if loc.city})[:4]

    context = {
        'form': form,
        'car_templates': CAR_LISTING_TEMPLATES,
        'selected_template': template_key,
        'selected_template_meta': template_meta,
        'car_categories': car_categories,
        'amenity_groups': amenity_groups,
        'available_locations': available_locations,
        'total_location_count': total_location_count,
        'location_city_sample': location_city_sample,
        'owner_company': company,
        'existing_car_count': existing_car_count,
    }
    return render(request, 'car_rentals/car_submission_form.html', context)


@login_required
def my_listings(request):
    """Dashboard for owners to view their cars and related rentals."""
    cars = Car.objects.filter(owner=request.user).select_related('company', 'category').prefetch_related('images')

    owner_rental_qs = CarRentalBooking.objects.filter(car__owner=request.user)
    owner_taxi_qs = TaxiBooking.objects.filter(car__owner=request.user)

    rental_bookings_qs = owner_rental_qs.select_related(
        'car', 'company', 'pickup_location', 'dropoff_location', 'user'
    ).order_by('-created_at')[:10]
    taxi_bookings_qs = owner_taxi_qs.select_related(
        'car', 'company', 'driver', 'user'
    ).order_by('-created_at')[:10]

    rental_bookings = list(rental_bookings_qs)
    taxi_bookings = list(taxi_bookings_qs)

    thirty_days_ago = timezone.now() - timedelta(days=30)

    def _sum(qs, field):
        result = qs.aggregate(total=Sum(field))
        return result['total'] or Decimal('0')

    lifetime_rental_value = _sum(owner_rental_qs, 'total_amount')
    lifetime_taxi_value = _sum(owner_taxi_qs, 'total_fare')
    monthly_rental_value = _sum(owner_rental_qs.filter(created_at__gte=thirty_days_ago), 'total_amount')
    monthly_taxi_value = _sum(owner_taxi_qs.filter(created_at__gte=thirty_days_ago), 'total_fare')

    avg_daily_rate = cars.aggregate(avg=Avg('daily_price'))['avg'] or Decimal('0')
    active_rentals = owner_rental_qs.filter(status__in=['pending', 'confirmed', 'active']).count()
    active_taxis = owner_taxi_qs.filter(status__in=['pending', 'confirmed', 'driver_assigned', 'en_route', 'in_progress']).count()

    pending_reviews = owner_rental_qs.filter(status__in=['completed', 'active'], driver_review__isnull=True).count()
    pending_reviews += owner_taxi_qs.filter(status__in=['completed', 'in_progress'], driver_review__isnull=True).count()

    owner_stats = {
        'live_listings': cars.filter(moderation_status=CarStatus.APPROVED).count(),
        'pending_review': cars.filter(moderation_status=CarStatus.PENDING).count(),
        'dual_service': cars.filter(service_type='both').count(),
        'avg_daily_rate': avg_daily_rate,
        'monthly_revenue': monthly_rental_value + monthly_taxi_value,
        'lifetime_value': lifetime_rental_value + lifetime_taxi_value,
        'active_trips': active_rentals + active_taxis,
        'pending_reviews': pending_reviews,
    }

    attention_flags = []
    seen_ids = set()

    def enqueue(qs, badge, badge_label, message):
        for car in qs:
            if car.id in seen_ids:
                continue
            attention_flags.append({'car': car, 'badge': badge, 'badge_label': badge_label, 'message': message})
            seen_ids.add(car.id)
            if len(attention_flags) >= 5:
                return

    enqueue(
        cars.filter(moderation_status=CarStatus.PENDING).order_by('-updated_at'),
        'badge-warning',
        'Pending review',
        'Awaiting human / AI moderation'
    )
    enqueue(
        cars.filter(moderation_status=CarStatus.REJECTED).order_by('-updated_at'),
        'badge-error',
        'Needs fixes',
        'Update evidence, photos, or pricing before resubmitting'
    )
    enqueue(
        cars.filter(daily_price__lte=0),
        'badge-neutral',
        'Add pricing',
        'Missing a base daily rate'
    )
    enqueue(
        cars.filter(status__in=[OperationalStatus.MAINTENANCE, OperationalStatus.RESERVED]),
        'badge-info',
        'Unavailable',
        'Not available to travelers'
    )

    def vehicle_label(obj):
        if getattr(obj, 'car', None):
            return f"{obj.car.make} {obj.car.model}" if obj.car else 'Assigned vehicle'
        if getattr(obj, 'category', None):
            return obj.category.name
        return 'Unassigned vehicle'

    activity_events = []
    for booking in rental_bookings[:5]:
        activity_events.append({
            'type': 'rental',
            'ref': booking.booking_reference,
            'vehicle': vehicle_label(booking),
            'status': booking.get_status_display(),
            'meta': f"{booking.pickup_date} → {booking.dropoff_date}",
            'timestamp': booking.created_at,
        })

    for booking in taxi_bookings[:5]:
        pickup = (booking.pickup_address or '')[:42]
        activity_events.append({
            'type': 'taxi',
            'ref': booking.booking_reference,
            'vehicle': vehicle_label(booking),
            'status': booking.get_status_display(),
            'meta': pickup,
            'timestamp': booking.created_at,
        })

    recent_activity = sorted(activity_events, key=lambda item: item['timestamp'], reverse=True)[:6]

    incoming_requests = []
    for booking in rental_bookings[:5]:
        incoming_requests.append({
            'traveler': booking.user.get_full_name() or booking.user.email,
            'car': booking.car,
            'pickup': booking.pickup_location.name if booking.pickup_location else 'TBD',
            'dropoff': booking.dropoff_location.name if booking.dropoff_location else 'TBD',
            'window': f"{booking.pickup_date} → {booking.dropoff_date}",
            'status': booking.get_status_display(),
        })

    context = {
        'cars': cars,
        'rental_bookings': rental_bookings,
        'taxi_bookings': taxi_bookings,
        'owner_stats': owner_stats,
        'attention_flags': attention_flags,
        'recent_activity': recent_activity,
        'incoming_requests': incoming_requests,
    }

    return render(request, 'car_rentals/my_listings.html', context)


@login_required
def car_submission_success(request):
    """Simple success page after submitting a car."""
    return render(request, 'car_rentals/car_submission_success.html')


@login_required
def car_edit(request, car_id):
    """Allow owners to edit their car listings."""
    car = get_object_or_404(
        Car.objects.select_related('company', 'category', 'current_location').prefetch_related('images'),
        pk=car_id,
        owner=request.user,
        is_deleted=False
    )

    # Check if car can be edited
    editable_statuses = [CarStatus.PENDING, CarStatus.APPROVED, CarStatus.REJECTED]
    if car.moderation_status not in editable_statuses:
        messages.error(request, 'This car cannot be edited in its current status.')
        return redirect('car_rentals:my_listings')

    if request.method == 'POST':
        form = CarEditForm(request.POST, request.FILES, instance=car)
        if form.is_valid():
            car = form.save(commit=False)
            
            # If car was rejected, reset to pending for re-review
            if car.moderation_status == CarStatus.REJECTED:
                car.moderation_status = CarStatus.PENDING
                messages.info(request, 'Your car has been resubmitted for review.')
            else:
                messages.success(request, 'Car updated successfully.')
            
            car.save()

            # Handle gallery images
            gallery_images = form.cleaned_data.get('gallery_images', [])
            for img_file in gallery_images[:5]:
                CarImage.objects.create(car=car, image=img_file)

            return redirect('car_rentals:my_listings')
    else:
        form = CarEditForm(instance=car)

    context = {
        'form': form,
        'car': car,
        'existing_images': car.images.all(),
        'is_edit': True,
    }
    return render(request, 'car_rentals/car_edit.html', context)


def car_detail(request, car_id):
    """Detailed view of a single car with gallery, features, location."""
    # Only show approved cars (not deleted), or owner can see their own cars
    base_qs = Car.objects.select_related('company', 'category', 'current_location').prefetch_related('images', 'assigned_drivers').filter(is_deleted=False)
    
    if request.user.is_authenticated:
        car = get_object_or_404(
            base_qs.filter(Q(moderation_status=CarStatus.APPROVED) | Q(owner=request.user)),
            pk=car_id
        )
    else:
        car = get_object_or_404(
            base_qs.filter(moderation_status=CarStatus.APPROVED),
            pk=car_id
        )

    # Similar cars - only approved and available
    similar_cars = Car.objects.filter(
        category=car.category,
        status=OperationalStatus.AVAILABLE,
        moderation_status=CarStatus.APPROVED,
        is_deleted=False,
    ).exclude(pk=car.pk).select_related('company', 'category').prefetch_related('images')[:4]

    for similar in similar_cars:
        similar.display_daily_rate = similar.daily_price
        similar.display_currency = 'USD'

    # Drivers assigned
    drivers = car.assigned_drivers.filter(is_active=True).order_by('-average_rating')

    context = {
        'car': car,
        'similar_cars': similar_cars,
        'drivers': drivers,
        'images': car.images.all(),
    }
    return render(request, 'car_rentals/car_detail.html', context)


@login_required
def car_booking_create(request, car_id):
    """Booking form for renting a specific car."""
    base_qs = Car.objects.filter(
        status=OperationalStatus.AVAILABLE,
        is_deleted=False,
    )

    # Owners can test bookings on their own cars even if not yet approved,
    # but regular users only see approved cars.
    if request.user.is_authenticated:
        car = get_object_or_404(
            base_qs.filter(
                Q(moderation_status=CarStatus.APPROVED) | Q(owner=request.user)
            ),
            pk=car_id,
        )
    else:
        car = get_object_or_404(
            base_qs.filter(moderation_status=CarStatus.APPROVED),
            pk=car_id,
        )

    if request.method == 'POST':
        form = CarRentalBookingForm(request.POST, user=request.user, car=car)
        if form.is_valid():
            try:
                booking = form.save(commit=False)
                booking.user = request.user
                booking.car = car
                booking.company = car.company
                booking.category = car.category
                booking.daily_rate = car.daily_price or Decimal('50.00')
                booking.currency = 'USD'

                # Set business booking if applicable
                if hasattr(request.user, 'is_business_account') and request.user.is_business_account:
                    try:
                        booking.business_account = request.user.business_account
                        booking.is_business_booking = True
                    except:
                        pass

                booking.save()
                
                # Notify the car owner
                try:
                    from notifications.tasks import send_owner_booking_notification
                    send_owner_booking_notification.delay(booking.id, 'car')
                except Exception as notify_err:
                    logger.warning(f"Failed to send owner notification: {notify_err}")
                
                messages.success(request, f'Rental booking {booking.booking_reference} confirmed!')
                return redirect('car_rentals:booking_confirmation', booking_id=booking.pk)
            except Exception as e:
                logger.error(f"Booking creation error: {e}")
                messages.error(request, f'Could not create booking: {str(e)}')
    else:
        initial = {
            'pickup_date': (timezone.now().date() + timedelta(days=1)).isoformat(),
            'dropoff_date': (timezone.now().date() + timedelta(days=3)).isoformat(),
        }
        form = CarRentalBookingForm(initial=initial, user=request.user, car=car)

    # Get locations for map
    map_locations = []
    if hasattr(form.fields['pickup_location'], 'queryset'):
        for loc in form.fields['pickup_location'].queryset:
            if loc.latitude and loc.longitude:
                map_locations.append({
                    'id': loc.id,
                    'name': loc.name,
                    'city': loc.city,
                    'address': loc.address,
                    'type': loc.location_type,
                    'latitude': float(loc.latitude),
                    'longitude': float(loc.longitude),
                })

    return render(request, 'car_rentals/car_booking_create.html', {
        'form': form,
        'car': car,
        'map_locations': map_locations,
    })


@login_required
def taxi_booking_create(request):
    """Book a taxi / transfer / chauffeur service."""
    # Get available taxi cars - only approved and not deleted
    taxi_cars = Car.objects.filter(
        service_type__in=['taxi', 'both'],
        status=OperationalStatus.AVAILABLE,
        moderation_status=CarStatus.APPROVED,
        is_deleted=False,
    ).select_related('company', 'category').prefetch_related('images', 'assigned_drivers')

    selected_car_id = request.GET.get('car_id') or request.POST.get('car_id')
    selected_car = None
    if selected_car_id:
        try:
            selected_car = taxi_cars.get(pk=selected_car_id)
        except (Car.DoesNotExist, ValueError):
            pass

    if request.method == 'POST':
        form = TaxiBookingForm(request.POST, user=request.user)
        if form.is_valid():
            try:
                booking = form.save(commit=False)
                booking.user = request.user

                if selected_car:
                    booking.car = selected_car
                    booking.company = selected_car.company
                    booking.category = selected_car.category
                    booking.base_fare = selected_car.taxi_base_fare or Decimal('5.00')

                    # Assign first available driver
                    driver = selected_car.assigned_drivers.filter(
                        is_active=True, is_available=True
                    ).order_by('-average_rating').first()
                    if driver:
                        booking.driver = driver

                booking.save()
                
                # Notify the car owner
                try:
                    from notifications.tasks import send_owner_booking_notification
                    send_owner_booking_notification.delay(booking.id, 'taxi')
                except Exception as notify_err:
                    logger.warning(f"Failed to send owner notification: {notify_err}")
                
                messages.success(request, f'Taxi booking {booking.booking_reference} confirmed!')
                return redirect('car_rentals:taxi_confirmation', booking_id=booking.pk)
            except Exception as e:
                logger.error(f"Taxi booking error: {e}")
                messages.error(request, f'Could not create booking: {str(e)}')
    else:
        form = TaxiBookingForm(user=request.user)

    context = {
        'form': form,
        'taxi_cars': taxi_cars[:12],
        'selected_car': selected_car,
        'cars': taxi_cars[:12],  # For template compatibility
    }
    return render(request, 'car_rentals/taxi_booking.html', context)


@login_required
def booking_confirmation(request, booking_id):
    """Rental booking confirmation page."""
    try:
        booking = get_object_or_404(CarRentalBooking, pk=booking_id, user=request.user)
    except (ValueError, TypeError):
        # Try with booking_reference
        booking = get_object_or_404(CarRentalBooking, booking_reference=booking_id, user=request.user)
    
    return render(request, 'car_rentals/booking_confirmation.html', {'booking': booking})


@login_required
def taxi_confirmation(request, booking_id):
    """Taxi booking confirmation page."""
    try:
        booking = get_object_or_404(TaxiBooking, pk=booking_id, user=request.user)
    except (ValueError, TypeError):
        booking = get_object_or_404(TaxiBooking, booking_reference=booking_id, user=request.user)
    
    return render(request, 'car_rentals/taxi_confirmation.html', {'booking': booking})


@login_required
def my_bookings(request):
    """User's car rental and taxi booking history."""
    rental_bookings = CarRentalBooking.objects.filter(
        user=request.user
    ).select_related('car', 'company', 'pickup_location', 'dropoff_location', 'car_review').order_by('-created_at')

    taxi_bookings = TaxiBooking.objects.filter(
        user=request.user
    ).select_related('car', 'driver', 'company').order_by('-created_at')

    pending_car_reviews = 0
    now = timezone.now()
    for booking in rental_bookings:
        booking.car_review_release = booking.review_release_at()
        booking.can_review_car_flag = booking.can_review_car()
        if not getattr(booking, 'car_review', None) and booking.car_review_release and now >= booking.car_review_release:
            pending_car_reviews += 1

    context = {
        'rental_bookings': rental_bookings,
        'taxi_bookings': taxi_bookings,
        'pending_car_reviews': pending_car_reviews,
    }
    return render(request, 'car_rentals/my_bookings.html', context)


@login_required
def track_car(request, booking_id):
    """Real-time car tracking page."""
    try:
        # Try rental booking first
        booking = CarRentalBooking.objects.filter(
            Q(pk=booking_id) | Q(booking_reference=booking_id),
            user=request.user
        ).select_related('car', 'driver').first()
        
        if not booking:
            # Try taxi booking
            booking = TaxiBooking.objects.filter(
                Q(pk=booking_id) | Q(booking_reference=booking_id),
                user=request.user
            ).select_related('car', 'driver').first()
    except:
        booking = None

    if not booking:
        messages.error(request, 'Booking not found.')
        return redirect('car_rentals:my_bookings')

    if not booking.car:
        messages.error(request, 'No car assigned to this booking yet.')
        return redirect('car_rentals:my_bookings')

    context = {
        'booking': booking,
        'car_id': booking.car.id,
        'driver_id': booking.driver.id if hasattr(booking, 'driver') and booking.driver else None,
    }
    return render(request, 'car_rentals/track_car.html', context)


@require_GET
def car_location_api(request, car_id):
    """API endpoint returning current car location as JSON."""
    car = get_object_or_404(Car, pk=car_id)
    
    data = {
        'car_id': str(car.id),
        'make': car.make,
        'model': car.model,
        'latitude': float(car.current_latitude) if car.current_latitude else None,
        'longitude': float(car.current_longitude) if car.current_longitude else None,
        'speed_kmh': None,  # Car model doesn't have speed field
        'heading': None,    # Car model doesn't have heading field
        'updated_at': car.location_updated_at.isoformat() if car.location_updated_at else None,
        'status': car.status,
    }

    # Also return recent track points
    recent = CarLocationTracker.objects.filter(car=car).order_by('-recorded_at')[:20]
    data['track'] = [
        {
            'latitude': float(p.latitude),
            'longitude': float(p.longitude),
            'speed_kmh': float(p.speed_kmh) if p.speed_kmh else None,
            'heading': float(p.heading) if p.heading else None,
            'recorded_at': p.recorded_at.isoformat(),
        }
        for p in recent
    ]
    return JsonResponse(data)


@require_GET
def driver_location_api(request, driver_id):
    """API endpoint returning current driver location as JSON."""
    driver = get_object_or_404(CarDriver, pk=driver_id)
    data = {
        'driver_id': driver.id,
        'name': driver.full_name,
        'latitude': float(driver.current_latitude) if driver.current_latitude else None,
        'longitude': float(driver.current_longitude) if driver.current_longitude else None,
        'is_available': driver.is_available,
        'updated_at': driver.location_updated_at.isoformat() if driver.location_updated_at else None,
    }
    return JsonResponse(data)


@login_required
def car_review_create(request, booking_id):
    """Allow renters to review a car after the 3-day cooling period."""
    booking = CarRentalBooking.objects.filter(
        Q(pk=booking_id) | Q(booking_reference=booking_id),
        user=request.user
    ).select_related('car', 'pickup_location', 'dropoff_location', 'car_review').first()

    if not booking:
        messages.error(request, 'Booking not found.')
        return redirect('car_rentals:my_bookings')

    if not booking.car:
        messages.error(request, 'No car was assigned to this booking yet.')
        return redirect('car_rentals:my_bookings')

    if getattr(booking, 'car_review', None):
        messages.info(request, 'You already reviewed this car.')
        return redirect('car_rentals:my_bookings')

    if booking.status not in ['completed', 'active']:
        messages.error(request, 'You can review this car after the trip is marked as completed.')
        return redirect('car_rentals:my_bookings')

    release_at = booking.review_release_at()
    if not release_at:
        messages.error(request, 'We need the trip end date before a review can be submitted.')
        return redirect('car_rentals:my_bookings')

    if timezone.now() < release_at:
        formatted = release_at.strftime('%d %b, %H:%M %Z')
        messages.warning(request, f'You can rate this car after {formatted}.')
        return redirect('car_rentals:my_bookings')

    if request.method == 'POST':
        form = CarReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            review.booking = booking
            review.car = booking.car
            review.user = request.user
            review.save()
            messages.success(request, 'Thanks! Your car review helps future travelers.')
            return redirect('car_rentals:my_bookings')
    else:
        form = CarReviewForm()

    context = {
        'form': form,
        'booking': booking,
        'car': booking.car,
    }
    return render(request, 'car_rentals/car_review_create.html', context)


@login_required
def driver_review_create(request, booking_id):
    """Allow authenticated users to leave one review for a booked driver."""
    # Try rental booking first
    booking = CarRentalBooking.objects.filter(
        Q(pk=booking_id) | Q(booking_reference=booking_id),
        user=request.user
    ).first()
    
    is_taxi = False
    if not booking:
        # Try taxi booking
        booking = TaxiBooking.objects.filter(
            Q(pk=booking_id) | Q(booking_reference=booking_id),
            user=request.user
        ).first()
        is_taxi = True

    if not booking:
        messages.error(request, 'Booking not found.')
        return redirect('car_rentals:my_bookings')

    driver = booking.driver if is_taxi else getattr(booking, 'selected_driver', None)
    if not driver:
        messages.error(request, 'No driver was assigned to this booking.')
        return redirect('car_rentals:my_bookings')

    if booking.status not in ['completed', 'active']:
        messages.error(request, 'You can review a driver after your trip is active or completed.')
        return redirect('car_rentals:my_bookings')

    # Check if review already exists
    review_exists = CarDriverReview.objects.filter(
        driver=driver, 
        user=request.user
    ).exists()
    
    if review_exists:
        messages.info(request, 'You already reviewed this driver.')
        return redirect('car_rentals:my_bookings')

    if request.method == 'POST':
        form = CarDriverReviewForm(request.POST)
        if form.is_valid():
            review = form.save(commit=False)
            if is_taxi:
                review.taxi_booking = booking
            else:
                review.booking = booking
            review.driver = driver
            review.user = request.user
            review.save()
            messages.success(request, 'Driver review submitted successfully.')
            return redirect('car_rentals:my_bookings')
    else:
        form = CarDriverReviewForm()

    return render(request, 'car_rentals/driver_review_create.html', {
        'form': form, 
        'booking': booking,
        'driver': driver
    })