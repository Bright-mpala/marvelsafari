from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Q, Avg
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from datetime import timedelta
from decimal import Decimal
import csv

from .models import (
    BusinessBookingApproval, BusinessDepartment, BusinessEmployee,
    BusinessTravelPolicy, BusinessExpenseReport, ExpenseItem
)
from accounts.models import User


def _resolve_business_context(user):
    """
    Resolve business account access for both account owners and employees.
    """
    business_account = getattr(user, 'business_account', None)
    if business_account:
        employee = BusinessEmployee.objects.filter(
            business_account=business_account,
            user=user,
            is_active=True,
        ).select_related('department').first()
        return business_account, employee

    employee = BusinessEmployee.objects.select_related('business_account', 'department').filter(
        user=user,
        is_active=True,
    ).first()
    if employee:
        return employee.business_account, employee
    return None, None


def _user_can_approve_for_account(user, business_account, employee=None):
    """Return whether the user can act as an approver for this business account."""
    if not business_account:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if business_account.user_id == user.id:
        return True
    return bool(employee and employee.business_account_id == business_account.id and employee.can_approve)


def _approval_total_amount(approval):
    """Return the total monetary amount for any approval booking type."""
    if approval.booking and approval.booking.total_amount is not None:
        return approval.booking.total_amount
    if approval.flight_booking and approval.flight_booking.total_amount is not None:
        return approval.flight_booking.total_amount
    if approval.car_rental_booking and approval.car_rental_booking.total_amount is not None:
        return approval.car_rental_booking.total_amount
    if approval.tour_booking and approval.tour_booking.total_amount is not None:
        return approval.tour_booking.total_amount
    return Decimal('0')


def _approval_destination(approval):
    """Resolve city/country for different approval booking types."""
    if approval.booking and approval.booking.property:
        property_obj = approval.booking.property
        return property_obj.city, str(property_obj.country or '')
    if approval.flight_booking and approval.flight_booking.flight_schedule:
        destination = approval.flight_booking.flight_schedule.flight.destination
        return destination.city, destination.country
    if approval.car_rental_booking and approval.car_rental_booking.dropoff_location:
        location = approval.car_rental_booking.dropoff_location
        return location.city, str(location.country or '')
    if approval.tour_booking and approval.tour_booking.tour:
        tour = approval.tour_booking.tour
        return tour.city, tour.country
    return '', ''


def _format_trend(current, previous):
    """Format trend percentage between two windows."""
    if previous > 0:
        percent = ((current - previous) / previous) * 100
    elif current > 0:
        percent = 100
    else:
        percent = 0
    rounded = round(percent, 1)
    sign = '+' if rounded > 0 else ''
    return f"{sign}{rounded}%"


def _parse_csv_list(value):
    """Parse comma/newline separated values from form inputs."""
    if not value:
        return []
    normalized = value.replace('\r', '\n')
    items = []
    for line in normalized.split('\n'):
        for chunk in line.split(','):
            chunk = chunk.strip()
            if chunk:
                items.append(chunk)
    return items


