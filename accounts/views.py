from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView, LogoutView, PasswordChangeView, PasswordChangeDoneView, PasswordResetConfirmView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from django.views import View
from django.views.generic import CreateView, TemplateView
from django.urls import reverse_lazy, reverse
from django.db.models import Count, Q, Sum
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta

from .models import User, UserProfile, BusinessAccount, EmailVerification
from .utils import send_verification_email, verify_email_code, VERIFICATION_CODE_EXPIRY_MINUTES
from .forms import (
    CustomUserCreationForm, CustomUserChangeForm, UserProfileForm,
    BusinessAccountForm, UserPasswordChangeForm, EmailVerificationForm,
    ResendVerificationForm
)
from bookings.models import Booking
from properties.models import Property
from car_rentals.models import Car, CarRentalBooking, TaxiBooking
from tours.models import TourOperator, TourBooking


# ========== AUTHENTICATION VIEWS ==========

class UserRegistrationView(CreateView):
    """Handle user registration with email verification."""
    form_class = CustomUserCreationForm
    template_name = 'accounts/register.html'
    success_url = reverse_lazy('accounts:verify_email_prompt')
    
    def dispatch(self, request, *args, **kwargs):
        """Redirect logged-in users to dashboard."""
        if request.user.is_authenticated:
            return redirect('accounts:dashboard')
        return super().dispatch(request, *args, **kwargs)
    
    def form_valid(self, form):
        """Handle successful registration."""
        response = super().form_valid(form)
        user = self.object
        
        # Send verification email
        email_sent = send_verification_email(user, self.request)
        
        if email_sent:
            messages.success(
                self.request,
                _('Account created successfully! Please check your email for the verification code.')
            )
        else:
            messages.warning(
                self.request,
                _('Account created but we couldn\'t send a verification email. Please contact support.')
            )
        
        # Store email in session for verification page
        self.request.session['verification_email'] = user.email
        
        return response


class EmailVerificationView(View):
    """Handle email verification with code."""
    template_name = 'accounts/verify_email.html'
    form_class = EmailVerificationForm
    
    def get(self, request):
        """Display verification form."""
        # Check if email is in session (from registration)
        email = request.session.get('verification_email')
        
        # Check if code and email in URL (auto-verification link)
        code = request.GET.get('code')
        email_from_url = request.GET.get('email')
        
        if code and email_from_url:
            # Auto-verification from email link
            return self.auto_verify(request, email_from_url, code)
        
        if not email and not request.user.is_authenticated:
            messages.error(request, _('Please register first.'))
            return redirect('accounts:register')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form, 'email': email})
    
    def post(self, request):
        """Verify the code."""
        form = self.form_class(request.POST)
        email = request.session.get('verification_email') or (request.user.email if request.user.is_authenticated else None)
        
        if not email:
            messages.error(request, _('Session expired. Please register again.'))
            return redirect('accounts:register')
        
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            messages.error(request, _('User not found.'))
            return redirect('accounts:register')
        
        if form.is_valid():
            code = form.cleaned_data['code']
            success, message = verify_email_code(user, code)
            
            if success:
                messages.success(request, message)
                # Clear session
                if 'verification_email' in request.session:
                    del request.session['verification_email']
                
                # Log the user in
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                
                return redirect('accounts:dashboard')
            else:
                messages.error(request, message)
        
        return render(request, self.template_name, {'form': form, 'email': email})
    
    def auto_verify(self, request, email, code):
        """Auto-verify from email link."""
        try:
            user = User.objects.get(email=email)
            success, message = verify_email_code(user, code)
            
            if success:
                messages.success(request, _('Email verified successfully! You are now logged in.'))
                login(request, user, backend='django.contrib.auth.backends.ModelBackend')
                return redirect('accounts:dashboard')
            else:
                messages.error(request, message)
                return redirect('accounts:verify_email_prompt')
        except User.DoesNotExist:
            messages.error(request, _('User not found.'))
            return redirect('accounts:register')


