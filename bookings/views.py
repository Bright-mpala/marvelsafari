from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from datetime import datetime, timedelta
from decimal import Decimal

from .models import Booking
from .forms import BookingForm
from properties.models import Property, PropertyStatus
from car_rentals.models import CarRentalBooking, TaxiBooking

@login_required
@require_http_methods(["GET"])
def booking_list(request):
    """List user's bookings with filtering and sorting."""
    bookings = Booking.objects.filter(user=request.user).select_related('property').order_by('-created_at')
    car_rental_bookings = CarRentalBooking.objects.filter(user=request.user).select_related('car', 'company', 'pickup_location', 'dropoff_location').order_by('-created_at')
    taxi_bookings = TaxiBooking.objects.filter(user=request.user).select_related('car', 'driver', 'company').order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter in dict(Booking.BOOKING_STATUS):
        bookings = bookings.filter(status=status_filter)
    
    # Filter upcoming vs past
    date_filter = request.GET.get('date')
    today = timezone.now().date()
    if date_filter == 'upcoming':
        bookings = bookings.filter(check_in_date__gte=today)
    elif date_filter == 'past':
        bookings = bookings.filter(check_out_date__lt=today)
    
    context = {
        'bookings': bookings,
        'car_rental_bookings': car_rental_bookings,
        'taxi_bookings': taxi_bookings,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'total_bookings': Booking.objects.filter(user=request.user).count(),
    }
    return render(request, 'bookings/booking_list.html', context)

@login_required
@require_http_methods(["GET"])
def booking_detail(request, pk):
    """Display booking details."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    context = {
        'booking': booking,
        'can_cancel': booking.status in ['pending', 'confirmed'] and booking.is_upcoming,
    }
    return render(request, 'bookings/booking_detail.html', context)

@login_required
@require_http_methods(["GET", "POST"])
def booking_create(request, property_id):
    """Create a new booking for a property."""
    # Try to get property by ID (UUID) first, then by slug
    public_statuses = list(PropertyStatus.public_statuses())
    try:
        property_obj = Property.objects.get(id=property_id, status__in=public_statuses)
    except (Property.DoesNotExist, ValueError):
        property_obj = get_object_or_404(Property, slug=property_id, status__in=public_statuses)

    if request.method == 'POST':
        form = BookingForm(request.POST)
        # Ensure the model instance has required relations before validation.
        form.instance.user = request.user
        form.instance.property = property_obj
        if form.is_valid():
            try:
                with transaction.atomic():
                    # Create booking
                    booking = form.save(commit=False)
                    booking.user = request.user
                    booking.property = property_obj
                    
                    # Calculate number of nights first
                    nights = (booking.check_out_date - booking.check_in_date).days
                    if nights <= 0:
                        raise ValidationError(_('Check-out must be after check-in.'))
                    
                    # Get price per night from property
                    # Ensure we have a valid price
                    if property_obj.minimum_price and property_obj.minimum_price > 0:
                        booking.price_per_night = property_obj.minimum_price
                    else:
                        # Fallback only if property has no price set
                        booking.price_per_night = Decimal('100.00')
                    
                    # Calculate total: price_per_night * nights
                    booking.total_amount = booking.price_per_night * Decimal(str(nights))
                    
                    # Validate total is positive
                    if booking.total_amount <= 0:
                        raise ValidationError(_('Total amount must be greater than zero.'))
                    
                    # Save (model.save() runs full_clean internally)
                    booking.save()

                    # Send styled confirmation email (fail silently in dev)
                    if request.user.email:
                        from django.template.loader import render_to_string

                        context = {
                            'user_name': request.user.get_full_name() or request.user.email,
                            'property_name': property_obj.name,
                            'check_in': booking.check_in_date,
                            'check_out': booking.check_out_date,
                            'total_amount': booking.total_amount,
                        }

                        text_body = render_to_string('bookings/emails/booking_confirmation.txt', context)
                        html_body = render_to_string('bookings/emails/booking_confirmation.html', context)

                        send_mail(
                            subject=_('Your booking request was received'),
                            message=text_body,
                            from_email=settings.DEFAULT_FROM_EMAIL,
                            recipient_list=[request.user.email],
                            html_message=html_body,
                            fail_silently=True,
                        )

                    messages.success(
                        request,
                        _('Booking request submitted successfully! Estimated total: ${:.2f}').format(booking.total_amount)
                    )
                    return redirect('bookings:detail', pk=booking.pk)
            except Exception as e:
                messages.error(request, _('Error creating booking: {}').format(str(e)))
    else:
        # Pre-fill form with URL parameters if provided, otherwise use sensible defaults
        today = timezone.now().date()
        check_in = request.GET.get('check_in')
        check_out = request.GET.get('check_out')
        guests = request.GET.get('guests', '2')
        
        # Try to parse check_in/check_out dates from URL parameters
        check_in_date = None
        check_out_date = None
        
        if check_in:
            try:
                check_in_date = datetime.fromisoformat(check_in).date()
            except (ValueError, TypeError):
                pass
        
        if check_out:
            try:
                check_out_date = datetime.fromisoformat(check_out).date()
            except (ValueError, TypeError):
                pass
        
        # Use provided dates or fall back to defaults
        initial_data = {
            'check_in_date': check_in_date or (today + timedelta(days=1)),
            'check_out_date': check_out_date or (today + timedelta(days=4)),
            'guests': guests,
        }
        form = BookingForm(initial=initial_data)

    context = {
        'form': form,
        'property': property_obj,
    }
    return render(request, 'bookings/booking_create.html', context)

@login_required
@require_http_methods(["POST"])
def booking_cancel(request, pk):
    """Cancel a booking."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    
    if booking.status not in ['pending', 'confirmed']:
        messages.error(request, _('This booking cannot be cancelled.'))
        return redirect('bookings:detail', pk=booking.pk)
    
    if not booking.is_upcoming:
        messages.error(request, _('Cannot cancel bookings that have already started.'))
        return redirect('bookings:detail', pk=booking.pk)
    
    # Handle cancellation
    cancellation_reason = request.POST.get('reason', '')
    try:
        with transaction.atomic():
            booking.status = 'cancelled'
            booking.cancellation_reason = cancellation_reason
            booking.save()
            messages.success(request, _('Booking cancelled successfully.'))
    except Exception as e:
        messages.error(request, _('Error cancelling booking: {}').format(str(e)))
    
    return redirect('bookings:detail', pk=booking.pk)
