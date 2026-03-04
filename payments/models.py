from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class PaymentGateway(models.Model):
    """Payment gateway configuration."""
    
    GATEWAY_TYPES = (
        ('stripe', 'Stripe'),
        ('paypal', 'PayPal'),
        ('braintree', 'Braintree'),
        ('authorize_net', 'Authorize.net'),
        ('adyen', 'Adyen'),
        ('razorpay', 'Razorpay'),
        ('offline', 'Offline'),
    )
    
    name = models.CharField(_('gateway name'), max_length=100)
    gateway_type = models.CharField(
        _('gateway type'),
        max_length=50,
        choices=GATEWAY_TYPES
    )
    
    # Configuration
    is_active = models.BooleanField(_('active'), default=True)
    is_test_mode = models.BooleanField(_('test mode'), default=True)
    
    # API credentials
    api_key = models.CharField(_('API key'), max_length=255, blank=True)
    api_secret = models.CharField(_('API secret'), max_length=255, blank=True)
    webhook_secret = models.CharField(_('webhook secret'), max_length=255, blank=True)
    
    # Configuration
    config = models.JSONField(
        _('configuration'),
        default=dict,
        blank=True,
        help_text=_('Gateway-specific configuration in JSON')
    )
    
    # Supported currencies
    supported_currencies = models.JSONField(
        _('supported currencies'),
        default=list,
        help_text=_('List of supported currency codes')
    )
    
    # Countries
    supported_countries = models.JSONField(
        _('supported countries'),
        default=list,
        blank=True,
        help_text=_('List of supported country codes')
    )
    
    # Fees
    transaction_fee_percent = models.DecimalField(
        _('transaction fee (%)'),
        max_digits=5,
        decimal_places=2,
        default=0
    )
    transaction_fee_fixed = models.DecimalField(
        _('fixed transaction fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.name} ({self.get_gateway_type_display()})"
    
    class Meta:
        verbose_name = _('payment gateway')
        verbose_name_plural = _('payment gateways')
        ordering = ['name']


class PaymentMethod(models.Model):
    """Payment methods available to users."""
    
    PAYMENT_METHOD_TYPES = (
        ('credit_card', _('Credit Card')),
        ('debit_card', _('Debit Card')),
        ('bank_account', _('Bank Account')),
        ('digital_wallet', _('Digital Wallet')),
        ('crypto', _('Cryptocurrency')),
        ('cash', _('Cash')),
        ('check', _('Check')),
    )
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='payment_methods'
    )
    method_type = models.CharField(
        _('method type'),
        max_length=50,
        choices=PAYMENT_METHOD_TYPES
    )
    
    # Card details (encrypted)
    card_last_four = models.CharField(_('card last four'), max_length=4, blank=True)
    card_brand = models.CharField(_('card brand'), max_length=50, blank=True)
    card_exp_month = models.PositiveSmallIntegerField(_('expiry month'), null=True, blank=True)
    card_exp_year = models.PositiveSmallIntegerField(_('expiry year'), null=True, blank=True)
    
    # Bank details (encrypted)
    bank_name = models.CharField(_('bank name'), max_length=100, blank=True)
    bank_last_four = models.CharField(_('account last four'), max_length=4, blank=True)
    
    # Wallet details
    wallet_type = models.CharField(_('wallet type'), max_length=50, blank=True)
    wallet_id = models.CharField(_('wallet ID'), max_length=255, blank=True)
    
    # Gateway reference
    gateway = models.ForeignKey(
        PaymentGateway,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='payment_methods'
    )
    gateway_customer_id = models.CharField(
        _('gateway customer ID'),
        max_length=255,
        blank=True
    )
    gateway_payment_method_id = models.CharField(
        _('gateway payment method ID'),
        max_length=255,
        blank=True
    )
    
    # Status
    is_default = models.BooleanField(_('default'), default=False)
    is_verified = models.BooleanField(_('verified'), default=False)
    is_active = models.BooleanField(_('active'), default=True)
    
    # Billing address
    billing_name = models.CharField(_('billing name'), max_length=255, blank=True)
    billing_address = models.TextField(_('billing address'), blank=True)
    billing_city = models.CharField(_('billing city'), max_length=100, blank=True)
    billing_state = models.CharField(_('billing state'), max_length=100, blank=True)
    billing_postal_code = models.CharField(_('billing postal code'), max_length=20, blank=True)
    billing_country = models.CharField(_('billing country'), max_length=100, blank=True)
    
    # Verification
    verified_at = models.DateTimeField(_('verified at'), null=True, blank=True)
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payment_methods'
    )
    
    # Security
    fingerprint = models.CharField(
        _('fingerprint'),
        max_length=255,
        blank=True,
        help_text=_('For duplicate detection')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.get_method_type_display()}"
    
    class Meta:
        verbose_name = _('payment method')
        verbose_name_plural = _('payment methods')
        ordering = ['-is_default', '-created_at']
    
    def save(self, *args, **kwargs):
        # Ensure only one default method per user
        if self.is_default:
            PaymentMethod.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)


