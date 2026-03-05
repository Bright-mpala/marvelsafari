from django.db import models
from django.utils.translation import gettext_lazy as _
import uuid


class BusinessDepartment(models.Model):
    """Business departments for corporate accounts."""
    
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='departments'
    )
    name = models.CharField(_('department name'), max_length=100)
    code = models.CharField(_('department code'), max_length=50)
    description = models.TextField(_('description'), blank=True)
    
    # Manager
    manager = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='managed_departments'
    )
    
    # Budget
    monthly_budget = models.DecimalField(
        _('monthly budget'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Settings
    requires_approval = models.BooleanField(_('requires approval'), default=True)
    approval_level = models.PositiveSmallIntegerField(
        _('approval level'),
        default=1,
        help_text=_('Hierarchy level for approval chain')
    )
    
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.business_account.company_name} - {self.name}"
    
    class Meta:
        verbose_name = _('business department')
        verbose_name_plural = _('business departments')
        ordering = ['name']


class BusinessEmployee(models.Model):
    """Employees in business accounts."""
    
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='employees'
    )
    user = models.OneToOneField(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='business_employee'
    )
    
    # Employee info
    employee_id = models.CharField(_('employee ID'), max_length=50, blank=True)
    job_title = models.CharField(_('job title'), max_length=100, blank=True)
    department = models.ForeignKey(
        BusinessDepartment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='employees'
    )
    
    # Permissions
    can_book = models.BooleanField(_('can book'), default=True)
    can_approve = models.BooleanField(_('can approve'), default=False)
    approval_limit = models.DecimalField(
        _('approval limit'),
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        help_text=_('Maximum booking amount they can approve')
    )
    
    # Travel preferences
    travel_class = models.CharField(
        _('travel class'),
        max_length=50,
        blank=True,
        choices=[
            ('economy', _('Economy')),
            ('premium_economy', _('Premium Economy')),
            ('business', _('Business')),
            ('first', _('First Class')),
        ]
    )
    
    hotel_preference = models.JSONField(
        _('hotel preference'),
        default=dict,
        blank=True,
        help_text=_('Preferred hotel chains, star ratings, etc.')
    )
    
    car_rental_preference = models.JSONField(
        _('car rental preference'),
        default=dict,
        blank=True,
        help_text=_('Preferred car rental companies, car types, etc.')
    )
    
    # Status
    is_active = models.BooleanField(_('active'), default=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email} - {self.business_account.company_name}"
    
    class Meta:
        verbose_name = _('business employee')
        verbose_name_plural = _('business employees')
        unique_together = ['business_account', 'user']


