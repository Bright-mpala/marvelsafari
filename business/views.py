from django.shortcuts import render
from django.contrib.auth.decorators import login_required
from django.db.models import Sum

from .models import BusinessBookingApproval, BusinessDepartment, BusinessEmployee

@login_required
def business_dashboard(request):
    """Business dashboard with core operational metrics."""
    business_account = getattr(request.user, 'business_account', None)
    if not business_account:
        return render(request, 'business/dashboard.html', {'business_account': None})

    departments = BusinessDepartment.objects.filter(
        business_account=business_account,
        is_active=True,
    )
    employees = BusinessEmployee.objects.filter(
        business_account=business_account,
        is_active=True,
    )
    approvals = BusinessBookingApproval.objects.filter(
        business_account=business_account,
    ).select_related('employee__user', 'approver').order_by('-created_at')

    approved_spend = approvals.filter(status='approved').aggregate(
        total=Sum('booking__total_amount')
    )['total'] or 0

    context = {
        'business_account': business_account,
        'departments': departments[:6],
        'employees': employees[:8],
        'recent_approvals': approvals[:10],
        'pending_approvals': approvals.filter(status='pending').count(),
        'approved_approvals': approvals.filter(status='approved').count(),
        'rejected_approvals': approvals.filter(status='rejected').count(),
        'approved_spend': approved_spend,
    }
    return render(request, 'business/dashboard.html', context)