class ResendVerificationView(View):
    """Resend verification email."""
    template_name = 'accounts/resend_verification.html'
    form_class = ResendVerificationForm
    
    def get(self, request):
        """Display resend form."""
        if request.user.is_authenticated and not request.user.is_email_verified:
            # Auto-resend for logged-in unverified users
            send_verification_email(request.user, request)
            messages.success(request, _('A new verification code has been sent to your email.'))
            request.session['verification_email'] = request.user.email
            return redirect('accounts:verify_email_prompt')
        
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        """Resend verification email."""
        form = self.form_class(request.POST)
        
        if form.is_valid():
            email = form.cleaned_data['email']
            
            try:
                user = User.objects.get(email=email)
                
                if user.is_email_verified:
                    messages.info(request, _('This email is already verified. Please login.'))
                    return redirect('accounts:login')
                
                send_verification_email(user, request)
                messages.success(request, _('A new verification code has been sent to your email.'))
                request.session['verification_email'] = email
                return redirect('accounts:verify_email_prompt')
                
            except User.DoesNotExist:
                # Don't reveal if email exists
                messages.success(request, _('If an account exists with this email, a verification code has been sent.'))
                return redirect('accounts:login')
        
        return render(request, self.template_name, {'form': form})


class UserLoginView(LoginView):
    """Handle user login."""
    template_name = 'accounts/login.html'
    redirect_authenticated_user = True
    
    def get_success_url(self):
        """Redirect to next page or home."""
        next_url = self.request.GET.get('next')
        if next_url:
            return next_url
        return reverse_lazy('properties:list')
    
    def form_valid(self, form):
        """Log user in and check verification."""
        user = form.get_user()
        
        if not user.is_email_verified:
            # Store email in session for verification
            self.request.session['verification_email'] = user.email
            messages.warning(
                self.request,
                _('Please verify your email address before logging in. A new verification code has been sent.')
            )
            send_verification_email(user, self.request)
            return redirect('accounts:verify_email_prompt')
        
        response = super().form_valid(form)
        messages.success(self.request, _('Welcome back, {}!').format(user.first_name or user.email))
        return response


class UserLogoutView(LogoutView):
    """Handle user logout."""
    next_page = reverse_lazy('properties:list')
    http_method_names = ['get', 'post', 'options']

    def get(self, request, *args, **kwargs):
        """Support logout via GET requests used by navigation links."""
        logout(request)
        messages.success(request, _('You have been logged out successfully.'))
        return redirect(self.next_page)


class UserPasswordChangeView(LoginRequiredMixin, PasswordChangeView):
    """Allow users to change their password."""
    form_class = UserPasswordChangeForm
    template_name = 'accounts/password_change.html'
    success_url = reverse_lazy('accounts:password_change_done')


class UserPasswordChangeDoneView(LoginRequiredMixin, PasswordChangeDoneView):
    """Show password change success message."""
    template_name = 'accounts/password_change_done.html'


# ========== PROFILE VIEWS ==========

