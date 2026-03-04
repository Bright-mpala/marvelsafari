from django.shortcuts import render
from django.db.models import Count, Sum
from django.utils import timezone
from datetime import timedelta

from bookings.models import Booking
from properties.models import Property
from flights.models import FlightBooking
from car_rentals.models import CarRentalBooking
from tours.models import TourBooking

def analytics_dashboard(request):
    """Platform analytics summary dashboard."""
    today = timezone.now().date()
    last_30_days = today - timedelta(days=30)

    property_bookings_qs = Booking.objects.all()
    flight_bookings_qs = FlightBooking.objects.all()
    car_bookings_qs = CarRentalBooking.objects.all()
    tour_bookings_qs = TourBooking.objects.all()

    total_bookings = (
        property_bookings_qs.count() +
        flight_bookings_qs.count() +
        car_bookings_qs.count() +
        tour_bookings_qs.count()
    )
    recent_property_bookings = property_bookings_qs.filter(created_at__date__gte=last_30_days).count()
    active_properties = Property.objects.filter(status='active', is_verified=True).count()

    top_cities = Property.objects.filter(status='active').values('city').annotate(
        total=Count('id')
    ).order_by('-total')[:8]

    revenue_property = property_bookings_qs.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_flight = flight_bookings_qs.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_car = car_bookings_qs.filter(status__in=['confirmed', 'completed', 'active']).aggregate(total=Sum('total_amount'))['total'] or 0
    revenue_tour = tour_bookings_qs.filter(status__in=['confirmed', 'completed']).aggregate(total=Sum('total_amount'))['total'] or 0

    context = {
        'total_bookings': total_bookings,
        'recent_property_bookings': recent_property_bookings,
        'active_properties': active_properties,
        'top_cities': top_cities,
        'revenue_property': revenue_property,
        'revenue_flight': revenue_flight,
        'revenue_car': revenue_car,
        'revenue_tour': revenue_tour,
        'total_revenue': revenue_property + revenue_flight + revenue_car + revenue_tour,
    }
    return render(request, 'analytics/dashboard.html', context)
