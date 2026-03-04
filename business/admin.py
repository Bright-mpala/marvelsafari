from django.contrib import admin
from .models import (
    BusinessDepartment, BusinessEmployee, BusinessTravelPolicy,
    BusinessBookingApproval, BusinessExpenseReport, ExpenseItem, BusinessDashboard
)
from travel_booking.admin import admin_site

@admin.register(BusinessDepartment, site=admin_site)
class BusinessDepartmentAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'name', 'manager', 'is_active')
    search_fields = ('business_account__company_name', 'name', 'manager__email')


@admin.register(BusinessEmployee, site=admin_site)
class BusinessEmployeeAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'user', 'employee_id', 'job_title', 'is_active')
    list_filter = ('business_account', 'is_active')
    search_fields = ('business_account__company_name', 'user__email', 'employee_id', 'job_title')


@admin.register(BusinessTravelPolicy, site=admin_site)
class BusinessTravelPolicyAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'max_flight_cost', 'max_hotel_cost_per_night', 'max_car_rental_cost_per_day')
    search_fields = ('business_account__company_name',)


@admin.register(BusinessBookingApproval, site=admin_site)
class BusinessBookingApprovalAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'employee', 'status', 'decision_date')
    list_filter = ('status', 'decision_date')
    search_fields = ('business_account__company_name', 'employee__user__email')


@admin.register(BusinessExpenseReport, site=admin_site)
class BusinessExpenseReportAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'employee', 'title', 'total_amount', 'status', 'submitted_at')
    list_filter = ('status', 'submitted_at')
    search_fields = ('business_account__company_name', 'employee__user__email', 'title')


@admin.register(ExpenseItem, site=admin_site)
class ExpenseItemAdmin(admin.ModelAdmin):
    list_display = ('expense_report', 'description', 'amount', 'category', 'date')
    list_filter = ('category', 'date')
    search_fields = ('expense_report__employee__user__email', 'description')


@admin.register(BusinessDashboard, site=admin_site)
class BusinessDashboardAdmin(admin.ModelAdmin):
    list_display = ('business_account', 'total_spent', 'total_bookings', 'active_travelers', 'last_updated')
    search_fields = ('business_account__company_name',)
    readonly_fields = ('last_updated',)
