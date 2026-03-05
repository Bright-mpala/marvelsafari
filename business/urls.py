from django.urls import path
from . import views

app_name = 'business'

urlpatterns = [
    path('', views.business_dashboard, name='business_dashboard'),
    path('departments/', views.department_list, name='departments'),
    path('departments/create/', views.create_department, name='create_department'),
    path('employees/', views.employee_list, name='employees'),
    path('employees/invite/', views.invite_employee, name='invite_employee'),
    path('employees/export/', views.export_employees, name='export_employees'),
    path('policies/', views.policy_list, name='policies'),
    path('policies/create/', views.create_policy, name='create_policy'),
    path('policies/<int:pk>/update/', views.update_policy, name='update_policy'),
    path('expenses/', views.expense_list, name='expenses'),
    path('expenses/create/', views.create_expense, name='create_expense'),
    path('expenses/<uuid:pk>/', views.expense_detail, name='expense_detail'),
    path('expenses/<uuid:pk>/edit/', views.edit_expense, name='edit_expense'),
    path('expenses/<uuid:pk>/approve/', views.approve_expense, name='approve_expense'),
    path('expenses/export/', views.export_expenses, name='export_expenses'),
    path('approvals/', views.approval_list, name='approvals'),
    path('approvals/<uuid:pk>/', views.approval_detail, name='approval_detail'),
    path('approvals/<uuid:pk>/approve/', views.approve_booking, name='approve_booking'),
    path('approvals/<uuid:pk>/reject/', views.reject_booking, name='reject_booking'),
    path('approvals/<uuid:pk>/escalate/', views.escalate_booking, name='escalate_booking'),
    path('impersonate/<int:employee_id>/', views.impersonate_employee, name='impersonate_employee'),
]