@login_required
def dashboard(request):
    """User dashboard with overview statistics."""
    user = request.user
    today = timezone.now().date()
    
    # Check if email is verified
    if not user.is_email_verified:
        messages.warning(
            request,
            _('Please verify your email address to access all features.')
        )
    
    # Bookings across stays, cars, and taxis
    stay_bookings = Booking.objects.filter(user=user).select_related('property')
    car_rental_bookings = CarRentalBooking.objects.filter(user=user).select_related('car', 'company')
    taxi_bookings = TaxiBooking.objects.filter(user=user).select_related('car', 'driver', 'company')

    total_bookings = stay_bookings.count() + car_rental_bookings.count() + taxi_bookings.count()

    upcoming_bookings = (
        stay_bookings.filter(check_in_date__gte=today, status__in=['confirmed', 'pending']).count()
        + car_rental_bookings.filter(pickup_date__gte=today, status__in=['confirmed', 'pending', 'active']).count()
        + taxi_bookings.filter(pickup_datetime__date__gte=today, status__in=['confirmed', 'pending', 'driver_assigned', 'en_route']).count()
    )

    completed_bookings = (
        stay_bookings.filter(status='completed').count()
        + car_rental_bookings.filter(status='completed').count()
        + taxi_bookings.filter(status='completed').count()
    )

    pending_bookings = (
        stay_bookings.filter(status='pending').count()
        + car_rental_bookings.filter(status='pending').count()
        + taxi_bookings.filter(status='pending').count()
    )

    # Recent bookings (combined and sorted by created_at)
    recent_items = []
    for b in stay_bookings:
        recent_items.append({
            'kind': 'stay',
            'title': getattr(b.property, 'name', 'Stay booking'),
            'location': f"{getattr(b.property, 'city', '')}, {getattr(b.property, 'country', '')}",
            'date_range': f"{b.check_in_date} - {b.check_out_date}",
            'status': b.status,
            'status_label': b.get_status_display(),
            'amount': b.total_amount,
            'created_at': b.created_at,
        })

    for b in car_rental_bookings:
        recent_items.append({
            'kind': 'car',
            'title': f"{getattr(b.car, 'make', 'Car')} {getattr(b.car, 'model', '')}".strip(),
            'location': getattr(b.pickup_location, 'city', '') if b.pickup_location else '',
            'date_range': f"{b.pickup_date} - {b.dropoff_date}",
            'status': b.status,
            'status_label': b.get_status_display(),
            'amount': b.total_amount,
            'created_at': b.created_at,
        })

    for b in taxi_bookings:
        recent_items.append({
            'kind': 'taxi',
            'title': 'Taxi ride',
            'location': b.pickup_address[:50] if b.pickup_address else '',
            'date_range': b.pickup_datetime.strftime('%Y-%m-%d %H:%M') if b.pickup_datetime else '',
            'status': b.status,
            'status_label': b.get_status_display(),
            'amount': b.total_fare,
            'created_at': b.created_at,
        })

    recent_bookings = sorted(recent_items, key=lambda x: x['created_at'], reverse=True)[:5]
    
    # Favorite destinations (most booked cities)
    favorite_destinations = stay_bookings.values(
        'property__city', 'property__country'
    ).annotate(
        booking_count=Count('id')
    ).order_by('-booking_count')[:5]
    
    # Calculate loyalty points (example: 100 points per booking)
    loyalty_points = total_bookings * 100
    
    # Alert: pending bookings needing confirmation
    pending_alert = pending_bookings > 0
    
    # =============================================================================
    # OWNER DASHBOARD DATA
    # =============================================================================
    
    # Properties owned by the user
    owned_properties = Property.objects.filter(owner=user, is_deleted=False).select_related('property_type')
    owned_properties_count = owned_properties.count()
    
    # Property bookings received (as owner)
    property_bookings_received = Booking.objects.filter(
        property__owner=user
    ).select_related('user', 'property').order_by('-created_at')[:10]
    
    # Cars owned by the user
    owned_cars = Car.objects.filter(owner=user, is_deleted=False).select_related('company', 'category')
    owned_cars_count = owned_cars.count()
    
    # Car rental and taxi bookings received (as owner)
    car_bookings_received = CarRentalBooking.objects.filter(
        car__owner=user
    ).select_related('user', 'car').order_by('-created_at')[:10]
    
    taxi_bookings_received = TaxiBooking.objects.filter(
        car__owner=user
    ).select_related('user', 'car').order_by('-created_at')[:10]
    
    # Tours operated by user (via TourOperator)
    tour_operators = TourOperator.objects.filter(user=user)
    owned_tours_count = 0
    tour_bookings_received = []
    
    if tour_operators.exists():
        from tours.models import Tour
        owned_tours_count = Tour.objects.filter(operator__user=user, is_deleted=False).count()
        tour_bookings_received = list(TourBooking.objects.filter(
            tour__operator__user=user
        ).select_related('user', 'tour').order_by('-created_at')[:10])
    
    # Aggregate owner stats
    is_owner = (owned_properties_count > 0 or owned_cars_count > 0 or owned_tours_count > 0)
    
    total_listings = owned_properties_count + owned_cars_count + owned_tours_count
    total_bookings_received = (
        property_bookings_received.count() + 
        car_bookings_received.count() + 
        len(taxi_bookings_received) +
        len(tour_bookings_received)
    )
    
    # Build unified received bookings list
    received_bookings = []
    
    for b in property_bookings_received[:5]:
        received_bookings.append({
            'type': 'property',
            'type_icon': 'building',
            'listing_name': b.property.name if b.property else 'Property',
            'guest_name': b.user.get_full_name() or b.user.email,
            'guest_email': b.user.email,
            'date_info': f"{b.check_in_date} - {b.check_out_date}",
            'guests': b.guests,
            'amount': b.total_amount,
            'status': b.status,
            'status_display': b.get_status_display(),
            'created_at': b.created_at,
            'booking_id': b.id,
        })
    
    for b in car_bookings_received[:5]:
        received_bookings.append({
            'type': 'car',
            'type_icon': 'car',
            'listing_name': f"{b.car.make} {b.car.model}" if b.car else 'Car',
            'guest_name': b.user.get_full_name() or b.user.email,
            'guest_email': b.user.email,
            'date_info': f"{b.pickup_date} - {b.dropoff_date}",
            'guests': 1,
            'amount': b.total_amount,
            'status': b.status,
            'status_display': b.get_status_display(),
            'created_at': b.created_at,
            'booking_id': b.id,
        })
    
    for b in taxi_bookings_received[:5]:
        received_bookings.append({
            'type': 'taxi',
            'type_icon': 'taxi',
            'listing_name': f"{b.car.make} {b.car.model}" if b.car else 'Taxi',
            'guest_name': b.user.get_full_name() or b.user.email,
            'guest_email': b.user.email,
            'date_info': b.pickup_datetime.strftime('%Y-%m-%d %H:%M') if b.pickup_datetime else 'TBD',
            'guests': getattr(b, 'passengers', 1),
            'amount': b.total_fare,
            'status': b.status,
            'status_display': b.get_status_display(),
            'created_at': b.created_at,
            'booking_id': b.id,
        })
    
    for b in tour_bookings_received[:5]:
        received_bookings.append({
            'type': 'tour',
            'type_icon': 'hiking',
            'listing_name': b.tour.name if b.tour else 'Tour',
            'guest_name': b.user.get_full_name() or b.user.email,
            'guest_email': b.user.email,
            'date_info': b.tour_date.strftime('%Y-%m-%d') if hasattr(b, 'tour_date') and b.tour_date else 'TBD',
            'guests': getattr(b, 'participant_count', 1),
            'amount': b.total_price if hasattr(b, 'total_price') else 0,
            'status': b.status,
            'status_display': b.get_status_display(),
            'created_at': b.created_at,
            'booking_id': b.id,
        })
    
    # Sort by created_at
    received_bookings = sorted(received_bookings, key=lambda x: x['created_at'], reverse=True)[:10]
    
    context = {
        'total_bookings': total_bookings,
        'upcoming_bookings': upcoming_bookings,
        'completed_bookings': completed_bookings,
        'pending_bookings': pending_bookings,
        'loyalty_points': loyalty_points,
        'recent_bookings': recent_bookings,
        'favorite_destinations': favorite_destinations,
        'car_rental_count': car_rental_bookings.count(),
        'taxi_booking_count': taxi_bookings.count(),
        'stay_booking_count': stay_bookings.count(),
        'pending_alert': pending_alert,
        'email_verified': user.is_email_verified,
        # Owner dashboard data
        'is_owner': is_owner,
        'owned_properties': owned_properties,
        'owned_properties_count': owned_properties_count,
        'owned_cars': owned_cars,
        'owned_cars_count': owned_cars_count,
        'owned_tours_count': owned_tours_count,
        'total_listings': total_listings,
        'total_bookings_received': total_bookings_received,
        'received_bookings': received_bookings,
    }
    
    return render(request, 'accounts/dashboard.html', context)


