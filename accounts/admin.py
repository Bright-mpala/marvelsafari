from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.db import IntegrityError
from django.db.models.deletion import ProtectedError
from django.utils.html import format_html
from .models import User, UserProfile, BusinessAccount
from travel_booking.admin import admin_site


def _get_user_blockers(user):
    """Return dict of models with protected relations to this user."""
    blockers = {}
    
    # Properties (user is owner/host)
    from properties.models import Property
    props = Property.objects.filter(owner=user)
    if props.exists():
        blockers['Properties'] = list(props.values_list('name', flat=True)[:5])
    
    # Car rental bookings
    from car_rentals.models import CarRentalBooking
    cars = CarRentalBooking.objects.filter(user=user)
    if cars.exists():
        blockers['Car Rental Bookings'] = list(cars.values_list('booking_reference', flat=True)[:5])
    
    # Payment transactions
    from payments.models import Transaction
    txns = Transaction.objects.filter(customer=user)
    if txns.exists():
        blockers['Payment Transactions'] = list(txns.values_list('transaction_reference', flat=True)[:5])
    
    # Flight bookings
    from flights.models import FlightBooking
    flights = FlightBooking.objects.filter(user=user)
    if flights.exists():
        blockers['Flight Bookings'] = list(flights.values_list('booking_reference', flat=True)[:5])
    
    # Tour bookings
    from tours.models import TourBooking
    tours = TourBooking.objects.filter(user=user)
    if tours.exists():
        blockers['Tour Bookings'] = list(tours.values_list('booking_reference', flat=True)[:5])
    
    # Bookings
    from bookings.models import Booking
    bookings = Booking.objects.filter(user=user)
    if bookings.exists():
        blockers['Property Bookings'] = list(bookings.values_list('id', flat=True)[:5])
    
    return blockers


@admin.register(User, site=admin_site)
class UserAdmin(BaseUserAdmin):
    list_display = ('email', 'first_name', 'last_name', 'is_staff', 'is_active', '_has_blockers', 'date_joined')
    list_filter = ('is_staff', 'is_active', 'is_business_account', 'country')
    search_fields = ('email', 'first_name', 'last_name', 'phone_number')
    ordering = ('-date_joined',)
    readonly_fields = ('last_login', 'date_joined', 'last_activity', 'email_verified_at', 'phone_verified_at')
    actions = ['anonymize_user']

    fieldsets = (
        (None, {'fields': ('email', 'password')}),
        ('Personal Info', {'fields': ('first_name', 'last_name', 'phone_number', 'date_of_birth', 'profile_picture')}),
        ('Address', {'fields': ('address', 'city', 'state', 'postal_code', 'country')}),
        ('Preferences', {'fields': ('preferred_language', 'preferred_currency', 'marketing_opt_in')}),
        ('Permissions', {'fields': ('is_active', 'is_staff', 'is_superuser', 'is_business_account', 'groups', 'user_permissions')}),
        ('Verification', {'fields': ('is_email_verified', 'is_phone_verified', 'email_verified_at', 'phone_verified_at')}),
        ('Important Dates', {'fields': ('last_login', 'date_joined', 'last_activity')}),
    )

    add_fieldsets = (
        (None, {
            'classes': ('wide',),
            'fields': ('email', 'password1', 'password2', 'first_name', 'last_name'),
        }),
    )

    def _has_blockers(self, obj):
        """Show indicator if user has records blocking deletion."""
        if _get_user_blockers(obj):
            return format_html('<span style="color: red; font-weight: bold;">⚠ Blocked</span>')
        return format_html('<span style="color: green;">✓ Clear</span>')
    _has_blockers.short_description = 'Deletion Status'

    def delete_model(self, request, obj):
        """Override delete to provide helpful error message on constraint violations."""
        try:
            super().delete_model(request, obj)
            messages.success(request, f'User "{obj.email}" has been deleted.')
        except (ProtectedError, IntegrityError) as exc:
            blockers = _get_user_blockers(obj)
            if blockers:
                msg = (
                    f'Cannot delete user "{obj.email}" — the following records still reference them:\n\n'
                )
                for model_name, examples in blockers.items():
                    msg += f'  • {model_name}: {", ".join(map(str, examples[:3]))}'
                    if len(examples) > 3:
                        msg += f' (+ {len(examples) - 3} more)'
                    msg += '\n'
                msg += (
                    '\n\nOptions:\n'
                    '  1. Use the "Anonymize User Data" action to deactivate instead of delete.\n'
                    '  2. Manually reassign or delete the blocking records.\n'
                    '  3. Contact support for bulk cleanup.'
                )
                messages.error(request, msg)
            else:
                messages.error(request, f'Could not delete user: {exc}')

    def delete_queryset(self, request, queryset):
        """Override bulk delete to catch errors and provide feedback."""
        deleted = 0
        failed = []
        
        for user in queryset:
            try:
                user.delete()
                deleted += 1
            except (ProtectedError, IntegrityError):
                blockers = _get_user_blockers(user)
                if blockers:
                    failed.append(f'{user.email} (has {", ".join(blockers.keys())})')
                else:
                    failed.append(user.email)
        
        if deleted:
            messages.success(request, f'Successfully deleted {deleted} user(s).')
        
        if failed:
            messages.warning(
                request,
                f'Could not delete {len(failed)} user(s) due to related records:\n' + '\n'.join(f'  • {u}' for u in failed[:10]) +
                (f'\n  ... and {len(failed) - 10} more' if len(failed) > 10 else '')
            )

    def anonymize_user(self, request, queryset):
        """Deactivate and anonymize user data instead of hard-deleting."""
        updated = 0
        for user in queryset:
            user.is_active = False
            user.first_name = '[Deleted]'
            user.last_name = f'User-{user.pk}'
            user.email = f'deleted-{user.pk}@example.invalid'
            user.phone_number = ''
            user.date_of_birth = None
            user.address = ''
            user.city = ''
            user.state = ''
            user.postal_code = ''
            user.save()
            updated += 1
        
        messages.success(
            request,
            f'Anonymized {updated} user(s). Their email, phone, and address have been cleared, '
            f'and their accounts are now deactivated. Associated bookings and transactions remain intact.'
        )
    anonymize_user.short_description = 'Anonymize selected users (safe alternative to delete)'


@admin.register(UserProfile, site=admin_site)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'travel_style', 'passport_number', 'passport_expiry')
    search_fields = ('user__email', 'passport_number', 'emergency_contact_name')
    list_filter = ('travel_style',)


@admin.register(BusinessAccount, site=admin_site)
class BusinessAccountAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'user', 'company_size', 'is_verified', 'created_at')
    list_filter = ('company_size', 'is_verified', 'approval_required')
    search_fields = ('company_name', 'user__email', 'company_registration_number')
    readonly_fields = ('verified_at',)