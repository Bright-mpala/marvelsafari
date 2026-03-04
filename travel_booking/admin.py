from django.contrib import admin, messages
from django.contrib.admin.sites import AdminSite
from django.utils.translation import gettext_lazy as _
from django.db.models import Count, Sum, Avg
from django.db.models.functions import TruncMonth
from django.utils import timezone
from django.core.cache import cache
from django.conf import settings
from django.core.mail import send_mail
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from datetime import timedelta


class MarvelSafariAdminSite(AdminSite):
    """Custom admin site for Marvel Safari."""

    site_header = _("marvel.safari.essence.admin")
    site_title = _("Marvel Safari Essence")
    index_title = _("Premium control center")
    site_url = "/"

    def get_urls(self):
        """Add custom admin URLs for dashboard actions."""
        urls = super().get_urls()
        custom_urls = [
            path(
                'bookings/<uuid:booking_id>/approve/',
                self.admin_view(self.approve_booking),
                name='approve_booking',
            ),
        ]
        return custom_urls + urls

    def approve_booking(self, request, booking_id):
        """Approve a booking from the admin dashboard and notify the guest."""
        from bookings.models import Booking

        booking = get_object_or_404(Booking, pk=booking_id)

        if booking.status != Booking.BookingStatus.CONFIRMED:
            booking.status = Booking.BookingStatus.CONFIRMED
            booking.save(update_fields=['status'])

            # Notify guest by email if address is available using styled template
            if booking.user.email:
                from django.template.loader import render_to_string

                target = booking.property or booking.car or booking.tour
                user_name = (
                    getattr(booking.user, "full_name", "")
                    or booking.user.get_full_name()
                    or booking.user.email
                )
                date_info = _("{check_in} to {check_out}").format(
                    check_in=booking.check_in_date,
                    check_out=booking.check_out_date,
                )

                context = {
                    'user_name': user_name,
                    'listing_label': str(target),
                    'date_info': date_info,
                }

                text_body = render_to_string('bookings/emails/booking_approved.txt', context)
                html_body = render_to_string('bookings/emails/booking_approved.html', context)

                send_mail(
                    subject=_("Your booking has been approved"),
                    message=text_body,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[booking.user.email],
                    html_message=html_body,
                    fail_silently=True,
                )

            messages.success(
                request,
                _("Booking {id} approved and guest notified.").format(id=booking.id),
            )
        else:
            messages.info(
                request,
                _("Booking {id} is already approved.").format(id=booking.id),
            )

        index_url = reverse('marvel_safari_admin:index')
        return redirect(index_url)

    def get_app_list(self, request, app_label=None):
        """Reorder apps in admin index."""
        app_list = super().get_app_list(request, app_label)

        # Define custom ordering
        app_ordering = [
            'accounts',
            'account',  # allauth email addresses
            'socialaccount',  # allauth social accounts
            'properties',
            'bookings',
            'flights',
            'car_rentals',
            'tours',
            'reviews',
            'payments',
            'business',
            'analytics',
            'notifications',
            'newsletter',
            'blog',
            'api',
        ]

        # Sort apps according to our custom ordering
        app_dict = {app['app_label']: app for app in app_list}
        ordered_apps = []

        for app_label in app_ordering:
            if app_label in app_dict:
                ordered_apps.append(app_dict[app_label])

        # Add any remaining apps not in our ordering
        for app in app_list:
            if app['app_label'] not in app_ordering:
                ordered_apps.append(app)

        return ordered_apps

    def index(self, request, extra_context=None):
        """Override index to add custom dashboard data."""
        extra_context = extra_context or {}
        cache_key = 'admin_dashboard_metrics_v1'
        cached = cache.get(cache_key)

        if cached:
            extra_context.update(cached)
        else:
            from accounts.models import User
            from bookings.models import Booking
            from properties.models import Property
            from payments.models import Transaction

            thirty_days_ago = timezone.now() - timedelta(days=30)

            payload = {
                'user_count': User.objects.count(),
                'booking_count': Booking.objects.filter(created_at__gte=thirty_days_ago).count(),
                'property_count': Property.objects.count(),
            }

            revenue = Transaction.objects.filter(
                created_at__gte=thirty_days_ago,
                status='completed'
            ).aggregate(total=Sum('amount'))['total'] or 0
            payload['revenue'] = f"{revenue:.2f}"

            payload['recent_bookings'] = list(
                Booking.objects.select_related('user', 'property').order_by('-created_at')[:5]
            )

            cache.set(
                cache_key,
                payload,
                getattr(settings, 'ADMIN_DASHBOARD_CACHE_SECONDS', 300),
            )
            extra_context.update(payload)

        return super().index(request, extra_context)


# Create the custom admin site instance
admin_site = MarvelSafariAdminSite(name='marvel_safari_admin')


# Register allauth models with custom admin site
from allauth.socialaccount.models import SocialAccount, SocialApp, SocialToken
from allauth.socialaccount.admin import SocialAccountAdmin, SocialAppAdmin, SocialTokenAdmin
from allauth.account.models import EmailAddress
from allauth.account.admin import EmailAddressAdmin

admin_site.register(SocialAccount, SocialAccountAdmin)
admin_site.register(SocialApp, SocialAppAdmin)
admin_site.register(SocialToken, SocialTokenAdmin)
admin_site.register(EmailAddress, EmailAddressAdmin)