from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from decimal import Decimal
import logging

from .models import Tour
from .forms import TourBookingForm

logger = logging.getLogger(__name__)


def tour_list(request):
    """List tours with optional filtering."""
    qs = Tour.objects.select_related('operator').filter(is_active=True)
    destination = (request.GET.get('destination') or '').strip()
    tour_type = (request.GET.get('tour_type') or '').strip()
    duration = request.GET.get('duration')
    price_range = request.GET.get('price_range')

    if destination:
        qs = qs.filter(
            Q(city__icontains=destination) |
            Q(country__icontains=destination) |
            Q(location__icontains=destination)
        )
    if tour_type:
        qs = qs.filter(tour_type__icontains=tour_type)
    if duration == 'half-day':
        qs = qs.filter(duration_hours__lte=5)
    elif duration == 'full-day':
        qs = qs.filter(duration_hours__gte=6, duration_hours__lte=12)
    elif duration == 'multi-day':
        qs = qs.filter(duration_days__gte=1)

    if price_range == 'budget':
        qs = qs.filter(base_price__lt=50)
    elif price_range == 'moderate':
        qs = qs.filter(base_price__gte=50, base_price__lte=150)
    elif price_range == 'premium':
        qs = qs.filter(base_price__gt=150)

    paginator = Paginator(qs, 9)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    query_params = request.GET.copy()
    query_params.pop('page', None)
    query_string = query_params.urlencode()

    active_filters = []
    if destination:
        active_filters.append({'label': 'Destination', 'value': destination})
    if tour_type:
        active_filters.append({'label': 'Tour type', 'value': tour_type.title()})
    if duration:
        active_filters.append({'label': 'Duration', 'value': duration.replace('-', ' ').title()})
    if price_range:
        labels = {
            'budget': 'Under $50',
            'moderate': '$50 - $150',
            'premium': 'Over $150',
        }
        active_filters.append({'label': 'Budget', 'value': labels.get(price_range, price_range)})

    context = {
        'tours': page_obj.object_list,
        'page_obj': page_obj,
        'total_tours': paginator.count,
        'query_string': query_string,
        'active_filters': active_filters,
    }
    return render(request, 'tours/tour_list.html', context)


@login_required
def tour_booking_create(request, tour_id):
    tour = get_object_or_404(Tour, pk=tour_id, is_active=True)

    if request.method == 'POST':
        form = TourBookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.user = request.user
            booking.base_price = tour.base_price
            booking.taxes = Decimal('0.00')
            booking.service_fee = Decimal('0.00')
            booking.total_amount = booking.base_price * booking.participant_count
            booking.currency = tour.currency if hasattr(tour, 'currency') else 'USD'
            booking.save()
            
            # Notify the tour operator
            try:
                from notifications.tasks import send_owner_booking_notification
                send_owner_booking_notification.delay(booking.id, 'tour')
            except Exception as notify_err:
                logger.warning(f"Failed to send tour operator notification: {notify_err}")
            
            messages.success(request, 'Tour booked!')
            return redirect('tours:tour_list')
    else:
        initial = {'tour': tour.pk}
        form = TourBookingForm(initial=initial)

    return render(request, 'tours/tour_booking_create.html', {'form': form, 'tour': tour})