@login_required
def business_dashboard(request):
    """Business dashboard with core operational metrics."""
    business_account, _ = _resolve_business_context(request.user)

    if not business_account:
        return render(request, 'business/dashboard.html', {
            'business_account': None,
            'has_business': False
        })

    departments = BusinessDepartment.objects.filter(
        business_account=business_account,
        is_active=True
    ).annotate(
        employee_count=Count('employees', filter=Q(employees__is_active=True))
    )

    employees = BusinessEmployee.objects.filter(
        business_account=business_account,
        is_active=True
    ).select_related('user', 'department')[:12]

    approvals = BusinessBookingApproval.objects.filter(
        business_account=business_account
    ).select_related(
        'employee__user',
        'approver',
        'booking__property',
        'flight_booking__flight_schedule__flight__destination',
        'car_rental_booking__dropoff_location',
        'tour_booking__tour',
    ).order_by('-created_at')

    pending_approvals = approvals.filter(status='pending').count()
    approved_approvals = approvals.filter(status='approved').count()
    rejected_approvals = approvals.filter(status='rejected').count()

    approved_spend = Decimal('0')
    for approval in approvals.filter(status='approved'):
        approved_spend += _approval_total_amount(approval)

    now = timezone.now()
    last_30_days = now - timedelta(days=30)
    previous_30_days = now - timedelta(days=60)

    pending_recent = approvals.filter(status='pending', created_at__gte=last_30_days).count()
    pending_previous = approvals.filter(
        status='pending',
        created_at__gte=previous_30_days,
        created_at__lt=last_30_days
    ).count()
    approved_recent = approvals.filter(status='approved', created_at__gte=last_30_days).count()
    approved_previous = approvals.filter(
        status='approved',
        created_at__gte=previous_30_days,
        created_at__lt=last_30_days
    ).count()
    rejected_recent = approvals.filter(status='rejected', created_at__gte=last_30_days).count()
    rejected_previous = approvals.filter(
        status='rejected',
        created_at__gte=previous_30_days,
        created_at__lt=last_30_days
    ).count()

    approved_recent_spend = Decimal('0')
    for approval in approvals.filter(status='approved', decision_date__gte=last_30_days):
        approved_recent_spend += _approval_total_amount(approval)

    approved_previous_spend = Decimal('0')
    for approval in approvals.filter(status='approved', decision_date__gte=previous_30_days, decision_date__lt=last_30_days):
        approved_previous_spend += _approval_total_amount(approval)

    pending_trend = _format_trend(pending_recent, pending_previous)
    approved_trend = _format_trend(approved_recent, approved_previous)
    rejected_trend = _format_trend(rejected_recent, rejected_previous)
    spend_trend = _format_trend(float(approved_recent_spend), float(approved_previous_spend))

    monthly_map = {}
    six_months_ago = now - timedelta(days=180)
    for approval in approvals.filter(created_at__gte=six_months_ago):
        month_key = approval.created_at.strftime('%Y-%m')
        if month_key not in monthly_map:
            monthly_map[month_key] = {
                'month_key': month_key,
                'month_label': approval.created_at.strftime('%b %Y'),
                'approved_count': 0,
                'pending_count': 0,
                'spend': Decimal('0'),
            }
        entry = monthly_map[month_key]
        if approval.status == 'approved':
            entry['approved_count'] += 1
            entry['spend'] += _approval_total_amount(approval)
        elif approval.status == 'pending':
            entry['pending_count'] += 1

    monthly_summary = [monthly_map[key] for key in sorted(monthly_map.keys())]
    max_monthly_spend = max((entry['spend'] for entry in monthly_summary), default=Decimal('0'))
    for entry in monthly_summary:
        if max_monthly_spend > 0:
            entry['spend_percent'] = round(float((entry['spend'] / max_monthly_spend) * 100), 1)
        else:
            entry['spend_percent'] = 0

    destination_summary = {}
    for approval in approvals.filter(status='approved'):
        city, country = _approval_destination(approval)
        if not city:
            continue
        key = (city, country)
        if key not in destination_summary:
            destination_summary[key] = {
                'city': city,
                'country': country,
                'count': 0,
                'total_amount': Decimal('0'),
            }
        destination_summary[key]['count'] += 1
        destination_summary[key]['total_amount'] += _approval_total_amount(approval)

    top_destinations = sorted(
        destination_summary.values(),
        key=lambda item: (item['count'], item['total_amount']),
        reverse=True
    )[:5]

    recent_expenses = BusinessExpenseReport.objects.filter(
        business_account=business_account
    ).select_related('employee__user').order_by('-submitted_at')[:5]

    try:
        policy = BusinessTravelPolicy.objects.get(business_account=business_account)
    except BusinessTravelPolicy.DoesNotExist:
        policy = None

    total_employees = BusinessEmployee.objects.filter(
        business_account=business_account,
        is_active=True
    ).count()

    active_travelers = BusinessEmployee.objects.filter(
        business_account=business_account,
        is_active=True
    ).filter(
        Q(booking_approvals__isnull=False)
    ).distinct().count()

    decisions_count = approved_approvals + rejected_approvals
    approval_success_rate = round((approved_approvals / decisions_count) * 100, 1) if decisions_count else 0

    context = {
        'business_account': business_account,
        'has_business': True,
        'departments': departments[:6],
        'employees': employees,
        'recent_approvals': approvals[:8],
        'pending_approvals': pending_approvals,
        'approved_approvals': approved_approvals,
        'rejected_approvals': rejected_approvals,
        'approved_spend': approved_spend,
        'pending_trend': pending_trend,
        'approved_trend': approved_trend,
        'rejected_trend': rejected_trend,
        'spend_trend': spend_trend,
        'monthly_summary': monthly_summary,
        'top_destinations': top_destinations,
        'recent_expenses': recent_expenses,
        'policy': policy,
        'total_employees': total_employees,
        'active_travelers': active_travelers,
        'approval_success_rate': approval_success_rate,
    }

    return render(request, 'business/dashboard.html', context)


@login_required
def department_list(request):
    """View all departments."""
    business_account, _ = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    departments = BusinessDepartment.objects.filter(
        business_account=business_account
    ).annotate(
        employee_count=Count('employees', filter=Q(employees__is_active=True))
    ).order_by('name')
    
    employees = BusinessEmployee.objects.filter(
        business_account=business_account,
        is_active=True
    ).select_related('user')
    
    return render(request, 'business/departments.html', {
        'business_account': business_account,
        'departments': departments,
        'employees': employees
    })