@login_required
def approve_received_booking(request, booking_type, booking_id):
    """Allow listing owners to approve received bookings from their dashboard.

    Supports property, car, taxi, and tour bookings.
    """
    user = request.user
    booking = None
    email_recipient = None
    listing_label = None
    check_in = None
    check_out = None

    if booking_type == 'property':
        booking = get_object_or_404(Booking, id=booking_id, property__owner=user)
        listing_label = booking.property.name if booking.property else _('Property booking')
        email_recipient = booking.user.email
        check_in = booking.check_in_date
        check_out = booking.check_out_date
        current_status = booking.status
        confirmed_value = Booking.BookingStatus.CONFIRMED
    elif booking_type == 'car':
        booking = get_object_or_404(CarRentalBooking, id=booking_id, car__owner=user)
        listing_label = f"{booking.car.make} {booking.car.model}" if booking.car else _('Car rental')
        email_recipient = booking.user.email or booking.driver_email
        check_in = booking.pickup_date
        check_out = booking.dropoff_date
        current_status = booking.status
        confirmed_value = 'confirmed'
    elif booking_type == 'taxi':
        booking = get_object_or_404(TaxiBooking, id=booking_id, car__owner=user)
        listing_label = f"Taxi - {booking.pickup_address[:40]}" if booking.pickup_address else _('Taxi ride')
        email_recipient = booking.user.email or booking.passenger_email
        check_in = booking.pickup_datetime
        check_out = None
        current_status = booking.status
        confirmed_value = 'confirmed'
    elif booking_type == 'tour':
        booking = get_object_or_404(TourBooking, id=booking_id, tour__operator__user=user)
        listing_label = booking.tour.name if booking.tour else _('Tour booking')
        email_recipient = booking.user.email or booking.contact_email
        check_in = getattr(booking, 'tour_date', None)
        check_out = None
        current_status = booking.status
        confirmed_value = 'confirmed'
    else:
        messages.error(request, _('Unsupported booking type.'))
        return redirect('accounts:dashboard')

    # Only update if still pending
    if current_status == 'pending':
        booking.status = confirmed_value
        booking.save(update_fields=['status'])

        if email_recipient:
            from django.template.loader import render_to_string

            if check_in and check_out:
                date_info = _('{check_in} to {check_out}').format(check_in=check_in, check_out=check_out)
            elif check_in:
                date_info = str(check_in)
            else:
                date_info = ''

            context = {
                'user_name': booking.user.get_full_name() or booking.user.email,
                'listing_label': listing_label,
                'date_info': date_info,
            }

            text_body = render_to_string('bookings/emails/booking_approved.txt', context)
            html_body = render_to_string('bookings/emails/booking_approved.html', context)

            send_mail(
                subject=_('Your booking has been approved'),
                message=text_body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[email_recipient],
                html_message=html_body,
                fail_silently=True,
            )

        messages.success(
            request,
            _('Booking has been approved and the guest has been notified.'),
        )
    else:
        messages.info(
            request,
            _('This booking is already processed (status: {status}).').format(status=current_status),
        )

    return redirect('accounts:dashboard')


