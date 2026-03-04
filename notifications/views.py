from django.shortcuts import render
from django.contrib.auth.decorators import login_required

from .models import Notification


@login_required
def notification_list(request):
    """List user notifications with status grouping."""
    notifications = Notification.objects.filter(user=request.user).select_related(
        'notification_type'
    ).order_by('-created_at')

    context = {
        'notifications': notifications,
        'unread_count': notifications.filter(read_at__isnull=True).count(),
        'failed_count': notifications.filter(status='failed').count(),
        'delivered_count': notifications.filter(status__in=['delivered', 'read']).count(),
    }
    return render(request, 'notifications/notification_list.html', context)