@login_required
def create_department(request):
    """Create a new department."""
    if request.method == 'POST':
        business_account = getattr(request.user, 'business_account', None)
        if not business_account:
            messages.error(request, "You don't have a business account.")
            return redirect('business:business_dashboard')
        
        name = request.POST.get('name')
        code = request.POST.get('code')
        manager_id = request.POST.get('manager')
        monthly_budget = request.POST.get('monthly_budget')
        requires_approval = request.POST.get('requires_approval') == 'on'
        
        if not name or not code:
            messages.error(request, "Name and code are required.")
            return redirect('business:departments')
        
        # Check if code is unique for this business
        if BusinessDepartment.objects.filter(business_account=business_account, code=code).exists():
            messages.error(request, f"Department code '{code}' already exists.")
            return redirect('business:departments')
        
        manager = None
        if manager_id:
            try:
                manager = User.objects.get(id=manager_id)
            except User.DoesNotExist:
                pass
        
        department = BusinessDepartment.objects.create(
            business_account=business_account,
            name=name,
            code=code,
            manager=manager,
            monthly_budget=monthly_budget if monthly_budget else None,
            requires_approval=requires_approval
        )
        
        messages.success(request, f"Department '{name}' created successfully.")
        return redirect('business:departments')
    
    return redirect('business:departments')


@login_required
def employee_list(request):
    """View all employees."""
    business_account, _ = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    employees_list = BusinessEmployee.objects.filter(
        business_account=business_account
    ).select_related('user', 'department').order_by('user__email')
    
    # Pagination
    paginator = Paginator(employees_list, 12)
    page_number = request.GET.get('page')
    employees = paginator.get_page(page_number)
    
    departments = BusinessDepartment.objects.filter(
        business_account=business_account,
        is_active=True
    )
    
    active_travelers = employees_list.filter(
        Q(booking_approvals__isnull=False)
    ).distinct().count()
    
    approvers_count = employees_list.filter(can_approve=True).count()
    pending_invites = employees_list.filter(user__is_active=False).count()
    
    context = {
        'business_account': business_account,
        'employees': employees,
        'departments': departments,
        'active_travelers': active_travelers,
        'approvers_count': approvers_count,
        'pending_invites': pending_invites,
    }
    
    return render(request, 'business/employees.html', context)


@login_required
def invite_employee(request):
    """Invite a new employee."""
    if request.method == 'POST':
        business_account = getattr(request.user, 'business_account', None)
        if not business_account:
            messages.error(request, "You don't have a business account.")
            return redirect('business:business_dashboard')
        
        email = request.POST.get('email')
        employee_id = request.POST.get('employee_id')
        job_title = request.POST.get('job_title')
        department_id = request.POST.get('department')
        can_book = request.POST.get('can_book') == 'on'
        can_approve = request.POST.get('can_approve') == 'on'
        approval_limit = request.POST.get('approval_limit')
        travel_class = request.POST.get('travel_class', 'economy')
        
        if not email:
            messages.error(request, "Email is required.")
            return redirect('business:employees')
        
        # Check if user already exists
        try:
            user = User.objects.get(email=email)
            # Check if already an employee
            if BusinessEmployee.objects.filter(business_account=business_account, user=user).exists():
                messages.error(request, f"User {email} is already an employee.")
                return redirect('business:employees')
        except User.DoesNotExist:
            # Create new user
            user = User.objects.create_user(
                email=email,
                password=None,
                is_active=False  # Inactive until they accept invitation
            )
        
        department = None
        if department_id:
            try:
                department = BusinessDepartment.objects.get(id=department_id, business_account=business_account)
            except BusinessDepartment.DoesNotExist:
                pass
        
        # Create employee record
        employee = BusinessEmployee.objects.create(
            business_account=business_account,
            user=user,
            employee_id=employee_id,
            job_title=job_title,
            department=department,
            can_book=can_book,
            can_approve=can_approve,
            approval_limit=approval_limit if approval_limit else None,
            travel_class=travel_class
        )
        
        # TODO: Send invitation email
        
        messages.success(request, f"Invitation sent to {email}")
        return redirect('business:employees')
    
    return redirect('business:employees')


