from django.contrib import admin
from .models import PaymentGateway, PaymentMethod, Transaction, Refund, CommissionPayment, PayoutAccount
from travel_booking.admin import admin_site

@admin.register(PaymentGateway, site=admin_site)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ('name', 'gateway_type', 'is_active', 'is_test_mode', 'created_at')
    list_filter = ('gateway_type', 'is_active', 'is_test_mode')
    search_fields = ('name', 'gateway_type')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PaymentMethod, site=admin_site)
class PaymentMethodAdmin(admin.ModelAdmin):
    list_display = ('user', 'method_type', 'card_last_four', 'is_default', 'is_active', 'created_at')
    list_filter = ('method_type', 'is_default', 'is_active')
    search_fields = ('user__email', 'card_last_four')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(Transaction, site=admin_site)
class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'customer', 'amount', 'currency', 'status', 'gateway', 'created_at')
    list_filter = ('status', 'currency', 'gateway', 'created_at')
    search_fields = ('customer__email', 'id', 'transaction_reference')
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'created_at'


@admin.register(Refund, site=admin_site)
class RefundAdmin(admin.ModelAdmin):
    list_display = ('transaction', 'amount', 'reason', 'status', 'processed_at')
    list_filter = ('status', 'reason')
    search_fields = ('transaction__id', 'transaction__user__email')
    readonly_fields = ('created_at', 'updated_at', 'processed_at')


@admin.register(CommissionPayment, site=admin_site)
class CommissionPaymentAdmin(admin.ModelAdmin):
    list_display = ('booking', 'recipient', 'amount', 'status', 'due_date', 'payment_date')
    list_filter = ('status', 'due_date')
    search_fields = ('booking__id', 'booking__property__name', 'recipient__email')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(PayoutAccount, site=admin_site)
class PayoutAccountAdmin(admin.ModelAdmin):
    list_display = ('user', 'account_type', 'account_name', 'is_verified', 'created_at')
    list_filter = ('account_type', 'is_verified')
    search_fields = ('user__email', 'account_name')
    readonly_fields = ('created_at', 'updated_at')