@login_required
def profile_view(request):
    """View user profile."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    business_account = None
    
    if user.is_business_account:
        business_account, _ = BusinessAccount.objects.get_or_create(user=user)
    
    # Booking statistics for profile
    total_bookings = Booking.objects.filter(user=user).count()
    completed_bookings = Booking.objects.filter(user=user, status='completed').count()
    confirmed_bookings = Booking.objects.filter(user=user, status='confirmed').count()

    # Car & taxi bookings
    car_rental_count = CarRentalBooking.objects.filter(user=user).count()
    taxi_booking_count = TaxiBooking.objects.filter(user=user).count()
    total_travel_bookings = total_bookings + car_rental_count + taxi_booking_count
    
    context = {
        'user': user,
        'profile': profile,
        'business_account': business_account,
        'total_bookings': total_bookings,
        'completed_bookings': completed_bookings,
        'confirmed_bookings': confirmed_bookings,
        'car_rental_count': car_rental_count,
        'taxi_booking_count': taxi_booking_count,
        'total_travel_bookings': total_travel_bookings,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
def profile_edit(request):
    """Edit user profile and preferences."""
    user = request.user
    profile, _ = UserProfile.objects.get_or_create(user=user)
    business_account = None
    business_form = None
    
    if request.method == 'POST':
        form = CustomUserChangeForm(request.POST, request.FILES, instance=user)
        profile_form = UserProfileForm(request.POST, instance=profile)
        
        if user.is_business_account:
            business_account, _ = BusinessAccount.objects.get_or_create(user=user)
            business_form = BusinessAccountForm(request.POST, instance=business_account)
        
        if form.is_valid() and profile_form.is_valid():
            form.save()
            profile_form.save()
            
            if business_form and business_form.is_valid():
                business_form.save()
            
            messages.success(request, _('Profile updated successfully!'))
            return redirect('accounts:profile')
        else:
            if form.errors:
                for field, errors in form.errors.items():
                    messages.error(request, f"{field}: {', '.join(errors)}")
    else:
        form = CustomUserChangeForm(instance=user)
        profile_form = UserProfileForm(instance=profile)
        
        if user.is_business_account:
            business_account, _ = BusinessAccount.objects.get_or_create(user=user)
            business_form = BusinessAccountForm(instance=business_account)
    
    context = {
        'form': form,
        'profile_form': profile_form,
        'business_form': business_form,
        'user': user,
    }
    
    return render(request, 'accounts/profile_edit.html', context)


@login_required
def booking_history(request):
    """View user's booking history with filtering."""
    bookings = Booking.objects.filter(user=request.user).select_related(
        'property'
    ).order_by('-created_at')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter in dict(Booking.BOOKING_STATUS):
        bookings = bookings.filter(status=status_filter)
    
    # Filter by date
    date_filter = request.GET.get('date')
    today = timezone.now().date()
    if date_filter == 'upcoming':
        bookings = bookings.filter(check_in_date__gte=today)
    elif date_filter == 'past':
        bookings = bookings.filter(check_out_date__lt=today)
    
    # Statistics
    total_bookings = Booking.objects.filter(user=request.user).count()
    upcoming_count = Booking.objects.filter(
        user=request.user,
        check_in_date__gte=today,
        status__in=['confirmed', 'pending']
    ).count()
    completed_count = Booking.objects.filter(
        user=request.user,
        status='completed'
    ).count()
    total_spent = Booking.objects.filter(
        user=request.user,
        status__in=['confirmed', 'completed']
    ).aggregate(total=Sum('total_amount'))['total'] or 0
    
    context = {
        'bookings': bookings,
        'status_filter': status_filter,
        'date_filter': date_filter,
        'total_bookings': total_bookings,
        'upcoming_count': upcoming_count,
        'completed_count': completed_count,
        'total_spent': total_spent,
    }
    
    return render(request, 'accounts/booking_history.html', context)