@login_required
def export_employees(request):
    """Export employees to CSV."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        return HttpResponse("No business account", status=400)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="employees.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Email', 'Name', 'Employee ID', 'Job Title', 'Department', 'Can Book', 'Can Approve', 'Active'])
    
    employees = BusinessEmployee.objects.filter(
        business_account=business_account
    ).select_related('user', 'department')
    
    for emp in employees:
        writer.writerow([
            emp.user.email,
            emp.user.get_full_name(),
            emp.employee_id,
            emp.job_title,
            emp.department.name if emp.department else '',
            'Yes' if emp.can_book else 'No',
            'Yes' if emp.can_approve else 'No',
            'Yes' if emp.is_active else 'No'
        ])
    
    return response


@login_required
def policy_list(request):
    """View travel policies."""
    business_account, _ = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')

    try:
        policy = BusinessTravelPolicy.objects.get(business_account=business_account)
    except BusinessTravelPolicy.DoesNotExist:
        policy = None

    approvals = BusinessBookingApproval.objects.filter(
        business_account=business_account
    ).select_related(
        'booking__property',
        'flight_booking__flight_schedule__flight__destination',
        'car_rental_booking__dropoff_location',
        'tour_booking__tour',
    )
    approved_approvals = approvals.filter(status='approved')
    approved_amounts = [_approval_total_amount(approval) for approval in approved_approvals]
    approved_total = sum(approved_amounts, Decimal('0'))
    approved_count = len(approved_amounts)
    avg_approved_amount = approved_total / approved_count if approved_count else Decimal('0')
    total_decisions = approvals.filter(status__in=['approved', 'rejected']).count()
    pending_approvals = approvals.filter(status='pending').count()

    allowed_classes_display = policy.allowed_classes if policy and policy.allowed_classes else ['economy']
    preferred_airlines_display = policy.preferred_airlines if policy else []
    preferred_hotel_chains_display = policy.preferred_hotel_chains if policy else []
    preferred_car_types_display = policy.preferred_car_types if policy and policy.preferred_car_types else ['standard']
    approval_levels_display = policy.approval_levels if policy and policy.approval_levels else ['Manager']

    context = {
        'business_account': business_account,
        'policy': policy,
        'policy_count': 1 if policy else 0,
        'total_decisions': total_decisions,
        'pending_approvals': pending_approvals,
        'avg_approved_amount': avg_approved_amount,
        'allowed_classes_display': allowed_classes_display,
        'preferred_airlines_display': preferred_airlines_display,
        'preferred_hotel_chains_display': preferred_hotel_chains_display,
        'preferred_car_types_display': preferred_car_types_display,
        'approval_levels_display': approval_levels_display,
    }

    return render(request, 'business/policies.html', context)


@login_required
def create_policy(request):
    """Create a new travel policy."""
    if request.method == 'POST':
        business_account, _ = _resolve_business_context(request.user)
        if not business_account:
            messages.error(request, "You don't have a business account.")
            return redirect('business:business_dashboard')

        # Check if policy already exists
        if BusinessTravelPolicy.objects.filter(business_account=business_account).exists():
            messages.error(request, "A policy already exists for this account.")
            return redirect('business:policies')

        max_flight_cost = request.POST.get('max_flight_cost')
        advance_booking_days = request.POST.get('advance_booking_days', 14)
        max_hotel_cost_per_night = request.POST.get('max_hotel_cost_per_night')
        max_star_rating = request.POST.get('max_star_rating', 4)
        max_car_rental_cost_per_day = request.POST.get('max_car_rental_cost_per_day')
        insurance_required = request.POST.get('insurance_required') == 'on'
        daily_meal_allowance = request.POST.get('daily_meal_allowance')
        expense_report_deadline = request.POST.get('expense_report_deadline', 30)
        requires_receipts = request.POST.get('requires_receipts') == 'on'

        allowed_classes = request.POST.getlist('allowed_classes')
        if not allowed_classes:
            allowed_classes = ['economy']
        preferred_airlines = _parse_csv_list(request.POST.get('preferred_airlines', ''))
        preferred_hotel_chains = _parse_csv_list(request.POST.get('preferred_hotel_chains', ''))
        preferred_car_types = _parse_csv_list(request.POST.get('preferred_car_types', ''))
        approval_levels = _parse_csv_list(request.POST.get('approval_levels', ''))

        policy = BusinessTravelPolicy.objects.create(
            business_account=business_account,
            max_flight_cost=max_flight_cost if max_flight_cost else None,
            advance_booking_days=advance_booking_days,
            allowed_classes=allowed_classes,
            preferred_airlines=preferred_airlines,
            max_hotel_cost_per_night=max_hotel_cost_per_night if max_hotel_cost_per_night else None,
            max_star_rating=max_star_rating,
            preferred_hotel_chains=preferred_hotel_chains,
            max_car_rental_cost_per_day=max_car_rental_cost_per_day if max_car_rental_cost_per_day else None,
            preferred_car_types=preferred_car_types,
            insurance_required=insurance_required,
            daily_meal_allowance=daily_meal_allowance if daily_meal_allowance else None,
            expense_report_deadline=expense_report_deadline,
            requires_receipts=requires_receipts,
            approval_levels=approval_levels,
        )

        messages.success(request, "Travel policy created successfully.")
        return redirect('business:policies')

    return redirect('business:policies')


@login_required
def update_policy(request, pk):
    """Update an existing travel policy."""
    business_account, _ = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')

    policy = get_object_or_404(BusinessTravelPolicy, id=pk, business_account=business_account)

    if request.method == 'POST':
        policy.max_flight_cost = request.POST.get('max_flight_cost') or None
        policy.advance_booking_days = request.POST.get('advance_booking_days', 14)
        policy.allowed_classes = request.POST.getlist('allowed_classes') or ['economy']
        policy.preferred_airlines = _parse_csv_list(request.POST.get('preferred_airlines', ''))
        policy.max_hotel_cost_per_night = request.POST.get('max_hotel_cost_per_night') or None
        policy.max_star_rating = request.POST.get('max_star_rating', 4)
        policy.preferred_hotel_chains = _parse_csv_list(request.POST.get('preferred_hotel_chains', ''))
        policy.max_car_rental_cost_per_day = request.POST.get('max_car_rental_cost_per_day') or None
        policy.preferred_car_types = _parse_csv_list(request.POST.get('preferred_car_types', ''))
        policy.insurance_required = request.POST.get('insurance_required') == 'on'
        policy.daily_meal_allowance = request.POST.get('daily_meal_allowance') or None
        policy.expense_report_deadline = request.POST.get('expense_report_deadline', 30)
        policy.requires_receipts = request.POST.get('requires_receipts') == 'on'
        policy.approval_levels = _parse_csv_list(request.POST.get('approval_levels', ''))

        policy.save()
        messages.success(request, "Travel policy updated successfully.")
        return redirect('business:policies')

    return redirect('business:policies')


@login_required
def expense_list(request):
    """View expense reports."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    expense_reports_list = BusinessExpenseReport.objects.filter(
        business_account=business_account
    ).select_related('employee__user', 'approver').prefetch_related('items').order_by('-created_at')
    
    # Pagination
    paginator = Paginator(expense_reports_list, 10)
    page_number = request.GET.get('page')
    expense_reports = paginator.get_page(page_number)
    
    # Calculate totals
    pending_total = expense_reports_list.filter(status='submitted').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    approved_total = expense_reports_list.filter(status='approved').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    paid_total = expense_reports_list.filter(status='paid').aggregate(
        total=Sum('total_amount')
    )['total'] or 0
    
    pending_count = expense_reports_list.filter(status='submitted').count()
    approved_count = expense_reports_list.filter(status='approved').count()
    paid_count = expense_reports_list.filter(status='paid').count()
    
    avg_amount = expense_reports_list.aggregate(avg=Avg('total_amount'))['avg'] or 0
    
    context = {
        'business_account': business_account,
        'expense_reports': expense_reports,
        'pending_total': pending_total,
        'approved_total': approved_total,
        'paid_total': paid_total,
        'pending_count': pending_count,
        'approved_count': approved_count,
        'paid_count': paid_count,
        'avg_amount': avg_amount,
    }
    
    return render(request, 'business/expenses.html', context)


