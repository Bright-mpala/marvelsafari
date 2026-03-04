from django.urls import path, reverse_lazy
from django.contrib.auth.views import (
    PasswordResetView, PasswordResetDoneView,
    PasswordResetCompleteView
)
from . import views

app_name = 'accounts'

urlpatterns = [
    # Authentication
    path('register/', views.UserRegistrationView.as_view(), name='register'),
    path('login/', views.UserLoginView.as_view(), name='login'),
    path('logout/', views.UserLogoutView.as_view(), name='logout'),
    
    # Email Verification
    path('verify/', views.EmailVerificationView.as_view(), name='verify_email'),
    path('verify/prompt/', views.verify_email_prompt, name='verify_email_prompt'),
    path('verify/resend/', views.ResendVerificationView.as_view(), name='resend_verification'),
    
    # Password management
    path('password-change/', views.UserPasswordChangeView.as_view(), name='password_change'),
    path('password-change/done/', views.UserPasswordChangeDoneView.as_view(), name='password_change_done'),
    path('password-reset/', PasswordResetView.as_view(
        template_name='accounts/password_reset.html',
        email_template_name='accounts/password_reset_email.html',
        html_email_template_name='accounts/password_reset_email_html.html',
        subject_template_name='accounts/password_reset_subject.txt',
        success_url=reverse_lazy('accounts:password_reset_done')
    ), name='password_reset'),
    path('password-reset/done/', PasswordResetDoneView.as_view(
        template_name='accounts/password_reset_done.html'
    ), name='password_reset_done'),
    path('password-reset/<uidb64>/<token>/', views.CustomPasswordResetConfirmView.as_view(), name='password_reset_confirm'),
    path('password-reset-complete/', PasswordResetCompleteView.as_view(
        template_name='accounts/password_reset_complete.html'
    ), name='password_reset_complete'),
    
    # Profile management
    path('dashboard/', views.dashboard, name='dashboard'),
    path('dashboard/received-bookings/<str:booking_type>/<uuid:booking_id>/approve/', views.approve_received_booking, name='approve_received_booking'),
    path('profile/', views.profile_view, name='profile'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('bookings/', views.booking_history, name='booking_history'),
    path('favorites/', views.favorites, name='favorites'),
    path('settings/', views.account_settings, name='settings'),
    path('business/enable/', views.enable_business_account, name='enable_business'),
]