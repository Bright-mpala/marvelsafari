from django.shortcuts import render

FLIGHTS_AVAILABLE = False


def flight_list(request):
    """Temporary placeholder while flights are disabled."""
    if not FLIGHTS_AVAILABLE:
        return render(request, 'flights/unavailable.html', status=503)
    return render(request, 'flights/unavailable.html', status=503)


def flight_booking_create(request, flight_id):
    """Booking is unavailable while flights are disabled."""
    return render(request, 'flights/unavailable.html', status=503)