@login_required
def create_expense(request):
    """Create a new expense report."""
    if request.method == 'POST':
        business_account = getattr(request.user, 'business_account', None)
        if not business_account:
            messages.error(request, "You don't have a business account.")
            return redirect('business:business_dashboard')
        
        # Get employee record for current user
        try:
            employee = BusinessEmployee.objects.get(business_account=business_account, user=request.user)
        except BusinessEmployee.DoesNotExist:
            messages.error(request, "You are not registered as an employee.")
            return redirect('business:expenses')
        
        title = request.POST.get('title')
        start_date = request.POST.get('start_date')
        end_date = request.POST.get('end_date')
        description = request.POST.get('description')
        submit_for_approval = request.POST.get('submit_for_approval') == 'on'
        
        if not title or not start_date or not end_date:
            messages.error(request, "Title, start date, and end date are required.")
            return redirect('business:expenses')
        
        # Create report
        report = BusinessExpenseReport(
            business_account=business_account,
            employee=employee,
            title=title,
            description=description,
            start_date=start_date,
            end_date=end_date,
            total_amount=0,  # Will be updated when items are added
            status='draft' if not submit_for_approval else 'submitted'
        )
        report.save()  # This generates the report number
        
        # Process expense items
        total = 0
        i = 1
        while request.POST.get(f'item_date_{i}'):
            item_date = request.POST.get(f'item_date_{i}')
            item_category = request.POST.get(f'item_category_{i}')
            item_description = request.POST.get(f'item_description_{i}')
            item_amount = request.POST.get(f'item_amount_{i}')
            
            if item_date and item_category and item_description and item_amount:
                item = ExpenseItem(
                    expense_report=report,
                    date=item_date,
                    category=item_category,
                    description=item_description,
                    amount=item_amount,
                    converted_amount=item_amount  # Assuming same currency
                )
                
                # Handle receipt upload
                if f'item_receipt_{i}' in request.FILES:
                    item.receipt_image = request.FILES[f'item_receipt_{i}']
                
                item.save()
                total += float(item_amount)
            
            i += 1
        
        # Update report total
        report.total_amount = total
        report.save()
        
        if submit_for_approval:
            report.submitted_at = timezone.now()
            report.save()
            messages.success(request, "Expense report submitted for approval.")
        else:
            messages.success(request, "Expense report saved as draft.")
        
        return redirect('business:expenses')
    
    return redirect('business:expenses')