@login_required
def favorites(request):
    """View saved favorite properties (if wishlist feature enabled)."""
    context = {
        'message': _('Favorites feature coming soon!')
    }
    return render(request, 'accounts/favorites.html', context)


@login_required
def account_settings(request):
    """Account settings and preferences."""
    user = request.user
    
    context = {
        'user': user,
        'email_verified': user.is_email_verified,
        'phone_verified': user.is_phone_verified,
    }
    
    return render(request, 'accounts/account_settings.html', context)


@login_required
def enable_business_account(request):
    """Enable business account for user."""
    user = request.user
    
    if request.method == 'POST':
        user.is_business_account = True
        user.save()
        
        # Create default business account
        BusinessAccount.objects.get_or_create(
            user=user,
            defaults={
                'company_name': user.full_name or user.email
            }
        )
        
        messages.success(request, _('Business account enabled! Complete your company details.'))
        return redirect('accounts:profile_edit')
    
    return render(request, 'accounts/enable_business_account.html')


def verify_email_prompt(request):
    """Show prompt to verify email."""
    if request.user.is_authenticated and request.user.is_email_verified:
        return redirect('accounts:dashboard')
    
    email = request.session.get('verification_email') or (
        request.user.email if request.user.is_authenticated else ''
    )
    if not email and not request.user.is_authenticated:
        messages.info(request, _('Please register or login to verify your email.'))
        return redirect('accounts:login')
    
    return render(request, 'accounts/verify_email_prompt.html', {'email': email})


class CustomPasswordResetConfirmView(PasswordResetConfirmView):
    """Custom password reset confirm view with better session handling."""
    template_name = 'accounts/password_reset_confirm.html'
    success_url = reverse_lazy('accounts:password_reset_complete')
    
    def dispatch(self, request, *args, **kwargs):
        """Override to handle token validation with better logging."""
        import logging
        logger = logging.getLogger(__name__)
        
        token = kwargs.get('token', '')
        uidb64 = kwargs.get('uidb64', '')
        
        logger.info(f"Password reset attempt: uidb64={uidb64}, token_prefix={token[:10] if token else 'none'}...")
        
        return super().dispatch(request, *args, **kwargs)