class Transaction(models.Model):
    """Payment transactions."""
    
    TRANSACTION_TYPES = (
        ('payment', _('Payment')),
        ('refund', _('Refund')),
        ('authorization', _('Authorization')),
        ('capture', _('Capture')),
        ('void', _('Void')),
        ('chargeback', _('Chargeback')),
    )
    
    TRANSACTION_STATUS = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
        ('refunded', _('Refunded')),
        ('partially_refunded', _('Partially Refunded')),
        ('charged_back', _('Charged Back')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    transaction_reference = models.CharField(
        _('transaction reference'),
        max_length=50,
        unique=True,
        editable=False
    )
    
    # Payment details
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    transaction_type = models.CharField(
        _('transaction type'),
        max_length=50,
        choices=TRANSACTION_TYPES
    )
    
    # Gateway details
    gateway = models.ForeignKey(
        PaymentGateway,
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    gateway_transaction_id = models.CharField(
        _('gateway transaction ID'),
        max_length=255,
        blank=True
    )
    gateway_response = models.JSONField(
        _('gateway response'),
        default=dict,
        blank=True
    )
    
    # Payment method
    payment_method = models.ForeignKey(
        PaymentMethod,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Customer
    customer = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='transactions'
    )
    
    # Related bookings
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    flight_booking = models.ForeignKey(
        'flights.FlightBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    car_rental_booking = models.ForeignKey(
        'car_rentals.CarRentalBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    tour_booking = models.ForeignKey(
        'tours.TourBooking',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='transactions'
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=50,
        choices=TRANSACTION_STATUS,
        default='pending'
    )
    
    # Fees
    gateway_fee = models.DecimalField(
        _('gateway fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    platform_fee = models.DecimalField(
        _('platform fee'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    tax_amount = models.DecimalField(
        _('tax amount'),
        max_digits=10,
        decimal_places=2,
        default=0
    )
    
    # Net amount (amount after fees)
    net_amount = models.DecimalField(
        _('net amount'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Description
    description = models.TextField(_('description'), blank=True)
    notes = models.TextField(_('notes'), blank=True)
    
    # Error information
    error_code = models.CharField(_('error code'), max_length=100, blank=True)
    error_message = models.TextField(_('error message'), blank=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    # Risk assessment
    risk_score = models.DecimalField(
        _('risk score'),
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    risk_level = models.CharField(
        _('risk level'),
        max_length=20,
        blank=True,
        choices=[
            ('low', _('Low')),
            ('medium', _('Medium')),
            ('high', _('High')),
        ]
    )
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)
    settled_at = models.DateTimeField(_('settled at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('transaction')
        verbose_name_plural = _('transactions')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['transaction_reference']),
            models.Index(fields=['customer', 'created_at']),
            models.Index(fields=['status', 'created_at']),
        ]
    
    def __str__(self):
        return f"Transaction {self.transaction_reference} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        if not self.transaction_reference:
            import random
            import string
            self.transaction_reference = 'TXN-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=12)
            )
        
        # Calculate net amount
        self.net_amount = self.amount - self.gateway_fee - self.platform_fee - self.tax_amount
        
        super().save(*args, **kwargs)


class Refund(models.Model):
    """Refund records."""
    
    REFUND_STATUS = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    )
    
    REFUND_REASONS = (
        ('customer_request', _('Customer Request')),
        ('duplicate', _('Duplicate Transaction')),
        ('fraudulent', _('Fraudulent')),
        ('service_not_provided', _('Service Not Provided')),
        ('cancellation', _('Cancellation')),
        ('other', _('Other')),
    )
    
    transaction = models.ForeignKey(
        Transaction,
        on_delete=models.PROTECT,
        related_name='refunds'
    )
    refund_reference = models.CharField(
        _('refund reference'),
        max_length=50,
        unique=True
    )
    
    # Refund details
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    reason = models.CharField(
        _('reason'),
        max_length=50,
        choices=REFUND_REASONS
    )
    reason_description = models.TextField(_('reason description'), blank=True)
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=REFUND_STATUS,
        default='pending'
    )
    
    # Gateway details
    gateway_refund_id = models.CharField(
        _('gateway refund ID'),
        max_length=255,
        blank=True
    )
    gateway_response = models.JSONField(
        _('gateway response'),
        default=dict,
        blank=True
    )
    
    # Processor
    processed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_refunds'
    )
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    processed_at = models.DateTimeField(_('processed at'), null=True, blank=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    def __str__(self):
        return f"Refund {self.refund_reference} - {self.amount} {self.currency}"
    
    class Meta:
        verbose_name = _('refund')
        verbose_name_plural = _('refunds')
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.refund_reference:
            import random
            import string
            self.refund_reference = 'REF-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=12)
            )
        super().save(*args, **kwargs)


class CommissionPayment(models.Model):
    """Commission payments to property owners/tour operators."""
    
    PAYMENT_STATUS = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('paid', _('Paid')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    )
    
    PAYMENT_METHOD = (
        ('bank_transfer', _('Bank Transfer')),
        ('paypal', _('PayPal')),
        ('check', _('Check')),
        ('wire_transfer', _('Wire Transfer')),
        ('other', _('Other')),
    )
    
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.PROTECT,
        related_name='commission_payments'
    )
    
    # Recipient
    recipient = models.ForeignKey(
        'accounts.User',
        on_delete=models.PROTECT,
        related_name='commission_payments_received'
    )
    recipient_type = models.CharField(
        _('recipient type'),
        max_length=50,
        choices=[
            ('property_owner', _('Property Owner')),
            ('tour_operator', _('Tour Operator')),
            ('car_rental_company', _('Car Rental Company')),
        ]
    )
    
    # Payment details
    amount = models.DecimalField(_('amount'), max_digits=12, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Commission calculation
    commission_rate = models.DecimalField(
        _('commission rate'),
        max_digits=5,
        decimal_places=2,
        help_text=_('Percentage')
    )
    commission_amount = models.DecimalField(
        _('commission amount'),
        max_digits=12,
        decimal_places=2
    )
    platform_fee = models.DecimalField(
        _('platform fee'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    tax_amount = models.DecimalField(
        _('tax amount'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Payment method
    payment_method = models.CharField(
        _('payment method'),
        max_length=50,
        choices=PAYMENT_METHOD
    )
    
    # Payment details
    payment_reference = models.CharField(
        _('payment reference'),
        max_length=100,
        blank=True
    )
    transaction_id = models.CharField(
        _('transaction ID'),
        max_length=255,
        blank=True
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=PAYMENT_STATUS,
        default='pending'
    )
    
    # Dates
    payment_date = models.DateField(_('payment date'), null=True, blank=True)
    due_date = models.DateField(_('due date'))
    
    # Notes
    notes = models.TextField(_('notes'), blank=True)
    
    # Processing
    processed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='processed_commission_payments'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Commission Payment for {self.booking.booking_reference} - {self.amount} {self.currency}"
    
    class Meta:
        verbose_name = _('commission payment')
        verbose_name_plural = _('commission payments')
        ordering = ['-due_date']
    
    def save(self, *args, **kwargs):
        # Calculate commission amount
        if not self.commission_amount and self.booking and self.commission_rate:
            self.commission_amount = (self.booking.total_amount * self.commission_rate) / 100
        
        super().save(*args, **kwargs)


class PayoutAccount(models.Model):
    """Payout accounts for service providers."""
    
    ACCOUNT_TYPES = (
        ('bank_account', _('Bank Account')),
        ('paypal', _('PayPal')),
        ('stripe', _('Stripe')),
        ('wise', _('Wise')),
        ('other', _('Other')),
    )
    
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='payout_accounts'
    )
    account_type = models.CharField(
        _('account type'),
        max_length=50,
        choices=ACCOUNT_TYPES
    )
    
    # Account details
    account_name = models.CharField(_('account name'), max_length=255)
    account_number = models.CharField(_('account number'), max_length=100, blank=True)
    routing_number = models.CharField(_('routing number'), max_length=100, blank=True)
    iban = models.CharField(_('IBAN'), max_length=100, blank=True)
    swift_bic = models.CharField(_('SWIFT/BIC'), max_length=100, blank=True)
    
    # Bank details
    bank_name = models.CharField(_('bank name'), max_length=255, blank=True)
    bank_address = models.TextField(_('bank address'), blank=True)
    bank_city = models.CharField(_('bank city'), max_length=100, blank=True)
    bank_country = models.CharField(_('bank country'), max_length=100, blank=True)
    
    # PayPal/Stripe
    email = models.EmailField(_('email'), blank=True)
    account_id = models.CharField(_('account ID'), max_length=255, blank=True)
    
    # Verification
    is_verified = models.BooleanField(_('verified'), default=False)
    is_default = models.BooleanField(_('default'), default=False)
    
    # Documents
    verification_document = models.FileField(
        _('verification document'),
        upload_to='payout_verification/',
        blank=True,
        null=True
    )
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    
    # Metadata
    metadata = models.JSONField(_('metadata'), default=dict, blank=True)
    
    verified_at = models.DateTimeField(_('verified at'), null=True, blank=True)
    verified_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='verified_payout_accounts'
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.get_account_type_display()}"
    
    class Meta:
        verbose_name = _('payout account')
        verbose_name_plural = _('payout accounts')
        ordering = ['-is_default', '-created_at']
    
    def save(self, *args, **kwargs):
        # Ensure only one default account per user
        if self.is_default:
            PayoutAccount.objects.filter(
                user=self.user,
                is_default=True
            ).exclude(pk=self.pk).update(is_default=False)
        super().save(*args, **kwargs)