@login_required
def expense_detail(request, pk):
    """View a single expense report."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    report = get_object_or_404(BusinessExpenseReport, id=pk, business_account=business_account)
    items = report.items.all()
    
    context = {
        'business_account': business_account,
        'report': report,
        'items': items,
    }
    
    return render(request, 'business/expense_detail.html', context)


@login_required
def edit_expense(request, pk):
    """Edit an expense report."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    report = get_object_or_404(BusinessExpenseReport, id=pk, business_account=business_account)
    
    # Only allow editing drafts or rejected reports
    if report.status not in ['draft', 'rejected']:
        messages.error(request, "This report cannot be edited.")
        return redirect('business:expense_detail', pk=pk)
    
    if request.method == 'POST':
        report.title = request.POST.get('title')
        report.description = request.POST.get('description')
        report.start_date = request.POST.get('start_date')
        report.end_date = request.POST.get('end_date')
        report.save()
        
        messages.success(request, "Expense report updated.")
        return redirect('business:expense_detail', pk=pk)
    
    return redirect('business:expense_detail', pk=pk)


@login_required
def approve_expense(request, pk):
    """Approve an expense report."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    report = get_object_or_404(BusinessExpenseReport, id=pk, business_account=business_account)
    
    if report.status != 'submitted':
        messages.error(request, "This report cannot be approved.")
        return redirect('business:expense_detail', pk=pk)
    
    report.status = 'approved'
    report.approver = request.user
    report.approval_date = timezone.now()
    report.approved_amount = report.total_amount
    report.save()
    
    messages.success(request, "Expense report approved.")
    return redirect('business:expenses')


@login_required
def export_expenses(request):
    """Export expense reports to CSV."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        return HttpResponse("No business account", status=400)
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="expense_reports.csv"'
    
    writer = csv.writer(response)
    writer.writerow(['Report Number', 'Employee', 'Title', 'Total Amount', 'Status', 'Submitted Date'])
    
    reports = BusinessExpenseReport.objects.filter(
        business_account=business_account
    ).select_related('employee__user')
    
    for report in reports:
        writer.writerow([
            report.report_number,
            report.employee.user.email,
            report.title,
            report.total_amount,
            report.status,
            report.submitted_at.strftime('%Y-%m-%d') if report.submitted_at else ''
        ])
    
    return response