class BusinessTravelPolicy(models.Model):
    """Travel policies for business accounts."""
    
    business_account = models.OneToOneField(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='business_travel_policy'
    )
    
    # Flight policies
    max_flight_cost = models.DecimalField(
        _('maximum flight cost'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    preferred_airlines = models.JSONField(
        _('preferred airlines'),
        default=list,
        blank=True
    )
    allowed_classes = models.JSONField(
        _('allowed classes'),
        default=list,
        help_text=_('List of allowed flight classes')
    )
    advance_booking_days = models.PositiveSmallIntegerField(
        _('advance booking days'),
        default=14,
        help_text=_('Minimum days before travel to book')
    )
    
    # Hotel policies
    max_hotel_cost_per_night = models.DecimalField(
        _('maximum hotel cost per night'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    preferred_hotel_chains = models.JSONField(
        _('preferred hotel chains'),
        default=list,
        blank=True
    )
    max_star_rating = models.PositiveSmallIntegerField(
        _('maximum star rating'),
        null=True,
        blank=True
    )
    
    # Car rental policies
    max_car_rental_cost_per_day = models.DecimalField(
        _('maximum car rental cost per day'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    preferred_car_types = models.JSONField(
        _('preferred car types'),
        default=list,
        blank=True
    )
    insurance_required = models.BooleanField(_('insurance required'), default=True)
    
    # Meal allowances
    daily_meal_allowance = models.DecimalField(
        _('daily meal allowance'),
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True
    )
    
    # Miscellaneous
    requires_receipts = models.BooleanField(_('requires receipts'), default=True)
    expense_report_deadline = models.PositiveSmallIntegerField(
        _('expense report deadline'),
        default=30,
        help_text=_('Days after travel to submit expenses')
    )
    
    # Approval workflow
    approval_levels = models.JSONField(
        _('approval levels'),
        default=list,
        help_text=_('Approval workflow configuration')
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"Travel Policy for {self.business_account.company_name}"
    
    class Meta:
        verbose_name = _('business travel policy')
        verbose_name_plural = _('business travel policies')


class BusinessBookingApproval(models.Model):
    """Booking approval workflow for business accounts."""
    
    APPROVAL_STATUS = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('cancelled', _('Cancelled')),
        ('escalated', _('Escalated')),
    )
    
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    
    # Booking reference
    booking = models.ForeignKey(
        'bookings.Booking',
        on_delete=models.CASCADE,
        related_name='approvals',
        null=True,
        blank=True
    )
    flight_booking = models.ForeignKey(
        'flights.FlightBooking',
        on_delete=models.CASCADE,
        related_name='approvals',
        null=True,
        blank=True
    )
    car_rental_booking = models.ForeignKey(
        'car_rentals.CarRentalBooking',
        on_delete=models.CASCADE,
        related_name='approvals',
        null=True,
        blank=True
    )
    tour_booking = models.ForeignKey(
        'tours.TourBooking',
        on_delete=models.CASCADE,
        related_name='approvals',
        null=True,
        blank=True
    )
    
    # Business context
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='booking_approvals'
    )
    employee = models.ForeignKey(
        BusinessEmployee,
        on_delete=models.CASCADE,
        related_name='booking_approvals'
    )
    
    # Approval chain
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='approvals_to_review'
    )
    approval_level = models.PositiveSmallIntegerField(_('approval level'), default=1)
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=APPROVAL_STATUS,
        default='pending'
    )
    
    # Decision
    decision_notes = models.TextField(_('decision notes'), blank=True)
    decision_date = models.DateTimeField(_('decision date'), null=True, blank=True)
    
    # Escalation
    escalated_to = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='escalated_approvals'
    )
    escalation_reason = models.TextField(_('escalation reason'), blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = _('business booking approval')
        verbose_name_plural = _('business booking approvals')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"Approval for {self.get_booking_reference()} - {self.status}"
    
    def get_booking_reference(self):
        """Get the booking reference based on booking type."""
        if self.booking:
            # Unified Booking model uses UUID primary keys (no booking_reference field).
            return getattr(self.booking, 'booking_reference', None) or f"BK-{str(self.booking_id)[:8].upper()}"
        elif self.flight_booking:
            return self.flight_booking.booking_reference
        elif self.car_rental_booking:
            return self.car_rental_booking.booking_reference
        elif self.tour_booking:
            return self.tour_booking.booking_reference
        return "No Booking"


class BusinessExpenseReport(models.Model):
    """Expense reports for business travel."""
    
    REPORT_STATUS = (
        ('draft', _('Draft')),
        ('submitted', _('Submitted')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('paid', _('Paid')),
    )
    
    business_account = models.ForeignKey(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='expense_reports'
    )
    employee = models.ForeignKey(
        BusinessEmployee,
        on_delete=models.CASCADE,
        related_name='expense_reports'
    )
    
    # Report details
    report_number = models.CharField(_('report number'), max_length=50, unique=True)
    title = models.CharField(_('title'), max_length=255)
    description = models.TextField(_('description'), blank=True)
    
    # Period
    start_date = models.DateField(_('start date'))
    end_date = models.DateField(_('end date'))
    
    # Totals
    total_amount = models.DecimalField(_('total amount'), max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(
        _('approved amount'),
        max_digits=12,
        decimal_places=2,
        default=0
    )
    
    # Status
    status = models.CharField(
        _('status'),
        max_length=20,
        choices=REPORT_STATUS,
        default='draft'
    )
    
    # Approval
    approver = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_expense_reports'
    )
    approval_date = models.DateTimeField(_('approval date'), null=True, blank=True)
    approval_notes = models.TextField(_('approval notes'), blank=True)
    
    # Payment
    paid_date = models.DateField(_('paid date'), null=True, blank=True)
    payment_reference = models.CharField(_('payment reference'), max_length=100, blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    submitted_at = models.DateTimeField(_('submitted at'), null=True, blank=True)
    
    def __str__(self):
        return f"Expense Report {self.report_number} - {self.employee.user.email}"
    
    class Meta:
        verbose_name = _('business expense report')
        verbose_name_plural = _('business expense reports')
        ordering = ['-created_at']
    
    def save(self, *args, **kwargs):
        if not self.report_number:
            import random
            import string
            self.report_number = 'EXP-' + ''.join(
                random.choices(string.ascii_uppercase + string.digits, k=10)
            )
        super().save(*args, **kwargs)


class ExpenseItem(models.Model):
    """Individual expense items."""
    
    CATEGORIES = (
        ('accommodation', _('Accommodation')),
        ('transportation', _('Transportation')),
        ('meals', _('Meals')),
        ('entertainment', _('Entertainment')),
        ('supplies', _('Supplies')),
        ('other', _('Other')),
    )
    
    expense_report = models.ForeignKey(
        BusinessExpenseReport,
        on_delete=models.CASCADE,
        related_name='items'
    )
    
    # Expense details
    date = models.DateField(_('date'))
    category = models.CharField(_('category'), max_length=50, choices=CATEGORIES)
    description = models.CharField(_('description'), max_length=255)
    amount = models.DecimalField(_('amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('currency'), max_length=3, default='USD')
    
    # Exchange rate for foreign currency
    exchange_rate = models.DecimalField(
        _('exchange rate'),
        max_digits=10,
        decimal_places=6,
        default=1
    )
    converted_amount = models.DecimalField(
        _('converted amount'),
        max_digits=10,
        decimal_places=2,
        help_text=_('Amount in report currency')
    )
    
    # Receipt
    receipt_image = models.ImageField(
        _('receipt image'),
        upload_to='expense_receipts/',
        blank=True,
        null=True
    )
    receipt_number = models.CharField(_('receipt number'), max_length=100, blank=True)
    
    # Business purpose
    business_purpose = models.TextField(_('business purpose'), blank=True)
    
    # Approval
    is_approved = models.BooleanField(_('approved'), default=False)
    approval_notes = models.TextField(_('approval notes'), blank=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.description} - {self.amount} {self.currency}"
    
    class Meta:
        verbose_name = _('expense item')
        verbose_name_plural = _('expense items')
        ordering = ['date']
    
    def save(self, *args, **kwargs):
        # Calculate converted amount
        self.converted_amount = self.amount * self.exchange_rate
        super().save(*args, **kwargs)


class BusinessDashboard(models.Model):
    """Business dashboard configuration and metrics."""
    
    business_account = models.OneToOneField(
        'accounts.BusinessAccount',
        on_delete=models.CASCADE,
        related_name='dashboard'
    )
    
    # Metrics (cached for performance)
    total_spent = models.DecimalField(
        _('total spent'),
        max_digits=15,
        decimal_places=2,
        default=0
    )
    total_bookings = models.PositiveIntegerField(_('total bookings'), default=0)
    active_travelers = models.PositiveIntegerField(_('active travelers'), default=0)
    
    # Monthly metrics
    monthly_spending = models.JSONField(
        _('monthly spending'),
        default=dict,
        blank=True
    )
    monthly_bookings = models.JSONField(
        _('monthly bookings'),
        default=dict,
        blank=True
    )
    
    # Top destinations
    top_destinations = models.JSONField(
        _('top destinations'),
        default=list,
        blank=True
    )
    
    # Policy compliance
    compliance_rate = models.DecimalField(
        _('compliance rate'),
        max_digits=5,
        decimal_places=2,
        default=100,
        help_text=_('Percentage of bookings compliant with policy')
    )
    
    # Savings
    total_savings = models.DecimalField(
        _('total savings'),
        max_digits=15,
        decimal_places=2,
        default=0,
        help_text=_('Savings from negotiated rates and policies')
    )
    
    # Last update
    last_updated = models.DateTimeField(_('last updated'), auto_now=True)
    
    def __str__(self):
        return f"Dashboard for {self.business_account.company_name}"
    
    class Meta:
        verbose_name = _('business dashboard')
        verbose_name_plural = _('business dashboards')