@login_required
def approval_list(request):
    """View booking approvals."""
    business_account, employee = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    can_approve = _user_can_approve_for_account(request.user, business_account, employee)
    
    if can_approve:
        # Account owner/admins can view all approvals; delegated approvers see assigned requests.
        if request.user.is_staff or request.user.is_superuser or business_account.user_id == request.user.id:
            approvals = BusinessBookingApproval.objects.filter(
                business_account=business_account
            )
        else:
            approvals = BusinessBookingApproval.objects.filter(
                business_account=business_account,
                approver=request.user,
            )
    else:
        approvals = BusinessBookingApproval.objects.filter(
            business_account=business_account,
            employee__user=request.user
        )
    
    approvals = approvals.select_related(
        'employee__user',
        'approver',
        'booking__property',
        'flight_booking__flight_schedule__flight__origin',
        'flight_booking__flight_schedule__flight__destination',
        'car_rental_booking__pickup_location',
        'car_rental_booking__dropoff_location',
        'tour_booking__tour',
    ).order_by('-created_at')
    
    # Filter by department if specified
    department_id = request.GET.get('department')
    if department_id:
        approvals = approvals.filter(employee__department_id=department_id)
    
    # Calculate stats
    pending_count = approvals.filter(status='pending').count()
    urgent_count = approvals.filter(
        status='pending',
        created_at__lt=timezone.now() - timedelta(hours=24)
    ).count()
    
    approved_today = approvals.filter(
        status='approved',
        decision_date__date=timezone.now().date()
    ).count()
    
    approved_count = approvals.filter(status='approved').count()
    rejected_count = approvals.filter(status='rejected').count()
    
    # Calculate average response time for approved/rejected
    completed = approvals.filter(status__in=['approved', 'rejected'], decision_date__isnull=False)
    
    total_response_time = 0
    count = 0
    for approval in completed:
        if approval.decision_date and approval.created_at:
            response_time = (approval.decision_date - approval.created_at).total_seconds() / 3600
            total_response_time += response_time
            count += 1
    
    avg_response_hours = round(total_response_time / count, 1) if count > 0 else 0
    
    approval_rate = round((approved_count / (approved_count + rejected_count) * 100), 1) if (approved_count + rejected_count) > 0 else 0
    week_ago = timezone.now() - timedelta(days=7)
    this_week_approved = approvals.filter(
        status='approved',
        decision_date__gte=week_ago
    ).count()

    top_approver_data = approvals.filter(
        status='approved',
        approver__isnull=False
    ).values(
        'approver__first_name',
        'approver__last_name',
        'approver__email'
    ).annotate(
        total=Count('id')
    ).order_by('-total').first()

    if top_approver_data:
        top_approver_name = (
            f"{top_approver_data.get('approver__first_name', '')} "
            f"{top_approver_data.get('approver__last_name', '')}"
        ).strip() or top_approver_data.get('approver__email', 'N/A')
        top_approver_count = top_approver_data.get('total', 0)
    else:
        top_approver_name = 'N/A'
        top_approver_count = 0
    
    # Get departments for filter
    departments = BusinessDepartment.objects.filter(
        business_account=business_account,
        is_active=True
    )
    
    # Get recent approved for sidebar
    recent_approved = approvals.filter(status='approved')[:5]
    
    # Get approvers for escalation
    approvers = BusinessEmployee.objects.filter(
        business_account=business_account,
        can_approve=True,
        is_active=True
    ).select_related('user')
    
    # Separate pending and other statuses
    pending_approvals = approvals.filter(status='pending')
    policy = BusinessTravelPolicy.objects.filter(business_account=business_account).first()
    
    context = {
        'business_account': business_account,
        'pending_approvals': pending_approvals,
        'recent_approved': recent_approved,
        'pending_count': pending_count,
        'urgent_count': urgent_count,
        'approved_today': approved_today,
        'avg_response_time': avg_response_hours,
        'approval_rate': approval_rate,
        'departments': departments,
        'approvers': approvers,
        'can_approve': can_approve,
        'selected_department': str(department_id or ''),
        'this_week_approved': this_week_approved,
        'top_approver_name': top_approver_name,
        'top_approver_count': top_approver_count,
        'policy': policy,
    }
    
    return render(request, 'business/approval.html', context)


@login_required
def approval_detail(request, pk):
    """View a single approval request."""
    business_account, employee = _resolve_business_context(request.user)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    approval = get_object_or_404(
        BusinessBookingApproval.objects.select_related(
            'employee__user',
            'approver',
            'booking__property',
            'flight_booking__flight_schedule__flight__origin',
            'flight_booking__flight_schedule__flight__destination',
            'car_rental_booking__pickup_location',
            'car_rental_booking__dropoff_location',
            'tour_booking__tour',
        ),
        id=pk,
        business_account=business_account
    )
    can_approve = _user_can_approve_for_account(request.user, business_account, employee)
    can_view = can_approve or approval.employee.user_id == request.user.id or approval.approver_id == request.user.id
    if not can_view:
        messages.error(request, "You are not authorized to view this approval request.")
        return redirect('business:approvals')
    can_override = request.user.is_staff or request.user.is_superuser or business_account.user_id == request.user.id
    can_act = approval.status == 'pending' and (
        approval.approver_id == request.user.id or (can_override and can_approve)
    )
    
    # Create approval chain for display
    approval_chain = []
    
    # Add current level
    approval_chain.append({
        'role': f'Level {approval.approval_level} Approver',
        'approver': approval.approver,
        'status': approval.status,
        'date': approval.decision_date,
        'notes': approval.decision_notes
    })
    
    # You can add more levels based on your business logic
    
    context = {
        'business_account': business_account,
        'approval': approval,
        'approval_chain': approval_chain,
        'can_act': can_act,
        'approvers': BusinessEmployee.objects.filter(
            business_account=business_account,
            can_approve=True,
            is_active=True
        ).select_related('user')
    }
    
    return render(request, 'business/approve_detail.html', context)


@login_required
def approve_booking(request, pk):
    """Approve a booking request."""
    if request.method == 'POST':
        business_account, employee = _resolve_business_context(request.user)
        if not business_account:
            return JsonResponse({'error': 'No business account'}, status=400)
        
        approval = get_object_or_404(BusinessBookingApproval, id=pk, business_account=business_account)
        
        # Primary approver can act; business account owner/admin can override.
        can_override = request.user.is_staff or request.user.is_superuser or approval.business_account.user_id == request.user.id
        if approval.approver != request.user and not (can_override and _user_can_approve_for_account(request.user, business_account, employee)):
            messages.error(request, "You are not authorized to approve this booking.")
            return redirect('business:approvals')
        
        notes = request.POST.get('notes', '')
        
        approval.status = 'approved'
        approval.decision_notes = notes
        approval.decision_date = timezone.now()
        approval.save()
        
        messages.success(request, "Booking approved successfully.")
        return redirect('business:approvals')
    
    return redirect('business:approvals')


@login_required
def reject_booking(request, pk):
    """Reject a booking request."""
    if request.method == 'POST':
        business_account, employee = _resolve_business_context(request.user)
        if not business_account:
            return JsonResponse({'error': 'No business account'}, status=400)
        
        approval = get_object_or_404(BusinessBookingApproval, id=pk, business_account=business_account)
        
        can_override = request.user.is_staff or request.user.is_superuser or approval.business_account.user_id == request.user.id
        if approval.approver != request.user and not (can_override and _user_can_approve_for_account(request.user, business_account, employee)):
            messages.error(request, "You are not authorized to reject this booking.")
            return redirect('business:approvals')
        
        notes = request.POST.get('notes', '')
        
        approval.status = 'rejected'
        approval.decision_notes = notes
        approval.decision_date = timezone.now()
        approval.save()
        
        messages.success(request, "Booking rejected.")
        return redirect('business:approvals')
    
    return redirect('business:approvals')


@login_required
def escalate_booking(request, pk):
    """Escalate a booking request to a higher approver."""
    if request.method == 'POST':
        business_account, employee = _resolve_business_context(request.user)
        if not business_account:
            return JsonResponse({'error': 'No business account'}, status=400)
        
        approval = get_object_or_404(BusinessBookingApproval, id=pk, business_account=business_account)
        
        can_override = request.user.is_staff or request.user.is_superuser or approval.business_account.user_id == request.user.id
        if approval.approver != request.user and not (can_override and _user_can_approve_for_account(request.user, business_account, employee)):
            messages.error(request, "You are not authorized to escalate this booking.")
            return redirect('business:approvals')
        
        escalate_to_id = request.POST.get('escalate_to')
        notes = request.POST.get('notes', '')
        
        if not escalate_to_id:
            messages.error(request, "Please select an approver to escalate to.")
            return redirect('business:approvals')
        
        escalate_employee = BusinessEmployee.objects.filter(
            business_account=business_account,
            can_approve=True,
            is_active=True,
        ).filter(
            Q(user_id=escalate_to_id) | Q(id=escalate_to_id)
        ).select_related('user').first()
        if not escalate_employee:
            messages.error(request, "Selected approver not found in this business account.")
            return redirect('business:approvals')
        escalate_to = escalate_employee.user
        if escalate_to.id == approval.approver_id:
            messages.error(request, "Selected approver is already assigned to this request.")
            return redirect('business:approvals')
        
        approval.status = 'escalated'
        approval.escalated_to = escalate_to
        approval.escalation_reason = notes
        approval.save()
        
        # Create new approval for escalated user
        BusinessBookingApproval.objects.create(
            business_account=approval.business_account,
            employee=approval.employee,
            approver=escalate_to,
            booking=approval.booking,
            flight_booking=approval.flight_booking,
            car_rental_booking=approval.car_rental_booking,
            tour_booking=approval.tour_booking,
            approval_level=approval.approval_level + 1
        )
        
        messages.success(request, f"Booking escalated to {escalate_to.get_full_name()}")
        return redirect('business:approvals')
    
    return redirect('business:approvals')


@login_required
def impersonate_employee(request, employee_id):
    """Impersonate an employee (admin only)."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        messages.error(request, "You don't have a business account.")
        return redirect('business:business_dashboard')
    
    # Check if user has admin privileges
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, "Not authorized to impersonate.")
        return redirect('business:employees')
    
    employee = get_object_or_404(BusinessEmployee, id=employee_id, business_account=business_account)
    
    # Store original user in session
    request.session['impersonate_id'] = request.user.id
    request.session['original_user'] = request.user.email
    
    # Log in as employee user
    from django.contrib.auth import login
    login(request, employee.user)
    
    messages.success(request, f"You are now viewing as {employee.user.get_full_name()}")
    return redirect('business:business_dashboard')
